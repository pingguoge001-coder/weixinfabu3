# -*- coding: utf-8 -*-
"""
扫描不同 confidence 值测试图像识别
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pyautogui
import uiautomation as auto

SNS_WINDOW_CLASS = "mmui::SNSWindow"
TEMPLATE_DIR = Path(__file__).parent / "data" / "templates"


def scan_confidence():
    """扫描不同 confidence 值"""

    template_path = TEMPLATE_DIR / "comment_btn.png"

    if not template_path.exists():
        print(f"模板图片不存在: {template_path}")
        return

    from PIL import Image
    img = Image.open(template_path)
    print(f"模板图片尺寸: {img.size}")

    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("未找到朋友圈窗口")
        return

    rect = sns_window.BoundingRectangle
    print(f"窗口位置: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

    search_region = (
        rect.left, rect.top,
        rect.right - rect.left, rect.bottom - rect.top
    )

    print("\n扫描不同 confidence 值:")
    print("-" * 50)

    for conf in [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]:
        try:
            location = pyautogui.locateOnScreen(
                str(template_path),
                region=search_region,
                confidence=conf
            )

            if location:
                center = pyautogui.center(location)
                print(f"confidence={conf}: 成功! 位置=({center.x}, {center.y}), 尺寸={location.width}x{location.height}")
            else:
                print(f"confidence={conf}: 失败")
        except Exception as e:
            print(f"confidence={conf}: 出错 - {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("扫描 Confidence 值")
    print("=" * 60)
    scan_confidence()
