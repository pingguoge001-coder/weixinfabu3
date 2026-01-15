# -*- coding: utf-8 -*-
"""
完整评论流程测试：点击 "..." -> 点击 "评论" -> 直接粘贴产品链接 -> 发送
"""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

import pyautogui
import pyperclip
import uiautomation as auto

SNS_WINDOW_CLASS = "mmui::SNSWindow"
TEMPLATE_DIR = Path(__file__).parent / "data" / "templates"

# 测试产品链接
TEST_PRODUCT_LINK = "https://test.example.com/product/12345"


def test_comment_flow():
    """完整评论流程测试"""

    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("未找到朋友圈窗口")
        return False

    rect = sns_window.BoundingRectangle
    win_width = rect.right - rect.left
    win_height = rect.bottom - rect.top

    print(f"窗口: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")
    print(f"大小: {win_width} x {win_height}")

    # ========== Step 1: 点击 "..." 按钮 ==========
    print("\n" + "=" * 50)
    print("Step 1: 点击 '...' 按钮")
    print("=" * 50)

    template_path = TEMPLATE_DIR / "comment_btn.png"
    if not template_path.exists():
        print(f"模板不存在: {template_path}")
        return False

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
        return False

    dots_center = pyautogui.center(loc)
    click_x = dots_center.x
    click_y = dots_center.y + 25  # Y偏移修正

    print(f"点击位置: ({click_x}, {click_y})")
    pyautogui.click(click_x, click_y)
    print("已点击 '...' 按钮")

    # 等待菜单弹出
    time.sleep(0.5)

    # ========== Step 2: 点击 "评论" 按钮 ==========
    print("\n" + "=" * 50)
    print("Step 2: 点击 '评论' 按钮")
    print("=" * 50)

    # 尝试 UI 自动化查找
    comment_btn = sns_window.TextControl(searchDepth=20, Name="评论")
    if comment_btn.Exists(2, 0):
        print("通过 TextControl 找到 '评论' 按钮")
        comment_btn.Click()
        print("已点击!")
    else:
        # 尝试 ButtonControl
        comment_btn = sns_window.ButtonControl(searchDepth=20, Name="评论")
        if comment_btn.Exists(1, 0):
            print("通过 ButtonControl 找到 '评论' 按钮")
            comment_btn.Click()
            print("已点击!")
        else:
            # 坐标后备
            print("UI 自动化未找到，使用坐标定位...")
            comment_x = click_x - 90
            comment_y = click_y
            pyautogui.click(comment_x, comment_y)
            print(f"已点击坐标: ({comment_x}, {comment_y})")

    time.sleep(0.8)

    # ========== Step 3: 直接粘贴产品链接 ==========
    print("\n" + "=" * 50)
    print("Step 3: 直接粘贴产品链接（光标已在输入框中）")
    print("=" * 50)

    pyperclip.copy(TEST_PRODUCT_LINK)
    time.sleep(0.2)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.8)
    print(f"已粘贴: {TEST_PRODUCT_LINK}")

    # ========== Step 4: 点击发送 ==========
    print("\n" + "=" * 50)
    print("Step 4: 点击 '发送' 按钮")
    print("=" * 50)

    # 图像识别发送按钮
    send_template = TEMPLATE_DIR / "send_btn.png"
    send_clicked = False
    if send_template.exists():
        print("尝试图像识别...")
        loc = pyautogui.locateOnScreen(str(send_template), confidence=0.8)
        if loc:
            center = pyautogui.center(loc)
            print(f"找到发送按钮: ({center.x}, {center.y})")
            pyautogui.click(center.x, center.y)
            print("已点击!")
            send_clicked = True

    if not send_clicked:
        # 后备: 相对坐标定位
        print("使用相对坐标定位...")
        send_x = rect.right - 80
        send_y = rect.top + int(win_height * 0.52)
        print(f"计算坐标: ({send_x}, {send_y})")
        pyautogui.click(send_x, send_y)
        print("已点击!")

    # ========== Step 5: 关闭窗口 ==========
    print("\n" + "=" * 50)
    print("Step 5: 关闭朋友圈窗口")
    print("=" * 50)

    time.sleep(1)  # 等待评论发送完成

    # 点击右上角关闭按钮 (×) - 最右边的按钮
    close_x = rect.right - 15
    close_y = rect.top + 15
    print(f"点击关闭按钮: ({close_x}, {close_y})")
    pyautogui.click(close_x, close_y)
    print("已点击!")

    print("\n" + "=" * 50)
    print("流程完成!")
    print("=" * 50)

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("完整评论流程测试")
    print("=" * 60)
    print(f"\n测试链接: {TEST_PRODUCT_LINK}")
    print("\n请确保已打开朋友圈详情页面")

    print("\n3秒后开始...")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    test_comment_flow()
