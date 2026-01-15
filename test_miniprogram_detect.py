"""
Detect WeChat mini program window (WeChatAppEx.exe) on Windows.
Prints matched top-level windows with class name and bounds.
"""

import os
import sys
from typing import List, Tuple


def _enum_windows() -> List[Tuple[int, str, str, str, Tuple[int, int, int, int]]]:
    import win32gui
    import win32process

    results = []

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
                return os.path.basename(exe_path)
            finally:
                win32api.CloseHandle(handle)
        except Exception:
            pass

        try:
            import ctypes
            import ctypes.wintypes as wt

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if not handle:
                return ""
            try:
                size = wt.DWORD(260)
                buf = ctypes.create_unicode_buffer(size.value)
                if ctypes.windll.kernel32.QueryFullProcessImageNameW(
                    handle, 0, buf, ctypes.byref(size)
                ):
                    return os.path.basename(buf.value)
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass

        return ""

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        try:
            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd) or ""
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc_name = get_process_name(pid)
            rect = win32gui.GetWindowRect(hwnd)
            results.append((hwnd, class_name, title, proc_name, rect))
        except Exception:
            pass
        return True

    win32gui.EnumWindows(callback, None)
    return results


def main() -> int:
    windows = _enum_windows()
    candidates = [
        w for w in windows
        if w[1] == "Chrome_WidgetWin_0" and w[3].lower() == "wechatappex.exe"
    ]

    print(f"Total windows: {len(windows)}")
    print(f"Mini program candidates: {len(candidates)}")
    for hwnd, class_name, title, proc_name, rect in candidates:
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        print(
            f"hwnd={hwnd} class={class_name} proc={proc_name} "
            f"title={title!r} rect=({left},{top},{right},{bottom}) "
            f"size={width}x{height}"
        )

    if not candidates:
        print("No WeChatAppEx.exe window found.")
        print("Hints:")
        print("- Confirm the mini program window is open on desktop (not minimized).")
        print("- Check if process name differs (e.g. WeChatAppEx.exe case).")
        print("- Try running this script as admin if window enumeration is restricted.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
