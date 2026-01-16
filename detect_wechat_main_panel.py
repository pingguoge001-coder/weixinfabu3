# -*- coding: utf-8 -*-
"""Detect WeChat main panel by checking stable UI features."""
import argparse
import io
import os
import sys
from typing import Callable, Iterable, Optional, Tuple

import uiautomation as auto
import win32api
import win32con
import win32process

from core.wechat_controller import get_wechat_controller, WeChatStatus


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TITLE_KEYWORDS = ["\u5fae\u4fe1", "WeChat"]
SEARCH_KEYWORDS = ["\u641c\u7d22", "Search"]
NAV_BUTTON_NAMES = [
    "\u5fae\u4fe1",
    "\u901a\u8baf\u5f55",
    "\u6536\u85cf",
    "\u670b\u53cb\u5708",
    "\u89c6\u9891\u53f7",
    "\u8bbe\u7f6e",
]
V4_MAIN_CLASSES = {"mmui::MainWindow", "Qt51514QWindowIcon"}
PROCESS_NAMES = {"weixin.exe", "wechat.exe", "wechatappex.exe"}
PANE_NAMES = ["Weixin", "微信"]
DEFAULT_MIN_WIDTH = 500
DEFAULT_MIN_HEIGHT = 400


def contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(k in text for k in keywords)


def get_rect(control: auto.Control) -> Optional[Tuple[int, int, int, int]]:
    try:
        rect = control.BoundingRectangle
        return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        return None


def get_process_name(hwnd: int) -> Tuple[str, int]:
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
        return "", 0

    try:
        handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
            False,
            pid,
        )
    except Exception:
        return "", pid

    try:
        path = win32process.GetModuleFileNameEx(handle, 0)
        return os.path.basename(path), pid
    except Exception:
        return "", pid
    finally:
        try:
            win32api.CloseHandle(handle)
        except Exception:
            pass


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


def find_first(control: auto.Control, predicate: Callable[[auto.Control], bool], max_depth: int) -> Optional[auto.Control]:
    for item, _ in walk_controls(control, max_depth):
        try:
            if predicate(item):
                return item
        except Exception:
            continue
    return None


def find_search_box(window: auto.Control, search_depth: int) -> Optional[auto.Control]:
    for keyword in SEARCH_KEYWORDS:
        try:
            box = window.EditControl(searchDepth=search_depth, SubName=keyword)
            if box.Exists(0, 0):
                return box
        except Exception:
            pass
    return None


def count_nav_buttons(window: auto.Control, search_depth: int) -> int:
    count = 0
    for name in NAV_BUTTON_NAMES:
        try:
            btn = window.ButtonControl(searchDepth=search_depth, Name=name)
            if btn.Exists(0, 0):
                count += 1
        except Exception:
            continue
    return count


def find_nav_container(window: auto.Control, max_depth: int) -> Optional[auto.Control]:
    def predicate(ctrl: auto.Control) -> bool:
        class_name = ctrl.ClassName or ""
        return "TabBar" in class_name or "ToolBar" in ctrl.ControlTypeName

    return find_first(window, predicate, max_depth)


def find_weixin_pane(window: auto.Control, max_depth: int) -> Optional[auto.Control]:
    def predicate(ctrl: auto.Control) -> bool:
        if ctrl.ControlTypeName != "PaneControl":
            return False
        name = ctrl.Name or ""
        return contains_any(name, PANE_NAMES)

    return find_first(window, predicate, max_depth)


def find_chat_list(window: auto.Control, max_depth: int) -> Optional[auto.Control]:
    def predicate(ctrl: auto.Control) -> bool:
        if ctrl.ControlTypeName != "ListControl":
            return False
        rect = get_rect(ctrl)
        if not rect:
            return False
        left, top, right, bottom = rect
        return (right - left) >= 200 and (bottom - top) >= 200

    return find_first(window, predicate, max_depth)


