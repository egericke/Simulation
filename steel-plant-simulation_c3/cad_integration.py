import salabim as sim
import logging
import os
import math
import subprocess
import tempfile
import msgpack  # Faster caching alternative to pickle
import hashlib  # Added import
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QImage, QPixmap
import xml.etree.ElementTree as ET

# Optional DXF support
try:
    import ezdxf
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False
    logging.warning("ezdxf library not found. DXF support will be limited.")

# Optional PDF support
try:
    import fitz  # PyMuPDF for PDF handling
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logging.warning("PyMuPDF library not found. PDF support will be limited.")

# Optional CAD conversion support
try:
    from oda_file_converter import convert_cad_to_dxf
    ODA_AVAILABLE = True
except ImportError:
    ODA_AVAILABLE = False
    logging.warning("ODA File Converter not found. CAD conversion will be limited.")

logger = logging.getLogger(__name__)

class CADBackground:
    """
    Handles loading and displaying CAD backgrounds for the simulation with optimized performance.
    Supports DXF, SVG, CAD/DWG (via conversion), and PDF files, with caching and layer management.
    """
    def __init__(self, env, layer_manager, config=None, parent_widget=None):
        self.env = env
        self.layer_manager = layer_manager
        self.config = config or {}
        self.cad_elements = {}  # Elements organized by layer
        self.cad_file_path = self.config.get("cad_file_path", None)
        self.background_image = self.config.get("background_image", None)
        self.scale = self.config.get("cad_scale", 1.0)
        self.x_offset = self.config.get("cad_x_offset", 0)
        self.y_offset = self.config.get("cad_y_offset", 0)
        self.parent_widget = parent_widget
        self.layers = {}  # Store layer info
        self.visible_layers = self.config.get("cad_visible_layers", [])  # Empty means all visible
        self.simplify_options = self.config.get("simplify_options", {})  # User-controlled simplification

        # PDF specific parameters
        self.pdf_real_width = self.config.get("pdf_real_width", 100.0)  # Real-world width in meters
        self.pdf_real_height = self.config.get("pdf_real_height", 100.0)  # Real-world height in meters
        self.temp_image_path = None  # Path to temporary image file for PDF rendering

        # Grid defaults
        self.grid_size = self.config.get("grid_size", 100)
        self.grid_width = self.config.get("grid_width", 1000)
        self.grid_height = self.config.get("grid_height", 1000)

        # Caching setup
        self.cache_dir = os.path.join(tempfile.gettempdir(), "steel_plant_sim_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_enabled = self.config.get("cad_cache_enabled", True)
        self.cached_files = {}

        # Initialize background
        self.create_background()

    def create_background(self):
        """Create background based on config with fallback."""
        try:
            if self.cad_file_path and os.path.exists(self.cad_file_path):
                # Check if it's a PDF file
                if self.cad_file_path.lower().endswith('.pdf'):
                    self.load_pdf_file()
                else:
                    self.load_cad_file()
            else:
                self.create_grid()
                logger.info("No CAD file provided. Using grid fallback.")
        except Exception as e:
            logger.error(f"Error creating background: {e}")
            self.create_grid()  # Fallback to grid if loading fails

    def load_pdf_file(self):
        """Load PDF file as background with proper scaling."""
        if not PYMUPDF_AVAILABLE:
            logger.error("PyMuPDF not available. Cannot load PDF.")
            self.create_grid()
            return

        try:
            logger.info(f"Loading PDF file: {self.cad_file_path}")
            
            # Clear existing elements if any
            for layer_name, elements in self.cad_elements.items():
                for element in elements:
                    element.remove()
            self.cad_elements = {}
            self.layers = {}

            # Calculate scale based on real-world dimensions
            if self.config.get("auto_scale_cad", True):
                self.calculate_pdf_scale()
                logger.info(f"Auto-detected PDF scale: {self.scale}")

            # Load the PDF using PyMuPDF
            doc = fitz.open(self.cad_file_path)
            if doc.page_count == 0:
                logger.error("PDF file contains no pages")
                self.create_grid()
                return

            # Get the first page and render it at a reasonable resolution
            page = doc.load_page(0)
            
            # Check if rotation is needed
            page_rect = page.rect
            rotation = 0
            if page_rect.width < page_rect.height:
                rotation = 90  # Apply 90-degree rotation for portrait PDFs
                logger.info("Portrait PDF detected, rotating...")
                
            resolution = 2.0  # Increase for higher quality
            matrix = fitz.Matrix(resolution, resolution).prerotate(rotation)
            pix = page.get_pixmap(matrix=matrix)
            
            # Save to a temporary file
            if self.temp_image_path and os.path.exists(self.temp_image_path):
                try:
                    os.remove(self.temp_image_path)
                except:
                    pass
                    
            self.temp_image_path = os.path.join(tempfile.gettempdir(), f"pdf_background_{hash(self.cad_file_path)}.png")
            pix.save(self.temp_image_path)
            
            # Calculate dimensions
            img_width = pix.width
            img_height = pix.height
            
            # Calculate the aspect ratio of the PDF
            pdf_aspect = img_width / img_height
            
            # Calculate the target dimensions based on real-world dimensions and scale
            target_width = self.pdf_real_width * self.scale
            target_height = self.pdf_real_height * self.scale
            
            # Center the image on the grid
            x_offset = (self.grid_width - target_width) / 2
            y_offset = (self.grid_height - target_height) / 2
            
            # Create the background image using Salabim's Animate class (not AnimateImage)
            bg_layer = self.layer_manager.get_layer("Background")
            
            # Create image using Animate with proper parameters
            image_obj = sim.Animate(
                image=self.temp_image_path,  # Path to the image
                x0=x_offset + self.x_offset,  # X position
                y0=y_offset + self.y_offset,  # Y position
                width0=target_width,          # Target width
                height0=target_height,        # Target height
                env=self.env                  # Simulation environment
            )
            
            self.cad_elements.setdefault("pdf_background", []).append(image_obj)
            bg_layer.add_object(image_obj)
            self.layers["pdf_background"] = True
            
            # Add a grid on top for reference
            self.add_grid_overlay(x_offset + self.x_offset, y_offset + self.y_offset, target_width, target_height)
            
            # Add bay markers for context
            self.add_bay_markers()
            
            logger.info(f"PDF loaded successfully with dimensions {target_width}x{target_height}")
            doc.close()
            
        except Exception as e:
            logger.error(f"Failed to load PDF file: {e}", exc_info=True)
            self.create_grid()

    def add_grid_overlay(self, x, y, width, height):
        """Add a grid overlay on top of the PDF background."""
        grid_size = self.config.get("grid_size", 100)
        grid_layer = self.layer_manager.get_layer("Background")
        
        # Horizontal grid lines
        for i in range(0, int(height) + 1, grid_size):
            y_pos = y + i
            line = sim.AnimateLine(
                spec=(x, y_pos, x + width, y_pos),
                linecolor='lightblue',
                linewidth=0.5,
                env=self.env
            )
            grid_layer.add_object(line)
            self.cad_elements.setdefault("grid_overlay", []).append(line)
        
        # Vertical grid lines
        for i in range(0, int(width) + 1, grid_size):
            x_pos = x + i
            line = sim.AnimateLine(
                spec=(x_pos, y, x_pos, y + height),
                linecolor='lightblue',
                linewidth=0.5,
                env=self.env
            )
            grid_layer.add_object(line)
            self.cad_elements.setdefault("grid_overlay", []).append(line)

    def add_bay_markers(self):
        bays = self.config.get("bays", {})
        bay_layer = self.layer_manager.get_layer("Background")
        
        for bay_name, bay_pos in bays.items():
            x = bay_pos.get("x_offset", 0)
            y = bay_pos.get("y_offset", 0)
        
           
            # Create rectangle outline for the bay
            width = bay_pos.get("width", 200)
            height = bay_pos.get("height", 200)
            
            # Top line
            top_line = sim.AnimateLine(
                spec=(x, y, x + width, y),
                linecolor='red',
                linewidth=2,
                env=self.env
            )
            bay_layer.add_object(top_line)
            self.cad_elements.setdefault("bay_markers", []).append(top_line)
            
            # Bottom line
            bottom_line = sim.AnimateLine(
                spec=(x, y + height, x + width, y + height),
                linecolor='red',
                linewidth=2,
                env=self.env
            )
            bay_layer.add_object(bottom_line)
            self.cad_elements.setdefault("bay_markers", []).append(bottom_line)
            
            # Left line
            left_line = sim.AnimateLine(
                spec=(x, y, x, y + height),
                linecolor='red',
                linewidth=2,
                env=self.env
            )
            bay_layer.add_object(left_line)
            self.cad_elements.setdefault("bay_markers", []).append(left_line)
            
            # Right line
            right_line = sim.AnimateLine(
                spec=(x + width, y, x + width, y + height),
                linecolor='red',
                linewidth=2,
                env=self.env
            )
            bay_layer.add_object(right_line)
            self.cad_elements.setdefault("bay_markers", []).append(right_line)
            
            text = sim.Animate(
                        text=bay_name,
                        x0=x + 10,
                        y0=y + 10,
                        textcolor0='red',  # Changed from text_color to textcolor0
                        fontsize0=12,
                        env=self.env
                    )
            bay_layer.add_object(text)
            self.cad_elements.setdefault("bay_markers", []).append(text)

    def calculate_pdf_scale(self):
        """Calculate the optimal scale to fit the PDF based on real-world dimensions."""
        try:
            # Calculate scale based on grid size and real-world dimensions
            grid_width = self.grid_width * 0.8  # Use 80% of grid width
            grid_height = self.grid_height * 0.8  # Use 80% of grid height
            
            # Determine scaling factors for width and height
            scale_x = grid_width / self.pdf_real_width
            scale_y = grid_height / self.pdf_real_height
            
            # Use the smaller scale to ensure the entire PDF fits
            self.scale = min(scale_x, scale_y)
            
            # Update offsets to center the PDF
            self.x_offset = (self.grid_width - (self.pdf_real_width * self.scale)) / 2
            self.y_offset = (self.grid_height - (self.pdf_real_height * self.scale)) / 2
            
            logger.info(f"PDF scale calculated: {self.scale} (x_offset: {self.x_offset}, y_offset: {self.y_offset})")
        except Exception as e:
            logger.error(f"Error calculating PDF scale: {e}")
            # Default to a reasonable scale
            self.scale = 1.0
            self.x_offset = 0
            self.y_offset = 0

    def generate_cad_elements(self):
        """Generator yielding batches of CAD elements for progressive loading."""
        extension = os.path.splitext(self.cad_file_path)[1].lower()
        if extension == '.dxf':
            for batch in self.generate_dxf_elements():
                yield batch
        elif extension == '.svg':
            for batch in self.generate_svg_elements():
                yield batch
        elif extension in ['.dwg', '.cad']:
            if self.convert_cad_to_dxf():
                for batch in self.generate_dxf_elements():
                    yield batch
            else:
                logger.error("CAD conversion failed. Falling back to grid.")
                return
        else:
            logger.warning(f"Unsupported format: {extension}")
            return

    # Rest of the existing methods remain the same...
    # I'm including just the methods that were modified for PDF support
    # and keeping all other methods intact

    def load_cad_file(self):
        """Load CAD file with caching and progressive addition."""
        if not self.cad_file_path:
            logger.warning("No CAD file specified")
            return

        try:
            logger.info(f"Loading CAD file: {self.cad_file_path}")
            
            # Special handling for PDF files
            if self.cad_file_path.lower().endswith('.pdf'):
                self.load_pdf_file()
                return
                
            if self.config.get("auto_scale_cad", True):
                self.scale = self.determine_optimal_scale()
                logger.info(f"Auto-detected scale: {self.scale}")

            # Optimization 4: Check cache first
            cache_path = self.get_cache_path()
            if cache_path and self.load_from_cache(cache_path):
                logger.info("Loaded from cache successfully")
                return

            # Clear existing elements
            for layer_name, elements in self.cad_elements.items():
                for element in elements:
                    element.remove()
            self.cad_elements = {}
            self.layers = {}

            # Optimization 1 & 8: Progressive loading and batch rendering
            bg_layer = self.layer_manager.get_layer("Background")
            entity_count = 0
            for batch in self.generate_cad_elements():
                for animate, layer_name in batch:
                    bg_layer.add_object(animate)
                    self.cad_elements.setdefault(layer_name, []).append(animate)
                    self.layers[layer_name] = True
                    entity_count += 1
                logger.debug(f"Added batch of {len(batch)} elements")
            
            logger.info(f"Loaded {entity_count} CAD elements")
            if entity_count == 0:
                self.create_grid()
            elif cache_path:
                self.save_to_cache(cache_path)
        except Exception as e:
            logger.error(f"Failed to load CAD file: {e}", exc_info=True)
            self.create_grid()



    def generate_dxf_elements(self):
        """Generate DXF elements in batches with optimized parsing."""
        if not EZDXF_AVAILABLE:
            logger.warning("ezdxf not available. Falling back to simple parser.")
            for batch in self.generate_dxf_elements_simple():
                yield batch
            return

        try:
            doc = ezdxf.readfile(self.cad_file_path)
            msp = doc.modelspace()
            # Optimization 2: Filter relevant entity types only
            supported_types = ['LINE', 'CIRCLE', 'ARC', 'LWPOLYLINE']
            query_string = ' or '.join(supported_types)
            if self.visible_layers:
                layer_query = 'Layer in {}'.format(list(self.visible_layers))
                query = msp.query(f'({query_string}) and ({layer_query})')
            else:
                query = msp.query(query_string)

            batch_size = 1000  # Adjustable for performance
            batch = []
            for entity in query:
                try:
                    animate, layer_name = self.create_animate_from_entity(entity)
                    if animate:
                        batch.append((animate, layer_name))
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
                except Exception as e:
                    logger.warning(f"Skipping problematic entity: {e}")
            if batch:
                yield batch
        except Exception as e:
            logger.error(f"DXF parsing error: {e}")
            return

    def generate_dxf_elements_simple(self):
        """Fallback generator for DXF without ezdxf."""
        try:
            with open(self.cad_file_path, 'r') as f:
                dxf_text = f.readlines()
            
            batch_size = 1000
            batch = []
            entity_count = 0
            current_layer = "0"
            i = 0
            while i < len(dxf_text):
                line = dxf_text[i].strip()
                if line == "8" and i+1 < len(dxf_text):
                    current_layer = dxf_text[i+1].strip()
                
                if self.visible_layers and current_layer not in self.visible_layers:
                    i += 1
                    continue
                
                if line in ["LINE", "CIRCLE"]:
                    entity_data = {}
                    for j in range(50):
                        if i+j >= len(dxf_text):
                            break
                        code = dxf_text[i+j].strip()
                        if code.isdigit() and i+j+1 < len(dxf_text):
                            try:
                                value = float(dxf_text[i+j+1].strip())
                                entity_data[int(code)] = value
                            except ValueError:
                                pass
                    
                    color = self._get_color_from_entity(entity_data)
                    animate = None
                    if line == "LINE" and all(k in entity_data for k in [10, 20, 11, 21]):
                        x1 = entity_data[10] * self.scale + self.x_offset
                        y1 = entity_data[20] * self.scale + self.y_offset
                        x2 = entity_data[11] * self.scale + self.x_offset
                        y2 = entity_data[21] * self.scale + self.y_offset
                        animate = sim.AnimateLine(spec=(x1, y1, x2, y2), linecolor=color, linewidth=1, env=self.env)
                    elif line == "CIRCLE" and all(k in entity_data for k in [10, 20, 40]):
                        x = entity_data[10] * self.scale + self.x_offset
                        y = entity_data[20] * self.scale + self.y_offset
                        r = entity_data[40] * self.scale
                        animate = sim.AnimateCircle(radius=r, x0=x, y0=y, fillcolor0="none", linecolor0=color, linewidth0=1, env=self.env)
                    
                    if animate:
                        batch.append((animate, current_layer))
                        entity_count += 1
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
                i += 1
            
            if batch:
                yield batch
            logger.info(f"Simple DXF parser generated {entity_count} elements")
        except Exception as e:
            logger.error(f"Simple DXF parser error: {e}")

    def generate_svg_elements(self):
        """Generate SVG elements in batches."""
        try:
            tree = ET.parse(self.cad_file_path)
            root = tree.getroot()
            ns = {"svg": "http://www.w3.org/2000/svg"}
            batch_size = 1000
            batch = []
            entity_count = 0

            for elem in root.findall(".//svg:line", ns) + root.findall(".//svg:circle", ns):
                try:
                    if elem.tag.endswith("line"):
                        x1 = float(elem.attrib.get('x1', 0)) * self.scale + self.x_offset
                        y1 = float(elem.attrib.get('y1', 0)) * self.scale + self.y_offset
                        x2 = float(elem.attrib.get('x2', 0)) * self.scale + self.x_offset
                        y2 = float(elem.attrib.get('y2', 0)) * self.scale + self.y_offset
                        color = self._svg_color_to_salabim(elem.attrib.get('stroke', 'white'))
                        animate = sim.AnimateLine(spec=(x1, y1, x2, y2), linecolor=color, linewidth=1, env=self.env)
                    elif elem.tag.endswith("circle"):
                        cx = float(elem.attrib.get('cx', 0)) * self.scale + self.x_offset
                        cy = float(elem.attrib.get('cy', 0)) * self.scale + self.y_offset
                        r = float(elem.attrib.get('r', 0)) * self.scale
                        stroke = self._svg_color_to_salabim(elem.attrib.get('stroke', 'white'))
                        animate = sim.AnimateCircle(radius=r, x0=cx, y0=cy, fillcolor0="none", linecolor0=stroke, linewidth0=1, env=self.env)
                    else:
                        continue
                    
                    batch.append((animate, "svg"))
                    entity_count += 1
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
                except Exception as e:
                    logger.warning(f"Skipping SVG element: {e}")
            
            if batch:
                yield batch
            logger.info(f"Generated {entity_count} SVG elements")
        except Exception as e:
            logger.error(f"SVG parsing error: {e}")

    def create_animate_from_entity(self, entity):
        """Create Animate objects from DXF entities with simplification options."""
        layer_name = entity.dxf.layer
        if self.visible_layers and layer_name not in self.visible_layers:
            return None, None
        
        # Optimization 9: Apply user-controlled simplification
        if entity.dxftype() == 'TEXT' and self.simplify_options.get("remove_text", False):
            return None, None
        
        precision = self.simplify_options.get("reduce_precision", None)
        color_map = {1: "red", 2: "yellow", 3: "green", 4: "cyan", 5: "blue", 6: "magenta", 7: "white", 8: "gray", 9: "lightgray"}
        color = color_map.get(entity.dxf.color, "white")

        if entity.dxftype() == 'LINE':
            start_x = round(entity.dxf.start.x, precision) if precision is not None else entity.dxf.start.x
            start_y = round(entity.dxf.start.y, precision) if precision is not None else entity.dxf.start.y
            end_x = round(entity.dxf.end.x, precision) if precision is not None else entity.dxf.end.x
            end_y = round(entity.dxf.end.y, precision) if precision is not None else entity.dxf.end.y
            x1 = start_x * self.scale + self.x_offset
            y1 = start_y * self.scale + self.y_offset
            x2 = end_x * self.scale + self.x_offset
            y2 = end_y * self.scale + self.y_offset
            return sim.AnimateLine(spec=(x1, y1, x2, y2), linecolor=color, linewidth=1, env=self.env), layer_name
        elif entity.dxftype() == 'CIRCLE':
            cx = round(entity.dxf.center.x, precision) if precision is not None else entity.dxf.center.x
            cy = round(entity.dxf.center.y, precision) if precision is not None else entity.dxf.center.y
            r = round(entity.dxf.radius, precision) if precision is not None else entity.dxf.radius
            x = cx * self.scale + self.x_offset
            y = cy * self.scale + self.y_offset
            r_scaled = r * self.scale
            return sim.AnimateCircle(radius=r_scaled, x0=x, y0=y, fillcolor0="none", linecolor0=color, linewidth0=1, env=self.env), layer_name
        elif entity.dxftype() == 'ARC':
            # Simplified arc handling (could be expanded)
            cx = entity.dxf.center.x * self.scale + self.x_offset
            cy = entity.dxf.center.y * self.scale + self.y_offset
            r = entity.dxf.radius * self.scale
            start_angle = math.radians(entity.dxf.start_angle)
            end_angle = math.radians(entity.dxf.end_angle)
            segments = min(max(int(r * abs(end_angle - start_angle) / 10) + 5, 8), 32)
            angle_step = (end_angle - start_angle) / segments
            lines = []
            for i in range(segments):
                a1 = start_angle + i * angle_step
                a2 = start_angle + (i + 1) * angle_step
                x1 = cx + r * math.cos(a1)
                y1 = cy + r * math.sin(a1)
                x2 = cx + r * math.cos(a2)
                y2 = cy + r * math.sin(a2)
                line = sim.AnimateLine(spec=(x1, y1, x2, y2), linecolor=color, linewidth=1, env=self.env)
                lines.append((line, layer_name))
            return lines[0] if lines else None, layer_name  # Return first line for simplicity
        return None, None

    def load_cad_file(self):
        """Load CAD file with caching and progressive addition."""
        if not self.cad_file_path:
            logger.warning("No CAD file specified")
            return

        try:
            logger.info(f"Loading CAD file: {self.cad_file_path}")
            
            # Special handling for PDF files
            if self.cad_file_path.lower().endswith('.pdf'):
                self.load_pdf_file()
                return
                
            if self.config.get("auto_scale_cad", True):
                self.scale = self.determine_optimal_scale()
                logger.info(f"Auto-detected scale: {self.scale}")

            # Optimization 4: Check cache first
            cache_path = self.get_cache_path()
            if cache_path and self.load_from_cache(cache_path):
                logger.info("Loaded from cache successfully")
                return

            # Clear existing elements
            for layer_name, elements in self.cad_elements.items():
                for element in elements:
                    element.remove()
            self.cad_elements = {}
            self.layers = {}

            # Optimization 1 & 8: Progressive loading and batch rendering
            bg_layer = self.layer_manager.get_layer("Background")
            entity_count = 0
            for batch in self.generate_cad_elements():
                for animate, layer_name in batch:
                    bg_layer.add_object(animate)
                    self.cad_elements.setdefault(layer_name, []).append(animate)
                    self.layers[layer_name] = True
                    entity_count += 1
                logger.debug(f"Added batch of {len(batch)} elements")
            
            logger.info(f"Loaded {entity_count} CAD elements")
            if entity_count == 0:
                self.create_grid()
            elif cache_path:
                self.save_to_cache(cache_path)
        except Exception as e:
            logger.error(f"Failed to load CAD file: {e}", exc_info=True)
            self.create_grid()

    def create_grid(self):
        """Generate a simple grid background as fallback."""
        logger.info("Creating grid background")
        try:
            for layer_name, elements in self.cad_elements.items():
                for element in elements:
                    element.remove()
            self.cad_elements = {}
            self.layers = {}
            bg_layer = self.layer_manager.get_layer("Background")
            batch = []
            for x in range(0, self.grid_width + 1, self.grid_size):
                line = sim.AnimateLine(spec=(x, 0, x, self.grid_height), linecolor="lightgray", linewidth=0.5, env=self.env)
                batch.append((line, "grid"))
            for y in range(0, self.grid_height + 1, self.grid_size):
                line = sim.AnimateLine(spec=(0, y, self.grid_width, y), linecolor="lightgray", linewidth=0.5, env=self.env)
                batch.append((line, "grid"))
            for animate, layer_name in batch:
                bg_layer.add_object(animate)
                self.cad_elements.setdefault(layer_name, []).append(animate)
            self.layers["grid"] = True
        except Exception as e:
            logger.error(f"Error creating grid: {e}")

    def determine_optimal_scale(self):
        """Calculate optimal scale to fit CAD file in grid."""
        try:
            if not self.cad_file_path or not os.path.exists(self.cad_file_path):
                return self.scale

            min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
            if self.cad_file_path.lower().endswith('.dxf') and EZDXF_AVAILABLE:
                doc = ezdxf.readfile(self.cad_file_path)
                msp = doc.modelspace()
                for entity in msp.query('LINE CIRCLE ARC'):
                    if entity.dxftype() == 'LINE':
                        min_x = min(min_x, entity.dxf.start.x, entity.dxf.end.x)
                        min_y = min(min_y, entity.dxf.start.y, entity.dxf.end.y)
                        max_x = max(max_x, entity.dxf.start.x, entity.dxf.end.x)
                        max_y = max(max_y, entity.dxf.start.y, entity.dxf.end.y)
                    elif entity.dxftype() == 'CIRCLE':
                        min_x = min(min_x, entity.dxf.center.x - entity.dxf.radius)
                        min_y = min(min_y, entity.dxf.center.y - entity.dxf.radius)
                        max_x = max(max_x, entity.dxf.center.x + entity.dxf.radius)
                        max_y = max(max_y, entity.dxf.center.y + entity.dxf.radius)
                    elif entity.dxftype() == 'ARC':
                        min_x = min(min_x, entity.dxf.center.x - entity.dxf.radius)
                        min_y = min(min_y, entity.dxf.center.y - entity.dxf.radius)
                        max_x = max(max_x, entity.dxf.center.x + entity.dxf.radius)
                        max_y = max(max_y, entity.dxf.center.y + entity.dxf.radius)

            if min_x != float('inf') and max_x != float('-inf'):
                cad_width = max_x - min_x
                cad_height = max_y - min_y
                if cad_width > 0 and cad_height > 0:
                    target_width = self.grid_width * 0.8
                    target_height = self.grid_height * 0.8
                    scale_x = target_width / cad_width
                    scale_y = target_height / cad_height
                    optimal_scale = min(scale_x, scale_y)
                    self.x_offset = (self.grid_width - cad_width * optimal_scale) / 2 - min_x * optimal_scale
                    self.y_offset = (self.grid_height - cad_height * optimal_scale) / 2 - min_y * optimal_scale
                    return optimal_scale
            return self.scale
        except Exception as e:
            logger.error(f"Error determining scale: {e}")
            return self.scale

    def _get_color_from_entity(self, entity_data):
        """Map DXF color index to salabim color."""
        color_map = {1: "red", 2: "yellow", 3: "green", 4: "cyan", 5: "blue", 6: "magenta", 7: "white", 8: "gray", 9: "lightgray", 0: "white"}
        return color_map.get(entity_data.get(62, 7), "white")

    def _svg_color_to_salabim(self, color):
        """Convert SVG color to salabim color."""
        if color == 'none' or not color:
            return "none"
        color_map = {"red": "red", "green": "green", "blue": "blue", "yellow": "yellow", "cyan": "cyan", 
                     "magenta": "magenta", "white": "white", "black": "black", "gray": "gray", "lightgray": "lightgray"}
        if color.lower() in color_map:
            return color_map[color.lower()]
        if color.startswith('#'):
            return color
        if color.startswith('rgb('):
            try:
                rgb = color[4:-1].split(',')
                if len(rgb) == 3:
                    r, g, b = map(int, rgb)
                    return f"#{r:02x}{g:02x}{b:02x}"
            except:
                pass
        return "white"

    def convert_cad_to_dxf(self):
        """Convert CAD file to DXF."""
        try:
            if ODA_AVAILABLE:
                temp_dxf = os.path.join(tempfile.gettempdir(), "converted_temp.dxf")
                if convert_cad_to_dxf(self.cad_file_path, temp_dxf):
                    self.cad_file_path = temp_dxf
                    return True
            return False
        except Exception as e:
            logger.error(f"CAD conversion error: {e}")
            return False

    def get_cache_path(self):
        """Generate cache file path based on file metadata."""
        if not self.cache_enabled or not self.cad_file_path:
            return None
        try:
            file_stat = os.stat(self.cad_file_path)
            cache_key = f"{os.path.basename(self.cad_file_path)}_{file_stat.st_mtime}_{file_stat.st_size}_{self.scale}_{self.x_offset}_{self.y_offset}"
            cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
            return os.path.join(self.cache_dir, f"{cache_hash}.msgpack")
        except Exception as e:
            logger.error(f"Cache path generation error: {e}")
            return None

    def load_from_cache(self, cache_path):
        """Load elements from MessagePack cache."""
        if not cache_path or not os.path.exists(cache_path):
            return False
        try:
            with open(cache_path, 'rb') as f:
                cache_data = msgpack.load(f)
            if not isinstance(cache_data, dict) or 'elements' not in cache_data:
                logger.warning("Invalid cache format")
                return False

            bg_layer = self.layer_manager.get_layer("Background")
            self.cad_elements = {}
            self.layers = {layer: True for layer in cache_data.get('layers', [])}
            entity_count = 0
            for element_data in cache_data['elements']:
                layer_name = element_data.get('layer', 'default')
                self.cad_elements.setdefault(layer_name, [])
                if element_data['type'] == 'line':
                    animate = sim.AnimateLine(
                        spec=element_data['spec'],
                        linecolor=element_data['linecolor'],
                        linewidth=element_data.get('linewidth', 1),
                        env=self.env
                    )
                elif element_data['type'] == 'circle':
                    animate = sim.AnimateCircle(
                        radius=element_data['radius'],
                        x0=element_data['x0'],
                        y0=element_data['y0'],
                        fillcolor0=element_data.get('fillcolor0', 'none'),
                        linecolor0=element_data['linecolor0'],
                        linewidth0=element_data.get('linewidth0', 1),
                        env=self.env
                    )
                else:
                    continue
                bg_layer.add_object(animate)
                self.cad_elements[layer_name].append(animate)
                entity_count += 1
            logger.info(f"Loaded {entity_count} elements from cache")
            return entity_count > 0
        except Exception as e:
            logger.error(f"Cache load error: {e}")
            return False

    def save_to_cache(self, cache_path):
        """Save elements to MessagePack cache."""
        if not self.cache_enabled or not cache_path or not self.cad_elements:
            return False
        try:
            cache_data = {'layers': list(self.layers.keys()), 'elements': []}
            for layer_name, elements in self.cad_elements.items():
                for element in elements:
                    if isinstance(element, sim.AnimateLine):
                        cache_data['elements'].append({
                            'type': 'line',
                            'layer': layer_name,
                            'spec': element.spec,
                            'linecolor': element.linecolor,
                            'linewidth': element.linewidth
                        })
                    elif isinstance(element, sim.AnimateCircle):
                        cache_data['elements'].append({
                            'type': 'circle',
                            'layer': layer_name,
                            'x0': element.x0,
                            'y0': element.y0,
                            'radius': element.radius,
                            'fillcolor0': element.fillcolor0,
                            'linecolor0': element.linecolor0,
                            'linewidth0': element.linewidth0
                        })
            with open(cache_path, 'wb') as f:
                msgpack.dump(cache_data, f)
            logger.info(f"Saved {len(cache_data['elements'])} elements to cache")
            return True
        except Exception as e:
            logger.error(f"Cache save error: {e}")
            return False

    def setup_layer_management(self):
        """
        Configure layer visibility toggling with a fallback mechanism.
        Integrates with the layer manager if available, otherwise uses an internal fallback.
        """
        try:
            # Check if the layer manager supports the required interface
            if not hasattr(self.layer_manager, 'add_cad_layer'):
                logger.warning("LayerManager doesn't support CAD layers. Using fallback mechanism.")
                self._setup_fallback_layer_management()
                return
                
            # Use the proper layer manager
            self.toggle_layer = self._toggle_cad_layer
            if self.layers:
                for layer_name in self.layers:
                    is_visible = layer_name in self.visible_layers or not self.visible_layers
                    self.layer_manager.add_cad_layer(layer_name, is_visible)
            logger.info("CAD layer management setup complete")
        except Exception as e:
            logger.error(f"Error setting up layer management: {e}")
            # Fall back to internal layer management
            self._setup_fallback_layer_management()
    
    def _setup_fallback_layer_management(self):
        """
        Set up internal fallback layer management when the external layer manager isn't available.
        Initializes visibility states for all layers.
        """
        self.using_fallback_layer_manager = True
        self.fallback_visibility = {}
        
        # Initialize fallback visibility for all layers
        for layer_name in self.layers:
            self.fallback_visibility[layer_name] = layer_name in self.visible_layers or not self.visible_layers
        
        # Set the toggle function to use the fallback
        self.toggle_layer = self._toggle_fallback_layer
        logger.info("Using fallback layer management system")
    
    def _toggle_fallback_layer(self, layer_name, visible):
        """
        Toggle visibility of a CAD layer using the fallback system.
        Manually adjusts the visibility of elements in the layer.
        
        Args:
            layer_name (str): The name of the layer to toggle.
            visible (bool): Whether the layer should be visible.
        """
        if layer_name not in self.cad_elements:
            return
            
        self.fallback_visibility[layer_name] = visible
        
        # Manually show/hide elements
        for element in self.cad_elements[layer_name]:
            try:
                if visible:
                    # Use alpha property if available
                    if hasattr(element, 'update') and hasattr(element, 'alpha0'):
                        element.update(alpha0=1)
                    # Otherwise try other methods
                    elif hasattr(element, 'show'):
                        element.show()
                else:
                    if hasattr(element, 'update') and hasattr(element, 'alpha0'):
                        element.update(alpha0=0)
                    elif hasattr(element, 'hide'):
                        element.hide()
            except Exception as e:
                logger.error(f"Error toggling element visibility in fallback mode: {e}")
    
    def _toggle_cad_layer(self, layer_name, visible):
        """
        Toggle visibility of a CAD layer using the layer manager.
        Adjusts visibility of elements within the specified layer.
        
        Args:
            layer_name (str): The name of the layer to toggle.
            visible (bool): Whether the layer should be visible.
        """
        if layer_name not in self.cad_elements:
            return
            
        try:
            for element in self.cad_elements[layer_name]:
                try:
                    if visible:
                        if hasattr(element, 'show'):
                            element.show()
                        elif hasattr(element, 'update'):
                            element.update(alpha0=1)
                    else:
                        if hasattr(element, 'hide'):
                            element.hide()
                        elif hasattr(element, 'update'):
                            element.update(alpha0=0)
                except Exception as e:
                    logger.error(f"Error toggling individual element visibility: {e}")
        except Exception as e:
            logger.error(f"Error in _toggle_cad_layer for {layer_name}: {e}")
    
    def get_cad_layers(self):
        """
        Get information about CAD layers for UI display.
        
        Returns:
            list: List of (layer_name, is_visible) tuples representing layer names and their visibility states.
        """
        if self.using_fallback_layer_manager:
            return [(name, self.fallback_visibility.get(name, True)) for name in self.layers.keys()]
        elif hasattr(self.layer_manager, 'get_cad_layers'):
            # Use the layer manager's implementation if available
            return self.layer_manager.get_cad_layers()
        else:
            # Basic fallback
            return [(name, name in self.visible_layers or not self.visible_layers) 
                    for name in self.layers.keys()]   # Remaining methods like setup_layer_management, toggle_layer, etc., remain unchanged for brevity