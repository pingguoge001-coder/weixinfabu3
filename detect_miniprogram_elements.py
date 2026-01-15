# -*- coding: utf-8 -*-
"""探测小程序内部元素"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import uiautomation as auto
import win32gui
import win32process
import psutil

def find_miniprogram_hwnd():
    result = None
    def callback(hwnd, _):
        nonlocal result
        if win32gui.IsWindowVisible(hwnd):
            try:
                class_name = win32gui.GetClassName(hwnd)
                if class_name == 'Chrome_WidgetWin_0':
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc = psutil.Process(pid)
                    if proc.name().lower() == 'wechatappex.exe':
                        result = hwnd
                        return False
            except:
                pass
        return True
    try:
        win32gui.EnumWindows(callback, None)
    except:
        pass
    return result

hwnd = find_miniprogram_hwnd()
print(f'MiniProgram hwnd: {hwnd}')

if hwnd:
    window = auto.ControlFromHandle(hwnd)
    print(f'Window Name: {window.Name}')
    print(f'Window Class: {window.ClassName}')
    rect = window.BoundingRectangle
    print(f'Window Rect: ({rect.left}, {rect.top}) - {rect.width()}x{rect.height()}')
    print()

    # 递归打印所有子控件
    print('=' * 60)
    print('All child controls (depth=10):')
    print('=' * 60)

    def print_children(control, depth=0, max_depth=10):
        if depth > max_depth:
            return

        try:
            children = control.GetChildren()
            for child in children:
                indent = '  ' * depth
                name = child.Name or ''
                ctrl_type = child.ControlTypeName
                class_name = child.ClassName or ''

                try:
                    rect = child.BoundingRectangle
                    pos = f'({rect.left},{rect.top}) {rect.width()}x{rect.height()}'
                except:
                    pos = '(unknown)'

                # 只打印有名字或有位置的控件
                if name or (rect.width() > 0 and rect.height() > 0):
                    print(f'{indent}[{ctrl_type}] "{name}" {class_name} {pos}')

                print_children(child, depth + 1, max_depth)
        except Exception as e:
            pass

    print_children(window)

    print()
    print('=' * 60)
    print('Looking for clickable elements near top-right (search area):')
    print('=' * 60)

    # 搜索按钮通常在窗口右上角
    # 窗口位置: (1630, 121), 大小: 585x1085
    # 搜索按钮大概在 (1630+500, 121+100) 附近

    # 查找所有 ButtonControl
    print('\nAll Buttons:')
    for i in range(50):
        try:
            btn = window.ButtonControl(searchDepth=20, foundIndex=i+1)
            if btn.Exists(0, 0):
                name = btn.Name or '(no name)'
                rect = btn.BoundingRectangle
                auto_id = btn.AutomationId or ''
                print(f'  [{i+1}] Name="{name}" AutoId="{auto_id}" Pos=({rect.left},{rect.top}) Size={rect.width()}x{rect.height()}')
        except:
            break

    # 查找所有可点击的控件
    print('\nAll Controls with position:')
    count = 0
    for i in range(200):
        try:
            ctrl = window.Control(searchDepth=20, foundIndex=i+1)
            if ctrl.Exists(0, 0):
                rect = ctrl.BoundingRectangle
                if rect.width() > 10 and rect.height() > 10 and rect.left > 0:
                    count += 1
                    name = ctrl.Name or ''
                    ctrl_type = ctrl.ControlTypeName
                    print(f'  [{count}] {ctrl_type} "{name}" ({rect.left},{rect.top}) {rect.width()}x{rect.height()}')
                    if count >= 30:
                        break
        except:
            break

print('\nDone.')
