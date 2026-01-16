# -*- coding: utf-8 -*-
"""
由于微信朋友圈使用 Qt 自绘控件，UIA 无法识别内部元素
改用相对窗口坐标方式定位第一条朋友圈
"""
import uiautomation as auto
import time
import sys
sys.stdout.reconfigure(encoding='utf-8')

auto.SetGlobalSearchTimeout(3)

def get_moments_window():
    """获取朋友圈窗口"""
    win = auto.WindowControl(searchDepth=1, SubName="朋友圈")
    if not win.Exists(1, 0):
        return None
    return win

def get_first_moment_position(win):
    """
    计算第一条朋友圈的点击位置（相对窗口坐标）

    基于微信朋友圈窗口布局分析：
    - 顶部有标题栏 (~50px)
    - 顶部有个人封面区域 (~200-300px)
    - 第一条朋友圈大约在窗口高度的 25%-35% 位置
    """
    rect = win.BoundingRectangle

    win_left = rect.left
    win_top = rect.top
    win_width = rect.right - rect.left
    win_height = rect.bottom - rect.top

    # 第一条朋友圈的相对位置（需要根据实际情况调整）
    # 水平位置：窗口中心
    x_offset_ratio = 0.5
    # 垂直位置：大约在 30% 的位置（跳过封面区域）
    y_offset_ratio = 0.30

    click_x = int(win_left + win_width * x_offset_ratio)
    click_y = int(win_top + win_height * y_offset_ratio)

    return click_x, click_y, {
        'window_rect': (win_left, win_top, rect.right, rect.bottom),
        'window_size': (win_width, win_height),
        'x_offset_ratio': x_offset_ratio,
        'y_offset_ratio': y_offset_ratio
    }

def main():
    print("=" * 60)
    print("微信朋友圈 - 坐标定位方案")
    print("=" * 60)

    # 1. 获取朋友圈窗口
    win = get_moments_window()
    if not win:
        print("❌ 未找到朋友圈窗口")
        return

    print(f"✓ 找到朋友圈窗口")

    # 2. 计算第一条朋友圈位置
    click_x, click_y, info = get_first_moment_position(win)

    print(f"\n窗口信息:")
    print(f"  位置: {info['window_rect']}")
    print(f"  大小: {info['window_size'][0]} x {info['window_size'][1]}")

    print(f"\n计算的第一条朋友圈点击位置:")
    print(f"  X: {click_x} (窗口 {info['x_offset_ratio']*100:.0f}%)")
    print(f"  Y: {click_y} (窗口 {info['y_offset_ratio']*100:.0f}%)")

    # 3. 可视化标记（不实际点击）
    print(f"\n如需点击，可使用:")
    print(f"  auto.Click({click_x}, {click_y})")

    # 4. 建议的调整参数
    print(f"\n" + "=" * 60)
    print("调整建议:")
    print("=" * 60)
    print("如果位置不准确，调整 y_offset_ratio:")
    print("  - 往上移: 减小 y_offset_ratio (如 0.25)")
    print("  - 往下移: 增大 y_offset_ratio (如 0.35)")
    print("\n或者使用固定像素偏移:")
    print("  - 从窗口顶部偏移约 400-500 像素")

    return click_x, click_y

if __name__ == "__main__":
    main()
