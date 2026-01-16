# -*- coding: utf-8 -*-
"""
测试完整的 ".." 按钮定位流程
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import uiautomation as auto
from core.moment.locator import ElementLocator

print("=" * 60)
print("测试完整的 '..' 按钮定位流程")
print("=" * 60)

# 找到朋友圈窗口
sns_win = auto.WindowControl(searchDepth=1, SubName="朋友圈")
if not sns_win.Exists(1, 0):
    print("❌ 未找到朋友圈窗口")
    sys.exit(1)

rect = sns_win.BoundingRectangle
print(f"✓ 朋友圈窗口: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

# 创建定位器
locator = ElementLocator(sns_win)

# 测试各个方法
print("\n" + "-" * 60)
print("方法1: 图像识别 (dots_btn.png)")
print("-" * 60)
pos1 = locator.find_dots_by_image()
if pos1:
    print(f"✓ 成功: ({pos1[0]}, {pos1[1]})")
else:
    print("❌ 失败")

print("\n" + "-" * 60)
print("方法2: 垃圾桶锚定 (delete_btn.png)")
print("-" * 60)
pos2 = locator.find_dots_by_delete_btn()
if pos2:
    print(f"✓ 成功: ({pos2[0]}, {pos2[1]})")
else:
    print("❌ 失败")

print("\n" + "-" * 60)
print("方法3: 时间戳锚定 (UIA + OCR)")
print("-" * 60)
pos3 = locator.find_dots_by_timestamp()
if pos3:
    print(f"✓ 成功: ({pos3[0]}, {pos3[1]})")
else:
    print("❌ 失败")

print("\n" + "-" * 60)
print("混合定位 (find_dots_button_hybrid)")
print("-" * 60)
pos_hybrid = locator.find_dots_button_hybrid()
if pos_hybrid:
    print(f"✓ 成功: ({pos_hybrid[0]}, {pos_hybrid[1]})")
else:
    print("❌ 失败")

print("\n" + "=" * 60)
print("总结")
print("=" * 60)
results = [
    ("图像识别", pos1),
    ("垃圾桶锚定", pos2),
    ("时间戳锚定", pos3),
    ("混合定位", pos_hybrid),
]
for name, pos in results:
    status = f"✓ ({pos[0]}, {pos[1]})" if pos else "❌"
    print(f"  {name}: {status}")
