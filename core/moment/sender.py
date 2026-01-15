"""
朋友圈发送器主模块

整合所有朋友圈发布功能模块:
- WindowHandler: 窗口管理
- ImageHandler: 图片处理
- TextHandler: 文案处理
- PublishHandler: 发布操作
- ElementLocator: 元素定位

提供统一的 MomentSender 接口
"""

import time
import ctypes
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

import pyautogui

from models.content import Content
from models.enums import Channel, SendStatus
from services.config_manager import get_config
from core.wechat_controller import WeChatController, get_wechat_controller, WeChatStatus
from core.clipboard_manager import ClipboardManager

from .window_handler import WindowHandler, create_window_handler
from .image_handler import ImageHandler, create_image_handler
from .text_handler import TextHandler, create_text_handler
from .publish_handler import PublishHandler, create_publish_handler
from .locator import ElementLocator, create_locator

logger = logging.getLogger(__name__)


# ============================================================
# 配置常量
# ============================================================

# 操作间隔时间（秒）
STEP_DELAY = 0.8


@dataclass
class SendResult:
    """发送结果"""
    status: SendStatus
    content_code: str = ""
    message: str = ""
    screenshot_path: Optional[str] = None
    images_added: int = 0
    images_failed: int = 0
    error_step: Optional[str] = None
    duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_success(self) -> bool:
        return self.status == SendStatus.SUCCESS

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "content_code": self.content_code,
            "message": self.message,
            "screenshot_path": self.screenshot_path,
            "images_added": self.images_added,
            "images_failed": self.images_failed,
            "error_step": self.error_step,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat(),
        }


