"""
显示器管理模块

提供多显示器环境下的显示器信息获取、DPI感知处理和窗口管理功能。
使用 ctypes 直接调用 Windows API 获取准确的显示器信息。
"""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# Windows API 常量
MONITOR_DEFAULTTONEAREST = 2
MONITOR_DEFAULTTOPRIMARY = 1
MDT_EFFECTIVE_DPI = 0

# DPI 感知模式
DPI_AWARENESS_UNAWARE = 0
DPI_AWARENESS_SYSTEM_AWARE = 1
DPI_AWARENESS_PER_MONITOR_AWARE = 2


@dataclass
class MonitorInfo:
    """显示器信息"""
    handle: int                  # 显示器句柄
    name: str                    # 显示器名称
    x: int                       # 左上角 X 坐标
    y: int                       # 左上角 Y 坐标
    width: int                   # 宽度（像素）
    height: int                  # 高度（像素）
    work_x: int                  # 工作区 X 坐标
    work_y: int                  # 工作区 Y 坐标
    work_width: int              # 工作区宽度
    work_height: int             # 工作区高度
    is_primary: bool             # 是否为主显示器
    dpi_x: int = 96              # 水平 DPI
    dpi_y: int = 96              # 垂直 DPI
    scale_factor: float = 1.0    # 缩放比例（相对于 100%）

    @property
    def resolution(self) -> tuple[int, int]:
        """返回分辨率元组 (width, height)"""
        return (self.width, self.height)

    @property
    def dpi_percentage(self) -> int:
        """返回 DPI 缩放百分比（100, 125, 150 等）"""
        return round(self.dpi_x / 96 * 100)


@dataclass
class DisplayInfo:
    """显示环境总体信息"""
    monitor_count: int           # 显示器数量
    primary_monitor: MonitorInfo # 主显示器
    virtual_width: int           # 虚拟屏幕宽度
    virtual_height: int          # 虚拟屏幕高度
    all_monitors: list[MonitorInfo]  # 所有显示器列表


