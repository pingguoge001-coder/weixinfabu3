"""
小程序转发流程测试脚本
前提：搜索框已打开（运行 test_miniprogram_step.py 后）

步骤6: 输入产品编号 F006
步骤7: 按 Enter 搜索
步骤8: 点击产品链接
步骤9: 点击转发按钮
步骤10: 输入群名"朋友圈内容"
步骤11: 点击群聊选项
步骤12: 点击发送按钮
"""
import time
import ctypes
import win32gui
import win32process
import win32con
import psutil
import pyautogui
import pyperclip

pyautogui.FAILSAFE = False

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
        print("❌ 未找到小程序窗口！")
        return False

    try:
        user32 = ctypes.windll.user32
        rect = win32gui.GetWindowRect(hwnd)
        current_width = rect[2] - rect[0]
        current_height = rect[3] - rect[1]

        user32.ShowWindow(hwnd, 9)
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            x, y, current_width, current_height,
            win32con.SWP_SHOWWINDOW
        )
        user32.SetForegroundWindow(hwnd)
        print(f"✅ 小程序窗口已激活: 位置({x},{y})")
        return True
    except Exception as e:
        print(f"❌ 恢复小程序窗口失败: {e}")
        return False

def find_forward_dialog():
    """查找微信转发对话框"""
    result_hwnd = None

    def callback(hwnd, _):
        nonlocal result_hwnd
        if win32gui.IsWindowVisible(hwnd):
            try:
                title = win32gui.GetWindowText(hwnd)
                if '发送给' in title or '转发' in title:
                    result_hwnd = hwnd
                    return False
            except:
                pass
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except:
        pass

    return result_hwnd

if __name__ == "__main__":
    print("=" * 50)
    print("小程序转发流程测试")
    print("前提：已运行 test_miniprogram_step.py，搜索框已打开")
    print("=" * 50)
    print()
    input("按回车键开始测试...")
    print()

    # 步骤6: 输入产品编号
    print("【步骤6】输入产品编号 F006...")
    pyperclip.copy("F006")
    time.sleep(0.5)
    pyautogui.hotkey('ctrl', 'v')
    print("✅ 已输入产品编号: F006")
    print("等待3秒...")
    time.sleep(3)
    print()

    # 步骤7: 按 Enter 搜索
    print("【步骤7】按 Enter 搜索...")
    pyautogui.press('enter')
    print("✅ 已按 Enter")
    print("等待3秒...")
    time.sleep(3)
    print()

    # 步骤7.1: 重新激活小程序窗口
    print("【步骤7.1】重新激活小程序窗口...")
    restore_miniprogram_window(x=1493, y=236)
    print("等待1秒...")
    time.sleep(1)
    print()

    # 步骤8: 点击产品链接
    print("【步骤8】点击产品链接...")
    product_x, product_y = 1950, 554
    pyautogui.click(product_x, product_y)
    print(f"✅ 点击产品链接: ({product_x}, {product_y})")
    print("等待3秒...")
    time.sleep(3)
    print()

    # 步骤9: 点击转发按钮
    print("【步骤9】点击转发按钮...")
    forward_x, forward_y = 2177, 1110
    pyautogui.click(forward_x, forward_y)
    print(f"✅ 点击转发按钮: ({forward_x}, {forward_y})")
    print("等待3秒...")
    time.sleep(3)
    print()

    # 步骤10: 在转发对话框中输入群名
    print("【步骤10】输入群名'朋友圈内容'...")
    hwnd = find_forward_dialog()
    if hwnd:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.5)
    pyperclip.copy("朋友圈内容")
    time.sleep(0.5)
    pyautogui.hotkey('ctrl', 'v')
    print("✅ 已输入群名: 朋友圈内容")
    print("等待3秒...")
    time.sleep(3)
    print()

    # 步骤11: 点击群聊选项
    print("【步骤11】点击群聊选项...")
    hwnd = find_forward_dialog()
    if hwnd:
        rect = win32gui.GetWindowRect(hwnd)
        dialog_x, dialog_y = rect[0], rect[1]
        group_x = dialog_x + 150
        group_y = dialog_y + 180
        pyautogui.click(group_x, group_y)
        print(f"✅ 点击群聊选项: ({group_x}, {group_y})")
    else:
        print("❌ 未找到转发对话框")
    print("等待3秒...")
    time.sleep(3)
    print()

    # 步骤12: 点击发送按钮
    print("【步骤12】点击发送按钮...")
    hwnd = find_forward_dialog()
    if hwnd:
        rect = win32gui.GetWindowRect(hwnd)
        dialog_x, dialog_y = rect[0], rect[1]
        send_x = dialog_x + 663
        send_y = dialog_y + 778
        pyautogui.click(send_x, send_y)
        print(f"✅ 点击发送按钮: ({send_x}, {send_y})")
    else:
        print("❌ 未找到转发对话框")
    print()

    print("=" * 50)
    print("✅ 转发流程测试完成！")
    print("请检查是否成功转发到群聊'朋友圈内容'")
    print("=" * 50)
