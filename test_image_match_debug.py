# -*- coding: utf-8 -*-
"""
调试图像识别 - 截图并标记识别位置
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

import pyautogui
import uiautomation as auto
from PIL import Image, ImageDraw

SNS_WINDOW_CLASS = "mmui::SNSWindow"
TEMPLATE_DIR = Path(__file__).parent / "data" / "templates"


def debug_image_match():
    """调试图像识别，截图并标记位置"""

    template_path = TEMPLATE_DIR / "comment_btn.png"

    if not template_path.exists():
        print(f"模板图片不存在: {template_path}")
        return

    # 显示模板图片信息
    template_img = Image.open(template_path)
    print(f"模板图片尺寸: {template_img.size}")
    print(f"建议：模板图片应该尽量小，只包含按钮本身")

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

    # 先截图
    screenshot = pyautogui.screenshot()
    draw = ImageDraw.Draw(screenshot)

    # 画窗口边框（蓝色）
    draw.rectangle(
        [rect.left, rect.top, rect.right, rect.bottom],
        outline="blue", width=2
    )

    # 尝试识别
    print("\n正在进行图像识别...")

    try:
        location = pyautogui.locateOnScreen(
            str(template_path),
            region=search_region,
            confidence=0.6
        )

        if location:
            center = pyautogui.center(location)
            print(f"识别成功!")
            print(f"  匹配区域: ({location.left}, {location.top}) - ({location.left + location.width}, {location.top + location.height})")
            print(f"  匹配尺寸: {location.width}x{location.height}")
            print(f"  中心点: ({center.x}, {center.y})")

            # 画匹配区域（红色矩形）
            draw.rectangle(
                [location.left, location.top,
                 location.left + location.width, location.top + location.height],
                outline="red", width=3
            )

            # 画中心点（红色十字）
            cross_size = 20
            draw.line([(center.x - cross_size, center.y), (center.x + cross_size, center.y)], fill="red", width=2)
            draw.line([(center.x, center.y - cross_size), (center.x, center.y + cross_size)], fill="red", width=2)

            # 添加文字
            draw.text((location.left, location.top - 20), f"Match: {location.width}x{location.height}", fill="red")

        else:
            print("识别失败")

    except Exception as e:
        print(f"识别出错: {e}")

    # 保存调试截图
    timestamp = datetime.now().strftime("%H%M%S")
    debug_path = Path(__file__).parent / "screenshots" / f"debug_match_{timestamp}.png"
    debug_path.parent.mkdir(exist_ok=True)
    screenshot.save(debug_path)
    print(f"\n调试截图已保存: {debug_path}")
    print("请查看截图中红框标记的位置是否正确")


if __name__ == "__main__":
    print("=" * 60)
    print("图像识别调试")
    print("=" * 60)
    debug_image_match()
