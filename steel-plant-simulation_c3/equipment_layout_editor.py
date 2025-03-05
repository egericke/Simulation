import os
import json
from PyQt5.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QSpinBox, QGroupBox, QToolBar, QAction, QFileDialog, QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsTextItem, QApplication, QMessageBox, QMenu, QFrame, QInputDialog, QListWidget, QListWidgetItem, QSplitter)
from PyQt5.QtGui import (QIcon, QPainter, QPen, QBrush, QColor, QPixmap, QImage, QFont, QFontMetrics, QPainterPath, QDrag, QTransform)
from PyQt5.QtCore import (Qt, QPointF, QSizeF, QRectF, QLineF, QEventLoop, QObject, pyqtSignal, QCoreApplication, QTimer)
import logging
import numpy as np
import random
import copy
from ladle_path_editor import LadlePathEditor
from shared_items import RoutePointItem, RoutePathItem

# Setup logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class EquipmentItem(QGraphicsRectItem):
    """Graphics item representing a piece of equipment in the layout."""
    
    def __init__(self, x, y, width, height, equipment_type, equipment_id, name, parent=None):
        super().__init__(x, y, width, height, parent)
        self.equipment_type = equipment_type
        self.equipment_id = equipment_id
        self.name = name
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        
        # Set up appearance based on equipment type
        if equipment_type == "EAF":
            self.setBrush(QBrush(QColor(200, 100, 100, 150)))
            self.setPen(QPen(QColor(150, 50, 50), 2))
        elif equipment_type == "LMF":
            self.setBrush(QBrush(QColor(100, 200, 100, 150)))
            self.setPen(QPen(QColor(50, 150, 50), 2))
        elif equipment_type == "DEGAS":
            self.setBrush(QBrush(QColor(100, 100, 200, 150)))
            self.setPen(QPen(QColor(50, 50, 150), 2))
        elif equipment_type == "CASTER":
            self.setBrush(QBrush(QColor(200, 200, 100, 150)))
            self.setPen(QPen(QColor(150, 150, 50), 2))
        else:
            self.setBrush(QBrush(QColor(150, 150, 150, 150)))
            self.setPen(QPen(QColor(100, 100, 100), 2))
            
        # Add text label
        self.text_item = QGraphicsTextItem(f"{name}\n({equipment_type})", self)
        self.text_item.setPos(10, 10)
        self.text_item.setDefaultTextColor(Qt.black)
        
    def paint(self, painter, option, widget=None):
        """Paint the equipment item."""
        super().paint(painter, option, widget)
        
    def hoverEnterEvent(self, event):
        """Handle hover enter events."""
        if self.equipment_type == "EAF":
            self.setBrush(QBrush(QColor(255, 150, 150, 200)))
        elif self.equipment_type == "LMF":
            self.setBrush(QBrush(QColor(150, 255, 150, 200)))
        elif self.equipment_type == "DEGAS":
            self.setBrush(QBrush(QColor(150, 150, 255, 200)))
        elif self.equipment_type == "CASTER":
            self.setBrush(QBrush(QColor(255, 255, 150, 200)))
        else:
            self.setBrush(QBrush(QColor(200, 200, 200, 200)))
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        """Handle hover leave events."""
        if self.equipment_type == "EAF":
            self.setBrush(QBrush(QColor(200, 100, 100, 150)))
        elif self.equipment_type == "LMF":
            self.setBrush(QBrush(QColor(100, 200, 100, 150)))
        elif self.equipment_type == "DEGAS":
            self.setBrush(QBrush(QColor(100, 100, 200, 150)))
        elif self.equipment_type == "CASTER":
            self.setBrush(QBrush(QColor(200, 200, 100, 150)))
        else:
            self.setBrush(QBrush(QColor(150, 150, 150, 150)))
        super().hoverLeaveEvent(event)
        
    def get_data(self):
        """Get the equipment item data."""
        return {
            "equipment_type": self.equipment_type,
            "equipment_id": self.equipment_id,
            "name": self.name,
            "x": self.x(),
            "y": self.y(),
            "width": self.rect().width(),
            "height": self.rect().height()
        }
        
    def contextMenuEvent(self, event):
        """Display context menu when right-clicking on the equipment."""
        menu = QMenu()
        name_action = menu.addAction("Edit Name")
        delete_action = menu.addAction("Delete")
        
        selected_action = menu.exec_(event.screenPos())
        
        if selected_action == name_action:
            new_name, ok = QInputDialog.getText(None, "Edit Equipment Name", "New name:", text=self.name)
            if ok and new_name:
                self.name = new_name
                self.text_item.setPlainText(f"{new_name}\n({self.equipment_type})")
        elif selected_action == delete_action:
            # Remove the item from the scene
            scene = self.scene()
            if scene:
                scene.removeItem(self)

