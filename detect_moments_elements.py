import uiautomation as auto
import time

auto.SetGlobalSearchTimeout(2)

# 1) 找到朋友圈窗口
win = auto.WindowControl(searchDepth=1, SubName="朋友圈")
print("window exists:", win.Exists(1, 0))
if not win.Exists(1, 0):
    raise SystemExit("Moments window not found")

print("window:", win.Name, win.ClassName, win.ControlTypeName)

# 2) 打印前两层树
def dump(ctrl, depth=0, max_depth=2):
    if depth > max_depth:
        return
    try:
        rect = ctrl.BoundingRectangle
        rect_str = f"({rect.left},{rect.top},{rect.right},{rect.bottom})"
    except Exception:
        rect_str = "(no-rect)"
    print("  " * depth + f"{ctrl.ControlTypeName} | {ctrl.ClassName} | {ctrl.Name} | {rect_str}")
    try:
        for c in ctrl.GetChildren():
            dump(c, depth+1, max_depth)
    except Exception:
        pass

dump(win, 0, 2)

# 3) 找候选列表项
candidates = []
def collect(ctrl, depth=0, max_depth=10):
    if depth > max_depth:
        return
    try:
        if ctrl.ControlTypeName in ("ListItemControl","ListControl","PaneControl","GroupControl"):
            rect = ctrl.BoundingRectangle
            candidates.append((rect.top, ctrl, rect))
    except Exception:
        pass
    try:
        for c in ctrl.GetChildren():
            collect(c, depth+1, max_depth)
    except Exception:
        pass

collect(win, 0, 12)
candidates = [c for c in candidates if c[2]]
candidates.sort(key=lambda x: x[0])
print("\nTop candidates:")
for i, (_, c, r) in enumerate(candidates[:5], 1):
    print(i, c.ControlTypeName, c.ClassName, c.Name, f"({r.left},{r.top},{r.right},{r.bottom})")

# 4) 如果有可能的第一条，尝试点击
if candidates:
    first = candidates[0][1]
    print("\nFirst candidate:", first.ControlTypeName, first.ClassName, first.Name)
