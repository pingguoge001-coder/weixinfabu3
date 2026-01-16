# -*- coding: utf-8 -*-
"""
调试 OCR 时间戳识别
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import uiautomation as auto
import pyautogui
import re

print("测试 OCR 时间戳识别")
print("=" * 60)

# 找到朋友圈窗口
sns_win = auto.WindowControl(searchDepth=1, SubName="朋友圈")
if not sns_win.Exists(1, 0):
    print("❌ 未找到朋友圈窗口")
    sys.exit(1)

rect = sns_win.BoundingRectangle
print(f"窗口位置: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

# 导入 easyocr
try:
    import easyocr
    print("✓ easyocr 已导入")
except ImportError as e:
    print(f"❌ easyocr 导入失败: {e}")
    sys.exit(1)

# 截取窗口
print("\n截取窗口...")
region = (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
screenshot = pyautogui.screenshot(region=region)
print(f"截图大小: {screenshot.size}")

# 初始化 reader
print("\n初始化 easyocr reader...")
try:
    reader = easyocr.Reader(['ch_sim', 'en'], verbose=False)
    print("✓ reader 初始化成功")
except Exception as e:
    print(f"❌ reader 初始化失败: {e}")
    sys.exit(1)

# 执行 OCR
print("\n执行 OCR...")
try:
    results = reader.readtext(screenshot)
    print(f"✓ OCR 完成，识别到 {len(results)} 个文本块")
except Exception as e:
    print(f"❌ OCR 执行失败: {e}")
    sys.exit(1)

# 检查时间戳
def is_standalone_timestamp(text):
    if not text:
        return False
    text = text.strip()
    if '~' in text or '-' in text:
        return False
    if len(text) > 15:
        return False

    patterns = [
        r'^(\d{1,2})[:\.;](\d{2})$',
        r'^(\d+)分钟前$',
        r'^(\d+)小时前$',
        r'^昨天$',
        r'^今天$',
        r'^(\d+)天前$',
        r'^(\d{1,2})月(\d{1,2})日$',
    ]
    for pattern in patterns:
        if re.match(pattern, text):
            return True
    return False

print("\n检查时间戳...")
for (box, text, conf) in results:
    is_time = is_standalone_timestamp(text)
    marker = "⏰" if is_time else "  "
    if conf > 0.3:
        print(f"{marker} '{text}' conf={conf:.2f} is_time={is_time}")
