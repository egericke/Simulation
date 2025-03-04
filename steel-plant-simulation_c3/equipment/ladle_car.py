import salabim as sim
import logging

logger = logging.getLogger(__name__)

class BaseLadleCar(sim.Component):
    def __init__(self, env, car_id, car_type, home_bay, speed=150, spatial_manager=None, on_idle_callback=None, name=None, **kwargs):
        """
        Initialize a base ladle car.

        Args:
            env: Salabim simulation environment.
            car_id: Unique identifier for the car.
            car_type: Type of ladle car ("tapping", "treatment", "rh").
            home_bay: Starting bay location.
            speed: Movement speed in units per minute (default: 150).
            spatial_manager: SpatialManager instance for pathfinding and positioning.
            on_idle_callback: Callback function to trigger when the car becomes idle.
            name: Custom name for the car (optional).
        """
        # Validate car_type
        valid_types = ["tapping", "treatment", "rh"]
        if car_type.lower() not in valid_types:
            raise ValueError(f"Invalid car_type '{car_type}'. Must be one of {valid_types}")
            
        super().__init__(env=env, name=name or f"{car_type.capitalize()}Car_{car_id}", **kwargs)
        self.car_id = car_id
        self.car_type = car_type.lower()
        self.home_bay = home_bay
        self.speed = speed
        self.spatial_manager = spatial_manager
        self.on_idle_callback = on_idle_callback
        
        # Store the string state explicitly to handle Salabim's State.value returning a Monitor
        self._status_string = "idle"
        
        # Create the State object for Salabim but access via our property/methods
        self._car_status_state = sim.State("car_status", value=self._status_string, env=env)
        
        self.current_bay = home_bay
        self.position = spatial_manager.get_bay_position(home_bay) if spatial_manager else {"x": 0, "y": 0}
        self.current_heat = None
        self.current_ladle = None
        self.destination = None
        self.path = []
        self.move_queue = []  # Ensure move_queue is initialized
        self.current_path_segment = 0
        self.total_distance_traveled = 0.0
        self.activate()
        logger.info(f"{self.name()} initialized at {home_bay}")

    # Property to access car_status with an adapter to handle Salabim's behavior
    @property
    def car_status(self):
        """Get the car's status State object."""
        return self._car_status_state
    
    # Disable direct assignment to car_status
    @car_status.setter
    def car_status(self, value):
        """Prevent direct assignment to car_status."""
        logger.error(f"Attempted direct assignment to car_status on {self.name()}. Use set_status() instead.")
        raise AttributeError("Use set_status() method to modify car status")

    # Helper method to get the actual status string safely
    def get_status_string(self):
        """
        Get the current status as a string, safely handling Salabim's Monitor objects.
        
        Returns:
            str: Current status string
        """
        # Return our explicitly tracked status string
        return self._status_string

    def set_status(self, new_status):
        """
        Set the ladle car's status and trigger callback if idle.

        Args:
            new_status (str): New status ("idle", "moving", "loading", "unloading").
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Enhanced validation with type checking
        if not isinstance(new_status, str):
            logger.error(f"Invalid status type for {self.name()}: {type(new_status)}. Expected string.")
            return False
            
        valid_statuses = ["idle", "moving", "loading", "unloading"]
        if new_status not in valid_statuses:
            logger.warning(f"Invalid status '{new_status}' for {self.name()}; ignoring")
            return False
        
        # Only update if status has changed
        if new_status != self._status_string:
            logger.debug(f"{self.name()} status changing from {self._status_string} to {new_status}")
            
            # Update both our internal string and the Salabim State
            self._status_string = new_status
            self._car_status_state.set(new_status)
            
            if new_status == "idle" and callable(self.on_idle_callback):
                try:
                    logger.info(f"{self.name()} is idle, triggering callback")
                    self.on_idle_callback()
                except Exception as e:
                    logger.error(f"Error in on_idle_callback for {self.name()}: {e}")
        return True

    def process(self):
        """
        Main process loop for the ladle car.

        Manages states:
        - idle: Wait for tasks.
        - moving: Travel along the assigned path.
        - loading: Acquire heat using a crane.
        - unloading: Deliver heat to the destination unit using a crane.
        """
        while True:
            try:
                # Get current status with our safe method
                current_status = self.get_status_string()

                if current_status == "idle":
                    # Wait for a task assignment; callback may trigger new tasks
                    if callable(self.on_idle_callback):
                        try:
                            self.on_idle_callback()
                        except Exception as e:
                            logger.error(f"Idle callback failed for {self.name()}: {e}")
                    yield self.hold(1)  # Minimal wait to avoid tight looping

                elif current_status == "moving":
                    if not self.path or self.current_path_segment >= len(self.path):
                        logger.warning(f"{self.name()} in 'moving' state with invalid path; resetting to idle")
                        self.set_status("idle")
                        self.path = []
                        self.current_path_segment = 0
                        self.destination = None
                        continue

                    segment = self.path[self.current_path_segment]
                    travel_time = segment.get("travel_time", 0)
                    to_point = segment.get("to", {"x": 0, "y": 0})

                    if travel_time <= 0:
                        logger.warning(f"Invalid travel time {travel_time} for segment; using default 1 unit")
                        travel_time = 1

                    # Calculate distance for this segment
                    distance = ((self.position['x'] - to_point['x'])**2 + (self.position['y'] - to_point['y'])**2)**0.5
                    self.total_distance_traveled += distance

                    logger.info(f"{self.name()} moving from ({self.position['x']}, {self.position['y']}) "
                               f"to ({to_point['x']}, {to_point['y']}), ETA: {travel_time:.1f} min")
                    yield self.hold(travel_time)

                    # Update position and path progress
                    self.position = to_point
                    self.current_path_segment += 1

                    # Update heat temperature if carrying one
                    if self.current_heat:
                        try:
                            self.current_heat.update_temperature(self.env.now())
                        except AttributeError:
                            logger.warning(f"Heat {self.current_heat.id} lacks update_temperature method")

                    # Check if journey is complete
                    if self.current_path_segment >= len(self.path):
                        if self.destination:
                            self.current_bay = self.destination.get("bay", self.current_bay)
                            self.set_status("unloading" if self.current_heat else "idle")
                            if not self.current_heat:
                                self.destination = None
                                self.path = []
                                self.current_path_segment = 0
                        else:
                            logger.error(f"{self.name()} completed path but has no destination")
                            self.set_status("idle")

                elif current_status == "loading":
                    crane = self._request_crane(self.current_bay, "loading")
                    if crane:
                        load_time = crane.assign_task(source="unit", destination=f"{self.name()}")
                        logger.info(f"{self.name()} loading heat {self.current_heat.id} with crane, "
                                   f"time: {load_time:.1f} min")
                        yield self.hold(load_time)
                        self.set_status("moving")
                    else:
                        logger.debug(f"{self.name()} waiting for crane in bay {self.current_bay}")
                        yield self.hold(1)  # Wait and retry

                elif current_status == "unloading":
                    crane = self._request_crane(self.current_bay, "unloading")
                    if crane:
                        target_unit = self.destination.get("unit") if self.destination else None
                        if not target_unit or not hasattr(target_unit, "add_heat"):
                            logger.error(f"{self.name()} has invalid or missing destination unit")
                            self.set_status("idle")
                            self.current_heat = None
                            continue

                        unload_time = crane.assign_task(source=f"{self.name()}", destination="unit")
                        logger.info(f"{self.name()} unloading heat {self.current_heat.id} with crane, "
                                   f"time: {unload_time:.1f} min")
                        yield self.hold(unload_time)

                        # Transfer heat to the target unit
                        if target_unit.add_heat(self.current_heat):
                            logger.info(f"Heat {self.current_heat.id} transferred to {target_unit.name}")
                        else:
                            logger.warning(f"Failed to transfer heat {self.current_heat.id} to {target_unit.name}")
                        self.current_heat = None
                        self.destination = None
                        self.path = []
                        self.current_path_segment = 0
                        self.set_status("idle")
                    else:
                        logger.debug(f"{self.name()} waiting for crane in bay {self.current_bay}")
                        yield self.hold(1)  # Wait and retry
                else:
                    logger.warning(f"Unknown status '{current_status}' for {self.name()}; defaulting to idle")
                    self.set_status("idle")
                    yield self.hold(1)
            except Exception as e:
                logger.error(f"Error in {self.name()} process: {e}", exc_info=True)
                # Reset to a safe state
                self.set_status("idle")
                yield self.hold(1)

    def assign_heat(self, heat, destination):
        """
        Assign a heat to the ladle car for transportation.

        Args:
            heat: Heat object to transport.
            destination: Dict with target info (e.g., {"bay": "bay2", "unit": unit_object}).

        Returns:
            bool: True if assignment succeeds, False otherwise.
        """
        # Check availability using our safe status method
        if self.get_status_string() != "idle":
            logger.warning(f"{self.name()} busy (status: {self.get_status_string()}), cannot assign heat {heat.id}")
            return False
            
        self.current_heat = heat
        self.destination = destination
        from_bay = self.current_bay
        to_bay = destination.get("bay")
        
        if not self.spatial_manager:
            logger.error(f"No spatial manager for {self.name()}; using fallback path")
            self.path = [{"from": self.position, "to": self.position, "travel_time": 0}]
        else:
            self.path = self.spatial_manager.get_path(from_bay, to_bay, car_type=self.car_type)
            if not self.path or not isinstance(self.path, list) or not all("travel_time" in seg for seg in self.path):
                logger.error(f"Invalid path from {from_bay} to {to_bay} for {self.name()}")
                self.current_heat = None
                self.destination = None
                return False
                
        self.current_path_segment = 0
        logger.info(f"{self.name()} assigned heat {heat.id} from {from_bay} to {to_bay}, path segments: {len(self.path)}")
        self.set_status("loading")
        return True

    def is_available(self):
        """
        Check if the ladle car is available for a new task.

        Returns:
            bool: True if idle, False otherwise.
        """
        return self.get_status_string() == "idle"

    def _request_crane(self, bay, operation):
        """
        Request a crane in the specified bay for loading or unloading.

        Args:
            bay (str): Bay ID where the crane is needed.
            operation (str): "loading" or "unloading".

        Returns:
            Crane: Available crane object, or None if unavailable.
        """
        if not hasattr(self.env, 'transport_manager') or not self.env.transport_manager:
            logger.error(f"TransportManager not initialized in environment for {self.name()}")
            return None
        cranes = self.env.transport_manager.cranes.get(bay, [])
        for crane in cranes:
            if crane.is_available():
                logger.debug(f"{self.name()} assigned crane {crane.name()} for {operation} in bay {bay}")
                return crane
        logger.info(f"No available cranes for {operation} in bay {bay} by {self.name()}")
        return None