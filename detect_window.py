# -*- coding: utf-8 -*-
"""通过进程和win32查找所有窗口"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ctypes
from ctypes import wintypes
import win32gui
import win32process
import psutil

print("="*70)
print("Window Detection via Win32 API")
print("="*70 + "\n")

# 存储所有窗口
all_windows = []

def enum_windows_callback(hwnd, _):
    """枚举窗口回调"""
    if win32gui.IsWindowVisible(hwnd):
        try:
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            rect = win32gui.GetWindowRect(hwnd)

            x, y, x2, y2 = rect
            width = x2 - x
            height = y2 - y

            # 获取进程信息
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                process = psutil.Process(pid)
                proc_name = process.name()
            except:
                proc_name = "unknown"

            if width > 100 and height > 100:
                all_windows.append({
                    'hwnd': hwnd,
                    'title': title,
                    'class': class_name,
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                    'pid': pid,
                    'process': proc_name
                })
        except:
            pass
    return True

# 枚举所有窗口
win32gui.EnumWindows(enum_windows_callback, None)

print(f"Total visible windows: {len(all_windows)}\n")

# 找微信相关的窗口
print("="*70)
print("WECHAT RELATED WINDOWS:")
print("="*70 + "\n")

wechat_windows = []
for w in all_windows:
    proc_lower = w['process'].lower()
    if 'wechat' in proc_lower or 'mmui' in w['class'].lower():
        wechat_windows.append(w)
        print(f"[hwnd={w['hwnd']}]")
        print(f"  Process: {w['process']} (PID: {w['pid']})")
        print(f"  Class: {w['class']}")
        print(f"  Title: {w['title'][:50] if w['title'] else '(empty)'}")
        print(f"  Position: ({w['x']}, {w['y']})")
        print(f"  Size: {w['width']} x {w['height']}")
        print()

# 寻找可能的小程序窗口（苹果哥相关）
print("="*70)
print("SEARCHING FOR MINIPROGRAM (苹果哥):")
print("="*70 + "\n")

for w in all_windows:
    title = w['title']
    if any(kw in title for kw in ['苹果哥', '花城', '农夫', '小程序']):
        print(f">>> FOUND MINIPROGRAM!")
        print(f"  hwnd: {w['hwnd']}")
        print(f"  Process: {w['process']}")
        print(f"  Class: {w['class']}")
        print(f"  Title: {title}")
        print(f"  Position: ({w['x']}, {w['y']})")
        print(f"  Size: {w['width']} x {w['height']}")
        print()

# 列出所有窗口供参考
print("="*70)
print("ALL WINDOWS (for reference):")
print("="*70 + "\n")

for w in sorted(all_windows, key=lambda x: x['x']):
    if w['x'] > -100:  # 只显示可见的
        title_short = w['title'][:40] if w['title'] else "(no title)"
        print(f"[{w['process'][:15]:15}] {w['class'][:30]:30} | {title_short}")
        print(f"                  Pos:({w['x']},{w['y']}) Size:{w['width']}x{w['height']}")
        print()

print("="*70)
print("If MiniProgram not found, please ensure it's open and visible.")
print("="*70)
