# -*- coding: utf-8 -*-
"""
获取鼠标位置 - 用于定位 "..." 按钮
按空格键记录当前鼠标位置
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import time
import pyautogui
import uiautomation as auto
import keyboard

SNS_WINDOW_CLASS = "mmui::SNSWindow"


def get_mouse_position():
    """获取鼠标位置 - 按空格键记录"""

    # 获取窗口信息
    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if sns_window.Exists(3, 1):
        rect = sns_window.BoundingRectangle
        print(f"[INFO] Window: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")
        print(f"[INFO] Window size: {rect.right - rect.left} x {rect.bottom - rect.top}")
    else:
        print("[WARN] SNS window not found")
        rect = None

    print("\n" + "=" * 50)
    print("Move mouse to '...' button, then press SPACE")
    print("Press 'q' to quit")
    print("=" * 50 + "\n")

    while True:
        if keyboard.is_pressed('space'):
            x, y = pyautogui.position()
            print(f"\n>>> Mouse position: ({x}, {y})")

            if rect:
                rel_x = x - rect.left
                rel_y = y - rect.top
                offset_right = rect.right - x
                offset_top = y - rect.top
                print(f"    Relative to window top-left: ({rel_x}, {rel_y})")
                print(f"    Distance from right edge: {offset_right} px")
                print(f"    Distance from top edge: {offset_top} px")

                # 检查是否在窗口内
                if rect.left <= x <= rect.right and rect.top <= y <= rect.bottom:
                    print("    [OK] Position is INSIDE window")
                else:
                    print("    [WARN] Position is OUTSIDE window!")

            time.sleep(0.5)  # 防止重复触发

        if keyboard.is_pressed('q'):
            print("\nQuit.")
            break

        time.sleep(0.05)


if __name__ == "__main__":
    print("=" * 50)
    print("Mouse Position Tool")
    print("=" * 50)
    get_mouse_position()
