"""
环境自检模块

提供运行环境的全面检查功能，包括微信状态、文件夹访问、显示器配置等。
"""

import os
import ctypes
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from .display_manager import DisplayManager, MonitorInfo, get_display_manager

logger = logging.getLogger(__name__)


class CheckStatus(Enum):
    """检查状态枚举"""
    PASS = "pass"           # 通过
    WARNING = "warning"     # 警告（不阻断）
    FAIL = "fail"           # 失败（阻断）
    SKIP = "skip"           # 跳过


@dataclass
class CheckResult:
    """单项检查结果"""
    name: str               # 检查项名称
    status: CheckStatus     # 检查状态
    message: str            # 检查信息
    detail: str = ""        # 详细信息

    @property
    def passed(self) -> bool:
        return self.status in (CheckStatus.PASS, CheckStatus.WARNING, CheckStatus.SKIP)


@dataclass
class DisplayCheckInfo:
    """显示器检查信息"""
    monitor_count: int
    primary_monitor: Optional[MonitorInfo]
    resolution_ok: bool
    resolution_message: str
    dpi_ok: bool
    dpi_message: str


@dataclass
class EnvCheckResult:
    """环境检查总结果"""
    success: bool                           # 是否全部通过（不含警告）
    can_continue: bool                      # 是否可以继续运行
    checks: list[CheckResult] = field(default_factory=list)
    display_info: Optional[DisplayCheckInfo] = None

    def add_check(self, result: CheckResult):
        """添加检查结果"""
        self.checks.append(result)

    def get_failed_checks(self) -> list[CheckResult]:
        """获取失败的检查项"""
        return [c for c in self.checks if c.status == CheckStatus.FAIL]

    def get_warnings(self) -> list[CheckResult]:
        """获取警告的检查项"""
        return [c for c in self.checks if c.status == CheckStatus.WARNING]

    def get_summary(self) -> str:
        """获取检查摘要"""
        passed = sum(1 for c in self.checks if c.status == CheckStatus.PASS)
        warnings = sum(1 for c in self.checks if c.status == CheckStatus.WARNING)
        failed = sum(1 for c in self.checks if c.status == CheckStatus.FAIL)
        skipped = sum(1 for c in self.checks if c.status == CheckStatus.SKIP)

        parts = []
        if passed > 0:
            parts.append(f"通过: {passed}")
        if warnings > 0:
            parts.append(f"警告: {warnings}")
        if failed > 0:
            parts.append(f"失败: {failed}")
        if skipped > 0:
            parts.append(f"跳过: {skipped}")

        return ", ".join(parts) if parts else "无检查项"


