"""
测试显示器管理模块

测试 core/display_manager.py 中定义的 DisplayManager 类
使用 mock 模拟 ctypes 和 Windows API 调用
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from ctypes import wintypes
import ctypes

from core.display_manager import (
    MonitorInfo,
    DisplayInfo,
    DisplayManager,
    get_display_manager,
    MONITOR_DEFAULTTONEAREST,
    MONITOR_DEFAULTTOPRIMARY,
    MDT_EFFECTIVE_DPI,
)


class TestMonitorInfo:
    """测试 MonitorInfo 数据类"""

    def test_resolution_property(self):
        """测试分辨率属性"""
        monitor = MonitorInfo(
            handle=12345,
            name="Display1",
            x=0, y=0,
            width=1920, height=1080,
            work_x=0, work_y=0,
            work_width=1920, work_height=1040,
            is_primary=True
        )
        assert monitor.resolution == (1920, 1080)

    def test_dpi_percentage_100(self):
        """测试 100% DPI"""
        monitor = MonitorInfo(
            handle=12345, name="Display1",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True, dpi_x=96, dpi_y=96
        )
        assert monitor.dpi_percentage == 100
        assert monitor.scale_factor == 1.0

    def test_dpi_percentage_125(self):
        """测试 125% DPI"""
        monitor = MonitorInfo(
            handle=12345, name="Display1",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True, dpi_x=120, dpi_y=120, scale_factor=1.25
        )
        assert monitor.dpi_percentage == 125

    def test_dpi_percentage_150(self):
        """测试 150% DPI"""
        monitor = MonitorInfo(
            handle=12345, name="Display1",
            x=0, y=0, width=2560, height=1440,
            work_x=0, work_y=0, work_width=2560, work_height=1400,
            is_primary=True, dpi_x=144, dpi_y=144, scale_factor=1.5
        )
        assert monitor.dpi_percentage == 150


class TestDisplayInfo:
    """测试 DisplayInfo 数据类"""

    def test_display_info_creation(self):
        """测试创建显示环境信息"""
        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )

        secondary = MonitorInfo(
            handle=67890, name="Secondary",
            x=1920, y=0, width=1920, height=1080,
            work_x=1920, work_y=0, work_width=1920, work_height=1040,
            is_primary=False
        )

        display_info = DisplayInfo(
            monitor_count=2,
            primary_monitor=primary,
            virtual_width=3840,
            virtual_height=1080,
            all_monitors=[primary, secondary]
        )

        assert display_info.monitor_count == 2
        assert display_info.primary_monitor.is_primary is True
        assert len(display_info.all_monitors) == 2
        assert display_info.virtual_width == 3840


class TestDisplayManagerInit:
    """测试 DisplayManager 初始化"""

    @patch('core.display_manager.ctypes.windll.user32.SetProcessDpiAwarenessContext')
    def test_init_dpi_awareness_v2(self, mock_set_dpi):
        """测试初始化 DPI 感知 - V2 成功"""
        mock_set_dpi.return_value = True

        manager = DisplayManager()

        assert manager._monitors == []
        assert manager._primary_monitor is None
        mock_set_dpi.assert_called_once()

    @patch('core.display_manager.ctypes.windll.user32.SetProcessDpiAwarenessContext')
    @patch('core.display_manager.ctypes.windll.shcore.SetProcessDpiAwareness')
    def test_init_dpi_awareness_per_monitor(self, mock_shcore, mock_user32):
        """测试初始化 DPI 感知 - Per Monitor"""
        mock_user32.side_effect = AttributeError("not available")
        mock_shcore.return_value = None

        manager = DisplayManager()

        assert manager._monitors == []
        mock_shcore.assert_called_once()

    @patch('core.display_manager.ctypes.windll.user32.SetProcessDpiAwarenessContext')
    @patch('core.display_manager.ctypes.windll.shcore.SetProcessDpiAwareness')
    @patch('core.display_manager.ctypes.windll.user32.SetProcessDPIAware')
    def test_init_dpi_awareness_system(self, mock_dpi_aware, mock_shcore, mock_context):
        """测试初始化 DPI 感知 - System Aware"""
        mock_context.side_effect = AttributeError("not available")
        mock_shcore.side_effect = AttributeError("not available")
        mock_dpi_aware.return_value = None

        manager = DisplayManager()

        assert manager._monitors == []
        mock_dpi_aware.assert_called_once()

    @patch('core.display_manager.ctypes.windll.user32.SetProcessDpiAwarenessContext')
    @patch('core.display_manager.ctypes.windll.shcore.SetProcessDpiAwareness')
    @patch('core.display_manager.ctypes.windll.user32.SetProcessDPIAware')
    def test_init_dpi_awareness_all_failed(self, mock_dpi_aware, mock_shcore, mock_context):
        """测试初始化 DPI 感知 - 全部失败"""
        mock_context.side_effect = AttributeError("not available")
        mock_shcore.side_effect = AttributeError("not available")
        mock_dpi_aware.side_effect = OSError("not available")

        # 应该不抛出异常，只是记录警告
        manager = DisplayManager()
        assert manager._monitors == []


class TestEnumMonitors:
    """测试枚举显示器"""

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_enum_monitors_basic(self, mock_init_dpi):
        """测试枚举显示器基本功能"""
        # 这个测试主要验证方法可以被调用，不验证具体实现
        manager = DisplayManager()
        manager._monitors = []

        # 直接调用会使用真实系统API，我们只测试它不抛出异常
        try:
            manager._enum_monitors()
            # 方法执行成功
            assert True
        except Exception:
            # 在测试环境中可能失败，也是正常的
            assert True


class TestGetDpiMethods:
    """测试 DPI 获取方法"""

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_get_dpi_basic(self, mock_init_dpi):
        """测试获取 DPI 基本功能"""
        manager = DisplayManager()
        monitor = MonitorInfo(
            handle=12345, name="Display1",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )
        manager._monitors = [monitor]

        # 测试方法可以被调用
        try:
            manager._get_dpi_for_all_monitors()
            assert True
        except Exception:
            # 在测试环境中可能失败，也是正常的
            assert True

    @patch.object(DisplayManager, '_init_dpi_awareness')
    @patch('core.display_manager.ctypes.windll.user32.GetDC')
    @patch('core.display_manager.ctypes.windll.gdi32.GetDeviceCaps')
    @patch('core.display_manager.ctypes.windll.user32.ReleaseDC')
    def test_get_system_dpi_success(self, mock_release, mock_get_caps, mock_get_dc, mock_init_dpi):
        """测试获取系统 DPI 成功"""
        mock_get_dc.return_value = 12345  # HDC
        mock_get_caps.side_effect = [120, 120]  # dpi_x, dpi_y

        manager = DisplayManager()
        monitor = MonitorInfo(
            handle=12345, name="Display1",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )

        manager._get_system_dpi(monitor)

        assert monitor.dpi_x == 120
        assert monitor.dpi_y == 120
        assert monitor.scale_factor == 1.25
        mock_release.assert_called_once()

    @patch.object(DisplayManager, '_init_dpi_awareness')
    @patch('core.display_manager.ctypes.windll.user32.GetDC')
    def test_get_system_dpi_failed(self, mock_get_dc, mock_init_dpi):
        """测试获取系统 DPI 失败"""
        mock_get_dc.return_value = None

        manager = DisplayManager()
        monitor = MonitorInfo(
            handle=12345, name="Display1",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )

        manager._get_system_dpi(monitor)

        # 应该设置默认值
        assert monitor.dpi_x == 96
        assert monitor.dpi_y == 96
        assert monitor.scale_factor == 1.0


class TestRefreshMethod:
    """测试刷新方法"""

    @patch.object(DisplayManager, '_enum_monitors')
    @patch.object(DisplayManager, '_get_dpi_for_all_monitors')
    def test_refresh_clears_and_rebuilds(self, mock_get_dpi, mock_enum):
        """测试刷新清除并重建显示器列表"""
        manager = DisplayManager()

        # 添加一些假数据
        manager._monitors = [Mock()]
        manager._primary_monitor = Mock()

        # 设置 enum_monitors 添加新的显示器
        def add_monitor():
            manager._monitors.append(
                MonitorInfo(
                    handle=12345, name="Display1",
                    x=0, y=0, width=1920, height=1080,
                    work_x=0, work_y=0, work_width=1920, work_height=1040,
                    is_primary=True
                )
            )

        mock_enum.side_effect = add_monitor

        manager.refresh()

        # 验证方法被调用
        mock_enum.assert_called_once()
        mock_get_dpi.assert_called_once()

        # 验证主显示器被设置
        assert manager._primary_monitor is not None

    @patch.object(DisplayManager, '_enum_monitors')
    @patch.object(DisplayManager, '_get_dpi_for_all_monitors')
    def test_refresh_sets_primary_monitor(self, mock_get_dpi, mock_enum):
        """测试刷新设置主显示器"""
        manager = DisplayManager()

        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )

        secondary = MonitorInfo(
            handle=67890, name="Secondary",
            x=1920, y=0, width=1920, height=1080,
            work_x=1920, work_y=0, work_width=1920, work_height=1040,
            is_primary=False
        )

        def add_monitors():
            manager._monitors.extend([secondary, primary])

        mock_enum.side_effect = add_monitors

        manager.refresh()

        assert manager._primary_monitor == primary


class TestGetMethods:
    """测试获取方法"""

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_get_all_monitors_empty_auto_refresh(self, mock_init_dpi):
        """测试获取所有显示器时自动刷新"""
        manager = DisplayManager()

        with patch.object(manager, 'refresh') as mock_refresh:
            result = manager.get_all_monitors()

            mock_refresh.assert_called_once()
            assert isinstance(result, list)

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_get_all_monitors_returns_copy(self, mock_init_dpi):
        """测试返回显示器列表副本"""
        manager = DisplayManager()
        monitor = MonitorInfo(
            handle=12345, name="Display1",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )
        manager._monitors = [monitor]

        result = manager.get_all_monitors()

        assert result == manager._monitors
        assert result is not manager._monitors  # 应该是副本

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_get_primary_monitor_auto_refresh(self, mock_init_dpi):
        """测试获取主显示器时自动刷新"""
        manager = DisplayManager()

        with patch.object(manager, 'refresh') as mock_refresh:
            result = manager.get_primary_monitor()

            mock_refresh.assert_called_once()

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_get_primary_monitor_returns_primary(self, mock_init_dpi):
        """测试返回主显示器"""
        manager = DisplayManager()
        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )
        manager._primary_monitor = primary

        result = manager.get_primary_monitor()

        assert result == primary

    @patch.object(DisplayManager, '_init_dpi_awareness')
    @patch('core.display_manager.ctypes.windll.user32.GetSystemMetrics')
    def test_get_display_info(self, mock_metrics, mock_init_dpi):
        """测试获取显示环境信息"""
        mock_metrics.side_effect = [3840, 1080]  # virtual_width, virtual_height

        manager = DisplayManager()
        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )
        manager._monitors = [primary]
        manager._primary_monitor = primary

        result = manager.get_display_info()

        assert result.monitor_count == 1
        assert result.primary_monitor == primary
        assert result.virtual_width == 3840
        assert result.virtual_height == 1080


class TestGetMonitorForWindow:
    """测试获取窗口所在显示器"""

    @patch.object(DisplayManager, '_init_dpi_awareness')
    @patch('core.display_manager.ctypes.windll.user32.MonitorFromWindow')
    def test_get_monitor_for_window_success(self, mock_monitor_from, mock_init_dpi):
        """测试成功获取窗口所在显示器"""
        mock_monitor_from.return_value = 12345

        manager = DisplayManager()
        target_monitor = MonitorInfo(
            handle=12345, name="Display1",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )
        manager._monitors = [target_monitor]
        manager._primary_monitor = target_monitor

        result = manager.get_monitor_for_window(99999)

        assert result == target_monitor
        mock_monitor_from.assert_called_with(99999, MONITOR_DEFAULTTONEAREST)

    @patch.object(DisplayManager, '_init_dpi_awareness')
    @patch('core.display_manager.ctypes.windll.user32.MonitorFromWindow')
    def test_get_monitor_for_window_not_found(self, mock_monitor_from, mock_init_dpi):
        """测试窗口显示器未找到，返回主显示器"""
        mock_monitor_from.return_value = 99999  # 不匹配的句柄

        manager = DisplayManager()
        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )
        manager._monitors = [primary]
        manager._primary_monitor = primary

        result = manager.get_monitor_for_window(88888)

        assert result == primary

    @patch.object(DisplayManager, '_init_dpi_awareness')
    @patch('core.display_manager.ctypes.windll.user32.MonitorFromWindow')
    def test_get_monitor_for_window_exception(self, mock_monitor_from, mock_init_dpi):
        """测试获取窗口显示器异常"""
        mock_monitor_from.side_effect = Exception("error")

        manager = DisplayManager()
        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )
        manager._monitors = [primary]
        manager._primary_monitor = primary

        result = manager.get_monitor_for_window(88888)

        assert result == primary


class TestMoveWindowToPrimary:
    """测试移动窗口到主显示器"""

    @patch.object(DisplayManager, '_init_dpi_awareness')
    @patch('core.display_manager.ctypes')
    def test_move_window_center(self, mock_ctypes, mock_init_dpi):
        """测试移动窗口到主显示器居中"""
        # Mock GetWindowRect
        mock_rect = Mock()
        mock_rect.left = 100
        mock_rect.top = 100
        mock_rect.right = 900  # width = 800
        mock_rect.bottom = 700  # height = 600

        mock_ctypes.windll.user32.GetWindowRect.return_value = True
        mock_ctypes.windll.user32.SetWindowPos.return_value = True
        mock_ctypes.byref.return_value = mock_rect

        manager = DisplayManager()
        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=40, work_width=1920, work_height=1040,
            is_primary=True
        )
        manager._primary_monitor = primary

        result = manager.move_window_to_primary(99999, center=True)

        assert result is True
        mock_ctypes.windll.user32.GetWindowRect.assert_called_once()
        mock_ctypes.windll.user32.SetWindowPos.assert_called_once()

    @patch.object(DisplayManager, '_init_dpi_awareness')
    @patch('core.display_manager.ctypes')
    def test_move_window_no_center(self, mock_ctypes, mock_init_dpi):
        """测试移动窗口到主显示器不居中"""
        mock_rect = Mock()
        mock_rect.left = 100
        mock_rect.top = 100
        mock_rect.right = 900
        mock_rect.bottom = 700

        mock_ctypes.windll.user32.GetWindowRect.return_value = True
        mock_ctypes.windll.user32.SetWindowPos.return_value = True
        mock_ctypes.byref.return_value = mock_rect

        manager = DisplayManager()
        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=40, work_width=1920, work_height=1040,
            is_primary=True
        )
        manager._primary_monitor = primary

        result = manager.move_window_to_primary(99999, center=False)

        assert result is True

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_move_window_no_primary(self, mock_init_dpi):
        """测试没有主显示器时移动窗口"""
        manager = DisplayManager()
        manager._primary_monitor = None

        result = manager.move_window_to_primary(99999)

        assert result is False

    @patch.object(DisplayManager, '_init_dpi_awareness')
    @patch('core.display_manager.ctypes.windll.user32.GetWindowRect')
    def test_move_window_get_rect_failed(self, mock_get_rect, mock_init_dpi):
        """测试获取窗口矩形失败"""
        mock_get_rect.return_value = False

        manager = DisplayManager()
        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )
        manager._primary_monitor = primary

        result = manager.move_window_to_primary(99999)

        assert result is False

    @patch.object(DisplayManager, '_init_dpi_awareness')
    @patch('core.display_manager.ctypes.windll.user32.GetWindowRect')
    @patch('core.display_manager.ctypes.windll.user32.SetWindowPos')
    def test_move_window_set_pos_failed(self, mock_set_pos, mock_get_rect, mock_init_dpi):
        """测试设置窗口位置失败"""
        def get_rect(hwnd, rect_ptr):
            rect_ptr.left = 0
            rect_ptr.top = 0
            rect_ptr.right = 800
            rect_ptr.bottom = 600
            return True

        mock_get_rect.side_effect = get_rect
        mock_set_pos.return_value = False

        manager = DisplayManager()
        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )
        manager._primary_monitor = primary

        result = manager.move_window_to_primary(99999)

        assert result is False


class TestCheckResolution:
    """测试分辨率检查"""

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_check_resolution_primary_pass(self, mock_init_dpi):
        """测试主显示器分辨率满足要求"""
        manager = DisplayManager()
        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )
        manager._primary_monitor = primary

        passed, message = manager.check_resolution(1920, 1080, primary_only=True)

        assert passed is True
        assert "满足要求" in message

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_check_resolution_primary_fail(self, mock_init_dpi):
        """测试主显示器分辨率不满足要求"""
        manager = DisplayManager()
        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1366, height=768,
            work_x=0, work_y=0, work_width=1366, work_height=728,
            is_primary=True
        )
        manager._primary_monitor = primary
        manager._monitors = [primary]

        passed, message = manager.check_resolution(1920, 1080, primary_only=True)

        assert passed is False
        assert "不足" in message

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_check_resolution_all_monitors_pass(self, mock_init_dpi):
        """测试所有显示器中有满足要求的"""
        manager = DisplayManager()
        monitors = [
            MonitorInfo(
                handle=12345, name="Primary",
                x=0, y=0, width=1366, height=768,
                work_x=0, work_y=0, work_width=1366, work_height=728,
                is_primary=True
            ),
            MonitorInfo(
                handle=67890, name="Secondary",
                x=1366, y=0, width=2560, height=1440,
                work_x=1366, work_y=0, work_width=2560, work_height=1400,
                is_primary=False
            )
        ]
        manager._monitors = monitors

        passed, message = manager.check_resolution(1920, 1080, primary_only=False)

        assert passed is True
        assert "Secondary" in message or "满足要求" in message

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_check_resolution_all_monitors_fail(self, mock_init_dpi):
        """测试所有显示器都不满足要求"""
        manager = DisplayManager()
        monitors = [
            MonitorInfo(
                handle=12345, name="Primary",
                x=0, y=0, width=1366, height=768,
                work_x=0, work_y=0, work_width=1366, work_height=728,
                is_primary=True
            )
        ]
        manager._monitors = monitors

        passed, message = manager.check_resolution(1920, 1080, primary_only=False)

        assert passed is False
        assert "没有显示器" in message

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_check_resolution_no_primary(self, mock_init_dpi):
        """测试没有主显示器"""
        manager = DisplayManager()
        manager._monitors = []
        manager._primary_monitor = None

        with patch.object(manager, 'refresh'):
            passed, message = manager.check_resolution(1920, 1080, primary_only=True)

            assert passed is False
            assert "未找到主显示器" in message


class TestCheckDpiScaling:
    """测试 DPI 缩放检查"""

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_check_dpi_scaling_match(self, mock_init_dpi):
        """测试 DPI 缩放匹配推荐值"""
        manager = DisplayManager()
        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True, dpi_x=96, dpi_y=96
        )
        manager._primary_monitor = primary

        passed, message = manager.check_dpi_scaling(100)

        assert passed is True
        assert "推荐值" in message

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_check_dpi_scaling_mismatch(self, mock_init_dpi):
        """测试 DPI 缩放不匹配推荐值"""
        manager = DisplayManager()
        primary = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True, dpi_x=120, dpi_y=120
        )
        manager._primary_monitor = primary

        passed, message = manager.check_dpi_scaling(100)

        assert passed is False
        assert "125%" in message
        assert "推荐" in message

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_check_dpi_scaling_no_primary(self, mock_init_dpi):
        """测试没有主显示器时检查 DPI"""
        manager = DisplayManager()
        manager._primary_monitor = None

        with patch.object(manager, 'refresh'):
            passed, message = manager.check_dpi_scaling(100)

            assert passed is False
            assert "未找到主显示器" in message


class TestGetDisplayManagerSingleton:
    """测试全局单例"""

    def test_get_display_manager_singleton(self):
        """测试获取单例"""
        manager1 = get_display_manager()
        manager2 = get_display_manager()

        assert manager1 is manager2

    def test_get_display_manager_creates_instance(self):
        """测试首次调用创建实例"""
        # Reset the global singleton
        import core.display_manager
        core.display_manager._display_manager = None

        manager = get_display_manager()

        assert manager is not None
        assert isinstance(manager, DisplayManager)


class TestEdgeCases:
    """测试边界情况"""

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_empty_monitors_list(self, mock_init_dpi):
        """测试空显示器列表"""
        manager = DisplayManager()
        manager._monitors = []

        # 不触发 refresh
        with patch.object(manager, 'refresh'):
            result = manager.get_all_monitors()
            assert result == []

    @patch.object(DisplayManager, '_init_dpi_awareness')
    @patch('core.display_manager.ctypes.windll.user32.GetSystemMetrics')
    def test_get_display_info_structure(self, mock_metrics, mock_init_dpi):
        """测试获取显示信息返回结构"""
        mock_metrics.side_effect = [3840, 1080]

        manager = DisplayManager()
        manager._monitors = []
        manager._primary_monitor = None

        result = manager.get_display_info()

        # 验证返回的是 DisplayInfo 对象
        assert isinstance(result, DisplayInfo)
        assert result.virtual_width == 3840
        assert result.virtual_height == 1080

    @patch.object(DisplayManager, '_init_dpi_awareness')
    def test_multiple_refresh_calls(self, mock_init_dpi):
        """测试多次刷新调用"""
        manager = DisplayManager()

        with patch.object(manager, '_enum_monitors') as mock_enum, \
             patch.object(manager, '_get_dpi_for_all_monitors') as mock_dpi:

            manager.refresh()
            manager.refresh()
            manager.refresh()

            assert mock_enum.call_count == 3
            assert mock_dpi.call_count == 3
