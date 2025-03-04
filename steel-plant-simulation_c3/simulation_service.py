import logging
import json
import os
import datetime
from process_control.scenario_manager import ScenarioManager
from spatial.spatial_manager import SpatialManager
from equipment.transport_manager import TransportManager
from equipment.ladle_manager import LadleManager

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
        # Validate required configuration parameters
        self._validate_config(config)
        
        self.config = config  # Store the full config
        self.env = env
        self.config_version = 1  # Track configuration version

        # Initialize managers with the config
        self.spatial_manager = SpatialManager(self.config)
        self.scenario_manager = ScenarioManager(self.config)
        self.transport_manager = None
        self.ladle_manager = None

        # Component references that will be set by the main script
        self.production_manager = None
        self.layer_manager = None
        self.cad_background = None
        self.bottleneck_analyzer = None
        
        # Save configuration file path for persistence
        self.config_file_path = None

        logger.info("SimulationService initialized successfully.")
    
    def _validate_config(self, config):
        """
        Validate critical configuration parameters.
        
        Args:
            config: Configuration dictionary to validate
            
        Raises:
            ValueError: If required configuration is missing
        """
        # Check for missing required sections
        required_sections = ["n_bays", "units"]
        missing_sections = [section for section in required_sections if section not in config]
        
        if missing_sections:
            error_msg = f"Missing required configuration sections: {', '.join(missing_sections)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Check for required unit types
        required_units = ["EAF", "LMF", "Degasser", "Caster"]
        units = config.get("units", {})
        missing_units = [unit for unit in required_units if unit not in units]
        
        if missing_units:
            logger.warning(f"Configuration missing some unit types: {', '.join(missing_units)}")
    
    def initialize_transport_systems(self):
        """
        Initialize the transport-related systems.
        Must be called after the environment is set up.
        """
        if not self.env:
            logger.error("Cannot initialize transport systems: environment not available")
            return False
            
        try:
            # Create TransportManager instance within the environment
            self.transport_manager = TransportManager(
                self.env, self.config, self.spatial_manager
            )
            self.env.transport_manager = self.transport_manager
            
            # Create LadleManager instance
            self.ladle_manager = LadleManager(
                self.env, self.config, self.spatial_manager
            )
            self.env.ladle_manager = self.ladle_manager
            
            logger.info("Transport systems initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize transport systems: {e}", exc_info=True)
            return False
    
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
        
        # Preserve animation settings
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
        
        # Initialize transport systems
        new_service.initialize_transport_systems()
        
        # Preserve config file path
        new_service.config_file_path = self.config_file_path
        
        # Recreate key managers
        new_service.scenario_manager = ScenarioManager(self.config)
        
        logger.info("Simulation reset complete")
        return new_env, new_service
    
    def update_config(self, new_config, section=None):
        """
        Update the configuration, optionally targeting a specific section.
        
        Args:
            new_config: New configuration dictionary
            section: Optional section name to update selectively
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            if section:
                # Update just one section
                if section not in self.config:
                    self.config[section] = {}
                self._update_nested_dict(self.config[section], new_config)
                logger.info(f"Configuration section '{section}' updated")
            else:
                # Update entire config
                self._update_nested_dict(self.config, new_config)
                logger.info("Full configuration updated")
            
            # Increment version
            self.config_version += 1
            
            # Update scenario manager
            self.scenario_manager.config = self.config
            
            # Update spatial manager
            if hasattr(self.spatial_manager, 'update_config'):
                self.spatial_manager.update_config(self.config)
            
            # Update transport manager if available
            if self.transport_manager and hasattr(self.transport_manager, 'update_config'):
                self.transport_manager.update_config(self.config)
                
            return True
        except Exception as e:
            logger.error(f"Failed to update configuration: {e}", exc_info=True)
            return False
    
    def _update_nested_dict(self, target, source):
        """
        Update nested dictionary structures recursively.
        
        Args:
            target: Target dictionary to update
            source: Source dictionary with updates
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                # Recursive update for nested dicts
                self._update_nested_dict(target[key], value)
            else:
                # Direct update for non-dict values or new keys
                target[key] = value
    
    def save_config(self, file_path=None):
        """
        Save the current configuration to a file.
        
        Args:
            file_path: Path to save the configuration file, uses last path if None
            
        Returns:
            bool: True if saving was successful
        """
        if file_path:
            self.config_file_path = file_path
        elif not self.config_file_path:
            # Generate a timestamped default filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.config_file_path = f"config_{timestamp}.json"
        
        try:
            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(self.config_file_path)), exist_ok=True)
            
            # Add metadata
            config_with_meta = self.config.copy()
            config_with_meta["_metadata"] = {
                "version": self.config_version,
                "save_time": datetime.datetime.now().isoformat(),
                "simulator_version": "1.0" 
            }
            
            with open(self.config_file_path, 'w') as f:
                json.dump(config_with_meta, f, indent=2)
            logger.info(f"Configuration saved to {self.config_file_path}")
            
            # Also save a backup with the original filename plus timestamp
            backup_path = f"{os.path.splitext(self.config_file_path)[0]}.backup.json"
            with open(backup_path, 'w') as f:
                json.dump(config_with_meta, f, indent=2)
            logger.info(f"Configuration backup saved to {backup_path}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}", exc_info=True)
            return False
    
    def load_config(self, file_path):
        """
        Load configuration from a file.
        
        Args:
            file_path: Path to the configuration file
        
        Returns:
            bool: True if loading was successful
        """
        if not os.path.isfile(file_path):
            logger.error(f"Configuration file does not exist: {file_path}")
            return False
            
        try:
            with open(file_path, 'r') as f:
                new_config = json.load(f)
            
            # Remove metadata if present
            if "_metadata" in new_config:
                loaded_version = new_config["_metadata"].get("version", 0)
                save_time = new_config["_metadata"].get("save_time", "unknown")
                logger.info(f"Loading configuration version {loaded_version}, saved at {save_time}")
                new_config.pop("_metadata")
            
            # Validate configuration
            try:
                self._validate_config(new_config)
            except ValueError as e:
                logger.error(f"Invalid configuration file: {e}")
                return False
            
            # Store the new configuration
            self.config = new_config
            self.config_file_path = file_path
            
            # Update dependent components
            self.scenario_manager.config = self.config
            
            # Update spatial manager if already initialized
            if hasattr(self.spatial_manager, 'update_config'):
                self.spatial_manager.update_config(self.config)
            else:
                self.spatial_manager = SpatialManager(self.config)
            
            logger.info(f"Configuration loaded from {file_path}")
            return True
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in configuration file: {file_path}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}", exc_info=True)
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
            "units": {},
            "config_version": self.config_version
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
                            "utilization": unit.get_utilization() if hasattr(unit, "get_utilization") else 0
                        }
                    else:
                        # LMF, Degasser, Caster are lists
                        for unit in units:
                            stats["units"][unit.name] = {
                                "heats_processed": getattr(unit, "heats_processed", 0),
                                "utilization": unit.get_utilization() if hasattr(unit, "get_utilization") else 0
                            }
        
        # Collect transport system stats if available
        if self.transport_manager:
            stats["transport"] = {
                "pending_requests": len(self.transport_manager.pending_requests),
                "active_ladle_cars": sum(1 for car in self.transport_manager.ladle_cars if car.get_status_string() != "idle"),
                "total_ladle_cars": len(self.transport_manager.ladle_cars)
            }
            
            # Collect crane utilization stats
            crane_stats = {}
            for bay, cranes in self.transport_manager.cranes.items():
                crane_stats[bay] = [{"id": crane.unit_id, "utilization": crane.get_utilization()} for crane in cranes]
            stats["cranes"] = crane_stats
        
        return stats
    
    def export_layout(self, file_path):
        """
        Export the current layout (bays and equipment positions) to a file.
        
        Args:
            file_path: Path to save the layout file
            
        Returns:
            bool: True if export was successful
        """
        try:
            layout = {
                "bays": self.config.get("bays", {}),
                "equipment_positions": self.config.get("equipment_positions", {})
            }
            
            with open(file_path, 'w') as f:
                json.dump(layout, f, indent=2)
                
            logger.info(f"Layout exported to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export layout: {e}", exc_info=True)
            return False
    
    def import_layout(self, file_path):
        """
        Import a layout from a file and update the configuration.
        
        Args:
            file_path: Path to the layout file
            
        Returns:
            bool: True if import was successful
        """
        try:
            with open(file_path, 'r') as f:
                layout = json.load(f)
            
            # Validate the layout file
            if not isinstance(layout, dict) or "bays" not in layout:
                logger.error(f"Invalid layout file: missing 'bays' section")
                return False
            
            # Update configuration
            self.config["bays"] = layout.get("bays", {})
            self.config["equipment_positions"] = layout.get("equipment_positions", {})
            
            # Update spatial manager
            if hasattr(self.spatial_manager, 'update_config'):
                self.spatial_manager.update_config(self.config)
            
            logger.info(f"Layout imported from {file_path}")
            return True
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in layout file: {file_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to import layout: {e}", exc_info=True)
            return False