"""
测试脚本：只测试点击朋友圈详情页的 "••" 按钮
使用前请先手动打开朋友圈详情页面
"""

import time
import os
from datetime import datetime
from pathlib import Path

import pyautogui
import uiautomation as auto
from PIL import Image, ImageDraw

from core.moment.locator import ElementLocator


# 截图保存目录
DEBUG_DIR = Path(r"E:\GitHub\weixinfabu3\data\debug")


def find_detail_window():
    """查找朋友圈详情窗口"""
    # 方法1: 按标题精确匹配
    window = auto.WindowControl(searchDepth=1, Name="详情")
    if window.Exists(1, 0):
        print(f"找到详情窗口 (Name): class={window.ClassName}")
        return window

    # 方法2: 按标题模糊匹配
    window = auto.WindowControl(searchDepth=1, SubName="详情")
    if window.Exists(1, 0):
        print(f"找到详情窗口 (SubName): class={window.ClassName}")
        return window

    # 方法3: 查找 mmui::SNSWindow
    window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
    if window.Exists(1, 0):
        print(f"找到 SNSWindow: title={window.Name}, class={window.ClassName}")
        return window

    return None


def save_debug_screenshot(x, y, label="dots_btn"):
    """保存调试截图，在点击位置画标记"""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    # 截取全屏
    screenshot = pyautogui.screenshot()

    # 画标记
    draw = ImageDraw.Draw(screenshot)

    # 画十字线
    draw.line([(x - 50, y), (x + 50, y)], fill="red", width=4)
    draw.line([(x, y - 50), (x, y + 50)], fill="red", width=4)
    # 画圆圈
    draw.ellipse([(x - 30, y - 30), (x + 30, y + 30)], outline="red", width=4)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{label}_{timestamp}_{x}_{y}.png"
    filepath = DEBUG_DIR / filename
    screenshot.save(str(filepath))
    print(f"\n截图已保存: {filepath}")
    print(f"文件存在: {filepath.exists()}")
    print(f"文件大小: {filepath.stat().st_size if filepath.exists() else 0} bytes")
    return filepath


def main():
    print("=" * 50)
    print("测试点击朋友圈详情页 '••' 按钮")
    print("请先手动打开朋友圈详情页面！")
    print("=" * 50)

    # 确保目录存在
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n截图保存目录: {DEBUG_DIR}")
    print(f"目录存在: {DEBUG_DIR.exists()}")

    # 等待用户准备
    print("\n3秒后开始查找窗口...")
    time.sleep(3)

    # 查找详情窗口
    window = find_detail_window()
    if not window:
        print("\n错误：未找到朋友圈详情窗口！")
        print("请确保已打开朋友圈详情页面（标题应该是'详情'）")
        input("\n按回车退出...")
        return

    rect = window.BoundingRectangle
    print(f"\n窗口信息:")
    print(f"  标题: {window.Name}")
    print(f"  类名: {window.ClassName}")
    print(f"  位置: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")
    print(f"  大小: {rect.right - rect.left} x {rect.bottom - rect.top}")

    # 创建定位器
    locator = ElementLocator(window)

    # 查找 "••" 按钮
    print("\n正在查找 '••' 按钮...")
    dots_pos = locator.find_dots_button_hybrid()

    if dots_pos:
        x, y = dots_pos[0], dots_pos[1]
        print(f"\n找到 '••' 按钮位置: ({x}, {y})")

        # 先保存截图（标记位置）
        print("\n保存截图...")
        filepath = save_debug_screenshot(x, y)

        # 移动鼠标到按钮位置（不点击）
        print(f"\n移动鼠标到按钮位置 ({x}, {y})...")
        pyautogui.moveTo(x, y, duration=0.5)

        print("\n鼠标已移动到目标位置，请确认位置是否正确")
        user_input = input("是否点击？(y/n): ").strip().lower()

        if user_input == 'y':
            pyautogui.click(x, y)
            print("已点击！")
        else:
            print("取消点击")
    else:
        print("\n错误：无法定位 '••' 按钮！")

        # 保存整个窗口截图用于调试
        print("\n保存窗口截图用于调试...")
        screenshot = pyautogui.screenshot()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = DEBUG_DIR / f"window_full_{timestamp}.png"
        screenshot.save(str(filepath))
        print(f"窗口截图已保存: {filepath}")
        print(f"文件存在: {filepath.exists()}")

    # 打开截图目录
    print(f"\n打开截图目录...")
    os.startfile(str(DEBUG_DIR))

    input("\n按回车退出...")


if __name__ == "__main__":
    main()
