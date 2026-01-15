# -*- coding: utf-8 -*-
"""
连续操作：点击 "..." -> 点击 "评论"
"""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

import pyautogui
import uiautomation as auto

SNS_WINDOW_CLASS = "mmui::SNSWindow"
TEMPLATE_DIR = Path(__file__).parent / "data" / "templates"


def click_dots_then_comment():
    """点击 ... 然后点击评论"""

    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("未找到朋友圈窗口")
        return

    rect = sns_window.BoundingRectangle
    win_width = rect.right - rect.left
    win_height = rect.bottom - rect.top

    print(f"窗口: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

    # Step 1: 点击 "..." 按钮
    print("\nStep 1: 点击 '...' 按钮")
    template_path = TEMPLATE_DIR / "comment_btn.png"

    if not template_path.exists():
        print(f"模板不存在: {template_path}")
        return

    # 限定搜索区域
    search_region = (
        rect.left + win_width // 2,
        rect.top + 300,
        win_width // 2 - 20,
        win_height - 500
    )

    loc = pyautogui.locateOnScreen(str(template_path), region=search_region, confidence=0.4)

    if not loc:
        print("未找到 '...' 按钮")
        return

    dots_center = pyautogui.center(loc)
    click_x = dots_center.x
    click_y = dots_center.y + 25  # Y偏移修正

    print(f"点击位置: ({click_x}, {click_y})")
    pyautogui.click(click_x, click_y)
    print("已点击 '...' 按钮")

    # 等待菜单弹出
    time.sleep(0.5)

    # Step 2: 查找并点击"评论"按钮
    print("\nStep 2: 查找并点击 '评论' 按钮")

    # 尝试 UI 自动化查找
    comment_btn = sns_window.TextControl(searchDepth=20, Name="评论")
    if comment_btn.Exists(2, 0):
        print("通过 UI 自动化找到 '评论' 按钮")
        comment_btn.Click()
        print("已点击!")
        return True

    # 尝试 ButtonControl
    comment_btn = sns_window.ButtonControl(searchDepth=20, Name="评论")
    if comment_btn.Exists(1, 0):
        print("通过 ButtonControl 找到 '评论' 按钮")
        comment_btn.Click()
        print("已点击!")
        return True

    # UI 自动化失败，尝试坐标定位
    # "评论" 按钮应该在 "..." 按钮的左边
    print("UI 自动化未找到，尝试坐标定位...")

    # 根据截图，"评论"按钮在 "..." 左边大约 80-100 像素
    comment_x = click_x - 90
    comment_y = click_y

    print(f"尝试点击坐标: ({comment_x}, {comment_y})")
    pyautogui.click(comment_x, comment_y)
    print("已点击!")

    return True


if __name__ == "__main__":
    print("=" * 50)
    print("连续操作: 点击 '...' -> 点击 '评论'")
    print("=" * 50)

    print("\n3秒后开始...")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    click_dots_then_comment()
