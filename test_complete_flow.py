"""完成选择图片并关闭发布页面"""
import sys
import io
import time
import os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import uiautomation as auto

print("=" * 50)
print("完成选择图片并关闭")
print("=" * 50)

image_folder = r"D:\苹果哥的商业系统A\电商\产品素材\待发布\十一月\2025-11-25"

# 查找文件对话框 (作为朋友圈窗口的子窗口)
print("\n--- Step 1: 查找文件对话框 ---")
dialog = auto.WindowControl(searchDepth=2, Name="打开")
if not dialog.Exists(3, 1):
    print("[X] 未找到文件对话框")
    exit(1)

print(f"[OK] 找到文件对话框: {dialog.ClassName}")
dialog.SetFocus()
time.sleep(0.3)

# 获取第一张图片
print("\n--- Step 2: 选择图片 ---")
if os.path.exists(image_folder):
    files = [f for f in os.listdir(image_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]
    if files:
        first_image = os.path.join(image_folder, files[0])
        print(f"选择图片: {first_image}")

        # 找到文件名输入框
        edit = auto.EditControl(searchDepth=15, Name="文件名(N):")
        if edit.Exists(2, 0):
            edit.Click()
            time.sleep(0.2)
            edit.SendKeys("{Ctrl}a", waitTime=0.1)
            edit.SendKeys(first_image, waitTime=0.02)
            print("[OK] 已输入图片路径")
            time.sleep(0.5)

            # 点击打开按钮
            open_btn = auto.ButtonControl(searchDepth=15, Name="打开(O)")
            if open_btn.Exists(2, 0):
                open_btn.Click()
                print("[OK] 已点击打开按钮")
                time.sleep(2)
            else:
                print("[X] 未找到打开按钮")
        else:
            print("[X] 未找到文件名输入框")
    else:
        print(f"[X] 文件夹中没有图片")
else:
    print(f"[X] 文件夹不存在")

# 关闭发布页面
print("\n--- Step 3: 关闭发布页面 ---")
time.sleep(1)

sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if sns_window.Exists(2, 0):
    sns_window.SetFocus()
    time.sleep(0.3)

    # 查找取消按钮
    cancel_btn = sns_window.Control(searchDepth=15, Name="取消")
    if cancel_btn.Exists(2, 0):
        cancel_btn.Click()
        print("[OK] 已点击取消按钮")
        time.sleep(1)

        # 处理确认对话框
        for _ in range(5):
            discard = auto.ButtonControl(searchDepth=10, Name="放弃")
            if discard.Exists(0.5, 0):
                discard.Click()
                print("[OK] 已确认放弃")
                break
            time.sleep(0.3)
    else:
        print("未找到取消按钮，尝试按 Escape...")
        sns_window.SendKeys("{Escape}")
        time.sleep(0.5)

# 最终检查
time.sleep(0.5)
sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if not sns_window.Exists(1, 0):
    print("[OK] 朋友圈窗口已关闭")
else:
    print("[!] 朋友圈窗口仍存在")

print("\n" + "=" * 50)
print("流程完成")
print("=" * 50)
