"""
UI 元素操作辅助模块

提供通用的 UI 自动化操作方法，从 moment_sender.py、group_sender.py、wechat_controller.py 中提取
"""

import time
import logging
from typing import Optional, Tuple, Callable, Union, List

import uiautomation as auto
import pyautogui
import pyperclip

logger = logging.getLogger(__name__)


# ============================================================
# 常量定义
# ============================================================

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 10
DEFAULT_SEARCH_DEPTH = 15

# 默认延迟时间（秒）
DEFAULT_CLICK_DELAY = 0.3
DEFAULT_INPUT_DELAY = 0.1
DEFAULT_WAIT_INTERVAL = 0.5


# ============================================================
# 元素查找方法
# ============================================================

def find_element_by_name(
    window: auto.WindowControl,
    name: str,
    control_type: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
    search_depth: int = DEFAULT_SEARCH_DEPTH
) -> Optional[auto.Control]:
    """
    通过名称查找 UI 元素

    Args:
        window: 父窗口控件
        name: 元素名称
        control_type: 控件类型（ButtonControl、EditControl 等），None 表示通用 Control
        timeout: 超时时间（秒）
        search_depth: 搜索深度

    Returns:
        找到的控件，未找到返回 None

    Examples:
        >>> button = find_element_by_name(window, "发表", "ButtonControl")
        >>> text = find_element_by_name(window, "朋友圈", "TextControl")
    """
    if not window or not window.Exists(0, 0):
        logger.warning("父窗口不存在")
        return None

    try:
        # 根据控件类型选择查找方法
        if control_type:
            # 使用指定的控件类型
            control_class = getattr(window, control_type, None)
            if control_class:
                element = control_class(searchDepth=search_depth, Name=name)
            else:
                logger.warning(f"未知的控件类型: {control_type}")
                element = window.Control(searchDepth=search_depth, Name=name)
        else:
            # 使用通用 Control
            element = window.Control(searchDepth=search_depth, Name=name)

        if element.Exists(timeout, 1):
            logger.debug(f"找到元素: Name={name}, Type={control_type or 'Control'}")
            return element

        logger.debug(f"未找到元素: Name={name}, Type={control_type or 'Control'}")
        return None

    except Exception as e:
        logger.error(f"查找元素异常 (Name={name}): {e}")
        return None


def find_element_by_class(
    window: auto.WindowControl,
    class_name: str,
    control_type: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
    search_depth: int = DEFAULT_SEARCH_DEPTH
) -> Optional[auto.Control]:
    """
    通过类名查找 UI 元素

    Args:
        window: 父窗口控件
        class_name: 类名
        control_type: 控件类型（ButtonControl、EditControl 等），None 表示通用 Control
        timeout: 超时时间（秒）
        search_depth: 搜索深度

    Returns:
        找到的控件，未找到返回 None

    Examples:
        >>> input_box = find_element_by_class(window, "mmui::XTextEdit", "EditControl")
        >>> button = find_element_by_class(window, "mmui::XButton", "ButtonControl")
    """
    if not window or not window.Exists(0, 0):
        logger.warning("父窗口不存在")
        return None

    try:
        # 根据控件类型选择查找方法
        if control_type:
            control_class = getattr(window, control_type, None)
            if control_class:
                element = control_class(searchDepth=search_depth, ClassName=class_name)
            else:
                logger.warning(f"未知的控件类型: {control_type}")
                element = window.Control(searchDepth=search_depth, ClassName=class_name)
        else:
            element = window.Control(searchDepth=search_depth, ClassName=class_name)

        if element.Exists(timeout, 1):
            logger.debug(f"找到元素: ClassName={class_name}, Type={control_type or 'Control'}")
            return element

        logger.debug(f"未找到元素: ClassName={class_name}, Type={control_type or 'Control'}")
        return None

    except Exception as e:
        logger.error(f"查找元素异常 (ClassName={class_name}): {e}")
        return None


