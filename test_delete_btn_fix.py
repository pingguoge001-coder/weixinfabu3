# -*- coding: utf-8 -*-
"""
验证垃圾桶识别修复是否有效
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import uiautomation as auto

# 导入修复后的 locator
from core.moment.locator import ElementLocator

print("=" * 60)
print("验证垃圾桶识别修复")
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

# 测试垃圾桶定位
print("\n测试 find_dots_by_delete_btn()...")
dots_pos = locator.find_dots_by_delete_btn()

if dots_pos:
    print(f"✓ 成功! '..' 按钮位置: ({dots_pos[0]}, {dots_pos[1]})")
else:
    print("❌ 失败")

# 测试完整的混合定位
print("\n测试 find_dots_button_hybrid()...")
dots_pos2 = locator.find_dots_button_hybrid()

if dots_pos2:
    print(f"✓ 成功! '..' 按钮位置: ({dots_pos2[0]}, {dots_pos2[1]})")
else:
    print("❌ 失败")
