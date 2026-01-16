# -*- coding: utf-8 -*-
"""
诊断 dots_btn.png 图像识别失败的原因
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import pyautogui
import uiautomation as auto
from PIL import Image
from pathlib import Path

# 模板路径
TEMPLATE_DIR = Path(__file__).parent / "data" / "templates"

print("=" * 60)
print("诊断 dots_btn.png 图像识别")
print("=" * 60)

# 1. 检查模板图片
template_path = TEMPLATE_DIR / "dots_btn.png"
print(f"\n1. 模板图片: {template_path}")
print(f"   存在: {template_path.exists()}")

if template_path.exists():
    template = Image.open(template_path)
    print(f"   尺寸: {template.width} x {template.height}")
    print(f"   模式: {template.mode}")
    # 显示图片的大致颜色
    if template.mode == 'RGBA':
        pixels = list(template.getdata())
        non_transparent = [p for p in pixels if p[3] > 128]
        if non_transparent:
            avg_r = sum(p[0] for p in non_transparent) // len(non_transparent)
            avg_g = sum(p[1] for p in non_transparent) // len(non_transparent)
            avg_b = sum(p[2] for p in non_transparent) // len(non_transparent)
            print(f"   主要颜色(RGB): ({avg_r}, {avg_g}, {avg_b})")

# 2. 找到朋友圈窗口
print("\n2. 查找朋友圈窗口")
sns_win = auto.WindowControl(searchDepth=1, SubName="朋友圈")
if not sns_win.Exists(1, 0):
    print("   ❌ 未找到朋友圈窗口")
    sys.exit(1)

rect = sns_win.BoundingRectangle
print(f"   ✓ 找到朋友圈窗口")
print(f"   位置: ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})")
print(f"   大小: {rect.right - rect.left} x {rect.bottom - rect.top}")

# 3. 计算搜索区域（与 locator.py 中的逻辑一致）
print("\n3. 搜索区域分析")

# 区域1：底部右侧框
box_w = 260
box_h = 220
box_right_pad = 40
box_bottom_pad = 120
bottom_box = (
    rect.right - box_right_pad - box_w,
    rect.bottom - box_bottom_pad - box_h,
    box_w,
    box_h,
)
print(f"   区域1 (底部框): {bottom_box}")

# 区域2：右侧条带
right_strip = 140
top_pad = 120
bottom_pad = 160
right_strip_region = (
    rect.right - right_strip,
    rect.top + top_pad,
    right_strip,
    max(10, rect.bottom - rect.top - top_pad - bottom_pad),
)
print(f"   区域2 (右侧条带): {right_strip_region}")

# 4. 截取这两个区域保存用于分析
debug_dir = Path(__file__).parent / "data" / "debug"
debug_dir.mkdir(parents=True, exist_ok=True)

print(f"\n4. 截取搜索区域保存到: {debug_dir}")

try:
    # 截取区域1
    img1 = pyautogui.screenshot(region=bottom_box)
    path1 = debug_dir / "dots_region1_bottom_box.png"
    img1.save(str(path1))
    print(f"   ✓ 已保存区域1: {path1}")

    # 截取区域2
    img2 = pyautogui.screenshot(region=right_strip_region)
    path2 = debug_dir / "dots_region2_right_strip.png"
    img2.save(str(path2))
    print(f"   ✓ 已保存区域2: {path2}")

except Exception as e:
    print(f"   ❌ 截图失败: {e}")

# 5. 尝试图像识别
print("\n5. 尝试图像识别")

if template_path.exists():
    confidence_levels = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
    scales = [1.0, 1.25, 1.5, 0.75, 0.5]

    for region_name, region in [("底部框", bottom_box), ("右侧条带", right_strip_region)]:
        print(f"\n   在 {region_name} 中搜索:")
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

            for conf in confidence_levels:
                try:
                    # 灰度模式
                    location = pyautogui.locateOnScreen(
                        img,
                        region=region,
                        confidence=conf,
                        grayscale=True
                    )
                    if location:
                        center = pyautogui.center(location)
                        print(f"   ✓ 找到! scale={scale}, confidence={conf}, 位置={center}")
                        found = True
                        break
                except Exception as e:
                    pass

            if found:
                break

        if not found:
            print(f"   ❌ 未找到 (尝试了所有 scale={scales}, confidence={confidence_levels})")

# 6. 计算理论上 ".." 按钮的位置
print("\n6. '..' 按钮理论位置分析")
print("   从截图分析，'..' 按钮位于:")
print(f"   - 朋友圈窗口右侧，约距右边 45-55px")
print(f"   - 垂直位置取决于内容，通常在时间戳同一行")

# 假设位于窗口右侧 50px，垂直位置约在 75% 高度（内容区域）
dots_x = rect.right - 50
dots_y_ratio = 0.5  # 默认窗口中间
dots_y = rect.top + int((rect.bottom - rect.top) * dots_y_ratio)

print(f"\n   预估坐标 (需校准): ({dots_x}, {dots_y})")

# 7. 建议
print("\n" + "=" * 60)
print("7. 诊断建议")
print("=" * 60)
print("""
可能的失败原因:
1. 模板尺寸不匹配 - 当前模板可能是在不同 DPI/分辨率下截取的
2. 颜色差异 - 微信主题或系统颜色设置不同
3. 搜索区域不准确 - '..' 按钮可能不在预设的搜索区域内

建议修复方案:
1. 重新截取当前屏幕上的 '..' 按钮图像作为模板
2. 检查 data/debug/ 目录下的截图，确认 '..' 按钮是否在搜索区域内
3. 如果图像识别持续不稳定，建议使用坐标相对定位方案
""")

print("\n请查看以下文件进行人工检查:")
print(f"  - 模板: {template_path}")
print(f"  - 区域1截图: {debug_dir / 'dots_region1_bottom_box.png'}")
print(f"  - 区域2截图: {debug_dir / 'dots_region2_right_strip.png'}")
