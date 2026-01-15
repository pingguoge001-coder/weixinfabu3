"""
获取当前小程序窗口的大小
"""
import win32gui
import win32process
import psutil

def find_miniprogram_window():
    """查找小程序窗口"""
    result_hwnd = None

    def callback(hwnd, _):
        nonlocal result_hwnd
        if win32gui.IsWindowVisible(hwnd):
            try:
                class_name = win32gui.GetClassName(hwnd)
                if class_name == "Chrome_WidgetWin_0":
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        proc = psutil.Process(pid)
                        if proc.name().lower() == "wechatappex.exe":
                            result_hwnd = hwnd
                            return False
                    except:
                        pass
            except:
                pass
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except:
        pass

    return result_hwnd

if __name__ == "__main__":
    print("获取当前小程序窗口大小")
    print("=" * 50)

    hwnd = find_miniprogram_window()
    if hwnd is None:
        print("❌ 未找到小程序窗口！请先打开花城农夫小程序")
    else:
        rect = win32gui.GetWindowRect(hwnd)
        x, y, x2, y2 = rect
        width = x2 - x
        height = y2 - y

        print(f"窗口句柄: {hwnd}")
        print(f"位置: x={x}, y={y}")
        print(f"大小: width={width}, height={height}")
        print()
        print("请把这个大小记录下来，以后固定使用")
