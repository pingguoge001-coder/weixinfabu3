# -*- coding: utf-8 -*-
"""
在特定区域搜索按钮
"""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

import pyautogui
import uiautomation as auto
from PIL import Image, ImageDraw
from datetime import datetime

SNS_WINDOW_CLASS = "mmui::SNSWindow"
TEMPLATE_DIR = Path(__file__).parent / "data" / "templates"


def test_areas():
    """测试在不同区域搜索"""
    template_path = TEMPLATE_DIR / "comment_btn.png"

    if not template_path.exists():
        print(f"模板不存在")
        return

    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("未找到朋友圈窗口")
        return

    rect = sns_window.BoundingRectangle
    win_width = rect.right - rect.left
    win_height = rect.bottom - rect.top

    print(f"窗口: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")
    print(f"窗口尺寸: {win_width} x {win_height}")

    # 截图用于标记
    screenshot = pyautogui.screenshot()
    draw = ImageDraw.Draw(screenshot)

    # 定义多个搜索区域
    # "..." 按钮应该在内容区域的右侧
    areas = [
        {
            "name": "右下1/4",
            "region": (
                rect.left + win_width // 2,  # 右半边
                rect.top + win_height // 2,  # 下半边
                win_width // 2,
                win_height // 2
            )
        },
        {
            "name": "右侧中间",
            "region": (
                rect.left + win_width * 2 // 3,  # 右1/3
                rect.top + win_height // 4,      # 从1/4开始
                win_width // 3,
                win_height // 2
            )
        },
        {
            "name": "中间区域",
            "region": (
                rect.left + win_width // 4,
                rect.top + win_height // 4,
                win_width // 2,
                win_height // 2
            )
        },
    ]

    colors = ["red", "green", "blue"]

    print("\n搜索不同区域:")
    print("-" * 50)

    for i, area in enumerate(areas):
        region = area["region"]
        color = colors[i % len(colors)]

        # 画区域边框
        draw.rectangle(
            [region[0], region[1], region[0] + region[2], region[1] + region[3]],
            outline=color, width=2
        )

        try:
            loc = pyautogui.locateOnScreen(
                str(template_path),
                region=region,
                confidence=0.6
            )

            if loc:
                center = pyautogui.center(loc)
                print(f"{area['name']} ({color}): 找到! 位置=({center.x}, {center.y})")

                # 画找到的位置
                draw.rectangle(
                    [loc.left, loc.top, loc.left + loc.width, loc.top + loc.height],
                    outline=color, width=3
                )
                # 画十字
                draw.line([(center.x - 15, center.y), (center.x + 15, center.y)], fill=color, width=2)
                draw.line([(center.x, center.y - 15), (center.x, center.y + 15)], fill=color, width=2)
            else:
                print(f"{area['name']} ({color}): 未找到")

        except Exception as e:
            print(f"{area['name']} ({color}): 出错 - {e}")

    # 保存截图
    timestamp = datetime.now().strftime("%H%M%S")
    debug_path = Path(__file__).parent / "screenshots" / f"areas_{timestamp}.png"
    debug_path.parent.mkdir(exist_ok=True)
    screenshot.save(debug_path)
    print(f"\n截图已保存: {debug_path}")


if __name__ == "__main__":
    print("=" * 50)
    print("区域搜索测试")
    print("=" * 50)
    test_areas()
