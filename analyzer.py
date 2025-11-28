import cv2
import numpy as np
import pytesseract
import mss
import time
import re
from game_state import GameState

from paddleocr import PaddleOCR
import logging

# Suppress PaddleOCR logging
logging.getLogger("ppocr").setLevel(logging.ERROR)



class Analyzer:
    def __init__(self, livesplit_client, timer_region=None, gametype_region=None, level_region=None, countdown_region=None, log_callback=None, latency_compensation=0.1):
        self.livesplit = livesplit_client
        self.state = GameState()
        # self.sct = mss.mss() # Moved to thread
        
        # Four separate regions
        self.timer_region = timer_region
        self.gametype_region = gametype_region
        self.level_region = level_region
        self.countdown_region = countdown_region
        
        self.running = False
        self.log_callback = log_callback  # Function to call for logging
        self.latency_compensation = latency_compensation # User-configurable buffer
        
        self.last_split_time = 0
        self.split_cooldown = 5 # Seconds
        
        # Track previous timer value to detect jumps
        self.last_timer_value = None
        
        # Track countdown sequence (3 -> 2 -> 1)
        self.last_countdown_value = None
        self.last_countdown_reset_time = 0
        self.countdown_reset_cooldown = 10 # Don't reset again within 10 seconds
        
        # OCR Optimization Flags - Enable/disable OCR regions based on state
        self.ocr_countdown_enabled = True   # Start with countdown enabled
        self.ocr_gametype_enabled = True    # Start with gametype enabled (Parallel detection)
        self.ocr_timer_enabled = False      # Enable after gametype detected
        self.ocr_level_enabled = False      # Enable when run starts
        self.gametype_detected = False      # Track if we've detected game type
        
        # Debug
        self.debug_mode = True
        self.debug_counter = 0
        
        # Initialize PaddleOCR (English, use_angle_cls=False for speed)
        # use_gpu=False for CPU (or True if CUDA available and installed)
        print("Initializing PaddleOCR... (this may take a moment)", flush=True)
        self.ocr = PaddleOCR(use_angle_cls=False, lang='en')
        print("PaddleOCR Initialized!", flush=True)
    
    def log(self, message):
        """Log to both console and GUI"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        timestamped_msg = f"[{timestamp}] {message}"
        print(timestamped_msg, flush=True)
        if self.log_callback:
            self.log_callback(timestamped_msg)

    def update_regions(self, timer_region=None, gametype_region=None, level_region=None, countdown_region=None):
        """Update one or more regions"""
        if timer_region:
            self.timer_region = timer_region
        if gametype_region:
            self.gametype_region = gametype_region
        if level_region:
            self.level_region = level_region
        if countdown_region:
            self.countdown_region = countdown_region

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
        # Robust Preprocessing for PaddleOCR (Recognition Mode)
        # 1. Upscale (2x) to ensure text is large enough
        h, w = img.shape[:2]
        img = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        
        # 2. Invert (White text on Dark bg -> Black text on White bg)
        # PaddleOCR (and most OCR) is trained on black text on white paper
        img = cv2.bitwise_not(img)
        
        # 3. Add Padding (White border)
        # Helps if text is touching edges
        img = cv2.copyMakeBorder(img, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        
        return img
        
        # OLD TESSERACT PREPROCESSING (Disabled)
        # gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # _, thresh = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
        # return thresh

    def run_ocr(self, img, whitelist=None):
        """
        Run PaddleOCR on the image.
        Returns the concatenated text found.
        """
        if img is None:
            return ""
            
        # PaddleOCR expects RGB or BGR, works with grayscale too but might need conversion
        # It handles numpy arrays directly
        
        # Ensure 3 channels (PaddleOCR might fail on single channel)
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        
        # Run OCR
        # Calling without arguments defaults to det=True, rec=True, cls=False (from init)
        try:
            result = self.ocr.ocr(img)
        except Exception as e:
            print(f"OCR ERROR: {e}", flush=True)
            return ""
        
        # Result structure with det=False: [(text, score)]
        # Result structure with det=True: [ [ [box], [text, score] ], ... ]
        
        # DEBUG: Log raw result to see what's happening
        # print(f"DEBUG OCR RAW: {result}", flush=True)
        
        full_text = []
        if result:
            # Check format
            if isinstance(result[0], tuple):
                # Recognition only format: [(text, score), ...]
                for line in result:
                    text = line[0]
                    score = line[1]
                    # print(f"DEBUG OCR CANDIDATE: '{text}' (score: {score})", flush=True)
                    if score > 0.1: # Lowered threshold from 0.6 to 0.1
                        full_text.append(text)
            elif isinstance(result[0], list):
                # Detection + Recognition format
                for line in result[0]:
                    text = line[1][0]
                    score = line[1][1]
                    # print(f"DEBUG OCR CANDIDATE: '{text}' (score: {score})", flush=True)
                    if score > 0.1:
                        full_text.append(text)
                # Optional: Filter by whitelist if provided (simple regex)
                if whitelist:
                    # Very basic filtering - keep only chars in whitelist
                    # But regex is better done by caller usually
                    pass
                full_text.append(text)
        
        return " ".join(full_text).strip()

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
        
        # Check that required regions are set (countdown is optional)
        if not self.timer_region or not self.gametype_region or not self.level_region:
            self.log("ERROR: Not all required regions are set. Please select Timer, Game Type, and Level regions.")
            return
        
        if self.countdown_region:
            self.log("Countdown region enabled - timer will reset when countdown (3, 2, 1) is detected")
        
        try:
            with mss.mss() as sct:
                while self.running:
                    try:
                        loop_start_time = time.time()
                        
                        # STATE-BASED OCR - Only run necessary OCR operations
                        countdown_text = ""
                        gametype_text = ""
                        timer_text = ""
                        level_text = ""
                        
                        # 1. Countdown OCR (when enabled)
                        if self.ocr_countdown_enabled and self.countdown_region:
                            countdown_frame = self.capture_frame(sct, self.countdown_region)
                            if countdown_frame is not None:
                                countdown_thresh = self.preprocess_image(countdown_frame)
                                # countdown_text = pytesseract.image_to_string(countdown_thresh, config='--psm 7 -c tessedit_char_whitelist=0123456789').strip()
                                countdown_text = self.run_ocr(countdown_thresh)
                        
                        # 2. Game Type OCR (when enabled)
                        if self.ocr_gametype_enabled:
                            gametype_frame = self.capture_frame(sct, self.gametype_region)
                            if gametype_frame is not None:
                                gametype_thresh = self.preprocess_image(gametype_frame)
                                # gametype_text = pytesseract.image_to_string(gametype_thresh, config='--psm 7').strip()
                                gametype_text = self.run_ocr(gametype_thresh)
                        
                        # 3. Timer OCR (when enabled)
                        if self.ocr_timer_enabled:
                            timer_frame = self.capture_frame(sct, self.timer_region)
                            if timer_frame is not None:
                                timer_thresh = self.preprocess_image(timer_frame)
                                # timer_text = pytesseract.image_to_string(timer_thresh, config='--psm 7 -c tessedit_char_whitelist=0123456789:').strip()
                                timer_text = self.run_ocr(timer_thresh)
                        
                        # 4. Level OCR (when enabled)
                        if self.ocr_level_enabled:
                            level_frame = self.capture_frame(sct, self.level_region)
                            if level_frame is not None:
                                level_thresh = self.preprocess_image(level_frame)
                                # level_text = pytesseract.image_to_string(level_thresh, config='--psm 7').strip()
                                level_text = self.run_ocr(level_thresh)
                        
                        # COUNTDOWN DETECTION - Simple: Reset when "2" appears after "3"
                        if countdown_text == '3':
                            # Remember we saw 3
                            self.last_countdown_value = '3'
                        elif countdown_text == '2' and self.last_countdown_value == '3':
                            # 3 -> 2 transition detected! Reset timer
                            if time.time() - self.last_countdown_reset_time > self.countdown_reset_cooldown:
                                self.log(f"Countdown detected (3->2) - Resetting LiveSplit timer")
                                # OPTIMIZATION: After countdown, disable countdown OCR
                                # Since GameType is checked in parallel, we can switch DIRECTLY to Timer OCR
                                self.ocr_countdown_enabled = False
                                self.ocr_gametype_enabled = False # Disable gametype too (assume checked or don't care)
                                self.ocr_timer_enabled = True
                                self.gametype_detected = False
                                self.log("OCR: Countdown disabled, Timer enabled (GameType skipped/done)")
                                
                            self.last_countdown_value = None  # Reset for next countdown
                        elif countdown_text not in ['1', '2', '3']:
                            # Not a countdown number, reset tracking
                            self.last_countdown_value = None
                        
                        # GAME TYPE DETECTION - Detect once then disable (Parallel with Countdown)
                        if self.ocr_gametype_enabled and not self.gametype_detected and gametype_text:
                            if "ZOMBIES" in gametype_text.upper() or "SURVIVAL" in gametype_text.upper():
                                self.gametype_detected = True
                                self.log(f"Game type detected: {gametype_text}")
                                # Don't change other flags, just mark as detected
                                # We wait for countdown to finish to switch to Timer

                        # Logic
                        current_time_seconds = self.parse_time(timer_text)
                        
                        # Debug - only log every 10 frames to reduce spam
                        # Debug - only log every 10 frames to reduce spam
                        if self.debug_counter % 10 == 0:
                            log_parts = []
                            if self.ocr_timer_enabled or timer_text:
                                log_parts.append(f"Timer: '{timer_text}' ({current_time_seconds})")
                            if self.ocr_gametype_enabled or gametype_text:
                                log_parts.append(f"GameType: '{gametype_text}'")
                            if self.ocr_level_enabled or level_text:
                                log_parts.append(f"Level: '{level_text}'")
                            if self.ocr_countdown_enabled and countdown_text:
                                log_parts.append(f"Countdown: '{countdown_text}'")
                            
                            if log_parts:
                                self.log(", ".join(log_parts))

                        # Debug: Save images every 30 frames
                        if self.debug_mode and self.debug_counter % 30 == 0:
                            if self.ocr_timer_enabled and timer_frame is not None:
                                cv2.imwrite('debug_timer.png', timer_frame)
                                if 'timer_thresh' in locals(): cv2.imwrite('debug_timer_processed.png', timer_thresh)
                                
                            if self.ocr_gametype_enabled and gametype_frame is not None:
                                cv2.imwrite('debug_gametype.png', gametype_frame)
                                if 'gametype_thresh' in locals(): cv2.imwrite('debug_gametype_processed.png', gametype_thresh)
                                
                            if self.ocr_level_enabled and level_frame is not None:
                                cv2.imwrite('debug_level.png', level_frame)
                                if 'level_thresh' in locals(): cv2.imwrite('debug_level_processed.png', level_thresh)
                                
                            if self.ocr_countdown_enabled and countdown_frame is not None:
                                cv2.imwrite('debug_countdown.png', countdown_frame)
                                if 'countdown_thresh' in locals(): cv2.imwrite('debug_countdown_processed.png', countdown_thresh)
                            
                            # self.log("Saved debug images")
                        self.debug_counter += 1

                        if self.state.state == GameState.IDLE or self.state.state == GameState.FINISHED:
                            # Start Detection: Detect JUMP from low time to high time (approximately +10 minutes)
                            if current_time_seconds and self.last_timer_value:
                                timer_jump = current_time_seconds - self.last_timer_value
                                # If timer jumps UP by at least 10 minutes (600 seconds), it's a start
                                if timer_jump >= 600:
                                    self.log(f"Detected Start Condition (Timer jump: {self.last_timer_value}s → {current_time_seconds}s, +{timer_jump}s). Starting Run.")
                                    self.state.start_run(current_time_seconds)
                                    self.livesplit.start()
                                    self.livesplit.set_gametime(0) # Start at 0
                                    
                                    # OPTIMIZATION: Run started, enable Level OCR
                                    self.ocr_level_enabled = True
                                    self.log("OCR: Run started, Level enabled")
                            
                            # Update last timer value for next iteration
                            if current_time_seconds:
                                self.last_timer_value = current_time_seconds

                        elif self.state.state == GameState.RUNNING or self.state.state == GameState.FINISHED:
                            # Reset Detection: DISABLED as per user request
                            # if current_time_seconds and current_time_seconds < 600:
                            #    self.log(f"Detected Lobby/Low Time ({current_time_seconds}s). Resetting state to IDLE.")
                            #    self.state.reset()
                            #    self.livesplit.reset()
                            
                            # IGT Update: Sync LiveSplit Game Time with OCR Time
                            # DISABLED as per user request (only set once at start)
                            # if current_time_seconds is not None and self.state.start_time is not None:
                            #     # Calculate elapsed Game Time
                            #     # Start Time (e.g. 1800s) - Current Time (e.g. 1789s) = 11s elapsed
                            #     elapsed_gametime = self.state.start_time - current_time_seconds
                            #     
                            #     # COMPENSATION: Add processing latency + buffer
                            #     # The frame captured at 'loop_start_time' took 'time.time() - loop_start_time' to process.
                            #     # By the time we send this, the game has advanced by that much.
                            #     # We also add a small buffer (user configured) to account for transmission/display lag
                            #     latency = time.time() - loop_start_time
                            #     adjusted_gametime = elapsed_gametime + latency + self.latency_compensation
                            #     
                            #     # Send to LiveSplit (only if valid positive time)
                            #     if adjusted_gametime >= 0:
                            #         self.livesplit.set_gametime(adjusted_gametime)
                            
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
                                    
                                    # OPTIMIZATION: Run finished, reset OCR state
                                    self.ocr_countdown_enabled = True
                                    self.ocr_gametype_enabled = False
                                    self.ocr_timer_enabled = False
                                    self.ocr_level_enabled = False
                                    self.gametype_detected = False
                                    self.log("OCR: Run finished, resetting state (Countdown enabled)")
                            
                            # 2. Traditional end detection (VICTOIRE/SCORE text)
                            if "VICTOIRE" in level_text.upper() or "SCORE" in level_text.upper():
                                self.log("Run Complete: Detected VICTOIRE/SCORE")
                                self.state.finish_run()
                                self.livesplit.split()
                                
                                # OPTIMIZATION: Run finished, reset OCR state
                                self.ocr_countdown_enabled = True
                                self.ocr_gametype_enabled = True # Enable parallel detection
                                self.ocr_timer_enabled = False
                                self.ocr_level_enabled = False
                                self.gametype_detected = False
                                self.log("OCR: Run finished, resetting state (Countdown + GameType enabled)")

                        # No sleep - process frames as fast as possible for instant response
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
