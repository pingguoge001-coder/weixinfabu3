"""
微信窗口管理模块

功能:
- 查找微信主窗口、登录窗口、朋友圈窗口
- 激活窗口到前台
- 窗口位置/大小调整
- 显示器管理
- 截图功能
"""

import time
import ctypes
import logging
from pathlib import Path
from typing import Optional, NamedTuple, Tuple
from dataclasses import dataclass

import uiautomation as auto

from services.config_manager import get_config


logger = logging.getLogger(__name__)


# ============================================================
# 类型定义
# ============================================================

class Rect(NamedTuple):
    """窗口矩形区域"""
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center(self) -> Tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)


@dataclass
class MonitorInfo:
    """显示器信息"""
    handle: int
    is_primary: bool
    rect: Rect
    work_rect: Rect  # 排除任务栏后的工作区域


# ============================================================
# Windows API 常量
# ============================================================

SW_RESTORE = 9
SW_SHOW = 5
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
HWND_TOP = 0
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


# ============================================================
# 窗口管理器
# ============================================================

class WindowManager:
    """
    微信窗口管理器

    负责窗口的查找、激活、移动、调整大小等操作
    """

    def __init__(self):
        """初始化窗口管理器"""
        self._screenshot_dir = Path(get_config("advanced.screenshot_dir", "screenshots"))
        logger.debug("窗口管理器初始化完成")

    # ========================================================
    # 窗口查找
    # ========================================================

    def find_window_by_class(
        self,
        class_names: list[str],
        timeout: int = 10,
        title_contains: Optional[str] = None
    ) -> Optional[auto.WindowControl]:
        """
        通过类名查找窗口（支持多个备选类名）

        Args:
            class_names: 窗口类名列表（按优先级排序）
            timeout: 超时时间（秒）
            title_contains: 窗口标题必须包含的文字（可选）

        Returns:
            窗口控件，未找到返回 None
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            for class_name in class_names:
                try:
                    window = auto.WindowControl(
                        searchDepth=1,
                        ClassName=class_name
                    )

                    if window.Exists(0, 0):
                        # 验证窗口标题（如果指定）
                        if title_contains:
                            if window.Name and title_contains in window.Name:
                                logger.info(f"找到窗口: {window.Name} ({class_name})")
                                return window
                        else:
                            logger.info(f"找到窗口: {class_name}")
                            return window

                except Exception as e:
                    logger.debug(f"查找窗口时出错 ({class_name}): {e}")

            time.sleep(0.5)

        logger.warning(f"未找到窗口，超时 {timeout} 秒")
        return None

    def find_window_by_title(
        self,
        title: str,
        timeout: int = 5
    ) -> Optional[auto.WindowControl]:
        """
        通过标题查找窗口

        Args:
            title: 窗口标题（支持部分匹配）
            timeout: 超时时间（秒）

        Returns:
            窗口控件，未找到返回 None
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # 枚举所有顶级窗口
                window = auto.WindowControl(searchDepth=1, SubName=title)
                if window.Exists(0.5, 0):
                    logger.info(f"找到窗口: {window.Name}")
                    return window
            except Exception as e:
                logger.debug(f"查找窗口时出错: {e}")

            time.sleep(0.5)

        logger.warning(f"未找到标题包含 '{title}' 的窗口")
        return None

    # ========================================================
    # 窗口激活
    # ========================================================

    def activate_window(self, window: auto.WindowControl) -> bool:
        """
        激活窗口到前台

        Args:
            window: 要激活的窗口

        Returns:
            是否成功
        """
        if window is None or not window.Exists(0, 0):
            logger.error("窗口不存在，无法激活")
            return False

        try:
            hwnd = window.NativeWindowHandle

            # 获取窗口状态
            user32 = ctypes.windll.user32

            # 如果窗口最小化或不可见，先恢复
            if user32.IsIconic(hwnd) or not user32.IsWindowVisible(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
                time.sleep(0.3)

            try:
                window.SetFocus()
            except Exception:
                pass

            # 设置为前台窗口
            # 先模拟 Alt 键按下释放，解除前台锁定
            user32.keybd_event(0x12, 0, 0, 0)  # Alt down
            user32.keybd_event(0x12, 0, 2, 0)  # Alt up

            result = user32.SetForegroundWindow(hwnd)

            if not result:
                flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
                user32.BringWindowToTop(hwnd)
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
                user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
                time.sleep(0.1)
                result = user32.SetForegroundWindow(hwnd)

            if result:
                # 确保窗口可见
                user32.ShowWindow(hwnd, SW_SHOW)

                # 将窗口置顶
                user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

                logger.debug(f"窗口已激活: {window.Name}")
                return True
            else:
                logger.warning("SetForegroundWindow 返回失败")
                return False

        except Exception as e:
            logger.error(f"激活窗口失败: {e}")
            return False

    def minimize_window(self, window: auto.WindowControl) -> bool:
        """
        最小化窗口

        Args:
            window: 要最小化的窗口

        Returns:
            是否成功
        """
        if window is None or not window.Exists(0, 0):
            logger.error("窗口不存在，无法最小化")
            return False

        try:
            hwnd = window.NativeWindowHandle
            ctypes.windll.user32.ShowWindow(hwnd, SW_MINIMIZE)
            logger.debug("窗口已最小化")
            return True
        except Exception as e:
            logger.error(f"最小化窗口失败: {e}")
            return False

    # ========================================================
    # 窗口位置和大小
    # ========================================================

    def get_window_rect(self, window: auto.WindowControl) -> Optional[Rect]:
        """
        获取窗口矩形区域

        Args:
            window: 目标窗口

        Returns:
            窗口矩形区域
        """
        if window is None or not window.Exists(0, 0):
            return None

        try:
            rect = window.BoundingRectangle
            return Rect(rect.left, rect.top, rect.right, rect.bottom)
        except Exception as e:
            logger.error(f"获取窗口区域失败: {e}")
            return None

    def move_window(
        self,
        window: auto.WindowControl,
        x: int,
        y: int,
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> bool:
        """
        移动窗口到指定位置

        Args:
            window: 目标窗口
            x: 左上角 X 坐标
            y: 左上角 Y 坐标
            width: 窗口宽度（可选）
            height: 窗口高度（可选）

        Returns:
            是否成功
        """
        if window is None or not window.Exists(0, 0):
            logger.error("窗口不存在，无法移动")
            return False

        try:
            hwnd = window.NativeWindowHandle
            user32 = ctypes.windll.user32

            if width is None or height is None:
                # 保持原始大小
                rect = self.get_window_rect(window)
                if rect:
                    width = width or rect.width
                    height = height or rect.height
                else:
                    width = width or 800
                    height = height or 600

            user32.MoveWindow(hwnd, x, y, width, height, True)
            logger.debug(f"窗口已移动至 ({x}, {y})，大小: {width}x{height}")
            return True

        except Exception as e:
            logger.error(f"移动窗口失败: {e}")
            return False

    def move_window_to_primary(self, window: auto.WindowControl) -> bool:
        """
        将窗口移动到主显示器

        Args:
            window: 目标窗口

        Returns:
            是否成功
        """
        monitors = self.get_monitors()
        primary = next((m for m in monitors if m.is_primary), None)

        if primary is None:
            logger.error("未找到主显示器")
            return False

        # 居中放置
        window_rect = self.get_window_rect(window)
        if window_rect is None:
            return False

        work_rect = primary.work_rect
        x = work_rect.left + (work_rect.width - window_rect.width) // 2
        y = work_rect.top + (work_rect.height - window_rect.height) // 2

        return self.move_window(window, x, y)

    # ========================================================
    # 显示器管理
    # ========================================================

    def get_monitors(self) -> list[MonitorInfo]:
        """
        获取所有显示器信息

        Returns:
            显示器信息列表
        """
        monitors = []

        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            # 获取显示器信息
            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", ctypes.c_long * 4),
                    ("rcWork", ctypes.c_long * 4),
                    ("dwFlags", ctypes.c_ulong),
                ]

            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(info))

            is_primary = bool(info.dwFlags & 1)  # MONITORINFOF_PRIMARY
            rect = Rect(*info.rcMonitor)
            work_rect = Rect(*info.rcWork)

            monitors.append(MonitorInfo(
                handle=hMonitor,
                is_primary=is_primary,
                rect=rect,
                work_rect=work_rect
            ))
            return True

        # 枚举回调类型
        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_long * 4),
            ctypes.c_double
        )

        ctypes.windll.user32.EnumDisplayMonitors(
            None, None, MonitorEnumProc(callback), 0
        )

        return monitors

    # ========================================================
    # 截图功能
    # ========================================================

    def take_screenshot(
        self,
        window: auto.WindowControl,
        filename: Optional[str] = None
    ) -> Optional[str]:
        """
        对窗口截图

        Args:
            window: 目标窗口
            filename: 保存文件名（不含扩展名）

        Returns:
            截图文件路径
        """
        if not get_config("advanced.save_screenshots", False):
            return None

        if window is None or not window.Exists(0, 0):
            return None

        try:
            # 确保截图目录存在
            self._screenshot_dir.mkdir(parents=True, exist_ok=True)

            # 生成文件名
            if filename is None:
                filename = f"wechat_{int(time.time())}"

            filepath = self._screenshot_dir / f"{filename}.png"

            # 使用 uiautomation 截图
            bitmap = window.CaptureToImage(str(filepath))

            if bitmap:
                logger.debug(f"截图已保存: {filepath}")
                return str(filepath)

        except Exception as e:
            logger.error(f"截图失败: {e}")

        return None
