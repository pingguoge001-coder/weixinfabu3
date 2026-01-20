# -*- coding: utf-8 -*-
"""
测试完整流程：点击头像 -> 点击朋友圈 -> 点击第一条朋友圈
"""
import uiautomation as auto
import pyautogui
import time

SNS_WINDOW_CLASS = "mmui::SNSWindow"

def test_click_first_moment():
    """
    完整流程：
    1. 点击头像
    2. 点击"朋友圈"区域
    3. 点击第一条朋友圈 (mmui::AlbumContentCell)
    """
    # 1. 找到朋友圈窗口
    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("Not found SNS window")
        return

    rect = sns_window.BoundingRectangle
    print(f"SNS Window: ({rect.left},{rect.top}) - ({rect.right},{rect.bottom})")

    # 2. 点击头像
    avatar_x = rect.right - 110
    avatar_y = rect.top + 400
    print(f"\nStep 1: Click avatar at ({avatar_x}, {avatar_y})")
    pyautogui.click(avatar_x, avatar_y)  # 头像坐标
    print("Avatar clicked!")

    # 3. 等待弹窗
    print("\nWaiting 2 seconds...")
    time.sleep(2)

    # 4. 点击"朋友圈"区域
    moment_x = avatar_x + 400
    moment_y = avatar_y + 200
    print(f"\nStep 2: Click moment link at ({moment_x}, {moment_y})")
    pyautogui.click(moment_x, moment_y)  # 朋友圈入口坐标
    print("Moment link clicked!")

    # 5. 等待页面加载
    print("\nWaiting 3 seconds for page load...")
    time.sleep(3)

    # 6. 查找并点击第一条朋友圈
    print("\nStep 3: Find and click first moment (mmui::AlbumContentCell)...")

    # 重新获取窗口
    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(1, 0):
        print("SNS window lost")
        return

    # 查找 mmui::AlbumContentCell
    first_moment = sns_window.ListItemControl(
        searchDepth=15,
        ClassName="mmui::AlbumContentCell"
    )

    if first_moment.Exists(5, 1):
        ctrl_rect = first_moment.BoundingRectangle
        print(f"Found first moment: ({ctrl_rect.left},{ctrl_rect.top}) - ({ctrl_rect.right},{ctrl_rect.bottom})")

        # 点击
        first_moment.Click()
        print("First moment clicked!")
    else:
        print("First moment element not found!")

        # 尝试查找其他可能的元素
        print("\nTrying alternative: mmui::AlbumBaseCell...")
        alt_moment = sns_window.ListItemControl(
            searchDepth=15,
            ClassName="mmui::AlbumBaseCell"
        )

        if alt_moment.Exists(3, 1):
            ctrl_rect = alt_moment.BoundingRectangle
            print(f"Found: ({ctrl_rect.left},{ctrl_rect.top}) - ({ctrl_rect.right},{ctrl_rect.bottom})")
            alt_moment.Click()
            print("Clicked!")
        else:
            print("Alternative element not found either.")

if __name__ == "__main__":
    print("Test: Click First Moment via Element")
    print("=" * 60)
    test_click_first_moment()
