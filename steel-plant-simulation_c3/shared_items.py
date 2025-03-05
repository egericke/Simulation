import logging
from PyQt5.QtWidgets import (QGraphicsItem, QGraphicsEllipseItem, QGraphicsPathItem)
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainterPath)
from PyQt5.QtCore import (Qt, QPointF)

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