class MomentSender:
    """
    朋友圈发布器

    发布流程 (微信 4.0):
    1. 激活微信窗口
    2. 点击导航栏"朋友圈"按钮
    3. 等待朋友圈页面加载
    4. 点击发布按钮
    5. 添加图片（如有）
    6. 输入文案
    7. 点击发表
    8. 等待发布完成
    9. 返回主界面

    发布流程 (微信 3.x):
    1. 激活微信窗口
    2. 点击"发现"标签
    3. 点击"朋友圈"入口
    4-9. 同上
    """

    def __init__(
        self,
        wechat_controller: Optional[WeChatController] = None,
        screenshot_dir: Optional[Path] = None,
        save_screenshots: bool = True,
        step_callback: Optional[Callable[[str, bool], None]] = None,
    ):
        """
        初始化朋友圈发布器

        Args:
            wechat_controller: 微信控制器实例
            screenshot_dir: 截图保存目录
            save_screenshots: 是否保存失败截图
            step_callback: 步骤回调函数 (step_name, success)
        """
        self._controller = wechat_controller or get_wechat_controller()
        self._clipboard = ClipboardManager()
        self._screenshot_dir = screenshot_dir or Path("screenshots")
        self._save_screenshots = save_screenshots
        self._step_callback = step_callback

        # 确保截图目录存在
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

        # 创建功能模块
        self._window_handler = create_window_handler(self._controller)
        self._image_handler = create_image_handler(self._clipboard)
        self._text_handler = create_text_handler(self._clipboard)
        self._publish_handler = create_publish_handler()
        self._locator = create_locator()

        # 状态
        self._current_step: str = ""
        self._folder_path: Optional[str] = None

        # 配置 pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1

        logger.debug("朋友圈发布器初始化完成")

    # ========================================================
    # 主发布方法
    # ========================================================

    def send_moment(self, content: Content, folder_path: Optional[str] = None) -> SendResult:
        """
        发布朋友圈

        Args:
            content: 发布内容
            folder_path: 图片所在文件夹路径（用于文件对话框导航）

        Returns:
            SendResult
        """
        # 保存文件夹路径
        self._folder_path = folder_path
        start_time = time.time()
        result = SendResult(
            status=SendStatus.FAILED,
            content_code=content.content_code,
        )

        # 验证内容
        valid, error = content.validate()
        if not valid:
            result.message = f"内容验证失败: {error}"
            logger.error(result.message)
            return result

        # 检查渠道
        if content.channel != Channel.moment:
            result.message = f"内容渠道不匹配: {content.channel.value}"
            logger.error(result.message)
            return result

        has_images = content.has_images
        logger.info(f"开始发布朋友圈: {content.content_code}, "
                   f"{'图文' if has_images else '纯文字'}, "
                   f"图片数: {content.image_count}")

        try:
            # 备份剪贴板
            self._clipboard.backup()

            # Step 1: 激活微信窗口
            if not self._step("activate_wechat", self._activate_wechat):
                result.error_step = "activate_wechat"
                result.message = "激活微信窗口失败"
                return self._finalize_result(result, start_time)

            # Step 2: 导航到朋友圈
            if not self._step("navigate_to_moment", self._navigate_to_moment):
                result.error_step = "navigate_to_moment"
                result.message = "导航到朋友圈失败"
                return self._finalize_result(result, start_time)

            # Step 3: 打开编辑框
            if not self._step("open_compose", lambda: self._open_compose_dialog(has_images)):
                result.error_step = "open_compose"
                result.message = "打开编辑框失败"
                return self._finalize_result(result, start_time)

            # Step 4: 添加图片（如有）
            if has_images:
                images_result = self._step_with_result(
                    "add_images",
                    lambda: self._add_images(content.image_paths)
                )
                result.images_added = images_result.get("added", 0)
                result.images_failed = images_result.get("failed", 0)

                if result.images_added == 0:
                    result.error_step = "add_images"
                    result.message = "添加图片失败"
                    self._cancel_compose()
                    return self._finalize_result(result, start_time)

            # Step 5: 输入文案（包含标签）
            full_text = content.full_text
            if full_text:
                if not self._step("input_text", lambda: self._input_text(full_text)):
                    result.error_step = "input_text"
                    result.message = "输入文案失败"
                    self._cancel_compose()
                    return self._finalize_result(result, start_time)

            # Step 6: 点击发表
            if not self._step("click_publish", self._click_publish):
                result.error_step = "click_publish"
                result.message = "点击发表按钮失败"
                return self._finalize_result(result, start_time)

            # Step 7: 等待发布完成
            if not self._step("wait_publish", self._wait_for_publish_complete):
                result.error_step = "wait_publish"
                result.message = "等待发布完成超时"
                return self._finalize_result(result, start_time)

            # Step 8: 查看发布的朋友圈
            self._step("view_moment", lambda: self._view_published_moment(content.product_link))

            # Step 9: 返回主界面
            self._step("return_main", self._return_to_main)

            # 成功
            result.status = SendStatus.SUCCESS
            result.message = "发布成功"
            logger.info(f"朋友圈发布成功: {content.content_code}")

        except Exception as e:
            result.error_step = self._current_step
            result.message = f"发布异常: {str(e)}"
            result.screenshot_path = self._take_error_screenshot(f"error_{content.content_code}")
            logger.exception(f"朋友圈发布异常: {content.content_code}")

        finally:
            # 恢复剪贴板
            try:
                self._clipboard.restore()
            except Exception:
                pass

        return self._finalize_result(result, start_time)

    # ========================================================
    # 步骤执行辅助
    # ========================================================

    def _step(self, name: str, action: Callable[[], bool]) -> bool:
        """执行步骤"""
        self._current_step = name
        logger.debug(f"执行步骤: {name}")

        try:
            success = action()

            if self._step_callback:
                self._step_callback(name, success)

            if not success:
                logger.warning(f"步骤失败: {name}")
                self._take_error_screenshot(f"step_failed_{name}")

            return success

        except Exception as e:
            logger.error(f"步骤异常: {name}, {e}")
            self._take_error_screenshot(f"step_error_{name}")
            return False

    def _step_with_result(self, name: str, action: Callable[[], dict]) -> dict:
        """执行步骤并返回详细结果"""
        self._current_step = name
        logger.debug(f"执行步骤: {name}")

        try:
            result = action()

            if self._step_callback:
                success = result.get("success", False)
                self._step_callback(name, success)

            return result

        except Exception as e:
            logger.error(f"步骤异常: {name}, {e}")
            self._take_error_screenshot(f"step_error_{name}")
            return {"success": False, "error": str(e)}

    def _finalize_result(self, result: SendResult, start_time: float) -> SendResult:
        """完成结果处理"""
        result.duration = time.time() - start_time

        if result.status == SendStatus.FAILED and not result.screenshot_path:
            result.screenshot_path = self._take_error_screenshot(
                f"final_{result.content_code}_{result.error_step}"
            )

        return result

    # ========================================================
    # 核心操作方法（委托给各个处理器）
    # ========================================================

    def _activate_wechat(self) -> bool:
        """激活微信窗口"""
        # 先尝试从托盘恢复微信窗口（解决最小化到托盘找不到窗口的问题）
        self._restore_wechat_window()
        time.sleep(0.3)

        # 检查微信状态
        status = self._controller.check_login_status()
        if status != WeChatStatus.LOGGED_IN:
            logger.error(f"微信状态异常: {status.value}")
            return False

        # 重置微信主窗口位置和大小
        self._controller.reset_main_window_position()

        # 激活窗口
        if not self._controller.activate_window():
            return False

        time.sleep(STEP_DELAY)
        return True

    def _restore_wechat_window(self) -> bool:
        """
        尝试恢复微信窗口（从托盘或最小化状态）

        使用 Windows API 查找并恢复窗口，即使窗口最小化到托盘也能找到
        """
        user32 = ctypes.windll.user32

        # 微信窗口类名列表（4.0 和 3.x 版本）
        class_names = ["mmui::MainWindow", "WeChatMainWndForPC", "WeChat"]

        hwnd = None
        for class_name in class_names:
            hwnd = user32.FindWindowW(class_name, None)
            if hwnd:
                logger.debug(f"找到微信窗口句柄: {hwnd} (类名: {class_name})")
                break

        if not hwnd:
            # 尝试通过 UIAutomation 查找窗口句柄（兼容托盘隐藏场景）
            window = self._controller.find_wechat_window(timeout=2)
            if window:
                try:
                    hwnd = window.NativeWindowHandle
                    logger.debug(f"通过 UIAutomation 找到微信窗口句柄: {hwnd}")
                except Exception as e:
                    logger.debug(f"读取窗口句柄失败: {e}")

        if not hwnd:
            logger.warning("未找到微信窗口句柄")
            return False

        try:
            # Windows API 常量
            SW_RESTORE = 9
            SW_SHOW = 5

            # 如果窗口最小化，先恢复
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
                logger.info("微信窗口已从最小化恢复")
                time.sleep(0.2)

            # 模拟 Alt 键解除前台锁定
            user32.keybd_event(0x12, 0, 0, 0)  # Alt down
            user32.keybd_event(0x12, 0, 2, 0)  # Alt up

            # 设置为前台窗口
            user32.SetForegroundWindow(hwnd)
            user32.ShowWindow(hwnd, SW_SHOW)

            logger.info("微信窗口已激活到前台")
            return True

        except Exception as e:
            logger.error(f"恢复微信窗口失败: {e}")
            return False

    def _navigate_to_moment(self) -> bool:
        """导航到朋友圈"""
        success = self._window_handler.navigate_to_moment()
        if success:
            # 同步版本信息到其他处理器
            version = self._window_handler.wechat_version
            self._image_handler.set_version(version)
            self._text_handler.set_version(version)
            self._publish_handler.set_version(version)

            # 设置定位器窗口
            if self._window_handler.sns_window:
                self._locator.set_window(self._window_handler.sns_window)
                self._publish_handler.set_locator(self._locator)
        return success

    def _open_compose_dialog(self, has_images: bool) -> bool:
        """打开编辑框"""
        return self._publish_handler.open_compose_dialog(
            has_images,
            self._window_handler.moments_window,
            self._window_handler.sns_window
        )

    def _add_images(self, image_paths: list) -> dict:
        """添加图片"""
        # 设置文件夹路径
        self._image_handler.set_folder_path(self._folder_path)

        # 使用合适的窗口
        window = self._window_handler.sns_window or self._window_handler.moments_window
        return self._image_handler.add_images(image_paths, window)

    def _input_text(self, text: str) -> bool:
        """输入文案"""
        window = self._window_handler.sns_window or self._window_handler.moments_window
        return self._text_handler.input_text(text, window)

    def _click_publish(self) -> bool:
        """点击发表按钮"""
        window = self._window_handler.sns_window or self._window_handler.moments_window
        return self._publish_handler.click_publish(window)

    def _wait_for_publish_complete(self) -> bool:
        """等待发布完成"""
        return self._publish_handler.wait_for_publish_complete(
            self._window_handler.sns_window,
            self._window_handler.moments_window
        )

    def _view_published_moment(self, product_link: str = "") -> bool:
        """查看发布的朋友圈"""
        if self._window_handler.sns_window:
            return self._publish_handler.view_published_moment(
                self._window_handler.sns_window,
                product_link
            )
        return True

    def _return_to_main(self) -> bool:
        """返回主界面"""
        return self._window_handler.return_to_main()

    def _cancel_compose(self) -> bool:
        """取消编辑"""
        window = self._window_handler.sns_window or self._window_handler.moments_window
        return self._publish_handler.cancel_compose(window)

    # ========================================================
    # 辅助方法
    # ========================================================

    def _take_error_screenshot(self, name: str) -> Optional[str]:
        """保存错误截图"""
        if not self._save_screenshots:
            return None

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = self._screenshot_dir / filename

            # 全屏截图
            screenshot = pyautogui.screenshot()
            screenshot.save(str(filepath))

            logger.debug(f"已保存错误截图: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.warning(f"保存截图失败: {e}")
            return None

    def is_moment_window_open(self) -> bool:
        """检查朋友圈窗口是否打开"""
        return self._window_handler.is_moment_window_open()


# ============================================================
# 便捷函数
# ============================================================

_sender_instance: Optional[MomentSender] = None


def get_moment_sender() -> MomentSender:
    """获取朋友圈发布器单例"""
    global _sender_instance
    if _sender_instance is None:
        _sender_instance = MomentSender()
    return _sender_instance


def send_moment(content: Content) -> SendResult:
    """
    便捷函数：发布朋友圈

    Args:
        content: 发布内容

    Returns:
        SendResult
    """
    sender = get_moment_sender()
    return sender.send_moment(content)
