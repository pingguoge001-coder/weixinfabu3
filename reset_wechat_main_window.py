# -*- coding: utf-8 -*-
"""Reset WeChat main window position/size to configured values."""
import io
import sys

from core.wechat_controller import get_wechat_controller

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def format_rect(rect):
    if not rect:
        return "(none)"
    return f"({rect.left}, {rect.top}) {rect.width}x{rect.height}"


def main() -> int:
    controller = get_wechat_controller()
    window = controller.find_wechat_window(timeout=5)
    if not window:
        print("Main window not found.")
        return 1

    before = controller.get_window_rect(window)
    print(f"before: {format_rect(before)}")

    if not controller.reset_main_window_position():
        print("reset failed.")
        return 2

    after = controller.get_window_rect(window)
    print(f"after:  {format_rect(after)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
