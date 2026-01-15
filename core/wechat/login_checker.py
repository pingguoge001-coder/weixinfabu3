"""
微信登录状态检查模块

功能:
- 检测微信登录状态
- 等待微信登录
- 启动微信
"""

import os
import time
import logging
import subprocess
from pathlib import Path
from typing import Optional
from enum import Enum

import uiautomation as auto

from services.config_manager import get_config


logger = logging.getLogger(__name__)


# ============================================================
# 类型定义
# ============================================================

class WeChatStatus(Enum):
    """微信状态"""
    NOT_RUNNING = "not_running"      # 微信未运行
    NOT_LOGGED_IN = "not_logged_in"  # 未登录
    LOGGED_IN = "logged_in"          # 已登录
    LOCKED = "locked"                # 锁定状态
    UNKNOWN = "unknown"              # 未知状态


# ============================================================
# 登录检查器
# ============================================================

class LoginChecker:
    """
    微信登录状态检查器

    检测微信登录状态、等待登录、启动微信
    """

    def __init__(self, version_detector, window_manager):
        """
        初始化登录检查器

        Args:
            version_detector: 版本检测器实例
            window_manager: 窗口管理器实例
        """
        self._version_detector = version_detector
        self._window_manager = window_manager
        logger.debug("登录检查器初始化完成")

    # ========================================================
    # 登录状态检测
    # ========================================================

    def check_login_status(
        self,
        main_window: Optional[auto.WindowControl] = None,
        timeout: int = 5
    ) -> WeChatStatus:
        """
        检测微信登录状态 (支持 3.x 和 4.0+ 版本)

        Args:
            main_window: 微信主窗口（可选，如果不提供则自动查找）
            timeout: 超时时间（秒）

        Returns:
            微信状态
        """
        # 检查微信进程是否运行
        if not self._version_detector.is_wechat_running():
            return WeChatStatus.NOT_RUNNING

        # 如果没有提供主窗口，尝试查找
        if not main_window:
            main_window = self._window_manager.find_window_by_class(
                self._version_detector.get_main_window_classes(),
                timeout=timeout,
                title_contains="微信"
            )

        if not main_window:
            return WeChatStatus.UNKNOWN

        # 检查是否已登录 - 通过查找登录后才有的元素
        # 微信4.0登录后会显示"发现"、"通讯录"等按钮
        try:
            # 尝试查找登录后才有的元素
            logged_in_indicators = [
                ("ButtonControl", "发现"),
                ("ButtonControl", "通讯录"),
                ("ButtonControl", "聊天"),
                ("TextControl", "发现"),
                ("TextControl", "通讯录"),
            ]

            for control_type, name in logged_in_indicators:
                if control_type == "ButtonControl":
                    element = main_window.ButtonControl(searchDepth=5, Name=name)
                else:
                    element = main_window.TextControl(searchDepth=5, Name=name)

                if element.Exists(1, 0):
                    logger.debug(f"找到登录标志: {name}")
                    # 检查是否锁定状态
                    lock_hint = main_window.TextControl(searchDepth=5, Name="已锁定")
                    if lock_hint.Exists(0, 0):
                        return WeChatStatus.LOCKED
                    return WeChatStatus.LOGGED_IN

            # 检查是否显示登录二维码或"登录"按钮
            login_indicators = [
                ("ButtonControl", "登录"),
                ("ButtonControl", "进入微信"),
                ("TextControl", "扫码登录"),
            ]

            for control_type, name in login_indicators:
                if control_type == "ButtonControl":
                    element = main_window.ButtonControl(searchDepth=5, Name=name)
                else:
                    element = main_window.TextControl(searchDepth=5, Name=name)

                if element.Exists(1, 0):
                    logger.debug(f"找到登录界面标志: {name}")
                    return WeChatStatus.NOT_LOGGED_IN

        except Exception as e:
            logger.debug(f"检查登录状态时出错: {e}")

        # 如果找到了窗口但无法确定状态，假设已登录（窗口标题为"微信"）
        if main_window.Name and '微信' in main_window.Name:
            return WeChatStatus.LOGGED_IN

        return WeChatStatus.UNKNOWN

    def wait_for_login(
        self,
        main_window: Optional[auto.WindowControl] = None,
        timeout: int = 300,
        check_interval: int = 5
    ) -> bool:
        """
        等待微信登录

        Args:
            main_window: 微信主窗口（可选）
            timeout: 最大等待时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            是否登录成功
        """
        logger.info(f"等待微信登录，超时 {timeout} 秒...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.check_login_status(main_window)

            if status == WeChatStatus.LOGGED_IN:
                logger.info("微信已登录")
                return True

            if status == WeChatStatus.NOT_RUNNING:
                logger.warning("微信未运行")
                return False

            time.sleep(check_interval)

        logger.warning("等待登录超时")
        return False

    # ========================================================
    # 微信启动
    # ========================================================

    def start_wechat(self) -> bool:
        """
        启动微信

        Returns:
            是否成功启动
        """
        wechat_path = get_config("paths.wechat_path")

        if not wechat_path:
            # 尝试自动查找微信路径
            wechat_path = self._find_wechat_path()

        if not wechat_path or not Path(wechat_path).exists():
            logger.error("未找到微信安装路径")
            return False

        try:
            subprocess.Popen(
                [wechat_path],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            logger.info(f"微信已启动: {wechat_path}")
            return True
        except Exception as e:
            logger.error(f"启动微信失败: {e}")
            return False

    def _find_wechat_path(self) -> Optional[str]:
        """
        自动查找微信安装路径

        Returns:
            微信可执行文件路径
        """
        common_paths = [
            Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Tencent" / "WeChat" / "WeChat.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Tencent" / "WeChat" / "WeChat.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Tencent" / "WeChat" / "WeChat.exe",
        ]

        for path in common_paths:
            if path.exists():
                logger.info(f"找到微信: {path}")
                return str(path)

        # 尝试从注册表查找
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Tencent\WeChat"
            )
            install_path, _ = winreg.QueryValueEx(key, "InstallPath")
            winreg.CloseKey(key)

            exe_path = Path(install_path) / "WeChat.exe"
            if exe_path.exists():
                return str(exe_path)
        except Exception:
            pass

        return None
