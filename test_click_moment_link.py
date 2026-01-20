# -*- coding: utf-8 -*-
"""
测试点击头像后，再点击弹窗中"朋友圈"区域
"""
import uiautomation as auto
import pyautogui
import time
import sys

SNS_WINDOW_CLASS = "mmui::SNSWindow"

def test_full_flow(moment_offset_x, moment_offset_y):
    """
    完整流程：
    1. 找到朋友圈窗口
    2. 点击头像 (right-110, top+400)
    3. 等待弹窗出现
    4. 点击"朋友圈"区域
    """
    # 1. 找到朋友圈窗口
    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("Not found SNS window")
        return

    rect = sns_window.BoundingRectangle
    print(f"SNS Window: ({rect.left},{rect.top}) - ({rect.right},{rect.bottom})")

    # 2. 点击头像 (已测试确定的坐标)
    avatar_x = rect.right - 110
    avatar_y = rect.top + 400
    print(f"\nStep 1: Click avatar at ({avatar_x}, {avatar_y})")

    pyautogui.click(avatar_x, avatar_y)  # 头像坐标
    print("Avatar clicked!")

    # 3. 等待弹窗出现
    print("\nWaiting 2 seconds for popup...")
    time.sleep(2)

    # 4. 点击"朋友圈"区域
    # 弹窗会出现在头像附近，使用相对于头像位置的偏移
    moment_x = avatar_x + moment_offset_x
    moment_y = avatar_y + moment_offset_y

    print(f"\nStep 2: Click moment link at ({moment_x}, {moment_y})")
    print(f"  (Avatar position + offset: {moment_offset_x}, {moment_offset_y})")

    for i in range(3, 0, -1):
        print(f"Clicking in {i}...")
        time.sleep(1)

    pyautogui.click(moment_x, moment_y)  # 朋友圈入口坐标
    print("Moment link clicked!")

if __name__ == "__main__":
    # 默认偏移：相对于头像位置
    # 根据截图，弹窗中"朋友圈"区域大约在头像右边偏下
    offset_x = 50   # 相对头像 X 偏移
    offset_y = 60   # 相对头像 Y 偏移

    if len(sys.argv) >= 3:
        offset_x = int(sys.argv[1])
        offset_y = int(sys.argv[2])

    print("Test: Click Avatar -> Click Moment Link")
    print("=" * 60)
    print(f"Moment link offset from avatar: ({offset_x}, {offset_y})")
    print()

    test_full_flow(offset_x, offset_y)
