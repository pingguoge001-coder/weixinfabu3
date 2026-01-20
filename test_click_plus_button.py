"""点击朋友圈发布界面的+号按钮（添加图片）"""
import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, '.')

import uiautomation as auto

print("=" * 50)
print("点击添加图片按钮")
print("=" * 50)

# 查找朋友圈窗口 (SNSWindow)
sns_window = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if not sns_window.Exists(3, 1):
    print("[X] 未找到朋友圈窗口")
    exit(1)

print(f"[OK] 找到朋友圈窗口: {sns_window.Name}")

# 查找添加图片按钮
add_image_btn = sns_window.ListItemControl(searchDepth=15, Name="添加图片", ClassName="mmui::PublishImageAddGridCell")
if add_image_btn.Exists(3, 1):
    rect = add_image_btn.BoundingRectangle
    print(f"[OK] 找到添加图片按钮: ({rect.left}, {rect.top}) {rect.right-rect.left}x{rect.bottom-rect.top}")

    # 点击按钮
    add_image_btn.Click()
    print("[OK] 已点击添加图片按钮")

    time.sleep(1)

    # 检查是否弹出文件选择对话框
    print("\n--- 检查弹出窗口 ---")

    # 查找文件选择对话框
    file_dialog = auto.WindowControl(searchDepth=1, ClassName="#32770")  # 标准文件对话框
    if file_dialog.Exists(2, 0):
        print(f"[OK] 弹出文件选择对话框: {file_dialog.Name}")
    else:
        # 可能是其他类型的窗口
        for i in range(1, 5):
            win = auto.WindowControl(searchDepth=1, foundIndex=i)
            if win.Exists(0.5, 0):
                print(f"  窗口 [{i}]: {win.Name} | {win.ClassName}")
else:
    print("[X] 未找到添加图片按钮")

    # 尝试直接通过坐标点击
    print("尝试通过坐标点击 (897, 819)...")
    auto.Click(897 + 72, 819 + 72)  # 添加图片按钮中心坐标
    time.sleep(1)

print("\n" + "=" * 50)
print("完成")
print("=" * 50)
