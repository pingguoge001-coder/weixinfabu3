# -*- coding: utf-8 -*-
"""Detect the Moments (朋友圈) entry/button via UIA and print candidates."""
import argparse
import io
import sys
from typing import Iterable, Optional, Tuple

import uiautomation as auto

from core.wechat_controller import get_wechat_controller


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TARGET_NAMES = [
    "\u670b\u53cb\u5708",  # 朋友圈
    "Moments",
    "\u53d1\u73b0",        # 发现
    "Discover",
]
TAB_ITEM_CLASS = "mmui::XTabBarItem"


def get_rect(control: auto.Control) -> Optional[Tuple[int, int, int, int]]:
    try:
        rect = control.BoundingRectangle
        return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        return None


def walk_controls(control: auto.Control, max_depth: int):
    stack = [(control, 0)]
    while stack:
        node, depth = stack.pop()
        yield node, depth
        if depth >= max_depth:
            continue
        try:
            children = node.GetChildren()
        except Exception:
            continue
        for child in reversed(children):
            stack.append((child, depth + 1))


def find_by_name(window: auto.Control, name: str, search_depth: int) -> Optional[auto.Control]:
    try:
        ctrl = window.Control(searchDepth=search_depth, Name=name)
        if ctrl.Exists(0, 0):
            return ctrl
    except Exception:
        pass
    for cls in (auto.ButtonControl, auto.TextControl, auto.TabItemControl, auto.ListItemControl, auto.CustomControl):
        try:
            ctrl = cls(parent=window, searchDepth=search_depth, Name=name)
            if ctrl.Exists(0, 0):
                return ctrl
        except Exception:
            continue
    return None


def print_control(label: str, control: auto.Control) -> None:
    rect = get_rect(control)
    rect_str = f"{rect}" if rect else "(no-rect)"
    print(f"{label}: name='{control.Name}' class='{control.ClassName}' type='{control.ControlTypeName}' rect={rect_str}")


def print_candidates(window: auto.Control, max_depth: int, left_max: int) -> None:
    print("\nCandidates with name match:")
    found_any = False
    for ctrl, _ in walk_controls(window, max_depth):
        name = ctrl.Name or ""
        if name and any(key in name for key in TARGET_NAMES):
            found_any = True
            print_control("  match", ctrl)
    if not found_any:
        print("  (none)")

    print("\nLeft-side controls (possible nav items):")
    left_candidates = []
    for ctrl, _ in walk_controls(window, max_depth):
        rect = get_rect(ctrl)
        if not rect:
            continue
        left, top, right, bottom = rect
        if left <= left_max and (right - left) >= 30 and (bottom - top) >= 20:
            left_candidates.append(ctrl)

    if not left_candidates:
        print("  (none)")
        return

    for ctrl in left_candidates[:30]:
        print_control("  left", ctrl)


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect Moments entry/button by UIA.")
    parser.add_argument("--search-depth", type=int, default=8)
    parser.add_argument("--max-depth", type=int, default=8)
    parser.add_argument("--left-max", type=int, default=260)
    args = parser.parse_args()

    controller = get_wechat_controller()
    window = controller.get_main_window()

    print("=" * 70)
    print("WeChat Moments Button Detection")
    print("=" * 70)

    if not window or not window.Exists(0, 0):
        print("Main window not found.")
        return 1

    print(f"window: name='{window.Name}' class='{window.ClassName}'")

    found = None
    for name in TARGET_NAMES:
        ctrl = find_by_name(window, name, search_depth=args.search_depth)
        if ctrl:
            found = ctrl
            print_control("found", ctrl)
            break

    if not found:
        print("Direct name lookup failed.")
        print_candidates(window, max_depth=args.max_depth, left_max=args.left_max)

    print("\nTabBar items by class:")
    tab_found = False
    for ctrl, _ in walk_controls(window, args.max_depth):
        if (ctrl.ClassName or "") == TAB_ITEM_CLASS:
            tab_found = True
            print_control("  tab", ctrl)
    if not tab_found:
        print("  (none)")

    return 0 if found else 2


if __name__ == "__main__":
    raise SystemExit(main())
