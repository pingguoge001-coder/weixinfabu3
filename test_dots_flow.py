# -*- coding: utf-8 -*-
"""
测试从 "..." 按钮开始的完整流程
前提：朋友圈详情页已打开（已点击了某条朋友圈）

流程：
1. 点击 "..." 按钮（混合定位）
2. 点击 "评论" 按钮
3. 输入产品链接
4. 点击 "发送" 按钮
5. 关闭窗口
"""
import sys
import time
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pyautogui
import pyperclip
import uiautomation as auto

from services.config_manager import get_config

# 配置
SNS_WINDOW_CLASS = "mmui::SNSWindow"
TEMPLATE_DIR = Path(__file__).parent / "data" / "templates"

# 测试产品链接
TEST_PRODUCT_LINK = "#小程序://测试链接/test123"


def get_sns_window():
    """获取朋友圈窗口"""
    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)
    if sns_window.Exists(3, 1):
        return sns_window
    return None


def find_button_by_image(template_name, region=None, confidence=0.6):
    """图像识别查找按钮"""
    template_path = TEMPLATE_DIR / template_name
    if not template_path.exists():
        print(f"[WARN] 模板不存在: {template_path}")
        return None

    try:
        location = pyautogui.locateOnScreen(str(template_path), region=region, confidence=confidence)
        if location:
            center = pyautogui.center(location)
            return (center.x, center.y)
    except Exception as e:
        print(f"[WARN] 图像识别失败: {e}")
    return None


def find_dots_by_delete_btn(sns_window):
    """通过识别删除按钮（垃圾桶）来定位 '...' 按钮"""
    rect = sns_window.BoundingRectangle
    if not rect:
        return None

    # 用图像识别找删除按钮
    for confidence in [0.8, 0.7, 0.6, 0.5]:
        pos = find_button_by_image("delete_btn.png", confidence=confidence)
        if pos:
            # "..." 按钮的 X 坐标固定，Y 坐标和删除按钮相同
            dots_x_offset = get_config("ui_location.dots_btn_right_offset", 55)
            dots_x = rect.right - dots_x_offset
            dots_y = pos[1]
            print(f"[OK] 通过删除按钮定位: delete={pos}, dots=({dots_x}, {dots_y}), confidence={confidence}")
            return (dots_x, dots_y)

    return None


def find_dots_by_timestamp(sns_window):
    """通过时间戳相对定位"""
    rect = sns_window.BoundingRectangle
    if not rect:
        return None

    time_patterns = [
        r'^\d{1,2}:\d{2}$',
        r'^昨天$',
        r'^\d+小时前$',
        r'^\d+分钟前$',
        r'^\d+天前$',
    ]

    def is_timestamp(text):
        if not text:
            return False
        return any(re.match(p, text) for p in time_patterns)

    def find_timestamp_control(ctrl, depth=0):
        if depth > 20:
            return None
        try:
            if ctrl.ControlTypeName == 'TextControl' and is_timestamp(ctrl.Name):
                ctrl_rect = ctrl.BoundingRectangle
                if ctrl_rect and rect.top + 400 < ctrl_rect.top < rect.bottom - 300:
                    return ctrl
            for child in ctrl.GetChildren():
                result = find_timestamp_control(child, depth + 1)
                if result:
                    return result
        except:
            pass
        return None

    timestamp_ctrl = find_timestamp_control(sns_window)
    if timestamp_ctrl:
        ts_rect = timestamp_ctrl.BoundingRectangle
        offset = get_config("ui_location.dots_timestamp_offset", 40)
        dots_x = ts_rect.right + offset
        dots_y = (ts_rect.top + ts_rect.bottom) // 2
        print(f"[OK] 时间戳定位成功: '{timestamp_ctrl.Name}' @ ({dots_x}, {dots_y})")
        return (dots_x, dots_y)

    return None


def find_dots_button_hybrid(sns_window):
    """混合定位策略 - 优先级: 删除按钮定位 > 时间戳 > 坐标后备"""
    rect = sns_window.BoundingRectangle

    # 1. 通过删除按钮（垃圾桶）定位
    print("[1] 尝试通过删除按钮定位...")
    pos = find_dots_by_delete_btn(sns_window)
    if pos:
        return pos

    # 2. 时间戳相对定位
    print("[2] 尝试时间戳相对定位...")
    pos = find_dots_by_timestamp(sns_window)
    if pos:
        return pos

    # 3. 坐标后备
    print("[3] 使用坐标后备...")
    if rect:
        right_offset = get_config("ui_location.dots_btn_right_offset", 55)
        top_offset = get_config("ui_location.dots_btn_top_offset", 864)
        return (rect.right - right_offset, rect.top + top_offset)

    return None


