import tkinter as tk
from tkinter import ttk
import threading
import cv2
import mss
import numpy as np
from PIL import Image, ImageTk
from analyzer import Analyzer
from livesplit_client import LiveSplitClient

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("EVA Zombie Split Analyzer")
        self.root.geometry("400x300")
        self.root.attributes("-topmost", True)

        self.livesplit = LiveSplitClient()
        self.analyzer = Analyzer(self.livesplit)
        self.analysis_thread = None

        self.create_widgets()

    def create_widgets(self):
        # Status Frame
        status_frame = ttk.LabelFrame(self.root, text="Status")
        status_frame.pack(fill="x", padx=5, pady=5)

        self.lbl_connection = ttk.Label(status_frame, text="LiveSplit: Disconnected", foreground="red")
        self.lbl_connection.pack(side="left", padx=5)

        btn_connect = ttk.Button(status_frame, text="Connect", command=self.connect_livesplit)
        btn_connect.pack(side="right", padx=5)

        # Region Selection
        region_frame = ttk.LabelFrame(self.root, text="Capture Region")
        region_frame.pack(fill="x", padx=5, pady=5)

        self.lbl_region = ttk.Label(region_frame, text="Region: Not Selected")
        self.lbl_region.pack(pady=5)

        btn_select = ttk.Button(region_frame, text="Select Region", command=self.select_region)
        btn_select.pack(pady=5)

        # Controls
        control_frame = ttk.LabelFrame(self.root, text="Controls")
        control_frame.pack(fill="x", padx=5, pady=5)

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

    def connect_livesplit(self):
        if self.livesplit.connect():
            self.lbl_connection.config(text="LiveSplit: Connected", foreground="green")
            self.log("Connected to LiveSplit Server.")
        else:
            self.lbl_connection.config(text="LiveSplit: Failed", foreground="red")
            self.log("Failed to connect to LiveSplit. Make sure Server is running.")

    def select_region(self):
        self.root.withdraw()
        selector = RegionSelector(self.root, self.set_region)

    def set_region(self, region):
        self.root.deiconify()
        if region:
            self.analyzer.update_region(region)
            self.lbl_region.config(text=f"Region: {region}")
            self.btn_start.config(state="normal")
            self.log(f"Region selected: {region}")

    def toggle_analysis(self):
        if self.analysis_thread and self.analysis_thread.is_alive():
            self.analyzer.stop()
            self.btn_start.config(text="Start Analysis")
            self.log("Analysis stopped.")
        else:
            self.analysis_thread = threading.Thread(target=self.analyzer.process_loop)
            self.analysis_thread.daemon = True
            self.analysis_thread.start()
            self.btn_start.config(text="Stop Analysis")
            self.log("Analysis started.")

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
