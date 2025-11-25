import socket
import time

class LiveSplitClient:
    def __init__(self, host='localhost', port=16834):
        self.host = host
        self.port = port
        self.socket = None

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"Connected to LiveSplit Server at {self.host}:{self.port}", flush=True)
            return True
        except Exception as e:
            print(f"Failed to connect to LiveSplit: {e}", flush=True)
            self.socket = None
            return False

    def send_command(self, command):
        if not self.socket:
            return
        try:
            self.socket.sendall((command + '\r\n').encode('utf-8'))
        except Exception as e:
            print(f"Error sending command '{command}': {e}", flush=True)
            self.socket = None  # Force reconnect on next attempt

    def start(self):
        print("[LiveSplit] Starting timer", flush=True)
        self.send_command("starttimer")

    def split(self):
        print("[LiveSplit] Splitting", flush=True)
        self.send_command("split")

    def reset(self):
        self.send_command("reset")

    def pause(self):
        self.send_command("pause")
        
    def resume(self):
        self.send_command("resume")

    def set_gametime(self, seconds):
        # LiveSplit expects time in seconds (float)
        # Only log occasionally to avoid spam
        self.send_command(f"setgametime {seconds}")
