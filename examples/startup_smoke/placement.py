"""Place the generated household using the windowed game UI."""

import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path
import time

from PIL import ImageGrab, ImageStat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("window", type=int)
    parser.add_argument("output", type=Path)
    parser.add_argument("saves", type=Path)
    parser.add_argument("seconds", type=float)
    args = parser.parse_args()

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetProcessDPIAware()
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    bounds = wintypes.RECT()
    origin = wintypes.POINT()
    if not user32.GetClientRect(args.window, ctypes.byref(bounds)) or not user32.ClientToScreen(
        args.window, ctypes.byref(origin)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    if bounds.right < 1000 or not 1.6 <= bounds.right / bounds.bottom <= 2.0:
        raise SystemExit("Placement requires a landscape game window at least 1000 pixels wide.")

    def point(x, y):
        return round(x * bounds.right / 1920), round(y * bounds.bottom / 1080)

    def click(x, y):
        if user32.GetForegroundWindow() != args.window:
            raise SystemExit("The Sims 4 lost focus during placement.")
        px, py = point(x, y)
        user32.SetCursorPos(origin.x + px, origin.y + py)
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        user32.mouse_event(0x0004, 0, 0, 0, 0)

    def average(frame, left, top, right, bottom):
        return ImageStat.Stat(frame.crop((*point(left, top), *point(right, bottom)))).mean

    placement_deadline = time.monotonic() + args.seconds

    def wait_for(stage, ready, timeout=8):
        deadline = min(time.monotonic() + timeout, placement_deadline)
        while True:
            if user32.GetForegroundWindow() != args.window:
                raise SystemExit("The Sims 4 lost focus during placement.")
            frame = ImageGrab.grab(
                bbox=(origin.x, origin.y, origin.x + bounds.right, origin.y + bounds.bottom),
                all_screens=True,
            )
            if ready(frame):
                return frame
            if time.monotonic() >= deadline:
                path = args.output / f"placement-{stage}.png"
                frame.save(path)
                raise SystemExit(f"Timed out waiting for {stage}. Screenshot: {path}")
            time.sleep(0.08)

    def world_ready(frame):
        red, green, blue = average(frame, 910, 320, 975, 400)
        return red >= green and red > blue + 40 and average(frame, 60, 100, 200, 300)[0] > 180

    def map_ready(frame):
        red, green, blue = average(frame, 680, 485, 1240, 760)
        return (green > red + 12 or green > blue + 20) and average(frame, 60, 100, 200, 300)[1] > 95

    def move_button_ready(frame):
        rim = average(frame, 1826, 974, 1857, 989)
        red, green, blue = average(frame, 1810, 1000, 1873, 1022)
        return min(rim) > 225 and max(green, blue) > red + 70

    cursor = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(cursor))
    previous = user32.GetForegroundWindow()
    if previous != args.window and not user32.SetForegroundWindow(args.window):
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
        user32.SetForegroundWindow(args.window)
    try:
        wait_for("world-selection", world_ready, timeout=16)
        click(681, 300)
        wait_for("Willow-Creek", map_ready)
        click(1101, 675)
        selected_lot = wait_for("lot-selection", move_button_ready)
        click(1844, 1018)
        map_green = average(selected_lot, 100, 300, 350, 480)[1]
        autosave = args.saves / "Slot_ffffffff.save"

        def confirmation_ready(frame):
            return (average(frame, 100, 300, 350, 480)[1] < map_green - 20
                    and min(average(frame, 835, 370, 1060, 425)) > 205)

        wait_for("move-in", lambda frame: autosave.is_file() or confirmation_ready(frame))
        if not autosave.is_file():
            click(1243, 750)
            wait_for("move-in-confirmation", lambda frame: autosave.is_file())
    finally:
        if user32.GetForegroundWindow() == args.window:
            user32.SetCursorPos(cursor.x, cursor.y)
            if previous and previous != args.window:
                user32.SetForegroundWindow(previous)


if __name__ == "__main__":
    main()