def test_dots_flow():
    """测试完整流程"""
    print("=" * 60)
    print("测试 '...' 按钮流程")
    print("请确保朋友圈详情页已打开")
    print("=" * 60)
    print("\n5 秒后开始...\n")
    time.sleep(5)

    # 获取窗口
    sns_window = get_sns_window()
    if not sns_window:
        print("[ERROR] 未找到朋友圈窗口")
        return False

    rect = sns_window.BoundingRectangle
    print(f"[INFO] 窗口位置: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")

    # Step 1: 点击 "..." 按钮
    print("\n--- Step 1: 点击 '...' 按钮 ---")
    dots_pos = find_dots_button_hybrid(sns_window)
    if dots_pos:
        print(f"[OK] 定位成功: {dots_pos}")
        pyautogui.click(dots_pos[0], dots_pos[1])
        print("[OK] 已点击 '...' 按钮")
    else:
        print("[ERROR] 无法定位 '...' 按钮")
        return False

    time.sleep(0.5)

    # Step 2: 点击 "评论" 按钮
    print("\n--- Step 2: 点击 '评论' 按钮 ---")
    comment_btn = sns_window.TextControl(searchDepth=20, Name="评论")
    if comment_btn.Exists(2, 0):
        comment_btn.Click()
        print("[OK] 已点击 '评论' 按钮 (UI自动化)")
    else:
        comment_btn = sns_window.ButtonControl(searchDepth=20, Name="评论")
        if comment_btn.Exists(1, 0):
            comment_btn.Click()
            print("[OK] 已点击 '评论' 按钮 (ButtonControl)")
        else:
            # 坐标后备
            if dots_pos:
                pyautogui.click(dots_pos[0] - 90, dots_pos[1])
                print(f"[OK] 已点击 '评论' 按钮 (坐标后备: {dots_pos[0] - 90}, {dots_pos[1]})")
            else:
                print("[ERROR] 未找到 '评论' 按钮")
                return False

    time.sleep(0.5)

    # Step 3: 输入产品链接
    print("\n--- Step 3: 输入产品链接 ---")
    print(f"[INFO] 链接: {TEST_PRODUCT_LINK}")
    pyperclip.copy(TEST_PRODUCT_LINK)
    time.sleep(0.2)
    pyautogui.hotkey('ctrl', 'v')
    print("[OK] 已粘贴产品链接")

    time.sleep(0.5)

    # Step 4: 点击 "发送" 按钮
    print("\n--- Step 4: 点击 '发送' 按钮 ---")

    # 尝试图像识别
    send_pos = None
    for confidence in [0.8, 0.6, 0.4]:
        send_pos = find_button_by_image("send_btn.png", confidence=confidence)
        if send_pos:
            print(f"[OK] 图像识别找到发送按钮 (confidence={confidence})")
            break

    if send_pos:
        pyautogui.click(send_pos[0], send_pos[1])
        print(f"[OK] 已点击 '发送' 按钮 @ {send_pos}")
    else:
        # 坐标后备
        rect = sns_window.BoundingRectangle
        if rect:
            win_height = rect.bottom - rect.top
            send_x_offset = get_config("ui_location.send_btn_x_offset", 80)
            send_y_ratio = get_config("ui_location.send_btn_y_ratio", 0.52)
            send_x = rect.right - send_x_offset
            send_y = rect.top + int(win_height * send_y_ratio)
            pyautogui.click(send_x, send_y)
            print(f"[OK] 已点击 '发送' 按钮 (坐标后备: {send_x}, {send_y})")

    time.sleep(1)

    # Step 5: 关闭窗口（可选）
    print("\n--- Step 5: 关闭窗口 (跳过) ---")
    print("[INFO] 跳过关闭窗口，以便检查结果")

    # 如需关闭窗口，取消下面注释
    # rect = sns_window.BoundingRectangle
    # if rect:
    #     close_offset = get_config("ui_location.close_btn_offset", 15)
    #     close_x = rect.right - close_offset
    #     close_y = rect.top + close_offset
    #     pyautogui.click(close_x, close_y)
    #     print(f"[OK] 已点击关闭按钮 ({close_x}, {close_y})")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    test_dots_flow()
