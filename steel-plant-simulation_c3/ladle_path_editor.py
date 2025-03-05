import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QListWidget, QListWidgetItem
)
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QPainterPath
)
from PyQt5.QtCore import (
    Qt, QPointF
)
from equipment_layout_editor import RoutePointItem, RoutePathItem, QGraphicsPathItem, QGraphicsEllipseItem

logger = logging.getLogger(__name__)

class LadlePathEditor(QWidget):
    """Widget for creating and editing ladle car paths."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.bay_label = QLabel("Bay:")
        controls_layout.addWidget(self.bay_label)
        
        self.bay_combo = QComboBox()
        controls_layout.addWidget(self.bay_combo)
        
        self.path_label = QLabel("Path ID:")
        controls_layout.addWidget(self.path_label)
        
        self.path_id_spin = QSpinBox()
        self.path_id_spin.setRange(1, 100)
        self.path_id_spin.setValue(1)
        controls_layout.addWidget(self.path_id_spin)
        
        self.draw_path_button = QPushButton("Draw Path")
        self.draw_path_button.setStyleSheet("background-color: #4CAF50; color: white; font-size: 14px; padding: 5px;")
        self.draw_path_button.setCheckable(True)
        self.draw_path_button.clicked.connect(self.toggle_path_drawing)
        controls_layout.addWidget(self.draw_path_button)
        
        controls_layout.addStretch()
        self.layout.addLayout(controls_layout)
        
        # Paths list
        paths_group = QGroupBox("Ladle Car Paths")
        paths_layout = QVBoxLayout()
        
        self.paths_list = QListWidget()
        paths_layout.addWidget(self.paths_list)
        
        # Path operations buttons
        path_buttons_layout = QHBoxLayout()
        
        self.add_path_button = QPushButton("New Path")
        self.add_path_button.clicked.connect(self.add_new_path)
        path_buttons_layout.addWidget(self.add_path_button)
        
        self.edit_path_button = QPushButton("Edit Path")
        self.edit_path_button.clicked.connect(self.edit_selected_path)
        path_buttons_layout.addWidget(self.edit_path_button)
        
        self.delete_path_button = QPushButton("Delete Path")
        self.delete_path_button.clicked.connect(self.delete_selected_path)
        path_buttons_layout.addWidget(self.delete_path_button)
        
        paths_layout.addLayout(path_buttons_layout)
        
        paths_group.setLayout(paths_layout)
        self.layout.addWidget(paths_group)
        
        # Internal properties
        self.scene = None
        self.drawing_active = False
        self.waypoints = []
        self.current_path_id = 1
        self.current_bay = None
        self.temp_path_segment = None
        self.active_path_items = []
    
    def set_scene(self, scene):
        """Set the scene reference for path editing."""
        self.scene = scene
        self.update_bay_combo()
        self.update_paths_list()
    
    def update_bay_combo(self):
        """Update the bay combo box with available bays."""
        if not self.scene:
            return
            
        self.bay_combo.clear()
        for bay in self.scene.bay_items:
            self.bay_combo.addItem(bay.name)
        
        if self.bay_combo.count() > 0:
            self.current_bay = self.bay_combo.currentText()
            self.update_paths_list()
        
        # Connect after populating to avoid triggering during setup
        self.bay_combo.currentTextChanged.connect(self.on_bay_changed)
    
    def on_bay_changed(self, bay_name):
        """Handle bay selection change."""
        self.current_bay = bay_name
        self.update_paths_list()
    
    def update_paths_list(self):
        """Update the list of paths for the current bay."""
        if not self.scene or not self.current_bay:
            return
        
        self.paths_list.clear()
        
        # Find all paths for the current bay
        paths = []
        for path_id in range(1, 100):  # Arbitrary limit
            path_key = f"{self.current_bay}_path_{path_id}"
            for key, path in self.scene.ladle_car_paths.items():
                if key == path_key:
                    paths.append((path_id, path))
                    break
        
        # Add them to the list widget
        for path_id, path in paths:
            waypoints = path.get("waypoints", [])
            item_text = f"Path {path_id}: {len(waypoints)} waypoints"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, {"path_id": path_id, "path": path})
            self.paths_list.addItem(item)
    
    def toggle_path_drawing(self, checked):
        """Toggle path drawing mode."""
        self.drawing_active = checked
        
        if checked:
            # Enable drawing mode in scene
            if self.scene:
                # Clear any existing temporary path segments
                for item in self.active_path_items:
                    self.scene.removeItem(item)
                self.active_path_items.clear()
                
                # Reset waypoints
                self.waypoints.clear()
                
                # Get current bay and path ID
                self.current_bay = self.bay_combo.currentText()
                self.current_path_id = self.path_id_spin.value()
                
                # Set cursor for drawing
                self.scene.views()[0].setCursor(Qt.CrossCursor)
                
                self.draw_path_button.setText("Finish Path")
                self.draw_path_button.setStyleSheet("background-color: #f44336; color: white; font-size: 14px; padding: 5px;")
        else:
            # Disable drawing mode
            if self.scene and self.waypoints:
                # Save the path
                path_data = {
                    "path_id": self.current_path_id,
                    "waypoints": self.waypoints
                }
                
                # Store in scene's paths dictionary
                path_key = f"{self.current_bay}_path_{self.current_path_id}"
                self.scene.ladle_car_paths[path_key] = path_data
                
                # Clear temporary items
                self.temp_path_segment = None
                
                # Convert to permanent path items
                self.convert_to_permanent_path()
                
                # Reset cursor
                self.scene.views()[0].setCursor(Qt.ArrowCursor)
                
                self.draw_path_button.setText("Draw Path")
                self.draw_path_button.setStyleSheet("background-color: #4CAF50; color: white; font-size: 14px; padding: 5px;")
                
                # Update the paths list
                self.update_paths_list()
    
    def add_waypoint(self, position):
        """Add a new waypoint to the current path."""
        if not self.drawing_active:
            return
            
        # Add to waypoints list
        self.waypoints.append({"x": position.x(), "y": position.y()})
        
        # Draw visual representation
        if len(self.waypoints) > 1:
            # Draw line to previous point
            p1 = self.waypoints[-2]
            p2 = self.waypoints[-1]
            
            path = QPainterPath()
            path.moveTo(p1["x"], p1["y"])
            path.lineTo(p2["x"], p2["y"])
            
            path_item = QGraphicsPathItem(path)
            path_item.setPen(QPen(QColor(0, 128, 255), 2, Qt.DashLine))
            
            self.scene.addItem(path_item)
            self.active_path_items.append(path_item)
            
        # Draw point marker
        ellipse_item = QGraphicsEllipseItem(position.x() - 5, position.y() - 5, 10, 10)
        ellipse_item.setBrush(QBrush(QColor(0, 128, 255)))
        ellipse_item.setPen(QPen(Qt.black))
        
        self.scene.addItem(ellipse_item)
        self.active_path_items.append(ellipse_item)
    
    def convert_to_permanent_path(self):
        """Convert temporary path to a permanent route path."""
        if len(self.waypoints) < 2:
            return
            
        # Remove temporary items
        for item in self.active_path_items:
            self.scene.removeItem(item)
        self.active_path_items.clear()
        
        # Create a route path from the waypoints
        for i in range(len(self.waypoints) - 1):
            p1 = {"x": self.waypoints[i]["x"], "y": self.waypoints[i]["y"]}
            p2 = {"x": self.waypoints[i+1]["x"], "y": self.waypoints[i+1]["y"]}
            
            # Create start and end points for the path
            start_point = RoutePointItem(f"wp_{i}", p1["x"], p1["y"])
            end_point = RoutePointItem(f"wp_{i+1}", p2["x"], p2["y"])
            
            self.scene.addItem(start_point)
            self.scene.addItem(end_point)
            
            # Create a path between the points
            route = RoutePathItem(start_point, end_point, "LadleCar")
            self.scene.addItem(route)
            self.scene.route_paths.append(route)
    
    def add_new_path(self):
        """Start creating a new path."""
        # Find the next available path ID
        max_id = 0
        for key in self.scene.ladle_car_paths.keys():
            if key.startswith(f"{self.current_bay}_path_"):
                try:
                    path_id = int(key.split("_")[-1])
                    max_id = max(max_id, path_id)
                except ValueError:
                    pass
        
        # Set the path ID and start drawing
        self.path_id_spin.setValue(max_id + 1)
        self.draw_path_button.setChecked(True)
        self.toggle_path_drawing(True)
    
    def edit_selected_path(self):
        """Edit the selected path."""
        selected_items = self.paths_list.selectedItems()
        if not selected_items:
            return
            
        item = selected_items[0]
        path_data = item.data(Qt.UserRole)
        
        self.current_path_id = path_data["path_id"]
        self.path_id_spin.setValue(self.current_path_id)
        
        # Load the waypoints
        self.waypoints = path_data["path"].get("waypoints", []).copy()
        
        # Start editing
        self.draw_path_button.setChecked(True)
        self.toggle_path_drawing(True)
    
    def delete_selected_path(self):
        """Delete the selected path."""
        selected_items = self.paths_list.selectedItems()
        if not selected_items:
            return
            
        item = selected_items[0]
        path_data = item.data(Qt.UserRole)
        
        path_id = path_data["path_id"]
        path_key = f"{self.current_bay}_path_{path_id}"
        
        # Remove from scene paths dictionary
        if path_key in self.scene.ladle_car_paths:
            del self.scene.ladle_car_paths[path_key]
        
        # Update the list
        self.update_paths_list()
        
        # Remove visual representation
        self.remove_path_visual(path_id)
    
    def remove_path_visual(self, path_id):
        """Remove visual representation of a path."""
        # This would need to identify and remove the path items in the scene
        # For simplicity, we'll just update the scene
        if self.scene:
            self.scene.update()