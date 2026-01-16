# -*- coding: utf-8 -*-
"""
验证垃圾桶和时间戳的位置是否正确
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import pyautogui
import uiautomation as auto
from PIL import Image, ImageDraw
from pathlib import Path

DEBUG_DIR = Path(__file__).parent / "data" / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

print("验证定位位置")
print("=" * 60)

# 找到朋友圈窗口
sns_win = auto.WindowControl(searchDepth=1, SubName="朋友圈")
if not sns_win.Exists(1, 0):
    print("❌ 未找到朋友圈窗口")
    sys.exit(1)

rect = sns_win.BoundingRectangle
print(f"窗口: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

# 截取窗口
screenshot = pyautogui.screenshot(region=(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top))

# 导入定位器
from core.moment.locator import ElementLocator
locator = ElementLocator(sns_win)

# 获取各个方法的位置
pos_delete = locator.find_dots_by_delete_btn()
pos_timestamp = locator.find_dots_by_timestamp()

print(f"\n垃圾桶锚定: {pos_delete}")
print(f"时间戳锚定: {pos_timestamp}")

# 在截图上标记位置
draw = ImageDraw.Draw(screenshot)

if pos_delete:
    # 转换为相对窗口坐标
    x = pos_delete[0] - rect.left
    y = pos_delete[1] - rect.top
    # 画红色圆圈
    draw.ellipse([x-15, y-15, x+15, y+15], outline="red", width=3)
    draw.text((x+20, y-10), "垃圾桶锚定", fill="red")
    print(f"  垃圾桶锚定 相对坐标: ({x}, {y})")

if pos_timestamp:
    # 转换为相对窗口坐标
    x = pos_timestamp[0] - rect.left
    y = pos_timestamp[1] - rect.top
    # 画蓝色圆圈
    draw.ellipse([x-15, y-15, x+15, y+15], outline="blue", width=3)
    draw.text((x+20, y-10), "时间戳锚定", fill="blue")
    print(f"  时间戳锚定 相对坐标: ({x}, {y})")

# 保存标记后的图片
marked_path = DEBUG_DIR / "dots_positions_marked.png"
screenshot.save(str(marked_path))
print(f"\n已保存标记图片: {marked_path}")
print("请查看图片确认哪个位置是正确的 '..' 按钮位置")
