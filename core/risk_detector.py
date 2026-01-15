"""
风控检测器模块

功能:
- 窗口标题关键词检测
- 弹窗内容风控识别
- 截图 OCR 检测（可选）
- 操作结果判断
"""

import sys
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import uiautomation as auto

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.config_manager import get_config
from models.enums import RiskLevel
from core.popup_detector import (
    PopupDetector,
    PopupInfo,
    PopupType,
    RISK_KEYWORDS,
    get_popup_detector,
)
from core.wechat_controller import get_wechat_controller, WeChatStatus


logger = logging.getLogger(__name__)


# ============================================================
# OCR 支持（可选）
# ============================================================

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.debug("pytesseract 未安装，OCR 功能不可用")


# ============================================================
# 类型定义
# ============================================================

class RiskSource(Enum):
    """风险来源"""
    WINDOW_TITLE = "window_title"      # 窗口标题
    POPUP_CONTENT = "popup_content"    # 弹窗内容
    OCR_RESULT = "ocr_result"          # OCR 识别
    OPERATION_RESULT = "operation"     # 操作结果
    WECHAT_STATUS = "wechat_status"    # 微信状态


@dataclass
class RiskDetectionResult:
    """风险检测结果"""
    detected: bool
    risk_level: Optional[RiskLevel] = None
    source: Optional[RiskSource] = None
    keyword: str = ""
    detail: str = ""
    popup_info: Optional[PopupInfo] = None
    screenshot_path: Optional[str] = None
    detection_time: datetime = field(default_factory=datetime.now)

    @property
    def is_critical(self) -> bool:
        return self.risk_level == RiskLevel.critical

    @property
    def is_high(self) -> bool:
        return self.risk_level == RiskLevel.high

    @property
    def requires_shutdown(self) -> bool:
        """是否需要停机"""
        return self.detected and self.risk_level in (
            RiskLevel.medium, RiskLevel.high, RiskLevel.critical
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected": self.detected,
            "risk_level": self.risk_level.value if self.risk_level else None,
            "source": self.source.value if self.source else None,
            "keyword": self.keyword,
            "detail": self.detail,
            "popup_info": self.popup_info.to_dict() if self.popup_info else None,
            "screenshot_path": self.screenshot_path,
            "detection_time": self.detection_time.isoformat(),
        }


# ============================================================
# 窗口标题风控关键词
# ============================================================

WINDOW_TITLE_KEYWORDS: Dict[RiskLevel, List[str]] = {
    RiskLevel.critical: [
        "账号已被封禁",
        "登录受限",
        "账号异常",
        "无法登录",
    ],
    RiskLevel.high: [
        "安全验证",
        "验证身份",
        "异常检测",
    ],
    RiskLevel.medium: [
        "操作频繁",
        "请稍后再试",
    ],
}


# ============================================================
# 风控检测器
# ============================================================

