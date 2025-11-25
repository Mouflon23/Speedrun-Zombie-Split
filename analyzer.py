import cv2
import numpy as np
import pytesseract
import mss
import time
import re
from game_state import GameState

# Set tesseract path if needed (Windows default)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# If the user has it elsewhere, they might need to uncomment and adjust this.
try:
    pytesseract.get_tesseract_version()
except pytesseract.TesseractNotFoundError:
    print("Tesseract not found in PATH. Trying default location...", flush=True)
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'



class Analyzer:
    def __init__(self, livesplit_client, timer_region=None, gametype_region=None, level_region=None, log_callback=None):
        self.livesplit = livesplit_client
        self.state = GameState()
        # self.sct = mss.mss() # Moved to thread
        
        # Three separate regions
        self.timer_region = timer_region
        self.gametype_region = gametype_region
        self.level_region = level_region
        
        self.running = False
        self.log_callback = log_callback  # Function to call for logging
        
        self.last_split_time = 0
        self.split_cooldown = 5 # Seconds
        
        # Debug
        self.debug_mode = True
        self.debug_counter = 0
    
    def log(self, message):
        """Log to both console and GUI"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        timestamped_msg = f"[{timestamp}] {message}"
        print(timestamped_msg, flush=True)
        if self.log_callback:
            self.log_callback(timestamped_msg)

    def update_regions(self, timer_region=None, gametype_region=None, level_region=None):
        """Update one or more regions"""
        if timer_region:
            self.timer_region = timer_region
        if gametype_region:
            self.gametype_region = gametype_region
        if level_region:
            self.level_region = level_region

    def capture_frame(self, sct, region):
        if not region:
            return None
        
        # mss requires int
        monitor = {
            "top": int(region['top']),
            "left": int(region['left']),
            "width": int(region['width']),
            "height": int(region['height'])
        }
        img = np.array(sct.grab(monitor))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def preprocess_image(self, img, upscale=3):
        """
        Preprocess image for better OCR accuracy.
        - Upscale the image (OCR works better on larger text)
        - Convert to grayscale
        - Apply thresholding to isolate white text
        """
        # Upscale for better OCR
        h, w = img.shape[:2]
        img = cv2.resize(img, (w * upscale, h * upscale), interpolation=cv2.INTER_CUBIC)
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Try adaptive threshold first (better for varying lighting)
        # thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        
        # Or simple threshold for white text on dark background
        _, thresh = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
        
        return thresh

    def parse_time(self, text):
        # Matches MM:SS, M:SS, MM SS, M SS, MM.SS, etc.
        # Replace common OCR errors
        text = text.replace('O', '0').replace('o', '0')
        
        # Try finding digits separated by colon, dot, or space
        match = re.search(r'(\d{1,2})[:\.\s](\d{2})', text)
        if match:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            return minutes * 60 + seconds
        return None

    def process_loop(self):
        self.log("=== PROCESS LOOP STARTED ===")
        self.running = True
        
        # Check that all regions are set
        if not self.timer_region or not self.gametype_region or not self.level_region:
            self.log("ERROR: Not all regions are set. Please select all three regions.")
            return
        
        try:
            with mss.mss() as sct:
                while self.running:
                    try:
                        # Capture from each region separately
                        timer_frame = self.capture_frame(sct, self.timer_region)
                        gametype_frame = self.capture_frame(sct, self.gametype_region)
                        level_frame = self.capture_frame(sct, self.level_region)
                        
                        if timer_frame is None or gametype_frame is None or level_frame is None:
                            time.sleep(0.1)
                            continue

                        # Preprocess each frame
                        timer_thresh = self.preprocess_image(timer_frame)
                        gametype_thresh = self.preprocess_image(gametype_frame)
                        level_thresh = self.preprocess_image(level_frame)

                        # Debug: Save images every 30 frames
                        if self.debug_mode and self.debug_counter % 30 == 0:
                            cv2.imwrite(f'debug_timer_{self.debug_counter}.png', timer_thresh)
                            cv2.imwrite(f'debug_gametype_{self.debug_counter}.png', gametype_thresh)
                            cv2.imwrite(f'debug_level_{self.debug_counter}.png', level_thresh)
                        self.debug_counter += 1

                        # OCR
                        # psm 7 = Treat the image as a single text line.
                        timer_text = pytesseract.image_to_string(timer_thresh, config='--psm 7 -c tessedit_char_whitelist=0123456789:').strip()
                        gametype_text = pytesseract.image_to_string(gametype_thresh, config='--psm 7').strip()
                        level_text = pytesseract.image_to_string(level_thresh, config='--psm 7').strip()

                        # Logic
                        current_time_seconds = self.parse_time(timer_text)
                        
                        # Debug - only log every 10 frames to reduce spam
                        if self.debug_counter % 10 == 0:
                            self.log(f"Timer: '{timer_text}' ({current_time_seconds}), GameType: '{gametype_text}', Level: '{level_text}'")

                        if self.state.state == GameState.IDLE or self.state.state == GameState.FINISHED:
                            # Start Detection: Jump from low time to high time
                            # Or just if we see a high time (e.g. > 15 minutes) and we were not running
                            if current_time_seconds and current_time_seconds > 900: # > 15 mins
                                 # Wait, usually it goes 05:00 -> 30:00. 
                                 # If we see > 15:00, it's likely a start.
                                 self.log(f"Detected Start Condition (Timer: {current_time_seconds}). Starting Run.")
                                 self.state.start_run(current_time_seconds)
                                 self.livesplit.start()
                                 self.livesplit.set_gametime(0) # Start at 0

                        elif self.state.state == GameState.RUNNING or self.state.state == GameState.FINISHED:
                            # Reset Detection: DISABLED as per user request
                            # if current_time_seconds and current_time_seconds < 600:
                            #    self.log(f"Detected Lobby/Low Time ({current_time_seconds}s). Resetting state to IDLE.")
                            #    self.state.reset()
                            #    self.livesplit.reset()
                            
                            # IGT Update: DISABLED as per user request (only set once at start)
                            
                            # Split Logic
                            # 1. "ZOMBIES" transition
                            if "ZOMBIES" in level_text.upper():
                                if time.time() - self.last_split_time > self.split_cooldown:
                                    self.log("Triggering Split: ZOMBIES transition")
                                    self.livesplit.split()
                                    self.last_split_time = time.time()
                            
                            # 2. Level Name Change
                            # Filter noise - only process clean level names
                            clean_level = level_text.strip()
                            # Allow spaces in level names (e.g. "Top Floor")
                            is_valid_name = clean_level.replace(" ", "").isalpha()
                            if len(clean_level) > 2 and "ZOMBIES" not in clean_level.upper() and is_valid_name:
                                 # Check if level changed (Valid Sequence)
                                 if self.state.set_level(level_text):
                                     # Level changed (e.g. Isolation -> Lab)
                                     # Trigger split if we haven't split recently (e.g. on "ZOMBIES")
                                     if time.time() - self.last_split_time > self.split_cooldown:
                                         self.log(f"Triggering Split: Level changed to '{level_text}'")
                                         self.livesplit.split()
                                         self.last_split_time = time.time()
                                     else:
                                         self.log(f"Level changed to '{level_text}' (Split already handled by ZOMBIES)")

                            # End Logic
                            # 1. Game Type Change Detection (after Hangar level)
                            # If we're at Hangar and GameType changes from ZOMBIES, the run is complete
                            if self.state.current_level == "Hangar":
                                if "ZOMBIES" not in gametype_text.upper() and len(gametype_text.strip()) > 0:
                                    self.log(f"Run Complete: GameType changed from ZOMBIES to '{gametype_text}' at Hangar")
                                    self.state.finish_run()
                                    self.livesplit.split()
                            
                            # 2. Traditional end detection (VICTOIRE/SCORE text)
                            if "VICTOIRE" in level_text.upper() or "SCORE" in level_text.upper():
                                self.log("Run Complete: Detected VICTOIRE/SCORE")
                                self.state.finish_run()
                                self.livesplit.split()

                        time.sleep(0.05) # 20 FPS for more responsive updates
                    except Exception as e:
                        self.log(f"ERROR in frame processing: {e}")
                        import traceback
                        traceback.print_exc()
                        time.sleep(0.1)
        except Exception as e:
            self.log(f"FATAL ERROR in process_loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.log("=== PROCESS LOOP ENDED ===")

    def stop(self):
        self.log("=== STOP REQUESTED ===")
        self.running = False
