---
claude_md_version: 1.1
last_updated: 2025-03-05
---

# Project Overview
This is a steel plant simulation application built with Python (using salabim for simulation, PyQt/PySide for GUI), designed to model and optimize steelmaking processes. It includes equipment layout editing, simulation services, and transportation management.

# Directory Structure
- `/home/runner/workspace/steel-plant-simulation_c3/`: Contains source code.
  - `/home/runner/workspace/steel-plant-simulation_c3/equipment/`: Modules for cranes, ladle cars, and ladle managers.
  - `/home/runner/workspace/steel-plant-simulation_c3/spatial/`: Spatial management for layout positioning.
  - `/home/runner/workspace/steel-plant-simulation_c3/process_control/`: Process control logic.
  - `/home/runner/workspace/steel-plant-simulation_c3/production_units/`: Production unit definitions.
  - `/home/runner/workspace/steel-plant-simulation_c3/setup_wizard.py`: GUI for configuring the simulation layout.
  - `/home/runner/workspace/steel-plant-simulation_c3/simulation_service.py`: Core simulation service logic.
  - `/home/runner/workspace/steel-plant-simulation_c3/equipment_layout_editor.py`: Equipment layout editing interface.
  - `/home/runner/workspace/steel-plant-simulation_c3/ladle_path_editor.py`: Ladle path editing component.
  - `/home/runner/workspace/steel-plant-simulation_c3/config.json`: Main configuration file.
  - `/home/runner/workspace/steel-plant-simulation_c3/test.py`: Basic simulation tests.
- `/home/runner/workspace/steel-plant-simulation_c3/tests/`: Test suites.

# Key Components
- `setup_wizard.py`: Implements `SetupWizard` and pages like `PlacementPage` and `EquipmentConfigPage`.
- `simulation_service.py`: Manages simulation state and configuration.
- `equipment_layout_editor.py`: Equipment layout editing interface with classes like `EquipmentLayoutEditor`, `LayoutScene`, and `LayoutView`.
- `ladle_path_editor.py`: Component for editing ladle car paths.

# Coding Conventions
- Use PEP 8 for Python style.
- Use Qt styles for GUI elements.
- Comprehensive logging for debugging.
- Use the Replace tool instead of Edit for large or complex file changes, as it avoids string matching issues.
- When small edits are required, be very precise with string matching including whitespace.
- Always use dispatch_agent to find exact line numbers and content before attempting edits.

# Frequently Used Commands
- `python setup_wizard.py`: Launches the setup wizard GUI.
- `python main.py`: Runs the main simulation.
- `python test.py`: Runs basic simulation tests.

# Important Files
- `config.json`: Main configuration file for simulation.
- `config_backup.json`: Stores configuration backups.
- `setup_wizard.log`: Logs GUI actions and errors.

# Project-Specific Terms
- **Bay**: A physical area in the layout for equipment.
- **Equipment**: Entities like EAF, LMF, Degasser, Caster.
- **Heat**: A batch of molten steel being processed through the plant.
- **Ladle Car Path**: Defined route for ladle cars to follow in the layout.

# Integration Points
- **salabim**: For discrete-event simulation.
- **PyQt/PySide**: For the GUI (Equipment Layout Editor).
- **JSON**: For configuration storage.

# Testing Strategy
- Unit tests for simulation components using `salabim`.
- Integration tests for GUI and configuration persistence.

# Key Classes and Methods
- `EquipmentLayoutEditor`: Main dialog for editing equipment layout
  - `create_ui()`: Creates the editor UI
  - `toggle_ladle_path_mode()`: Toggles path drawing mode
  - `save_layout()`: Saves layout to configuration
  - `load_layout_data()`: Loads layout from configuration
- `LayoutScene`: Graphics scene for the layout
  - `set_ladle_path_mode()`: Enables/disables path drawing mode
  - `mouseReleaseEvent()`: Handles mouse clicks for adding waypoints
- `LadlePathEditor`: Component for editing ladle paths
  - `toggle_path_drawing()`: Starts/stops path drawing
  - `add_waypoint()`: Adds a waypoint to the current path

# Known Issues and Fixes
- **Equipment Configuration Persistence**: Configurations weren't persisting after saving and closing.
  - **Solution**: Updated `SimulationService.load_config` to ensure `equipment_positions` and `bays` sections exist, and modified `SummaryPage.save_config_file` to guarantee these sections are saved.
  
- **Toggle Button Visibility**: Buttons in the Equipment Layout Editor were hard to read without hovering.
  - **Solution**: Enhanced button styling in `PlacementPage` with high-contrast colors, larger fonts, and tooltips.
  
- **Equipment Sizing**: Equipment appeared too large for the bays.
  - **Solution**: Added size customization to `EquipmentConfigPage` (width/height fields) and updated rendering to use these dimensions.

- **File Path Issues**: Difficulty locating files with relative paths.
  - **Solution**: Always use absolute paths when working with files in this project.

- **String Matching Issues**: The Edit tool often fails with "String to replace not found in file" errors.
  - **Solution**: Use the Replace tool for larger changes, dispatch_agent to find exact content, or make very small, precise edits.

---

**Note**: When making changes to the simulation configuration, use the "Save and Close" button or the "Save Configuration to File" button on the Summary page to ensure your changes persist.