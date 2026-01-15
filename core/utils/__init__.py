"""
UI 自动化工具模块

提供通用的 UI 操作辅助函数
"""

from .element_helper import (
    # 元素查找
    find_element_by_name,
    find_element_by_class,
    find_element_with_fallback,
    find_button,
    find_input_box,

    # 等待方法
    wait_for_element,
    wait_for_element_disappear,
    wait_for_window,

    # 点击操作
    safe_click,
    click_at_position,
    click_element_center,
    long_click,

    # 输入操作
    input_text_via_clipboard,
    paste_from_clipboard,
    clear_and_input,

    # 窗口操作
    activate_window,
    is_window_foreground,
    get_window_rect,
)

__all__ = [
    # 元素查找
    "find_element_by_name",
    "find_element_by_class",
    "find_element_with_fallback",
    "find_button",
    "find_input_box",

    # 等待方法
    "wait_for_element",
    "wait_for_element_disappear",
    "wait_for_window",

    # 点击操作
    "safe_click",
    "click_at_position",
    "click_element_center",
    "long_click",

    # 输入操作
    "input_text_via_clipboard",
    "paste_from_clipboard",
    "clear_and_input",

    # 窗口操作
    "activate_window",
    "is_window_foreground",
    "get_window_rect",
]
