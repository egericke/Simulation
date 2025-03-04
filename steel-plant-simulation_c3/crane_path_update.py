with open('equipment_layout_editor.py', 'r') as file:
    content = file.read()

# Add is_dynamic to init
if 'self.transit_time = transit_time' in content:
    content = content.replace('self.transit_time = transit_time', 'self.transit_time = transit_time\n        self.is_dynamic = False')

# Change Crane style from DotLine to SolidLine and add is_dynamic = True
if 'color = QColor(255, 200, 100)  # Orange\n            style = Qt.DotLine' in content:
    content = content.replace('color = QColor(255, 200, 100)  # Orange\n            style = Qt.DotLine', 
                            'color = QColor(255, 200, 100)  # Orange\n            style = Qt.SolidLine')
    content = content.replace('style = Qt.SolidLine\n            width = 3', 
                            'style = Qt.SolidLine\n            width = 3\n            self.is_dynamic = True  # Mark crane routes as dynamic')

# Update the update_path method
update_path_old = """    def update_path(self):
        \"\"\"Update the path between the connected items.\"\"\"
        if not self.start_item or not self.end_item:
            return
        
        path = QPainterPath()
        start_pos = self.start_item.pos()
        end_pos = self.end_item.pos()
        
        # Draw a curved path
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
        self.setPath(path)"""

update_path_new = """    def update_path(self):
        \"\"\"Update the path between the connected items.\"\"\"
        if not self.start_item or not self.end_item:
            return
        
        path = QPainterPath()
        start_pos = self.start_item.pos()
        end_pos = self.end_item.pos()
        
        if self.route_type == "Crane" and hasattr(self, 'is_dynamic') and self.is_dynamic:
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
        
        self.setPath(path)"""

if update_path_old in content:
    content = content.replace(update_path_old, update_path_new)

# Add collision detection to LayoutScene
if 'class LayoutScene(QGraphicsScene):' in content:
    layout_scene_start = content.find('class LayoutScene(QGraphicsScene):')
    init_end = content.find('    def drawBackground(self, painter, rect):', layout_scene_start)
    
    # Add check_crane_collision method after the initialization
    insert_pos = init_end
    collision_method = """    def check_crane_collision(self, crane_item):
        # Check if a crane would collide with any other cranes in the bay
        crane_rect = crane_item.boundingRect().translated(crane_item.pos())
        for item in self.items():
            if isinstance(item, EquipmentItem) and item \!= crane_item and item.equipment_type == "Crane" and item.bay_name == crane_item.bay_name:
                other_rect = item.boundingRect().translated(item.pos())
                if crane_rect.intersects(other_rect):
                    return True
        return False
        
"""
    # Insert collision detection method
    if 'def check_crane_collision(self' not in content:
        content = content[:insert_pos] + collision_method + content[insert_pos:]

# Update itemChange in EquipmentItem class to implement collision detection and bay constraints
if 'def itemChange(self, change, value):' in content:
    item_change_start = content.find('def itemChange(self, change, value):')
    item_change_end = content.find('return super().itemChange(change, value)', item_change_start)
    
    old_item_change = content[item_change_start:item_change_end + len('return super().itemChange(change, value)')]
    
    new_item_change = """def itemChange(self, change, value):
        # Handle item changes, particularly position changes
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
        return super().itemChange(change, value)"""
    
    if old_item_change in content:
        content = content.replace(old_item_change, new_item_change)

# Write updated content back to file
with open('equipment_layout_editor.py', 'w') as file:
    file.write(content)

print("File updated successfully.")
