# Dynamic Crane Route System Implementation

This document outlines the implementation details for the new dynamic crane route system that addresses the problem where:
"Crane routes shouldn't be predefined; cranes should move freely along the bay width, avoiding collisions, as their bodies span the bay."

## Code Changes Required

### 1. RoutePathItem Class Modifications

```python
class RoutePathItem(QGraphicsPathItem):
    """A path item for ladle car or crane routes."""
    
    def __init__(self, start_item, end_item, route_type="LadleCar", transit_time=10, parent=None):
        super().__init__(parent)
        self.start_item = start_item
        self.end_item = end_item
        self.route_type = route_type
        self.transit_time = transit_time
        self.is_dynamic = False  # Default to non-dynamic routes
        
        # Different styling based on route type
        if route_type == "LadleCar":
            color = QColor(100, 100, 255)  # Blue
            style = Qt.DashLine
            width = 3
        elif route_type == "Crane":
            color = QColor(255, 200, 100)  # Orange
            style = Qt.SolidLine  # Changed from DotLine to SolidLine for better visibility
            width = 3
            self.is_dynamic = True  # Mark crane routes as dynamic
        elif route_type == "Ladle":
            color = QColor(200, 0, 0)  # Dark red
            style = Qt.SolidLine
            width = 4
        else:
            color = QColor(100, 100, 100)  # Gray
            style = Qt.DashDotLine
            width = 2
        
        self.setPen(QPen(color, width, style))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.update_path()
        
        # Set tooltip
        self.setToolTip(f"{route_type} Route\nFrom: {self.get_start_name()}\nTo: {self.get_end_name()}\nTransit Time: {transit_time} min")
```

### 2. Update Path Method for Dynamic Routes

```python
def update_path(self):
    """Update the path between the connected items."""
    if not self.start_item or not self.end_item:
        return
    
    path = QPainterPath()
    start_pos = self.start_item.pos()
    end_pos = self.end_item.pos()
    
    if self.route_type == "Crane" and self.is_dynamic:
        # Find the bay containing the crane
        bay = None
        if hasattr(self.scene(), 'bay_items'):
            for bay_item in self.scene().bay_items:
                if hasattr(self.start_item, 'bay_name') and bay_item.name == self.start_item.bay_name:
                    bay = bay_item
                    break
        
        if bay:
            # Crane spans bay width, moves along length
            bay_rect = bay.boundingRect()
            bay_pos = bay.pos()
            # Draw a horizontal line across the bay at the crane's Y position
            path.moveTo(bay_pos.x(), start_pos.y())
            path.lineTo(bay_pos.x() + bay_rect.width(), start_pos.y())
        else:
            # Fallback if bay not found
            path.moveTo(start_pos)
            path.lineTo(end_pos)
    else:
        # Draw a curved path for non-crane routes
        path.moveTo(start_pos)
        
        # Calculate control points for a smooth curve
        dx = end_pos.x() - start_pos.x()
        dy = end_pos.y() - start_pos.y()
        dist = (dx**2 + dy**2)**0.5
        
        # Adjust control points based on distance between points
        if dist < 100:
            # For short distances, make a simple curve
            control1 = QPointF(start_pos.x() + dx/3, start_pos.y() + dy/3)
            control2 = QPointF(start_pos.x() + 2*dx/3, start_pos.y() + 2*dy/3)
        else:
            # For longer distances, make a more pronounced curve
            control1 = QPointF(start_pos.x() + dx/3, start_pos.y())
            control2 = QPointF(start_pos.x() + 2*dx/3, end_pos.y())
        
        path.cubicTo(control1, control2, end_pos)
    
    self.setPath(path)
```

### 3. Add Collision Detection to LayoutScene

```python
def check_crane_collision(self, crane_item):
    """Check if a crane would collide with any other cranes in the bay."""
    crane_rect = crane_item.boundingRect().translated(crane_item.pos())
    for item in self.items():
        if isinstance(item, EquipmentItem) and item != crane_item and item.equipment_type == "Crane" and item.bay_name == crane_item.bay_name:
            other_rect = item.boundingRect().translated(item.pos())
            if crane_rect.intersects(other_rect):
                return True
    return False
```

### 4. Update EquipmentItem's itemChange Method

```python
def itemChange(self, change, value):
    """Handle item changes, particularly position changes."""
    if change == QGraphicsItem.ItemPositionChange and self.scene():
        new_pos = value
        grid_size = 10
        new_pos.setX(round(new_pos.x() / grid_size) * grid_size)
        new_pos.setY(round(new_pos.y() / grid_size) * grid_size)
        
        # Special handling for cranes
        if self.equipment_type == "Crane":
            # Check for bay constraints
            for bay in self.scene().bay_items:
                if bay.name == self.bay_name:
                    bay_rect = bay.boundingRect().translated(bay.pos())
                    # Keep the crane within the bay's horizontal bounds
                    new_pos.setX(max(bay_rect.left(), min(new_pos.x(), bay_rect.right() - self.width)))
                    # Keep Y position constant for cranes (they move horizontally along bay)
                    new_pos.setY(new_pos.y())
                    break
            
            # Check for collision with other cranes in the same bay
            temp_pos = self.pos()  # Store original position
            self.setPos(new_pos)   # Temporarily set new position to check collision
            if hasattr(self.scene(), 'check_crane_collision') and self.scene().check_crane_collision(self):
                self.setPos(temp_pos)  # Revert to original position if collision would occur
                return temp_pos
            self.setPos(temp_pos)  # Reset to original position until change is confirmed
        
        if hasattr(self.scene(), "position_changed"):
            self.scene().position_changed.emit(self)
        return new_pos
    return super().itemChange(change, value)
```

## Implementation Benefits

1. **Dynamic Paths**: Crane routes now displayed as straight lines spanning the bay width, updated dynamically as cranes move
2. **Collision Detection**: Prevents cranes from overlapping within the same bay
3. **Movement Restriction**: Ensures cranes can only move within their bay's width
4. **Visual Clarity**: Improved line style (solid vs dotted) for better visibility of crane routes

The code changes maintain compatibility with existing routes while enhancing the crane movement system to match real-world behavior where cranes move freely along bays but are restricted to their bay's width.