class DisplayManager:
    """
    显示器管理器

    功能：
    - 获取所有显示器信息
    - 获取主显示器
    - DPI 感知处理
    - 窗口移动到主显示器
    """

    def __init__(self):
        """初始化显示器管理器"""
        self._monitors: list[MonitorInfo] = []
        self._primary_monitor: Optional[MonitorInfo] = None
        self._init_dpi_awareness()

    def _init_dpi_awareness(self):
        """设置进程 DPI 感知"""
        try:
            # Windows 10 1607+ (Build 14393)
            # 尝试使用最新的 DPI 感知 API
            awareness_context = ctypes.c_void_p(-4)  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            result = ctypes.windll.user32.SetProcessDpiAwarenessContext(awareness_context)
            if result:
                logger.debug("已设置 DPI 感知模式: PER_MONITOR_AWARE_V2")
                return
        except (AttributeError, OSError):
            pass

        try:
            # Windows 8.1+
            ctypes.windll.shcore.SetProcessDpiAwareness(DPI_AWARENESS_PER_MONITOR_AWARE)
            logger.debug("已设置 DPI 感知模式: PER_MONITOR_AWARE")
        except (AttributeError, OSError):
            try:
                # Windows Vista+
                ctypes.windll.user32.SetProcessDPIAware()
                logger.debug("已设置 DPI 感知模式: SYSTEM_AWARE")
            except (AttributeError, OSError):
                logger.warning("无法设置 DPI 感知模式，可能导致分辨率检测不准确")

    def refresh(self):
        """刷新显示器信息"""
        self._monitors.clear()
        self._primary_monitor = None
        self._enum_monitors()
        self._get_dpi_for_all_monitors()

        # 设置主显示器
        for monitor in self._monitors:
            if monitor.is_primary:
                self._primary_monitor = monitor
                break

        logger.debug(f"检测到 {len(self._monitors)} 个显示器")

    def _enum_monitors(self):
        """枚举所有显示器"""
        # 定义回调函数类型
        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_void_p,  # hMonitor
            ctypes.c_void_p,  # hdcMonitor
            ctypes.POINTER(wintypes.RECT),  # lprcMonitor
            ctypes.c_longlong  # dwData
        )

        # 定义 MONITORINFOEX 结构
        class MONITORINFOEX(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
                ("szDevice", wintypes.WCHAR * 32),
            ]

        monitors_data = []

        def enum_callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            """枚举回调函数"""
            try:
                info = MONITORINFOEX()
                info.cbSize = ctypes.sizeof(MONITORINFOEX)

                if ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(info)):
                    is_primary = bool(info.dwFlags & 1)  # MONITORINFOF_PRIMARY = 1

                    monitor = MonitorInfo(
                        handle=hMonitor,
                        name=info.szDevice.rstrip('\x00'),
                        x=info.rcMonitor.left,
                        y=info.rcMonitor.top,
                        width=info.rcMonitor.right - info.rcMonitor.left,
                        height=info.rcMonitor.bottom - info.rcMonitor.top,
                        work_x=info.rcWork.left,
                        work_y=info.rcWork.top,
                        work_width=info.rcWork.right - info.rcWork.left,
                        work_height=info.rcWork.bottom - info.rcWork.top,
                        is_primary=is_primary,
                    )
                    monitors_data.append(monitor)
            except Exception as e:
                logger.error(f"获取显示器信息失败: {e}")

            return True  # 继续枚举

        # 枚举显示器
        callback = MONITORENUMPROC(enum_callback)
        ctypes.windll.user32.EnumDisplayMonitors(None, None, callback, 0)

        # 按主显示器优先排序
        self._monitors = sorted(monitors_data, key=lambda m: (not m.is_primary, m.x, m.y))

    def _get_dpi_for_all_monitors(self):
        """获取所有显示器的 DPI"""
        for monitor in self._monitors:
            try:
                dpi_x = ctypes.c_uint()
                dpi_y = ctypes.c_uint()

                # 使用 GetDpiForMonitor (Windows 8.1+)
                result = ctypes.windll.shcore.GetDpiForMonitor(
                    monitor.handle,
                    MDT_EFFECTIVE_DPI,
                    ctypes.byref(dpi_x),
                    ctypes.byref(dpi_y)
                )

                if result == 0:  # S_OK
                    monitor.dpi_x = dpi_x.value
                    monitor.dpi_y = dpi_y.value
                    monitor.scale_factor = dpi_x.value / 96.0
                else:
                    # 回退到系统 DPI
                    self._get_system_dpi(monitor)
            except (AttributeError, OSError):
                # 旧版 Windows，使用系统 DPI
                self._get_system_dpi(monitor)

    def _get_system_dpi(self, monitor: MonitorInfo):
        """获取系统 DPI（回退方法）"""
        try:
            hdc = ctypes.windll.user32.GetDC(None)
            if hdc:
                dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                dpi_y = ctypes.windll.gdi32.GetDeviceCaps(hdc, 90)  # LOGPIXELSY
                ctypes.windll.user32.ReleaseDC(None, hdc)

                monitor.dpi_x = dpi_x
                monitor.dpi_y = dpi_y
                monitor.scale_factor = dpi_x / 96.0
        except Exception as e:
            logger.warning(f"获取系统 DPI 失败: {e}")
            monitor.dpi_x = 96
            monitor.dpi_y = 96
            monitor.scale_factor = 1.0

    def get_all_monitors(self) -> list[MonitorInfo]:
        """
        获取所有显示器信息

        Returns:
            显示器信息列表
        """
        if not self._monitors:
            self.refresh()
        return self._monitors.copy()

    def get_primary_monitor(self) -> Optional[MonitorInfo]:
        """
        获取主显示器信息

        Returns:
            主显示器信息，如果未找到返回 None
        """
        if not self._primary_monitor:
            self.refresh()
        return self._primary_monitor

    def get_display_info(self) -> DisplayInfo:
        """
        获取显示环境总体信息

        Returns:
            显示环境信息
        """
        if not self._monitors:
            self.refresh()

        # 获取虚拟屏幕尺寸
        virtual_width = ctypes.windll.user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
        virtual_height = ctypes.windll.user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN

        primary = self._primary_monitor or self._monitors[0] if self._monitors else None

        return DisplayInfo(
            monitor_count=len(self._monitors),
            primary_monitor=primary,
            virtual_width=virtual_width,
            virtual_height=virtual_height,
            all_monitors=self._monitors.copy()
        )

    def get_monitor_for_window(self, hwnd: int) -> Optional[MonitorInfo]:
        """
        获取窗口所在的显示器

        Args:
            hwnd: 窗口句柄

        Returns:
            显示器信息
        """
        if not self._monitors:
            self.refresh()

        try:
            hmonitor = ctypes.windll.user32.MonitorFromWindow(
                hwnd, MONITOR_DEFAULTTONEAREST
            )

            for monitor in self._monitors:
                if monitor.handle == hmonitor:
                    return monitor
        except Exception as e:
            logger.error(f"获取窗口显示器失败: {e}")

        return self._primary_monitor

    def move_window_to_primary(self, hwnd: int, center: bool = True) -> bool:
        """
        将窗口移动到主显示器

        Args:
            hwnd: 窗口句柄
            center: 是否居中显示

        Returns:
            是否成功
        """
        primary = self.get_primary_monitor()
        if not primary:
            logger.error("未找到主显示器")
            return False

        try:
            # 获取窗口当前尺寸
            rect = wintypes.RECT()
            if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                logger.error("获取窗口尺寸失败")
                return False

            window_width = rect.right - rect.left
            window_height = rect.bottom - rect.top

            if center:
                # 在主显示器工作区居中
                new_x = primary.work_x + (primary.work_width - window_width) // 2
                new_y = primary.work_y + (primary.work_height - window_height) // 2
            else:
                # 移动到主显示器左上角
                new_x = primary.work_x
                new_y = primary.work_y

            # 确保窗口不超出工作区
            new_x = max(primary.work_x, min(new_x, primary.work_x + primary.work_width - window_width))
            new_y = max(primary.work_y, min(new_y, primary.work_y + primary.work_height - window_height))

            # 移动窗口
            result = ctypes.windll.user32.SetWindowPos(
                hwnd,
                0,  # HWND_TOP
                new_x,
                new_y,
                0,  # 保持当前宽度
                0,  # 保持当前高度
                0x0001 | 0x0004  # SWP_NOSIZE | SWP_NOZORDER
            )

            if result:
                logger.info(f"窗口已移动到主显示器 ({new_x}, {new_y})")
                return True
            else:
                logger.error("移动窗口失败")
                return False

        except Exception as e:
            logger.error(f"移动窗口到主显示器失败: {e}")
            return False

    def check_resolution(self, min_width: int = 1920, min_height: int = 1080,
                         primary_only: bool = True) -> tuple[bool, str]:
        """
        检查分辨率是否满足要求

        Args:
            min_width: 最小宽度
            min_height: 最小高度
            primary_only: 是否只检查主显示器

        Returns:
            (是否满足, 详细信息)
        """
        if not self._monitors:
            self.refresh()

        if primary_only:
            primary = self.get_primary_monitor()
            if not primary:
                return False, "未找到主显示器"

            if primary.width >= min_width and primary.height >= min_height:
                return True, f"主显示器分辨率满足要求: {primary.width}x{primary.height}"
            else:
                return False, f"主显示器分辨率不足: {primary.width}x{primary.height}，要求至少 {min_width}x{min_height}"
        else:
            # 检查所有显示器
            for monitor in self._monitors:
                if monitor.width >= min_width and monitor.height >= min_height:
                    return True, f"找到满足要求的显示器: {monitor.name} ({monitor.width}x{monitor.height})"

            return False, f"没有显示器满足分辨率要求 {min_width}x{min_height}"

    def check_dpi_scaling(self, recommended_dpi: int = 100) -> tuple[bool, str]:
        """
        检查 DPI 缩放比例

        Args:
            recommended_dpi: 推荐的 DPI 缩放百分比

        Returns:
            (是否为推荐值, 详细信息)
        """
        primary = self.get_primary_monitor()
        if not primary:
            return False, "未找到主显示器"

        current_dpi = primary.dpi_percentage

        if current_dpi == recommended_dpi:
            return True, f"DPI 缩放比例为推荐值: {current_dpi}%"
        else:
            return False, f"DPI 缩放比例为 {current_dpi}%，推荐设置为 {recommended_dpi}%"


# 全局单例
_display_manager: Optional[DisplayManager] = None


def get_display_manager() -> DisplayManager:
    """获取显示器管理器单例"""
    global _display_manager
    if _display_manager is None:
        _display_manager = DisplayManager()
    return _display_manager
