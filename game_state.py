class GameState:
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"

    def __init__(self):
        self.state = self.IDLE
        self.current_level = None
        self.start_time_value = None # The timer value when the run started (e.g., 30:00)
        self.last_timer_value = None

    def reset(self):
        self.state = self.IDLE
        self.current_level = None
        self.start_time_value = None
        self.last_timer_value = None

    def start_run(self, start_timer_value):
        self.state = self.RUNNING
        self.start_time_value = start_timer_value
        self.last_timer_value = start_timer_value
        print(f"Run Started! Initial Timer: {start_timer_value}")

    def set_level(self, level_name):
        if self.current_level != level_name:
            print(f"Level Changed: {self.current_level} -> {level_name}")
            self.current_level = level_name
            return True # Level changed
        return False

    def finish_run(self):
        self.state = self.FINISHED
        print("Run Finished!")
