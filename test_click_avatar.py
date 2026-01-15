# -*- coding: utf-8 -*-
"""
测试点击头像位置
运行后会在指定位置点击，观察是否点中头像
"""
import uiautomation as auto
import pyautogui
import time

SNS_WINDOW_CLASS = "mmui::SNSWindow"

def test_click(offset_x, offset_y):
    """测试点击指定偏移位置"""
    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)

    if not sns_window.Exists(3, 1):
        print("Not found SNS window")
        return

    rect = sns_window.BoundingRectangle
    print(f"Window: ({rect.left},{rect.top}) - ({rect.right},{rect.bottom})")

    # 计算点击位置
    click_x = rect.right + offset_x  # offset_x 是负数，表示距离右边
    click_y = rect.top + offset_y    # offset_y 是正数，表示距离顶部

    print(f"Click position: ({click_x}, {click_y})")
    print(f"Offset: right{offset_x}, top+{offset_y}")
    print()

    # 3秒倒计时
    for i in range(3, 0, -1):
        print(f"Clicking in {i}...")
        time.sleep(1)

    # 点击
    pyautogui.click(click_x, click_y)
    print("Clicked!")

if __name__ == "__main__":
    import sys

    # 默认偏移：距离右边 90px，距离顶部 200px
    offset_x = -90
    offset_y = 200

    if len(sys.argv) >= 3:
        offset_x = int(sys.argv[1])
        offset_y = int(sys.argv[2])

    print(f"Test click at offset: right{offset_x}, top+{offset_y}")
    print("=" * 60)
    test_click(offset_x, offset_y)
