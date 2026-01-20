# -*- coding: utf-8 -*-
"""
测试点击评论按钮（...按钮）的坐标
"""
import uiautomation as auto
import pyautogui
import time
import sys

SNS_WINDOW_CLASS = "mmui::SNSWindow"

def test_click_comment(offset_x, offset_y):
    """
    测试点击评论按钮
    offset_x: 相对于窗口右边的偏移（负数）
    offset_y: 相对于窗口顶部的偏移（正数）
    """
    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("Not found SNS window")
        return

    rect = sns_window.BoundingRectangle
    print(f"Window: ({rect.left},{rect.top}) - ({rect.right},{rect.bottom})")

    # 计算点击位置
    click_x = rect.right + offset_x  # offset_x 是负数
    click_y = rect.top + offset_y

    print(f"\nClick position: ({click_x}, {click_y})")
    print(f"Offset: right{offset_x}, top+{offset_y}")

    # 3秒倒计时
    for i in range(3, 0, -1):
        print(f"Clicking in {i}...")
        time.sleep(1)

    pyautogui.click(click_x, click_y)  # 评论按钮坐标
    print("Clicked!")

if __name__ == "__main__":
    # 默认偏移：根据截图估计，"..."按钮在右下角
    # 距离右边约 50px，距离顶部约 630px（在详情页中）
    offset_x = -50
    offset_y = 630

    if len(sys.argv) >= 3:
        offset_x = int(sys.argv[1])
        offset_y = int(sys.argv[2])

    print("Test: Click Comment Button (...)")
    print("=" * 60)
    print(f"Offset: right{offset_x}, top+{offset_y}")
    print()
    test_click_comment(offset_x, offset_y)
