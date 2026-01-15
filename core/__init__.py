# Core package - 微信窗口控制核心模块

from .display_manager import (
    DisplayManager,
    MonitorInfo,
    DisplayInfo,
    get_display_manager,
)

from .clipboard_manager import (
    ClipboardManager,
    ClipboardContent,
    ClipboardFormat,
    ClipboardError,
    copy_text,
    copy_image,
    get_clipboard_text,
)

from .env_checker import (
    EnvChecker,
    EnvCheckResult,
    CheckResult,
    CheckStatus,
    DisplayCheckInfo,
    quick_check,
    check_wechat_ready,
)

from .wechat_controller import (
    WeChatController,
    WeChatStatus,
    Rect,
    get_wechat_controller,
)

from .moment_sender import (
    MomentSender,
    SendResult as MomentSendResult,
    get_moment_sender,
    send_moment,
)

from .group_sender import (
    GroupSender,
    SendResult as GroupSendResult,
    BatchSendResult,
    get_group_sender,
    send_message,
    batch_send,
)

from .element_locator import (
    ElementLocator,
    ElementInfo,
    get_element_locator,
)

from .popup_detector import (
    PopupDetector,
    PopupType,
    PopupInfo,
    get_popup_detector,
)

from .risk_detector import (
    RiskDetector,
    RiskSource,
    RiskDetectionResult,
    get_risk_detector,
)

from .shutdown_controller import (
    ShutdownController,
    ShutdownInfo,
    StateSnapshot,
    get_shutdown_controller,
)

# 从 models.enums 重新导出 SendStatus 以保持向后兼容
from models.enums import SendStatus

__all__ = [
    # display_manager
    "DisplayManager",
    "MonitorInfo",
    "DisplayInfo",
    "get_display_manager",
    # clipboard_manager
    "ClipboardManager",
    "ClipboardContent",
    "ClipboardFormat",
    "ClipboardError",
    "copy_text",
    "copy_image",
    "get_clipboard_text",
    # env_checker
    "EnvChecker",
    "EnvCheckResult",
    "CheckResult",
    "CheckStatus",
    "DisplayCheckInfo",
    "quick_check",
    "check_wechat_ready",
    # wechat_controller
    "WeChatController",
    "WeChatStatus",
    "Rect",
    "get_wechat_controller",
    # moment_sender
    "MomentSender",
    "MomentSendResult",
    "get_moment_sender",
    "send_moment",
    # group_sender
    "GroupSender",
    "GroupSendResult",
    "BatchSendResult",
    "get_group_sender",
    "send_message",
    "batch_send",
    # element_locator
    "ElementLocator",
    "ElementInfo",
    "get_element_locator",
    # popup_detector
    "PopupDetector",
    "PopupType",
    "PopupInfo",
    "get_popup_detector",
    # risk_detector
    "RiskDetector",
    "RiskSource",
    "RiskDetectionResult",
    "get_risk_detector",
    # shutdown_controller
    "ShutdownController",
    "ShutdownInfo",
    "StateSnapshot",
    "get_shutdown_controller",
    # 统一枚举
    "SendStatus",
]
