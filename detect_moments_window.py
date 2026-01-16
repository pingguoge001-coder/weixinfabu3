# -*- coding: utf-8 -*-
"""Detect and optionally activate the WeChat Moments window."""
import io
import sys
import time
import argparse
from typing import Optional, Tuple

import uiautomation as auto

from core.wechat_controller import get_wechat_controller


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MOMENTS_TITLES = ["朋友圈", "Moments"]
MOMENTS_WINDOW_CLASSES = ["Qt51514QWindowIcon", "mmui::SNSWindow", "SnsWnd", "mmui::MainWindow"]


def get_rect(control: auto.Control) -> Optional[Tuple[int, int, int, int]]:
    try:
        rect = control.BoundingRectangle
        return rect.left, rect.top, rect.right, rect.bottom
    except Exception:
        return None


def find_by_class(
    class_name: str,
    timeout: float,
    title_contains: Optional[str] = None,
) -> Optional[auto.WindowControl]:
    window = auto.WindowControl(searchDepth=1, ClassName=class_name)
    if window.Exists(timeout, 0):
        if title_contains:
            if window.Name and title_contains in window.Name:
                return window
            return None
        return window
    return None


def find_by_title(timeout: float) -> Optional[auto.WindowControl]:
    start = time.time()
    while time.time() - start < timeout:
        for title in MOMENTS_TITLES:
            window = auto.WindowControl(searchDepth=1, SubName=title)
            if window.Exists(0.5, 0):
                return window
        time.sleep(0.2)
    return None


def print_window_info(window: auto.Control) -> None:
    rect = get_rect(window)
    rect_str = f"{rect}" if rect else "(no-rect)"
    print(f"class: {window.ClassName}")
    print(f"title: {window.Name or '(empty)'}")
    print(f"rect: {rect_str}")
    try:
        print(f"hwnd: {window.NativeWindowHandle}")
    except Exception:
        print("hwnd: (unknown)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect and activate WeChat Moments window.")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--no-activate", action="store_true")
    args = parser.parse_args()

    controller = get_wechat_controller()
    window = controller.find_moments_window(timeout=int(args.timeout))

    if not window:
        window = find_by_title(args.timeout)

    if not window:
        for cls in MOMENTS_WINDOW_CLASSES:
            if cls in ("Qt51514QWindowIcon", "mmui::MainWindow"):
                for title in MOMENTS_TITLES:
                    window = find_by_class(cls, args.timeout, title_contains=title)
                    if window:
                        break
                if window:
                    break
                continue

            window = find_by_class(cls, args.timeout)
            if window:
                break

    print("=" * 70)
    print("WeChat Moments Window Detection")
    print("=" * 70)

    if not window or not window.Exists(0, 0):
        print("Moments window not found.")
        return 1

    print_window_info(window)

    if args.no_activate:
        return 0

    ok = controller.activate_window(window)
    print(f"activate: {ok}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
