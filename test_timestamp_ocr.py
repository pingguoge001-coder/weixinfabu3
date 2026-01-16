# -*- coding: utf-8 -*-
"""
测试用 OCR 识别时间戳坐标
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import pyautogui
import uiautomation as auto
from pathlib import Path
import re

DEBUG_DIR = Path(__file__).parent / "data" / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("测试 OCR 识别时间戳")
print("=" * 60)

# 导入 easyocr
try:
    import easyocr
    print("✓ easyocr 可用")
except ImportError:
    print("❌ easyocr 未安装")
    sys.exit(1)

# 找到朋友圈窗口
sns_win = auto.WindowControl(searchDepth=1, SubName="朋友圈")
if not sns_win.Exists(1, 0):
    print("❌ 未找到朋友圈窗口")
    sys.exit(1)

rect = sns_win.BoundingRectangle
print(f"✓ 朋友圈窗口: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

# 截取朋友圈窗口
print("\n截取朋友圈窗口...")
region = (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
screenshot = pyautogui.screenshot(region=region)
screenshot_path = DEBUG_DIR / "sns_window_for_ocr.png"
screenshot.save(str(screenshot_path))
print(f"已保存截图: {screenshot_path}")

# 严格的时间戳匹配 - 只匹配独立的时间格式
def is_standalone_timestamp(text):
    """
    检查是否是独立的时间戳（不是昵称中的时间）

    真正的时间戳格式：
    - 15:51 (纯时间)
    - 昨天
    - 3分钟前
    - 2小时前
    - 3天前
    - 1月15日
    """
    if not text:
        return False
    text = text.strip()

    # 排除包含 "~" 或 "-" 的时间范围（如 9:00~21:00）
    if '~' in text or '-' in text:
        return False

    # 排除太长的文本（时间戳通常很短）
    if len(text) > 15:
        return False

    # 严格匹配模式（OCR 可能把冒号识别成点号）
    patterns = [
        r'^(\d{1,2})[:\.;](\d{2})$',      # 纯时间 HH:MM (冒号可能被识别为点号)
        r'^(\d+)分钟前$',                  # X分钟前
        r'^(\d+)小时前$',                  # X小时前
        r'^昨天$',                         # 昨天
        r'^今天$',                         # 今天
        r'^(\d+)天前$',                    # X天前
        r'^(\d{1,2})月(\d{1,2})日$',       # M月D日
        r'^(\d{1,2})月(\d{1,2})日\s+\d{1,2}[:\.]\d{2}$',  # M月D日 HH:MM
    ]

    for pattern in patterns:
        if re.match(pattern, text):
            return True
    return False

# 执行 OCR
print(f"\n执行 OCR...")
reader = easyocr.Reader(['ch_sim', 'en'], verbose=False)
results = reader.readtext(str(screenshot_path))

print(f"\nOCR 识别到 {len(results)} 个文本块:")
print("-" * 50)

time_results = []
for (box, text, conf) in results:
    # 计算位置
    center_x = int((box[0][0] + box[2][0]) / 2)
    center_y = int((box[0][1] + box[2][1]) / 2)
    screen_x = rect.left + center_x
    screen_y = rect.top + center_y

    is_time = is_standalone_timestamp(text)
    marker = "⏰" if is_time else "  "

    # 只显示可能相关的（置信度 > 0.3，长度 < 30）
    if conf > 0.3 and len(text) < 30:
        print(f"{marker} '{text}' @ ({screen_x}, {screen_y}) conf={conf:.2f}")

    if is_time:
        time_results.append({
            'text': text,
            'x': screen_x,
            'y': screen_y,
            'conf': conf
        })

print("-" * 50)

if time_results:
    print(f"\n✓ 找到 {len(time_results)} 个时间戳:")
    for r in time_results:
        print(f"  ⏰ '{r['text']}' @ ({r['x']}, {r['y']})")
        dots_x = rect.right - 55
        dots_y = r['y']
        print(f"     推算'..'位置: ({dots_x}, {dots_y})")
else:
    print("\n❌ 未找到独立时间戳")
    print("\n提示: 真正的时间戳格式应该是:")
    print("  - 15:51 (纯时间)")
    print("  - 昨天 / 今天")
    print("  - X分钟前 / X小时前 / X天前")

print("\n" + "=" * 60)
print("结论")
print("=" * 60)
if time_results:
    print("✓ OCR 可以识别时间戳，可作为定位 '..' 按钮的备选方案")
else:
    print("⚠️ OCR 未能识别到独立时间戳")
    print("  建议优先使用垃圾桶图像识别方案")