def find_element_with_fallback(
    window: auto.WindowControl,
    primary_selector: dict,
    fallback_selector: dict,
    timeout: float = DEFAULT_TIMEOUT
) -> Optional[auto.Control]:
    """
    使用主选择器查找元素，失败时使用备用选择器

    Args:
        window: 父窗口控件
        primary_selector: 主选择器字典，包含 name/class_name/control_type/search_depth
        fallback_selector: 备用选择器字典
        timeout: 超时时间（秒）

    Returns:
        找到的控件，未找到返回 None

    Examples:
        >>> element = find_element_with_fallback(
        ...     window,
        ...     {"name": "发表", "control_type": "ButtonControl"},
        ...     {"class_name": "mmui::XButton", "control_type": "ButtonControl"}
        ... )
    """
    # 尝试主选择器
    if "name" in primary_selector:
        element = find_element_by_name(
            window,
            primary_selector["name"],
            primary_selector.get("control_type"),
            timeout,
            primary_selector.get("search_depth", DEFAULT_SEARCH_DEPTH)
        )
        if element:
            return element
    elif "class_name" in primary_selector:
        element = find_element_by_class(
            window,
            primary_selector["class_name"],
            primary_selector.get("control_type"),
            timeout,
            primary_selector.get("search_depth", DEFAULT_SEARCH_DEPTH)
        )
        if element:
            return element

    # 尝试备用选择器
    logger.debug("主选择器未找到元素，尝试备用选择器")
    if "name" in fallback_selector:
        return find_element_by_name(
            window,
            fallback_selector["name"],
            fallback_selector.get("control_type"),
            timeout,
            fallback_selector.get("search_depth", DEFAULT_SEARCH_DEPTH)
        )
    elif "class_name" in fallback_selector:
        return find_element_by_class(
            window,
            fallback_selector["class_name"],
            fallback_selector.get("control_type"),
            timeout,
            fallback_selector.get("search_depth", DEFAULT_SEARCH_DEPTH)
        )

    return None


def find_button(
    window: auto.WindowControl,
    name: str,
    timeout: float = DEFAULT_TIMEOUT
) -> Optional[auto.ButtonControl]:
    """
    查找按钮（专用方法）

    Args:
        window: 父窗口控件
        name: 按钮名称
        timeout: 超时时间（秒）

    Returns:
        按钮控件，未找到返回 None

    Examples:
        >>> send_btn = find_button(window, "发送")
        >>> cancel_btn = find_button(window, "取消")
    """
    return find_element_by_name(window, name, "ButtonControl", timeout)


def find_input_box(
    window: auto.WindowControl,
    class_names_v3: Optional[List[str]] = None,
    class_names_v4: Optional[List[str]] = None,
    timeout: float = DEFAULT_TIMEOUT
) -> Optional[auto.EditControl]:
    """
    查找输入框（支持 v3 和 v4）

    Args:
        window: 父窗口控件
        class_names_v3: 微信 3.x 输入框类名列表（默认 ["RichEdit20W"]）
        class_names_v4: 微信 4.0 输入框类名列表（默认 ["mmui::XTextEdit", "mmui::ReplyInputField"]）
        timeout: 超时时间（秒）

    Returns:
        输入框控件，未找到返回 None

    Examples:
        >>> input_box = find_input_box(window)
        >>> chat_input = find_input_box(window, class_names_v4=["mmui::XTextEdit"])
    """
    if not window or not window.Exists(0, 0):
        return None

    # 默认类名列表
    if class_names_v3 is None:
        class_names_v3 = ["RichEdit20W"]
    if class_names_v4 is None:
        class_names_v4 = ["mmui::XTextEdit", "mmui::ReplyInputField"]

    # 优先尝试 v4 类名（新版本优先）
    for class_name in class_names_v4:
        element = find_element_by_class(window, class_name, "EditControl", timeout)
        if element:
            logger.debug(f"找到输入框 (v4): {class_name}")
            return element

    # 尝试 v3 类名
    for class_name in class_names_v3:
        element = find_element_by_class(window, class_name, "EditControl", timeout)
        if element:
            logger.debug(f"找到输入框 (v3): {class_name}")
            return element

    # 最后尝试通用 EditControl
    element = window.EditControl(searchDepth=DEFAULT_SEARCH_DEPTH)
    if element.Exists(timeout, 1):
        logger.debug("找到输入框 (通用)")
        return element

    logger.warning("未找到输入框")
    return None


# ============================================================
# 等待方法
# ============================================================

