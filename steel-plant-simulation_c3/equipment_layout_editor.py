"""
Interactive equipment layout editor for steel plant simulation.

This module provides a visual interface for placing equipment on the CAD layout
and defining their positions interactively.
"""

import os
import json
from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QToolBar, QAction, QFileDialog,
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsTextItem,
    QApplication, QMessageBox, QMenu, QFrame, QInputDialog, QListWidget,
    QListWidgetItem, QSplitter
)
from PyQt5.QtGui import (
    QIcon, QPainter, QPen, QBrush, QColor, QPixmap, QImage, 
    QFont, QFontMetrics, QPainterPath, QDrag, QTransform
)
from PyQt5.QtCore import (
    Qt, QPointF, QSizeF, QRectF, QLineF, QEventLoop, 
    QObject, pyqtSignal, QCoreApplication, QTimer
)
import logging
import numpy as np
import random
import copy
from ladle_path_editor import LadlePathEditor

logger = logging.getLogger(__name__)

class BayItem(QGraphicsRectItem):
    """Graphics item representing a bay in the layout."""
    
    def __init__(self, name, x, y, width, height, parent=None):
        super().__init__(x, y, width, height, parent)
        self.name = name
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        
        # Set a semi-transparent fill color
        self.setBrush(QBrush(QColor(100, 100, 255, 50)))
        self.setPen(QPen(QColor(100, 100, 255), 2))
        
        # Add a text label
        self.label = QGraphicsTextItem(self)
        self.label.setPlainText(name)
        self.label.setFont(QFont("Arial", 10, QFont.Bold))
        self.label.setDefaultTextColor(QColor(0, 0, 100))
        self.label.setPos(10, 10)
        
    def paint(self, painter, option, widget=None):
        """Paint the bay item."""
        super().paint(painter, option, widget)
        
    def hoverEnterEvent(self, event):
        """Handle hover enter events."""
        self.setBrush(QBrush(QColor(100, 100, 255, 80)))
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        """Handle hover leave events."""
        self.setBrush(QBrush(QColor(100, 100, 255, 50)))
        super().hoverLeaveEvent(event)
        
    def get_data(self):
        """Get the bay data."""
        rect = self.rect()
        return {
            "name": self.name,
            "x": rect.x(),
            "y": rect.y(),
            "width": rect.width(),
            "height": rect.height()
        }

class EquipmentItem(QGraphicsRectItem):
    """Graphics item representing a piece of equipment in the layout."""
    
    def __init__(self, equipment_type, name, x, y, width, height, parent=None):
        super().__init__(x, y, width, height, parent)
        self.equipment_type = equipment_type
        self.name = name
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        
        # Set up appearance
        color_map = {
            "EAF": QColor(255, 100, 100),
            "LMF": QColor(100, 255, 100),
            "VD": QColor(100, 100, 255),
            "Caster": QColor(255, 255, 100),
            "LaunchPad": QColor(255, 100, 255),
            "EntranceExit": QColor(100, 255, 255)
        }
        
        color = color_map.get(equipment_type, QColor(200, 200, 200))
        self.setBrush(QBrush(color.lighter(150)))
        self.setPen(QPen(color.darker(150), 2))
        
        # Add a text label
        self.label = QGraphicsTextItem(self)
        self.label.setPlainText(f"{name}\n({equipment_type})")
        self.label.setFont(QFont("Arial", 8, QFont.Bold))
        self.label.setDefaultTextColor(QColor(0, 0, 0))
        self.label.setPos(5, 5)
        
    def paint(self, painter, option, widget=None):
        """Paint the equipment item."""
        super().paint(painter, option, widget)
        
    def hoverEnterEvent(self, event):
        """Handle hover enter events."""
        self.setBrush(QBrush(self.brush().color().lighter(120)))
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        """Handle hover leave events."""
        self.setBrush(QBrush(self.brush().color().darker(120)))
        super().hoverLeaveEvent(event)
        
    def get_data(self):
        """Get the equipment data."""
        rect = self.rect()
        return {
            "equipment_type": self.equipment_type,
            "name": self.name,
            "x": rect.x(),
            "y": rect.y(),
            "width": rect.width(),
            "height": rect.height()
        }

