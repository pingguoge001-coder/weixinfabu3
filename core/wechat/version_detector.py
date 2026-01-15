"""
微信版本检测模块

功能:
- 检测微信版本（3.x 或 4.0+）
- 提供版本相关的窗口类名
- 检测微信进程是否运行
"""

import logging
import subprocess
from typing import Optional

import uiautomation as auto


logger = logging.getLogger(__name__)


# ============================================================
# 版本检测器
# ============================================================

class VersionDetector:
    """
    微信版本检测器

    检测微信版本并提供相应的窗口类名
    """

    # 微信主窗口类名 (支持多版本)
    MAIN_WINDOW_CLASS_V4 = "mmui::MainWindow"          # 微信 4.0+
    MAIN_WINDOW_CLASS_V3 = "WeChatMainWndForPC"        # 微信 3.x

    # 微信登录窗口类名
    LOGIN_WINDOW_CLASS_V4 = "mmui::MainWindow"         # 微信 4.0+ (登录也是同一个窗口类)
    LOGIN_WINDOW_CLASS_V3 = "WeChatLoginWndForPC"      # 微信 3.x

    # 微信进程名 (支持多版本)
    PROCESS_NAME = "WeChat.exe"
    PROCESS_NAME_V4 = "WeChatAppEx.exe"  # 微信 4.0+
    PROCESS_NAMES = ["WeChat.exe", "WeChatAppEx.exe"]

    # 所有可能的主窗口类名
    MAIN_WINDOW_CLASSES = [MAIN_WINDOW_CLASS_V4, MAIN_WINDOW_CLASS_V3]
    LOGIN_WINDOW_CLASSES = [LOGIN_WINDOW_CLASS_V4, LOGIN_WINDOW_CLASS_V3]

    def __init__(self):
        """初始化版本检测器"""
        self._detected_version: Optional[str] = None  # 检测到的微信版本 (v4 或 v3)
        logger.debug("版本检测器初始化完成")

    def detect_version_from_window(self, window: auto.WindowControl) -> Optional[str]:
        """
        从窗口检测微信版本

        Args:
            window: 微信窗口控件

        Returns:
            "v4" 或 "v3"，检测失败返回 None
        """
        if not window or not window.Exists(0, 0):
            return None

        try:
            class_name = window.ClassName

            if class_name == self.MAIN_WINDOW_CLASS_V4:
                self._detected_version = "v4"
                logger.info("检测到微信版本: 4.0+")
                return "v4"
            elif class_name == self.MAIN_WINDOW_CLASS_V3:
                self._detected_version = "v3"
                logger.info("检测到微信版本: 3.x")
                return "v3"
            else:
                logger.warning(f"未知窗口类名: {class_name}")
                return None

        except Exception as e:
            logger.error(f"检测版本失败: {e}")
            return None

    def detect_version_from_process(self) -> Optional[str]:
        """
        从进程名检测微信版本

        Returns:
            "v4" 或 "v3"，检测失败返回 None
        """
        try:
            result = subprocess.run(
                ["tasklist"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            output_lower = result.stdout.lower()

            # 检查 4.0 进程
            if self.PROCESS_NAME_V4.lower() in output_lower:
                self._detected_version = "v4"
                logger.info("检测到微信版本: 4.0+ (从进程)")
                return "v4"

            # 检查 3.x 进程
            if self.PROCESS_NAME.lower() in output_lower:
                self._detected_version = "v3"
                logger.info("检测到微信版本: 3.x (从进程)")
                return "v3"

            return None

        except Exception as e:
            logger.error(f"从进程检测版本失败: {e}")
            return None

    def get_detected_version(self) -> Optional[str]:
        """
        获取检测到的微信版本

        Returns:
            "v4" 或 "v3"，未检测到返回 None
        """
        return self._detected_version

    def is_version_4(self) -> bool:
        """
        检查是否为微信 4.0+

        Returns:
            是否为 4.0+
        """
        return self._detected_version == "v4"

    def is_version_3(self) -> bool:
        """
        检查是否为微信 3.x

        Returns:
            是否为 3.x
        """
        return self._detected_version == "v3"

    def get_main_window_classes(self) -> list[str]:
        """
        获取主窗口类名列表（按优先级排序）

        Returns:
            窗口类名列表
        """
        return self.MAIN_WINDOW_CLASSES.copy()

    def get_login_window_classes(self) -> list[str]:
        """
        获取登录窗口类名列表（按优先级排序）

        Returns:
            窗口类名列表
        """
        return self.LOGIN_WINDOW_CLASSES.copy()

    def get_process_names(self) -> list[str]:
        """
        获取微信进程名列表

        Returns:
            进程名列表
        """
        return self.PROCESS_NAMES.copy()

    def is_wechat_running(self) -> bool:
        """
        检查微信进程是否运行 (支持 3.x 和 4.0+ 版本)

        Returns:
            是否运行
        """
        try:
            # 获取所有进程列表
            result = subprocess.run(
                ["tasklist"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            output_lower = result.stdout.lower()

            # 检查所有可能的微信进程名
            for process_name in self.PROCESS_NAMES:
                if process_name.lower() in output_lower:
                    logger.debug(f"找到微信进程: {process_name}")
                    return True

            return False
        except Exception as e:
            logger.error(f"检查进程失败: {e}")
            return False