class RiskDetector:
    """
    风控检测器

    综合检测微信运行中的各类风控信号
    """

    def __init__(self):
        """初始化风控检测器"""
        self._popup_detector = get_popup_detector()
        self._controller = get_wechat_controller()

        self._screenshot_dir = Path(get_config("advanced.screenshot_dir", "screenshots"))
        self._save_screenshots = get_config("advanced.save_screenshots", False)
        self._enable_ocr = get_config("advanced.enable_ocr", False) and OCR_AVAILABLE

        # 检测回调
        self._risk_callbacks: List[Callable[[RiskDetectionResult], None]] = []

        # 检测历史
        self._detection_history: List[RiskDetectionResult] = []
        self._max_history = 100

        logger.debug(f"风控检测器初始化完成, OCR: {'启用' if self._enable_ocr else '禁用'}")

    # ========================================================
    # 主要接口
    # ========================================================

    def detect_risk(self) -> RiskDetectionResult:
        """
        执行全面的风控检测

        Returns:
            风控检测结果
        """
        # 1. 检查微信状态
        result = self._check_wechat_status()
        if result.detected:
            self._handle_detection(result)
            return result

        # 2. 检查窗口标题
        result = self.check_window_title()
        if result.detected:
            self._handle_detection(result)
            return result

        # 3. 检查弹窗内容
        result = self.check_popup_content()
        if result.detected:
            self._handle_detection(result)
            return result

        # 4. OCR 检测（如果启用）
        if self._enable_ocr:
            result = self._check_ocr()
            if result.detected:
                self._handle_detection(result)
                return result

        # 未检测到风险
        return RiskDetectionResult(detected=False)

    def check_window_title(self) -> RiskDetectionResult:
        """
        检查窗口标题中的风控关键词

        Returns:
            检测结果
        """
        try:
            # 获取所有微信相关窗口
            windows = self._get_wechat_windows()

            for window in windows:
                try:
                    title = window.Name or ""
                    if not title:
                        continue

                    # 检查风控关键词
                    for level in [RiskLevel.critical, RiskLevel.high, RiskLevel.medium]:
                        keywords = WINDOW_TITLE_KEYWORDS.get(level, [])
                        for keyword in keywords:
                            if keyword in title:
                                logger.warning(
                                    f"窗口标题检测到风控关键词: '{keyword}', "
                                    f"标题: '{title}', 级别: {level.value}"
                                )

                                screenshot = self._take_screenshot(window, "risk_title")

                                return RiskDetectionResult(
                                    detected=True,
                                    risk_level=level,
                                    source=RiskSource.WINDOW_TITLE,
                                    keyword=keyword,
                                    detail=f"窗口标题: {title}",
                                    screenshot_path=screenshot,
                                )

                except Exception as e:
                    logger.debug(f"检查窗口标题时出错: {e}")
                    continue

        except Exception as e:
            logger.error(f"窗口标题检测失败: {e}")

        return RiskDetectionResult(detected=False)

    def check_popup_content(self) -> RiskDetectionResult:
        """
        检查弹窗内容中的风控信号

        Returns:
            检测结果
        """
        try:
            # 检测弹窗
            popup = self._popup_detector.detect_popup(timeout=0.5)

            if popup and popup.is_risk_popup:
                logger.warning(
                    f"检测到风控弹窗: 类型={popup.popup_type.value}, "
                    f"标题='{popup.title}', 级别={popup.risk_level.value if popup.risk_level else 'unknown'}"
                )

                return RiskDetectionResult(
                    detected=True,
                    risk_level=popup.risk_level or RiskLevel.medium,
                    source=RiskSource.POPUP_CONTENT,
                    keyword=self._find_matched_keyword(popup.title, popup.content),
                    detail=f"弹窗: {popup.title} - {popup.content}",
                    popup_info=popup,
                    screenshot_path=popup.screenshot_path,
                )

            # 即使没有检测到风控弹窗，也检查所有弹窗的内容
            all_popups = self._popup_detector.detect_all_popups()
            for p in all_popups:
                combined = f"{p.title} {p.content}"
                risk_level = self._check_text_risk(combined)
                if risk_level:
                    return RiskDetectionResult(
                        detected=True,
                        risk_level=risk_level,
                        source=RiskSource.POPUP_CONTENT,
                        keyword=self._find_matched_keyword(p.title, p.content),
                        detail=f"弹窗: {p.title} - {p.content}",
                        popup_info=p,
                        screenshot_path=p.screenshot_path,
                    )

        except Exception as e:
            logger.error(f"弹窗内容检测失败: {e}")

        return RiskDetectionResult(detected=False)

    def check_operation_result(
        self,
        success: bool,
        error_message: str = ""
    ) -> RiskDetectionResult:
        """
        检查操作结果中的风控信号

        Args:
            success: 操作是否成功
            error_message: 错误消息

        Returns:
            检测结果
        """
        if success:
            return RiskDetectionResult(detected=False)

        # 检查错误消息中的风控关键词
        risk_level = self._check_text_risk(error_message)

        if risk_level:
            logger.warning(
                f"操作结果检测到风控信号: '{error_message}', 级别: {risk_level.value}"
            )

            return RiskDetectionResult(
                detected=True,
                risk_level=risk_level,
                source=RiskSource.OPERATION_RESULT,
                keyword=self._find_matched_keyword(error_message),
                detail=f"操作错误: {error_message}",
            )

        return RiskDetectionResult(detected=False)

    # ========================================================
    # 内部检测方法
    # ========================================================

    def _check_wechat_status(self) -> RiskDetectionResult:
        """检查微信状态"""
        try:
            status = self._controller.check_login_status()

            if status == WeChatStatus.NOT_LOGGED_IN:
                logger.warning("微信未登录，可能存在风险")
                return RiskDetectionResult(
                    detected=True,
                    risk_level=RiskLevel.high,
                    source=RiskSource.WECHAT_STATUS,
                    keyword="未登录",
                    detail="微信处于未登录状态",
                )

            if status == WeChatStatus.LOCKED:
                return RiskDetectionResult(
                    detected=True,
                    risk_level=RiskLevel.medium,
                    source=RiskSource.WECHAT_STATUS,
                    keyword="已锁定",
                    detail="微信处于锁定状态",
                )

            if status == WeChatStatus.NOT_RUNNING:
                return RiskDetectionResult(
                    detected=True,
                    risk_level=RiskLevel.high,
                    source=RiskSource.WECHAT_STATUS,
                    keyword="未运行",
                    detail="微信进程未运行",
                )

        except Exception as e:
            logger.error(f"检查微信状态失败: {e}")

        return RiskDetectionResult(detected=False)

    def _check_ocr(self) -> RiskDetectionResult:
        """使用 OCR 检测屏幕内容"""
        if not self._enable_ocr or not OCR_AVAILABLE:
            return RiskDetectionResult(detected=False)

        try:
            # 获取主窗口截图
            main_window = self._controller.get_main_window()
            if not main_window:
                return RiskDetectionResult(detected=False)

            # 截图并进行 OCR
            screenshot_path = self._take_screenshot(main_window, "ocr_check")
            if not screenshot_path:
                return RiskDetectionResult(detected=False)

            # OCR 识别
            image = Image.open(screenshot_path)
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')

            # 检查识别结果中的风控关键词
            risk_level = self._check_text_risk(text)

            if risk_level:
                keyword = self._find_matched_keyword(text)
                logger.warning(f"OCR 检测到风控关键词: '{keyword}', 级别: {risk_level.value}")

                return RiskDetectionResult(
                    detected=True,
                    risk_level=risk_level,
                    source=RiskSource.OCR_RESULT,
                    keyword=keyword,
                    detail=f"OCR 识别内容包含风控关键词",
                    screenshot_path=screenshot_path,
                )

        except Exception as e:
            logger.error(f"OCR 检测失败: {e}")

        return RiskDetectionResult(detected=False)

    def _check_text_risk(self, text: str) -> Optional[RiskLevel]:
        """检查文本中的风控关键词"""
        if not text:
            return None

        for level in [RiskLevel.critical, RiskLevel.high, RiskLevel.medium, RiskLevel.low]:
            keywords = RISK_KEYWORDS.get(level, [])
            for keyword in keywords:
                if keyword in text:
                    return level

        return None

    def _find_matched_keyword(self, *texts: str) -> str:
        """查找匹配的关键词"""
        combined = " ".join(texts)

        for level in [RiskLevel.critical, RiskLevel.high, RiskLevel.medium, RiskLevel.low]:
            keywords = RISK_KEYWORDS.get(level, [])
            for keyword in keywords:
                if keyword in combined:
                    return keyword

        return ""

    def _get_wechat_windows(self) -> List[auto.WindowControl]:
        """获取所有微信相关窗口"""
        windows = []

        # 主窗口
        main_class_names = ["WeChatMainWndForPC", "WeChatLoginWndForPC"]
        for class_name in main_class_names:
            try:
                window = auto.WindowControl(searchDepth=1, ClassName=class_name)
                if window.Exists(0.3, 0):
                    windows.append(window)
            except:
                pass

        # 其他微信窗口
        other_class_names = ["ChatWnd", "SnsWnd", "SnsEditWnd", "SelectContactWnd"]
        for class_name in other_class_names:
            try:
                window = auto.WindowControl(searchDepth=1, ClassName=class_name)
                if window.Exists(0.3, 0):
                    windows.append(window)
            except:
                pass

        return windows

    # ========================================================
    # 回调和历史
    # ========================================================

    def _handle_detection(self, result: RiskDetectionResult) -> None:
        """处理检测结果"""
        # 记录历史
        self._detection_history.append(result)
        if len(self._detection_history) > self._max_history:
            self._detection_history = self._detection_history[-self._max_history:]

        # 触发回调
        for callback in self._risk_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"风控回调执行失败: {e}")

    def register_callback(self, callback: Callable[[RiskDetectionResult], None]) -> None:
        """注册风控检测回调"""
        self._risk_callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[RiskDetectionResult], None]) -> None:
        """注销风控检测回调"""
        if callback in self._risk_callbacks:
            self._risk_callbacks.remove(callback)

    def get_detection_history(self, limit: int = 10) -> List[RiskDetectionResult]:
        """获取检测历史"""
        return self._detection_history[-limit:]

    def get_recent_risks(self, minutes: int = 60) -> List[RiskDetectionResult]:
        """获取最近一段时间的风险检测结果"""
        cutoff = datetime.now().timestamp() - minutes * 60
        return [
            r for r in self._detection_history
            if r.detected and r.detection_time.timestamp() > cutoff
        ]

    # ========================================================
    # 辅助方法
    # ========================================================

    def _take_screenshot(self, window: auto.WindowControl, prefix: str) -> Optional[str]:
        """保存截图"""
        if not self._save_screenshots:
            return None

        try:
            self._screenshot_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{prefix}_{int(time.time())}.png"
            filepath = self._screenshot_dir / filename

            window.CaptureToImage(str(filepath))
            logger.debug(f"截图已保存: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"保存截图失败: {e}")
            return None

    def clear_history(self) -> None:
        """清空检测历史"""
        self._detection_history.clear()


# ============================================================
# 便捷函数
# ============================================================

_detector: Optional[RiskDetector] = None


def get_risk_detector() -> RiskDetector:
    """获取风控检测器单例"""
    global _detector
    if _detector is None:
        _detector = RiskDetector()
    return _detector


def detect_risk() -> RiskDetectionResult:
    """快捷风控检测"""
    return get_risk_detector().detect_risk()


def check_text_for_risk(text: str) -> Optional[RiskLevel]:
    """检查文本中的风控关键词"""
    for level in [RiskLevel.critical, RiskLevel.high, RiskLevel.medium, RiskLevel.low]:
        keywords = RISK_KEYWORDS.get(level, [])
        for keyword in keywords:
            if keyword in text:
                return level
    return None
