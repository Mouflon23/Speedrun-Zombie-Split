class GameState:
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"

    def __init__(self):
        self.state = self.IDLE
        self.current_level = None
        self.start_time_value = None # The timer value when the run started (e.g., 30:00)
        self.last_timer_value = None
        
        # Define expected level sequence
        self.level_sequence = ["Isolation", "Lab", "Top Floor", "Reactor", "Hangar"]
        self.current_level_index = -1

    def reset(self):
        self.state = self.IDLE
        self.current_level = None
        self.current_level_index = -1
        self.start_time_value = None
        self.last_timer_value = None

    def start_run(self, start_timer_value):
        self.state = self.RUNNING
        self.start_time_value = start_timer_value
        self.last_timer_value = start_timer_value
        self.current_level = self.level_sequence[0] # Assume start at first level
        self.current_level_index = 0
        print(f"Run Started! Initial Timer: {start_timer_value}", flush=True)

    def set_level(self, level_name):
        # Clean input
        level_name = level_name.strip()
        
        # Check against ALL future levels to allow skipping/recovery
        # Start from next level
        start_search = self.current_level_index + 1
        
        for i in range(start_search, len(self.level_sequence)):
            expected = self.level_sequence[i]
            
            # Check match
            if expected.upper() in level_name.upper():
                # Found a match!
                if i == start_search:
                    print(f"Level Changed (Valid Sequence): {self.current_level} -> {expected}", flush=True)
                else:
                    print(f"Level Changed (SKIPPED TO): {self.current_level} -> {expected} (Skipped {i - start_search} levels)", flush=True)
                
                self.current_level = expected
                self.current_level_index = i
                return True # Level changed
        
        # Debug logging to see why it fails
        # if len(level_name) > 3:
        #    print(f"DEBUG: '{level_name}' did not match any future level starting from index {start_search}", flush=True)
        
        return False

    def finish_run(self):
        self.state = self.FINISHED
        print("Run Finished!", flush=True)
