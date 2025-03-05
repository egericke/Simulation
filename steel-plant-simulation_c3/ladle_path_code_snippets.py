"""
Reusable code snippets for Ladle Car Path integration in the Equipment Layout Editor.
This is not intended to be run directly, but provides copy-paste code for integrating
into equipment_layout_editor.py.
"""

# ----- ATTRIBUTES FOR EQUIPMENT LAYOUT EDITOR -----
# Add to EquipmentLayoutEditor.__init__ after existing initializations
self.path_drawing = False
self.current_path_waypoints = []
self.current_path_item = None

# ----- TOGGLE LADLE PATH MODE METHOD -----
def toggle_ladle_path_mode(self, checked):
    """Toggle ladle path drawing mode."""
    # Update scene's path mode
    self.scene.set_ladle_path_mode(checked)
    
    # Initialize path drawing attributes
    self.path_drawing = checked
    if checked:
        self.current_path_waypoints = []
        self.current_path_item = None
    
    # Disable other modes when ladle path mode is enabled
    if checked:
        if self.route_action.isChecked():
            self.route_action.setChecked(False)
        if self.bay_action.isChecked():
            self.bay_action.setChecked(False)
            
        # Switch to the Ladle Car Paths tab
        for i in range(self.findChild(QTabWidget).count()):
            if self.findChild(QTabWidget).tabText(i) == "Ladle Car Paths":
                self.findChild(QTabWidget).setCurrentIndex(i)
                break
        
        # Enable drawing mode in the ladle path editor
        if hasattr(self, "ladle_path_editor"):
            self.ladle_path_editor.toggle_path_drawing(True)
        
        self.status_label.setText("Ladle path mode: Click to add waypoints, finish by clicking button again")
    else:
        # Disable drawing mode in the ladle path editor
        if hasattr(self, "ladle_path_editor"):
            self.ladle_path_editor.toggle_path_drawing(False)
        self.status_label.setText("Ready")

# ----- PATH DRAWING METHODS -----
def start_drawing_path(self):
    """Start drawing a new ladle car path."""
    # Find the bay selector or use the LadlePathEditor's bay combo
    bay_selector = getattr(self, "bay_selector", None)
    if not bay_selector and hasattr(self, "ladle_path_editor"):
        bay_selector = self.ladle_path_editor.bay_combo
        
    if not bay_selector or not bay_selector.currentText():
        QMessageBox.warning(self, "No Bay Selected", "Please select a bay first.")
        return
        
    # Enable path drawing mode via toggle
    self.path_action.setChecked(True)
    self.toggle_ladle_path_mode(True)
    
    # Initialize path state
    self.path_drawing = True
    self.current_path_waypoints = []
    self.current_path_item = None
    logger.info(f"Started drawing path for bay {bay_selector.currentText()}")

