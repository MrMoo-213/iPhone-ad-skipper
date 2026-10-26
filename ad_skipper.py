import os
import sys
import time
import glob
import socket
import threading
# ---------------- SETTINGS (tweak these) ----------------
TEMPLATE_DIR = "ad_templates"
SMALL_SIZE = (48, 48)        # width, height of crop for F2
WIDE_SIZE = (140, 48)        # width, height of crop for F3
MATCH_THRESHOLD = 0.95       # higher = stricter (fewer false clicks), lower = more forgiving
DUPLICATE_THRESHOLD = 0.96   # don't save near-identical templates
SCAN_INTERVAL = 0.3          # seconds between scans while in ad mode
CLICK_COOLDOWN = 1.0         # pause after clicking an ad button
AD_TIMEOUT = 120             # safety: auto-stop ad mode after this many seconds (0 = never)
CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 48765
# --------------------------------------------------------
COMMANDS = {"start", "stop", "toggle", "status", "quit"}
# ---------- client mode: python ad_skipper.py start ----------
if len(sys.argv) > 1:
    cmd = sys.argv[1].lower()
    if cmd not in COMMANDS:
        print(f"Unknown command '{cmd}'. Use one of: {', '.join(sorted(COMMANDS))}")
        sys.exit(1)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1.0)
    s.sendto(cmd.encode(), (CONTROL_HOST, CONTROL_PORT))
    if cmd == "status":
        try:
            print(s.recvfrom(1024)[0].decode())
        except socket.timeout:
            print("no response (is ad_skipper.py running?)")
    sys.exit(0)
# ---------- server mode ----------
import cv2
import numpy as np
import mss
import pyautogui
from pynput import keyboard

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True

os.makedirs(TEMPLATE_DIR, exist_ok=True)

ad_mode = threading.Event()
quit_flag = threading.Event()
region = None
region_points = []
templates = []
lock = threading.Lock()
ad_started_at = 0.0
clicks_this_ad = 0
total_clicks = 0


def get_scale():
    """Ratio of physical pixels to pyautogui coordinates (matters on HiDPI/Retina)."""
    with mss.mss() as sct:
        return sct.monitors[1]["width"] / pyautogui.size().width


SCALE = get_scale()


def grab():
    with mss.mss() as sct:
        mon = region or sct.monitors[1]
        img = np.array(sct.grab(mon))
    return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY), mon


def load_templates():
    global templates
    loaded = []
    for path in sorted(glob.glob(os.path.join(TEMPLATE_DIR, "*.png"))):
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            loaded.append((os.path.basename(path), img))
    with lock:
        templates = loaded
    print(f"[info] {len(loaded)} templates loaded")


def save_template(size):
    pos = pyautogui.position()
    gray, mon = grab()
    cx = int(pos.x * SCALE) - mon["left"]
    cy = int(pos.y * SCALE) - mon["top"]
    w, h = size
    x1, y1 = cx - w // 2, cy - h // 2
    x2, y2 = x1 + w, y1 + h
    if x1 < 0 or y1 < 0 or x2 > gray.shape[1] or y2 > gray.shape[0]:
        print("[warn] too close to the edge of the scan area, try again")
        return
    crop = gray[y1:y2, x1:x2]

    with lock:
        existing = list(templates)
    for name, t in existing:
        if t.shape == crop.shape:
            score = cv2.matchTemplate(crop, t, cv2.TM_CCOEFF_NORMED).max()
            if score >= DUPLICATE_THRESHOLD:
                print(f"[info] already known ({name}), skipped")
                return

    name = f"tpl_{int(time.time() * 1000)}.png"
    cv2.imwrite(os.path.join(TEMPLATE_DIR, name), crop)
    load_templates()