class BayItem(QGraphicsRectItem):
    """Graphics item representing a bay area in the layout."""
    
    def __init__(self, x, y, width, height, bay_id, name, parent=None):
        super().__init__(x, y, width, height, parent)
        self.bay_id = bay_id
        self.name = name
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        
        # Set up appearance
        self.setBrush(QBrush(QColor(200, 200, 200, 100)))
        self.setPen(QPen(QColor(150, 150, 150, 200), 2, Qt.DashDotLine))
            
        # Add text label
        self.text_item = QGraphicsTextItem(f"Bay: {name}", self)
        self.text_item.setPos(10, 10)
        self.text_item.setDefaultTextColor(Qt.darkGray)
        
    def paint(self, painter, option, widget=None):
        """Paint the bay item."""
        super().paint(painter, option, widget)
        
    def hoverEnterEvent(self, event):
        """Handle hover enter events."""
        self.setBrush(QBrush(QColor(220, 220, 220, 150)))
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        """Handle hover leave events."""
        self.setBrush(QBrush(QColor(200, 200, 200, 100)))
        super().hoverLeaveEvent(event)
        
    def get_data(self):
        """Get the bay item data."""
        return {
            "bay_id": self.bay_id,
            "name": self.name,
            "x": self.x(),
            "y": self.y(),
            "width": self.rect().width(),
            "height": self.rect().height()
        }
        
    def contextMenuEvent(self, event):
        """Display context menu when right-clicking on the bay."""
        menu = QMenu()
        name_action = menu.addAction("Edit Name")
        delete_action = menu.addAction("Delete")
        
        selected_action = menu.exec_(event.screenPos())
        
        if selected_action == name_action:
            new_name, ok = QInputDialog.getText(None, "Edit Bay Name", "New name:", text=self.name)
            if ok and new_name:
                self.name = new_name
                self.text_item.setPlainText(f"Bay: {new_name}")
        elif selected_action == delete_action:
            # Remove the item from the scene
            scene = self.scene()
            if scene:
                scene.removeItem(self)

