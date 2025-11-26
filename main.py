import tkinter as tk
from tkinter import ttk
import threading
import cv2
import mss
import numpy as np
from PIL import Image, ImageTk
from analyzer import Analyzer
from livesplit_client import LiveSplitClient
import sys

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("EVA Zombie Split Analyzer")
        self.root.geometry("400x520")
        self.root.attributes("-topmost", True)

        self.livesplit = LiveSplitClient()
        self.analyzer = Analyzer(self.livesplit, log_callback=self.log_async)
        self.analysis_thread = None
        
        # Four separate regions
        self.timer_region = None
        self.gametype_region = None
        self.level_region = None
        self.countdown_region = None

        self.create_widgets()
        self.load_config()
        
        # Auto-connect to LiveSplit on launch
        self.connect_livesplit()

    def create_widgets(self):
        # Status Frame
        status_frame = ttk.LabelFrame(self.root, text="Status")
        status_frame.pack(fill="x", padx=5, pady=5)

        self.lbl_connection = ttk.Label(status_frame, text="LiveSplit: Disconnected", foreground="red")
        self.lbl_connection.pack(side="left", padx=5)

        btn_connect = ttk.Button(status_frame, text="Connect", command=self.connect_livesplit)
        btn_connect.pack(side="right", padx=5)

        # Region Selection
        region_frame = ttk.LabelFrame(self.root, text="Capture Regions")
        region_frame.pack(fill="x", padx=5, pady=5)

        # Timer Region
        self.lbl_timer_region = ttk.Label(region_frame, text="Timer: Not Selected", foreground="red")
        self.lbl_timer_region.pack(pady=2)
        btn_select_timer = ttk.Button(region_frame, text="Select Timer Region", command=lambda: self.select_region("timer"))
        btn_select_timer.pack(pady=2)
        
        # Game Type Region
        self.lbl_gametype_region = ttk.Label(region_frame, text="Game Type: Not Selected", foreground="red")
        self.lbl_gametype_region.pack(pady=2)
        btn_select_gametype = ttk.Button(region_frame, text="Select Game Type Region", command=lambda: self.select_region("gametype"))
        btn_select_gametype.pack(pady=2)
        
        # Level Region
        self.lbl_level_region = ttk.Label(region_frame, text="Level: Not Selected", foreground="red")
        self.lbl_level_region.pack(pady=2)
        btn_select_level = ttk.Button(region_frame, text="Select Level Region", command=lambda: self.select_region("level"))
        btn_select_level.pack(pady=2)
        
        # Countdown Region (Optional)
        self.lbl_countdown_region = ttk.Label(region_frame, text="Countdown: Not Selected (Optional)", foreground="gray")
        self.lbl_countdown_region.pack(pady=2)
        btn_select_countdown = ttk.Button(region_frame, text="Select Countdown Region", command=lambda: self.select_region("countdown"))
        btn_select_countdown.pack(pady=2)

        # Controls
        control_frame = ttk.LabelFrame(self.root, text="Controls")
        control_frame.pack(fill="x", padx=5, pady=5)
        
        # Latency Compensation Input
        comp_frame = ttk.Frame(control_frame)
        comp_frame.pack(fill="x", padx=5, pady=2)
        ttk.Label(comp_frame, text="Latency Comp (s):").pack(side="left")
        self.var_latency = tk.DoubleVar(value=0.1)
        self.spin_latency = ttk.Spinbox(comp_frame, from_=0.0, to=2.0, increment=0.05, textvariable=self.var_latency, width=6)
        self.spin_latency.pack(side="left", padx=5)
        self.spin_latency.bind("<FocusOut>", self.update_latency)
        self.spin_latency.bind("<Return>", self.update_latency)

        self.btn_start = ttk.Button(control_frame, text="Start Analysis", command=self.toggle_analysis, state="disabled")
        self.btn_start.pack(fill="x", padx=5, pady=5)

        # Preview (Optional, maybe just a text log)
        self.log_text = tk.Text(self.root, height=5, state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    def log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        # Force immediate update
        self.log_text.update_idletasks()
    
    def log_async(self, message):
        """Thread-safe logging - schedules update on main thread"""
        self.root.after(0, lambda: self.log(message))

    def connect_livesplit(self):
        if self.livesplit.connect():
            self.lbl_connection.config(text="LiveSplit: Connected", foreground="green")
            self.log("Connected to LiveSplit Server.")
        else:
            self.lbl_connection.config(text="LiveSplit: Failed", foreground="red")
            self.log("Failed to connect to LiveSplit. Make sure Server is running.")

    def select_region(self, region_type):
        """region_type: 'timer', 'gametype', or 'level'"""
        self.root.withdraw()
        selector = RegionSelector(self.root, lambda r: self.set_region(region_type, r))

    def set_region(self, region_type, region):
        self.root.deiconify()
        if region:
            # Store the region
            if region_type == "timer":
                self.timer_region = region
                self.lbl_timer_region.config(text=f"Timer: {region['width']}x{region['height']}", foreground="green")
            elif region_type == "gametype":
                self.gametype_region = region
                self.lbl_gametype_region.config(text=f"Game Type: {region['width']}x{region['height']}", foreground="green")
            elif region_type == "level":
                self.level_region = region
                self.lbl_level_region.config(text=f"Level: {region['width']}x{region['height']}", foreground="green")
            elif region_type == "countdown":
                self.countdown_region = region
                self.lbl_countdown_region.config(text=f"Countdown: {region['width']}x{region['height']}", foreground="green")
            
            # Update analyzer
            self.analyzer.update_regions(
                timer_region=self.timer_region,
                gametype_region=self.gametype_region,
                level_region=self.level_region,
                countdown_region=self.countdown_region
            )
            
            # Enable start button if all three REQUIRED regions are set (countdown is optional)
            if self.timer_region and self.gametype_region and self.level_region:
                self.btn_start.config(state="normal")
            
            # Save configuration
            self.save_config()
            self.log(f"{region_type.capitalize()} region selected: {region['width']}x{region['height']}")

    def load_config(self):
        """Load regions from config file"""
        import json
        import os
        
        config_file = "config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                
                # Load regions
                if 'timer_region' in config:
                   self.set_region('timer', config['timer_region'])
                if 'gametype_region' in config:
                    self.set_region('gametype', config['gametype_region'])
                if 'level_region' in config:
                    self.set_region('level', config['level_region'])
                if 'countdown_region' in config:
                    self.set_region('countdown', config['countdown_region'])
                
                # Load latency compensation
                if 'latency_compensation' in config:
                    self.var_latency.set(config['latency_compensation'])
                
                self.log("Configuration loaded.")
            except Exception as e:
                self.log(f"Failed to load config: {e}")
    
    def save_config(self):
        """Save regions to config file"""
        import json
        
        config = {
            'timer_region': self.timer_region,
            'gametype_region': self.gametype_region,
            'level_region': self.level_region,
            'countdown_region': self.countdown_region,
            'latency_compensation': self.var_latency.get()
        }
        
        try:
            with open("config.json", 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.log(f"Failed to save config: {e}")

    def update_latency(self, event=None):
        """Update analyzer latency when input changes"""
        val = self.var_latency.get()
        self.analyzer.latency_compensation = val
        self.save_config()
        # self.log(f"Latency compensation updated to {val}s")

    def toggle_analysis(self):
        if self.analysis_thread and self.analysis_thread.is_alive():
            self.analyzer.stop()
            self.btn_start.config(text="Start Analysis")
            self.log("=== ANALYSIS STOPPED ===")
        else:
            # Update latency before starting
            self.analyzer.latency_compensation = self.var_latency.get()
            
            self.log("=== ANALYSIS STARTED ===")
            self.analysis_thread = threading.Thread(target=self.analyzer.process_loop)
            self.analysis_thread.daemon = True
            self.analysis_thread.start()
            self.btn_start.config(text="Stop Analysis")

class RegionSelector:
    def __init__(self, master, callback):
        self.master = master
        self.callback = callback
        self.top = tk.Toplevel(master)
        self.top.attributes("-fullscreen", True)
        self.top.attributes("-alpha", 0.3)
        self.top.configure(bg="black")
        
        self.start_x = None
        self.start_y = None
        self.rect = None

        self.canvas = tk.Canvas(self.top, cursor="cross", bg="grey")
        self.canvas.pack(fill="both", expand=True)
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Escape>", self.cancel)

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2)

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        
        width = x2 - x1
        height = y2 - y1
        
        self.top.destroy()
        if width > 10 and height > 10:
            self.callback({'top': y1, 'left': x1, 'width': width, 'height': height})
        else:
            self.callback(None)

    def cancel(self, event):
        self.top.destroy()
        self.callback(None)

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
