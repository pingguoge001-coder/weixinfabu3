"""检查点击添加图片后的界面状态"""
import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, '.')

import uiautomation as auto

print("=" * 50)
print("检查当前界面状态")
print("=" * 50)

# 列出所有顶层窗口
print("\n--- 所有顶层窗口 ---")
for i in range(1, 10):
    win = auto.WindowControl(searchDepth=1, foundIndex=i)
    if win.Exists(0.3, 0):
        try:
            rect = win.BoundingRectangle
            print(f"  [{i}] {win.Name} | {win.ClassName} | ({rect.left}, {rect.top}) {rect.right-rect.left}x{rect.bottom-rect.top}")
        except:
            print(f"  [{i}] {win.Name} | {win.ClassName}")
    else:
        break

# 查找朋友圈窗口
sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if sns_window.Exists(2, 0):
    print(f"\n[OK] 朋友圈窗口存在")

    # 查找新出现的控件
    print("\n--- 检查是否有新的弹出面板 ---")

    # 查找 Popup 或 Menu
    popup = sns_window.Control(searchDepth=5, ControlType=auto.ControlType.MenuControl)
    if popup.Exists(0.5, 0):
        print(f"找到 Menu: {popup.Name} | {popup.ClassName}")

    # 查找 Pane
    print("\n--- 朋友圈窗口内的 Pane ---")
    for i in range(1, 10):
        pane = sns_window.PaneControl(searchDepth=5, foundIndex=i)
        if pane.Exists(0.2, 0):
            try:
                rect = pane.BoundingRectangle
                name = pane.Name or "(无名称)"
                print(f"  Pane [{i}]: {name} | {pane.ClassName} | ({rect.left}, {rect.top})")
            except:
                pass
        else:
            break

    # 查找 List
    print("\n--- 朋友圈窗口内的 List ---")
    for i in range(1, 10):
        lst = sns_window.ListControl(searchDepth=10, foundIndex=i)
        if lst.Exists(0.2, 0):
            try:
                rect = lst.BoundingRectangle
                name = lst.Name or "(无名称)"
                print(f"  List [{i}]: {name} | {lst.ClassName} | ({rect.left}, {rect.top}) {rect.right-rect.left}x{rect.bottom-rect.top}")
            except:
                pass
        else:
            break

    # 再次检查图片网格
    print("\n--- 检查图片网格区域 ---")
    grid_view = sns_window.Control(searchDepth=15, ClassName="mmui::XDragGridView")
    if grid_view.Exists(1, 0):
        rect = grid_view.BoundingRectangle
        print(f"图片网格: ({rect.left}, {rect.top}) {rect.right-rect.left}x{rect.bottom-rect.top}")

        children = grid_view.GetChildren()
        print(f"子元素数量: {len(children)}")
        for i, child in enumerate(children):
            try:
                crect = child.BoundingRectangle
                name = child.Name or "(无名称)"
                print(f"  [{i}] {child.ControlTypeName} | {name} | {child.ClassName}")
            except:
                pass

# 查找文件对话框（可能是不同类名）
print("\n--- 查找可能的文件对话框 ---")
dialog_classes = ["#32770", "SysListView32", "DirectUIHWND", "Alternate Modal Top Most"]
for cls in dialog_classes:
    dialog = auto.WindowControl(searchDepth=1, ClassName=cls)
    if dialog.Exists(0.3, 0):
        print(f"[OK] 找到对话框: {dialog.Name} | {cls}")

# 查找包含 "打开" 或 "选择" 的窗口
print("\n--- 查找打开/选择相关窗口 ---")
for name in ["打开", "选择", "Open", "Select", "图片", "相册"]:
    win = auto.WindowControl(searchDepth=2, SubName=name)
    if win.Exists(0.3, 0):
        print(f"[OK] 找到: {win.Name} | {win.ClassName}")

print("\n" + "=" * 50)
print("检查完成")
print("=" * 50)
