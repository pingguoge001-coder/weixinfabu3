"""完整的朋友圈发布流程测试"""
import sys
import io
import time
import os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, '.')

import uiautomation as auto

print("=" * 50)
print("完整朋友圈发布流程")
print("=" * 50)

# 图片文件夹路径
image_folder = r"D:\苹果哥的商业系统A\电商\产品素材\待发布\十一月\2025-11-25"

# Step 1: 找到微信主窗口
print("\n--- Step 1: 找到微信主窗口 ---")
main_window = auto.WindowControl(searchDepth=1, ClassName="mmui::MainWindow")
if not main_window.Exists(5, 1):
    print("[X] 未找到微信窗口")
    exit(1)
print(f"[OK] 找到微信窗口: {main_window.Name}")

# 先关闭可能存在的朋友圈窗口
sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if sns_window.Exists(1, 0):
    print("关闭已存在的朋友圈窗口...")
    sns_window.SendKeys("{Escape}")
    time.sleep(0.5)
    sns_window.SendKeys("{Escape}")
    time.sleep(0.5)

# Step 2: 双击朋友圈按钮打开朋友圈窗口
print("\n--- Step 2: 打开朋友圈窗口 ---")
moment_btn = main_window.ButtonControl(searchDepth=10, Name="朋友圈")
if not moment_btn.Exists(3, 1):
    print("[X] 未找到朋友圈按钮")
    exit(1)

moment_btn.DoubleClick()
print("[OK] 已双击朋友圈按钮")
time.sleep(2)

# 等待朋友圈窗口出现
sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if not sns_window.Exists(5, 1):
    print("[X] 朋友圈窗口未打开")
    exit(1)
print(f"[OK] 朋友圈窗口已打开: {sns_window.Name}")

# Step 3: 点击发表按钮
print("\n--- Step 3: 点击发表按钮 ---")
publish_btn = sns_window.Control(searchDepth=10, Name="发表")
if not publish_btn.Exists(3, 1):
    print("[X] 未找到发表按钮")
    exit(1)

publish_btn.Click()
print("[OK] 已点击发表按钮")
time.sleep(1.5)

# Step 4: 点击添加图片按钮
print("\n--- Step 4: 点击添加图片按钮 ---")
add_image_btn = sns_window.ListItemControl(searchDepth=15, Name="添加图片", ClassName="mmui::PublishImageAddGridCell")
if not add_image_btn.Exists(3, 1):
    print("[X] 未找到添加图片按钮")
    exit(1)

add_image_btn.Click()
print("[OK] 已点击添加图片按钮")
time.sleep(2)  # 等待文件对话框弹出

# Step 5: 在文件对话框中选择图片
print("\n--- Step 5: 选择图片 ---")

# 尝试多种方式查找文件对话框
file_dialog = None
for attempt in range(5):
    # 方式1: 通过类名
    file_dialog = auto.WindowControl(searchDepth=1, ClassName="#32770")
    if file_dialog.Exists(1, 0):
        print(f"[OK] 找到文件对话框 (方式1): {file_dialog.Name}")
        break

    # 方式2: 通过名称
    file_dialog = auto.WindowControl(searchDepth=1, Name="打开")
    if file_dialog.Exists(1, 0):
        print(f"[OK] 找到文件对话框 (方式2): {file_dialog.Name}")
        break

    print(f"  等待文件对话框... ({attempt + 1}/5)")
    time.sleep(1)

if not file_dialog or not file_dialog.Exists(1, 0):
    print("[X] 未找到文件对话框")
    print("当前所有窗口:")
    for i in range(1, 8):
        win = auto.WindowControl(searchDepth=1, foundIndex=i)
        if win.Exists(0.3, 0):
            print(f"  [{i}] {win.Name} | {win.ClassName}")
    exit(1)

# 获取文件夹中的第一张图片
if os.path.exists(image_folder):
    files = [f for f in os.listdir(image_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]
    if files:
        first_image = os.path.join(image_folder, files[0])
        print(f"选择图片: {first_image}")

        # 找到地址栏或文件名输入框，直接输入完整路径
        # 方式：使用 Ctrl+L 聚焦地址栏，然后输入路径
        file_dialog.SetFocus()
        time.sleep(0.3)

        # 直接在文件名框输入完整路径
        # 查找文件名编辑框
        edit = file_dialog.EditControl(searchDepth=10)
        if edit.Exists(2, 0):
            edit.Click()
            time.sleep(0.2)
            edit.SendKeys("{Ctrl}a", waitTime=0.1)
            edit.SendKeys(first_image, waitTime=0.02)
            print("[OK] 已输入图片路径")
            time.sleep(0.5)

            # 点击打开按钮
            open_btn = file_dialog.ButtonControl(searchDepth=10, Name="打开(O)")
            if open_btn.Exists(2, 0):
                open_btn.Click()
                print("[OK] 已点击打开按钮")
                time.sleep(1.5)
            else:
                # 尝试按 Enter
                file_dialog.SendKeys("{Enter}")
                print("[OK] 已按 Enter 确认")
                time.sleep(1.5)
        else:
            print("[X] 未找到文件名输入框")
    else:
        print(f"[X] 文件夹中没有图片: {image_folder}")
        exit(1)
else:
    print(f"[X] 文件夹不存在: {image_folder}")
    exit(1)

# Step 6: 关闭发布页面
print("\n--- Step 6: 关闭发布页面 ---")
time.sleep(1)

# 检查朋友圈窗口是否还在
sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if sns_window.Exists(2, 0):
    # 查找取消按钮
    cancel_btn = sns_window.Control(searchDepth=15, Name="取消")
    if cancel_btn.Exists(2, 0):
        cancel_btn.Click()
        print("[OK] 已点击取消按钮")
        time.sleep(1)

        # 可能会有确认对话框，查找并处理
        # 检查是否有弹窗
        for i in range(3):
            # 查找确认放弃的按钮
            discard_btn = auto.ButtonControl(searchDepth=5, Name="放弃")
            if discard_btn.Exists(0.5, 0):
                discard_btn.Click()
                print("[OK] 已确认放弃")
                break

            # 查找其他确认按钮
            confirm_btn = auto.ButtonControl(searchDepth=5, Name="确定")
            if confirm_btn.Exists(0.5, 0):
                confirm_btn.Click()
                print("[OK] 已点击确定")
                break

            time.sleep(0.3)
    else:
        # 尝试按 Escape 关闭
        print("未找到取消按钮，尝试按 Escape...")
        sns_window.SendKeys("{Escape}")
        time.sleep(0.5)

# 最终检查
time.sleep(0.5)
sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if not sns_window.Exists(1, 0):
    print("[OK] 朋友圈窗口已关闭")
else:
    print("[!] 朋友圈窗口仍然存在")

print("\n" + "=" * 50)
print("流程完成")
print("=" * 50)
