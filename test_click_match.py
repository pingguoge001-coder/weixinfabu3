# -*- coding: utf-8 -*-
"""
测试点击图像识别到的位置
"""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

import pyautogui
import uiautomation as auto

SNS_WINDOW_CLASS = "mmui::SNSWindow"
TEMPLATE_DIR = Path(__file__).parent / "data" / "templates"


def test_click():
    template_path = TEMPLATE_DIR / "comment_btn.png"

    if not template_path.exists():
        print(f"模板不存在: {template_path}")
        return

    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("未找到朋友圈窗口")
        return

    rect = sns_window.BoundingRectangle
    search_region = (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)

    print("正在搜索...")
    loc = pyautogui.locateOnScreen(str(template_path), region=search_region, confidence=0.6)

    if not loc:
        print("未找到匹配")
        return

    center = pyautogui.center(loc)
    print(f"找到位置: ({center.x}, {center.y})")
    print(f"匹配区域: ({loc.left}, {loc.top}) - ({loc.left + loc.width}, {loc.top + loc.height})")

    print("\n3秒后点击...")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    pyautogui.click(center.x, center.y)  # 匹配中心坐标
    print("已点击!")


if __name__ == "__main__":
    print("=" * 50)
    print("测试点击图像识别位置")
    print("=" * 50)
    test_click()
