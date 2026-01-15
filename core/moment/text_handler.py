"""
朋友圈文案处理模块

功能:
- 输入文案到朋友圈编辑框
- 通过剪贴板操作（支持中文）
- 支持微信 3.x 和 4.0
"""

import time
import logging
from typing import Optional

import pyautogui
import uiautomation as auto

logger = logging.getLogger(__name__)


# ============================================================
# 配置常量
# ============================================================

# 操作间隔时间（秒）
SHORT_DELAY = 0.3
STEP_DELAY = 0.8

# 微信 4.0 UI 元素类名
INPUT_FIELD_CLASS = "mmui::ReplyInputField"


class TextHandler:
    """朋友圈文案处理器"""

    def __init__(
        self,
        clipboard_manager,
        wechat_version: Optional[str] = None
    ):
        """
        初始化文案处理器

        Args:
            clipboard_manager: 剪贴板管理器实例
            wechat_version: 微信版本 ("v3" 或 "v4")
        """
        self._clipboard = clipboard_manager
        self._wechat_version = wechat_version

    def set_version(self, version: str):
        """设置微信版本"""
        self._wechat_version = version

    # ========================================================
    # 文案输入方法
    # ========================================================

    def input_text(
        self,
        text: str,
        window: auto.WindowControl
    ) -> bool:
        """
        输入文案

        Args:
            text: 文案内容
            window: 朋友圈窗口控件

        Returns:
            是否成功
        """
        if not text:
            return True

        if not window or not window.Exists(0, 0):
            logger.error("编辑窗口不存在")
            return False

        # 根据版本查找文本输入框
        text_edit = self._find_text_input(window)

        if not text_edit or not text_edit.Exists(5, 1):
            logger.error("未找到文本输入框")
            return False

        # 点击输入框获取焦点
        text_edit.Click()
        time.sleep(SHORT_DELAY)

        # 通过剪贴板粘贴文案
        if not self._clipboard.set_text(text):
            logger.error("复制文案到剪贴板失败")
            return False

        time.sleep(SHORT_DELAY)

        # 验证剪贴板
        if not self._clipboard.verify_text(text):
            logger.warning("剪贴板内容验证失败")

        # 粘贴文案 (Ctrl+V)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(STEP_DELAY)

        logger.debug(f"已输入文案，长度: {len(text)}")
        return True

    def _find_text_input(
        self,
        window: auto.WindowControl
    ) -> Optional[auto.Control]:
        """
        查找文本输入框

        Args:
            window: 窗口控件

        Returns:
            输入框控件或 None
        """
        text_edit = None

        if self._wechat_version == "v4":
            # 微信 4.0 使用 mmui::ReplyInputField 类名
            text_edit = window.Control(
                searchDepth=15,
                ClassName=INPUT_FIELD_CLASS  # mmui::ReplyInputField
            )

            if not text_edit.Exists(5, 1):
                # 备用：通过 Name 查找
                text_edit = window.Control(
                    searchDepth=15,
                    Name="这一刻的想法..."
                )

            if not text_edit.Exists(5, 1):
                # 再尝试 EditControl
                text_edit = window.EditControl(searchDepth=15)
        else:
            # 微信 3.x 使用 EditControl
            text_edit = window.EditControl(
                searchDepth=10,
                Name="这一刻的想法..."
            )

            if not text_edit.Exists(5, 1):
                text_edit = window.EditControl(searchDepth=10)

        return text_edit


# ============================================================
# 便捷函数
# ============================================================

def create_text_handler(
    clipboard_manager,
    wechat_version: Optional[str] = None
) -> TextHandler:
    """
    创建文案处理器实例

    Args:
        clipboard_manager: 剪贴板管理器实例
        wechat_version: 微信版本

    Returns:
        TextHandler 实例
    """
    return TextHandler(clipboard_manager, wechat_version)
