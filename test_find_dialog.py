"""查找文件对话框 - 多种方式"""
import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import uiautomation as auto

print("=" * 50)
print("查找文件对话框")
print("=" * 50)

# 方式1: 遍历所有顶层窗口
print("\n--- 所有顶层窗口 ---")
root = auto.GetRootControl()
for i, child in enumerate(root.GetChildren()):
    try:
        name = child.Name or "(无名称)"
        cls = child.ClassName or "(无类名)"
        print(f"  [{i}] {name} | {cls} | {child.ControlTypeName}")
    except:
        pass

# 方式2: 通过名称查找
print("\n--- 通过名称'打开'查找 ---")
dialog = auto.WindowControl(searchDepth=2, Name="打开")
if dialog.Exists(2, 0):
    print(f"[OK] 找到: {dialog.Name} | {dialog.ClassName}")
    rect = dialog.BoundingRectangle
    print(f"    位置: ({rect.left}, {rect.top}) 大小: {rect.right-rect.left}x{rect.bottom-rect.top}")

# 方式3: 在朋友圈窗口内查找
print("\n--- 在朋友圈窗口内查找 ---")
sns = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if sns.Exists(1, 0):
    print("朋友圈窗口存在")

    # 查找子窗口
    for child in sns.GetChildren():
        name = child.Name or "(无名称)"
        cls = child.ClassName or "(无类名)"
        print(f"  子元素: {name} | {cls} | {child.ControlTypeName}")

    # 在朋友圈窗口内查找对话框
    inner_dialog = sns.WindowControl(searchDepth=5, Name="打开")
    if inner_dialog.Exists(1, 0):
        print(f"[OK] 内部对话框: {inner_dialog.ClassName}")

# 方式4: 使用 SubName
print("\n--- 使用 SubName 查找 ---")
dialog = auto.WindowControl(searchDepth=3, SubName="打开")
if dialog.Exists(1, 0):
    print(f"[OK] SubName找到: {dialog.Name} | {dialog.ClassName}")

# 方式5: 查找包含"文件名"的控件
print("\n--- 查找文件名输入框 ---")
edit = auto.EditControl(searchDepth=15, Name="文件名(N):")
if edit.Exists(1, 0):
    print(f"[OK] 找到文件名输入框")
    parent = edit.GetParentControl()
    if parent:
        print(f"    父元素: {parent.Name} | {parent.ClassName}")

# 方式6: 查找"打开(O)"按钮
print("\n--- 查找打开按钮 ---")
btn = auto.ButtonControl(searchDepth=15, Name="打开(O)")
if btn.Exists(1, 0):
    print(f"[OK] 找到打开按钮")
    rect = btn.BoundingRectangle
    print(f"    位置: ({rect.left}, {rect.top})")

print("\n" + "=" * 50)
