"""Dialog for editing the equipment layout."""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.layout_modified = False
        self.setWindowTitle("Equipment Layout Editor")
        self.setMinimumSize(1200, 800)
        # Attributes for path drawing
        self.path_drawing = False
        self.current_path_waypoints = []
        self.current_path_item = None
        self.create_ui()
        self.load_layout_data()