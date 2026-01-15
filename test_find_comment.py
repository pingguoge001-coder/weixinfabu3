# -*- coding: utf-8 -*-
"""
查找"评论"按钮
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import uiautomation as auto

SNS_WINDOW_CLASS = "mmui::SNSWindow"


def find_comment_button():
    """查找评论按钮"""

    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if not sns_window.Exists(3, 1):
        print("未找到朋友圈窗口")
        return

    rect = sns_window.BoundingRectangle
    print(f"窗口: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

    # 尝试直接查找"评论"按钮
    print("\n尝试查找'评论'按钮:")
    print("-" * 50)

    for ctrl_type in ["ButtonControl", "TextControl", "Control"]:
        method = getattr(sns_window, ctrl_type)
        btn = method(searchDepth=20, Name="评论")
        if btn.Exists(2, 0):
            r = btn.BoundingRectangle
            print(f"找到! 类型={ctrl_type}")
            print(f"  Rect: ({r.left}, {r.top}) - ({r.right}, {r.bottom})")
            print(f"  ClassName: {btn.ClassName}")
            return btn
        else:
            print(f"{ctrl_type}: 未找到")

    # 遍历所有控件查找
    print("\n遍历所有控件查找包含'评论'的元素:")
    print("-" * 50)

    found = []

    def find_all(control, depth=0):
        if depth > 25:
            return
        try:
            name = control.Name or ""
            if "评论" in name or "comment" in name.lower():
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
        print(f"找到 {len(found)} 个包含'评论'的元素:\n")
        for i, item in enumerate(found):
            print(f"[{i+1}] {item['type']} - {item['class']}")
            print(f"    Name: '{item['name']}'")
            r = item['rect']
            if r:
                print(f"    Rect: ({r.left}, {r.top}) - ({r.right}, {r.bottom})")
            print()
        return found[0]['control'] if found else None
    else:
        print("未找到包含'评论'的元素")
        return None


if __name__ == "__main__":
    print("=" * 50)
    print("查找评论按钮")
    print("=" * 50)
    print("请先点击 '...' 按钮让菜单弹出\n")

    btn = find_comment_button()

    if btn:
        confirm = input("\n是否点击该按钮? (y/N): ")
        if confirm.lower() == 'y':
            btn.Click()
            print("已点击!")
