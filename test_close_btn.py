# -*- coding: utf-8 -*-
"""
测试关闭按钮位置
"""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

import pyautogui
import uiautomation as auto

SNS_WINDOW_CLASS = "mmui::SNSWindow"


def test_close_button():
    """测试关闭按钮"""

    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("未找到朋友圈窗口")
        return

    rect = sns_window.BoundingRectangle
    print(f"窗口: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")
    print(f"大小: {rect.right - rect.left} x {rect.bottom - rect.top}")

    # 尝试 UI 自动化查找关闭按钮
    print("\n尝试 UI 自动化查找关闭按钮...")

    close_btn = sns_window.ButtonControl(searchDepth=10, Name="关闭")
    if close_btn.Exists(2, 0):
        r = close_btn.BoundingRectangle
        print(f"找到 '关闭' 按钮: ({r.left}, {r.top}) - ({r.right}, {r.bottom})")
    else:
        print("未找到 '关闭' 按钮")

    # 查找窗口顶部的所有按钮
    print("\n查找窗口顶部区域的所有控件...")
    found = []

    def find_top_controls(control, depth=0):
        if depth > 15:
            return
        try:
            ctrl_rect = control.BoundingRectangle
            # 只关注顶部 100px 区域
            if ctrl_rect and ctrl_rect.top < rect.top + 100:
                name = control.Name or ""
                ctrl_type = control.ControlTypeName
                class_name = control.ClassName or ""
                found.append({
                    'type': ctrl_type,
                    'class': class_name,
                    'name': name,
                    'rect': ctrl_rect,
                    'control': control
                })
            for child in control.GetChildren():
                find_top_controls(child, depth + 1)
        except:
            pass

    find_top_controls(sns_window)

    print(f"找到 {len(found)} 个控件:")
    for item in found:
        r = item['rect']
        print(f"  {item['type']}: '{item['name']}' ({item['class']})")
        if r:
            print(f"       -> ({r.left}, {r.top}) - ({r.right}, {r.bottom})")

    # 计算几个可能的关闭按钮位置
    print("\n可能的关闭按钮坐标:")
    positions = [
        ("rect.right - 25, rect.top + 25", rect.right - 25, rect.top + 25),
        ("rect.right - 20, rect.top + 20", rect.right - 20, rect.top + 20),
        ("rect.right - 15, rect.top + 15", rect.right - 15, rect.top + 15),
        ("rect.right - 30, rect.top + 30", rect.right - 30, rect.top + 30),
    ]

    for desc, x, y in positions:
        print(f"  {desc} = ({x}, {y})")

    # 让用户选择测试哪个位置
    print("\n请选择要测试的位置 (1-4)，或输入自定义坐标 (格式: x,y):")
    choice = input("选择: ")

    if choice in ['1', '2', '3', '4']:
        idx = int(choice) - 1
        _, x, y = positions[idx]
    elif ',' in choice:
        parts = choice.split(',')
        x, y = int(parts[0].strip()), int(parts[1].strip())
    else:
        print("无效选择")
        return

    print(f"\n3秒后点击 ({x}, {y})...")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    pyautogui.click(x, y)
    print("已点击!")


if __name__ == "__main__":
    print("=" * 50)
    print("测试关闭按钮位置")
    print("=" * 50)

    test_close_button()
