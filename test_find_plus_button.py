"""探测朋友圈发布界面的+号按钮"""
import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, '.')

import uiautomation as auto

print("=" * 50)
print("探测朋友圈发布界面 - 查找+号按钮")
print("=" * 50)

# 查找朋友圈窗口 (SNSWindow)
sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if not sns_window.Exists(3, 1):
    print("[X] 未找到朋友圈窗口 (mmui::SNSWindow)")
    print("尝试查找主窗口...")
    main_window = auto.WindowControl(searchDepth=1, ClassName="mmui::MainWindow")
    if main_window.Exists(3, 1):
        print(f"[OK] 找到主窗口: {main_window.Name}")
        # 尝试双击朋友圈按钮打开独立窗口
        moment_btn = main_window.ButtonControl(searchDepth=10, Name="朋友圈")
        if moment_btn.Exists(2, 1):
            print("双击朋友圈按钮...")
            moment_btn.DoubleClick()
            time.sleep(1)
            sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
            if not sns_window.Exists(3, 1):
                print("[X] 仍未找到朋友圈窗口")
                exit(1)
        else:
            print("[X] 未找到朋友圈按钮")
            exit(1)
    else:
        exit(1)

print(f"[OK] 找到朋友圈窗口: {sns_window.Name}")

# 检查是否已经在发布界面（查找输入框）
input_field = sns_window.Control(searchDepth=15, ClassName="mmui::ReplyInputField")
if not input_field.Exists(2, 0):
    print("未在发布界面，尝试点击发表按钮...")
    publish_btn = sns_window.Control(searchDepth=10, Name="发表")
    if publish_btn.Exists(2, 1):
        publish_btn.Click()
        time.sleep(1)
        print("[OK] 已点击发表按钮")
    else:
        print("[X] 未找到发表按钮")
        exit(1)

print("\n--- 查找 mmui::XDragGridView (图片区域) ---")
grid_view = sns_window.Control(searchDepth=15, ClassName="mmui::XDragGridView")
if grid_view.Exists(2, 0):
    rect = grid_view.BoundingRectangle
    print(f"[OK] 找到图片网格: ({rect.left}, {rect.top}) 大小: {rect.right-rect.left}x{rect.bottom-rect.top}")

    # 遍历子元素
    print("\n子元素:")
    children = grid_view.GetChildren()
    for i, child in enumerate(children):
        try:
            crect = child.BoundingRectangle
            name = child.Name or "(无名称)"
            print(f"  [{i}] {child.ControlTypeName} | {name} | {child.ClassName} | ({crect.left}, {crect.top}) {crect.right-crect.left}x{crect.bottom-crect.top}")

            # 继续查找子元素
            for j, sub in enumerate(child.GetChildren()):
                try:
                    srect = sub.BoundingRectangle
                    sname = sub.Name or "(无名称)"
                    print(f"    [{i}.{j}] {sub.ControlTypeName} | {sname} | {sub.ClassName} | ({srect.left}, {srect.top})")
                except:
                    pass
        except:
            pass
else:
    print("[X] 未找到图片网格控件")

# 查找所有按钮
print("\n--- 查找发布界面中的所有按钮 ---")
for i in range(1, 30):
    btn = sns_window.Control(searchDepth=15, ClassName="mmui::XButton", foundIndex=i)
    if btn.Exists(0.2, 0):
        try:
            rect = btn.BoundingRectangle
            name = btn.Name or "(无名称)"
            # 显示所有按钮
            print(f"  [{i}] {name} | ({rect.left}, {rect.top}) {rect.right-rect.left}x{rect.bottom-rect.top}")
        except:
            pass
    else:
        break

# 查找名称包含 "+" 或 "添加" 的控件
print("\n--- 查找+号或添加相关控件 ---")
plus_names = ["+", "添加", "加号", "add", "plus", "添加图片"]
for name in plus_names:
    ctrl = sns_window.Control(searchDepth=15, Name=name)
    if ctrl.Exists(0.5, 0):
        rect = ctrl.BoundingRectangle
        print(f"[OK] 找到 '{name}': {ctrl.ControlTypeName} | {ctrl.ClassName} | ({rect.left}, {rect.top})")

# 查找 ImageControl
print("\n--- 查找 ImageControl (可能是+号图标) ---")
for i in range(1, 20):
    img = sns_window.ImageControl(searchDepth=15, foundIndex=i)
    if img.Exists(0.2, 0):
        try:
            rect = img.BoundingRectangle
            name = img.Name or "(无名称)"
            # 只显示在图片区域附近的 (y > 750, y < 1000)
            if 750 < rect.top < 1000:
                print(f"  [{i}] {name} | {img.ClassName} | ({rect.left}, {rect.top}) {rect.right-rect.left}x{rect.bottom-rect.top}")
        except:
            pass
    else:
        break

# 查找 ListItem 或 GridItem
print("\n--- 查找 ListItem/GridItem ---")
for i in range(1, 10):
    item = sns_window.ListItemControl(searchDepth=15, foundIndex=i)
    if item.Exists(0.2, 0):
        try:
            rect = item.BoundingRectangle
            name = item.Name or "(无名称)"
            print(f"  ListItem [{i}] {name} | {item.ClassName} | ({rect.left}, {rect.top})")
        except:
            pass
    else:
        break

# 尝试直接点击图片区域（通常+号在图片区域内）
print("\n--- 图片区域信息 ---")
if grid_view.Exists(0.5, 0):
    rect = grid_view.BoundingRectangle
    center_x = (rect.left + rect.right) // 2
    center_y = (rect.top + rect.bottom) // 2
    print(f"图片区域中心: ({center_x}, {center_y})")
    print(f"左上角: ({rect.left}, {rect.top})")
    print(f"区域大小: {rect.right-rect.left}x{rect.bottom-rect.top}")

print("\n" + "=" * 50)
print("探测完成")
print("=" * 50)
