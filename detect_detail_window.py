# -*- coding: utf-8 -*-
"""
检测所有微信相关窗口，特别是"详情"窗口
"""
import uiautomation as auto
import sys
sys.stdout.reconfigure(encoding='utf-8')

auto.SetGlobalSearchTimeout(2)

print("=" * 60)
print("查找所有微信相关窗口")
print("=" * 60)

# 查找所有顶层窗口
desktop = auto.GetRootControl()
all_windows = desktop.GetChildren()

wechat_windows = []
for win in all_windows:
    try:
        name = win.Name or ""
        classname = win.ClassName or ""
        # 微信窗口通常使用 Qt 类名
        if "Qt" in classname or "WeChat" in classname or "Weixin" in name:
            rect = win.BoundingRectangle
            wechat_windows.append({
                'name': name,
                'class': classname,
                'rect': rect,
                'ctrl': win
            })
        # 也检查特定名称
        if name in ["详情", "朋友圈", "微信"] or "朋友" in name:
            rect = win.BoundingRectangle
            wechat_windows.append({
                'name': name,
                'class': classname,
                'rect': rect,
                'ctrl': win
            })
    except Exception:
        pass

# 去重
seen = set()
unique_windows = []
for w in wechat_windows:
    key = (w['name'], w['class'], w['rect'].left if w['rect'] else 0)
    if key not in seen:
        seen.add(key)
        unique_windows.append(w)

print(f"找到 {len(unique_windows)} 个微信相关窗口:\n")

for i, w in enumerate(unique_windows, 1):
    r = w['rect']
    if r:
        print(f"{i}. 名称: '{w['name']}'")
        print(f"   类名: {w['class']}")
        print(f"   位置: ({r.left}, {r.top}, {r.right}, {r.bottom})")
        print(f"   大小: {r.right - r.left} x {r.bottom - r.top}")
        print()

# 专门查找"详情"窗口
print("=" * 60)
print("专门查找'详情'窗口")
print("=" * 60)

detail_win = auto.WindowControl(searchDepth=1, Name="详情")
if detail_win.Exists(1, 0):
    print(f"✓ 找到'详情'窗口")
    rect = detail_win.BoundingRectangle
    print(f"  类名: {detail_win.ClassName}")
    print(f"  位置: ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})")

    # 遍历子控件
    print("\n  子控件树:")
    def dump(ctrl, depth=0, max_depth=5):
        if depth > max_depth:
            return
        try:
            r = ctrl.BoundingRectangle
            name = ctrl.Name[:20] if ctrl.Name else ""
            indent = "  " * (depth + 1)
            print(f"{indent}{ctrl.ControlTypeName} | {ctrl.ClassName} | '{name}' | "
                  f"({r.left},{r.top},{r.right},{r.bottom})")
        except Exception:
            pass
        try:
            for c in ctrl.GetChildren():
                dump(c, depth+1, max_depth)
        except Exception:
            pass
    dump(detail_win, 0, 5)
else:
    print("❌ 未找到名为'详情'的窗口")

# 查找包含"详情"的窗口
print("\n" + "=" * 60)
print("查找包含'详情'的窗口 (SubName)")
print("=" * 60)

detail_win2 = auto.WindowControl(searchDepth=1, SubName="详情")
if detail_win2.Exists(1, 0):
    print(f"✓ 找到包含'详情'的窗口: {detail_win2.Name}")
    rect = detail_win2.BoundingRectangle
    print(f"  类名: {detail_win2.ClassName}")
    print(f"  位置: ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})")
else:
    print("❌ 未找到包含'详情'的窗口")
