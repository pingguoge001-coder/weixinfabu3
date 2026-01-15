# -*- coding: utf-8 -*-
"""
测试图像识别功能

用法:
1. 先安装依赖: pip install opencv-python
2. 截取 "..." 按钮的图片，保存到 data/templates/comment_btn.png
3. 打开微信朋友圈详情页
4. 运行此脚本: python test_image_match.py
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

import pyautogui
import uiautomation as auto

SNS_WINDOW_CLASS = "mmui::SNSWindow"
TEMPLATE_DIR = Path(__file__).parent / "data" / "templates"


def test_image_match():
    """测试图像识别"""

    # 检查 OpenCV 是否安装
    try:
        import cv2
        print(f"OpenCV 版本: {cv2.__version__}")
    except ImportError:
        print("错误: OpenCV 未安装")
        print("请运行: pip install opencv-python")
        return

    # 检查模板图片
    template_path = TEMPLATE_DIR / "comment_btn.png"
    if not template_path.exists():
        print(f"错误: 模板图片不存在: {template_path}")
        print("\n请截取 '...' 按钮的图片并保存到上述路径")
        print("截图要求:")
        print("  1. 只包含按钮本身，不要多余背景")
        print("  2. 尺寸尽量小但清晰")
        print("  3. PNG 格式")
        return

    print(f"模板图片: {template_path}")

    # 查找朋友圈窗口
    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("错误: 未找到朋友圈窗口")
        print("请先打开微信朋友圈详情页")
        return

    rect = sns_window.BoundingRectangle
    print(f"窗口位置: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

    # 设置搜索区域（只在窗口内搜索）
    search_region = (
        rect.left, rect.top,
        rect.right - rect.left, rect.bottom - rect.top
    )
    print(f"搜索区域: {search_region}")

    # 尝试图像识别
    print("\n正在进行图像识别...")

    try:
        location = pyautogui.locateOnScreen(
            str(template_path),
            region=search_region,
            confidence=0.8
        )

        if location:
            center = pyautogui.center(location)
            print(f"\n识别成功!")
            print(f"  位置: {location}")
            print(f"  中心点: ({center.x}, {center.y})")

            # 询问是否点击
            confirm = input("\n是否点击该位置? (y/N): ")
            if confirm.lower() == 'y':
                pyautogui.click(center.x, center.y)
                print("已点击!")
        else:
            print("\n识别失败: 未找到匹配的按钮")
            print("\n可能原因:")
            print("  1. 模板图片不正确（尝试重新截图）")
            print("  2. confidence 值过高（尝试降低到 0.7 或 0.6）")
            print("  3. 按钮不在当前屏幕可见区域")

    except Exception as e:
        print(f"\n识别出错: {e}")


def test_with_confidence(conf: float):
    """使用指定 confidence 测试"""
    template_path = TEMPLATE_DIR / "comment_btn.png"

    if not template_path.exists():
        print(f"模板图片不存在: {template_path}")
        return

    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(1, 0):
        print("朋友圈窗口不存在")
        return

    rect = sns_window.BoundingRectangle
    search_region = (
        rect.left, rect.top,
        rect.right - rect.left, rect.bottom - rect.top
    )

    print(f"测试 confidence={conf}...")

    try:
        location = pyautogui.locateOnScreen(
            str(template_path),
            region=search_region,
            confidence=conf
        )

        if location:
            center = pyautogui.center(location)
            print(f"  成功! 位置: ({center.x}, {center.y})")
            return True
        else:
            print(f"  失败")
            return False
    except Exception as e:
        print(f"  出错: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("图像识别测试")
    print("=" * 60)

    if len(sys.argv) > 1 and sys.argv[1] == "--scan":
        # 扫描不同 confidence 值
        print("\n扫描不同 confidence 值:")
        for conf in [0.9, 0.8, 0.7, 0.6, 0.5]:
            test_with_confidence(conf)
    else:
        test_image_match()