class LayoutScene(QGraphicsScene):
    """Custom graphics scene for the layout editor."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 1200, 800)
        self.grid_size = 20
        self.draw_grid()
        self.ladle_path_mode = False
        self.current_path_points = []
        self.current_path_type = "ladle_car"
        self.routes = []

    def draw_grid(self):
        """Draw a grid on the scene."""
        grid_pen = QPen(QColor(230, 230, 230))
        
        # Draw horizontal grid lines
        for y in range(0, int(self.height()), self.grid_size):
            self.addLine(0, y, self.width(), y, grid_pen)
            
        # Draw vertical grid lines
        for x in range(0, int(self.width()), self.grid_size):
            self.addLine(x, 0, x, self.height(), grid_pen)
    
    def set_ladle_path_mode(self, enabled, path_type="ladle_car"):
        """Set whether ladle path drawing mode is enabled."""
        self.ladle_path_mode = enabled
        self.current_path_type = path_type
        if not enabled:
            self.current_path_points = []
        
    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        pos = event.scenePos()
        
        if self.ladle_path_mode:
            # Snap to grid
            x = round(pos.x() / self.grid_size) * self.grid_size
            y = round(pos.y() / self.grid_size) * self.grid_size
            
            # Create a new route point
            point_item = RoutePointItem(x, y)
            self.addItem(point_item)
            
            # If we have previous points, create a path between them
            if self.current_path_points:
                prev_point = self.current_path_points[-1]
                path_item = RoutePathItem(prev_point, point_item, self.current_path_type)
                self.addItem(path_item)
                self.routes.append(path_item)
            
            self.current_path_points.append(point_item)
        else:
            super().mouseReleaseEvent(event)
            
    def clear_routes(self):
        """Clear all routes from the scene."""
        for route in self.routes:
            self.removeItem(route)
        self.routes = []
        
        # Also remove all route points
        for item in self.items():
            if isinstance(item, RoutePointItem):
                self.removeItem(item)
                
        self.current_path_points = []

class LayoutView(QGraphicsView):
    """Custom graphics view for the layout editor."""
    
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming."""
        if event.modifiers() & Qt.ControlModifier:
            # Zoom in/out
            zoom_factor = 1.2
            if event.angleDelta().y() < 0:
                zoom_factor = 1 / zoom_factor
                
            self.scale(zoom_factor, zoom_factor)
            event.accept()
        else:
            # Regular scrolling
            super().wheelEvent(event)
            
    def reset_zoom(self):
        """Reset the view to its original zoom level."""
        self.setTransform(QTransform())

def load_equipment_data():
    """Load equipment data from a JSON file."""
    equipment_data = {}
    try:
        with open("equipment_data.json", "r") as f:
            equipment_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Use default equipment types
        equipment_data = {
            "EAF": {"width": 100, "height": 100, "color": "#c86464"},
            "LMF": {"width": 100, "height": 100, "color": "#64c864"},
            "DEGAS": {"width": 100, "height": 100, "color": "#6464c8"},
            "CASTER": {"width": 100, "height": 100, "color": "#c8c864"}
        }
        # Save default data
        with open("equipment_data.json", "w") as f:
            json.dump(equipment_data, f, indent=4)
            
    return equipment_data

