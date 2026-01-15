"""
弹窗检测器模块

功能:
- 检测微信弹窗（确认框、警告框、提示框）
- 自动关闭非关键弹窗
- 识别风控相关弹窗
"""

import sys
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

import uiautomation as auto

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.config_manager import get_config
from models.enums import RiskLevel
from .element_locator import get_element_locator, ElementLocator


logger = logging.getLogger(__name__)


# ============================================================
# 类型定义
# ============================================================

class PopupType(Enum):
    """弹窗类型"""
    CONFIRM = "confirm"          # 确认框
    WARNING = "warning"          # 警告框
    ERROR = "error"              # 错误框
    INFO = "info"                # 信息框
    INPUT = "input"              # 输入框
    RISK = "risk"                # 风控相关
    CAPTCHA = "captcha"          # 验证码
    UNKNOWN = "unknown"          # 未知类型


class PopupAction(Enum):
    """弹窗处理动作"""
    CLOSE = "close"              # 关闭
    CONFIRM = "confirm"          # 确认
    CANCEL = "cancel"            # 取消
    IGNORE = "ignore"            # 忽略
    ALERT = "alert"              # 告警（需人工处理）


@dataclass
class PopupInfo:
    """弹窗信息"""
    popup_type: PopupType
    title: str = ""
    content: str = ""
    buttons: List[str] = field(default_factory=list)
    window: Optional[auto.WindowControl] = None
    risk_level: Optional[RiskLevel] = None
    detected_time: datetime = field(default_factory=datetime.now)
    screenshot_path: Optional[str] = None

    @property
    def is_risk_popup(self) -> bool:
        """是否为风控弹窗"""
        return self.popup_type == PopupType.RISK or self.risk_level is not None

    @property
    def requires_human(self) -> bool:
        """是否需要人工处理"""
        return self.popup_type in (PopupType.RISK, PopupType.CAPTCHA) or \
               (self.risk_level and self.risk_level in (RiskLevel.high, RiskLevel.critical))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "popup_type": self.popup_type.value,
            "title": self.title,
            "content": self.content,
            "buttons": self.buttons,
            "risk_level": self.risk_level.value if self.risk_level else None,
            "detected_time": self.detected_time.isoformat(),
            "screenshot_path": self.screenshot_path,
        }


# ============================================================
# 风控关键词配置
# ============================================================

RISK_KEYWORDS: Dict[RiskLevel, List[str]] = {
    RiskLevel.critical: [
        "账号已被封禁",
        "账号被封",
        "永久封禁",
        "登录受限",
        "账号异常",
        "无法登录",
        "账号已冻结",
        "违规封号",
    ],
    RiskLevel.high: [
        "安全验证",
        "验证码",
        "功能不可用",
        "功能被限制",
        "请完成验证",
        "安全检测",
        "异常操作",
        "需要验证",
        "滑动验证",
    ],
    RiskLevel.medium: [
        "发送过于频繁",
        "消息发送失败",
        "操作太频繁",
        "请稍后再试",
        "发送频率过高",
        "操作失败",
        "网络异常",
    ],
    RiskLevel.low: [
        "发送失败",
        "请重试",
        "加载失败",
    ],
}

# 可自动关闭的弹窗关键词
AUTO_CLOSE_KEYWORDS = [
    "更新提示",
    "版本更新",
    "新功能",
    "评价",
    "反馈",
    "活动",
    "推荐",
    "广告",
]

# 弹窗窗口类名
POPUP_CLASS_NAMES = [
    "#32770",           # Windows 标准对话框
    "WeChatPopupWnd",   # 微信弹窗
    "ConfirmWnd",       # 确认窗口
    "AlertWnd",         # 警告窗口
    "TipWnd",           # 提示窗口
]


# ============================================================
# 弹窗检测器
# ============================================================

