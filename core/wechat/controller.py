"""
微信控制器主模块

整合所有子模块，提供统一的控制接口
"""

import time
import ctypes
import logging
from typing import Optional

import uiautomation as auto

from services.config_manager import get_config_manager, get_config
from models.enums import Channel
from .window_manager import WindowManager, Rect, MonitorInfo
from .version_detector import VersionDetector
from .login_checker import LoginChecker, WeChatStatus
from .navigation import NavigationOperator


logger = logging.getLogger(__name__)


# ============================================================
# 进程优先级常量
# ============================================================

PROCESS_PRIORITY_MAP = {
    "low": 0x00000040,       # IDLE_PRIORITY_CLASS
    "normal": 0x00000020,    # NORMAL_PRIORITY_CLASS
    "high": 0x00000080,      # HIGH_PRIORITY_CLASS
}


# ============================================================
# 微信控制器
# ============================================================

class WeChatController:
    """
    微信窗口控制器

    负责查找、激活、移动微信窗口，检测登录状态等操作
    整合了 WindowManager, VersionDetector, LoginChecker, NavigationOperator
    """

    def __init__(self):
        """初始化控制器"""
        self._config = get_config_manager()
        self._main_window: Optional[auto.WindowControl] = None

        # 初始化子模块
        self._window_manager = WindowManager()
        self._version_detector = VersionDetector()
        self._login_checker = LoginChecker(self._version_detector, self._window_manager)
        self._navigation = NavigationOperator()

        # 设置 uiautomation 超时
        timeout = get_config("automation.timeout.window_wait", 15)
        auto.SetGlobalSearchTimeout(timeout)

        logger.debug("微信窗口控制器初始化完成")

    # ========================================================
    # 窗口查找 (委托给 WindowManager 和 VersionDetector)
    # ========================================================

    def find_wechat_window(self, timeout: int = 10) -> Optional[auto.WindowControl]:
        """
        查找微信主窗口 (支持 3.x 和 4.0+ 版本)

        Args:
            timeout: 超时时间（秒）

        Returns:
            微信主窗口控件，未找到返回 None
        """
        window = self._window_manager.find_window_by_class(
            self._version_detector.get_main_window_classes(),
            timeout=timeout,
            title_contains="微信"
        )

        if not window:
            window = self._window_manager.find_window_by_class(
                self._version_detector.get_main_window_classes(),
                timeout=2,
                title_contains="WeChat"
            )

        if not window:
            window = self._window_manager.find_window_by_class(
                self._version_detector.get_main_window_classes(),
                timeout=2
            )

        if not window:
            window = self._find_wechat_window_by_process()

        if window:
            self._main_window = window
            # 检测版本
            detected = self._version_detector.detect_version_from_window(window)
            if not detected:
                self._version_detector.detect_version_from_process()

        return window

    def _find_wechat_window_by_process(self) -> Optional[auto.WindowControl]:
        """通过进程枚举查找微信主窗口（用于类名识别失败的兜底）"""
        try:
            import win32gui
            import win32process
            import psutil
        except Exception as e:
            logger.debug(f"无法加载窗口枚举依赖: {e}")
            return None

        target_names = {name.lower() for name in self._version_detector.get_process_names()}
        candidates: list[tuple[int, str, str, bool]] = []
        known_classes = set(self._version_detector.get_main_window_classes())

        def callback(hwnd, _):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid)
                if proc.name().lower() not in target_names:
                    return True
                class_name = ""
                title = ""
                try:
                    class_name = win32gui.GetClassName(hwnd)
                except Exception:
                    pass
                try:
                    title = win32gui.GetWindowText(hwnd)
                except Exception:
                    pass
                is_visible = False
                try:
                    is_visible = win32gui.IsWindowVisible(hwnd)
                except Exception:
                    pass
                candidates.append((hwnd, class_name, title, is_visible))
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception as e:
            logger.debug(f"枚举窗口失败: {e}")
            return None

        if not candidates:
            return None

        def score(item):
            _, class_name, title, is_visible = item
            value = 0
            if class_name in known_classes:
                value += 3
            if title:
                value += 1
                if "微信" in title or "WeChat" in title:
                    value += 2
            if is_visible:
                value += 1
            return value

        hwnd, class_name, title, _ = max(candidates, key=score)
        window = auto.ControlFromHandle(hwnd)
        if window:
            logger.info(f"通过进程枚举找到微信窗口: class={class_name}, title={title}")
        return window

    def get_detected_version(self) -> Optional[str]:
        """
        获取检测到的微信版本

        Returns:
            "v4" 或 "v3"，未检测到返回 None
        """
        return self._version_detector.get_detected_version()

    def find_login_window(self, timeout: int = 5) -> Optional[auto.WindowControl]:
        """
        查找微信登录窗口 (支持 3.x 和 4.0+ 版本)

        Args:
            timeout: 超时时间（秒）

        Returns:
            登录窗口控件
        """
        return self._window_manager.find_window_by_class(
            self._version_detector.get_login_window_classes(),
            timeout=timeout
        )

    def find_moments_window(self, timeout: int = 10) -> Optional[auto.WindowControl]:
        """
        查找朋友圈窗口 (支持 3.x 和 4.0+ 版本)

        Args:
            timeout: 超时时间（秒）

        Returns:
            朋友圈窗口控件
        """
        # 先尝试从配置获取类名
        class_name = self._config.get_selector("moments_window.class_name")

        # 可能的朋友圈窗口类名（不包含 mmui::MainWindow，避免误判）
        moments_classes = []
        if class_name:
            moments_classes.append(class_name)
        moments_classes.extend([
            "mmui::SNSWindow",
            "SnsWnd",
            "Qt51514QWindowIcon",
        ])

        title_candidates = ["朋友圈", "Moments"]

        def _find_by_title(title: str) -> Optional[auto.WindowControl]:
            window = auto.WindowControl(searchDepth=1, SubName=title)
            if window.Exists(0.5, 0):
                return window
            return None

        def _find_by_class(cls: str, title_contains: Optional[str] = None) -> Optional[auto.WindowControl]:
            window = auto.WindowControl(searchDepth=1, ClassName=cls)
            if not window.Exists(0.5, 0):
                return None
            if title_contains:
                if window.Name and title_contains in window.Name:
                    return window
                return None
            return window

        def _is_real_moments_window(window: auto.WindowControl) -> bool:
            """
            验证是否是真正的朋友圈窗口，而不是微信主窗口

            微信主窗口左侧导航栏也有"朋友圈"按钮，不能仅凭此判断
            """
            if not window or not window.Exists(0, 0):
                return False

            class_name = window.ClassName or ""
            title = window.Name or ""

            # 如果是 mmui::SNSWindow，直接认为是朋友圈窗口
            if class_name == "mmui::SNSWindow":
                return True

            # 如果是 mmui::MainWindow，需要额外验证
            if class_name == "mmui::MainWindow":
                # 检查窗口标题是否包含"朋友圈"（朋友圈独立窗口标题通常是"朋友圈"）
                if "朋友圈" in title or "Moments" in title:
                    return True

                # 检查是否有朋友圈特有的顶部"发表"按钮（TabBarItem 类型）
                try:
                    publish_tab = window.Control(
                        searchDepth=10,
                        Name="发表",
                        ClassName="mmui::XTabBarItem"
                    )
                    if publish_tab.Exists(0.5, 0):
                        return True
                except Exception:
                    pass

                # 如果窗口标题是"微信"，这是主窗口，不是朋友圈窗口
                if title == "微信" or title == "WeChat":
                    return False

                return False

            # 其他类名的窗口，默认认为是朋友圈窗口
            return True

        start_time = time.time()
        while time.time() - start_time < timeout:
            # 优先按标题查找（避免无效类名导致重复日志）
            for title in title_candidates:
                window = _find_by_title(title)
                if window and _is_real_moments_window(window):
                    logger.info(f"找到朋友圈窗口: title={title}, class={window.ClassName}")
                    return window

            # 再按类名查找
            for cls in moments_classes:
                if cls == "Qt51514QWindowIcon":
                    for title in title_candidates:
                        window = _find_by_class(cls, title_contains=title)
                        if window and _is_real_moments_window(window):
                            logger.info(f"找到朋友圈窗口: class={cls}, title={title}")
                            return window
                    continue

                window = _find_by_class(cls)
                if window and _is_real_moments_window(window):
                    logger.info(f"找到朋友圈窗口: {cls}")
                    return window

            time.sleep(0.5)

        return None

    def get_main_window(self) -> Optional[auto.WindowControl]:
        """
        获取已缓存的主窗口，如果不存在则重新查找

        Returns:
            微信主窗口
        """
        if self._main_window and self._main_window.Exists(0, 0):
            return self._main_window

        return self.find_wechat_window()

    def is_main_panel(
        self,
        window: Optional[auto.WindowControl] = None,
        min_width: int = 500,
        min_height: int = 400,
    ) -> bool:
        """
        Check whether the current window looks like the WeChat main panel.

        This is a lightweight structural check to avoid running flows on
        the wrong page or a login/lock screen.
        """
        if window is None:
            window = self.get_main_window()

        if window is None or not window.Exists(0, 0):
            logger.warning("Main window not found for main panel check.")
            return False

        class_name = window.ClassName or ""
        title = window.Name or ""
        class_ok = class_name in ("mmui::MainWindow", "Qt51514QWindowIcon")
        title_ok = ("\u5fae\u4fe1" in title) or ("WeChat" in title)
        if not (class_ok and title_ok):
            logger.debug(
                "Main panel check failed on class/title: class=%s title=%s",
                class_name,
                title,
            )
            return False

        process_ok: Optional[bool] = None
        try:
            import os
            import win32api
            import win32con
            import win32process

            hwnd = window.NativeWindowHandle
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False,
                pid,
            )
            try:
                exe_path = win32process.GetModuleFileNameEx(handle, 0)
                exe_name = os.path.basename(exe_path).lower()
            finally:
                win32api.CloseHandle(handle)

            process_ok = exe_name in {"weixin.exe", "wechat.exe", "wechatappex.exe"}
        except Exception as e:
            logger.debug("Main panel process check skipped: %s", e)

        if process_ok is False:
            logger.warning("Main panel process name mismatch.")
            return False

        rect = self.get_window_rect(window)
        size_ok = False
        if rect:
            size_ok = rect.width >= min_width and rect.height >= min_height

        weixin_pane = False
        try:
            pane = window.PaneControl(searchDepth=3, Name="Weixin")
            if pane.Exists(0, 0):
                weixin_pane = True
        except Exception:
            pass
        if not weixin_pane:
            try:
                pane = window.PaneControl(searchDepth=3, Name="\u5fae\u4fe1")
                if pane.Exists(0, 0):
                    weixin_pane = True
            except Exception:
                pass

        nav_names = [
            "\u5fae\u4fe1",
            "\u901a\u8baf\u5f55",
            "\u6536\u85cf",
            "\u670b\u53cb\u5708",
            "\u89c6\u9891\u53f7",
            "\u8bbe\u7f6e",
        ]
        nav_count = 0
        for name in nav_names:
            try:
                btn = window.ButtonControl(searchDepth=6, Name=name)
                if btn.Exists(0, 0):
                    nav_count += 1
            except Exception:
                continue

        search_box = False
        for keyword in ["\u641c\u7d22", "Search"]:
            try:
                box = window.EditControl(searchDepth=6, SubName=keyword)
                if box.Exists(0, 0):
                    search_box = True
                    break
            except Exception:
                continue

        ui_ok = weixin_pane or search_box or nav_count >= 1
        if not (ui_ok or size_ok):
            logger.debug(
                "Main panel UI check insufficient: size_ok=%s weixin_pane=%s nav_count=%s search_box=%s",
                size_ok,
                weixin_pane,
                nav_count,
                search_box,
            )
            return False

        return True

    # ========================================================
    # 窗口激活 (委托给 WindowManager)
    # ========================================================

    def activate_window(self, window: Optional[auto.WindowControl] = None) -> bool:
        """
        激活窗口到前台

        Args:
            window: 要激活的窗口，默认为主窗口

        Returns:
            是否成功
        """
        if window is None:
            window = self.get_main_window()

        return self._window_manager.activate_window(window)

    def minimize_window(self, window: Optional[auto.WindowControl] = None) -> bool:
        """
        最小化窗口

        Args:
            window: 要最小化的窗口

        Returns:
            是否成功
        """
        if window is None:
            window = self.get_main_window()

        return self._window_manager.minimize_window(window)

    def reset_main_window_position(self) -> bool:
        """
        重置微信主窗口位置和大小到配置值

        从 display.wechat_window 读取目标位置和大小

        Returns:
            是否成功
        """
        window = self.get_main_window()
        if window is None or not window.Exists(0, 0):
            logger.warning("微信主窗口不存在，无法重置位置")
            return False

        # 从配置读取目标位置和大小
        x = get_config("display.wechat_window.x", 85)
        y = get_config("display.wechat_window.y", 124)
        width = get_config("display.wechat_window.width", 1536)
        height = get_config("display.wechat_window.height", 1080)

        try:
            # 先激活窗口
            self.activate_window(window)
            time.sleep(0.2)

            # 移动窗口到目标位置
            result = self.move_window(x, y, width, height, window)
            if result:
                logger.info(f"微信主窗口已重置: 位置({x},{y}), 大小{width}x{height}")
            return result

        except Exception as e:
            logger.error(f"重置微信主窗口位置失败: {e}")
            return False

    # ========================================================
    # 窗口位置和大小 (委托给 WindowManager)
    # ========================================================

    def get_window_rect(self, window: Optional[auto.WindowControl] = None) -> Optional[Rect]:
        """
        获取窗口矩形区域

        Args:
            window: 目标窗口

        Returns:
            窗口矩形区域
        """
        if window is None:
            window = self.get_main_window()

        return self._window_manager.get_window_rect(window)

    def move_window(
        self,
        x: int,
        y: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
        window: Optional[auto.WindowControl] = None
    ) -> bool:
        """
        移动窗口到指定位置

        Args:
            x: 左上角 X 坐标
            y: 左上角 Y 坐标
            width: 窗口宽度（可选）
            height: 窗口高度（可选）
            window: 目标窗口

        Returns:
            是否成功
        """
        if window is None:
            window = self.get_main_window()

        return self._window_manager.move_window(window, x, y, width, height)

    def move_window_to_primary(self, window: Optional[auto.WindowControl] = None) -> bool:
        """
        将窗口移动到主显示器

        Args:
            window: 目标窗口

        Returns:
            是否成功
        """
        if window is None:
            window = self.get_main_window()

        return self._window_manager.move_window_to_primary(window)

    def get_monitors(self) -> list[MonitorInfo]:
        """
        获取所有显示器信息

        Returns:
            显示器信息列表
        """
        return self._window_manager.get_monitors()

    # ========================================================
    # 登录状态检测 (委托给 LoginChecker)
    # ========================================================

    def check_login_status(self, timeout: int = 5) -> WeChatStatus:
        """
        检测微信登录状态 (支持 3.x 和 4.0+ 版本)

        Args:
            timeout: 超时时间（秒）

        Returns:
            微信状态
        """
        if not self._main_window or not self._main_window.Exists(0, 0):
            self.find_wechat_window(timeout=timeout)
        return self._login_checker.check_login_status(self._main_window, timeout)

    def is_wechat_running(self) -> bool:
        """
        检查微信进程是否运行 (支持 3.x 和 4.0+ 版本)

        Returns:
            是否运行
        """
        return self._version_detector.is_wechat_running()

    def wait_for_login(self, timeout: int = 300, check_interval: int = 5) -> bool:
        """
        等待微信登录

        Args:
            timeout: 最大等待时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            是否登录成功
        """
        return self._login_checker.wait_for_login(self._main_window, timeout, check_interval)

    # ========================================================
    # 微信启动和进程管理 (委托给 LoginChecker)
    # ========================================================

    def start_wechat(self) -> bool:
        """
        启动微信

        Returns:
            是否成功启动
        """
        return self._login_checker.start_wechat()

    def set_process_priority(self, priority: str = "normal") -> bool:
        """
        设置微信进程优先级

        Args:
            priority: 优先级 (low, normal, high)

        Returns:
            是否成功
        """
        if priority not in PROCESS_PRIORITY_MAP:
            logger.error(f"无效的优先级: {priority}")
            return False

        try:
            import subprocess

            process_name = self._version_detector.PROCESS_NAME

            # 获取微信进程 ID
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            lines = result.stdout.strip().split('\n')
            if len(lines) < 2:
                logger.error("未找到微信进程")
                return False

            # 解析 PID
            pid = int(lines[1].split(',')[1].strip('"'))

            # 设置优先级
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x0200 | 0x0400, False, pid)  # PROCESS_SET_INFORMATION | PROCESS_QUERY_INFORMATION

            if handle:
                result = kernel32.SetPriorityClass(handle, PROCESS_PRIORITY_MAP[priority])
                kernel32.CloseHandle(handle)

                if result:
                    logger.info(f"微信进程优先级已设置为: {priority}")
                    return True

            logger.error("设置进程优先级失败")
            return False

        except Exception as e:
            logger.error(f"设置进程优先级失败: {e}")
            return False

    # ========================================================
    # 截图功能 (委托给 WindowManager)
    # ========================================================

    def take_screenshot(
        self,
        filename: Optional[str] = None,
        window: Optional[auto.WindowControl] = None
    ) -> Optional[str]:
        """
        对窗口截图

        Args:
            filename: 保存文件名（不含扩展名）
            window: 目标窗口

        Returns:
            截图文件路径
        """
        if window is None:
            window = self.get_main_window()

        return self._window_manager.take_screenshot(window, filename)

    # ========================================================
    # 小程序窗口操作 (委托给 NavigationOperator)
    # ========================================================

    def find_miniprogram_window(self) -> Optional[int]:
        """
        查找小程序窗口，返回窗口句柄

        Returns:
            窗口句柄，未找到返回 None
        """
        return self._navigation.find_miniprogram_window()

    def restore_miniprogram_window(self, x: int, y: int) -> bool:
        """
        恢复小程序窗口位置并置顶（不改变大小）

        Args:
            x: 左上角 X 坐标
            y: 左上角 Y 坐标

        Returns:
            是否成功
        """
        return self._navigation.restore_miniprogram_window(x, y)

    def get_miniprogram_window_rect(self):
        """
        获取小程序窗口位置和大小

        Returns:
            (x, y, width, height) 或 None
        """
        return self._navigation.get_miniprogram_window_rect()

    def click_miniprogram_button(self, x_offset: int, y_offset: int) -> bool:
        """
        点击小程序窗口内的按钮

        Args:
            x_offset: 相对于窗口左上角的X偏移
            y_offset: 相对于窗口左上角的Y偏移

        Returns:
            是否成功
        """
        return self._navigation.click_miniprogram_button(x_offset, y_offset)

    def refresh_miniprogram(self) -> bool:
        """
        刷新小程序（弹出窗口 -> 点击更多 -> 点击重新进入）

        Returns:
            是否成功
        """
        return self._navigation.refresh_miniprogram()

    def find_forward_dialog(self) -> Optional[int]:
        """
        查找微信转发对话框

        Returns:
            窗口句柄，未找到返回 None
        """
        return self._navigation.find_forward_dialog()

    def forward_to_group(self, group_name: str) -> bool:
        """
        在转发对话框中选择群聊并发送

        Args:
            group_name: 群聊名称

        Returns:
            是否成功
        """
        return self._navigation.forward_to_group(group_name)

    def open_product_forward(self, content_code: str, group_name: str = None, channel: Channel = None) -> bool:
        """
        打开产品转发页面并转发到群聊（完整流程）

        Args:
            content_code: 文案编号（如 F00619，前4位是产品编号）
            group_name: 要转发到的群聊名称（可选，如果提供则执行完整转发流程）
            channel: 渠道类型（用于选择配置）

        Returns:
            是否成功
        """
        return self._navigation.open_product_forward(content_code, group_name, channel)

    # ========================================================
    # 上下文管理
    # ========================================================

    def __enter__(self) -> "WeChatController":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._main_window = None
