import logging
from typing import Dict, List, Optional, Any
from .bay import Bay  # Assuming Bay class is defined in bay.py

logger = logging.getLogger(__name__)

class SpatialManager:
    """
    Manages the spatial aspects of a steel plant simulation.

    Handles bays, equipment placement, crane movements, and path planning for ladle cars.
    Includes optimizations like caching and enhanced features like user-defined bay dimensions.
    """
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the SpatialManager with a configuration dictionary.

        Args:
            config (dict): Configuration containing bays, ladle car speed, etc.
        """
        self.config = config
        self.bays: Dict[str, Bay] = {}
        self.equipment_locations: Dict[str, Dict[str, Any]] = {}
        self.ladle_car_paths: Dict[str, Dict[str, Any]] = {}
        self.bay_centers: Dict[str, Dict[str, float]] = {}
        self.path_cache: Dict[str, Dict[str, Any]] = {}

        self._setup_bays()
        self._setup_default_paths()

        if not self.bays:
            logger.warning("SpatialManager initialized with no bays; check config['bays']")
        logger.info(f"SpatialManager initialized with {len(self.bays)} bays")

    def _setup_bays(self) -> None:
        """Create bay objects from configuration and cache their centers."""
        bays_config = self.config.get("bays", {})
        if not bays_config:
            logger.warning("No 'bays' key in config or empty bays configuration")
            return
        for bay_id, bay_config in bays_config.items():
            try:
                # Support both old (x_offset, y_offset) and new (x, y, width, height) formats
                x = float(bay_config.get("x", bay_config.get("x_offset", 0)))
                y = float(bay_config.get("y", bay_config.get("y_offset", 0)))
                width = float(bay_config.get("width", 100))  # Default width
                height = float(bay_config.get("height", 100))  # Default height
                top_left = {"x": x, "y": y}
                bottom_right = {"x": x + width, "y": y + height}
                bay = Bay(
                    bay_id=bay_id,
                    top_left=top_left,
                    bottom_right=bottom_right,
                    crane_paths=bay_config.get("crane_paths", [])
                )
                self.bays[bay_id] = bay
                # Cache bay center for efficiency
                self.bay_centers[bay_id] = bay.get_center()
                logger.debug(f"Created bay {bay_id} with top_left {top_left} and bottom_right {bottom_right}")
            except (KeyError, TypeError, ValueError) as e:
                logger.error(f"Invalid data for bay {bay_id}: {e}")

    def _setup_default_paths(self) -> None:
        """Create default paths between bays for ladle cars with actual distance calculations."""
        bay_list = list(self.bays.values())
        default_speed = self.config.get("ladle_car_speed", 150.0)  # units/min
        if default_speed <= 0:
            logger.error("Ladle car speed must be positive; default paths not created")
            return
        for i in range(len(bay_list) - 1):
            bay1, bay2 = bay_list[i], bay_list[i + 1]
            center1 = self.bay_centers[bay1.bay_id]
            center2 = self.bay_centers[bay2.bay_id]
            dx = center2["x"] - center1["x"]
            dy = center2["y"] - center1["y"]
            distance = (dx**2 + dy**2)**0.5
            travel_time = distance / default_speed
            path_key = f"{bay1.bay_id}_to_{bay2.bay_id}"
            self.ladle_car_paths[path_key] = {
                "waypoints": [center1, center2],
                "distance": distance,
                "travel_time": travel_time
            }
            # Add reverse path
            path_key_reverse = f"{bay2.bay_id}_to_{bay1.bay_id}"
            self.ladle_car_paths[path_key_reverse] = {
                "waypoints": [center2, center1],
                "distance": distance,
                "travel_time": travel_time
            }
            logger.debug(f"Created path {path_key}: distance {distance:.2f}, time {travel_time:.2f} min")

    def get_bay_at_position(self, x: float, y: float) -> Optional[str]:
        """
        Return the bay ID containing the given position.

        Args:
            x (float): X-coordinate
            y (float): Y-coordinate

        Returns:
            str or None: Bay ID if position is within a bay, None otherwise
        """
        for bay_id, bay in self.bays.items():
            tl, br = bay.top_left, bay.bottom_right
            if tl["x"] <= x <= br["x"] and tl["y"] <= y <= br["y"]:
                return bay_id
        return None

    def add_equipment(self, equipment_type: str, x: float, y: float) -> None:
        """
        Add equipment position to the spatial map.

        Args:
            equipment_type (str): Type of equipment (e.g., "EAF")
            x (float): X-coordinate
            y (float): Y-coordinate
        """
        self.equipment_locations[equipment_type] = {"x": x, "y": y}
        logger.info(f"Added equipment {equipment_type} at ({x}, {y})")

    def get_unit_position(self, unit_id: str) -> Dict[str, float]:
        """
        Return the position of the specified unit.

        Args:
            unit_id (str): ID of the equipment/unit

        Returns:
            dict: Position {'x': x, 'y': y}, defaults to (0, 0) if not found
        """
        if unit_id not in self.equipment_locations:
            logger.warning(f"Unit {unit_id} not found in equipment_locations")
            return {"x": 0, "y": 0}
        return self.equipment_locations[unit_id]["position"]

    def place_equipment(self, equipment_id: str, equipment_type: str, bay_id: str, position: Dict[str, float]) -> bool:
        """
        Place equipment in a bay at the specified position.

        Args:
            equipment_id (str): Unique identifier for the equipment
            equipment_type (str): Type of equipment (e.g., "EAF", "LMF")
            bay_id (str): ID of the bay
            position (dict): Position {'x': x, 'y': y}

        Returns:
            bool: True if placement succeeded, False otherwise
        """
        if bay_id not in self.bays:
            logger.error(f"Cannot place equipment in non-existent bay {bay_id}")
            return False
        bay = self.bays[bay_id]
        tl, br = bay.top_left, bay.bottom_right
        if not (tl["x"] <= position["x"] <= br["x"] and tl["y"] <= position["y"] <= br["y"]):
            logger.error(f"Position {position} is outside bay {bay_id}")
            return False
        result = bay.add_equipment(equipment_id, equipment_type, position)
        if result:
            self.equipment_locations[equipment_id] = {
                "bay_id": bay_id,
                "type": equipment_type,
                "position": position
            }
            logger.info(f"Placed equipment {equipment_id} in bay {bay_id} at {position}")
        return result

    def get_path_between_equipment(self, from_equipment_id: str, to_equipment_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a path for a ladle car between two equipment pieces.

        Args:
            from_equipment_id (str): Starting equipment ID
            to_equipment_id (str): Destination equipment ID

        Returns:
            dict or None: Path info with waypoints, distance, travel_time, or None if no path
        """
        if (from_equipment_id not in self.equipment_locations or
                to_equipment_id not in self.equipment_locations):
            logger.error("Cannot find path between non-existent equipment")
            return None

        from_bay = self.equipment_locations[from_equipment_id]["bay_id"]
        to_bay = self.equipment_locations[to_equipment_id]["bay_id"]
        from_pos = self.equipment_locations[from_equipment_id]["position"]
        to_pos = self.equipment_locations[to_equipment_id]["position"]

        cache_key = f"{from_equipment_id}_to_{to_equipment_id}"
        if cache_key in self.path_cache:
            return self.path_cache[cache_key]

        ladle_car_speed = self.config.get("ladle_car_speed", 150)
        if ladle_car_speed <= 0:
            logger.error("Ladle car speed must be positive")
            return None

        if from_bay == to_bay:
            dx = to_pos["x"] - from_pos["x"]
            dy = to_pos["y"] - from_pos["y"]
            distance = (dx**2 + dy**2)**0.5
            travel_time = distance / ladle_car_speed
            path = {
                "waypoints": [from_pos, to_pos],
                "distance": distance,
                "travel_time": travel_time
            }
        else:
            path_key = f"{from_bay}_to_{to_bay}"
            if path_key not in self.ladle_car_paths:
                logger.warning(f"No path found between bays {from_bay} and {to_bay}")
                return None
            bay_path = self.ladle_car_paths[path_key]
            waypoints = [from_pos] + bay_path["waypoints"] + [to_pos]
            total_distance = bay_path["distance"] + 50  # Buffer for equipment offset
            total_time = total_distance / ladle_car_speed
            path = {
                "waypoints": waypoints,
                "distance": total_distance,
                "travel_time": total_time
            }
        self.path_cache[cache_key] = path
        return path

    def check_crane_collisions(self, time: float) -> Dict[str, bool]:
        """
        Check for potential crane collisions at the given time.

        Args:
            time (float): Current simulation time

        Returns:
            dict: Map of bay_id to collision status (True if collision detected)
        """
        collisions = {}
        for bay_id, bay in self.bays.items():
            crane_positions = {}
            for i in range(self.config.get("n_cranes_per_bay", 2)):
                crane_id = f"{bay_id}_crane_{i+1}"
                position = bay.get_crane_position_at_time(crane_id, time)
                if position:
                    crane_positions[crane_id] = position
            collisions[bay_id] = bay.check_crane_collision(crane_positions)
        return collisions

    def get_path_between_bays(self, from_bay_id: str, to_bay_id: str, car_type: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Get the path between two bays, tailored to the ladle car type.

        Args:
            from_bay_id (str): Starting bay ID
            to_bay_id (str): Destination bay ID
            car_type (str, optional): Type of ladle car ("tapping", "treatment", "rh")

        Returns:
            list or None: List of path segments with 'from', 'to', 'distance', 'travel_time'
        """
        if from_bay_id not in self.bays or to_bay_id not in self.bays:
            logger.error(f"One or both bays {from_bay_id} and {to_bay_id} not found")
            return None

        start = self.bay_centers[from_bay_id]
        end = self.bay_centers[to_bay_id]
        waypoints = []
        if car_type in ["tapping", "treatment"]:
            intermediate = {"x": end["x"], "y": start["y"]}
            waypoints = [start, intermediate, end]
        else:
            waypoints = [start, end]

        segments = []
        ladle_car_speed = self.config.get("ladle_car_speed", 150)
        if ladle_car_speed <= 0:
            logger.error("Ladle car speed must be positive")
            return None
        for i in range(len(waypoints) - 1):
            p1 = waypoints[i]
            p2 = waypoints[i + 1]
            dx = p2["x"] - p1["x"]
            dy = p2["y"] - p1["y"]
            distance = (dx**2 + dy**2)**0.5
            travel_time = distance / ladle_car_speed
            segments.append({
                "from": p1,
                "to": p2,
                "distance": distance,
                "travel_time": travel_time
            })
        logger.info(f"Generated path from {from_bay_id} to {to_bay_id} for {car_type}: {len(segments)} segments")
        return segments

    def get_crane_home_position(self, bay_id: str) -> Dict[str, float]:
        """
        Get the home position for a crane in the specified bay.

        Args:
            bay_id (str): ID of the bay

        Returns:
            dict: Position {'x': x, 'y': y}, defaults to (0, 0) if bay not found
        """
        if bay_id not in self.bays:
            logger.error(f"Bay {bay_id} not found in SpatialManager.get_crane_home_position")
            return {"x": 0, "y": 0}

        bay = self.bays[bay_id]
        if hasattr(bay, 'crane_paths') and bay.crane_paths:
            path = bay.crane_paths[0]
            return {"x": path.get("start_x", 0), "y": path.get("y", 0)}
        center = self.bay_centers[bay_id]
        logger.info(f"Using bay center as crane home position for bay {bay_id}: {center}")
        return center
    

    def get_bay_position(self, bay_id: str) -> Dict[str, float]:
        """
        Return the center position of the specified bay.

        Args:
            bay_id (str): ID of the bay (e.g., "bay1")

        Returns:
            dict: Position {'x': x, 'y': y}, defaults to (0, 0) if bay not found
        """
        if bay_id not in self.bay_centers:
            logger.warning(f"Bay {bay_id} not found in bay_centers; returning default position")
            return {"x": 0, "y": 0}
        return self.bay_centers[bay_id]