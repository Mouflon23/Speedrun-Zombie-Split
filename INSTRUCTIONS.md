# How to Use EVA Zombie Split Analyzer

## Setup Steps

### 1. Start LiveSplit
- Open LiveSplit
- Go to **Control → Start TCP Server**
- Server should start on port 16834

### 2. Start the Game
- Launch **EVA After-h Moon of the Dead** (Zombie Mode) or a recording of your game
- Get to a point where you can see:
  - The **Timer** at the top (e.g., "30:00", "10:00")
  - The **Game Type** text ("ZOMBIES" or "SURVIVAL")
  - The **Level Name** (e.g., "Isolation", "Lab", "Top Floor")

### 3. Run the Analyzer
- Double-click `run.bat` (or run `python main.py`)
- Click **"Connect"** button → Should show "LiveSplit: Connected"

### 4. Select the THREE Capture Regions
**IMPORTANT**: All three regions must be selected while the game is visible on screen!

#### A. Select Timer Region
- Click **"Select Timer Region"**
- Drag a box around the countdown timer (e.g., "30:00")
- Should turn green when selected

#### B. Select Game Type Region
- Click **"Select Game Type Region"**
- Drag a box around where "ZOMBIES" or "SURVIVAL" appears
- Should turn green when selected

#### C. Select Level Region
- Click **"Select Level Region"**
- Drag a box around the level name (e.g., "Isolation", "Lab", "Top Floor", "Reactor", "Hangar")
- Should turn green when selected

**Visual Guide**:
```
Screen Layout:

      30:00          ← Timer Region (Select this area)
     
     ZOMBIES         ← Game Type Region (Select this area)
     
    Isolation        ← Level Region (Select this area)
```

**Note**: Your selections are automatically saved to `config.json` and will be loaded next time!

### 5. Start Analysis
- Click **"Start Analysis"** (enabled when all three regions are selected)
- Watch the log window for real-time OCR output
- Verify it's reading correctly from the logs

### 6. How It Works
The app will automatically:
- **Auto-start** when timer jumps from low (~7:00) to high (>15:00)
- **Auto-split** when:
  - It detects "Zombies" transition text, OR
  - Level name changes to the next level in sequence (Isolation → Lab → Top Floor → Reactor → Hangar)
- **Auto-finish** when:
  - Game Type changes from "Zombies" to something else after completing Hangar, OR
  - It detects "Victoire" or "Score" text
- **Consecutive Runs**: Automatically starts a new run after finishing (no manual reset needed)

### 7. Level Sequence
The app enforces the following level order:
1. Isolation
2. Lab
3. Top Floor
4. Reactor
5. Hangar

It will only split when progressing to the next level in this sequence.

## Troubleshooting

### "ERROR: Not all regions are set"
- You haven't selected all three regions yet
- Solution: Select Timer, Game Type, AND Level regions

### "Timer: '' (None), GameType: '...', Level: '...'"
- Timer region may be incorrect or obscured
- Solution: Re-select the timer region while it's clearly visible

### OCR reads wrong text
- Region might be too large or too small
- Solution: Re-select the region to be more precise
- Make sure the text is clearly visible when selecting

### "Tesseract not found"
- Tesseract OCR is not installed or not in PATH
- Download from: https://github.com/UB-Mannheim/tesseract/wiki
- Install to: `C:\Program Files\Tesseract-OCR\`

### LiveSplit doesn't respond
- Make sure LiveSplit Server is running (Control → Start Server)
- Check that it's on port 16834 (default)

### Run doesn't start automatically
- Make sure timer is > 15 minutes (e.g., 30:00) to trigger auto-start
- If stuck in FINISHED state from previous run, just start a new game and it will auto-start

### Level doesn't change / Splits missing
- Verify the Level Region captures the level name clearly
- Check logs to see what text the OCR is reading
- Level must match the exact sequence (Isolation → Lab → Top Floor → Reactor → Hangar)

