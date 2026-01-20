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

from services.config_manager import get_config

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

        if self._click_text_input_by_coord(window):
            if self._paste_text(text):
                logger.debug("已坐标点击后粘贴文案")
                return True

        logger.error("坐标点击或粘贴文案失败")
        return False

    def _paste_text(self, text: str) -> bool:
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

    def _click_text_input_by_coord(self, window: auto.WindowControl) -> bool:
        try:
            if not window or not window.Exists(0, 0):
                return False

            abs_x = get_config("ui_location.moments_input_box.absolute_x", None)
            abs_y = get_config("ui_location.moments_input_box.absolute_y", None)
            x_off = get_config("ui_location.moments_input_box.x_offset", None)
            y_off = get_config("ui_location.moments_input_box.y_offset", None)

            x = None
            y = None
            if isinstance(abs_x, int) and isinstance(abs_y, int) and abs_x > 0 and abs_y > 0:
                x, y = abs_x, abs_y
            else:
                rect = window.BoundingRectangle
                if (
                    rect
                    and isinstance(x_off, int)
                    and isinstance(y_off, int)
                    and x_off > 0
                    and y_off > 0
                ):
                    x, y = rect.left + x_off, rect.top + y_off

            if x is None or y is None:
                return False

            window.SetFocus()
            pyautogui.click(x, y)  # 输入框坐标
            time.sleep(SHORT_DELAY)
            return True

        except Exception as e:
            logger.error(f"坐标点击输入框异常: {e}")
            return False

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