class EquipmentLayoutEditor(QDialog):
    """Dialog for editing the equipment layout."""
    
    def __init__(self, parent=None, current_config=None):
        super().__init__(parent)
        self.setWindowTitle("Equipment Layout Editor")
        self.setMinimumSize(1200, 800)
        
        self.equipment_counter = 0
        self.bay_counter = 0
        self.ladle_path_editor = None
        
        # Load configuration if provided
        if current_config:
            self.config = current_config
        else:
            try:
                with open("config.json", "r") as f:
                    self.config = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                # Default empty configuration
                self.config = {"equipment_positions": [], "bays": [], "ladle_paths": []}
                
        # Create UI
        self.create_ui()
        
        # Load layout data
        self.load_layout_data()
        
    def create_ui(self):
        """Create the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Create the toolbar
        toolbar = QToolBar("Tools")
        main_layout.addWidget(toolbar)
        
        # Add equipment selection
        equipment_label = QLabel("Add Equipment:")
        toolbar.addWidget(equipment_label)
        
        self.equipment_combo = QComboBox()
        for equipment_type in ["EAF", "LMF", "DEGAS", "CASTER"]:
            self.equipment_combo.addItem(equipment_type)
        toolbar.addWidget(self.equipment_combo)
        
        add_equipment_btn = QPushButton("Add")
        add_equipment_btn.clicked.connect(self.add_equipment)
        toolbar.addWidget(add_equipment_btn)
        
        toolbar.addSeparator()
        
        # Add bay area
        bay_label = QLabel("Add Bay Area:")
        toolbar.addWidget(bay_label)
        
        add_bay_btn = QPushButton("Add Bay")
        add_bay_btn.clicked.connect(self.add_bay)
        toolbar.addWidget(add_bay_btn)
        
        toolbar.addSeparator()
        
        # Ladle path editor
        self.ladle_path_btn = QPushButton("Ladle Path Editor")
        self.ladle_path_btn.setCheckable(True)
        self.ladle_path_btn.clicked.connect(self.toggle_ladle_path_editor)
        toolbar.addWidget(self.ladle_path_btn)
        
        # Ladle car path drawing
        self.ladle_car_path_btn = QPushButton("Draw Ladle Car Path")
        self.ladle_car_path_btn.setCheckable(True)
        self.ladle_car_path_btn.clicked.connect(lambda: self.toggle_ladle_path_mode("ladle_car"))
        toolbar.addWidget(self.ladle_car_path_btn)
        
        # Crane path drawing
        self.crane_path_btn = QPushButton("Draw Crane Path")
        self.crane_path_btn.setCheckable(True)
        self.crane_path_btn.clicked.connect(lambda: self.toggle_ladle_path_mode("crane"))
        toolbar.addWidget(self.crane_path_btn)
        
        # Clear paths
        clear_paths_btn = QPushButton("Clear Paths")
        clear_paths_btn.clicked.connect(self.clear_paths)
        toolbar.addWidget(clear_paths_btn)
        
        toolbar.addSeparator()
        
        # View controls
        zoom_in_btn = QPushButton("Zoom In")
        zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar.addWidget(zoom_in_btn)
        
        zoom_out_btn = QPushButton("Zoom Out")
        zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar.addWidget(zoom_out_btn)
        
        reset_zoom_btn = QPushButton("Reset Zoom")
        reset_zoom_btn.clicked.connect(self.reset_zoom)
        toolbar.addWidget(reset_zoom_btn)
        
        toolbar.addSeparator()
        
        # Save and load
        save_btn = QPushButton("Save Layout")
        save_btn.clicked.connect(self.save_layout)
        toolbar.addWidget(save_btn)
        
        load_btn = QPushButton("Load Layout")
        load_btn.clicked.connect(self.load_layout)
        toolbar.addWidget(load_btn)
        
        # Create the graphics scene and view
        self.scene = LayoutScene()
        self.view = LayoutView(self.scene)
        
        # Equipment info panel
        info_panel = QGroupBox("Equipment Information")
        info_layout = QVBoxLayout(info_panel)
        
        self.equipment_list = QListWidget()
        info_layout.addWidget(self.equipment_list)
        
        # Create a splitter for the main area
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.view)
        splitter.addWidget(info_panel)
        splitter.setSizes([800, 200])
        
        main_layout.addWidget(splitter)
        
        # Save and close button at the bottom
        bottom_layout = QHBoxLayout()
        save_close_btn = QPushButton("Save and Close")
        save_close_btn.clicked.connect(self.save_and_close)
        bottom_layout.addStretch()
        bottom_layout.addWidget(save_close_btn)
        main_layout.addLayout(bottom_layout)
        
    def add_equipment(self):
        """Add a new equipment item to the scene."""
        equipment_type = self.equipment_combo.currentText()
        self.equipment_counter += 1
        equipment_id = f"{equipment_type.lower()}_{self.equipment_counter}"
        
        # Get equipment dimensions from data
        equipment_data = load_equipment_data()
        width = equipment_data.get(equipment_type, {}).get("width", 100)
        height = equipment_data.get(equipment_type, {}).get("height", 100)
        
        # Create the equipment item
        item = EquipmentItem(100, 100, width, height, equipment_type, equipment_id, equipment_id)
        self.scene.addItem(item)
        
        # Add to the equipment list
        self.equipment_list.addItem(f"{equipment_id} ({equipment_type})")
        
    def add_bay(self):
        """Add a new bay area to the scene."""
        self.bay_counter += 1
        bay_id = f"bay_{self.bay_counter}"
        
        # Create the bay item
        item = BayItem(100, 100, 300, 200, bay_id, bay_id)
        self.scene.addItem(item)
        
        # Add to the equipment list
        self.equipment_list.addItem(f"Bay: {bay_id}")
        
    def toggle_ladle_path_editor(self, checked):
        """Toggle the ladle path editor."""
        if checked:
            # Disable path drawing buttons
            self.ladle_car_path_btn.setChecked(False)
            self.crane_path_btn.setChecked(False)
            self.scene.set_ladle_path_mode(False)
            
            # Show the ladle path editor dialog
            if not self.ladle_path_editor:
                self.ladle_path_editor = LadlePathEditor(self, self.config.get("ladle_paths", []))
            
            # Show the dialog non-modal
            self.ladle_path_editor.show()
        else:
            # Hide the ladle path editor
            if self.ladle_path_editor:
                self.ladle_path_editor.hide()
                
    def toggle_ladle_path_mode(self, path_type):
        """Toggle ladle path drawing mode."""
        sender = self.sender()
        checked = sender.isChecked()
        
        # Uncheck the other button
        if path_type == "ladle_car":
            self.crane_path_btn.setChecked(False)
            self.ladle_path_btn.setChecked(False)
        else:
            self.ladle_car_path_btn.setChecked(False)
            self.ladle_path_btn.setChecked(False)
            
        # Set the scene mode
        self.scene.set_ladle_path_mode(checked, path_type)
        
    def clear_paths(self):
        """Clear all paths from the scene."""
        self.scene.clear_routes()
        
    def zoom_in(self):
        """Zoom in on the view."""
        self.view.scale(1.2, 1.2)
        
    def zoom_out(self):
        """Zoom out on the view."""
        self.view.scale(1/1.2, 1/1.2)
        
    def reset_zoom(self):
        """Reset the zoom level."""
        self.view.reset_zoom()
        
    def save_layout(self):
        """Save the layout to a JSON file."""
        # Collect equipment data
        equipment_data = []
        bay_data = []
        
        for item in self.scene.items():
            if isinstance(item, EquipmentItem):
                equipment_data.append(item.get_data())
            elif isinstance(item, BayItem):
                bay_data.append(item.get_data())
                
        # Collect route data
        route_data = []
        for route in self.scene.routes:
            route_data.append(route.get_data())
                
        # Create the layout data
        layout_data = {
            "equipment_positions": equipment_data,
            "bays": bay_data,
            "routes": route_data
        }
        
        # Get ladle paths from editor if available
        if self.ladle_path_editor:
            layout_data["ladle_paths"] = self.ladle_path_editor.get_path_data()
        elif "ladle_paths" in self.config:
            layout_data["ladle_paths"] = self.config["ladle_paths"]
        
        # Save to a JSON file
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Layout", "", "JSON Files (*.json)")
        if file_path:
            with open(file_path, "w") as f:
                json.dump(layout_data, f, indent=4)
                
            QMessageBox.information(self, "Layout Saved", f"Layout saved to {file_path}")
        
    def load_layout(self):
        """Load a layout from a JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Layout", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, "r") as f:
                    layout_data = json.load(f)
                    
                # Clear the scene
                self.scene.clear()
                self.scene.draw_grid()
                self.equipment_list.clear()
                self.equipment_counter = 0
                self.bay_counter = 0
                
                # Load equipment
                for equip_data in layout_data.get("equipment_positions", []):
                    item = EquipmentItem(
                        equip_data["x"],
                        equip_data["y"],
                        equip_data["width"],
                        equip_data["height"],
                        equip_data["equipment_type"],
                        equip_data["equipment_id"],
                        equip_data["name"]
                    )
                    self.scene.addItem(item)
                    self.equipment_list.addItem(f"{equip_data['name']} ({equip_data['equipment_type']})")
                    
                    # Update counter
                    if equip_data["equipment_id"].startswith(equip_data["equipment_type"].lower()):
                        try:
                            counter = int(equip_data["equipment_id"].split("_")[1])
                            self.equipment_counter = max(self.equipment_counter, counter)
                        except (IndexError, ValueError):
                            pass
                
                # Load bays
                for bay_data in layout_data.get("bays", []):
                    item = BayItem(
                        bay_data["x"],
                        bay_data["y"],
                        bay_data["width"],
                        bay_data["height"],
                        bay_data["bay_id"],
                        bay_data["name"]
                    )
                    self.scene.addItem(item)
                    self.equipment_list.addItem(f"Bay: {bay_data['name']}")
                    
                    # Update counter
                    if bay_data["bay_id"].startswith("bay_"):
                        try:
                            counter = int(bay_data["bay_id"].split("_")[1])
                            self.bay_counter = max(self.bay_counter, counter)
                        except (IndexError, ValueError):
                            pass
                
                # Update configuration
                self.config = layout_data
                
                # Update ladle path editor if open
                if self.ladle_path_editor:
                    self.ladle_path_editor.set_path_data(layout_data.get("ladle_paths", []))
                    
                QMessageBox.information(self, "Layout Loaded", f"Layout loaded from {file_path}")
                
            except (FileNotFoundError, json.JSONDecodeError) as e:
                QMessageBox.warning(self, "Error Loading Layout", f"Failed to load layout: {str(e)}")
                
    def load_layout_data(self):
        """Load layout data from the configuration."""
        # Clear the scene
        self.scene.clear()
        self.scene.draw_grid()
        self.equipment_list.clear()
        
        # Load equipment positions
        for equip_data in self.config.get("equipment_positions", []):
            item = EquipmentItem(
                equip_data["x"],
                equip_data["y"],
                equip_data.get("width", 100),
                equip_data.get("height", 100),
                equip_data["equipment_type"],
                equip_data["equipment_id"],
                equip_data.get("name", equip_data["equipment_id"])
            )
            self.scene.addItem(item)
            self.equipment_list.addItem(f"{equip_data.get('name', equip_data['equipment_id'])} ({equip_data['equipment_type']})")
            
            # Update counter
            if equip_data["equipment_id"].startswith(equip_data["equipment_type"].lower()):
                try:
                    counter = int(equip_data["equipment_id"].split("_")[1])
                    self.equipment_counter = max(self.equipment_counter, counter)
                except (IndexError, ValueError):
                    pass
        
        # Load bays
        for bay_data in self.config.get("bays", []):
            item = BayItem(
                bay_data["x"],
                bay_data["y"],
                bay_data.get("width", 300),
                bay_data.get("height", 200),
                bay_data["bay_id"],
                bay_data.get("name", bay_data["bay_id"])
            )
            self.scene.addItem(item)
            self.equipment_list.addItem(f"Bay: {bay_data.get('name', bay_data['bay_id'])}")
            
            # Update counter
            if bay_data["bay_id"].startswith("bay_"):
                try:
                    counter = int(bay_data["bay_id"].split("_")[1])
                    self.bay_counter = max(self.bay_counter, counter)
                except (IndexError, ValueError):
                    pass
        
    def save_and_close(self):
        """Save the layout to the configuration and close the dialog."""
        # Collect equipment data
        equipment_data = []
        bay_data = []
        
        for item in self.scene.items():
            if isinstance(item, EquipmentItem):
                equipment_data.append(item.get_data())
            elif isinstance(item, BayItem):
                bay_data.append(item.get_data())
                
        # Collect route data
        route_data = []
        for route in self.scene.routes:
            route_data.append(route.get_data())
                
        # Update the configuration
        self.config["equipment_positions"] = equipment_data
        self.config["bays"] = bay_data
        self.config["routes"] = route_data
        
        # Get ladle paths from editor if available
        if self.ladle_path_editor:
            self.config["ladle_paths"] = self.ladle_path_editor.get_path_data()
            self.ladle_path_editor.close()
            
        # Close the dialog
        self.accept()
        
    def get_config(self):
        """Get the current configuration."""
        return self.config

def show_equipment_layout_editor(current_config=None):
    """Show the equipment layout editor dialog."""
    app = QCoreApplication.instance()
    if not app:
        app = QApplication([])

    dialog = EquipmentLayoutEditor(current_config=current_config)
    if dialog.exec_() == QDialog.Accepted:
        return dialog.get_config()
    return None

if __name__ == "__main__":
    app = QApplication([])
    editor = EquipmentLayoutEditor()
    editor.show()
    app.exec_()