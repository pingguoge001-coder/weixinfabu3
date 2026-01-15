# -*- coding: utf-8 -*-
"""
查找删除按钮（垃圾桶）的位置
"""
import uiautomation as auto

sns = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if not sns.Exists(3, 1):
    print("Window not found")
    exit()

rect = sns.BoundingRectangle
print(f"Window: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

print("\n=== 查找删除按钮 ===")

# 尝试各种名称
names = ["删除", "Delete", "垃圾桶", "trash", "remove"]
for name in names:
    btn = sns.ButtonControl(searchDepth=20, Name=name)
    if btn.Exists(1, 0):
        r = btn.BoundingRectangle
        print(f"Found '{name}': ({r.left}, {r.top}) - ({r.right}, {r.bottom})")

# 遍历所有按钮
print("\n=== 所有按钮 ===")
def find_buttons(ctrl, depth=0):
    if depth > 20:
        return
    try:
        if ctrl.ControlTypeName == 'ButtonControl':
            r = ctrl.BoundingRectangle
            name = ctrl.Name or "(no name)"
            cls = ctrl.ClassName or ""
            if r and r.top > rect.top + 300:  # 排除顶部
                print(f"Button: '{name}' | Class: {cls} | Y={r.top}")
        for child in ctrl.GetChildren():
            find_buttons(child, depth + 1)
    except:
        pass

find_buttons(sns)

# 遍历所有图像控件（垃圾桶可能是图像）
print("\n=== 所有图像控件 ===")
def find_images(ctrl, depth=0):
    if depth > 20:
        return
    try:
        if ctrl.ControlTypeName == 'ImageControl':
            r = ctrl.BoundingRectangle
            name = ctrl.Name or "(no name)"
            if r and r.top > rect.top + 300:
                print(f"Image: '{name}' | Y={r.top}, Center=({(r.left+r.right)//2}, {(r.top+r.bottom)//2})")
        for child in ctrl.GetChildren():
            find_images(child, depth + 1)
    except:
        pass

find_images(sns)

# 查找所有小型控件（可能是图标按钮）
print("\n=== 小型控件 (可能是图标) ===")
def find_small(ctrl, depth=0):
    if depth > 20:
        return
    try:
        r = ctrl.BoundingRectangle
        if r:
            w = r.right - r.left
            h = r.bottom - r.top
            # 小型控件，在窗口中部
            if 15 < w < 60 and 15 < h < 60 and rect.top + 400 < r.top < rect.bottom - 300:
                name = ctrl.Name or ""
                typ = ctrl.ControlTypeName
                print(f"{typ}: '{name}' | Size={w}x{h} | Y={r.top} | Center=({(r.left+r.right)//2}, {(r.top+r.bottom)//2})")
        for child in ctrl.GetChildren():
            find_small(child, depth + 1)
    except:
        pass

find_small(sns)