def find_and_click_ad():
    global clicks_this_ad, total_clicks
    with lock:
        current = list(templates)
    if not current:
        return False
    gray, mon = grab()
    for name, t in current:
        if t.shape[0] > gray.shape[0] or t.shape[1] > gray.shape[1]:
            continue
        res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
        _, best, _, loc = cv2.minMaxLoc(res)
        if best >= MATCH_THRESHOLD:
            h, w = t.shape
            px = (mon["left"] + loc[0] + w / 2) / SCALE
            py = (mon["top"] + loc[1] + h / 2) / SCALE
            pyautogui.click(px, py)
            clicks_this_ad += 1
            total_clicks += 1
            print(f"[click] {name} score {best:.2f} at {int(px)},{int(py)}")
            return True
    return False


def start_ad_mode():
    global ad_started_at, clicks_this_ad
    if not ad_mode.is_set():
        ad_started_at = time.time()
        clicks_this_ad = 0
        ad_mode.set()
        print("[ad mode] STARTED - hunting for skip buttons")


def stop_ad_mode(reason="signal"):
    if ad_mode.is_set():
        ad_mode.clear()
        print(f"[ad mode] STOPPED ({reason}) - {clicks_this_ad} clicks this ad")


def handle_command(cmd):
    cmd = cmd.strip().lower()
    if cmd == "start":
        start_ad_mode()
    elif cmd == "stop":
        stop_ad_mode()
    elif cmd == "toggle":
        stop_ad_mode() if ad_mode.is_set() else start_ad_mode()
    elif cmd == "quit":
        quit_flag.set()
    return (f"{'AD MODE' if ad_mode.is_set() else 'IDLE'} | "
            f"templates={len(templates)} | total clicks={total_clicks}")


def udp_listener():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind((CONTROL_HOST, CONTROL_PORT))
    except OSError:
        print(f"[error] port {CONTROL_PORT} busy - is another copy already running?")
        quit_flag.set()
        return
    s.settimeout(0.5)
    while not quit_flag.is_set():
        try:
            data, addr = s.recvfrom(1024)
        except socket.timeout:
            continue
        reply = handle_command(data.decode(errors="ignore"))
        try:
            s.sendto(reply.encode(), addr)
        except OSError:
            pass
    s.close()


def on_press(key):
    global region
    try:
        if key == keyboard.Key.f2:
            save_template(SMALL_SIZE)
        elif key == keyboard.Key.f3:
            save_template(WIDE_SIZE)
        elif key == keyboard.Key.f4:
            pos = pyautogui.position()
            region_points.append((int(pos.x * SCALE), int(pos.y * SCALE)))
            if len(region_points) == 2:
                (x1, y1), (x2, y2) = region_points
                region = {
                    "left": min(x1, x2), "top": min(y1, y2),
                    "width": abs(x2 - x1), "height": abs(y2 - y1),
                }
                region_points.clear()
                print(f"[info] scan region set: {region}")
            else:
                print("[info] top-left set, now hover bottom-right and press F4")
        elif key == keyboard.Key.f9:
            start_ad_mode()
        elif key == keyboard.Key.f10:
            stop_ad_mode("hotkey")
        elif key == keyboard.Key.f8:
            quit_flag.set()
            return False
    except Exception as e:
        print(f"[error] {e}")


def main():
    load_templates()
    print(__doc__)
    threading.Thread(target=udp_listener, daemon=True).start()
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    print("[ready] idle - waiting for a start signal")

    try:
        while not quit_flag.is_set():
            if not ad_mode.is_set():
                time.sleep(0.1)
                continue

            if AD_TIMEOUT and time.time() - ad_started_at > AD_TIMEOUT:
                stop_ad_mode("timeout")
                continue

            if find_and_click_ad():
                time.sleep(CLICK_COOLDOWN)
            else:
                time.sleep(SCAN_INTERVAL)
    except pyautogui.FailSafeException:
        print("[stop] failsafe triggered (mouse in corner)")
    finally:
        listener.stop()
        quit_flag.set()
        print("[bye]")


if __name__ == "__main__":
    main()
