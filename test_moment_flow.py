"""测试朋友圈发布流程 - 探测 UI 元素"""
import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, '.')

import uiautomation as auto

print("=" * 50)
print("探测朋友圈界面元素")
print("=" * 50)

# 找到微信主窗口
main_window = auto.WindowControl(searchDepth=1, ClassName="mmui::MainWindow")
if not main_window.Exists(5, 1):
    print("[X] 未找到微信窗口")
    exit(1)

print(f"[OK] 找到微信窗口: {main_window.Name}")

# Step 1: 点击朋友圈按钮进入朋友圈
print("\n--- Step 1: 点击朋友圈按钮 ---")
moment_btn = main_window.ButtonControl(searchDepth=10, Name="朋友圈")
if moment_btn.Exists(5, 1):
    moment_btn.Click()
    print("[OK] 已点击朋友圈按钮")
    time.sleep(2)  # 等待加载
else:
    print("[X] 未找到朋友圈按钮")
    exit(1)

# Step 2: 探测朋友圈面板内的元素
print("\n--- Step 2: 探测朋友圈面板元素 ---")

def print_element(element, depth=0):
    """打印元素信息"""
    indent = "  " * depth
    name = element.Name or "(无名称)"
    class_name = element.ClassName or "(无类名)"
    control_type = element.ControlTypeName or "(无类型)"

    try:
        rect = element.BoundingRectangle
        pos = f"({rect.left}, {rect.top}) {rect.right-rect.left}x{rect.bottom-rect.top}"
    except:
        pos = "(无位置)"

    print(f"{indent}[{control_type}] {name} | {class_name} | {pos}")

# 查找相机相关按钮
print("\n查找相机/发布相关按钮...")
camera_names = ["相机", "拍照", "发布", "发表", "camera", "拍照分享", "发朋友圈"]
for name in camera_names:
    btn = main_window.Control(searchDepth=15, Name=name)
    if btn.Exists(1, 0):
        rect = btn.BoundingRectangle
        print(f"[OK] 找到 '{name}': {btn.ControlTypeName} | {btn.ClassName} | ({rect.left}, {rect.top})")

# 查找 mmui::XButton 按钮
print("\n--- 查找所有 mmui::XButton 按钮 ---")
for i in range(1, 30):
    btn = main_window.Control(searchDepth=15, ClassName="mmui::XButton", foundIndex=i)
    if btn.Exists(0.3, 0):
        try:
            rect = btn.BoundingRectangle
            name = btn.Name or "(无名称)"
            # 只显示在朋友圈区域内的按钮 (大约 x > 175)
            if rect.left > 170:
                print(f"  [{i}] {name} | 位置: ({rect.left}, {rect.top}) 大小: {rect.right-rect.left}x{rect.bottom-rect.top}")
        except:
            pass
    else:
        break

# 查找 Image 控件
print("\n--- 查找 ImageControl ---")
for i in range(1, 15):
    img = main_window.ImageControl(searchDepth=15, foundIndex=i)
    if img.Exists(0.3, 0):
        try:
            rect = img.BoundingRectangle
            name = img.Name or "(无名称)"
            if rect.left > 170:
                print(f"  [{i}] {name} | {img.ClassName} | ({rect.left}, {rect.top}) {rect.right-rect.left}x{rect.bottom-rect.top}")
        except:
            pass
    else:
        break

# 查找工具栏
print("\n--- 查找朋友圈区域的工具栏 ---")
toolbars = []
for i in range(1, 10):
    toolbar = main_window.ToolBarControl(searchDepth=15, foundIndex=i)
    if toolbar.Exists(0.3, 0):
        try:
            rect = toolbar.BoundingRectangle
            name = toolbar.Name or "(无名称)"
            print(f"  工具栏 [{i}]: {name} | {toolbar.ClassName} | ({rect.left}, {rect.top})")
            # 打印工具栏内的子元素
            for child in toolbar.GetChildren():
                print_element(child, 2)
        except:
            pass
    else:
        break

# 遍历朋友圈区域顶部
print("\n--- 遍历朋友圈顶部区域元素 ---")
# 查找 Pane 控件
pane = main_window.PaneControl(searchDepth=5)
if pane.Exists(1, 0):
    print(f"主 Pane: {pane.Name} | {pane.ClassName}")
    for child in pane.GetChildren():
        try:
            rect = child.BoundingRectangle
            # 只看朋友圈区域 (x > 175)
            if rect.left > 170 and rect.top < 300:  # 顶部区域
                print_element(child, 1)
                for sub in child.GetChildren():
                    try:
                        srect = sub.BoundingRectangle
                        if srect.top < 300:
                            print_element(sub, 2)
                    except:
                        pass
        except:
            pass

print("\n" + "=" * 50)
print("探测完成")
print("=" * 50)
