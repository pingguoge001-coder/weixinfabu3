# -*- coding: utf-8 -*-
"""
测试能否识别垃圾桶按钮和时间元素
用于定位 ".." 按钮
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import pyautogui
import uiautomation as auto
from PIL import Image
from pathlib import Path
import re

TEMPLATE_DIR = Path(__file__).parent / "data" / "templates"
DEBUG_DIR = Path(__file__).parent / "data" / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("测试垃圾桶按钮和时间元素识别")
print("=" * 60)

# 1. 找到朋友圈窗口
sns_win = auto.WindowControl(searchDepth=1, SubName="朋友圈")
if not sns_win.Exists(1, 0):
    print("❌ 未找到朋友圈窗口")
    sys.exit(1)

rect = sns_win.BoundingRectangle
print(f"✓ 朋友圈窗口: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

# ============================================================
# 测试1: 垃圾桶按钮图像识别
# ============================================================
print("\n" + "=" * 60)
print("测试1: 垃圾桶按钮图像识别")
print("=" * 60)

delete_template = TEMPLATE_DIR / "delete_btn.png"
print(f"模板路径: {delete_template}")
print(f"模板存在: {delete_template.exists()}")

if delete_template.exists():
    template = Image.open(delete_template)
    print(f"模板尺寸: {template.width} x {template.height}")

    # 在朋友圈窗口范围内搜索
    search_region = (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    print(f"搜索区域: {search_region}")

    # 尝试不同的置信度和缩放
    scales = [1.0, 1.25, 1.5, 0.75, 0.5]
    confidences = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3]

    found = False
    for scale in scales:
        if found:
            break

        if scale == 1.0:
            img = template
        else:
            new_w = max(1, int(template.width * scale))
            new_h = max(1, int(template.height * scale))
            img = template.resize((new_w, new_h), Image.LANCZOS)

        for conf in confidences:
            try:
                # 尝试灰度匹配
                location = pyautogui.locateOnScreen(
                    img,
                    region=search_region,
                    confidence=conf,
                    grayscale=True
                )
                if location:
                    center = pyautogui.center(location)
                    print(f"✓ 找到垃圾桶! scale={scale}, confidence={conf}")
                    print(f"  位置: ({center.x}, {center.y})")
                    print(f"  矩形: ({location.left}, {location.top}, {location.width}, {location.height})")

                    # 计算 ".." 按钮位置
                    dots_x = rect.right - 55  # 窗口右边 -55px
                    dots_y = center.y  # 同一行
                    print(f"  推算'..'位置: ({dots_x}, {dots_y})")
                    found = True
                    break
            except Exception as e:
                pass

    if not found:
        print("❌ 未找到垃圾桶按钮")
        print("  尝试了所有 scale 和 confidence 组合")

        # 截取窗口左下区域保存用于分析
        left_region = (rect.left, rect.top + (rect.bottom - rect.top) // 2,
                       200, (rect.bottom - rect.top) // 2)
        try:
            img = pyautogui.screenshot(region=left_region)
            save_path = DEBUG_DIR / "delete_btn_search_area.png"
            img.save(str(save_path))
            print(f"  已保存搜索区域截图: {save_path}")
        except Exception as e:
            print(f"  截图失败: {e}")

# ============================================================
# 测试2: 时间元素 UIA 识别
# ============================================================
print("\n" + "=" * 60)
print("测试2: 时间元素 UIA 识别")
print("=" * 60)

# 时间格式正则
time_patterns = [
    (r'^\d{1,2}:\d{2}$', "HH:MM"),
    (r'^\d+分钟前$', "X分钟前"),
    (r'^\d+小时前$', "X小时前"),
    (r'^昨天$', "昨天"),
    (r'^今天$', "今天"),
    (r'^\d+天前$', "X天前"),
    (r'^\d{1,2}月\d{1,2}日', "M月D日"),
]

def is_timestamp(text):
    if not text:
        return False, None
    text = text.strip()
    for pattern, desc in time_patterns:
        if re.search(pattern, text):
            return True, desc
    return False, None

# 遍历所有控件查找时间文本
print("遍历 UIA 控件查找时间文本...")

all_texts = []
def collect_text_controls(ctrl, depth=0):
    if depth > 20:
        return
    try:
        if ctrl.ControlTypeName == 'TextControl':
            name = ctrl.Name
            if name:
                is_time, time_type = is_timestamp(name)
                ctrl_rect = ctrl.BoundingRectangle
                all_texts.append({
                    'name': name,
                    'is_time': is_time,
                    'time_type': time_type,
                    'rect': ctrl_rect,
                    'depth': depth
                })
        for child in ctrl.GetChildren():
            collect_text_controls(child, depth + 1)
    except Exception:
        pass

collect_text_controls(sns_win)

print(f"找到 {len(all_texts)} 个 TextControl")

# 显示时间相关的
time_controls = [t for t in all_texts if t['is_time']]
if time_controls:
    print(f"\n✓ 找到 {len(time_controls)} 个时间元素:")
    for t in time_controls:
        r = t['rect']
        if r:
            print(f"  '{t['name']}' ({t['time_type']}) @ ({r.left}, {r.top})")
            # 计算 ".." 位置
            dots_x = rect.right - 55
            dots_y = (r.top + r.bottom) // 2
            print(f"    推算'..'位置: ({dots_x}, {dots_y})")
else:
    print("❌ 未找到任何时间元素")
    if all_texts:
        print(f"\n  找到的所有文本控件 ({len(all_texts)} 个):")
        for t in all_texts[:10]:
            print(f"    '{t['name'][:30]}'")
    else:
        print("  UIA 完全无法获取窗口内的文本控件")
        print("  (微信使用 Qt 自绘，UIA 不支持)")

# ============================================================
# 测试3: 全屏搜索垃圾桶（不限制区域）
# ============================================================
print("\n" + "=" * 60)
print("测试3: 全屏搜索垃圾桶")
print("=" * 60)

if delete_template.exists():
    template = Image.open(delete_template)

    for conf in [0.7, 0.6, 0.5, 0.4, 0.3]:
        try:
            locations = list(pyautogui.locateAllOnScreen(
                template,
                confidence=conf,
                grayscale=True
            ))
            if locations:
                print(f"✓ confidence={conf} 找到 {len(locations)} 个匹配:")
                for loc in locations[:5]:
                    center = pyautogui.center(loc)
                    print(f"    ({center.x}, {center.y})")
                break
        except Exception as e:
            pass
    else:
        print("❌ 全屏也未找到垃圾桶")

# ============================================================
# 结论
# ============================================================
print("\n" + "=" * 60)
print("结论")
print("=" * 60)

if found:
    print("✓ 方案1可行: 通过垃圾桶图像识别定位")
elif time_controls:
    print("✓ 方案2可行: 通过时间元素 UIA 定位")
else:
    print("❌ 两种方案都不可行")
    print("\n建议:")
    print("1. 重新截取当前屏幕上的垃圾桶图片作为模板")
    print("2. 或者使用其他可识别的锚点元素")
