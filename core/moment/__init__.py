"""
朋友圈发布模块

提供完整的朋友圈自动发布功能，包括：
- MomentSender: 朋友圈发布器主类
- SendResult: 发送结果数据类
- 各种处理器和工具类

使用示例:
    from core.moment import MomentSender, SendResult
    from models.content import Content

    sender = MomentSender()
    result = sender.send_moment(content)
    if result.is_success:
        print("发布成功")
"""

# 导出主要类和函数
from .sender import (
    MomentSender,
    SendResult,
    get_moment_sender,
    send_moment,
)

# 导出处理器（高级用法）
from .window_handler import WindowHandler, create_window_handler
from .image_handler import ImageHandler, create_image_handler
from .text_handler import TextHandler, create_text_handler
from .publish_handler import PublishHandler, create_publish_handler
from .locator import ElementLocator, create_locator


__all__ = [
    # 主要接口
    "MomentSender",
    "SendResult",
    "get_moment_sender",
    "send_moment",

    # 处理器类（高级用法）
    "WindowHandler",
    "ImageHandler",
    "TextHandler",
    "PublishHandler",
    "ElementLocator",

    # 工厂函数
    "create_window_handler",
    "create_image_handler",
    "create_text_handler",
    "create_publish_handler",
    "create_locator",
]


__version__ = "2.0.0"
__author__ = "wechat-fabu"
__description__ = "朋友圈自动发布模块（重构版）"
