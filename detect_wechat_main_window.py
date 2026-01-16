# -*- coding: utf-8 -*-
"""Detect WeChat main window and optionally restore it from minimized state."""
import sys
import io
import os
import argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import win32api
import win32con
import win32gui
import win32process


TARGET_PROCESS_NAMES = {"weixin.exe", "wechat.exe"}


def get_process_name(pid):
    try:
        handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
            False,
            pid,
        )
    except Exception:
        return ""
    try:
        path = win32process.GetModuleFileNameEx(handle, 0)
        return os.path.basename(path)
    except Exception:
        return ""
    finally:
        try:
            win32api.CloseHandle(handle)
        except Exception:
            pass


def enum_windows():
    windows = []

    def callback(hwnd, _):
        if not win32gui.IsWindow(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd) or ""
        class_name = win32gui.GetClassName(hwnd) or ""
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc_name = get_process_name(pid)
        windows.append(
            {
                "hwnd": hwnd,
                "title": title,
                "class": class_name,
                "pid": pid,
                "process": proc_name,
                "visible": bool(win32gui.IsWindowVisible(hwnd)),
                "iconic": bool(win32gui.IsIconic(hwnd)),
            }
        )
        return True

    win32gui.EnumWindows(callback, None)
    return windows


def score_wechat_window(item, class_hint):
    score = 0
    proc = (item["process"] or "").lower()
    if proc in TARGET_PROCESS_NAMES:
        score += 5
    if class_hint and item["class"] == class_hint:
        score += 3
    if item["class"].startswith("Qt"):
        score += 1
    if item["title"]:
        score += 1
    if item["visible"]:
        score += 1
    return score


def pick_wechat_window(windows, class_hint):
    best = None
    best_score = -1
    for item in windows:
        score = score_wechat_window(item, class_hint)
        if score > best_score:
            best = item
            best_score = score
    return best, best_score


def restore_window(hwnd):
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.BringWindowToTop(hwnd)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        return True
    except Exception as exc:
        print(f"Restore failed: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--class-name",
        default="Qt51514QWindowIcon",
        help="Preferred class name for WeChat main window.",
    )
    parser.add_argument(
        "--no-restore",
        action="store_true",
        help="Only detect, do not restore window.",
    )
    args = parser.parse_args()

    windows = enum_windows()
    wechat, score = pick_wechat_window(windows, args.class_name)

    print("=" * 70)
    print("WeChat Main Window Detection")
    print("=" * 70)
    print(f"Total windows: {len(windows)}")

    if not wechat or score <= 0:
        print("WeChat window not found.")
        return 1

    print("\nCandidate:")
    print(f"  hwnd: {wechat['hwnd']}")
    print(f"  process: {wechat['process']} (pid={wechat['pid']})")
    print(f"  class: {wechat['class']}")
    print(f"  title: {wechat['title'] or '(empty)'}")
    print(f"  visible: {wechat['visible']}")
    print(f"  minimized: {wechat['iconic']}")

    if args.no_restore:
        return 0

    if wechat["iconic"] or not wechat["visible"]:
        print("\nRestoring window...")
        ok = restore_window(wechat["hwnd"])
        print("Restore OK" if ok else "Restore failed")
    else:
        print("\nWindow already visible.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