def finish_drawing_path(self):
    """Finish drawing the current path and save it."""
    if not self.path_drawing or len(self.current_path_waypoints) < 2:
        QMessageBox.warning(self, "Invalid Path", "Path must have at least 2 waypoints.")
        return
        
    # Find the bay selector or use the LadlePathEditor's bay combo
    bay_selector = getattr(self, "bay_selector", None)
    if not bay_selector and hasattr(self, "ladle_path_editor"):
        bay_selector = self.ladle_path_editor.bay_combo
        
    bay_name = bay_selector.currentText()
    
    # Get the next path ID or use the one from the LadlePathEditor
    path_id = None
    if hasattr(self, "ladle_path_editor"):
        path_id = self.ladle_path_editor.path_id_spin.value()
    else:
        # Find the next available path ID
        path_id = 1
        if "ladle_car_paths" in self.config and bay_name in self.config["ladle_car_paths"]:
            path_ids = [p.get("path_id", 0) for p in self.config["ladle_car_paths"][bay_name]]
            if path_ids:
                path_id = max(path_ids) + 1
    
    # Save path to config
    path = {"path_id": path_id, "waypoints": self.current_path_waypoints}
    if "ladle_car_paths" not in self.config:
        self.config["ladle_car_paths"] = {}
    if bay_name not in self.config["ladle_car_paths"]:
        self.config["ladle_car_paths"][bay_name] = []
        
    # Check if path ID already exists and replace it
    found = False
    for i, existing_path in enumerate(self.config["ladle_car_paths"].get(bay_name, [])):
        if existing_path.get("path_id") == path_id:
            self.config["ladle_car_paths"][bay_name][i] = path
            found = True
            break
            
    if not found:
        self.config["ladle_car_paths"][bay_name].append(path)
        
    # Reset path drawing state
    self.path_drawing = False
    self.current_path_waypoints = []
    self.current_path_item = None
    
    # Update the scene and disable path mode
    self.scene.update()
    self.path_action.setChecked(False)
    self.toggle_ladle_path_mode(False)
    
    # Update the ladle path editor's list if it exists
    if hasattr(self, "ladle_path_editor"):
        self.ladle_path_editor.update_paths_list()
        
    logger.info(f"Finished path {path_id} for bay {bay_name}")

# ----- SCENE MOUSE RELEASE EVENT HANDLING -----
# This should replace or be merged with the existing mouseReleaseEvent in LayoutScene
def mouseReleaseEvent(self, event):
    """Handle mouse release events."""
    if event.button() == Qt.LeftButton and self.route_mode and self.route_start_item:
        end_item = self.itemAt(event.scenePos(), QTransform())
        
        # Check if we need to create a route point
        if not isinstance(end_item, (EquipmentItem, RoutePointItem)) or end_item == self.route_start_item:
            # Create a route point at mouse position
            pos = event.scenePos()
            end_item = self.add_route_point(pos.x(), pos.y())
            
        # Create the route between the two items
        if self.route_start_item != end_item:
            route = RoutePathItem(self.route_start_item, end_item, self.route_type)
            self.addItem(route)
            self.route_paths.append(route)
            event.accept()
        
        self.route_start_item = None
        return
        
    # Handle ladle path mode clicks
    elif hasattr(self, "ladle_path_mode") and self.ladle_path_mode:
        pos = event.scenePos()
        
        # Find the equipment layout editor
        for view in self.views():
            window = view.window()
            if hasattr(window, "current_path_waypoints"):
                # Add waypoint to editor's list
                window.current_path_waypoints.append({"x": pos.x(), "y": pos.y()})
                
                # Draw visual representation
                if len(window.current_path_waypoints) > 1:
                    p1 = window.current_path_waypoints[-2]
                    p2 = window.current_path_waypoints[-1]
                    
                    # Draw a line segment
                    from PyQt5.QtGui import QPainterPath
                    path = QPainterPath()
                    path.moveTo(p1["x"], p1["y"])
                    path.lineTo(p2["x"], p2["y"])
                    
                    path_item = QGraphicsPathItem(path)
                    path_item.setPen(QPen(QColor(0, 128, 255), 2, Qt.DashLine))
                    self.addItem(path_item)
                
                # Draw waypoint as a dot
                ellipse_item = QGraphicsEllipseItem(pos.x() - 5, pos.y() - 5, 10, 10)
                ellipse_item.setBrush(QBrush(QColor(0, 128, 255)))
                ellipse_item.setPen(QPen(Qt.black))
                self.addItem(ellipse_item)
                
                # Also forward to ladle path editor if it exists
                if hasattr(window, "ladle_path_editor"):
                    window.ladle_path_editor.add_waypoint(pos)
                    
                event.accept()
                return
    
    # Existing bay mode code
    elif self.bay_mode and self.bay_start_pos:
        end_pos = event.scenePos()
        rect = QRectF(self.bay_start_pos, end_pos).normalized()
        if rect.width() > 10 and rect.height() > 10:
            name, ok = QInputDialog.getText(None, "Bay Name", "Enter bay name:")
            if ok and name:
                self.removeItem(self.temp_bay_rect)
                bay = BayItem(name, rect.x(), rect.y(), rect.width(), rect.height())
                self.addItem(bay)
                self.bay_items.append(bay)
                QApplication.instance().activeWindow().update_bay_combo()
        self.bay_start_pos = None
        self.temp_bay_rect = None
        self.update()
        event.accept()
        return
    super().mouseReleaseEvent(event)

