"""通过坐标点击添加图片按钮"""
import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import uiautomation as auto

print("=" * 50)
print("通过坐标点击添加图片按钮")
print("=" * 50)

# 查找朋友圈窗口
sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if not sns_window.Exists(2, 0):
    print("[X] 未找到朋友圈窗口")
    exit(1)

print("[OK] 找到朋友圈窗口")

# 先确保窗口获得焦点
sns_window.SetFocus()
time.sleep(0.5)

# 检查添加图片按钮
add_btn = sns_window.ListItemControl(searchDepth=15, Name="添加图片")
if add_btn.Exists(1, 0):
    rect = add_btn.BoundingRectangle
    center_x = (rect.left + rect.right) // 2
    center_y = (rect.top + rect.bottom) // 2
    print(f"按钮位置: ({rect.left}, {rect.top}) 大小: {rect.right-rect.left}x{rect.bottom-rect.top}")
    print(f"点击中心: ({center_x}, {center_y})")

    # 使用 Invoke 模式（如果支持）
    try:
        invoke = add_btn.GetInvokePattern()
        if invoke:
            print("尝试 Invoke 模式...")
            invoke.Invoke()
            time.sleep(2)
    except Exception as e:
        print(f"Invoke 失败: {e}")

    # 使用坐标点击
    print("使用坐标点击...")
    auto.Click(center_x, center_y)
    time.sleep(2)

    # 检查结果
    print("\n--- 检查窗口 ---")
    for i in range(1, 10):
        win = auto.WindowControl(searchDepth=1, foundIndex=i)
        if win.Exists(0.2, 0):
            name = win.Name or "(无名称)"
            print(f"  [{i}] {name} | {win.ClassName}")
        else:
            break

    # 查找打开对话框
    dialog = auto.WindowControl(searchDepth=1, ClassName="#32770")
    if dialog.Exists(1, 0):
        print(f"\n[OK] 找到文件对话框: {dialog.Name}")
    else:
        print("\n[X] 未找到文件对话框")

        # 再次尝试使用 mouse click
        print("\n再次尝试 - 使用 mouse MoveTo + Click...")
        auto.MoveTo(center_x, center_y)
        time.sleep(0.3)
        auto.Click(center_x, center_y)
        time.sleep(2)

        dialog = auto.WindowControl(searchDepth=1, ClassName="#32770")
        if dialog.Exists(1, 0):
            print(f"[OK] 找到文件对话框: {dialog.Name}")
        else:
            print("[X] 仍未找到文件对话框")
else:
    print("[X] 未找到添加图片按钮")

print("\n" + "=" * 50)