class RoutePointItem(QGraphicsEllipseItem):
    """Graphics item representing a route point in the layout."""
    
    def __init__(self, x, y, parent=None):
        super().__init__(x - 10, y - 10, 20, 20, parent)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        
        # Set up appearance
        self.setBrush(QBrush(QColor(200, 200, 100, 150)))
        self.setPen(QPen(QColor(100, 100, 0), 2))
        
    def paint(self, painter, option, widget=None):
        """Paint the route point item."""
        super().paint(painter, option, widget)
        
    def hoverEnterEvent(self, event):
        """Handle hover enter events."""
        self.setBrush(QBrush(QColor(255, 255, 100, 200)))
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        """Handle hover leave events."""
        self.setBrush(QBrush(QColor(200, 200, 100, 150)))
        super().hoverLeaveEvent(event)
        
    def get_data(self):
        """Get the route point data."""
        rect = self.rect()
        center = rect.center()
        return {
            "x": center.x(),
            "y": center.y()
        }

class RoutePathItem(QGraphicsPathItem):
    """Graphics item representing a route path in the layout."""
    
    def __init__(self, start_item, end_item, route_type="crane", parent=None):
        super().__init__(parent)
        self.start_item = start_item
        self.end_item = end_item
        self.route_type = route_type
        self.setAcceptHoverEvents(True)
        
        # Set up appearance
        if route_type == "crane":
            self.setPen(QPen(QColor(255, 100, 100), 3, Qt.DashLine))
        else:
            self.setPen(QPen(QColor(100, 100, 255), 3, Qt.DashLine))
            
        # Create the path
        self.update_path()
        
    def update_path(self):
        """Update the path based on start and end items."""
        start_center = self.start_item.rect().center()
        start_pos = self.start_item.pos() + start_center
        
        end_center = self.end_item.rect().center()
        end_pos = self.end_item.pos() + end_center
        
        path = QPainterPath()
        path.moveTo(start_pos)
        path.lineTo(end_pos)
        self.setPath(path)
        
    def paint(self, painter, option, widget=None):
        """Paint the route path item."""
        # Make sure the path is updated before painting
        self.update_path()
        super().paint(painter, option, widget)
        
    def hoverEnterEvent(self, event):
        """Handle hover enter events."""
        if self.route_type == "crane":
            self.setPen(QPen(QColor(255, 0, 0), 4, Qt.DashLine))
        else:
            self.setPen(QPen(QColor(0, 0, 255), 4, Qt.DashLine))
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        """Handle hover leave events."""
        if self.route_type == "crane":
            self.setPen(QPen(QColor(255, 100, 100), 3, Qt.DashLine))
        else:
            self.setPen(QPen(QColor(100, 100, 255), 3, Qt.DashLine))
        super().hoverLeaveEvent(event)
        
    def get_data(self):
        """Get the route path data."""
        return {
            "start": self.start_item.get_data(),
            "end": self.end_item.get_data(),
            "route_type": self.route_type
        }

