"""
消息发送器基类

提供微信自动化发送器的通用功能：
- 微信窗口管理
- 剪贴板操作
- 截图功能
- 步骤执行和回调
- 延迟和超时管理

所有具体的发送器（如 MomentSender、GroupSender）都应继承此基类。
"""

import time
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime

import pyautogui
import uiautomation as auto

from .wechat_controller import WeChatController, get_wechat_controller, WeChatStatus
from .clipboard_manager import ClipboardManager
from .exceptions import WeChatStatusError

logger = logging.getLogger(__name__)


# ============================================================
# 基础配置常量
# ============================================================

# 操作间隔时间（秒）
STEP_DELAY = 0.8          # 步骤间隔
SHORT_DELAY = 0.3         # 短延迟
LONG_DELAY = 1.5          # 长延迟
PAGE_LOAD_DELAY = 2.0     # 页面加载延迟

# 超时设置（秒）
ELEMENT_TIMEOUT = 10      # 元素查找超时
OPERATION_TIMEOUT = 30    # 操作超时


# ============================================================
# 抽象基类
# ============================================================

class BaseSender(ABC):
    """
    消息发送器抽象基类

    提供所有发送器的通用功能，子类必须实现抽象方法。

    抽象方法：
        send() - 发送入口（供外部调用）
        _do_send() - 实际发送逻辑（内部实现）

    共同功能：
        - 微信状态检查和窗口激活
        - 剪贴板备份/恢复
        - 截图功能
        - 步骤执行和回调机制
        - 延迟和超时管理
    """

    def __init__(
        self,
        wechat_controller: Optional[WeChatController] = None,
        screenshot_dir: Optional[Path] = None,
        save_screenshots: bool = True,
        step_callback: Optional[Callable[[str, bool], None]] = None,
    ):
        """
        初始化发送器基类

        Args:
            wechat_controller: 微信控制器实例（可选，默认获取全局实例）
            screenshot_dir: 截图保存目录（可选，默认 "screenshots"）
            save_screenshots: 是否保存失败截图
            step_callback: 步骤回调函数 (step_name: str, success: bool) -> None
        """
        # 核心组件
        self._controller = wechat_controller or get_wechat_controller()
        self._clipboard = ClipboardManager()

        # 截图配置
        self._screenshot_dir = screenshot_dir or Path("screenshots")
        self._save_screenshots = save_screenshots
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

        # 回调
        self._step_callback = step_callback

        # 状态
        self._current_step: str = ""
        self._wechat_version: Optional[str] = None  # "v4" 或 "v3"

        # 配置 pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1

        logger.debug(f"{self.__class__.__name__} 初始化完成")

    # ========================================================
    # 抽象方法（子类必须实现）
    # ========================================================

    @abstractmethod
    def send(self, *args, **kwargs):
        """
        发送入口（抽象方法）

        子类必须实现此方法作为外部调用接口。

        Returns:
            发送结果对象（具体类型由子类定义）
        """
        pass

    @abstractmethod
    def _do_send(self, *args, **kwargs) -> bool:
        """
        实际发送逻辑（抽象方法）

        子类必须实现此方法来完成具体的发送操作。

        Returns:
            是否发送成功
        """
        pass

    # ========================================================
    # 微信状态管理
    # ========================================================

    def _ensure_wechat_ready(self) -> bool:
        """
        确保微信已就绪

        检查微信登录状态、激活窗口、重置窗口位置

        Returns:
            微信是否就绪

        Raises:
            WeChatStatusError: 微信状态异常时
        """
        try:
            # 检查登录状态
            status = self._controller.check_login_status()
            if status != WeChatStatus.LOGGED_IN:
                logger.error(f"微信状态异常: {status.value}")
                raise WeChatStatusError(
                    f"微信状态异常: {status.value}",
                    context={"status": status.value}
                )

            # 重置微信主窗口位置和大小
            self._controller.reset_main_window_position()

            # 激活窗口
            if not self._controller.activate_window():
                logger.error("激活微信窗口失败")
                return False

            if not self._controller.is_main_panel():
                logger.error("微信主面板识别失败")
                return False

            # 检测微信版本
            self._wechat_version = self._controller.get_detected_version()
            logger.debug(f"微信版本: {self._wechat_version}")

            time.sleep(STEP_DELAY)
            return True

        except WeChatStatusError:
            raise
        except Exception as e:
            logger.error(f"确保微信就绪时出错: {e}")
            return False

    # ========================================================
    # 截图功能
    # ========================================================

    def _take_screenshot(self, name: str) -> Optional[str]:
        """
        保存截图

        Args:
            name: 截图文件名前缀

        Returns:
            截图文件路径，失败返回 None
        """
        if not self._save_screenshots:
            return None

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = self._screenshot_dir / filename

            # 全屏截图
            screenshot = pyautogui.screenshot()
            screenshot.save(str(filepath))

            logger.debug(f"已保存截图: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.warning(f"保存截图失败: {e}")
            return None

    def _take_error_screenshot(self, name: str) -> Optional[str]:
        """
        保存错误截图（_take_screenshot 的别名，保持兼容性）

        Args:
            name: 截图文件名前缀

        Returns:
            截图文件路径，失败返回 None
        """
        return self._take_screenshot(name)

    # ========================================================
    # 步骤执行和回调
    # ========================================================

    def _step(self, name: str, action: Callable[[], bool]) -> bool:
        """
        执行步骤并处理回调

        执行指定的动作，记录步骤状态，触发回调，失败时保存截图。

        Args:
            name: 步骤名称（用于日志和回调）
            action: 执行动作的可调用对象，返回 bool 表示成功/失败

        Returns:
            步骤是否成功
        """
        self._current_step = name
        logger.debug(f"执行步骤: {name}")

        try:
            success = action()

            # 触发回调
            if self._step_callback:
                try:
                    self._step_callback(name, success)
                except Exception as e:
                    logger.warning(f"步骤回调出错: {e}")

            # 失败时截图
            if not success:
                logger.warning(f"步骤失败: {name}")
                self._take_screenshot(f"step_failed_{name}")

            return success

        except Exception as e:
            logger.error(f"步骤异常: {name}, {e}")
            self._take_screenshot(f"step_error_{name}")

            # 触发回调（失败）
            if self._step_callback:
                try:
                    self._step_callback(name, False)
                except Exception:
                    pass

            return False

    def _step_with_result(self, name: str, action: Callable[[], dict]) -> dict:
        """
        执行步骤并返回详细结果

        与 _step 类似，但动作返回字典而非布尔值，用于需要详细结果的场景。

        Args:
            name: 步骤名称
            action: 执行动作的可调用对象，返回字典（必须包含 "success" 键）

        Returns:
            动作返回的结果字典
        """
        self._current_step = name
        logger.debug(f"执行步骤: {name}")

        try:
            result = action()

            # 触发回调
            if self._step_callback:
                try:
                    success = result.get("success", False)
                    self._step_callback(name, success)
                except Exception as e:
                    logger.warning(f"步骤回调出错: {e}")

            return result

        except Exception as e:
            logger.error(f"步骤异常: {name}, {e}")
            self._take_screenshot(f"step_error_{name}")
            return {"success": False, "error": str(e)}

    # ========================================================
    # 等待和返回
    # ========================================================

    def _wait_for_send_complete(self, timeout: int = OPERATION_TIMEOUT) -> bool:
        """
        等待发送完成（通用实现）

        检查是否有发送失败标识或进度条，超时后返回。
        子类可以重写此方法以实现特定的等待逻辑。

        Args:
            timeout: 超时时间（秒）

        Returns:
            是否发送成功
        """
        start_time = time.time()
        main_window = self._controller.get_main_window()

        if not main_window:
            logger.warning("无法获取主窗口，跳过发送完成检查")
            return True

        while time.time() - start_time < timeout:
            try:
                # 检查是否有发送失败标识
                fail_btn = main_window.ButtonControl(
                    searchDepth=15,
                    Name="重新发送"
                )
                if fail_btn.Exists(0.5, 0):
                    logger.warning("检测到发送失败标识")
                    return False

                # 检查发送中状态（进度条）
                progress = main_window.ProgressBarControl(searchDepth=15)
                if progress.Exists(0.3, 0):
                    # 还在发送中
                    time.sleep(0.5)
                    continue

                # 没有失败标识且没有进度条，认为发送成功
                return True

            except Exception as e:
                logger.debug(f"检查发送状态时出错: {e}")

            time.sleep(0.5)

        logger.warning("等待发送完成超时")
        return False

    def _return_to_main(self) -> bool:
        """
        返回主界面（通用实现）

        关闭当前窗口并返回微信主界面。
        子类可以重写此方法以实现特定的返回逻辑。

        Returns:
            是否成功返回
        """
        try:
            # 使用 Escape 键关闭
            auto.SendKeys("{Escape}")
            time.sleep(SHORT_DELAY)

            # 激活主窗口
            if self._controller.activate_window():
                logger.debug("已返回主界面")
                return True

            return False

        except Exception as e:
            logger.error(f"返回主界面失败: {e}")
            return False

    # ========================================================
    # 工具方法
    # ========================================================

    def get_wechat_version(self) -> Optional[str]:
        """
        获取检测到的微信版本

        Returns:
            微信版本字符串 ("v3" 或 "v4")，未检测返回 None
        """
        return self._wechat_version

    def is_v4(self) -> bool:
        """
        判断是否为微信 4.0+

        Returns:
            是否为 v4
        """
        return self._wechat_version == "v4"

    def get_current_step(self) -> str:
        """
        获取当前执行的步骤名称

        Returns:
            步骤名称
        """
        return self._current_step


# ============================================================
# 便捷函数
# ============================================================

def create_sender(sender_class: type, **kwargs) -> BaseSender:
    """
    创建发送器实例的工厂函数

    Args:
        sender_class: 发送器类（必须继承 BaseSender）
        **kwargs: 传递给发送器构造函数的参数

    Returns:
        发送器实例

    Raises:
        TypeError: 如果 sender_class 不是 BaseSender 的子类
    """
    if not issubclass(sender_class, BaseSender):
        raise TypeError(f"{sender_class.__name__} 必须继承 BaseSender")

    return sender_class(**kwargs)


# ============================================================
# 示例用法
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=== BaseSender 基类示例 ===\n")

    # 演示如何继承 BaseSender
    class DemoSender(BaseSender):
        """演示发送器"""

        def send(self, message: str):
            """发送消息"""
            logger.info(f"开始发送: {message}")

            # 备份剪贴板
            self._clipboard.backup()

            try:
                # 确保微信就绪
                if not self._step("check_wechat", self._ensure_wechat_ready):
                    return False

                # 执行发送
                if not self._step("do_send", lambda: self._do_send(message)):
                    return False

                # 等待完成
                if not self._step("wait_complete", self._wait_for_send_complete):
                    return False

                logger.info("发送成功")
                return True

            finally:
                # 恢复剪贴板
                self._clipboard.restore()

        def _do_send(self, message: str) -> bool:
            """实际发送逻辑"""
            logger.info(f"正在发送: {message}")
            time.sleep(1)  # 模拟发送
            return True

    # 测试
    def step_callback(step: str, success: bool):
        status = "成功" if success else "失败"
        print(f"  步骤回调: {step} - {status}")

    sender = DemoSender(step_callback=step_callback)
    print(f"微信版本: {sender.get_wechat_version()}")
    print(f"是否 v4: {sender.is_v4()}")

    # sender.send("测试消息")  # 需要微信运行才能测试

    print("\n=== 示例完成 ===")
