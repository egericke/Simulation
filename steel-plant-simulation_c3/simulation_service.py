import logging
from process_control.scenario_manager import ScenarioManager
from spatial.spatial_manager import SpatialManager



logger = logging.getLogger(__name__)

class SimulationService:
    """
    Central service class that provides access to all simulation components.
    Acts as a service locator and coordinator between components.
    """
    def __init__(self, config, env):
        """
        Initialize the simulation service.

        Args:
            config: Configuration dictionary
            env: Salabim environment
        """
        self.config = config  # Store the full config
        self.env = env

        # Initialize managers with the config
        self.spatial_manager = SpatialManager(self.config)
        self.scenario_manager = ScenarioManager(self.config)

        # These will be set by the main script later
        self.production_manager = None
        self.layer_manager = None
        self.cad_background = None
        self.bottleneck_analyzer = None

        logger.info("SimulationService initialized successfully.")
    
    def reset_simulation(self):
        """
        Reset the simulation to initial state.
        Returns a new environment and initialized components.
        """
        logger.info("Resetting simulation...")
        
        # Create new environment (existing one can't be reset)
        import salabim as sim
        new_env = sim.Environment(trace=False)
        new_env.speed(self.config.get("sim_speed", 1.0))
        
        if hasattr(self.env, "animate") and self.env._animate:
            new_env.animate(True)
            new_env.background_color("black")
            new_env.animation_parameters(
                width=1200, 
                height=800,
                title="Steel Plant Simulation",
                speed=self.config.get("sim_speed", 1.0),
                show_fps=True
            )
        
        # Create a new service instance with the new environment
        new_service = SimulationService(self.config, new_env)
        
        # Recreate scenario manager
        new_service.scenario_manager = ScenarioManager(self.config)
        
        # The main script will need to recreate ProductionManager
        # and other components and assign them to the new service
        
        return new_env, new_service
    
    def update_config(self, new_config):
        """
        Update the configuration.
        
        Args:
            new_config: New configuration dictionary
        """
        self.config.update(new_config)
        logger.info("Configuration updated")
        
        # Update scenario manager
        self.scenario_manager.config = self.config
        
        # Production manager config updates would need to be handled separately
        # as they might require recreating units
    
    def save_config(self, file_path):
        """
        Save the current configuration to a file.
        
        Args:
            file_path: Path to save the configuration file
        """
        import json
        try:
            with open(file_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Configuration saved to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def load_config(self, file_path):
        """
        Load configuration from a file.
        
        Args:
            file_path: Path to the configuration file
        
        Returns:
            bool: True if loading was successful
        """
        import json
        try:
            with open(file_path, 'r') as f:
                new_config = json.load(f)
            self.config = new_config
            logger.info(f"Configuration loaded from {file_path}")
            
            # Update scenario manager
            self.scenario_manager.config = self.config
            
            return True
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return False
    
    def pause(self):
        """Pause the simulation."""
        if hasattr(self.env, "paused"):
            self.env.paused = True
            logger.info("Simulation paused")
    
    def resume(self):
        """Resume the simulation."""
        if hasattr(self.env, "paused"):
            self.env.paused = False
            logger.info("Simulation resumed")
    
    def toggle_pause(self):
        """Toggle the pause state of the simulation."""
        if hasattr(self.env, "paused"):
            self.env.paused = not self.env.paused
            logger.info(f"Simulation {'paused' if self.env.paused else 'resumed'}")
    
    def get_stats(self):
        """
        Get current simulation statistics.
        
        Returns:
            dict: Dictionary of statistics
        """
        stats = {
            "simulation_time": self.env.now() if self.env else 0,
            "heats_processed": 0,
            "heats_completed": 0,
            "avg_cycle_time": "N/A",
            "takt_time": self.config.get("takt_time", 60),
            "utilization": 0,
            "ladle_distance": 0,
            "units": {}
        }
        
        # Collect stats from production manager if available
        if self.production_manager:
            pm = self.production_manager
            stats["heats_processed"] = pm.heats_processed
            stats["heats_completed"] = pm.completed_heats
            
            if pm.completed_heats > 0:
                stats["avg_cycle_time"] = pm.total_cycle_time / pm.completed_heats
                if stats["takt_time"] > 0:
                    stats["utilization"] = min(stats["avg_cycle_time"] / stats["takt_time"], 1.0)
            
            stats["ladle_distance"] = sum(lc.total_distance_traveled for lc in pm.ladle_cars)
            
            # Collect unit-specific stats
            for bay_name, bay_units in pm.units.items():
                for unit_type, units in bay_units.items():
                    if unit_type == "EAF":
                        unit = units  # EAF is a single unit
                        stats["units"][unit.name] = {
                            "heats_processed": getattr(unit, "heats_processed", 0),
                            "utilization": 0       # Would need to track this in the unit
                        }
                    else:
                        # LMF, Degasser, Caster are lists
                        for unit in units:
                            stats["units"][unit.name] = {
                                "heats_processed": getattr(unit, "heats_processed", 0),
                                "utilization": 0       # Would need to track this in the unit
                            }
        
        return stats