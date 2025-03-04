import salabim as sim
import logging
import time
from enum import Enum
from heapq import heappush, heappop
from threading import Lock

logger = logging.getLogger(__name__)

class CraneState(Enum):
    IDLE = "idle"
    MOVING = "moving"
    LIFTING = "lifting"
    LOWERING = "lowering"
    ERROR = "error"  # New state for error conditions

class Crane(sim.Component):
    LIFT_TIME = 3  # minutes
    LOWER_TIME = 3  # minutes
    TASK_OVERHEAD = 6  # lift + lower time in minutes
    DEADLOCK_TIMEOUT = 10  # minutes - timeout for detecting deadlocks

    def __init__(self, env, crane_id, bay, speed=100, accel=10, hoist_speed=20, spatial_manager=None, name=None, **kwargs):
        """
        Initialize a crane component.
        
        Args:
            env: Simulation environment
            crane_id: Unique identifier for the crane
            bay: Bay where the crane is located
            speed: Maximum speed in units/min (default: 100)
            accel: Acceleration in units/min^2 (default: 10)
            hoist_speed: Vertical movement speed in units/min (default: 20)
            spatial_manager: Reference to the spatial manager
            name: Optional name override
            **kwargs: Additional arguments to pass to Component constructor
        """
        if not isinstance(crane_id, (int, str)):
            raise TypeError(f"crane_id must be int or str, got {type(crane_id)}")
        if not isinstance(bay, str):
            raise TypeError(f"bay must be str, got {type(bay)}")
        if not speed > 0:
            raise ValueError(f"speed must be positive, got {speed}")
            
        super().__init__(env=env, name=name or f"Crane_{bay}_{crane_id}", **kwargs)
        self.unit_id = crane_id
        self.bay = bay
        self.speed = speed
        self.accel = accel  # units/min^2
        self.hoist_speed = hoist_speed  # units/min
        self.crane_state = sim.State("crane_state", value=CraneState.IDLE.value, env=env)
        self.current_heat = None
        self.current_ladle = None
        self.source = None
        self.destination = None
        
        # Initialize position with error handling
        try:
            self.position = spatial_manager.get_crane_home_position(bay) if spatial_manager else {"x": 0, "y": 0}
        except (AttributeError, TypeError) as e:
            logger.error(f"Error getting home position: {e}", exc_info=True)
            self.position = {"x": 0, "y": 0}
            
        self.z_position = 0  # Crane height
        self.spatial_manager = spatial_manager
        self.task_queue = []
        self.busy_time = 0
        self.distance_cache = {}
        self.state_lock = Lock()  # Add lock for thread-safe state changes
        self.last_state_change = 0  # Track time of last state change for deadlock detection
        
        # Enhanced metrics for monitoring
        self.task_count = 0
        self.error_count = 0
        self.operation_times = {
            "moving": [],
            "lifting": [],
            "lowering": []
        }
        
        self.activate(process="process")  # Explicitly activate the process method
        logger.info(f"Crane {self.name()} initialized in bay {bay}", extra={
            "component": "crane",
            "crane_id": crane_id,
            "bay": bay,
            "position": self.position
        })

    def process(self):
        """Main process loop for the crane's operation."""
        while True:
            try:
                current_time = self.env.now()
                current_state = self.crane_state.value
                
                # Deadlock detection
                if current_state != CraneState.IDLE.value and current_time - self.last_state_change > self.DEADLOCK_TIMEOUT:
                    logger.warning(f"Potential deadlock detected in {self.name()}: stuck in {current_state} for {current_time - self.last_state_change} minutes", 
                                  extra={"component": "crane", "crane_id": self.unit_id, "state": current_state})
                
                if current_state == CraneState.IDLE.value and self.task_queue:
                    try:
                        _, source, destination = heappop(self.task_queue)
                        self.assign_task(source, destination)
                    except (IndexError, ValueError) as e:
                        logger.error(f"Error processing task from queue in {self.name()}: {e}", exc_info=True)
                        yield self.hold(1)
                        
                elif current_state == CraneState.MOVING.value:
                    try:
                        # Validate required fields are not None
                        if self.destination is None:
                            raise ValueError("Destination is None")
                            
                        move_time = self._calculate_movement_time(self.position, self.get_position(self.destination))
                        start_time = current_time
                        
                        logger.info(f"Crane {self.name()} moving to {self.destination}, ETA: {move_time:.1f} min", 
                                   extra={"component": "crane", "destination": self.destination, "eta": move_time})
                        
                        yield self.hold(move_time)
                        self.position = self.get_position(self.destination)
                        
                        # Record metrics
                        self.operation_times["moving"].append(self.env.now() - start_time)
                        
                        # Atomic state transition
                        with self.state_lock:
                            self.crane_state.set(CraneState.LIFTING.value if not self.current_ladle else CraneState.LOWERING.value)
                            self.last_state_change = self.env.now()
                            
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.error(f"Error during crane movement for {self.name()}: {e}", exc_info=True)
                        self._handle_error_state()
                        yield self.hold(1)
                        
                elif current_state == CraneState.LIFTING.value:
                    try:
                        if self.source is None:
                            raise ValueError("Source is None during lifting operation")
                            
                        lift_time = self._calculate_lift_time()
                        start_time = current_time
                        
                        logger.info(f"Crane {self.name()} lifting ladle at {self.source}, time: {lift_time:.1f} min", 
                                   extra={"component": "crane", "source": self.source, "lift_time": lift_time})
                                   
                        yield self.hold(lift_time)
                        
                        # Record metrics
                        self.operation_times["lifting"].append(self.env.now() - start_time)
                        
                        unit = self.find_unit(self.source)
                        if unit is None:
                            raise ValueError(f"Unit not found at {self.source}")
                        
                        if not hasattr(unit, "current_ladle"):
                            raise AttributeError(f"Unit at {self.source} has no current_ladle attribute")
                        
                        if unit.current_ladle is None:
                            logger.warning(f"No ladle found at {self.source} for crane {self.name()}")
                            self.crane_state.set(CraneState.IDLE.value)
                            self.source = None
                            self.destination = None
                            continue
                            
                        self.current_ladle = unit.current_ladle
                        self.current_heat = unit.current_ladle.current_heat
                        unit.current_ladle = None
                        
                        logger.info(f"Crane {self.name()} picked up ladle {self.current_ladle.id} with heat {self.current_heat.id if self.current_heat else 'None'}", 
                                   extra={"component": "crane", "ladle_id": self.current_ladle.id, 
                                          "heat_id": self.current_heat.id if self.current_heat else None})
                        
                        # Atomic state transition
                        with self.state_lock:
                            self.crane_state.set(CraneState.MOVING.value)
                            self.last_state_change = self.env.now()
                            
                    except (AttributeError, ValueError, TypeError) as e:
                        logger.error(f"Error during crane lifting for {self.name()}: {e}", exc_info=True)
                        self._handle_error_state()
                        yield self.hold(1)
                        
                elif current_state == CraneState.LOWERING.value:
                    try:
                        if self.destination is None:
                            raise ValueError("Destination is None during lowering operation")
                            
                        lower_time = self._calculate_lower_time()
                        start_time = current_time
                        
                        logger.info(f"Crane {self.name()} lowering ladle at {self.destination}, time: {lower_time:.1f} min", 
                                   extra={"component": "crane", "destination": self.destination, "lower_time": lower_time})
                                   
                        yield self.hold(lower_time)
                        
                        # Record metrics
                        self.operation_times["lowering"].append(self.env.now() - start_time)
                        
                        unit = self.find_unit(self.destination)
                        if unit is None:
                            raise ValueError(f"Destination unit not found at {self.destination}")
                            
                        try:
                            if not hasattr(unit, "add_ladle"):
                                raise AttributeError(f"Unit at {self.destination} lacks add_ladle method")
                                
                            if self.current_ladle is None:
                                raise ValueError("No ladle to place at destination")
                                
                            success = unit.add_ladle(self.current_ladle)
                            if success:
                                logger.info(f"Crane {self.name()} placed ladle {self.current_ladle.id} at {self.destination}", 
                                          extra={"component": "crane", "ladle_id": self.current_ladle.id, "destination": self.destination})
                            else:
                                logger.error(f"Failed to place ladle {self.current_ladle.id} at {self.destination}", 
                                           extra={"component": "crane", "ladle_id": self.current_ladle.id, "destination": self.destination})
                        except AttributeError as e:
                            logger.error(f"Unit at {self.destination} lacks add_ladle method: {e}", exc_info=True)
                            self.error_count += 1
                        except Exception as e:
                            logger.error(f"Unexpected error during ladle placement: {e}", exc_info=True)
                            self.error_count += 1
                        finally:
                            # Clean up and return to idle state regardless of errors
                            self.current_ladle = None
                            self.current_heat = None
                            self.source = None
                            self.destination = None
                            
                            # Atomic state transition
                            with self.state_lock:
                                self.crane_state.set(CraneState.IDLE.value)
                                self.last_state_change = self.env.now()
                                
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error during crane lowering for {self.name()}: {e}", exc_info=True)
                        self._handle_error_state()
                        yield self.hold(1)
                        
                elif current_state == CraneState.ERROR.value:
                    # Recovery from error state
                    logger.info(f"Crane {self.name()} attempting recovery from error state")
                    self.current_ladle = None
                    self.current_heat = None
                    self.source = None
                    self.destination = None
                    yield self.hold(3)  # Wait before attempting recovery
                    
                    # Atomic state transition
                    with self.state_lock:
                        self.crane_state.set(CraneState.IDLE.value)
                        self.last_state_change = self.env.now()
                        
                else:
                    yield self.hold(1)
                    
                # Track busy time
                if self.crane_state.value != CraneState.IDLE.value:
                    self.busy_time += self.env.now() - current_time
                    
            except Exception as e:
                logger.critical(f"Unhandled exception in {self.name()} process: {e}", exc_info=True)
                self.error_count += 1
                yield self.hold(5)  # Longer hold time after critical errors
                
                # Reset to a safe state
                with self.state_lock:
                    self.crane_state.set(CraneState.IDLE.value)
                    self.last_state_change = self.env.now()

    def _handle_error_state(self):
        """Handle transition to error state with proper logging."""
        self.error_count += 1
        with self.state_lock:
            self.crane_state.set(CraneState.ERROR.value)
            self.last_state_change = self.env.now()
        logger.warning(f"Crane {self.name()} entered error state (total errors: {self.error_count})")

    def assign_task(self, source, destination, priority=0):
        """
        Assign a task to the crane.
        
        Args:
            source: Source location ID
            destination: Destination location ID
            priority: Task priority (higher = more important, default: 0)
            
        Returns:
            float: Estimated completion time or 0 if task queued/rejected
        """
        # Pre-task validation
        if source is None or destination is None:
            logger.error(f"Invalid task assignment to {self.name()}: source or destination is None", 
                        extra={"component": "crane", "source": source, "destination": destination})
            return 0
            
        # Log task details - structured logging
        logger.info(f"Task assignment request to crane {self.name()}", extra={
            "component": "crane",
            "crane_id": self.unit_id,
            "bay": self.bay,
            "source": source,
            "destination": destination,
            "priority": priority,
            "state": self.crane_state.value,
            "queue_size": len(self.task_queue)
        })
        
        # Check crane availability
        with self.state_lock:
            if self.crane_state.value != CraneState.IDLE.value or self.task_queue:
                heappush(self.task_queue, (-priority, source, destination))
                logger.info(f"Crane {self.name()} queued task: {source} -> {destination}, priority: {priority}")
                return 0
            
            # Check if locations are in the crane's bay
            if not self.is_in_bay(source) or not self.is_in_bay(destination):
                logger.error(f"Source {source} or destination {destination} not in bay {self.bay}", 
                            extra={"component": "crane", "source": source, "destination": destination, "bay": self.bay})
                return 0
            
            # Assign the task
            self.source = source
            self.destination = destination
            self.crane_state.set(CraneState.MOVING.value)
            self.last_state_change = self.env.now()
            self.task_count += 1
        
        # Log successful assignment
        logger.info(f"Crane {self.name()} assigned task: {source} -> {destination} (task #{self.task_count})", 
                   extra={"component": "crane", "task_number": self.task_count})
        
        # Calculate and return the estimated completion time
        try:
            est_time = self._calculate_movement_time(self.position, self.get_position(source)) + self.TASK_OVERHEAD
            return est_time
        except Exception as e:
            logger.error(f"Error calculating task time: {e}", exc_info=True)
            return self.TASK_OVERHEAD + 5  # Default fallback

    def is_available(self):
        """
        Check if the crane is available for a new task.
        
        Returns:
            bool: True if the crane is idle and has no pending tasks
        """
        with self.state_lock:
            return self.crane_state.value == CraneState.IDLE.value and not self.task_queue

    def _calculate_movement_time(self, start, end):
        """
        Calculate the time required to move from start to end position.
        
        Args:
            start: Starting position {'x': x, 'y': y}
            end: Ending position {'x': x, 'y': y}
            
        Returns:
            float: Time in minutes
        """
        # Validate inputs
        if not isinstance(start, dict) or not isinstance(end, dict):
            logger.error(f"Invalid position format: start={start}, end={end}")
            return 5.0  # Default fallback
            
        # Type check for position values
        try:
            start_x = float(start.get("x", 0))
            start_y = float(start.get("y", 0))
            end_x = float(end.get("x", 0))
            end_y = float(end.get("y", 0))
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid position values: {e}", exc_info=True)
            return 5.0  # Default fallback
        
        key = (start_x, start_y, end_x, end_y)
        if key not in self.distance_cache:
            distance = ((start_x - end_x) ** 2 + (start_y - end_y) ** 2) ** 0.5
            t_accel = self.speed / self.accel
            d_accel = 0.5 * self.accel * t_accel ** 2
            if distance < 2 * d_accel:
                self.distance_cache[key] = (2 * distance / self.accel) ** 0.5
            else:
                self.distance_cache[key] = 2 * t_accel + (distance - 2 * d_accel) / self.speed
                
            # Also cache the reverse path
            reverse_key = (end_x, end_y, start_x, start_y)
            self.distance_cache[reverse_key] = self.distance_cache[key]
        
        return self.distance_cache[key]

    def _calculate_lift_time(self):
        """Calculate the time required for a lifting operation."""
        try:
            return abs(self.z_position - 10) / self.hoist_speed + self.LIFT_TIME  # Base lift time + hoist
        except (TypeError, ZeroDivisionError) as e:
            logger.error(f"Error calculating lift time: {e}", exc_info=True)
            return self.LIFT_TIME  # Fallback to base time

    def _calculate_lower_time(self):
        """Calculate the time required for a lowering operation."""
        try:
            return abs(self.z_position - 10) / self.hoist_speed + self.LOWER_TIME  # Base lower time + hoist
        except (TypeError, ZeroDivisionError) as e:
            logger.error(f"Error calculating lower time: {e}", exc_info=True)
            return self.LOWER_TIME  # Fallback to base time

    def get_position(self, location):
        """
        Get the position of a location.
        
        Args:
            location: Location identifier
            
        Returns:
            dict: Position {'x': x, 'y': y}
            
        Raises:
            ValueError: If spatial_manager is not available
        """
        if not self.spatial_manager:
            logger.error(f"Crane {self.name()} lacks spatial_manager; cannot determine position for {location}", 
                       extra={"component": "crane", "location": location})
            raise ValueError("SpatialManager required")
            
        try:
            return self.spatial_manager.get_unit_position(location)
        except (AttributeError, KeyError) as e:
            logger.error(f"Error getting position for {location}: {e}", exc_info=True)
            return {"x": 0, "y": 0}  # Default fallback

    def find_unit(self, location):
        """
        Find the unit at the specified location.
        
        Args:
            location: Location identifier
            
        Returns:
            Object or None: The unit at the location, or None if not found
        """
        if not self.spatial_manager:
            logger.error(f"Crane {self.name()} lacks spatial_manager; cannot find unit at {location}", 
                       extra={"component": "crane", "location": location})
            return None
            
        try:
            return self.spatial_manager.get_unit_at_location(location)
        except (AttributeError, KeyError) as e:
            logger.error(f"Error finding unit at {location}: {e}", exc_info=True)
            return None

    def is_in_bay(self, location):
        """
        Check if a location is in the crane's bay.
        
        Args:
            location: Location identifier
            
        Returns:
            bool: True if in bay, False otherwise
        """
        if not self.spatial_manager:
            logger.warning(f"Crane {self.name()} lacks spatial_manager; assuming {location} in bay", 
                         extra={"component": "crane", "location": location, "bay": self.bay})
            return True
            
        try:
            return self.spatial_manager.is_unit_in_bay(location, self.bay)
        except Exception as e:
            logger.error(f"Error checking if {location} is in bay {self.bay}: {e}", exc_info=True)
            return False  # Fail safe: don't assume in bay on error

    def get_utilization(self):
        """
        Return crane utilization as a percentage.
        
        Returns:
            float: Utilization percentage (0-100)
        """
        total_time = self.env.now()
        return (self.busy_time / total_time * 100) if total_time > 0 else 0
        
    def get_metrics(self):
        """
        Get detailed operational metrics for the crane.
        
        Returns:
            dict: Metrics dictionary
        """
        avg_times = {}
        for op_type, times in self.operation_times.items():
            avg_times[op_type] = sum(times) / len(times) if times else 0
            
        return {
            "utilization": self.get_utilization(),
            "task_count": self.task_count,
            "error_count": self.error_count,
            "average_times": avg_times,
            "queue_length": len(self.task_queue),
            "current_state": self.crane_state.value
        }