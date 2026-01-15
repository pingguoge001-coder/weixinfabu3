"""
微信控制模块

提供统一的微信窗口控制接口
"""

from .controller import WeChatController
from .window_manager import WindowManager, Rect, MonitorInfo
from .version_detector import VersionDetector
from .login_checker import LoginChecker, WeChatStatus
from .navigation import NavigationOperator


# 单例控制器
_controller = None


def get_wechat_controller() -> WeChatController:
    """
    获取微信控制器单例

    Returns:
        WeChatController 实例
    """
    global _controller
    if _controller is None:
        _controller = WeChatController()
    return _controller


# 导出所有公共类和函数
__all__ = [
    # 主控制器
    'WeChatController',
    'get_wechat_controller',

    # 子模块
    'WindowManager',
    'VersionDetector',
    'LoginChecker',
    'NavigationOperator',

    # 数据类型
    'Rect',
    'MonitorInfo',
    'WeChatStatus',
]
