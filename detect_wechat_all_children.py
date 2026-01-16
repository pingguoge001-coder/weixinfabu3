# -*- coding: utf-8 -*-
"""
深度检测微信主窗口内的所有子窗口和控件
"""
import uiautomation as auto
import sys
sys.stdout.reconfigure(encoding='utf-8')

auto.SetGlobalSearchTimeout(2)

print("=" * 60)
print("检测微信主窗口及其子窗口")
print("=" * 60)

# 1. 找到微信主窗口
win = auto.WindowControl(searchDepth=1, Name="微信")
if not win.Exists(1, 0):
    win = auto.WindowControl(searchDepth=1, ClassName="Qt51514QWindowIcon")

if not win.Exists(1, 0):
    print("❌ 未找到微信窗口")
    raise SystemExit(1)

rect = win.BoundingRectangle
print(f"✓ 微信主窗口: {win.Name}")
print(f"  位置: ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})")

# 2. 查找所有子窗口（包括弹出窗口）
print("\n" + "=" * 60)
print("查找所有 Qt 类名的顶层窗口（可能是微信的子窗口）")
print("=" * 60)

desktop = auto.GetRootControl()
all_windows = desktop.GetChildren()

qt_windows = []
for w in all_windows:
    try:
        if "Qt" in (w.ClassName or ""):
            r = w.BoundingRectangle
            qt_windows.append({
                'name': w.Name,
                'class': w.ClassName,
                'rect': r,
                'size': f"{r.right - r.left}x{r.bottom - r.top}" if r else "?"
            })
    except Exception:
        pass

print(f"找到 {len(qt_windows)} 个 Qt 窗口:")
for i, w in enumerate(qt_windows, 1):
    r = w['rect']
    print(f"{i}. '{w['name']}' | {w['class']} | ({r.left},{r.top},{r.right},{r.bottom}) | {w['size']}")

# 3. 检查微信主窗口内的所有控件
print("\n" + "=" * 60)
print("微信主窗口内的所有控件（深度遍历）")
print("=" * 60)

all_ctrls = []
def collect(ctrl, depth=0, max_depth=20):
    if depth > max_depth:
        return
    try:
        r = ctrl.BoundingRectangle
        if r and r.right > r.left and r.bottom > r.top:
            all_ctrls.append({
                'type': ctrl.ControlTypeName,
                'class': ctrl.ClassName,
                'name': ctrl.Name,
                'rect': r,
                'depth': depth
            })
    except Exception:
        pass
    try:
        for c in ctrl.GetChildren():
            collect(c, depth+1, max_depth)
    except Exception:
        pass

collect(win, 0, 20)
print(f"总共找到 {len(all_ctrls)} 个控件")

# 按类型统计
type_count = {}
for c in all_ctrls:
    t = c['type']
    type_count[t] = type_count.get(t, 0) + 1

print("\n控件类型统计:")
for t, count in sorted(type_count.items(), key=lambda x: -x[1]):
    print(f"  {t}: {count}")

# 4. 查找可能是按钮的控件
print("\n" + "=" * 60)
print("可能的按钮控件")
print("=" * 60)

buttons = [c for c in all_ctrls if 'Button' in c['type'] or 'Image' in c['type']]
if buttons:
    for c in buttons[:20]:
        r = c['rect']
        print(f"  {c['type']} | '{c['name'][:20] if c['name'] else ''}' | ({r.left},{r.top},{r.right},{r.bottom})")
else:
    print("未找到按钮控件")

# 5. 显示控件树
print("\n" + "=" * 60)
print("控件树（前6层）")
print("=" * 60)

def dump(ctrl, depth=0, max_depth=6):
    if depth > max_depth:
        return
    try:
        r = ctrl.BoundingRectangle
        name = ctrl.Name[:15] if ctrl.Name else ""
        indent = "  " * depth
        size = f"{r.right - r.left}x{r.bottom - r.top}" if r else "?"
        print(f"{indent}{ctrl.ControlTypeName} | {ctrl.ClassName[:20]} | '{name}' | {size}")
    except Exception:
        pass
    try:
        for c in ctrl.GetChildren():
            dump(c, depth+1, max_depth)
    except Exception:
        pass

dump(win, 0, 6)

# 6. 结论
print("\n" + "=" * 60)
print("结论")
print("=" * 60)

if len(all_ctrls) <= 5:
    print("⚠️ 微信窗口 UIA 结构极度稀疏")
    print("   微信使用 Qt 自绘界面，无法通过 UIA 访问内部元素")
    print("\n✗ UIA 方式不可行")
    print("✓ 建议使用：图像识别 或 坐标定位")