class PopupDetector:
    """
    弹窗检测器

    检测和处理微信运行中出现的各类弹窗
    """

    def __init__(self, element_locator: Optional[ElementLocator] = None):
        """
        初始化弹窗检测器

        Args:
            element_locator: 元素定位器实例，默认使用全局单例
        """
        self._screenshot_dir = Path(get_config("advanced.screenshot_dir", "screenshots"))
        self._save_screenshots = get_config("advanced.save_screenshots", False)
        self._detection_timeout = get_config("automation.timeout.element_wait", 10)

        # 元素定位器
        self._locator = element_locator or get_element_locator()

        # 主窗口缓存
        self._main_window: Optional[auto.WindowControl] = None

        logger.debug("弹窗检测器初始化完成")

    def set_main_window(self, window: auto.WindowControl) -> None:
        """设置主窗口引用"""
        self._main_window = window

    # ========================================================
    # 弹窗检测
    # ========================================================

    def detect_popup(self, timeout: float = 1.0) -> Optional[PopupInfo]:
        """
        检测当前是否有弹窗

        Args:
            timeout: 检测超时时间（秒）

        Returns:
            检测到的弹窗信息，无弹窗返回 None
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            # 1. 检测标准 Windows 对话框
            popup = self._detect_standard_dialog()
            if popup:
                return popup

            # 2. 检测微信自定义弹窗
            popup = self._detect_wechat_popup()
            if popup:
                return popup

            # 3. 检测模态窗口
            popup = self._detect_modal_window()
            if popup:
                return popup

            time.sleep(0.1)

        return None

    def detect_all_popups(self) -> List[PopupInfo]:
        """
        检测所有弹窗

        Returns:
            弹窗列表
        """
        popups = []

        # 检测所有可能的弹窗窗口
        for class_name in POPUP_CLASS_NAMES:
            try:
                window = auto.WindowControl(
                    searchDepth=1,
                    ClassName=class_name
                )

                index = 1
                while True:
                    popup_window = auto.WindowControl(
                        searchDepth=1,
                        ClassName=class_name,
                        foundIndex=index
                    )

                    if not popup_window.Exists(0.5, 0):
                        break

                    popup_info = self._analyze_popup(popup_window)
                    if popup_info:
                        popups.append(popup_info)

                    index += 1

            except Exception as e:
                logger.debug(f"检测弹窗类型 {class_name} 时出错: {e}")

        return popups

    def _detect_standard_dialog(self) -> Optional[PopupInfo]:
        """检测标准 Windows 对话框"""
        try:
            dialog = auto.WindowControl(
                searchDepth=1,
                ClassName="#32770"
            )

            if dialog.Exists(0.3, 0):
                return self._analyze_popup(dialog)

        except Exception as e:
            logger.debug(f"检测标准对话框时出错: {e}")

        return None

    def _detect_wechat_popup(self) -> Optional[PopupInfo]:
        """检测微信自定义弹窗"""
        wechat_popup_classes = ["WeChatPopupWnd", "ConfirmWnd", "AlertWnd", "TipWnd"]

        for class_name in wechat_popup_classes:
            try:
                popup = auto.WindowControl(
                    searchDepth=1,
                    ClassName=class_name
                )

                if popup.Exists(0.3, 0):
                    return self._analyze_popup(popup)

            except Exception as e:
                logger.debug(f"检测微信弹窗 {class_name} 时出错: {e}")

        return None

    def _detect_modal_window(self) -> Optional[PopupInfo]:
        """检测模态窗口"""
        if not self._main_window:
            return None

        try:
            # 查找子窗口中的模态对话框
            for child in self._main_window.GetChildren():
                try:
                    if child.ControlTypeName == "WindowControl":
                        # 检查是否是弹窗特征
                        if self._is_popup_window(child):
                            return self._analyze_popup(child)
                except:
                    continue

        except Exception as e:
            logger.debug(f"检测模态窗口时出错: {e}")

        return None

    def _is_popup_window(self, window: auto.Control) -> bool:
        """判断是否是弹窗窗口"""
        try:
            # 检查窗口大小（弹窗通常较小）
            rect = window.BoundingRectangle
            width = rect.right - rect.left
            height = rect.bottom - rect.top

            if width < 100 or height < 50:
                return False

            if width > 800 or height > 600:
                return False

            # 使用 element_locator 尝试查找弹窗按钮（如果有配置）
            try:
                confirm_btn = self._locator.find_element(
                    "popup.confirm_button",
                    parent=window,
                    timeout=0
                )
                if confirm_btn:
                    return True
            except Exception:
                pass

            # 回退：直接查找确认/取消按钮
            confirm_btn = window.ButtonControl(Name="确定")
            cancel_btn = window.ButtonControl(Name="取消")

            if confirm_btn.Exists(0, 0) or cancel_btn.Exists(0, 0):
                return True

            return False

        except:
            return False

    def _analyze_popup(self, window: auto.WindowControl) -> Optional[PopupInfo]:
        """
        分析弹窗内容

        Args:
            window: 弹窗窗口

        Returns:
            弹窗信息
        """
        try:
            title = window.Name or ""
            content = self._extract_popup_content(window)
            buttons = self._extract_buttons(window)

            # 判断弹窗类型
            popup_type = self._determine_popup_type(title, content)

            # 判断风险等级
            risk_level = self._check_risk_level(title, content)

            # 如果检测到风险，更新类型
            if risk_level and risk_level in (RiskLevel.high, RiskLevel.critical):
                popup_type = PopupType.RISK

            popup_info = PopupInfo(
                popup_type=popup_type,
                title=title,
                content=content,
                buttons=buttons,
                window=window,
                risk_level=risk_level,
            )

            # 保存截图
            if self._save_screenshots and popup_info.is_risk_popup:
                popup_info.screenshot_path = self._take_screenshot(window, "popup")

            logger.info(f"检测到弹窗: 类型={popup_type.value}, 标题='{title}', "
                       f"风险={risk_level.value if risk_level else 'none'}")

            return popup_info

        except Exception as e:
            logger.error(f"分析弹窗时出错: {e}")
            return None

    def _extract_popup_content(self, window: auto.WindowControl) -> str:
        """提取弹窗文本内容"""
        texts = []

        try:
            # 获取所有文本控件
            for child in window.GetChildren():
                try:
                    if child.ControlTypeName == "TextControl":
                        text = child.Name
                        if text and text.strip():
                            texts.append(text.strip())
                except:
                    continue

            # 递归查找深层文本
            text_controls = []
            self._find_text_controls(window, text_controls, max_depth=5)
            for ctrl in text_controls:
                try:
                    text = ctrl.Name
                    if text and text.strip() and text not in texts:
                        texts.append(text.strip())
                except:
                    continue

        except Exception as e:
            logger.debug(f"提取弹窗内容时出错: {e}")

        return " ".join(texts)

    def _find_text_controls(
        self,
        parent: auto.Control,
        result: List,
        current_depth: int = 0,
        max_depth: int = 5
    ) -> None:
        """递归查找文本控件"""
        if current_depth >= max_depth:
            return

        try:
            for child in parent.GetChildren():
                if child.ControlTypeName == "TextControl":
                    result.append(child)
                self._find_text_controls(child, result, current_depth + 1, max_depth)
        except:
            pass

    def _extract_buttons(self, window: auto.WindowControl) -> List[str]:
        """提取弹窗按钮"""
        buttons = []

        try:
            # 查找所有按钮
            for child in window.GetChildren():
                try:
                    if child.ControlTypeName == "ButtonControl":
                        name = child.Name
                        if name and name.strip():
                            buttons.append(name.strip())
                except:
                    continue

            # 递归查找
            button_controls = []
            self._find_button_controls(window, button_controls, max_depth=5)
            for ctrl in button_controls:
                try:
                    name = ctrl.Name
                    if name and name.strip() and name not in buttons:
                        buttons.append(name.strip())
                except:
                    continue

        except Exception as e:
            logger.debug(f"提取按钮时出错: {e}")

        return buttons

    def _find_button_controls(
        self,
        parent: auto.Control,
        result: List,
        current_depth: int = 0,
        max_depth: int = 5
    ) -> None:
        """递归查找按钮控件"""
        if current_depth >= max_depth:
            return

        try:
            for child in parent.GetChildren():
                if child.ControlTypeName == "ButtonControl":
                    result.append(child)
                self._find_button_controls(child, result, current_depth + 1, max_depth)
        except:
            pass

    def _determine_popup_type(self, title: str, content: str) -> PopupType:
        """判断弹窗类型"""
        combined = f"{title} {content}".lower()

        # 验证码类型
        if any(kw in combined for kw in ["验证码", "验证", "captcha", "滑动"]):
            return PopupType.CAPTCHA

        # 错误类型
        if any(kw in combined for kw in ["错误", "失败", "error", "异常"]):
            return PopupType.ERROR

        # 警告类型
        if any(kw in combined for kw in ["警告", "warning", "注意", "提醒"]):
            return PopupType.WARNING

        # 确认类型
        if any(kw in combined for kw in ["确认", "confirm", "是否", "确定"]):
            return PopupType.CONFIRM

        # 信息类型
        if any(kw in combined for kw in ["提示", "info", "通知"]):
            return PopupType.INFO

        return PopupType.UNKNOWN

    def _check_risk_level(self, title: str, content: str) -> Optional[RiskLevel]:
        """检查风险等级"""
        combined = f"{title} {content}"

        # 按风险等级从高到低检查
        for level in [RiskLevel.critical, RiskLevel.high, RiskLevel.medium, RiskLevel.low]:
            keywords = RISK_KEYWORDS.get(level, [])
            for keyword in keywords:
                if keyword in combined:
                    logger.warning(f"检测到风险关键词: '{keyword}', 级别: {level.value}")
                    return level

        return None

    # ========================================================
    # 弹窗处理
    # ========================================================

    def close_popup(self, popup: PopupInfo) -> bool:
        """
        关闭弹窗

        Args:
            popup: 弹窗信息

        Returns:
            是否成功关闭
        """
        if popup.window is None:
            logger.warning("弹窗窗口引用为空，无法关闭")
            return False

        # 风控弹窗不自动关闭
        if popup.requires_human:
            logger.warning(f"风控弹窗需要人工处理，不自动关闭: {popup.title}")
            return False

        try:
            window = popup.window

            # 优先使用 element_locator 查找关闭按钮
            try:
                close_btn = self._locator.find_element(
                    "popup.close_button",
                    parent=window,
                    timeout=1
                )
                if close_btn and close_btn.Exists(0, 0):
                    close_btn.Click()
                    time.sleep(0.3)
                    logger.info("已通过 element_locator 关闭弹窗")
                    return True
            except Exception:
                pass

            # 回退：尝试点击关闭按钮
            close_buttons = ["关闭", "取消", "×", "X", "Close", "Cancel"]
            for btn_name in close_buttons:
                btn = window.ButtonControl(Name=btn_name)
                if btn.Exists(0.5, 0):
                    btn.Click()
                    time.sleep(0.3)
                    logger.info(f"已点击 '{btn_name}' 关闭弹窗")
                    return True

            # 尝试按 Escape 关闭
            window.SendKeys("{Escape}")
            time.sleep(0.3)

            # 验证是否关闭
            if not window.Exists(0.5, 0):
                logger.info("弹窗已通过 Escape 关闭")
                return True

            # 尝试点击窗口外部区域
            # 这可能会关闭某些弹窗

            logger.warning("无法自动关闭弹窗")
            return False

        except Exception as e:
            logger.error(f"关闭弹窗时出错: {e}")
            return False

    def auto_handle_popup(self, popup: PopupInfo) -> PopupAction:
        """
        自动处理弹窗

        Args:
            popup: 弹窗信息

        Returns:
            执行的动作
        """
        # 风控弹窗需要告警
        if popup.is_risk_popup:
            logger.warning(f"检测到风控弹窗，需要告警: {popup.title}")
            return PopupAction.ALERT

        # 检查是否可以自动关闭
        combined = f"{popup.title} {popup.content}"
        for keyword in AUTO_CLOSE_KEYWORDS:
            if keyword in combined:
                if self.close_popup(popup):
                    logger.info(f"已自动关闭非关键弹窗: {popup.title}")
                    return PopupAction.CLOSE

        # 验证码需要人工处理
        if popup.popup_type == PopupType.CAPTCHA:
            return PopupAction.ALERT

        # 尝试点击确认
        if popup.popup_type == PopupType.CONFIRM:
            if self._click_confirm(popup):
                return PopupAction.CONFIRM

        # 默认忽略
        return PopupAction.IGNORE

    def _click_confirm(self, popup: PopupInfo) -> bool:
        """点击确认按钮"""
        if popup.window is None:
            return False

        try:
            # 优先使用 element_locator 查找确认按钮
            try:
                confirm_btn = self._locator.find_element(
                    "popup.confirm_button",
                    parent=popup.window,
                    timeout=1
                )
                if confirm_btn and confirm_btn.Exists(0, 0):
                    confirm_btn.Click()
                    time.sleep(0.3)
                    logger.info("已通过 element_locator 点击确认弹窗")
                    return True
            except Exception:
                pass

            # 回退：按名称查找
            confirm_names = ["确定", "确认", "好的", "OK", "是", "Yes"]
            for name in confirm_names:
                btn = popup.window.ButtonControl(Name=name)
                if btn.Exists(0.5, 0):
                    btn.Click()
                    time.sleep(0.3)
                    logger.info(f"已点击 '{name}' 确认弹窗")
                    return True

            return False

        except Exception as e:
            logger.error(f"点击确认按钮时出错: {e}")
            return False

    def is_risk_popup(self, popup: PopupInfo) -> bool:
        """
        判断是否为风控弹窗

        Args:
            popup: 弹窗信息

        Returns:
            是否为风控弹窗
        """
        return popup.is_risk_popup

    # ========================================================
    # 辅助方法
    # ========================================================

    def _take_screenshot(self, window: auto.WindowControl, prefix: str) -> Optional[str]:
        """保存弹窗截图"""
        try:
            self._screenshot_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{prefix}_{int(time.time())}.png"
            filepath = self._screenshot_dir / filename

            window.CaptureToImage(str(filepath))
            logger.debug(f"弹窗截图已保存: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"保存截图失败: {e}")
            return None

    def wait_for_popup_close(self, popup: PopupInfo, timeout: int = 10) -> bool:
        """
        等待弹窗关闭

        Args:
            popup: 弹窗信息
            timeout: 超时时间（秒）

        Returns:
            弹窗是否已关闭
        """
        if popup.window is None:
            return True

        start_time = time.time()
        while time.time() - start_time < timeout:
            if not popup.window.Exists(0.5, 0):
                return True
            time.sleep(0.5)

        return False


# ============================================================
# 便捷函数
# ============================================================

_detector: Optional[PopupDetector] = None


def get_popup_detector() -> PopupDetector:
    """获取弹窗检测器单例"""
    global _detector
    if _detector is None:
        _detector = PopupDetector()
    return _detector


def detect_popup(timeout: float = 1.0) -> Optional[PopupInfo]:
    """快捷检测弹窗"""
    return get_popup_detector().detect_popup(timeout)


def check_risk_keywords(text: str) -> Optional[RiskLevel]:
    """检查文本中的风控关键词"""
    for level in [RiskLevel.critical, RiskLevel.high, RiskLevel.medium, RiskLevel.low]:
        keywords = RISK_KEYWORDS.get(level, [])
        for keyword in keywords:
            if keyword in text:
                return level
    return None
