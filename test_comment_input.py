# -*- coding: utf-8 -*-
"""
测试评论输入框
"""
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent))

import pyautogui
import pyperclip
import uiautomation as auto

SNS_WINDOW_CLASS = "mmui::SNSWindow"


def find_and_input_comment():
    """查找评论输入框并输入内容"""

    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("未找到朋友圈窗口")
        return

    rect = sns_window.BoundingRectangle
    print(f"窗口: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

    # 遍历所有控件，查找可能的输入框
    print("\n查找所有可能的输入控件:")
    print("-" * 60)

    found_controls = []

    def find_all(control, depth=0):
        if depth > 25:
            return
        try:
            ctrl_type = control.ControlTypeName
            class_name = control.ClassName or ""
            name = control.Name or ""

            # 查找可能是输入框的控件
            is_input = (
                "Edit" in ctrl_type or
                "Input" in class_name or
                "Reply" in class_name or
                "评论" in name or
                ctrl_type == "DocumentControl"
            )

            if is_input:
                ctrl_rect = control.BoundingRectangle
                found_controls.append({
                    'type': ctrl_type,
                    'class': class_name,
                    'name': name,
                    'rect': ctrl_rect,
                    'control': control,
                    'depth': depth
                })

            for child in control.GetChildren():
                find_all(child, depth + 1)
        except:
            pass

    find_all(sns_window)

    if found_controls:
        print(f"找到 {len(found_controls)} 个可能的输入控件:\n")
        for i, item in enumerate(found_controls):
            print(f"[{i+1}] {item['type']} (depth={item['depth']})")
            print(f"    ClassName: '{item['class']}'")
            print(f"    Name: '{item['name']}'")
            r = item['rect']
            if r:
                print(f"    Rect: ({r.left}, {r.top}) - ({r.right}, {r.bottom})")
            print()
    else:
        print("未找到输入控件")
        return

    # 尝试输入
    test_link = "https://test.example.com/product"

    for i, item in enumerate(found_controls):
        ctrl = item['control']
        print(f"\n尝试在控件 [{i+1}] 中输入...")

        try:
            # 点击控件
            ctrl.Click()
            time.sleep(0.3)

            # 使用剪贴板粘贴
            pyperclip.copy(test_link)
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.3)

            confirm = input(f"控件 [{i+1}] 是否成功输入? (y/n/q退出): ")
            if confirm.lower() == 'y':
                print(f"成功! 使用的控件: {item['type']} - {item['class']}")
                return item
            elif confirm.lower() == 'q':
                break
            else:
                # 清空输入
                pyautogui.hotkey('ctrl', 'a')
                pyautogui.press('delete')
        except Exception as e:
            print(f"  失败: {e}")

    return None


if __name__ == "__main__":
    print("=" * 60)
    print("测试评论输入框")
    print("=" * 60)
    print("\n请确保评论输入框已打开\n")

    result = find_and_input_comment()

    if result:
        print(f"\n最终结果: 使用 {result['type']} (ClassName={result['class']})")
