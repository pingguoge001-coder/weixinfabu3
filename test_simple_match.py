# -*- coding: utf-8 -*-
"""
简单图像识别测试
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pyautogui
import uiautomation as auto
from PIL import Image

SNS_WINDOW_CLASS = "mmui::SNSWindow"
TEMPLATE_DIR = Path(__file__).parent / "data" / "templates"


def simple_test():
    template_path = TEMPLATE_DIR / "comment_btn.png"

    print(f"模板路径: {template_path}")
    print(f"模板存在: {template_path.exists()}")

    if template_path.exists():
        img = Image.open(template_path)
        print(f"模板尺寸: {img.size}")
        print(f"模板模式: {img.mode}")

    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("未找到朋友圈窗口")
        return

    rect = sns_window.BoundingRectangle
    print(f"\n窗口: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

    # 不使用 region，在全屏搜索
    print("\n测试1: 全屏搜索 (confidence=0.6)")
    try:
        loc = pyautogui.locateOnScreen(str(template_path), confidence=0.6)
        if loc:
            center = pyautogui.center(loc)
            print(f"  找到! 位置=({center.x}, {center.y})")

            # 检查是否在窗口内
            if rect.left <= center.x <= rect.right and rect.top <= center.y <= rect.bottom:
                print(f"  位置在窗口内 ✓")
            else:
                print(f"  位置在窗口外 ✗")
        else:
            print("  未找到")
    except Exception as e:
        print(f"  出错: {type(e).__name__}: {e}")

    # 使用 region
    search_region = (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    print(f"\n测试2: 窗口区域搜索 (confidence=0.6)")
    print(f"  region={search_region}")
    try:
        loc = pyautogui.locateOnScreen(str(template_path), region=search_region, confidence=0.6)
        if loc:
            center = pyautogui.center(loc)
            print(f"  找到! 位置=({center.x}, {center.y})")
        else:
            print("  未找到")
    except Exception as e:
        print(f"  出错: {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("简单图像识别测试")
    print("=" * 50)
    simple_test()