class LayoutScene(QGraphicsScene):
    """Custom graphics scene for the layout."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.equipment_items = []
        self.bay_items = []
        self.route_points = []
        self.route_paths = []
        self.ladle_car_paths = {}
        
        # Mode flags
        self.bay_mode = False
        self.route_mode = False
        self.ladle_path_mode = False
        
        # Temporary items
        self.bay_start_pos = None
        self.temp_bay_rect = None
        self.route_start_item = None
        self.route_type = "crane"
        
        # Set a background color
        self.setBackgroundBrush(QBrush(QColor(240, 240, 240)))
        
        # Grid settings
        self.grid_visible = True
        self.grid_size = 50
        
    def drawBackground(self, painter, rect):
        """Draw the scene background with grid."""
        super().drawBackground(painter, rect)
        
        if self.grid_visible:
            # Draw the grid
            grid_pen = QPen(QColor(200, 200, 200))
            painter.setPen(grid_pen)
            
            # Calculate grid lines within the visible area
            left = int(rect.left() - (rect.left() % self.grid_size))
            top = int(rect.top() - (rect.top() % self.grid_size))
            
            # Draw vertical lines
            for x in range(left, int(rect.right()), self.grid_size):
                painter.drawLine(x, rect.top(), x, rect.bottom())
                
            # Draw horizontal lines
            for y in range(top, int(rect.bottom()), self.grid_size):
                painter.drawLine(rect.left(), y, rect.right(), y)
                
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
    
    def paint(self, painter, option, widget=None):
        """Paint custom scene content."""
        super().paint(painter, option, widget)
        # Draw paths
        self.draw_ladle_car_paths(painter)
                
    def set_bay_mode(self, enabled):
        """Set bay mode."""
        self.bay_mode = enabled
        if enabled:
            self.route_mode = False
            self.ladle_path_mode = False
        
    def set_route_mode(self, enabled, route_type="crane"):
        """Set route mode."""
        self.route_mode = enabled
        self.route_type = route_type
        if enabled:
            self.bay_mode = False
            self.ladle_path_mode = False
            
    def set_ladle_path_mode(self, enabled):
        """Set ladle path mode."""
        self.ladle_path_mode = enabled
        if enabled:
            self.bay_mode = False
            self.route_mode = False
    
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if event.button() == Qt.LeftButton and self.bay_mode:
            self.bay_start_pos = event.scenePos()
            self.temp_bay_rect = QGraphicsRectItem(
                self.bay_start_pos.x(),
                self.bay_start_pos.y(),
                0, 0
            )
            self.temp_bay_rect.setBrush(QBrush(QColor(100, 100, 255, 50)))
            self.temp_bay_rect.setPen(QPen(QColor(100, 100, 255), 2, Qt.DashLine))
            self.addItem(self.temp_bay_rect)
            event.accept()
            return
            
        if event.button() == Qt.LeftButton and self.route_mode:
            item = self.itemAt(event.scenePos(), QTransform())
            if isinstance(item, (EquipmentItem, RoutePointItem)):
                self.route_start_item = item
                event.accept()
                return
                
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        """Handle mouse move events."""
        if self.bay_mode and self.bay_start_pos:
            # Update the temporary bay rectangle
            pos = event.scenePos()
            rect = QRectF(self.bay_start_pos, pos).normalized()
            self.temp_bay_rect.setRect(rect)
            event.accept()
            return
            
        super().mouseMoveEvent(event)
        
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
            
        # Handle ladle path mode clicks - forward to the ladle path editor
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
        
    def add_route_point(self, x, y):
        """Add a route point at the given coordinates."""
        point = RoutePointItem(x, y)
        self.addItem(point)
        self.route_points.append(point)
        return point
        
    def clear_all(self):
        """Clear all items from the scene."""
        for item in self.equipment_items + self.bay_items + self.route_points + self.route_paths:
            self.removeItem(item)
        self.equipment_items = []
        self.bay_items = []
        self.route_points = []
        self.route_paths = []
        self.ladle_car_paths = {}
        
        # Make sure we update the UI
        self.update()
        
    def get_equipment_data(self):
        """Get data for all equipment items."""
        return [item.get_data() for item in self.equipment_items]
        
    def get_bay_data(self):
        """Get data for all bay items."""
        return [item.get_data() for item in self.bay_items]
        
    def get_route_point_data(self):
        """Get data for all route points."""
        return [point.get_data() for point in self.route_points]
        
    def get_route_path_data(self):
        """Get data for all route paths."""
        return [path.get_data() for path in self.route_paths]
        
    def add_equipment(self, equipment_type, name, x, y, width, height):
        """Add an equipment item to the scene."""
        equipment = EquipmentItem(equipment_type, name, x, y, width, height)
        self.addItem(equipment)
        self.equipment_items.append(equipment)
        return equipment

class LayoutView(QGraphicsView):
    """Custom graphics view for the layout."""
    
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setRenderHint(QPainter.TextAntialiasing, True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        # Set up scroll bars
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        # Set the scene rect to a large area
        scene.setSceneRect(-5000, -5000, 10000, 10000)
        
        # Initialize the scale factor for zooming
        self.scale_factor = 1.0
        
    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming."""
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        
        # Save the scene pos
        old_pos = self.mapToScene(event.pos())
        
        # Zoom
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        
        # Update the scale factor
        self.scale_factor *= zoom_factor
        
        # Limit the scale factor
        if self.scale_factor < 0.1:
            self.scale_factor = 0.1
            return
        elif self.scale_factor > 10:
            self.scale_factor = 10
            return
            
        # Apply zoom
        self.scale(zoom_factor, zoom_factor)
        
        # Get the new position
        new_pos = self.mapToScene(event.pos())
        
        # Move scene to old position
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
        
    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            # Zoom in
            self.scale(1.25, 1.25)
            self.scale_factor *= 1.25
        elif event.key() == Qt.Key_Minus:
            # Zoom out
            self.scale(0.8, 0.8)
            self.scale_factor *= 0.8
        elif event.key() == Qt.Key_R:
            # Reset view
            self.resetTransform()
            self.scale_factor = 1.0
        elif event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            # Delete selected items
            for item in self.scene().selectedItems():
                if isinstance(item, (EquipmentItem, BayItem, RoutePointItem, RoutePathItem)):
                    self.scene().removeItem(item)
                    if item in self.scene().equipment_items:
                        self.scene().equipment_items.remove(item)
                    elif item in self.scene().bay_items:
                        self.scene().bay_items.remove(item)
                    elif item in self.scene().route_points:
                        self.scene().route_points.remove(item)
                    elif item in self.scene().route_paths:
                        self.scene().route_paths.remove(item)
        else:
            super().keyPressEvent(event)

