# -*- coding: utf-8 -*-
"""
在限定区域搜索 - 只搜索内容区域，排除标题栏
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


def restricted_search():
    """在限定区域搜索"""
    template_path = TEMPLATE_DIR / "comment_btn.png"

    if not template_path.exists():
        print(f"模板不存在")
        return

    img = Image.open(template_path)
    print(f"模板尺寸: {img.size}")

    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("未找到朋友圈窗口")
        return

    rect = sns_window.BoundingRectangle
    win_width = rect.right - rect.left
    win_height = rect.bottom - rect.top

    print(f"窗口: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

    # 限定搜索区域：
    # - 排除顶部 300px（标题栏和头像区域）
    # - 只搜索右侧区域
    # - 排除底部 200px
    search_top = rect.top + 300
    search_bottom = rect.bottom - 200
    search_left = rect.left + win_width // 2  # 右半边
    search_right = rect.right - 20  # 留一点边距

    search_region = (
        search_left,
        search_top,
        search_right - search_left,
        search_bottom - search_top
    )

    print(f"限定搜索区域: ({search_left}, {search_top}) - ({search_right}, {search_bottom})")

    # 截图标记
    screenshot = pyautogui.screenshot()
    draw = ImageDraw.Draw(screenshot)

    # 画搜索区域（蓝色）
    draw.rectangle(
        [search_left, search_top, search_right, search_bottom],
        outline="blue", width=2
    )

    # 尝试不同 confidence
    print("\n在限定区域搜索:")
    print("-" * 50)

    found_pos = None
    for conf in [0.7, 0.6, 0.5, 0.4]:
        try:
            loc = pyautogui.locateOnScreen(
                str(template_path),
                region=search_region,
                confidence=conf
            )

            if loc:
                center = pyautogui.center(loc)
                print(f"confidence={conf}: 找到! 位置=({center.x}, {center.y})")

                # 画找到的位置（红色）
                draw.rectangle(
                    [loc.left, loc.top, loc.left + loc.width, loc.top + loc.height],
                    outline="red", width=3
                )
                draw.line([(center.x - 20, center.y), (center.x + 20, center.y)], fill="red", width=2)
                draw.line([(center.x, center.y - 20), (center.x, center.y + 20)], fill="red", width=2)

                if found_pos is None:
                    found_pos = (center.x, center.y)
            else:
                print(f"confidence={conf}: 未找到")

        except Exception as e:
            print(f"confidence={conf}: 出错 - {e}")

    # 保存截图
    timestamp = datetime.now().strftime("%H%M%S")
    debug_path = Path(__file__).parent / "screenshots" / f"restricted_{timestamp}.png"
    debug_path.parent.mkdir(exist_ok=True)
    screenshot.save(debug_path)
    print(f"\n截图已保存: {debug_path}")

    # 如果找到了，询问是否点击
    if found_pos:
        # 向下偏移 25 像素修正
        click_x = found_pos[0]
        click_y = found_pos[1] + 25
        print(f"\n最佳匹配位置: {found_pos}")
        print(f"修正后点击位置: ({click_x}, {click_y}) (Y+10)")
        confirm = input("是否点击该位置? (y/N): ")
        if confirm.lower() == 'y':
            pyautogui.click(click_x, click_y)  # 匹配点击坐标
            print("已点击!")


if __name__ == "__main__":
    print("=" * 50)
    print("限定区域搜索")
    print("=" * 50)
    restricted_search()
