import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QSpinBox, QGroupBox, QListWidget, QListWidgetItem)
from PyQt5.QtGui import (QPainter, QPen, QBrush, QColor, QPainterPath)
from PyQt5.QtCore import (Qt, QPointF)
from shared_items import RoutePointItem, RoutePathItem, QGraphicsPathItem, QGraphicsEllipseItem

# Setup logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class LadlePathEditor(QWidget):
    """Widget for editing ladle paths."""
    
    def __init__(self, parent=None, initial_paths=None):
        super().__init__(parent)
        self.setWindowTitle("Ladle Path Editor")
        self.setMinimumSize(800, 600)
        
        self.paths = initial_paths or []
        self.current_path = None
        self.path_drawing = False
        self.current_points = []
        
        # Create UI
        self.create_ui()
        
        # Populate path list
        self.update_path_list()
        
    def create_ui(self):
        """Create the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Path list group
        path_list_group = QGroupBox("Ladle Paths")
        path_list_layout = QVBoxLayout(path_list_group)
        
        # Path list
        self.path_list = QListWidget()
        self.path_list.currentRowChanged.connect(self.on_path_selected)
        path_list_layout.addWidget(self.path_list)
        
        # Path controls
        path_controls_layout = QHBoxLayout()
        
        # Add path button
        add_path_btn = QPushButton("Add Path")
        add_path_btn.clicked.connect(self.add_path)
        path_controls_layout.addWidget(add_path_btn)
        
        # Remove path button
        remove_path_btn = QPushButton("Remove Path")
        remove_path_btn.clicked.connect(self.remove_path)
        path_controls_layout.addWidget(remove_path_btn)
        
        path_list_layout.addLayout(path_controls_layout)
        
        # Path editing group
        path_edit_group = QGroupBox("Edit Path")
        path_edit_layout = QVBoxLayout(path_edit_group)
        
        # Path type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Path Type:"))
        self.path_type_combo = QComboBox()
        self.path_type_combo.addItems(["Ladle Car", "Crane"])
        self.path_type_combo.currentIndexChanged.connect(self.on_path_type_changed)
        type_layout.addWidget(self.path_type_combo)
        path_edit_layout.addLayout(type_layout)
        
        # Path name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Path Name:"))
        self.path_name_combo = QComboBox()
        self.path_name_combo.setEditable(True)
        self.path_name_combo.addItems(["Path 1", "Path 2", "Path 3", "Custom"])
        name_layout.addWidget(self.path_name_combo)
        path_edit_layout.addLayout(name_layout)
        
        # Path drawing controls
        drawing_layout = QHBoxLayout()
        
        # Toggle path drawing
        self.draw_path_btn = QPushButton("Start Drawing Path")
        self.draw_path_btn.setCheckable(True)
        self.draw_path_btn.clicked.connect(self.toggle_path_drawing)
        drawing_layout.addWidget(self.draw_path_btn)
        
        # Clear path
        clear_path_btn = QPushButton("Clear Path")
        clear_path_btn.clicked.connect(self.clear_path)
        drawing_layout.addWidget(clear_path_btn)
        
        path_edit_layout.addLayout(drawing_layout)
        
        # Save path
        save_path_btn = QPushButton("Save Path")
        save_path_btn.clicked.connect(self.save_path)
        path_edit_layout.addWidget(save_path_btn)
        
        # Add the groups to the main layout
        main_layout.addWidget(path_list_group)
        main_layout.addWidget(path_edit_group)
        
        # Done button
        done_btn = QPushButton("Done")
        done_btn.clicked.connect(self.close)
        main_layout.addWidget(done_btn)
        
    def update_path_list(self):
        """Update the path list widget."""
        self.path_list.clear()
        for i, path in enumerate(self.paths):
            path_name = path.get("name", f"Path {i+1}")
            path_type = path.get("type", "Ladle Car")
            self.path_list.addItem(f"{path_name} ({path_type})")
        
    def on_path_selected(self, index):
        """Handle path selection."""
        if index < 0 or index >= len(self.paths):
            self.current_path = None
            return
            
        self.current_path = self.paths[index]
        
        # Update UI
        path_type = self.current_path.get("type", "Ladle Car")
        self.path_type_combo.setCurrentText(path_type)
        
        path_name = self.current_path.get("name", f"Path {index+1}")
        self.path_name_combo.setCurrentText(path_name)
        
        # Reset drawing state
        self.path_drawing = False
        self.draw_path_btn.setChecked(False)
        self.draw_path_btn.setText("Start Drawing Path")
        
    def on_path_type_changed(self, index):
        """Handle path type changes."""
        if self.current_path:
            self.current_path["type"] = self.path_type_combo.currentText()
            self.update_path_list()
        
    def add_path(self):
        """Add a new path."""
        new_path = {
            "name": f"Path {len(self.paths)+1}",
            "type": "Ladle Car",
            "waypoints": []
        }
        self.paths.append(new_path)
        self.update_path_list()
        self.path_list.setCurrentRow(len(self.paths) - 1)
        
    def remove_path(self):
        """Remove the selected path."""
        current_row = self.path_list.currentRow()
        if current_row >= 0 and current_row < len(self.paths):
            self.paths.pop(current_row)
            self.update_path_list()
            if self.paths:
                self.path_list.setCurrentRow(min(current_row, len(self.paths) - 1))
            else:
                self.current_path = None
                
    def toggle_path_drawing(self, checked):
        """Toggle path drawing mode."""
        self.path_drawing = checked
        if checked:
            self.draw_path_btn.setText("Stop Drawing Path")
            # Signal to the parent that we're starting path drawing
            if hasattr(self.parent(), "toggle_ladle_path_mode"):
                path_type = self.path_type_combo.currentText().lower().replace(" ", "_")
                self.parent().toggle_ladle_path_mode(path_type)
        else:
            self.draw_path_btn.setText("Start Drawing Path")
            # Signal to the parent that we're stopping path drawing
            if hasattr(self.parent(), "toggle_ladle_path_mode"):
                # Disable path drawing
                path_type = self.path_type_combo.currentText().lower().replace(" ", "_")
                self.parent().toggle_ladle_path_mode(path_type, force_disable=True)
                
    def add_waypoint(self, x, y):
        """Add a waypoint to the current path."""
        if self.current_path and self.path_drawing:
            self.current_path.setdefault("waypoints", []).append({
                "x": x,
                "y": y
            })
            
    def clear_path(self):
        """Clear the current path."""
        if self.current_path:
            self.current_path["waypoints"] = []
            
    def save_path(self):
        """Save the current path."""
        if self.current_path:
            self.current_path["name"] = self.path_name_combo.currentText()
            self.current_path["type"] = self.path_type_combo.currentText()
            self.update_path_list()
            
    def get_path_data(self):
        """Get the path data."""
        return self.paths
        
    def set_path_data(self, paths):
        """Set the path data."""
        self.paths = paths or []
        self.update_path_list()
        
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    editor = LadlePathEditor()
    editor.show()
    sys.exit(app.exec_())