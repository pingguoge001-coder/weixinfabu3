# -*- coding: utf-8 -*-
import uiautomation as auto
import sys

# 设置控制台编码
sys.stdout.reconfigure(encoding='utf-8')

auto.SetGlobalSearchTimeout(3)

# 1) 找到朋友圈窗口
win = auto.WindowControl(searchDepth=1, SubName="朋友圈")
print("=" * 60)
print("1. 朋友圈窗口基本信息")
print("=" * 60)
print(f"窗口存在: {win.Exists(1, 0)}")
if not win.Exists(1, 0):
    raise SystemExit("朋友圈窗口未找到")

try:
    rect = win.BoundingRectangle
    print(f"窗口名称: {win.Name}")
    print(f"窗口类名: {win.ClassName}")
    print(f"控件类型: {win.ControlTypeName}")
    print(f"窗口位置: ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})")
    print(f"窗口大小: {rect.right - rect.left} x {rect.bottom - rect.top}")
except Exception as e:
    print(f"获取窗口信息失败: {e}")

# 2) 打印更深的控件树（前5层）
print("\n" + "=" * 60)
print("2. 朋友圈窗口子控件树（前5层）")
print("=" * 60)

def dump(ctrl, depth=0, max_depth=5):
    if depth > max_depth:
        return
    try:
        rect = ctrl.BoundingRectangle
        rect_str = f"({rect.left},{rect.top},{rect.right},{rect.bottom})"
        size = f"{rect.right - rect.left}x{rect.bottom - rect.top}"
    except Exception:
        rect_str = "(no-rect)"
        size = "?"

    name = ctrl.Name[:30] if ctrl.Name else ""
    indent = "  " * depth
    print(f"{indent}{ctrl.ControlTypeName} | {ctrl.ClassName} | '{name}' | {rect_str} | {size}")

    try:
        children = ctrl.GetChildren()
        for c in children:
            dump(c, depth+1, max_depth)
    except Exception as e:
        print(f"{indent}  [获取子控件失败: {e}]")

dump(win, 0, 5)

# 3) 收集所有控件（不限类型），找候选项
print("\n" + "=" * 60)
print("3. 所有控件按 top 排序（前20个有效控件）")
print("=" * 60)

all_controls = []
def collect_all(ctrl, depth=0, max_depth=15):
    if depth > max_depth:
        return
    try:
        rect = ctrl.BoundingRectangle
        # 过滤掉无效矩形和太小的控件
        if rect and rect.right > rect.left and rect.bottom > rect.top:
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width > 10 and height > 10:  # 至少 10x10 像素
                all_controls.append({
                    'top': rect.top,
                    'ctrl': ctrl,
                    'rect': rect,
                    'depth': depth,
                    'type': ctrl.ControlTypeName,
                    'class': ctrl.ClassName,
                    'name': ctrl.Name
                })
    except Exception:
        pass

    try:
        for c in ctrl.GetChildren():
            collect_all(c, depth+1, max_depth)
    except Exception:
        pass

collect_all(win, 0, 15)

# 按 top 排序
all_controls.sort(key=lambda x: x['top'])

for i, item in enumerate(all_controls[:20], 1):
    r = item['rect']
    name = item['name'][:20] if item['name'] else ""
    print(f"{i:2}. [{item['depth']}] {item['type']:20} | {item['class']:25} | '{name}' | "
          f"({r.left},{r.top},{r.right},{r.bottom}) | {r.right-r.left}x{r.bottom-r.top}")

# 4) 专门找 ListItem/List 类型
print("\n" + "=" * 60)
print("4. 列表相关控件 (ListItem/List/DataGrid)")
print("=" * 60)

list_controls = [c for c in all_controls if 'List' in c['type'] or 'Grid' in c['type'] or 'Item' in c['type']]
if list_controls:
    for i, item in enumerate(list_controls[:10], 1):
        r = item['rect']
        name = item['name'][:30] if item['name'] else ""
        print(f"{i}. {item['type']} | {item['class']} | '{name}' | ({r.left},{r.top},{r.right},{r.bottom})")
else:
    print("未找到列表相关控件")

# 5) 找 Pane 控件（可能是内容区域）
print("\n" + "=" * 60)
print("5. Pane 控件（按大小排序，可能是内容区域）")
print("=" * 60)

pane_controls = [c for c in all_controls if 'Pane' in c['type']]
# 按面积排序
pane_controls.sort(key=lambda x: (x['rect'].right - x['rect'].left) * (x['rect'].bottom - x['rect'].top), reverse=True)

for i, item in enumerate(pane_controls[:10], 1):
    r = item['rect']
    area = (r.right - r.left) * (r.bottom - r.top)
    name = item['name'][:20] if item['name'] else ""
    print(f"{i}. {item['class']:25} | '{name}' | ({r.left},{r.top},{r.right},{r.bottom}) | "
          f"{r.right-r.left}x{r.bottom-r.top} | 面积:{area}")

# 6) 尝试用 FindAll 查找
print("\n" + "=" * 60)
print("6. 使用 FindAll 查找特定控件类型")
print("=" * 60)

try:
    # 查找所有 TextControl
    texts = win.GetChildren()
    print(f"直接子控件数量: {len(texts)}")

    # 使用 Control 遍历
    all_by_find = []
    for ctrl_type in ['ButtonControl', 'TextControl', 'ImageControl', 'CustomControl']:
        try:
            found = win.GetChildren()
            print(f"GetChildren 找到: {len(found)} 个")
            break
        except Exception as e:
            print(f"查找 {ctrl_type} 失败: {e}")
except Exception as e:
    print(f"FindAll 查找失败: {e}")

# 7) 结论和建议
print("\n" + "=" * 60)
print("7. 分析结论和建议")
print("=" * 60)

total = len(all_controls)
print(f"总共找到有效控件: {total} 个")

if total <= 2:
    print("\n⚠️ 警告: 朋友圈窗口的 UIA 结构非常稀疏！")
    print("   微信可能使用了自绘控件或 DirectUI，UIA 无法正确识别内部元素。")
    print("\n建议方案:")
    print("   1. 【推荐】使用图像识别 + 坐标点击方式")
    print("   2. 使用相对窗口坐标定位（窗口位置 + 固定偏移）")
    print("   3. 尝试使用 Windows Accessibility Insights 工具进一步分析")
    print("   4. 考虑使用 pywinauto 的 backend='uia' 或 'win32' 模式")
else:
    print("\n找到了一些控件，可以尝试基于 UIA 定位。")
    # 找最可能的第一条朋友圈
    # 排除窗口本身，找内容区域内最上面的大控件
    win_rect = win.BoundingRectangle
    content_controls = [c for c in all_controls
                        if c['rect'].top > win_rect.top + 50  # 排除标题栏
                        and c['rect'].left > win_rect.left + 10
                        and (c['rect'].right - c['rect'].left) > 100]  # 有一定宽度

    if content_controls:
        first = content_controls[0]
        r = first['rect']
        print(f"\n可能的第一条朋友圈:")
        print(f"   ClassName: {first['class']}")
        print(f"   Name: {first['name']}")
        print(f"   ControlType: {first['type']}")
        print(f"   Rect: ({r.left}, {r.top}, {r.right}, {r.bottom})")
