# How to Use EVA Zombie Split Analyzer

## Setup Steps

### 1. Start LiveSplit
- Open LiveSplit
- Go to **Control → Start TCP Server**
- Server should start on port 16834

### 2. Start the Game
- Launch **EVA After-h Moon of the Dead** (Zombie Mode) or a record of your game
- Get to a point where you can see:
  - The **Timer** at the top (e.g., "30:00", "10:00")
  - The **Level Name** below "ZOMBIES" (e.g., "Isolation", "Lab")

### 3. Run the Analyzer
- Double-click `run.bat` (or run `python main.py`)
- Click **"Connect"** button → Should show "LiveSplit: Connected"

### 4. Select the Capture Region
**IMPORTANT**: This must be done while the game is visible on screen!

- Make sure the game is running and you can see the timer/level name
- Click **"Select Region"** in the app
- Your screen will dim with a transparent overlay
- **Drag a box** around the top-center area that includes:
  - The countdown timer (e.g., "30:00")
  - The word "ZOMBIES"
  - The level name below it (e.g., "Isolation")

**Example of what to select**:
```
┌─────────────────────┐
│      30:00          │  ← Timer
│     ZOMBIES         │  ← Mode
│    Isolation        │  ← Level Name
└─────────────────────┘
```

### 5. Start Analysis
- Click **"Start Analysis"**
- Watch the console/log window for OCR output
- Check the `debug_*.png` files to verify it's reading correctly

### 6. Test with Gameplay
- The app will:
  - **Auto-start** when timer jumps from low (05:00/10:00) to high (30:00+)
  - **Auto-split** when it sees "ZOMBIES" transition between levels
  - **Update IGT** continuously based on the countdown timer
  - **Auto-finish** when it sees "VICTOIRE"

## Troubleshooting

### "Timer: '' (None), Level: '...gibberish...'"
- You selected the wrong region (desktop, taskbar, etc.)
- Solution: Select region while **game is actually visible**

### "Tesseract not found"
- Tesseract OCR is not installed or not in PATH
- Download from: https://github.com/UB-Mannheim/tesseract/wiki
- Install to: `C:\Program Files\Tesseract-OCR\`

### LiveSplit doesn't respond
- Make sure LiveSplit Server is running (Control → Start Server)
- Check that it's on port 16834 (default)