def print_tree(window: auto.Control, max_depth: int) -> None:
    for item, depth in walk_controls(window, max_depth):
        indent = "  " * depth
        name = item.Name or ""
        class_name = item.ClassName or ""
        print(f"{indent}[{item.ControlTypeName}] name='{name}' class='{class_name}'")


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect WeChat main panel.")
    parser.add_argument("--search-depth", type=int, default=8)
    parser.add_argument("--tree-depth", type=int, default=2)
    parser.add_argument("--dump-tree", action="store_true")
    parser.add_argument("--min-width", type=int, default=DEFAULT_MIN_WIDTH)
    parser.add_argument("--min-height", type=int, default=DEFAULT_MIN_HEIGHT)
    parser.add_argument("--skip-login-check", action="store_true")
    args = parser.parse_args()

    controller = get_wechat_controller()
    window = controller.find_wechat_window(timeout=5)

    print("=" * 70)
    print("WeChat Main Panel Detection")
    print("=" * 70)

    if not window:
        print("Main window not found.")
        return 1

    class_name = window.ClassName or ""
    title = window.Name or ""
    class_ok = class_name in V4_MAIN_CLASSES
    title_ok = contains_any(title, TITLE_KEYWORDS)

    hwnd = window.NativeWindowHandle
    proc_name, pid = get_process_name(hwnd)
    process_ok = proc_name.lower() in PROCESS_NAMES if proc_name else False

    rect = get_rect(window)
    size_ok = False
    if rect:
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        size_ok = width >= args.min_width and height >= args.min_height

    nav_container = find_nav_container(window, max_depth=6)
    nav_count = count_nav_buttons(window, search_depth=args.search_depth)
    search_box = find_search_box(window, search_depth=args.search_depth)
    chat_list = find_chat_list(window, max_depth=6)
    weixin_pane = find_weixin_pane(window, max_depth=6)

    status = WeChatStatus.UNKNOWN
    skip_login_check = args.skip_login_check
    if os.environ.get("PYTHONUTF8") == "1" or os.environ.get("PYTHONIOENCODING") == "utf-8":
        skip_login_check = True

    if not skip_login_check:
        try:
            status = controller.check_login_status(timeout=2)
        except Exception:
            status = WeChatStatus.UNKNOWN

    if status == WeChatStatus.NOT_RUNNING and process_ok:
        status = WeChatStatus.UNKNOWN

    status_logged_in = status == WeChatStatus.LOGGED_IN
    status_blocked = status in {WeChatStatus.NOT_LOGGED_IN, WeChatStatus.LOCKED}

    score = 0
    score += 2 if class_ok else 0
    score += 2 if process_ok else 0
    score += 1 if title_ok else 0
    score += 1 if size_ok else 0
    score += 1 if weixin_pane else 0
    score += 1 if nav_container else 0
    score += 1 if nav_count >= 2 else 0
    score += 1 if search_box else 0
    score += 1 if chat_list else 0
    score += 2 if status_logged_in else 0
    score -= 3 if status_blocked else 0

    print(f"class_name: {class_name}")
    print(f"title: {title or '(empty)'}")
    print(f"process: {proc_name or '(unknown)'} (pid={pid})")
    print(f"class_ok: {class_ok}")
    print(f"process_ok: {process_ok}")
    print(f"title_ok: {title_ok}")
    print(f"size_ok: {size_ok}")
    print(f"weixin_pane: {bool(weixin_pane)}")
    print(f"nav_container: {bool(nav_container)}")
    print(f"nav_button_count: {nav_count}")
    print(f"search_box: {bool(search_box)}")
    print(f"chat_list: {bool(chat_list)}")
    if skip_login_check:
        print("login_status: skipped")
    else:
        print(f"login_status: {status.value}")
    print(f"score: {score}")

    base_ok = class_ok and process_ok and title_ok
    ui_ok = any([nav_container, nav_count >= 1, search_box, chat_list, weixin_pane])
    likely_main_panel = base_ok and not status_blocked and (ui_ok or size_ok or status_logged_in)
    print(f"main_panel: {likely_main_panel}")

    if args.dump_tree:
        print("\nUI tree (partial):")
        print_tree(window, max_depth=args.tree_depth)

    return 0 if likely_main_panel else 2


if __name__ == "__main__":
    raise SystemExit(main())
