"""
Print the mini program window rectangle (left, top, right, bottom).
"""

import os


def get_process_name(pid: int) -> str:
    try:
        import win32api
        import win32con
        import win32process

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


def find_miniprogram_rect():
    import win32gui
    import win32process

    result = None

    def callback(hwnd, _):
        nonlocal result
        if not win32gui.IsWindowVisible(hwnd):
            return True
        try:
            class_name = win32gui.GetClassName(hwnd)
            if class_name != "Chrome_WidgetWin_0":
                return True
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc_name = get_process_name(pid)
            if proc_name.lower() == "wechatappex.exe":
                result = win32gui.GetWindowRect(hwnd)
                return False
        except Exception:
            pass
        return True

    win32gui.EnumWindows(callback, None)
    return result


def main() -> int:
    rect = find_miniprogram_rect()
    if not rect:
        print("Mini program window not found.")
        return 1

    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    print(f"left={left} top={top} right={right} bottom={bottom} size={width}x{height}")
    print(f"restore_window: x={left} y={top}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
