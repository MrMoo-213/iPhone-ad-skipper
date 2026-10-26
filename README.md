# iPhone-ad-skipper
A python script that automatically skips all types of ads on iPhone. This includes some training data but more may be needed depending on the app.

# Instructions
1. Install and setup iDesktop
2. Open the phone's view in `Classic Window` -> `Big Screen`
3. (Optional) if you need to control the whole screen bring your mouse to the bottom and inspect on the floating menu and delete it, To undo this press `F5`
4. Have `ad_skipper.py` and `ad_templates folder` in the same folder (for example we'll call this Downloads)
5. In command prompt / terminal run: `cd C:\Users\yourUsername\Downloads` then `python ad_skipper.py`
6. Press `F4` in both top left corner and bottom right corner of the screen
###### Your now done and can either start it manually by pressing `F9` or use alternative methods listed below

# Usage
* Run it once and leave it running:   `python ad_skipper.py` 
* It sits idle (no screen scanning) until told to start.

#### CONTROL FROM YOUR MACROS (any one of these)
*  Hotkeys:       `F9` = start ad mode      `F10` = stop ad mode
*  Command line:  `python ad_skipper.py` `start` | `stop` | `toggle` | `status` | `quit`
*  UDP message:   send the text `start` / `stop` / `toggle` / `quit` to `127.0.0.1:48765`

#### TEACHING (works any time, even while idle)
*  `F2` = save a SMALL icon (X, arrow) under your mouse cursor
*  `F3` = save a WIDE button (e.g. "Skip Ad" text) under your mouse cursor
*  `F4` = press twice (top-left, then bottom-right) to limit scanning to the game area
*  `F8` = quit
*   Emergency stop: slam the mouse into a screen corner.

###### Templates are saved in ./ad_templates and remembered next time.