def wait_for_element(
    window: auto.WindowControl,
    selector: dict,
    timeout: float = DEFAULT_TIMEOUT,
    interval: float = DEFAULT_WAIT_INTERVAL
) -> Optional[auto.Control]:
    """
    等待元素出现

    Args:
        window: 父窗口控件
        selector: 选择器字典，包含 name/class_name/control_type/search_depth
        timeout: 超时时间（秒）
        interval: 检查间隔（秒）

    Returns:
        找到的元素，超时返回 None

    Examples:
        >>> element = wait_for_element(
        ...     window,
        ...     {"name": "发表", "control_type": "ButtonControl"},
        ...     timeout=10
        ... )
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        if "name" in selector:
            element = find_element_by_name(
                window,
                selector["name"],
                selector.get("control_type"),
                0.5,  # 短超时，因为外部有循环
                selector.get("search_depth", DEFAULT_SEARCH_DEPTH)
            )
        elif "class_name" in selector:
            element = find_element_by_class(
                window,
                selector["class_name"],
                selector.get("control_type"),
                0.5,
                selector.get("search_depth", DEFAULT_SEARCH_DEPTH)
            )
        else:
            logger.warning("选择器缺少 name 或 class_name")
            return None

        if element:
            logger.debug(f"元素已出现: {selector}")
            return element

        time.sleep(interval)

    logger.debug(f"等待元素超时: {selector}")
    return None


def wait_for_element_disappear(
    window: auto.WindowControl,
    selector: dict,
    timeout: float = DEFAULT_TIMEOUT
) -> bool:
    """
    等待元素消失

    Args:
        window: 父窗口控件
        selector: 选择器字典
        timeout: 超时时间（秒）

    Returns:
        是否在超时前消失

    Examples:
        >>> disappeared = wait_for_element_disappear(
        ...     window,
        ...     {"name": "正在上传", "control_type": "TextControl"},
        ...     timeout=30
        ... )
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        if "name" in selector:
            element = find_element_by_name(
                window,
                selector["name"],
                selector.get("control_type"),
                0.5,
                selector.get("search_depth", DEFAULT_SEARCH_DEPTH)
            )
        elif "class_name" in selector:
            element = find_element_by_class(
                window,
                selector["class_name"],
                selector.get("control_type"),
                0.5,
                selector.get("search_depth", DEFAULT_SEARCH_DEPTH)
            )
        else:
            logger.warning("选择器缺少 name 或 class_name")
            return False

        if not element or not element.Exists(0, 0):
            logger.debug(f"元素已消失: {selector}")
            return True

        time.sleep(DEFAULT_WAIT_INTERVAL)

    logger.debug(f"等待元素消失超时: {selector}")
    return False