class EquipmentSelector(QWidget):
    """Widget for selecting equipment types to add to the layout."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Add equipment type selection
        type_group = QGroupBox("Equipment Type")
        type_layout = QVBoxLayout()
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["EAF", "LMF", "VD", "Caster", "LaunchPad", "EntranceExit"])
        type_layout.addWidget(self.type_combo)
        
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # Add name field
        name_group = QGroupBox("Equipment Name")
        name_layout = QVBoxLayout()
        
        self.name_combo = QComboBox()
        self.name_combo.setEditable(True)
        self.update_name_suggestions()
        name_layout.addWidget(self.name_combo)
        
        self.type_combo.currentTextChanged.connect(self.update_name_suggestions)
        
        name_group.setLayout(name_layout)
        layout.addWidget(name_group)
        
        # Add size fields
        size_group = QGroupBox("Size")
        size_layout = QVBoxLayout()
        
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(50, 500)
        self.width_spin.setValue(150)
        self.width_spin.setSingleStep(10)
        width_layout.addWidget(self.width_spin)
        size_layout.addLayout(width_layout)
        
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Height:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(50, 500)
        self.height_spin.setValue(100)
        self.height_spin.setSingleStep(10)
        height_layout.addWidget(self.height_spin)
        size_layout.addLayout(height_layout)
        
        size_group.setLayout(size_layout)
        layout.addWidget(size_group)
        
        # Add a button to add equipment
        self.add_button = QPushButton("Add Equipment")
        self.add_button.clicked.connect(self.add_equipment)
        layout.addWidget(self.add_button)
        
        layout.addStretch()
        
        self.setLayout(layout)
        
    def update_name_suggestions(self):
        """Update name suggestions based on the selected equipment type."""
        equipment_type = self.type_combo.currentText()
        
        name_suggestions = {
            "EAF": ["EAF-1", "EAF-2", "EAF-3"],
            "LMF": ["LMF-1", "LMF-2"],
            "VD": ["VD-1"],
            "Caster": ["Caster-1", "Caster-2"],
            "LaunchPad": ["LaunchPad-1", "LaunchPad-2"],
            "EntranceExit": ["Entrance", "Exit", "Loading", "Unloading"]
        }
        
        self.name_combo.clear()
        if equipment_type in name_suggestions:
            self.name_combo.addItems(name_suggestions[equipment_type])
        
    def add_equipment(self):
        """Add equipment to the layout scene."""
        equipment_type = self.type_combo.currentText()
        name = self.name_combo.currentText()
        width = self.width_spin.value()
        height = self.height_spin.value()
        
        # Get the scene
        view = self.window().findChild(LayoutView)
        if view:
            scene = view.scene()
            
            # Calculate center of current view
            view_center = view.mapToScene(view.viewport().rect().center())
            
            # Add the equipment at the view center
            x = view_center.x() - width/2
            y = view_center.y() - height/2
            
            equipment = scene.add_equipment(equipment_type, name, x, y, width, height)
            self.window().layout_modified = True

class RouteManager(QWidget):
    """Widget for managing routes in the layout."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Add route list
        self.route_list = QListWidget()
        layout.addWidget(self.route_list)
        
        # Add buttons for adding routes
        button_layout = QHBoxLayout()
        
        self.add_crane_route = QPushButton("Add Crane Route")
        self.add_crane_route.clicked.connect(lambda: self.start_route("crane"))
        button_layout.addWidget(self.add_crane_route)
        
        self.add_ladle_route = QPushButton("Add Ladle Route")
        self.add_ladle_route.clicked.connect(lambda: self.start_route("ladle"))
        button_layout.addWidget(self.add_ladle_route)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def start_route(self, route_type):
        """Start adding a route of the specified type."""
        # Find the equipment layout editor
        editor = self.window()
        
        # Enable route mode with the specified type
        if route_type == "crane":
            editor.route_action.setChecked(True)
            editor.toggle_route_mode(True, "crane")
        else:
            editor.route_action.setChecked(True)
            editor.toggle_route_mode(True, "ladle")
            
    def update_route_list(self):
        """Update the route list with routes from the scene."""
        self.route_list.clear()
        
        view = self.window().findChild(LayoutView)
        if not view:
            return
            
        scene = view.scene()
        
        for path in scene.route_paths:
            start_name = getattr(path.start_item, "name", "Point")
            end_name = getattr(path.end_item, "name", "Point")
            
            item_text = f"{start_name} -> {end_name} ({path.route_type})"
            self.route_list.addItem(item_text)

