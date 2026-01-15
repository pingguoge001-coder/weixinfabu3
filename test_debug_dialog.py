"""调试：检查添加图片按钮点击后的状态"""
import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import uiautomation as auto

print("=" * 50)
print("调试：检查当前状态")
print("=" * 50)

# 查找朋友圈窗口
sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if sns_window.Exists(2, 0):
    print(f"[OK] 朋友圈窗口存在")

    # 检查添加图片按钮是否还在
    add_btn = sns_window.ListItemControl(searchDepth=15, Name="添加图片")
    if add_btn.Exists(1, 0):
        rect = add_btn.BoundingRectangle
        print(f"[OK] 添加图片按钮: ({rect.left}, {rect.top})")

        # 尝试双击
        print("尝试双击添加图片按钮...")
        add_btn.DoubleClick()
        time.sleep(2)

# 列出所有窗口
print("\n--- 所有顶层窗口 ---")
for i in range(1, 15):
    win = auto.WindowControl(searchDepth=1, foundIndex=i)
    if win.Exists(0.2, 0):
        try:
            name = win.Name or "(无名称)"
            print(f"  [{i}] {name} | {win.ClassName}")
        except:
            pass
    else:
        break

# 查找任何对话框类型
print("\n--- 查找对话框 ---")
dialog = auto.WindowControl(searchDepth=1, ClassName="#32770")
if dialog.Exists(1, 0):
    print(f"[OK] #32770: {dialog.Name}")

# 查找 Dialog 控件类型
dialogs = auto.GetRootControl().GetChildren()
for child in dialogs:
    if "dialog" in child.ControlTypeName.lower() or "#32770" in (child.ClassName or ""):
        print(f"Dialog: {child.Name} | {child.ClassName}")

print("\n" + "=" * 50)