def wait_for_window(
    class_name: str,
    title: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT
) -> Optional[auto.WindowControl]:
    """
    等待窗口出现

    Args:
        class_name: 窗口类名
        title: 窗口标题（可选）
        timeout: 超时时间（秒）

    Returns:
        窗口控件，超时返回 None

    Examples:
        >>> dialog = wait_for_window("#32770", "打开", timeout=5)
        >>> sns_window = wait_for_window("mmui::SNSWindow")
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            if title:
                window = auto.WindowControl(
                    searchDepth=1,
                    ClassName=class_name,
                    Name=title
                )
            else:
                window = auto.WindowControl(
                    searchDepth=1,
                    ClassName=class_name
                )

            if window.Exists(0.5, 0):
                logger.debug(f"窗口已出现: ClassName={class_name}, Title={title}")
                return window

        except Exception as e:
            logger.debug(f"查找窗口异常: {e}")

        time.sleep(DEFAULT_WAIT_INTERVAL)

    logger.debug(f"等待窗口超时: ClassName={class_name}, Title={title}")
    return None


# ============================================================
# 点击操作
# ============================================================

def safe_click(
    element: auto.Control,
    delay_after: float = DEFAULT_CLICK_DELAY
) -> bool:
    """
    安全地点击元素

    Args:
        element: 要点击的元素
        delay_after: 点击后延迟时间（秒）

    Returns:
        是否成功

    Examples:
        >>> success = safe_click(button, delay_after=0.5)
    """
    if not element or not element.Exists(0, 0):
        logger.warning("元素不存在，无法点击")
        return False

    try:
        element.Click()
        logger.debug(f"已点击元素: {element.Name}")
        if delay_after > 0:
            time.sleep(delay_after)
        return True

    except Exception as e:
        logger.error(f"点击元素失败: {e}")
        return False


def click_at_position(
    x: int,
    y: int,
    delay_after: float = DEFAULT_CLICK_DELAY
) -> bool:
    """
    点击屏幕上的指定坐标

    Args:
        x: X 坐标
        y: Y 坐标
        delay_after: 点击后延迟时间（秒）

    Returns:
        是否成功

    Examples:
        >>> success = click_at_position(100, 200)
    """
    try:
        pyautogui.click(x, y)  # 屏幕坐标
        logger.debug(f"已点击坐标: ({x}, {y})")
        if delay_after > 0:
            time.sleep(delay_after)
        return True

    except Exception as e:
        logger.error(f"点击坐标失败: {e}")
        return False


def click_element_center(
    element: auto.Control,
    offset_x: int = 0,
    offset_y: int = 0
) -> bool:
    """
    点击元素中心（带偏移）

    Args:
        element: 要点击的元素
        offset_x: X 轴偏移量（相对于中心点）
        offset_y: Y 轴偏移量（相对于中心点）

    Returns:
        是否成功

    Examples:
        >>> success = click_element_center(button, offset_x=10, offset_y=5)
    """
    if not element or not element.Exists(0, 0):
        logger.warning("元素不存在，无法点击")
        return False

    try:
        rect = element.BoundingRectangle
        center_x = (rect.left + rect.right) // 2 + offset_x
        center_y = (rect.top + rect.bottom) // 2 + offset_y

        return click_at_position(center_x, center_y)

    except Exception as e:
        logger.error(f"点击元素中心失败: {e}")
        return False


def long_click(
    element: auto.Control,
    duration: float = 1.0
) -> bool:
    """
    长按元素

    Args:
        element: 要长按的元素
        duration: 长按时长（秒）

    Returns:
        是否成功

    Examples:
        >>> success = long_click(camera_button, duration=1.5)
    """
    if not element or not element.Exists(0, 0):
        logger.warning("元素不存在，无法长按")
        return False

    try:
        rect = element.BoundingRectangle
        center_x = (rect.left + rect.right) // 2
        center_y = (rect.top + rect.bottom) // 2

        pyautogui.mouseDown(center_x, center_y)  # 元素中心坐标
        time.sleep(duration)
        pyautogui.mouseUp(center_x, center_y)  # 元素中心坐标

        logger.debug(f"已长按元素: {element.Name}, 时长: {duration}s")
        return True

    except Exception as e:
        logger.error(f"长按元素失败: {e}")
        return False


# ============================================================
# 输入操作
# ============================================================

def input_text_via_clipboard(
    element: auto.Control,
    text: str
) -> bool:
    """
    通过剪贴板输入文本（支持中文）

    Args:
        element: 输入框元素
        text: 要输入的文本

    Returns:
        是否成功

    Examples:
        >>> success = input_text_via_clipboard(input_box, "你好，世界！")
    """
    if not element or not element.Exists(0, 0):
        logger.warning("输入框不存在")
        return False

    if not text:
        logger.warning("文本为空")
        return True

    try:
        # 点击输入框获取焦点
        element.Click()
        time.sleep(DEFAULT_INPUT_DELAY)

        # 备份剪贴板
        old_clipboard = pyperclip.paste()

        try:
            # 复制文本到剪贴板
            pyperclip.copy(text)
            time.sleep(DEFAULT_INPUT_DELAY)

            # 粘贴
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(DEFAULT_INPUT_DELAY)

            logger.debug(f"已输入文本，长度: {len(text)}")
            return True

        finally:
            # 恢复剪贴板
            try:
                pyperclip.copy(old_clipboard)
            except:
                pass

    except Exception as e:
        logger.error(f"输入文本失败: {e}")
        return False


def paste_from_clipboard() -> bool:
    """
    从剪贴板粘贴

    Returns:
        是否成功

    Examples:
        >>> success = paste_from_clipboard()
    """
    try:
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(DEFAULT_INPUT_DELAY)
        logger.debug("已从剪贴板粘贴")
        return True

    except Exception as e:
        logger.error(f"粘贴失败: {e}")
        return False


def clear_and_input(
    element: auto.Control,
    text: str
) -> bool:
    """
    清空输入框并输入新文本

    Args:
        element: 输入框元素
        text: 要输入的文本

    Returns:
        是否成功

    Examples:
        >>> success = clear_and_input(input_box, "新内容")
    """
    if not element or not element.Exists(0, 0):
        logger.warning("输入框不存在")
        return False

    try:
        # 点击输入框获取焦点
        element.Click()
        time.sleep(DEFAULT_INPUT_DELAY)

        # 全选
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(DEFAULT_INPUT_DELAY)

        # 删除
        pyautogui.press('delete')
        time.sleep(DEFAULT_INPUT_DELAY)

        # 输入新文本
        if text:
            return input_text_via_clipboard(element, text)

        return True

    except Exception as e:
        logger.error(f"清空并输入失败: {e}")
        return False


# ============================================================
# 窗口操作
# ============================================================

def activate_window(window: auto.WindowControl) -> bool:
    """
    激活窗口到前台

    Args:
        window: 窗口控件

    Returns:
        是否成功

    Examples:
        >>> success = activate_window(main_window)
    """
    if not window or not window.Exists(0, 0):
        logger.warning("窗口不存在，无法激活")
        return False

    try:
        import ctypes

        hwnd = window.NativeWindowHandle
        user32 = ctypes.windll.user32

        # 如果窗口最小化或不可见，先恢复
        if user32.IsIconic(hwnd) or not user32.IsWindowVisible(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE = 9
            time.sleep(0.3)

        try:
            window.SetFocus()
        except Exception:
            pass

        # 模拟 Alt 键解除前台锁定
        user32.keybd_event(0x12, 0, 0, 0)  # Alt down
        user32.keybd_event(0x12, 0, 2, 0)  # Alt up

        # 设置为前台窗口
        result = user32.SetForegroundWindow(hwnd)

        if not result:
            flags = 0x0002 | 0x0001 | 0x0040  # SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
            user32.BringWindowToTop(hwnd)
            user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, flags)  # HWND_TOPMOST
            user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, flags)  # HWND_NOTOPMOST
            time.sleep(0.1)
            result = user32.SetForegroundWindow(hwnd)

        if result:
            # 确保窗口可见
            user32.ShowWindow(hwnd, 5)  # SW_SHOW = 5

            # 将窗口置顶
            user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                0x0002 | 0x0001 | 0x0040  # SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
            )

            logger.debug(f"窗口已激活: {window.Name}")
            return True
        else:
            logger.warning("SetForegroundWindow 返回失败")
            return False

    except Exception as e:
        logger.error(f"激活窗口失败: {e}")
        return False


def is_window_foreground(window: auto.WindowControl) -> bool:
    """
    检查窗口是否在前台

    Args:
        window: 窗口控件

    Returns:
        是否在前台

    Examples:
        >>> is_active = is_window_foreground(main_window)
    """
    if not window or not window.Exists(0, 0):
        return False

    try:
        import ctypes

        hwnd = window.NativeWindowHandle
        foreground_hwnd = ctypes.windll.user32.GetForegroundWindow()

        return hwnd == foreground_hwnd

    except Exception as e:
        logger.error(f"检查窗口前台状态失败: {e}")
        return False


def get_window_rect(window: auto.WindowControl) -> Optional[Tuple[int, int, int, int]]:
    """
    获取窗口矩形区域

    Args:
        window: 窗口控件

    Returns:
        (left, top, right, bottom) 或 None

    Examples:
        >>> rect = get_window_rect(window)
        >>> if rect:
        ...     left, top, right, bottom = rect
        ...     width = right - left
        ...     height = bottom - top
    """
    if not window or not window.Exists(0, 0):
        logger.warning("窗口不存在")
        return None

    try:
        rect = window.BoundingRectangle
        return (rect.left, rect.top, rect.right, rect.bottom)

    except Exception as e:
        logger.error(f"获取窗口区域失败: {e}")
        return None


# ============================================================
# 测试代码
# ============================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=== UI 元素辅助工具测试 ===\n")

    # 尝试查找微信窗口
    print("1. 查找微信窗口...")
    wechat_window = wait_for_window("mmui::MainWindow", timeout=5)
    if not wechat_window:
        wechat_window = wait_for_window("WeChatMainWndForPC", timeout=5)

    if wechat_window:
        print(f"   找到微信窗口: {wechat_window.Name}\n")

        # 测试元素查找
        print("2. 测试元素查找...")
        button = find_button(wechat_window, "发现", timeout=2)
        if button:
            print(f"   找到按钮: {button.Name}")
        else:
            print("   未找到按钮")

        # 测试输入框查找
        print("\n3. 测试输入框查找...")
        input_box = find_input_box(wechat_window, timeout=2)
        if input_box:
            print(f"   找到输入框: {input_box.ClassName}")
        else:
            print("   未找到输入框")

        # 测试窗口信息
        print("\n4. 测试窗口信息...")
        rect = get_window_rect(wechat_window)
        if rect:
            left, top, right, bottom = rect
            print(f"   窗口位置: ({left}, {top})")
            print(f"   窗口大小: {right - left} x {bottom - top}")

        is_foreground = is_window_foreground(wechat_window)
        print(f"   是否在前台: {is_foreground}")

    else:
        print("   未找到微信窗口")

    print("\n测试完成")
