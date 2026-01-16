# -*- coding: utf-8 -*-
"""
检测朋友圈详情窗口中的评论按钮（两个点 ..）
"""
import uiautomation as auto
import sys
sys.stdout.reconfigure(encoding='utf-8')

auto.SetGlobalSearchTimeout(3)

# 1) 找到详情窗口（朋友圈详情页标题是"详情"）
print("=" * 60)
print("1. 查找朋友圈详情窗口")
print("=" * 60)

# 尝试多种方式查找
win = None
for name in ["详情", "朋友圈"]:
    win = auto.WindowControl(searchDepth=1, SubName=name)
    if win.Exists(1, 0):
        print(f"✓ 找到窗口: {win.Name}")
        break

if not win or not win.Exists(0.5, 0):
    print("❌ 未找到朋友圈详情窗口")
    raise SystemExit(1)

rect = win.BoundingRectangle
print(f"  类名: {win.ClassName}")
print(f"  位置: ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})")
print(f"  大小: {rect.right - rect.left} x {rect.bottom - rect.top}")

# 2) 深度遍历所有控件
print("\n" + "=" * 60)
print("2. 深度遍历所有控件（寻找按钮）")
print("=" * 60)

all_controls = []

def collect_all(ctrl, depth=0, max_depth=20, path=""):
    if depth > max_depth:
        return
    try:
        rect = ctrl.BoundingRectangle
        if rect and rect.right > rect.left and rect.bottom > rect.top:
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            all_controls.append({
                'ctrl': ctrl,
                'type': ctrl.ControlTypeName,
                'class': ctrl.ClassName,
                'name': ctrl.Name,
                'auto_id': getattr(ctrl, 'AutomationId', ''),
                'rect': rect,
                'width': width,
                'height': height,
                'depth': depth,
                'path': path
            })
    except Exception:
        pass

    try:
        children = ctrl.GetChildren()
        for i, c in enumerate(children):
            collect_all(c, depth+1, max_depth, f"{path}/{i}")
    except Exception:
        pass

collect_all(win, 0, 20, "")

print(f"总共找到 {len(all_controls)} 个控件")

# 3) 查找可能的按钮控件
print("\n" + "=" * 60)
print("3. 所有 Button 类型控件")
print("=" * 60)

buttons = [c for c in all_controls if 'Button' in c['type']]
if buttons:
    for i, btn in enumerate(buttons, 1):
        r = btn['rect']
        print(f"{i}. {btn['type']} | {btn['class']} | '{btn['name']}' | "
              f"({r.left},{r.top},{r.right},{r.bottom}) | {btn['width']}x{btn['height']}")
else:
    print("未找到 Button 控件")

# 4) 查找右下角区域的控件（评论按钮位置）
print("\n" + "=" * 60)
print("4. 右下角区域控件（可能是评论按钮）")
print("=" * 60)

win_rect = win.BoundingRectangle
# 评论按钮通常在：窗口右侧 80% 以后，垂直位置在内容区域
right_threshold = win_rect.left + (win_rect.right - win_rect.left) * 0.7

right_controls = [c for c in all_controls
                  if c['rect'].left > right_threshold
                  and c['width'] < 100 and c['height'] < 100  # 小控件
                  and c['width'] > 5 and c['height'] > 5]  # 排除太小的

right_controls.sort(key=lambda x: x['rect'].top)

if right_controls:
    for i, item in enumerate(right_controls[:10], 1):
        r = item['rect']
        print(f"{i}. {item['type']:20} | {item['class']:25} | '{item['name'][:15]}' | "
              f"({r.left},{r.top},{r.right},{r.bottom}) | {item['width']}x{item['height']}")
else:
    print("未找到右侧小控件")

# 5) 查找所有小型控件（可能是图标/按钮）
print("\n" + "=" * 60)
print("5. 所有小型控件 (20-60px，可能是图标按钮)")
print("=" * 60)

small_controls = [c for c in all_controls
                  if 15 <= c['width'] <= 80
                  and 15 <= c['height'] <= 80]

# 按位置排序（从上到下，从左到右）
small_controls.sort(key=lambda x: (x['rect'].top, x['rect'].left))

if small_controls:
    for i, item in enumerate(small_controls[:15], 1):
        r = item['rect']
        print(f"{i:2}. {item['type']:20} | {item['class']:20} | '{item['name'][:10] if item['name'] else ''}' | "
              f"({r.left},{r.top},{r.right},{r.bottom}) | {item['width']}x{item['height']}")
else:
    print("未找到小型控件")

# 6) 打印完整控件树（前3层）
print("\n" + "=" * 60)
print("6. 完整控件树（前4层）")
print("=" * 60)

def dump_tree(ctrl, depth=0, max_depth=4):
    if depth > max_depth:
        return
    try:
        rect = ctrl.BoundingRectangle
        rect_str = f"({rect.left},{rect.top},{rect.right},{rect.bottom})"
        size = f"{rect.right - rect.left}x{rect.bottom - rect.top}"
    except Exception:
        rect_str = "(no-rect)"
        size = "?"

    name = ctrl.Name[:20] if ctrl.Name else ""
    indent = "  " * depth
    print(f"{indent}{ctrl.ControlTypeName} | {ctrl.ClassName} | '{name}' | {rect_str} | {size}")

    try:
        for c in ctrl.GetChildren():
            dump_tree(c, depth+1, max_depth)
    except Exception:
        pass

dump_tree(win, 0, 4)

# 7) 结论
print("\n" + "=" * 60)
print("7. 分析结论")
print("=" * 60)

if len(all_controls) <= 2:
    print("⚠️ 窗口内部 UIA 结构稀疏，无法通过 UIA 找到评论按钮")
    print("\n建议方案：使用坐标定位")

    # 计算评论按钮的大致位置
    # 从截图看，按钮在窗口右侧，时间戳同一行
    btn_x = win_rect.right - 50  # 距离右边约 50px
    btn_y = win_rect.top + int((win_rect.bottom - win_rect.top) * 0.75)  # 约 75% 高度

    print(f"\n评论按钮预估坐标:")
    print(f"  X: {btn_x} (窗口右侧 -50px)")
    print(f"  Y: {btn_y} (窗口 75% 高度)")
    print(f"\n  auto.Click({btn_x}, {btn_y})")
else:
    # 尝试找出最可能的评论按钮
    # 特征：小控件，在右侧，可能是 Button 或 Image
    candidates = [c for c in all_controls
                  if c['rect'].left > right_threshold
                  and 20 <= c['width'] <= 60
                  and 20 <= c['height'] <= 60]

    if candidates:
        print("找到可能的评论按钮候选:")
        for c in candidates:
            r = c['rect']
            print(f"  {c['type']} | {c['class']} | '{c['name']}' | "
                  f"({r.left},{r.top},{r.right},{r.bottom})")
    else:
        print("未能定位到评论按钮，建议使用坐标方式")
