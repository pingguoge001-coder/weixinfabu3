"""
小程序操作逐步测试脚本
步骤1: 弹出小程序窗口
步骤2: 点击"更多"按钮
步骤3: 点击"重新进入小程序"
步骤4: 恢复小程序窗口位置
步骤5: 点击搜索按钮
"""
import time
import ctypes
import win32gui
import win32process
import win32con
import psutil
import pyautogui

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

def restore_miniprogram_window(x, y):
    """恢复小程序窗口位置并置顶（不改变大小）"""
    hwnd = find_miniprogram_window()
    if hwnd is None:
        print("❌ 未找到小程序窗口！请先打开花城农夫小程序")
        return False

    try:
        user32 = ctypes.windll.user32

        # 获取当前窗口大小（保持不变）
        rect = win32gui.GetWindowRect(hwnd)
        current_width = rect[2] - rect[0]
        current_height = rect[3] - rect[1]

        # 恢复窗口（如果最小化）
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE

        # 设置窗口位置并置顶（保持原大小）
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,  # 置顶
            x, y, current_width, current_height,
            win32con.SWP_SHOWWINDOW
        )

        # 激活窗口
        user32.SetForegroundWindow(hwnd)

        print(f"✅ 小程序窗口已移动并置顶: 位置({x},{y}), 大小{current_width}x{current_height}（保持不变）")
        return True
    except Exception as e:
        print(f"❌ 恢复小程序窗口失败: {e}")
        return False

def get_miniprogram_window_rect():
    """获取小程序窗口位置和大小"""
    hwnd = find_miniprogram_window()
    if hwnd is None:
        return None
    try:
        rect = win32gui.GetWindowRect(hwnd)
        x, y, x2, y2 = rect
        return (x, y, x2 - x, y2 - y)
    except:
        return None

def click_miniprogram_button(x_offset, y_offset):
    """点击小程序窗口内的按钮"""
    rect = get_miniprogram_window_rect()
    if rect is None:
        print("❌ 未找到小程序窗口")
        return False

    win_x, win_y, _, _ = rect
    click_x = win_x + x_offset
    click_y = win_y + y_offset

    try:
        pyautogui.click(click_x, click_y)  # 小程序按钮坐标
        print(f"✅ 点击位置: ({click_x}, {click_y})")
        return True
    except Exception as e:
        print(f"❌ 点击失败: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("步骤1测试: 弹出小程序窗口")
    print("步骤2测试: 点击'更多'按钮")
    print("=" * 50)
    print()
    print("前提条件: 请确保花城农夫小程序已经打开")
    print()
    input("按回车键开始测试...")
    print()

    # 步骤1: 弹出小程序窗口（只调整位置，不改变大小）
    print("【步骤1】弹出小程序窗口...")
    success = restore_miniprogram_window(x=1493, y=236)
    if not success:
        print("❌ 步骤1失败！")
        exit(1)

    print("等待3秒...")
    time.sleep(3)
    print()

    # 步骤2: 点击"更多"按钮（使用绝对坐标）
    print("【步骤2】点击'更多'按钮（右上角三个点）...")
    more_x, more_y = 2150, 323
    pyautogui.click(more_x, more_y)  # 更多按钮坐标
    print(f"✅ 点击更多按钮: ({more_x}, {more_y})")
    success = True
    if not success:
        print("❌ 步骤2失败！")
        exit(1)

    print("等待3秒...")
    time.sleep(3)
    print()

    # 步骤3: 点击"重新进入小程序"（使用绝对坐标）
    print("【步骤3】点击'重新进入小程序'...")
    reenter_x, reenter_y = 1871, 835
    pyautogui.click(reenter_x, reenter_y)  # 重新进入按钮坐标
    print(f"✅ 点击重新进入小程序: ({reenter_x}, {reenter_y})")
    success = True
    if not success:
        print("❌ 步骤3失败！")
        exit(1)

    print("等待3秒...")
    time.sleep(3)
    print()

    # 步骤4: 恢复小程序窗口位置（只调整位置，不改变大小）
    print("【步骤4】恢复小程序窗口位置...")
    success = restore_miniprogram_window(x=1493, y=236)
    if not success:
        print("❌ 步骤4失败！")
        exit(1)

    print("等待3秒...")
    time.sleep(3)
    print()

    # 步骤5: 点击搜索按钮
    # 使用用户测量的绝对坐标点击搜索按钮
    print("【步骤5】点击搜索按钮...")
    search_x, search_y = 2255, 371
    pyautogui.click(search_x, search_y)  # 搜索按钮坐标
    print(f"✅ 点击搜索按钮: ({search_x}, {search_y})")

    print()
    print("✅ 步骤1-5完成！")
    print("请检查是否打开了搜索框")
