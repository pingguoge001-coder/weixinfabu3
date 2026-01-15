# -*- coding: utf-8 -*-
"""
查找发送按钮
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import uiautomation as auto

SNS_WINDOW_CLASS = "mmui::SNSWindow"


def find_send_button():
    """查找发送按钮"""

    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("未找到朋友圈窗口")
        return

    rect = sns_window.BoundingRectangle
    print(f"窗口: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

    # 尝试不同方式查找"发送"按钮
    print("\n尝试查找'发送'按钮:")
    print("-" * 50)

    methods = [
        ("TextControl", lambda: sns_window.TextControl(searchDepth=20, Name="发送")),
        ("ButtonControl", lambda: sns_window.ButtonControl(searchDepth=20, Name="发送")),
        ("Control", lambda: sns_window.Control(searchDepth=20, Name="发送")),
    ]

    for name, method in methods:
        btn = method()
        if btn.Exists(2, 0):
            r = btn.BoundingRectangle
            print(f"{name}: 找到!")
            print(f"  ClassName: {btn.ClassName}")
            print(f"  Rect: ({r.left}, {r.top}) - ({r.right}, {r.bottom})")
            return btn
        else:
            print(f"{name}: 未找到")

    # 遍历所有控件查找包含"发送"的
    print("\n遍历所有控件查找包含'发送'的元素:")
    print("-" * 50)

    found = []

    def find_all(control, depth=0):
        if depth > 25:
            return
        try:
            name = control.Name or ""
            if "发送" in name or "send" in name.lower():
                ctrl_rect = control.BoundingRectangle
                found.append({
                    'type': control.ControlTypeName,
                    'class': control.ClassName or "",
                    'name': name,
                    'rect': ctrl_rect,
                    'control': control
                })

            for child in control.GetChildren():
                find_all(child, depth + 1)
        except:
            pass

    find_all(sns_window)

    if found:
        print(f"找到 {len(found)} 个包含'发送'的元素:\n")
        for i, item in enumerate(found):
            print(f"[{i+1}] {item['type']} - {item['class']}")
            print(f"    Name: '{item['name']}'")
            r = item['rect']
            if r:
                print(f"    Rect: ({r.left}, {r.top}) - ({r.right}, {r.bottom})")
            print()
        return found[0]['control'] if found else None
    else:
        print("未找到包含'发送'的元素")
        return None


if __name__ == "__main__":
    print("=" * 50)
    print("查找发送按钮")
    print("=" * 50)
    print("\n请确保评论输入框已打开且有内容\n")

    btn = find_send_button()

    if btn:
        confirm = input("\n是否点击该按钮? (y/N): ")
        if confirm.lower() == 'y':
            btn.Click()
            print("已点击!")
