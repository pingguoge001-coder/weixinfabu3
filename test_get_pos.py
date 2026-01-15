# -*- coding: utf-8 -*-
"""
获取鼠标位置 - 按空格记录
"""
import time
import pyautogui
import keyboard
import uiautomation as auto

sns = auto.WindowControl(searchDepth=1, ClassName="mmui::SNSWindow")
if sns.Exists(2, 0):
    rect = sns.BoundingRectangle
    print(f"Window: ({rect.left}, {rect.top}) - ({rect.right}, {rect.bottom})")
else:
    print("Window not found")
    rect = None

print("\nMove mouse to '...' button, press SPACE to record, Q to quit\n")

while True:
    if keyboard.is_pressed('space'):
        x, y = pyautogui.position()
        if rect:
            print(f"Position: ({x}, {y}) | Right offset: {rect.right - x}, Top offset: {y - rect.top}")
        else:
            print(f"Position: ({x}, {y})")
        time.sleep(0.3)
    if keyboard.is_pressed('q'):
        break
    time.sleep(0.05)
