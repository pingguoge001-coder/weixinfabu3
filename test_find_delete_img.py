# -*- coding: utf-8 -*-
"""
测试用图像识别找垃圾桶按钮
"""
import pyautogui
import uiautomation as auto
from pathlib import Path

TEMPLATE = Path(__file__).parent / "data" / "templates" / "delete_btn.png"

sns = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if not sns.Exists(3, 1):
    print("Window not found")
    exit()

rect = sns.BoundingRectangle
print(f"Window: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")
print(f"Template: {TEMPLATE}")
print(f"Exists: {TEMPLATE.exists()}")

# 测试不同置信度
for confidence in [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]:
    try:
        location = pyautogui.locateOnScreen(str(TEMPLATE), confidence=confidence)
        if location:
            center = pyautogui.center(location)
            print(f"[OK] confidence={confidence}: Found at ({center.x}, {center.y})")
            print(f"     Y offset from top: {center.y - rect.top}")
            break
        else:
            print(f"[--] confidence={confidence}: Not found")
    except Exception as e:
        print(f"[ERR] confidence={confidence}: {e}")
