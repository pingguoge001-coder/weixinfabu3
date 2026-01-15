"""
测试环境检查模块

测试 core/env_checker.py 中定义的 EnvChecker 类
使用 mock 模拟 Windows API 调用和文件系统操作
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path

from core.env_checker import (
    CheckStatus,
    CheckResult,
    EnvCheckResult,
    DisplayCheckInfo,
    EnvChecker,
    quick_check,
    check_wechat_ready,
)
from core.display_manager import MonitorInfo


class TestCheckStatus:
    """测试检查状态枚举"""

    def test_status_values(self):
        """测试状态枚举值"""
        assert CheckStatus.PASS.value == "pass"
        assert CheckStatus.WARNING.value == "warning"
        assert CheckStatus.FAIL.value == "fail"
        assert CheckStatus.SKIP.value == "skip"


class TestCheckResult:
    """测试单项检查结果"""

    def test_passed_property_pass(self):
        """测试通过状态"""
        result = CheckResult(
            name="测试项",
            status=CheckStatus.PASS,
            message="通过"
        )
        assert result.passed is True

    def test_passed_property_warning(self):
        """测试警告状态也算通过"""
        result = CheckResult(
            name="测试项",
            status=CheckStatus.WARNING,
            message="警告"
        )
        assert result.passed is True

    def test_passed_property_skip(self):
        """测试跳过状态也算通过"""
        result = CheckResult(
            name="测试项",
            status=CheckStatus.SKIP,
            message="跳过"
        )
        assert result.passed is True

    def test_passed_property_fail(self):
        """测试失败状态"""
        result = CheckResult(
            name="测试项",
            status=CheckStatus.FAIL,
            message="失败"
        )
        assert result.passed is False

    def test_with_detail(self):
        """测试带详细信息"""
        result = CheckResult(
            name="测试项",
            status=CheckStatus.FAIL,
            message="失败",
            detail="详细错误信息"
        )
        assert result.detail == "详细错误信息"


class TestEnvCheckResult:
    """测试环境检查总结果"""

    def test_add_check(self):
        """测试添加检查结果"""
        result = EnvCheckResult(success=True, can_continue=True)
        check = CheckResult(
            name="测试",
            status=CheckStatus.PASS,
            message="通过"
        )

        result.add_check(check)

        assert len(result.checks) == 1
        assert result.checks[0] == check

    def test_get_failed_checks(self):
        """测试获取失败的检查项"""
        result = EnvCheckResult(success=False, can_continue=False)
        result.add_check(CheckResult("检查1", CheckStatus.PASS, "通过"))
        result.add_check(CheckResult("检查2", CheckStatus.FAIL, "失败"))
        result.add_check(CheckResult("检查3", CheckStatus.WARNING, "警告"))
        result.add_check(CheckResult("检查4", CheckStatus.FAIL, "失败"))

        failed = result.get_failed_checks()

        assert len(failed) == 2
        assert all(c.status == CheckStatus.FAIL for c in failed)

    def test_get_warnings(self):
        """测试获取警告的检查项"""
        result = EnvCheckResult(success=True, can_continue=True)
        result.add_check(CheckResult("检查1", CheckStatus.PASS, "通过"))
        result.add_check(CheckResult("检查2", CheckStatus.WARNING, "警告1"))
        result.add_check(CheckResult("检查3", CheckStatus.WARNING, "警告2"))
        result.add_check(CheckResult("检查4", CheckStatus.FAIL, "失败"))

        warnings = result.get_warnings()

        assert len(warnings) == 2
        assert all(c.status == CheckStatus.WARNING for c in warnings)

    def test_get_summary(self):
        """测试获取检查摘要"""
        result = EnvCheckResult(success=True, can_continue=True)
        result.add_check(CheckResult("检查1", CheckStatus.PASS, "通过"))
        result.add_check(CheckResult("检查2", CheckStatus.PASS, "通过"))
        result.add_check(CheckResult("检查3", CheckStatus.WARNING, "警告"))
        result.add_check(CheckResult("检查4", CheckStatus.FAIL, "失败"))
        result.add_check(CheckResult("检查5", CheckStatus.SKIP, "跳过"))

        summary = result.get_summary()

        assert "通过: 2" in summary
        assert "警告: 1" in summary
        assert "失败: 1" in summary
        assert "跳过: 1" in summary

    def test_get_summary_empty(self):
        """测试空检查列表的摘要"""
        result = EnvCheckResult(success=True, can_continue=True)
        summary = result.get_summary()

        assert summary == "无检查项"


class TestEnvCheckerInit:
    """测试 EnvChecker 初始化"""

    @patch('core.env_checker.get_display_manager')
    def test_default_init(self, mock_get_display):
        """测试默认初始化"""
        mock_display = Mock()
        mock_get_display.return_value = mock_display

        checker = EnvChecker()

        assert checker.config == {}
        assert checker._display_manager == mock_display

    @patch('core.env_checker.get_display_manager')
    def test_init_with_config(self, mock_get_display):
        """测试带配置初始化"""
        config = {"key": "value"}
        checker = EnvChecker(config)

        assert checker.config == config

    def test_window_class_constants(self):
        """测试微信窗口类名常量"""
        assert EnvChecker.WECHAT_MAIN_WINDOW_CLASS == "WeChatMainWndForPC"
        assert EnvChecker.WECHAT_LOGIN_WINDOW_CLASS == "WeChatLoginWndForPC"


class TestCheckWeChatRunning:
    """测试微信运行检查"""

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    def test_wechat_running_main_window(self, mock_find, mock_display):
        """测试微信主窗口存在"""
        mock_find.side_effect = [12345, 0]  # main window exists, login window not

        checker = EnvChecker()
        result = checker.check_wechat_running()

        assert result.status == CheckStatus.PASS
        assert result.name == "微信进程"
        assert "运行" in result.message

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    def test_wechat_running_login_window(self, mock_find, mock_display):
        """测试微信登录窗口存在"""
        mock_find.side_effect = [0, 67890]  # main window not, login window exists

        checker = EnvChecker()
        result = checker.check_wechat_running()

        assert result.status == CheckStatus.PASS
        assert "运行" in result.message

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    def test_wechat_not_running(self, mock_find, mock_display):
        """测试微信未运行"""
        mock_find.side_effect = [0, 0]  # both not found

        checker = EnvChecker()
        result = checker.check_wechat_running()

        assert result.status == CheckStatus.FAIL
        assert "未运行" in result.message
        assert "启动微信" in result.detail

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    def test_wechat_check_exception(self, mock_find, mock_display):
        """测试检查微信时异常"""
        mock_find.side_effect = Exception("API error")

        checker = EnvChecker()
        result = checker.check_wechat_running()

        assert result.status == CheckStatus.FAIL
        assert "失败" in result.message


class TestCheckWeChatLogin:
    """测试微信登录状态检查"""

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    @patch('core.env_checker.ctypes.windll.user32.IsWindowVisible')
    def test_wechat_logged_in_visible(self, mock_visible, mock_find, mock_display):
        """测试微信已登录且窗口可见"""
        mock_find.side_effect = [12345, 0]  # main exists, login not
        mock_visible.return_value = True

        checker = EnvChecker()
        result = checker.check_wechat_login()

        assert result.status == CheckStatus.PASS
        assert "已登录" in result.message

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    @patch('core.env_checker.ctypes.windll.user32.IsWindowVisible')
    def test_wechat_logged_in_minimized(self, mock_visible, mock_find, mock_display):
        """测试微信已登录但窗口最小化"""
        mock_find.side_effect = [12345, 0]
        mock_visible.return_value = False

        checker = EnvChecker()
        result = checker.check_wechat_login()

        assert result.status == CheckStatus.PASS
        assert "已登录" in result.message
        assert "最小化" in result.message

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    def test_wechat_at_login_screen(self, mock_find, mock_display):
        """测试微信在登录界面"""
        mock_find.side_effect = [0, 67890]  # main not found, login exists

        checker = EnvChecker()
        result = checker.check_wechat_login()

        assert result.status == CheckStatus.FAIL
        assert "未登录" in result.message
        assert "扫码" in result.detail

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    def test_wechat_no_window(self, mock_find, mock_display):
        """测试未检测到微信窗口"""
        mock_find.side_effect = [0, 0]

        checker = EnvChecker()
        result = checker.check_wechat_login()

        assert result.status == CheckStatus.FAIL
        assert "未检测到" in result.message

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    def test_wechat_login_check_exception(self, mock_find, mock_display):
        """测试检查登录状态异常"""
        mock_find.side_effect = Exception("API error")

        checker = EnvChecker()
        result = checker.check_wechat_login()

        assert result.status == CheckStatus.FAIL
        assert "失败" in result.message


class TestCheckSharedFolder:
    """测试共享文件夹检查"""

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.Path')
    def test_shared_folder_exists_and_writable(self, mock_path_class, mock_display):
        """测试共享文件夹存在且可写"""
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.is_dir.return_value = True

        mock_test_file = Mock()
        mock_test_file.write_text.return_value = None
        mock_test_file.unlink.return_value = None

        mock_path.__truediv__ = Mock(return_value=mock_test_file)

        mock_path_class.return_value = mock_path

        checker = EnvChecker()
        result = checker.check_shared_folder("/path/to/shared")

        assert result.status == CheckStatus.PASS
        assert "可访问" in result.message

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.Path')
    def test_shared_folder_not_exists_created(self, mock_path_class, mock_display):
        """测试共享文件夹不存在但成功创建"""
        mock_path = Mock()
        mock_path.exists.side_effect = [False, True]  # first not exists, then exists
        mock_path.is_dir.return_value = True
        mock_path.mkdir.return_value = None

        mock_test_file = Mock()
        mock_test_file.write_text.return_value = None
        mock_test_file.unlink.return_value = None
        mock_path.__truediv__ = Mock(return_value=mock_test_file)

        mock_path_class.return_value = mock_path

        checker = EnvChecker()
        result = checker.check_shared_folder("/path/to/shared")

        assert result.status == CheckStatus.PASS
        mock_path.mkdir.assert_called_once()

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.Path')
    def test_shared_folder_create_permission_error(self, mock_path_class, mock_display):
        """测试创建共享文件夹权限错误"""
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_path.mkdir.side_effect = PermissionError("no permission")

        mock_path_class.return_value = mock_path

        checker = EnvChecker()
        result = checker.check_shared_folder("/path/to/shared")

        assert result.status == CheckStatus.FAIL
        assert "无权限" in result.message

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.Path')
    def test_shared_folder_not_directory(self, mock_path_class, mock_display):
        """测试路径不是目录"""
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.is_dir.return_value = False

        mock_path_class.return_value = mock_path

        checker = EnvChecker()
        result = checker.check_shared_folder("/path/to/file.txt")

        assert result.status == CheckStatus.FAIL
        assert "不是目录" in result.message

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.Path')
    def test_shared_folder_write_permission_error(self, mock_path_class, mock_display):
        """测试共享文件夹无写权限"""
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.is_dir.return_value = True

        mock_test_file = Mock()
        mock_test_file.write_text.side_effect = PermissionError("no write permission")
        mock_path.__truediv__ = Mock(return_value=mock_test_file)

        mock_path_class.return_value = mock_path

        checker = EnvChecker()
        result = checker.check_shared_folder("/path/to/shared")

        assert result.status == CheckStatus.WARNING
        assert "无写入权限" in result.message

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.Path')
    def test_shared_folder_check_exception(self, mock_path_class, mock_display):
        """测试检查共享文件夹异常"""
        mock_path_class.side_effect = Exception("error")

        checker = EnvChecker()
        result = checker.check_shared_folder("/path/to/shared")

        assert result.status == CheckStatus.FAIL
        assert "失败" in result.message


class TestCheckDisplay:
    """测试显示器检查"""

    @patch('core.env_checker.get_display_manager')
    def test_check_display_pass(self, mock_get_display):
        """测试显示器检查通过"""
        mock_display = Mock()
        mock_display.check_resolution.return_value = (True, "满足要求")
        mock_get_display.return_value = mock_display

        config = {
            "display": {
                "min_resolution": {"width": 1920, "height": 1080},
                "primary_monitor_only": True
            }
        }

        checker = EnvChecker(config)
        result = checker.check_display()

        assert result.status == CheckStatus.PASS
        assert "满足要求" in result.message

    @patch('core.env_checker.get_display_manager')
    def test_check_display_warning(self, mock_get_display):
        """测试显示器检查警告"""
        mock_display = Mock()
        mock_display.check_resolution.return_value = (False, "分辨率不足")
        mock_get_display.return_value = mock_display

        config = {
            "display": {
                "min_resolution": {"width": 1920, "height": 1080},
                "primary_monitor_only": True
            }
        }

        checker = EnvChecker(config)
        result = checker.check_display()

        assert result.status == CheckStatus.WARNING
        assert "不足" in result.message

    @patch('core.env_checker.get_display_manager')
    def test_check_display_with_default_config(self, mock_get_display):
        """测试使用默认配置检查显示器"""
        mock_display = Mock()
        mock_display.check_resolution.return_value = (True, "满足要求")
        mock_get_display.return_value = mock_display

        checker = EnvChecker()
        result = checker.check_display()

        assert result.status == CheckStatus.PASS
        # 验证使用默认值调用
        mock_display.check_resolution.assert_called_with(
            min_width=1920, min_height=1080, primary_only=True
        )

    @patch('core.env_checker.get_display_manager')
    def test_check_display_exception(self, mock_get_display):
        """测试显示器检查异常"""
        mock_display = Mock()
        mock_display.check_resolution.side_effect = Exception("error")
        mock_get_display.return_value = mock_display

        checker = EnvChecker()
        result = checker.check_display()

        assert result.status == CheckStatus.WARNING
        assert "失败" in result.message


class TestCheckDpi:
    """测试 DPI 检查"""

    @patch('core.env_checker.get_display_manager')
    def test_check_dpi_pass(self, mock_get_display):
        """测试 DPI 检查通过"""
        mock_display = Mock()
        mock_display.check_dpi_scaling.return_value = (True, "DPI 为推荐值: 100%")
        mock_get_display.return_value = mock_display

        config = {
            "display": {
                "check_dpi_scaling": True,
                "recommended_dpi": 100
            }
        }

        checker = EnvChecker(config)
        result = checker.check_dpi()

        assert result.status == CheckStatus.PASS
        assert "推荐值" in result.message

    @patch('core.env_checker.get_display_manager')
    def test_check_dpi_warning(self, mock_get_display):
        """测试 DPI 检查警告"""
        mock_display = Mock()
        mock_display.check_dpi_scaling.return_value = (False, "DPI 为 125%")
        mock_get_display.return_value = mock_display

        config = {
            "display": {
                "check_dpi_scaling": True,
                "recommended_dpi": 100
            }
        }

        checker = EnvChecker(config)
        result = checker.check_dpi()

        assert result.status == CheckStatus.WARNING
        assert "125%" in result.message

    @patch('core.env_checker.get_display_manager')
    def test_check_dpi_skip(self, mock_get_display):
        """测试跳过 DPI 检查"""
        mock_display = Mock()
        mock_get_display.return_value = mock_display

        config = {
            "display": {
                "check_dpi_scaling": False
            }
        }

        checker = EnvChecker(config)
        result = checker.check_dpi()

        assert result.status == CheckStatus.SKIP
        assert "跳过" in result.message

    @patch('core.env_checker.get_display_manager')
    def test_check_dpi_exception(self, mock_get_display):
        """测试 DPI 检查异常"""
        mock_display = Mock()
        mock_display.check_dpi_scaling.side_effect = Exception("error")
        mock_get_display.return_value = mock_display

        checker = EnvChecker()
        result = checker.check_dpi()

        assert result.status == CheckStatus.WARNING
        assert "失败" in result.message


class TestCheckAll:
    """测试完整环境检查"""

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    @patch('core.env_checker.ctypes.windll.user32.IsWindowVisible')
    def test_check_all_success(self, mock_visible, mock_find, mock_display_mgr):
        """测试所有检查通过"""
        # Mock 微信运行和登录
        mock_find.side_effect = lambda cls, *args: 12345 if cls == "WeChatMainWndForPC" else 0
        mock_visible.return_value = True

        # Mock 显示器管理器
        mock_display = Mock()
        mock_display.check_resolution.return_value = (True, "满足要求")
        mock_display.check_dpi_scaling.return_value = (True, "推荐值")
        mock_display.get_display_info.return_value = Mock(
            monitor_count=1,
            primary_monitor=Mock(),
            virtual_width=1920,
            virtual_height=1080,
            all_monitors=[Mock()]
        )
        mock_display_mgr.return_value = mock_display

        checker = EnvChecker()
        result = checker.check_all()

        # 检查 success 时应排除 SKIP 状态
        # 如果共享文件夹被跳过，success 会是 False 但 can_continue 是 True
        assert result.can_continue is True
        assert len(result.checks) >= 4  # 至少有微信进程、登录、显示器、DPI

        # 验证关键检查都通过
        pass_checks = [c for c in result.checks if c.status == CheckStatus.PASS]
        assert len(pass_checks) >= 4

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    def test_check_all_wechat_not_running(self, mock_find, mock_display_mgr):
        """测试微信未运行时的检查"""
        mock_find.return_value = 0  # 微信未运行

        mock_display = Mock()
        mock_display.check_resolution.return_value = (True, "满足要求")
        mock_display.check_dpi_scaling.return_value = (True, "推荐值")
        mock_display.get_display_info.return_value = Mock()
        mock_display_mgr.return_value = mock_display

        checker = EnvChecker()
        result = checker.check_all()

        assert result.success is False
        assert result.can_continue is False

        # 应该跳过登录检查
        login_checks = [c for c in result.checks if c.name == "微信登录"]
        assert len(login_checks) == 1
        assert login_checks[0].status == CheckStatus.SKIP

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    @patch('core.env_checker.ctypes.windll.user32.IsWindowVisible')
    @patch('core.env_checker.Path')
    def test_check_all_with_shared_folder(self, mock_path_class, mock_visible, mock_find, mock_display_mgr):
        """测试包含共享文件夹检查"""
        # Mock 微信
        mock_find.side_effect = lambda cls, *args: 12345 if cls == "WeChatMainWndForPC" else 0
        mock_visible.return_value = True

        # Mock 路径
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.is_dir.return_value = True
        mock_test_file = Mock()
        mock_path.__truediv__ = Mock(return_value=mock_test_file)
        mock_path_class.return_value = mock_path

        # Mock 显示器
        mock_display = Mock()
        mock_display.check_resolution.return_value = (True, "满足要求")
        mock_display.check_dpi_scaling.return_value = (True, "推荐值")
        mock_display.get_display_info.return_value = Mock()
        mock_display_mgr.return_value = mock_display

        config = {
            "paths": {
                "shared_folder": "/path/to/shared"
            }
        }

        checker = EnvChecker(config)
        result = checker.check_all()

        # 应该包含共享文件夹检查
        folder_checks = [c for c in result.checks if c.name == "共享文件夹"]
        assert len(folder_checks) == 1

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    @patch('core.env_checker.ctypes.windll.user32.IsWindowVisible')
    def test_check_all_no_shared_folder_config(self, mock_visible, mock_find, mock_display_mgr):
        """测试未配置共享文件夹"""
        mock_find.side_effect = lambda cls, *args: 12345 if cls == "WeChatMainWndForPC" else 0
        mock_visible.return_value = True

        mock_display = Mock()
        mock_display.check_resolution.return_value = (True, "满足要求")
        mock_display.check_dpi_scaling.return_value = (True, "推荐值")
        mock_display.get_display_info.return_value = Mock()
        mock_display_mgr.return_value = mock_display

        checker = EnvChecker()
        result = checker.check_all()

        # 共享文件夹检查应该被跳过
        folder_checks = [c for c in result.checks if c.name == "共享文件夹"]
        assert len(folder_checks) == 1
        assert folder_checks[0].status == CheckStatus.SKIP

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    @patch('core.env_checker.ctypes.windll.user32.IsWindowVisible')
    def test_check_all_with_warnings(self, mock_visible, mock_find, mock_display_mgr):
        """测试包含警告的检查"""
        mock_find.side_effect = lambda cls, *args: 12345 if cls == "WeChatMainWndForPC" else 0
        mock_visible.return_value = True

        mock_display = Mock()
        mock_display.check_resolution.return_value = (False, "分辨率不足")  # 警告
        mock_display.check_dpi_scaling.return_value = (False, "DPI 不匹配")  # 警告
        mock_display.get_display_info.return_value = Mock()
        mock_display_mgr.return_value = mock_display

        checker = EnvChecker()
        result = checker.check_all()

        # success 应该为 False（因为有警告）
        assert result.success is False
        # can_continue 应该为 True（警告不阻断）
        assert result.can_continue is True

        warnings = result.get_warnings()
        assert len(warnings) >= 2


class TestGetPrimaryMonitor:
    """测试获取主显示器"""

    @patch('core.env_checker.get_display_manager')
    def test_get_primary_monitor(self, mock_get_display):
        """测试获取主显示器"""
        mock_monitor = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )

        mock_display = Mock()
        mock_display.get_primary_monitor.return_value = mock_monitor
        mock_get_display.return_value = mock_display

        checker = EnvChecker()
        result = checker.get_primary_monitor()

        assert result == mock_monitor


class TestGetDisplayCheckInfo:
    """测试获取显示器检查详细信息"""

    @patch('core.env_checker.get_display_manager')
    def test_get_display_check_info(self, mock_get_display):
        """测试获取显示器检查信息"""
        mock_monitor = MonitorInfo(
            handle=12345, name="Primary",
            x=0, y=0, width=1920, height=1080,
            work_x=0, work_y=0, work_width=1920, work_height=1040,
            is_primary=True
        )

        mock_display = Mock()
        mock_display.get_display_info.return_value = Mock(
            monitor_count=1,
            primary_monitor=mock_monitor,
            virtual_width=1920,
            virtual_height=1080,
            all_monitors=[mock_monitor]
        )
        mock_display.check_resolution.return_value = (True, "满足要求")
        mock_display.check_dpi_scaling.return_value = (True, "推荐值")
        mock_get_display.return_value = mock_display

        checker = EnvChecker()
        info = checker._get_display_check_info()

        assert isinstance(info, DisplayCheckInfo)
        assert info.monitor_count == 1
        assert info.resolution_ok is True
        assert info.dpi_ok is True


class TestQuickCheck:
    """测试快速检查便捷函数"""

    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    @patch('core.env_checker.ctypes.windll.user32.IsWindowVisible')
    @patch('core.env_checker.get_display_manager')
    def test_quick_check_pass(self, mock_display_mgr, mock_visible, mock_find):
        """测试快速检查通过"""
        mock_find.side_effect = lambda cls, *args: 12345 if cls == "WeChatMainWndForPC" else 0
        mock_visible.return_value = True

        mock_display = Mock()
        mock_display.check_resolution.return_value = (True, "满足要求")
        mock_display.check_dpi_scaling.return_value = (True, "推荐值")
        mock_display.get_display_info.return_value = Mock()
        mock_display_mgr.return_value = mock_display

        passed, issues = quick_check()

        assert passed is True
        assert len(issues) == 0

    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    @patch('core.env_checker.get_display_manager')
    def test_quick_check_fail(self, mock_display_mgr, mock_find):
        """测试快速检查失败"""
        mock_find.return_value = 0  # 微信未运行

        mock_display = Mock()
        mock_display.check_resolution.return_value = (True, "满足要求")
        mock_display.check_dpi_scaling.return_value = (True, "推荐值")
        mock_display.get_display_info.return_value = Mock()
        mock_display_mgr.return_value = mock_display

        passed, issues = quick_check()

        assert passed is False
        assert len(issues) > 0

    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    @patch('core.env_checker.ctypes.windll.user32.IsWindowVisible')
    @patch('core.env_checker.get_display_manager')
    def test_quick_check_with_warnings(self, mock_display_mgr, mock_visible, mock_find):
        """测试快速检查有警告"""
        mock_find.side_effect = lambda cls, *args: 12345 if cls == "WeChatMainWndForPC" else 0
        mock_visible.return_value = True

        mock_display = Mock()
        mock_display.check_resolution.return_value = (False, "分辨率不足")
        mock_display.check_dpi_scaling.return_value = (True, "推荐值")
        mock_display.get_display_info.return_value = Mock()
        mock_display_mgr.return_value = mock_display

        passed, issues = quick_check()

        # 有警告但可以继续
        assert passed is True
        assert len(issues) > 0
        assert any("[警告]" in issue for issue in issues)


class TestCheckWeChatReady:
    """测试微信就绪检查便捷函数"""

    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    @patch('core.env_checker.ctypes.windll.user32.IsWindowVisible')
    @patch('core.env_checker.get_display_manager')
    def test_wechat_ready(self, mock_display, mock_visible, mock_find):
        """测试微信就绪"""
        mock_find.side_effect = lambda cls, *args: 12345 if cls == "WeChatMainWndForPC" else 0
        mock_visible.return_value = True

        ready, message = check_wechat_ready()

        assert ready is True
        assert "就绪" in message

    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    @patch('core.env_checker.get_display_manager')
    def test_wechat_not_running_not_ready(self, mock_display, mock_find):
        """测试微信未运行时不就绪"""
        mock_find.return_value = 0

        ready, message = check_wechat_ready()

        assert ready is False
        assert "未运行" in message

    @patch('core.env_checker.ctypes.windll.user32.FindWindowW')
    @patch('core.env_checker.get_display_manager')
    def test_wechat_not_logged_in_not_ready(self, mock_display, mock_find):
        """测试微信未登录时不就绪"""
        mock_find.side_effect = lambda cls, *args: 67890 if cls == "WeChatLoginWndForPC" else 0

        ready, message = check_wechat_ready()

        assert ready is False
        assert "未登录" in message or "未运行" in message


class TestEdgeCases:
    """测试边界情况"""

    @patch('core.env_checker.get_display_manager')
    def test_empty_config(self, mock_display):
        """测试空配置"""
        checker = EnvChecker({})
        assert checker.config == {}

    @patch('core.env_checker.get_display_manager')
    def test_none_config(self, mock_display):
        """测试 None 配置"""
        checker = EnvChecker(None)
        assert checker.config == {}

    @patch('core.env_checker.get_display_manager')
    def test_partial_config(self, mock_display):
        """测试部分配置"""
        config = {"display": {"min_resolution": {"width": 1920}}}
        checker = EnvChecker(config)

        # 应该使用默认值补全
        result = checker.check_display()
        # 不应抛出异常

    @patch('core.env_checker.get_display_manager')
    @patch('core.env_checker.Path')
    def test_check_shared_folder_empty_path(self, mock_path_class, mock_display):
        """测试检查空路径"""
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path

        checker = EnvChecker()
        result = checker.check_shared_folder("")

        # 应该处理空路径而不崩溃
        assert isinstance(result, CheckResult)
