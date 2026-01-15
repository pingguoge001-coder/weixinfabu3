"""
Capture absolute screen coordinates for mini program (or other) buttons.

Defaults:
- Keys 1-5 record: more, reenter, search, product, forward
- S prints a YAML snippet
- Q quits

You can override labels and section:
  python test_miniprogram_coords.py --labels "more,reenter,search,product,forward,send" --section miniprogram
"""

import time
import argparse
from typing import Dict, Tuple, Optional

import pyautogui
import keyboard


def find_miniprogram_rect() -> Optional[Tuple[int, int, int, int]]:
    try:
        import win32gui
        import win32process
    except Exception:
        return None

    result_hwnd = None

    def get_process_name(pid: int) -> str:
        try:
            import win32api
            import win32con

            handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False,
                pid,
            )
            try:
                exe_path = win32process.GetModuleFileNameEx(handle, 0)
                return exe_path.split("\\")[-1]
            finally:
                win32api.CloseHandle(handle)
        except Exception:
            return ""

    def callback(hwnd, _):
        nonlocal result_hwnd
        if not win32gui.IsWindowVisible(hwnd):
            return True
        try:
            class_name = win32gui.GetClassName(hwnd)
            if class_name == "Chrome_WidgetWin_0":
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc_name = get_process_name(pid)
                if proc_name.lower() == "wechatappex.exe":
                    result_hwnd = hwnd
                    return False
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except Exception:
        pass

    if result_hwnd:
        return win32gui.GetWindowRect(result_hwnd)
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--labels",
        default="more,reenter,search,product,forward",
        help="Comma-separated labels to map onto keys 1-9 (and 0 for the 10th).",
    )
    parser.add_argument(
        "--section",
        default="miniprogram",
        help="Top-level YAML section name to print. Use empty string to omit.",
    )
    parser.add_argument(
        "--no-restore",
        action="store_true",
        help="Do not print restore_window in YAML output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rect = find_miniprogram_rect()
    if rect:
        left, top, right, bottom = rect
        print(f"Mini program rect: ({left},{top})-({right},{bottom}) size={right-left}x{bottom-top}")
    else:
        print("Mini program rect: not found (still OK for absolute coords).")

    label_list = [label.strip() for label in args.labels.split(",") if label.strip()]
    key_order = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
    labels = {key: label for key, label in zip(key_order, label_list)}
    coords: Dict[str, Tuple[int, int]] = {}
    capture_order = []

    print("Move mouse to target, press key:")
    if labels:
        mapped = "  ".join([f"{k}={v}" for k, v in labels.items()])
        print(f"  {mapped}")
    print("  S=show YAML  Q=quit")

    while True:
        for key, name in labels.items():
            if keyboard.is_pressed(key):
                x, y = pyautogui.position()
                coords[name] = (x, y)
                if name not in capture_order:
                    capture_order.append(name)
                if rect:
                    rel_x = x - rect[0]
                    rel_y = y - rect[1]
                    print(f"{name}: ({x}, {y}) | relative ({rel_x}, {rel_y})")
                else:
                    print(f"{name}: ({x}, {y})")
                time.sleep(0.3)

        if keyboard.is_pressed("s"):
            print("\n--- YAML snippet ---")
            section = args.section.strip()
            indent = "  " if section else ""
            if section:
                print(f"{section}:")
            if rect and not args.no_restore:
                print(f"{indent}restore_window:")
                print(f"{indent}  x: {rect[0]}")
                print(f"{indent}  y: {rect[1]}")
            if coords:
                print(f"{indent}buttons:")
                ordered = [name for name in label_list if name in coords]
                ordered += [name for name in capture_order if name not in ordered]
                for name in ordered:
                    x, y = coords[name]
                    print(f"{indent}  {name}:")
                    print(f"{indent}    absolute_x: {x}")
                    print(f"{indent}    absolute_y: {y}")
            print("--------------------\n")
            time.sleep(0.5)

        if keyboard.is_pressed("q"):
            break

        time.sleep(0.05)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