class EnvChecker:
    """
    环境检查器

    检查项：
    - 微信进程是否运行
    - 微信是否已登录
    - 共享文件夹是否可访问
    - 屏幕分辨率是否满足要求
    - DPI 缩放比例
    - 主显示器检测
    """

    # 微信窗口类名
    WECHAT_MAIN_WINDOW_CLASS = "WeChatMainWndForPC"
    WECHAT_LOGIN_WINDOW_CLASS = "WeChatLoginWndForPC"

    def __init__(self, config: dict = None):
        """
        初始化环境检查器

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self._display_manager = get_display_manager()

    def check_all(self) -> EnvCheckResult:
        """
        执行所有环境检查

        Returns:
            环境检查结果
        """
        result = EnvCheckResult(success=True, can_continue=True)

        # 1. 检查微信进程
        wechat_running = self.check_wechat_running()
        result.add_check(wechat_running)
        if wechat_running.status == CheckStatus.FAIL:
            result.can_continue = False

        # 2. 检查微信登录状态
        if wechat_running.status == CheckStatus.PASS:
            wechat_login = self.check_wechat_login()
            result.add_check(wechat_login)
            if wechat_login.status == CheckStatus.FAIL:
                result.can_continue = False
        else:
            result.add_check(CheckResult(
                name="微信登录",
                status=CheckStatus.SKIP,
                message="跳过检查（微信未运行）"
            ))

        # 3. 检查共享文件夹
        paths_config = self.config.get("paths", {})
        shared_folder = paths_config.get("shared_folder", "")
        if shared_folder:
            folder_check = self.check_shared_folder(shared_folder)
            result.add_check(folder_check)
        else:
            result.add_check(CheckResult(
                name="共享文件夹",
                status=CheckStatus.SKIP,
                message="未配置共享文件夹路径"
            ))

        # 4. 检查显示器
        display_check = self.check_display()
        result.add_check(display_check)
        result.display_info = self._get_display_check_info()

        # 5. 检查 DPI
        dpi_check = self.check_dpi()
        result.add_check(dpi_check)

        # 计算总体结果
        result.success = all(c.status == CheckStatus.PASS for c in result.checks)
        result.can_continue = all(c.passed for c in result.checks)

        return result

    def check_wechat_running(self) -> CheckResult:
        """
        检查微信进程是否运行

        Returns:
            检查结果
        """
        try:
            # 使用 Windows API 查找窗口
            hwnd = ctypes.windll.user32.FindWindowW(
                self.WECHAT_MAIN_WINDOW_CLASS, None
            )
            login_hwnd = ctypes.windll.user32.FindWindowW(
                self.WECHAT_LOGIN_WINDOW_CLASS, None
            )

            if hwnd or login_hwnd:
                logger.info("检测到微信进程正在运行")
                return CheckResult(
                    name="微信进程",
                    status=CheckStatus.PASS,
                    message="微信正在运行"
                )
            else:
                logger.warning("未检测到微信进程")
                return CheckResult(
                    name="微信进程",
                    status=CheckStatus.FAIL,
                    message="微信未运行",
                    detail="请先启动微信客户端"
                )

        except Exception as e:
            logger.error(f"检查微信进程失败: {e}")
            return CheckResult(
                name="微信进程",
                status=CheckStatus.FAIL,
                message=f"检查失败: {e}"
            )

    def check_wechat_login(self) -> CheckResult:
        """
        检查微信是否已登录

        Returns:
            检查结果
        """
        try:
            # 主窗口存在表示已登录
            hwnd = ctypes.windll.user32.FindWindowW(
                self.WECHAT_MAIN_WINDOW_CLASS, None
            )

            if hwnd:
                # 检查窗口是否可见
                is_visible = ctypes.windll.user32.IsWindowVisible(hwnd)
                if is_visible:
                    logger.info("微信已登录")
                    return CheckResult(
                        name="微信登录",
                        status=CheckStatus.PASS,
                        message="微信已登录"
                    )
                else:
                    # 窗口存在但不可见，可能是最小化
                    logger.info("微信已登录（窗口最小化）")
                    return CheckResult(
                        name="微信登录",
                        status=CheckStatus.PASS,
                        message="微信已登录（窗口最小化）"
                    )

            # 检查是否在登录界面
            login_hwnd = ctypes.windll.user32.FindWindowW(
                self.WECHAT_LOGIN_WINDOW_CLASS, None
            )

            if login_hwnd:
                logger.warning("微信处于登录界面")
                return CheckResult(
                    name="微信登录",
                    status=CheckStatus.FAIL,
                    message="微信未登录",
                    detail="请先扫码登录微信"
                )

            logger.warning("未检测到微信窗口")
            return CheckResult(
                name="微信登录",
                status=CheckStatus.FAIL,
                message="未检测到微信窗口"
            )

        except Exception as e:
            logger.error(f"检查微信登录状态失败: {e}")
            return CheckResult(
                name="微信登录",
                status=CheckStatus.FAIL,
                message=f"检查失败: {e}"
            )

    def check_shared_folder(self, path: str) -> CheckResult:
        """
        检查共享文件夹是否可访问

        Args:
            path: 文件夹路径

        Returns:
            检查结果
        """
        try:
            folder_path = Path(path)

            # 检查路径是否存在
            if not folder_path.exists():
                # 尝试创建
                try:
                    folder_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"已创建共享文件夹: {path}")
                except PermissionError:
                    logger.error(f"无权限创建共享文件夹: {path}")
                    return CheckResult(
                        name="共享文件夹",
                        status=CheckStatus.FAIL,
                        message="无权限创建文件夹",
                        detail=f"路径: {path}"
                    )
                except Exception as e:
                    logger.error(f"创建共享文件夹失败: {e}")
                    return CheckResult(
                        name="共享文件夹",
                        status=CheckStatus.FAIL,
                        message=f"创建失败: {e}",
                        detail=f"路径: {path}"
                    )

            # 检查是否为目录
            if not folder_path.is_dir():
                logger.error(f"共享路径不是目录: {path}")
                return CheckResult(
                    name="共享文件夹",
                    status=CheckStatus.FAIL,
                    message="路径不是目录",
                    detail=f"路径: {path}"
                )

            # 检查读写权限
            test_file = folder_path / ".access_test"
            try:
                test_file.write_text("test", encoding="utf-8")
                test_file.unlink()
            except PermissionError:
                logger.warning(f"共享文件夹无写入权限: {path}")
                return CheckResult(
                    name="共享文件夹",
                    status=CheckStatus.WARNING,
                    message="文件夹可读但无写入权限",
                    detail=f"路径: {path}"
                )
            except Exception as e:
                logger.warning(f"共享文件夹权限检查失败: {e}")
                return CheckResult(
                    name="共享文件夹",
                    status=CheckStatus.WARNING,
                    message="权限检查失败",
                    detail=f"路径: {path}, 错误: {e}"
                )

            logger.info(f"共享文件夹可访问: {path}")
            return CheckResult(
                name="共享文件夹",
                status=CheckStatus.PASS,
                message="共享文件夹可访问",
                detail=f"路径: {path}"
            )

        except Exception as e:
            logger.error(f"检查共享文件夹失败: {e}")
            return CheckResult(
                name="共享文件夹",
                status=CheckStatus.FAIL,
                message=f"检查失败: {e}"
            )

    def check_display(self) -> CheckResult:
        """
        检查屏幕分辨率

        Returns:
            检查结果
        """
        try:
            display_config = self.config.get("display", {})
            min_resolution = display_config.get("min_resolution", {})
            min_width = min_resolution.get("width", 1920)
            min_height = min_resolution.get("height", 1080)
            primary_only = display_config.get("primary_monitor_only", True)

            passed, message = self._display_manager.check_resolution(
                min_width=min_width,
                min_height=min_height,
                primary_only=primary_only
            )

            if passed:
                return CheckResult(
                    name="屏幕分辨率",
                    status=CheckStatus.PASS,
                    message=message
                )
            else:
                return CheckResult(
                    name="屏幕分辨率",
                    status=CheckStatus.WARNING,
                    message=message,
                    detail=f"最低要求: {min_width}x{min_height}"
                )

        except Exception as e:
            logger.error(f"检查屏幕分辨率失败: {e}")
            return CheckResult(
                name="屏幕分辨率",
                status=CheckStatus.WARNING,
                message=f"检查失败: {e}"
            )

    def check_dpi(self) -> CheckResult:
        """
        检查 DPI 缩放

        Returns:
            检查结果
        """
        try:
            display_config = self.config.get("display", {})
            check_dpi = display_config.get("check_dpi_scaling", True)

            if not check_dpi:
                return CheckResult(
                    name="DPI 缩放",
                    status=CheckStatus.SKIP,
                    message="已跳过 DPI 检查"
                )

            recommended_dpi = display_config.get("recommended_dpi", 100)
            passed, message = self._display_manager.check_dpi_scaling(recommended_dpi)

            if passed:
                return CheckResult(
                    name="DPI 缩放",
                    status=CheckStatus.PASS,
                    message=message
                )
            else:
                # DPI 不匹配只是警告，不阻断
                return CheckResult(
                    name="DPI 缩放",
                    status=CheckStatus.WARNING,
                    message=message,
                    detail="非推荐 DPI 可能影响 UI 元素定位精度"
                )

        except Exception as e:
            logger.error(f"检查 DPI 缩放失败: {e}")
            return CheckResult(
                name="DPI 缩放",
                status=CheckStatus.WARNING,
                message=f"检查失败: {e}"
            )

    def get_primary_monitor(self) -> Optional[MonitorInfo]:
        """
        获取主显示器信息

        Returns:
            主显示器信息
        """
        return self._display_manager.get_primary_monitor()

    def _get_display_check_info(self) -> DisplayCheckInfo:
        """获取显示器检查详细信息"""
        display_info = self._display_manager.get_display_info()
        display_config = self.config.get("display", {})

        min_resolution = display_config.get("min_resolution", {})
        min_width = min_resolution.get("width", 1920)
        min_height = min_resolution.get("height", 1080)
        recommended_dpi = display_config.get("recommended_dpi", 100)

        res_ok, res_msg = self._display_manager.check_resolution(min_width, min_height)
        dpi_ok, dpi_msg = self._display_manager.check_dpi_scaling(recommended_dpi)

        return DisplayCheckInfo(
            monitor_count=display_info.monitor_count,
            primary_monitor=display_info.primary_monitor,
            resolution_ok=res_ok,
            resolution_message=res_msg,
            dpi_ok=dpi_ok,
            dpi_message=dpi_msg
        )


# 便捷函数

def quick_check(config: dict = None) -> tuple[bool, list[str]]:
    """
    快速环境检查（兼容 main.py 中的 environment_check 函数）

    Args:
        config: 配置字典

    Returns:
        (是否通过, 问题列表)
    """
    checker = EnvChecker(config)
    result = checker.check_all()

    issues = []
    for check in result.checks:
        if check.status == CheckStatus.FAIL:
            issues.append(f"{check.name}: {check.message}")
        elif check.status == CheckStatus.WARNING:
            issues.append(f"[警告] {check.name}: {check.message}")

    return result.can_continue, issues


def check_wechat_ready() -> tuple[bool, str]:
    """
    检查微信是否就绪

    Returns:
        (是否就绪, 状态信息)
    """
    checker = EnvChecker()

    running = checker.check_wechat_running()
    if running.status != CheckStatus.PASS:
        return False, running.message

    login = checker.check_wechat_login()
    if login.status != CheckStatus.PASS:
        return False, login.message

    return True, "微信已就绪"
