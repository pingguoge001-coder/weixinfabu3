"""完整朋友圈发布流程 v3 - 修复对话框查找"""
import sys
import io
import time
import os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import uiautomation as auto

print("=" * 50)
print("完整朋友圈发布流程 v3")
print("=" * 50)

image_folder = r"D:\苹果哥的商业系统A\电商\产品素材\待发布\十一月\2025-11-25"

# Step 1: 找到微信主窗口
print("\n--- Step 1: 找到微信主窗口 ---")
main_window = auto.WindowControl(searchDepth=1, ClassName="mmui::MainWindow")
if not main_window.Exists(5, 1):
    print("[X] 未找到微信窗口")
    exit(1)
print(f"[OK] 找到微信窗口")
main_window.SetFocus()
time.sleep(0.3)

# 关闭已有窗口
for _ in range(3):
    sns = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
    if sns.Exists(0.3, 0):
        sns.SendKeys("{Escape}")
        time.sleep(0.3)
    dialog = auto.WindowControl(searchDepth=2, Name="打开")
    if dialog.Exists(0.3, 0):
        dialog.SendKeys("{Escape}")
        time.sleep(0.3)

time.sleep(0.5)

# Step 2: 打开朋友圈
print("\n--- Step 2: 打开朋友圈窗口 ---")
main_window.SetFocus()
moment_btn = main_window.ButtonControl(searchDepth=10, Name="朋友圈")
if not moment_btn.Exists(3, 1):
    print("[X] 未找到朋友圈按钮")
    exit(1)

moment_btn.DoubleClick()
print("[OK] 已双击朋友圈按钮")
time.sleep(2)

sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if not sns_window.Exists(5, 1):
    print("[X] 朋友圈窗口未打开")
    exit(1)
print("[OK] 朋友圈窗口已打开")
sns_window.SetFocus()
time.sleep(0.5)

# Step 3: 点击发表
print("\n--- Step 3: 点击发表按钮 ---")
publish_btn = sns_window.Control(searchDepth=10, Name="发表")
if not publish_btn.Exists(3, 1):
    print("[X] 未找到发表按钮")
    exit(1)

publish_btn.Click()
print("[OK] 已点击发表按钮")
time.sleep(1.5)

# Step 4: 点击添加图片
print("\n--- Step 4: 点击添加图片按钮 ---")
add_btn = sns_window.ListItemControl(searchDepth=15, Name="添加图片")
if not add_btn.Exists(3, 1):
    print("[X] 未找到添加图片按钮")
    exit(1)

add_btn.Click()
print("[OK] 已点击添加图片按钮")
time.sleep(2)

# Step 5: 查找文件对话框 (重点：使用 searchDepth=2 查找子窗口)
print("\n--- Step 5: 选择图片 ---")

# 对话框是朋友圈窗口的子窗口
dialog = auto.WindowControl(searchDepth=2, Name="打开")
if not dialog.Exists(5, 1):
    # 备用方案：在朋友圈窗口内查找
    dialog = sns_window.WindowControl(searchDepth=5, Name="打开")

if not dialog.Exists(3, 0):
    print("[X] 未找到文件对话框")
    # 打印所有窗口用于调试
    print("所有顶层窗口:")
    root = auto.GetRootControl()
    for child in root.GetChildren()[:15]:
        try:
            print(f"  {child.Name} | {child.ClassName}")
        except:
            pass
    exit(1)

print(f"[OK] 找到文件对话框")
dialog.SetFocus()
time.sleep(0.3)

# 获取图片
if os.path.exists(image_folder):
    files = [f for f in os.listdir(image_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]
    if files:
        first_image = os.path.join(image_folder, files[0])
        print(f"选择图片: {first_image}")

        # 输入路径
        edit = auto.EditControl(searchDepth=15, Name="文件名(N):")
        if edit.Exists(2, 0):
            edit.Click()
            time.sleep(0.2)
            edit.SendKeys("{Ctrl}a", waitTime=0.1)
            edit.SendKeys(first_image, waitTime=0.02)
            print("[OK] 已输入图片路径")
            time.sleep(0.5)

            # 点击打开
            open_btn = auto.ButtonControl(searchDepth=15, Name="打开(O)")
            if open_btn.Exists(2, 0):
                open_btn.Click()
                print("[OK] 已点击打开按钮")
                time.sleep(2)
            else:
                dialog.SendKeys("{Enter}")
                print("[OK] 已按 Enter")
                time.sleep(2)
        else:
            print("[X] 未找到文件名输入框")
            exit(1)
    else:
        print("[X] 文件夹中没有图片")
        exit(1)
else:
    print(f"[X] 文件夹不存在: {image_folder}")
    exit(1)

# Step 6: 关闭发布页面
print("\n--- Step 6: 关闭发布页面 ---")
time.sleep(1)

sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if sns_window.Exists(2, 0):
    sns_window.SetFocus()
    time.sleep(0.3)

    cancel_btn = sns_window.Control(searchDepth=15, Name="取消")
    if cancel_btn.Exists(2, 0):
        cancel_btn.Click()
        print("[OK] 已点击取消按钮")
        time.sleep(1)

        # 确认放弃
        for _ in range(5):
            discard = auto.ButtonControl(searchDepth=10, Name="放弃")
            if discard.Exists(0.5, 0):
                discard.Click()
                print("[OK] 已确认放弃")
                break
            time.sleep(0.3)
    else:
        sns_window.SendKeys("{Escape}")
        print("[OK] 已按 Escape")
        time.sleep(0.5)

# 检查结果
time.sleep(0.5)
sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if not sns_window.Exists(1, 0):
    print("[OK] 朋友圈窗口已关闭")
else:
    print("[!] 朋友圈窗口仍存在")

print("\n" + "=" * 50)
print("流程完成！")
print("=" * 50)
