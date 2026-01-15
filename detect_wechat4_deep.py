"""深度探测微信 4.0 元素信息"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import uiautomation as auto

print('=' * 70)
print('深度探测微信 4.0 元素')
print('=' * 70)

# 查找微信主窗口
wechat_window = None
for win in auto.GetRootControl().GetChildren():
    name = win.Name or ''
    classname = win.ClassName or ''
    if name == '微信' and 'mmui' in classname:
        wechat_window = win
        break

if not wechat_window:
    print('未找到微信窗口')
    exit(1)

print(f'\n主窗口: {wechat_window.ClassName}')

# 深度遍历，找所有有名字的元素
print('\n' + '=' * 70)
print('所有有名称的元素 (深度5层)')
print('=' * 70)

def find_named_elements(control, depth=0, max_depth=5, results=None):
    if results is None:
        results = []
    if depth >= max_depth:
        return results

    name = control.Name or ''
    classname = control.ClassName or ''
    ctrl_type = control.ControlTypeName

    if name:  # 只记录有名称的元素
        results.append({
            'depth': depth,
            'name': name,
            'class': classname,
            'type': ctrl_type,
            'auto_id': control.AutomationId or ''
        })

    for child in control.GetChildren():
        find_named_elements(child, depth + 1, max_depth, results)

    return results

elements = find_named_elements(wechat_window)

# 按名称排序显示
print(f'\n共找到 {len(elements)} 个有名称的元素:\n')
for elem in sorted(elements, key=lambda x: x['name']):
    indent = '  ' * elem['depth']
    print(f"{indent}[{elem['type']}] \"{elem['name']}\" -> {elem['class']}")

# 查找导航相关元素
print('\n' + '=' * 70)
print('查找导航/标签栏元素')
print('=' * 70)

# 查找所有 TabBarItem
print('\n【所有 TabBarItem 元素】')
tab_items = []
def find_tab_items(control, depth=0, max_depth=10):
    if depth >= max_depth:
        return
    if 'TabBar' in (control.ClassName or ''):
        tab_items.append({
            'name': control.Name or '(无名称)',
            'class': control.ClassName,
            'type': control.ControlTypeName
        })
    for child in control.GetChildren():
        find_tab_items(child, depth + 1, max_depth)

find_tab_items(wechat_window)
for i, item in enumerate(tab_items):
    print(f"  [{i}] {item['type']}: \"{item['name']}\" -> {item['class']}")

# 查找所有按钮
print('\n【所有按钮元素 (前20个)】')
buttons = []
def find_buttons(control, depth=0, max_depth=8):
    if depth >= max_depth:
        return
    if control.ControlTypeName == 'ButtonControl':
        buttons.append({
            'name': control.Name or '(无名称)',
            'class': control.ClassName or '',
        })
    for child in control.GetChildren():
        find_buttons(child, depth + 1, max_depth)

find_buttons(wechat_window)
for i, btn in enumerate(buttons[:20]):
    print(f"  [{i}] \"{btn['name']}\" -> {btn['class']}")

print('\n' + '=' * 70)
print('探测完成')
print('=' * 70)
