import logging
from heapq import heappush, heappop
from equipment.ladle_car import BaseLadleCar  # Import the refactored base class
from equipment.crane import Crane

logger = logging.getLogger(__name__)

class TransportManager:
    def __init__(self, env, config, spatial_manager):
        self.env = env
        self.config = config or {}
        self.spatial_manager = spatial_manager
        self._ladle_cars = []  # Private storage for ladle cars
        self.cranes = {}
        self.pending_requests = []
        self._setup_transport_equipment()
        logger.info("TransportManager initialized with %d ladle cars and %d bays", 
                    len(self._ladle_cars), len(self.cranes))

    @property
    def ladle_cars(self):
        """
        Return a copy of the ladle cars list to prevent direct modification.
        """
        return self._ladle_cars.copy()

    def create_ladle_car(self, car_id, car_type, home_bay):
        """
        Factory method to create ladle cars with consistent configuration.
        
        Args:
            car_id: Unique identifier for the car
            car_type: Type of car ("tapping", "treatment", "rh")
            home_bay: Bay where the car is initially located
            
        Returns:
            BaseLadleCar: Newly created ladle car
        """
        return BaseLadleCar(
            env=self.env, 
            car_id=car_id, 
            car_type=car_type, 
            home_bay=home_bay,
            speed=self.config.get("ladle_car_speed", 150), 
            spatial_manager=self.spatial_manager,
            on_idle_callback=self._process_pending_requests
        )

    def _setup_transport_equipment(self):
        """
        Initialize ladle cars and cranes based on configuration.
        """
        # Configuration-driven approach
        car_types = self.config.get("ladle_car_types", ["tapping", "treatment", "rh"])
        n_per_type = self.config.get("n_ladle_cars_per_type", 1)
        n_bays = self.config.get("n_bays", 2)
        
        # Fallback to old approach if specific configuration is missing
        if not self.config.get("ladle_car_types"):
            n_ladle_cars = self.config.get("n_ladle_cars", 3)
            car_id = 1
            for i in range(n_ladle_cars):
                home_bay = f"bay{(i % n_bays) + 1}"
                car_type = "tapping" if i % 3 == 0 else "treatment" if i % 3 == 1 else "rh"
                car = self.create_ladle_car(car_id, car_type, home_bay)
                self._ladle_cars.append(car)
                car_id += 1
        else:
            # Use configuration-driven approach
            car_id = 1
            for car_type in car_types:
                for _ in range(n_per_type):
                    home_bay = f"bay{((car_id - 1) % n_bays) + 1}"
                    car = self.create_ladle_car(car_id, car_type, home_bay)
                    self._ladle_cars.append(car)
                    car_id += 1
        
        # Initialize cranes per bay
        n_cranes_per_bay = self.config.get("n_cranes_per_bay", 2)
        crane_speed = self.config.get("crane_speed", 100)
        
        for bay_id in range(1, n_bays + 1):
            bay_name = f"bay{bay_id}"
            self.cranes[bay_name] = []
            for j in range(n_cranes_per_bay):
                crane = Crane(env=self.env, crane_id=j+1, bay=bay_name, speed=crane_speed, 
                              spatial_manager=self.spatial_manager)
                crane.activate(process="process")
                self.cranes[bay_name].append(crane)

    def request_transport(self, heat, from_unit, to_unit, priority=0):
        """
        Request transport for a heat between units.
        
        Args:
            heat: Heat to transport
            from_unit: Source unit
            to_unit: Destination unit
            priority: Request priority (higher = more important)
            
        Returns:
            bool: True if request accepted
        """
        from_bay = getattr(from_unit, "bay", "unknown")
        to_bay = getattr(to_unit, "bay", "unknown")
        
        # Determine appropriate car type based on source and destination
        car_type = "tapping" if from_bay != to_bay else "treatment"
        if hasattr(to_unit, "name") and callable(to_unit.name) and "caster" in to_unit.name().lower():
            car_type = "treatment"  # Intra-bay to caster

        request = {
            "heat": heat,
            "from_unit": from_unit,
            "to_unit": to_unit,
            "from_bay": from_bay,
            "to_bay": to_bay,
            "car_type": car_type,
            "time_requested": self.env.now(),
            "status": "pending",
            "assigned_car": None
        }
        heappush(self.pending_requests, (priority, self.env.now(), request))
        logger.info("Transport request queued for heat %s from %s to %s with car type %s", 
                    heat.id, from_unit.name(), to_unit.name(), car_type)
        self._process_pending_requests()
        return True

    def _process_pending_requests(self):
        """
        Process pending transport requests, assigning available cars.
        """
        processed_count = 0
        while self.pending_requests and processed_count < 10:  # Limit iterations for performance
            priority, timestamp, request = heappop(self.pending_requests)
            if request["status"] != "pending":
                continue

            car_type = request["car_type"]
            available_cars = [car for car in self._ladle_cars 
                             if car.car_type == car_type and car.is_available()]
            
            if not available_cars:
                logger.info("No available %s cars; requeuing request for heat %s", 
                           car_type, request["heat"].id)
                heappush(self.pending_requests, (priority, timestamp, request))
                break

            # Find closest car to minimize travel time
            closest_car = min(available_cars, key=lambda car: self._calculate_distance(
                car.current_bay, request["from_bay"]))
            
            request["status"] = "assigned"
            request["assigned_car"] = closest_car
            destination = {"bay": request["to_bay"], "unit": request["to_unit"]}
            success = closest_car.assign_heat(request["heat"], destination)

            if success:
                logger.info("Assigned %s car %d to heat %s from %s to %s", 
                           car_type, closest_car.car_id, request["heat"].id, 
                           request["from_bay"], request["to_bay"])
            else:
                logger.warning("Failed to assign %s car %d to heat %s; requeuing", 
                              car_type, closest_car.car_id, request["heat"].id)
                request["status"] = "pending"
                request["assigned_car"] = None
                heappush(self.pending_requests, (priority, timestamp, request))
                break
                
            processed_count += 1

    def _calculate_distance(self, from_bay, to_bay):
        """
        Calculate distance between bays for car assignment decisions.
        
        Args:
            from_bay: Source bay
            to_bay: Destination bay
            
        Returns:
            float: Distance or time estimate
        """
        path = self.spatial_manager.get_path_between_bays(from_bay, to_bay)
        if path and isinstance(path, list) and len(path) > 0:
            return path[0].get("distance", 100)  # Adjusted for list of segments
            
        # Fallback to direct distance calculation
        from_pos = self.spatial_manager.get_bay_position(from_bay)
        to_pos = self.spatial_manager.get_bay_position(to_bay)
        if from_pos and to_pos:
            dx = to_pos["x"] - from_pos["x"]
            dy = to_pos["y"] - from_pos["y"]
            return (dx**2 + dy**2)**0.5
            
        logger.warning("No path or positions for bays %s to %s; using default distance 100", 
                      from_bay, to_bay)
        return 100

    def check_transport_status(self, heat):
        """
        Check status of transport for a specific heat.
        
        Args:
            heat: Heat object to check
            
        Returns:
            dict: Status information
        """
        # Check pending requests
        for _, _, request in self.pending_requests:
            if request["heat"].id == heat.id:
                return {
                    "status": request["status"],
                    "time_requested": request["time_requested"],
                    "waiting_time": self.env.now() - request["time_requested"],
                    "assigned_car": request["assigned_car"].car_id if request["assigned_car"] else None
                }
        
        # Check active transports
        for car in self._ladle_cars:
            if car.current_heat and car.current_heat.id == heat.id:
                # Check car status type safety
                car_status = car.car_status.value
                if not isinstance(car_status, str):
                    logger.warning(f"Invalid car status type: {type(car_status)}")
                    car_status = "unknown"
                
                return {
                    "status": car_status,
                    "car_id": car.car_id,
                    "current_bay": car.current_bay,
                    "destination_bay": car.destination.get("bay") if car.destination else None,
                    "progress": f"{car.current_path_segment}/{len(car.path)}" if car.path else "N/A"
                }
                
        return {"status": "not_in_transport"}

    def get_status(self):
        """
        Get overall status of transport system.
        
        Returns:
            dict: System status information
        """
        return {
            "ladle_cars": [
                {
                    "car_id": car.car_id,
                    "car_type": car.car_type,
                    "status": car.car_status.value if isinstance(car.car_status.value, str) else "unknown",
                    "current_bay": car.current_bay,
                    "destination": car.destination,
                    "current_heat": car.current_heat.id if car.current_heat else None
                }
                for car in self._ladle_cars
            ],
            "cranes": {
                bay: [{"crane_id": crane.crane_id, "status": crane.crane_state.value} 
                     for crane in cranes]
                for bay, cranes in self.cranes.items()
            },
            "pending_requests": len(self.pending_requests)
        }

    def request_crane(self, bay, task):
        """
        Request a crane for a specific task in a bay.
        
        Args:
            bay: Bay where crane is needed
            task: Task description
            
        Returns:
            Crane: Available crane or None
        """
        if bay not in self.cranes:
            logger.error("No cranes registered in bay %s", bay)
            return None
            
        available_cranes = [crane for crane in self.cranes[bay] if crane.is_available()]
        if not available_cranes:
            logger.info("No available cranes in bay %s", bay)
            return None
            
        crane = available_cranes[0]
        logger.debug("Crane %d in bay %s allocated for task", crane.crane_id, bay)
        return crane