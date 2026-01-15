"""探测微信 4.0 窗口和元素信息"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import uiautomation as auto

print('=' * 60)
print('探测微信 4.0 窗口信息')
print('=' * 60)

# 查找所有顶层窗口中包含微信的
found = False
wechat_window = None

for win in auto.GetRootControl().GetChildren():
    name = win.Name or ''
    classname = win.ClassName or ''

    # 匹配微信相关窗口 (排除本项目的窗口)
    if ('微信' in name or 'WeChat' in name or 'wechat' in classname.lower()) and '自动' not in name:
        found = True
        wechat_window = win
        print(f'\n【找到窗口】')
        print(f'  Name: {name}')
        print(f'  ClassName: {classname}')
        print(f'  AutomationId: {win.AutomationId}')
        print(f'  ControlType: {win.ControlTypeName}')
        print(f'  Handle: {win.NativeWindowHandle}')

if not found:
    print('\n未找到微信窗口，请确保微信已打开')
    exit(1)

# 深度遍历元素树
print('\n' + '=' * 60)
print('元素树 (深度3层)')
print('=' * 60)

def print_tree(control, depth=0, max_depth=3):
    if depth >= max_depth:
        return

    indent = '  ' * depth
    name = control.Name or ''
    classname = control.ClassName or ''
    ctrl_type = control.ControlTypeName
    auto_id = control.AutomationId or ''

    # 只打印有意义的信息
    info_parts = [f'{ctrl_type}']
    if name:
        info_parts.append(f'Name="{name[:30]}"')
    if classname:
        info_parts.append(f'Class="{classname}"')
    if auto_id:
        info_parts.append(f'AutoId="{auto_id}"')

    print(f'{indent}├─ {" | ".join(info_parts)}')

    for child in control.GetChildren():
        print_tree(child, depth + 1, max_depth)

print_tree(wechat_window)

# 特别查找关键元素
print('\n' + '=' * 60)
print('查找关键元素')
print('=' * 60)

# 查找 "发现" 按钮
print('\n【查找 "发现" 按钮】')
discover = wechat_window.ButtonControl(searchDepth=10, Name='发现')
if discover.Exists(0, 0):
    print(f'  [OK] 找到! ClassName={discover.ClassName}, AutomationId={discover.AutomationId}')
else:
    print('  [X] 未找到 "发现" 按钮')

# 查找 "朋友圈" 入口
print('\n【查找 "朋友圈" 入口】')
moments = wechat_window.ButtonControl(searchDepth=10, Name='朋友圈')
if moments.Exists(0, 0):
    print(f'  [OK] 找到! ClassName={moments.ClassName}, AutomationId={moments.AutomationId}')
else:
    print('  [X] 未找到 "朋友圈" 入口')

# 查找搜索框
print('\n【查找搜索框】')
search = wechat_window.EditControl(searchDepth=10, Name='搜索')
if search.Exists(0, 0):
    print(f'  [OK] 找到! ClassName={search.ClassName}, AutomationId={search.AutomationId}')
else:
    print('  [X] 未找到搜索框')

print('\n' + '=' * 60)
print('探测完成')
print('=' * 60)