# ----- UI CONTROLS FOR LADLE PATH DRAWING -----
# Add this to the controls_layout in EquipmentLayoutEditor.create_ui
bay_selector_label = QLabel("Select Bay for Path:")
self.bay_selector = QComboBox()
self.bay_selector.addItems(self.config.get("bays", {}).keys())
controls_layout.addWidget(bay_selector_label)
controls_layout.addWidget(self.bay_selector)

add_path_btn = QPushButton("Add Path")
add_path_btn.setStyleSheet("background-color: #4CAF50; color: white; font-size: 14px; padding: 5px;")
add_path_btn.clicked.connect(self.start_drawing_path)
add_path_btn.setToolTip("Start drawing a ladle car path for the selected bay")
controls_layout.addWidget(add_path_btn)

finish_path_btn = QPushButton("Finish Path")
finish_path_btn.setStyleSheet("background-color: #FF9800; color: white; font-size: 14px; padding: 5px;")
finish_path_btn.clicked.connect(self.finish_drawing_path)
finish_path_btn.setToolTip("Finish the current path")
controls_layout.addWidget(finish_path_btn)

# ----- PATH VISUALIZATION IN LAYOUTSCENE -----
def draw_ladle_car_paths(self, painter):
    """Draw all ladle car paths."""
    for bay_name, paths in self.ladle_car_paths.items():
        for path in paths:
            waypoints = path.get("waypoints", [])
            if len(waypoints) < 2:
                continue
                
            # Draw path lines
            painter.setPen(QPen(QColor(0, 128, 255), 2, Qt.SolidLine))
            for i in range(len(waypoints) - 1):
                p1 = waypoints[i]
                p2 = waypoints[i + 1]
                painter.drawLine(p1["x"], p1["y"], p2["x"], p2["y"])
                
            # Draw waypoints
            painter.setBrush(QBrush(QColor(0, 128, 255, 180)))
            for wp in waypoints:
                painter.drawEllipse(QPointF(wp["x"], wp["y"]), 5, 5)

# Call this from the scene's paint method
def paint(self, painter, option, widget=None):
    """Paint custom scene content."""
    super().paint(painter, option, widget)
    # Draw paths
    self.draw_ladle_car_paths(painter)

# ----- SAVE AND LOAD LADLE CAR PATHS -----
# Add to save_layout method
# Save ladle car paths from scene to config
self.config["ladle_car_paths"] = self.scene.ladle_car_paths

# Add to load_layout_data method
# Load ladle car paths from config to scene
self.scene.ladle_car_paths = self.config.get("ladle_car_paths", {})

# ----- UPDATE BAY COMBO METHOD -----
def update_bay_combo(self):
    """Update bay combo box with current bay items."""
    current_text = self.bay_combo.currentText()
    self.bay_combo.clear()
    for bay in self.scene.bay_items:
        self.bay_combo.addItem(bay.name)
    
    # Also update the bay selector for paths
    if hasattr(self, "bay_selector"):
        bay_selector_text = self.bay_selector.currentText()
        self.bay_selector.clear()
        for bay in self.scene.bay_items:
            self.bay_selector.addItem(bay.name)
        
        # Try to restore the previous selection
        index = self.bay_selector.findText(bay_selector_text)
        if index >= 0:
            self.bay_selector.setCurrentIndex(index)
    
    # Try to restore the previous selection
    index = self.bay_combo.findText(current_text)
    if index >= 0:
        self.bay_combo.setCurrentIndex(index)