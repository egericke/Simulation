import salabim as sim
import logging
from enum import Enum
from heapq import heappush, heappop

logger = logging.getLogger(__name__)

class CraneState(Enum):
    IDLE = "idle"
    MOVING = "moving"
    LIFTING = "lifting"
    LOWERING = "lowering"

class Crane(sim.Component):
    LIFT_TIME = 3  # minutes
    LOWER_TIME = 3  # minutes
    TASK_OVERHEAD = 6  # lift + lower time in minutes

    def __init__(self, env, crane_id, bay, speed=100, accel=10, hoist_speed=20, spatial_manager=None, name=None, **kwargs):
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
        self.position = spatial_manager.get_crane_home_position(bay) if spatial_manager else {"x": 0, "y": 0}
        self.z_position = 0  # Crane height
        self.spatial_manager = spatial_manager
        self.task_queue = []
        self.busy_time = 0
        self.distance_cache = {}
        self.activate(process="process")  # Explicitly activate the process method
        logger.info(f"Crane {self.name()} initialized in bay {bay}")

    def process(self):
        while True:
            current_time = self.env.now()
            if self.crane_state.value == CraneState.IDLE.value and self.task_queue:
                _, source, destination = heappop(self.task_queue)
                self.assign_task(source, destination)
            elif self.crane_state.value == CraneState.MOVING.value:
                move_time = self._calculate_movement_time(self.position, self.get_position(self.destination))
                logger.info(f"Crane {self.name()} moving to {self.destination}, ETA: {move_time:.1f} min")
                yield self.hold(move_time)
                self.position = self.get_position(self.destination)
                self.crane_state.set(CraneState.LIFTING.value if not self.current_ladle else CraneState.LOWERING.value)
            elif self.crane_state.value == CraneState.LIFTING.value:
                lift_time = self._calculate_lift_time()
                logger.info(f"Crane {self.name()} lifting ladle at {self.source}, time: {lift_time:.1f} min")
                yield self.hold(lift_time)
                unit = self.find_unit(self.source)
                if unit and hasattr(unit, "current_ladle") and unit.current_ladle:
                    self.current_ladle = unit.current_ladle
                    self.current_heat = unit.current_ladle.current_heat
                    unit.current_ladle = None
                    logger.info(f"Crane {self.name()} picked up ladle {self.current_ladle.id} with heat {self.current_heat.id}")
                else:
                    logger.warning(f"No ladle found at {self.source}")
                self.crane_state.set(CraneState.MOVING.value)
            elif self.crane_state.value == CraneState.LOWERING.value:
                lower_time = self._calculate_lower_time()
                logger.info(f"Crane {self.name()} lowering ladle at {self.destination}, time: {lower_time:.1f} min")
                yield self.hold(lower_time)
                unit = self.find_unit(self.destination)
                if unit:
                    try:
                        success = unit.add_ladle(self.current_ladle)
                        if success:
                            logger.info(f"Crane {self.name()} placed ladle {self.current_ladle.id} at {self.destination}")
                        else:
                            logger.error(f"Failed to place ladle {self.current_ladle.id} at {self.destination}")
                    except AttributeError:
                        logger.error(f"Unit at {self.destination} lacks add_ladle method")
                self.current_ladle = None
                self.current_heat = None
                self.source = None
                self.destination = None
                self.crane_state.set(CraneState.IDLE.value)
            else:
                yield self.hold(1)
            if self.crane_state.value != CraneState.IDLE.value:
                self.busy_time += self.env.now() - current_time

    def assign_task(self, source, destination, priority=0):
        if self.crane_state.value != CraneState.IDLE.value or self.task_queue:
            heappush(self.task_queue, (-priority, source, destination))
            logger.info(f"Crane {self.name()} queued task: {source} -> {destination}, priority: {priority}")
            return 0
        if not self.is_in_bay(source) or not self.is_in_bay(destination):
            logger.error(f"Source {source} or destination {destination} not in bay {self.bay}")
            return 0
        self.source = source
        self.destination = destination
        self.crane_state.set(CraneState.MOVING.value)
        logger.info(f"Crane {self.name()} assigned task: {source} -> {destination}")
        return self._calculate_movement_time(self.position, self.get_position(source)) + self.TASK_OVERHEAD

    def is_available(self):
        return self.crane_state.value == CraneState.IDLE.value and not self.task_queue

    def _calculate_movement_time(self, start, end):
        key = (start["x"], start["y"], end["x"], end["y"])
        if key not in self.distance_cache:
            distance = ((start["x"] - end["x"]) ** 2 + (start["y"] - end["y"]) ** 2) ** 0.5
            t_accel = self.speed / self.accel
            d_accel = 0.5 * self.accel * t_accel ** 2
            if distance < 2 * d_accel:
                self.distance_cache[key] = (2 * distance / self.accel) ** 0.5
            else:
                self.distance_cache[key] = 2 * t_accel + (distance - 2 * d_accel) / self.speed
        return self.distance_cache[key]

    def _calculate_lift_time(self):
        return abs(self.z_position - 10) / self.hoist_speed + self.LIFT_TIME  # Base lift time + hoist

    def _calculate_lower_time(self):
        return abs(self.z_position - 10) / self.hoist_speed + self.LOWER_TIME  # Base lower time + hoist

    def get_position(self, location):
        if not self.spatial_manager:
            logger.error(f"Crane {self.name()} lacks spatial_manager; cannot determine position for {location}")
            raise ValueError("SpatialManager required")
        return self.spatial_manager.get_unit_position(location)

    def find_unit(self, location):
        if not self.spatial_manager:
            logger.error(f"Crane {self.name()} lacks spatial_manager; cannot find unit at {location}")
            return None
        return self.spatial_manager.get_unit_at_location(location)

    def is_in_bay(self, location):
        if not self.spatial_manager:
            logger.warning(f"Crane {self.name()} lacks spatial_manager; assuming {location} in bay")
            return True
        return self.spatial_manager.is_unit_in_bay(location, self.bay)

    def get_utilization(self):
        """Return crane utilization as a percentage."""
        total_time = self.env.now()
        return (self.busy_time / total_time * 100) if total_time > 0 else 0