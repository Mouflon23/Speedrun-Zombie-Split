import cv2
import numpy as np
import pytesseract
import mss
import time
import re
from game_state import GameState

# Set tesseract path if needed (Windows default)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class Analyzer:
    def __init__(self, livesplit_client, region=None):
        self.livesplit = livesplit_client
        self.state = GameState()
        self.sct = mss.mss()
        self.region = region # {'top':, 'left':, 'width':, 'height':}
        self.running = False
        
        # Configuration
        self.timer_roi_pct = {'x': 0.3, 'y': 0.0, 'w': 0.4, 'h': 0.4} # Relative to region
        self.level_roi_pct = {'x': 0.2, 'y': 0.6, 'w': 0.6, 'h': 0.4} # Relative to region
        
        self.last_split_time = 0
        self.split_cooldown = 5 # Seconds

    def update_region(self, region):
        self.region = region

    def capture_frame(self):
        if not self.region:
            return None
        
        # mss requires int
        monitor = {
            "top": int(self.region['top']),
            "left": int(self.region['left']),
            "width": int(self.region['width']),
            "height": int(self.region['height'])
        }
        img = np.array(self.sct.grab(monitor))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def preprocess_image(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Threshold to isolate white text
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        # Invert if needed (Tesseract likes black text on white bg sometimes, but white on black works too)
        # Let's stick to white text on black bg for now, maybe invert if issues.
        return thresh

    def parse_time(self, text):
        # Matches MM:SS or M:SS
        match = re.search(r'(\d{1,2}):(\d{2})', text)
        if match:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            return minutes * 60 + seconds
        return None

    def process_loop(self):
        self.running = True
        while self.running:
            frame = self.capture_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            h, w, _ = frame.shape
            
            # Extract ROIs
            # Timer ROI
            tx = int(w * self.timer_roi_pct['x'])
            ty = int(h * self.timer_roi_pct['y'])
            tw = int(w * self.timer_roi_pct['w'])
            th = int(h * self.timer_roi_pct['h'])
            timer_img = frame[ty:ty+th, tx:tx+tw]

            # Level ROI
            lx = int(w * self.level_roi_pct['x'])
            ly = int(h * self.level_roi_pct['y'])
            lw = int(w * self.level_roi_pct['w'])
            lh = int(h * self.level_roi_pct['h'])
            level_img = frame[ly:ly+lh, lx:lx+lw]

            # Preprocess
            timer_thresh = self.preprocess_image(timer_img)
            level_thresh = self.preprocess_image(level_img)

            # OCR
            # psm 7 = Treat the image as a single text line.
            timer_text = pytesseract.image_to_string(timer_thresh, config='--psm 7 -c tessedit_char_whitelist=0123456789:').strip()
            level_text = pytesseract.image_to_string(level_thresh, config='--psm 7').strip()

            # Logic
            current_time_seconds = self.parse_time(timer_text)
            
            # Debug
            # print(f"Timer: {timer_text} ({current_time_seconds}), Level: {level_text}")

            if self.state.state == GameState.IDLE:
                # Start Detection: Jump from low time to high time
                # Or just if we see a high time (e.g. > 15 minutes) and we were not running
                if current_time_seconds and current_time_seconds > 900: # > 15 mins
                     # Wait, usually it goes 05:00 -> 30:00. 
                     # If we see > 15:00, it's likely a start.
                     self.state.start_run(current_time_seconds)
                     self.livesplit.start()
                     self.livesplit.set_gametime(0) # Start at 0

            elif self.state.state == GameState.RUNNING:
                # IGT Update
                if current_time_seconds:
                    # Calculate Elapsed Time
                    # Start: 30:00 (1800s). Current: 29:55 (1795s). Elapsed: 5s.
                    elapsed = self.state.start_time_value - current_time_seconds
                    if elapsed >= 0:
                        self.livesplit.set_gametime(elapsed)
                
                # Split Logic
                # 1. "ZOMBIES" transition
                if "ZOMBIES" in level_text.upper():
                    if time.time() - self.last_split_time > self.split_cooldown:
                        print("Triggering Split: ZOMBIES transition")
                        self.livesplit.split()
                        self.last_split_time = time.time()
                
                # 2. Level Name Change
                # Filter noise
                if len(level_text) > 2 and "ZOMBIES" not in level_text.upper():
                     if self.state.set_level(level_text):
                         # Level changed. 
                         # Note: If we already split on "ZOMBIES", we shouldn't split again immediately.
                         # But "ZOMBIES" is the transition. 
                         # If we go Level A -> ZOMBIES -> Level B.
                         # We split at ZOMBIES.
                         # Then ZOMBIES -> Level B. We don't want to split again.
                         # So we only split if the PREVIOUS level was NOT "ZOMBIES"?
                         # Actually, the user said: "stop timer from previous level when 'Zombies' appear and start the new timer level"
                         # This implies the split happens AT "ZOMBIES".
                         # So when we detect Level B, we just update the state, we don't need to split again.
                         pass

                # End Logic
                # If timer disappears or "VICTOIRE"
                # For now, let's rely on manual end or specific text
                if "VICTOIRE" in level_text.upper() or "SCORE" in level_text.upper():
                    self.state.finish_run()
                    self.livesplit.split()

            time.sleep(0.1) # 10 FPS

    def stop(self):
        self.running = False
