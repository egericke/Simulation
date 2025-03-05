import salabim as sim
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config(config_path="config.json"):
    """Load configuration from file."""
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}

def visualize_ladle_car_paths(env, config):
    """Create animation objects for ladle car paths."""
    if "ladle_car_paths" in config:
        for bay_name, paths in config.get("ladle_car_paths", {}).items():
            logger.info(f"Visualizing {len(paths)} paths for bay {bay_name}")
            for path in paths:
                waypoints = path.get("waypoints", [])
                logger.info(f"Path has {len(waypoints)} waypoints")
                if len(waypoints) < 2:
                    continue
                
                for i in range(len(waypoints) - 1):
                    try:
                        sim.AnimateLine(
                            x0=waypoints[i]["x"], y0=waypoints[i]["y"],
                            x1=waypoints[i + 1]["x"], y1=waypoints[i + 1]["y"],
                            linecolor="green", linewidth=2, env=env
                        )
                    except Exception as e:
                        logger.error(f"Error creating line for path: {e}")

def simulate_ladle_car_movement(env, config):
    """Simulate a ladle car moving along a path."""
    from equipment.ladle_car import BaseLadleCar
    from equipment.transport_manager import TransportManager
    from spatial.spatial_manager import SpatialManager
    
    # Initialize spatial manager
    spatial_manager = SpatialManager(config)
    
    # Initialize transport manager
    transport_manager = TransportManager(env, config, spatial_manager)
    
    # Create a ladle car and ladle
    class DummyLadle:
        def __init__(self, ladle_id):
            self.id = ladle_id
            self.current_heat = None
    
    # Create dummy ladle
    ladle = DummyLadle("test_ladle_1")
    
    # Find first available bay with paths
    target_bay = None
    target_path_id = None
    
    if "ladle_car_paths" in config:
        for bay_name, paths in config.get("ladle_car_paths", {}).items():
            if paths:
                target_bay = bay_name
                target_path_id = paths[0].get("path_id", 1)
                break
    
    if target_bay and target_path_id:
        logger.info(f"Found path to test: Bay={target_bay}, Path ID={target_path_id}")
        
        # Use the transport manager to move the ladle along the path
        success = transport_manager.move_ladle_along_path(target_bay, target_path_id, ladle)
        if success:
            logger.info("Successfully assigned path to ladle car")
        else:
            logger.error("Failed to assign path to ladle car")
    else:
        logger.warning("No paths found in config for testing")

def main():
    """Run the test."""
    # Load configuration
    config = load_config()
    
    # Create the simulation environment
    env = sim.Environment()
    env.animate(True)
    
    # Set up animation parameters
    env.animation_parameters(width=1200, height=800, title="Ladle Car Path Test")
    
    # Visualize paths from configuration
    visualize_ladle_car_paths(env, config)
    
    # Simulate movement
    try:
        simulate_ladle_car_movement(env, config)
    except Exception as e:
        logger.error(f"Error simulating movement: {e}")
    
    # Run the simulation
    logger.info("Starting simulation...")
    env.run(till=30)
    logger.info("Simulation complete")

if __name__ == "__main__":
    main()