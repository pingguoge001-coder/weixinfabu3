import pyautogui
import time
import win32gui
import win32con
import sys

sys.stdout.reconfigure(encoding='utf-8')
pyautogui.FAILSAFE = False

def find_forward_dialog():
    """查找微信转发对话框"""
    target_hwnd = None
    def callback(hwnd, extra):
        nonlocal target_hwnd
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if '发送给' in title or '转发' in title:
                target_hwnd = hwnd
                print(f'找到窗口: {title}')
        return True
    win32gui.EnumWindows(callback, None)
    return target_hwnd

hwnd = find_forward_dialog()
if hwnd:
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.2)

    rect = win32gui.GetWindowRect(hwnd)
    x, y, right, bottom = rect
    width = right - x
    height = bottom - y
    print(f'转发对话框位置: ({x}, {y}), 大小: {width}x{height}')

    # 尝试用图像识别找绿色发送按钮
    # 如果失败，使用固定偏移量
    # 发送按钮应该在左侧面板底部中央
    # 左侧面板大约400像素宽，按钮居中
    send_x = x + 200  # 左侧面板中央偏左
    send_y = y + height - 22  # 非常接近底部

    print(f'尝试点击发送按钮: ({send_x}, {send_y})')

    # 先移动看位置
    pyautogui.moveTo(send_x, send_y)
    time.sleep(0.3)
    pyautogui.screenshot('data/screenshots/send_pos_check.png')

    # 然后点击
    pyautogui.click(send_x, send_y)
    print('已点击')

    time.sleep(1)
    pyautogui.screenshot('data/screenshots/after_send2.png')
    print('点击后截图完成')
else:
    print('未找到转发对话框')