class BayManager(QWidget):
    """Widget for managing bays in the layout."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Add bay list
        self.bay_list = QListWidget()
        layout.addWidget(self.bay_list)
        
        # Add a button to add a bay
        self.add_bay = QPushButton("Add Bay")
        self.add_bay.clicked.connect(self.start_bay)
        layout.addWidget(self.add_bay)
        
        # Add bay selector
        bay_layout = QHBoxLayout()
        bay_layout.addWidget(QLabel("Select Bay:"))
        self.bay_combo = QComboBox()
        bay_layout.addWidget(self.bay_combo)
        layout.addLayout(bay_layout)
        
        self.setLayout(layout)
        
    def start_bay(self):
        """Start adding a bay."""
        # Find the equipment layout editor
        editor = self.window()
        
        # Enable bay mode
        editor.bay_action.setChecked(True)
        editor.toggle_bay_mode(True)
        
    def update_bay_list(self):
        """Update the bay list with bays from the scene."""
        self.bay_list.clear()
        
        view = self.window().findChild(LayoutView)
        if not view:
            return
            
        scene = view.scene()
        
        for bay in scene.bay_items:
            self.bay_list.addItem(bay.name)
            
    def update_bay_combo(self):
        """Update the bay combo box with bays from the scene."""
        current_text = self.bay_combo.currentText()
        self.bay_combo.clear()
        
        view = self.window().findChild(LayoutView)
        if not view:
            return
            
        scene = view.scene()
        
        for bay in scene.bay_items:
            self.bay_combo.addItem(bay.name)
            
        # Try to restore the previous selection
        index = self.bay_combo.findText(current_text)
        if index >= 0:
            self.bay_combo.setCurrentIndex(index)

class EquipmentLayoutEditor(QDialog):
    """Dialog for editing the equipment layout."""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.layout_modified = False
        self.setWindowTitle("Equipment Layout Editor")
        self.setMinimumSize(1200, 800)
        # Attributes for path drawing
        self.path_drawing = False
        self.current_path_waypoints = []
        self.current_path_item = None
        self.create_ui()
        self.load_layout_data()
    
    def create_ui(self):
        """Create the user interface."""
        main_layout = QVBoxLayout()
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(24, 24))
        
        save_action = QAction(QIcon.fromTheme("document-save", QIcon("icons/save.png")), "Save Layout", self)
        save_action.setToolTip("Save the current layout")
        save_action.triggered.connect(self.save_layout)
        toolbar.addAction(save_action)
        
        toolbar.addSeparator()
        
        # Add bay mode toggle
        self.bay_action = QAction(QIcon.fromTheme("edit-select-all", QIcon("icons/bay.png")), "Bay Mode", self)
        self.bay_action.setToolTip("Toggle bay drawing mode")
        self.bay_action.setCheckable(True)
        self.bay_action.toggled.connect(self.toggle_bay_mode)
        toolbar.addAction(self.bay_action)
        
        # Add route mode toggle
        self.route_action = QAction(QIcon.fromTheme("edit-select-all", QIcon("icons/route.png")), "Route Mode", self)
        self.route_action.setToolTip("Toggle route drawing mode")
        self.route_action.setCheckable(True)
        self.route_action.toggled.connect(self.toggle_route_mode)
        toolbar.addAction(self.route_action)
        
        # Add ladle path mode toggle
        self.path_action = QAction(QIcon.fromTheme("edit-select-all", QIcon("icons/path.png")), "Ladle Path Mode", self)
        self.path_action.setToolTip("Toggle ladle path drawing mode")
        self.path_action.setCheckable(True)
        self.path_action.toggled.connect(self.toggle_ladle_path_mode)
        toolbar.addAction(self.path_action)
        
        toolbar.addSeparator()
        
        # Zoom controls
        zoom_in_action = QAction(QIcon.fromTheme("zoom-in", QIcon("icons/zoom-in.png")), "Zoom In", self)
        zoom_in_action.setToolTip("Zoom in")
        zoom_in_action.triggered.connect(lambda: self.view.scale(1.25, 1.25))
        toolbar.addAction(zoom_in_action)
        
        zoom_out_action = QAction(QIcon.fromTheme("zoom-out", QIcon("icons/zoom-out.png")), "Zoom Out", self)
        zoom_out_action.setToolTip("Zoom out")
        zoom_out_action.triggered.connect(lambda: self.view.scale(0.8, 0.8))
        toolbar.addAction(zoom_out_action)
        
        zoom_reset_action = QAction(QIcon.fromTheme("zoom-original", QIcon("icons/zoom-original.png")), "Reset Zoom", self)
        zoom_reset_action.setToolTip("Reset zoom")
        zoom_reset_action.triggered.connect(lambda: self.view.resetTransform())
        toolbar.addAction(zoom_reset_action)
        
        main_layout.addWidget(toolbar)
        
        # Create a splitter for the main content
        splitter = QSplitter(Qt.Horizontal)
        
        # Create and add the scene and view
        self.scene = LayoutScene()
        self.view = LayoutView(self.scene)
        
        # Add controls under the view
        view_container = QWidget()
        view_layout = QVBoxLayout()
        view_layout.setContentsMargins(0, 0, 0, 0)
        
        view_layout.addWidget(self.view)
        
        # Add zoom controls
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(5, 5, 5, 5)
        
        # Add status label
        self.status_label = QLabel("Ready")
        controls_layout.addWidget(self.status_label)
        
        # Add bay selector and path controls
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
        
        # Add spacer
        controls_layout.addStretch()
        
        view_layout.addLayout(controls_layout)
        view_container.setLayout(view_layout)
        
        splitter.addWidget(view_container)
        
        # Create a tab widget for the control panels
        control_tabs = QTabWidget()
        
        # Add equipment selector
        self.equipment_selector = EquipmentSelector()
        control_tabs.addTab(self.equipment_selector, "Equipment")
        
        # Add route manager
        self.route_manager = RouteManager()
        control_tabs.addTab(self.route_manager, "Routes")
        
        # Add bay manager
        self.bay_manager = BayManager()
        control_tabs.addTab(self.bay_manager, "Bays")
        
        # Add ladle path editor
        self.ladle_path_editor = LadlePathEditor()
        control_tabs.addTab(self.ladle_path_editor, "Ladle Car Paths")
        
        # Connect the ladle path editor to the scene
        splitter.addWidget(control_tabs)
        
        main_layout.addWidget(splitter)
        
        # Add button layout
        button_layout = QHBoxLayout()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)
        
        save_close_button = QPushButton("Save and Close")
        save_close_button.clicked.connect(self.accept)
        button_layout.addWidget(save_close_button)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
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
        
    def toggle_bay_mode(self, checked):
        """Toggle bay drawing mode."""
        self.scene.set_bay_mode(checked)
        
        if checked:
            if self.route_action.isChecked():
                self.route_action.setChecked(False)
            if self.path_action.isChecked():
                self.path_action.setChecked(False)
            self.status_label.setText("Bay mode: Click and drag to add a bay")
        else:
            self.status_label.setText("Ready")
            
    def toggle_route_mode(self, checked, route_type="crane"):
        """Toggle route drawing mode."""
        self.scene.set_route_mode(checked, route_type)
        
        if checked:
            if self.bay_action.isChecked():
                self.bay_action.setChecked(False)
            if self.path_action.isChecked():
                self.path_action.setChecked(False)
            self.status_label.setText(f"Route mode ({route_type}): Click on start equipment, then end equipment")
        else:
            self.status_label.setText("Ready")
            
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
    
    def load_layout_data(self):
        """Load layout data from the configuration."""
        # Clear the scene
        self.scene.clear_all()
        
        # Load bays
        for bay_name, bay_data in self.config.get("bays", {}).items():
            bay = BayItem(
                bay_name,
                bay_data.get("x", 0),
                bay_data.get("y", 0),
                bay_data.get("width", 200),
                bay_data.get("height", 150)
            )
            self.scene.addItem(bay)
            self.scene.bay_items.append(bay)
            
        # Load equipment
        equipment_dict = {}
        for item_id, data in self.config.get("equipment_positions", {}).items():
            equipment = EquipmentItem(
                data.get("equipment_type", "Unknown"),
                data.get("name", item_id),
                data.get("x", 0),
                data.get("y", 0),
                data.get("width", 150),
                data.get("height", 100)
            )
            self.scene.addItem(equipment)
            self.scene.equipment_items.append(equipment)
            equipment_dict[item_id] = equipment
            
        # Load route points
        point_dict = {}
        for point_id, data in self.config.get("route_points", {}).items():
            point = RoutePointItem(data.get("x", 0), data.get("y", 0))
            self.scene.addItem(point)
            self.scene.route_points.append(point)
            point_dict[point_id] = point
            
        # Load routes
        for route_id, data in self.config.get("routes", {}).items():
            # Get the start and end items
            start_id = data.get("start", "")
            end_id = data.get("end", "")
            
            # Skip if we can't find the start or end
            if not (start_id in equipment_dict or start_id in point_dict) or \
               not (end_id in equipment_dict or end_id in point_dict):
                continue
                
            # Get the start and end items
            start_item = equipment_dict.get(start_id, point_dict.get(start_id))
            end_item = equipment_dict.get(end_id, point_dict.get(end_id))
            
            # Create and add the route path
            route_type = data.get("type", "crane")
            route = RoutePathItem(start_item, end_item, route_type)
            self.scene.addItem(route)
            self.scene.route_paths.append(route)
        
        # Load ladle car paths
        self.scene.ladle_car_paths = self.config.get("ladle_car_paths", {})
        
        # Update the managers
        self.bay_manager.update_bay_list()
        self.bay_manager.update_bay_combo()
        self.route_manager.update_route_list()
        
        # Update the ladle path editor
        if hasattr(self, "ladle_path_editor"):
            self.ladle_path_editor.initialize_from_config(self.config)
            self.ladle_path_editor.scene = self.scene
            
        # Update the bay selector for paths
        if hasattr(self, "bay_selector"):
            self.bay_selector.clear()
            for bay in self.scene.bay_items:
                self.bay_selector.addItem(bay.name)
        
        self.layout_modified = False
        
    def save_layout(self):
        """Save layout data to the configuration."""
        # Save bays
        bay_dict = {}
        for bay in self.scene.bay_items:
            bay_data = bay.get_data()
            bay_dict[bay_data["name"]] = {
                "x": bay_data["x"],
                "y": bay_data["y"],
                "width": bay_data["width"],
                "height": bay_data["height"]
            }
        self.config["bays"] = bay_dict
        
        # Save equipment
        equipment_dict = {}
        for i, equipment in enumerate(self.scene.equipment_items):
            equipment_data = equipment.get_data()
            equipment_dict[f"equipment_{i}"] = {
                "equipment_type": equipment_data["equipment_type"],
                "name": equipment_data["name"],
                "x": equipment_data["x"],
                "y": equipment_data["y"],
                "width": equipment_data["width"],
                "height": equipment_data["height"]
            }
        self.config["equipment_positions"] = equipment_dict
        
        # Save route points
        point_dict = {}
        for i, point in enumerate(self.scene.route_points):
            point_data = point.get_data()
            point_dict[f"point_{i}"] = {
                "x": point_data["x"],
                "y": point_data["y"]
            }
        self.config["route_points"] = point_dict
        
        # Save routes
        route_dict = {}
        for i, route in enumerate(self.scene.route_paths):
            # Determine the IDs for the start and end items
            start_id = ""
            end_id = ""
            
            for eq_id, eq in equipment_dict.items():
                if eq["name"] == getattr(route.start_item, "name", ""):
                    start_id = eq_id
                if eq["name"] == getattr(route.end_item, "name", ""):
                    end_id = eq_id
            
            for pt_id, pt in point_dict.items():
                if pt["x"] == route.start_item.rect().center().x() and \
                   pt["y"] == route.start_item.rect().center().y():
                    start_id = pt_id
                if pt["x"] == route.end_item.rect().center().x() and \
                   pt["y"] == route.end_item.rect().center().y():
                    end_id = pt_id
            
            route_dict[f"route_{i}"] = {
                "type": route.route_type,
                "start": start_id,
                "end": end_id
            }
        self.config["routes"] = route_dict
        
        # Save ladle car paths from scene to config
        self.config["ladle_car_paths"] = self.scene.ladle_car_paths
        
        QMessageBox.information(self, "Layout Saved", "The layout has been saved to the configuration.")
        self.layout_modified = False
        
    def accept(self):
        """Handle dialog acceptance."""
        # Save the layout before closing
        self.save_layout()
        super().accept()
        
    def reject(self):
        """Handle dialog rejection."""
        if self.layout_modified:
            reply = QMessageBox.question(
                self, "Save Changes?",
                "Do you want to save your changes before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                self.save_layout()
                super().reject()
            elif reply == QMessageBox.Discard:
                super().reject()
        else:
            super().reject()
            
    def update_bay_combo(self):
        """Update bay combo box with current bay items."""
        current_text = self.bay_manager.bay_combo.currentText()
        self.bay_manager.bay_combo.clear()
        for bay in self.scene.bay_items:
            self.bay_manager.bay_combo.addItem(bay.name)
        
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
        index = self.bay_manager.bay_combo.findText(current_text)
        if index >= 0:
            self.bay_manager.bay_combo.setCurrentIndex(index)

# Function to run the equipment layout editor
def run_equipment_layout_editor(config):
    """Run the equipment layout editor."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    editor = EquipmentLayoutEditor(config)
    result = editor.exec_()
    return result == QDialog.Accepted, config

if __name__ == "__main__":
    # Test the editor
    import sys
    app = QApplication(sys.argv)
    
    # Create a test configuration
    config = {
        "bays": {
            "Melt Shop": {
                "x": 100,
                "y": 100,
                "width": 500,
                "height": 300
            },
            "Caster Bay": {
                "x": 700,
                "y": 100,
                "width": 300,
                "height": 200
            }
        },
        "equipment_positions": {
            "equipment_0": {
                "equipment_type": "EAF",
                "name": "EAF-1",
                "x": 150,
                "y": 150,
                "width": 150,
                "height": 100
            },
            "equipment_1": {
                "equipment_type": "LMF",
                "name": "LMF-1",
                "x": 400,
                "y": 150,
                "width": 150,
                "height": 100
            },
            "equipment_2": {
                "equipment_type": "Caster",
                "name": "Caster-1",
                "x": 750,
                "y": 150,
                "width": 200,
                "height": 100
            }
        }
    }
    
    result, updated_config = run_equipment_layout_editor(config)
    print(f"Editor result: {result}")
    print(f"Updated config: {updated_config}")
    
    sys.exit(app.exec_())