"""
群发消息模块

功能:
- 向微信群发送消息
- 支持文本、图片、图文混合
- 批量群发
- 发送结果验证
"""

import sys
import time
import random
import logging
from pathlib import Path
from typing import Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

import uiautomation as auto
import pyautogui  # 用于键盘模拟
import pyperclip  # 用于剪贴板操作

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.config_manager import get_config_manager, get_config
from models.content import Content
from models.enums import SendStatus
from .wechat_controller import WeChatController
from .base_sender import BaseSender, SHORT_DELAY, STEP_DELAY, LONG_DELAY


logger = logging.getLogger(__name__)


# ============================================================
# 版本相关常量
# ============================================================

# 微信 4.0+ 输入框类名
INPUT_BOX_CLASS_V4 = "mmui::XTextEdit"
# 微信 3.x 输入框类名
INPUT_BOX_CLASS_V3 = "RichEdit20W"

# 微信 4.0+ 搜索框类名
SEARCH_BOX_CLASS_V4 = "mmui::XLineEdit"
# 微信 3.x 搜索框类名
SEARCH_BOX_CLASS_V3 = "SearchEdit"

# Coordinate-based targeting for group chat UI (absolute screen coords).
# 默认值，实际值从配置文件读取
GROUP_SEARCH_BOX_DEFAULT = (290, 185)
GROUP_INPUT_CLICK_DEFAULT = (573, 1053)
GROUP_UPLOAD_BUTTON_DEFAULT = (666, 1004)


# ============================================================
# 类型定义
# ============================================================

class ContentType(Enum):
    """内容类型"""
    TEXT = "text"
    IMAGE = "image"
    TEXT_AND_IMAGE = "text_and_image"


def _validate_group_content(content: Content) -> tuple[bool, str]:
    """
    验证群发内容有效性（群发不需要 content_code）

    Args:
        content: 内容对象

    Returns:
        (是否有效, 错误信息)
    """
    if not content.text and not content.image_paths:
        return False, "文本和图片不能同时为空"

    for path in content.image_paths:
        if not Path(path).exists():
            return False, f"图片文件不存在: {path}"

    return True, ""


@dataclass
class SendResult:
    """发送结果"""
    group_name: str
    status: SendStatus
    message: str = ""
    text_sent: bool = False
    images_sent: int = 0
    total_images: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    screenshot_path: Optional[str] = None

    @property
    def duration(self) -> float:
        """发送耗时（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0

    @property
    def is_success(self) -> bool:
        return self.status == SendStatus.SUCCESS

    def to_dict(self) -> dict:
        return {
            "group_name": self.group_name,
            "status": self.status.value,
            "message": self.message,
            "text_sent": self.text_sent,
            "images_sent": self.images_sent,
            "total_images": self.total_images,
            "duration": self.duration,
            "screenshot_path": self.screenshot_path,
        }


@dataclass
class BatchSendResult:
    """批量发送结果"""
    results: List[SendResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.is_success)

    @property
    def failed_count(self) -> int:
        return self.total - self.success_count

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0
        return self.success_count / self.total * 100

    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0


# ============================================================
# 群发消息器
# ============================================================

class GroupSender(BaseSender):
    """
    群发消息器

    支持向微信群发送文本、图片或图文混合消息
    """

    def __init__(
        self,
        wechat_controller: Optional[WeChatController] = None,
        screenshot_dir: Optional[Path] = None,
        save_screenshots: bool = None,
        step_callback: Optional[Callable[[str, bool], None]] = None,
    ):
        """
        初始化群发消息器

        Args:
            wechat_controller: 微信控制器实例（可选）
            screenshot_dir: 截图保存目录（可选）
            save_screenshots: 是否保存失败截图（可选，默认从配置读取）
            step_callback: 步骤回调函数（可选）
        """
        # 从配置读取默认值
        if save_screenshots is None:
            save_screenshots = get_config("advanced.save_screenshots", False)
        if screenshot_dir is None:
            screenshot_dir = Path(get_config("advanced.screenshot_dir", "screenshots"))

        # 调用基类初始化
        super().__init__(
            wechat_controller=wechat_controller,
            screenshot_dir=screenshot_dir,
            save_screenshots=save_screenshots,
            step_callback=step_callback,
        )

        # 配置管理器
        self._config = get_config_manager()

        # 超时配置
        self._element_timeout = get_config("automation.timeout.element_wait", 10)
        self._send_timeout = get_config("automation.timeout.publish_wait", 20)

        # 延迟配置
        self._click_delay = get_config("automation.delay.click", 100) / 1000
        self._type_delay = get_config("automation.delay.type", 50) / 1000
        self._action_delay = get_config("automation.delay.action", 500) / 1000

        # 批量发送配置
        self._group_interval_min = get_config("schedule.random_delay_min", 0)
        self._group_interval_max = get_config("schedule.random_delay_max", 60)

        # 群发特定状态
        self._main_window: Optional[auto.WindowControl] = None
        self._folder_path: Optional[str] = None  # 文件夹路径（用于文件对话框导航，v4专用）
        self._is_v4 = self._wechat_version == "v4" if self._wechat_version else False

        # 从配置读取坐标（如果配置中没有则使用默认值）
        self._search_box_pos = (
            get_config("group_chat.search_box.x", GROUP_SEARCH_BOX_DEFAULT[0]),
            get_config("group_chat.search_box.y", GROUP_SEARCH_BOX_DEFAULT[1]),
        )
        self._input_box_pos = (
            get_config("group_chat.input_box.x", GROUP_INPUT_CLICK_DEFAULT[0]),
            get_config("group_chat.input_box.y", GROUP_INPUT_CLICK_DEFAULT[1]),
        )
        self._upload_button_pos = (
            get_config("group_chat.upload_button.x", GROUP_UPLOAD_BUTTON_DEFAULT[0]),
            get_config("group_chat.upload_button.y", GROUP_UPLOAD_BUTTON_DEFAULT[1]),
        )

        logger.debug(f"群发消息器初始化完成, 微信版本: {self._wechat_version}")
        logger.debug(f"坐标配置: 搜索框={self._search_box_pos}, 输入框={self._input_box_pos}, 上传按钮={self._upload_button_pos}")

    # ========================================================
    # 主要接口（实现基类接口）
    # ========================================================

    def send(
        self,
        group_name: str,
        content: Content,
        folder_path: Optional[str] = None,
        verify_send: bool = True
    ) -> SendResult:
        """
        发送入口（实现基类抽象方法）

        Args:
            group_name: 群名称
            content: 发送内容
            folder_path: 图片所在文件夹路径
            verify_send: 是否验证发送成功

        Returns:
            发送结果
        """
        return self.send_to_group(group_name, content, folder_path, verify_send)

    def _do_send(
        self,
        group_name: str,
        content: Content,
        folder_path: Optional[str] = None,
        verify_send: bool = True
    ) -> bool:
        """
        实际发送逻辑（实现基类抽象方法）

        Args:
            group_name: 群名称
            content: 发送内容
            folder_path: 图片所在文件夹路径
            verify_send: 是否验证发送成功

        Returns:
            是否发送成功
        """
        result = self.send_to_group(group_name, content, folder_path, verify_send)
        return result.is_success

    def send_to_group(
        self,
        group_name: str,
        content: Content,
        folder_path: Optional[str] = None,
        verify_send: bool = True,
        stage_callback: Optional[Callable[[str, str], None]] = None
    ) -> SendResult:
        """
        向单个群发送消息

        Args:
            group_name: 群名称
            content: 发送内容
            folder_path: 图片所在文件夹路径（用于文件对话框导航，仅v4）
            verify_send: 是否验证发送成功
            stage_callback: 阶段回调，签名: (group_name, stage_name) -> None

        Returns:
            发送结果
        """
        # 保存文件夹路径
        self._folder_path = folder_path

        def emit_stage(stage_name: str) -> None:
            if not stage_callback:
                return
            try:
                stage_callback(group_name, stage_name)
            except Exception as exc:
                logger.error(f"阶段回调出错: {exc}")

        result = SendResult(
            group_name=group_name,
            status=SendStatus.FAILED,
            total_images=len(content.image_paths),
            start_time=datetime.now()
        )

        # 验证内容
        valid, error_msg = _validate_group_content(content)
        if not valid:
            result.status = SendStatus.FAILED
            result.message = error_msg
            result.end_time = datetime.now()
            return result

        try:
            # 1. 检查微信状态
            if not self._ensure_wechat_ready():
                result.status = SendStatus.WECHAT_ERROR
                result.message = "微信未就绪"
                result.end_time = datetime.now()
                return result

            emit_stage("open_group")

            # 2. 搜索并进入群聊
            if not self._search_group(group_name):
                result.status = SendStatus.GROUP_NOT_FOUND
                result.message = f"未找到群: {group_name}"
                result.end_time = datetime.now()
                self._take_screenshot(f"group_not_found_{group_name}")
                return result

            # 3. 点击进入聊天
            if not self._enter_chat(group_name):
                result.status = SendStatus.FAILED
                result.message = "无法进入群聊"
                result.end_time = datetime.now()
                return result

            # 等待聊天窗口加载
            time.sleep(self._action_delay)

            # 4. 先发送文案
            if content.text.strip():
                emit_stage("input_text")
                if self._send_text(content.text):
                    result.text_sent = True
                else:
                    logger.warning("文本发送失败")

            # 5. 再发送图片
            if content.image_paths:
                emit_stage("input_images")
                images_sent = self._send_images(content.image_paths)
                result.images_sent = images_sent
                if images_sent < len(content.image_paths):
                    logger.warning(f"部分图片发送失败: {images_sent}/{len(content.image_paths)}")

            # 6. 验证发送
            if verify_send:
                emit_stage("click_send")
                emit_stage("wait_complete")
                if self._wait_for_send_complete():
                    result.status = SendStatus.SUCCESS
                    result.message = "发送成功"
                else:
                    # 检查是否部分成功
                    if result.text_sent or result.images_sent > 0:
                        result.status = SendStatus.PARTIAL
                        result.message = "部分内容发送成功"
                    else:
                        result.status = SendStatus.TIMEOUT
                        result.message = "发送超时"
            else:
                # 不验证时假定成功
                emit_stage("click_send")
                if result.text_sent or result.images_sent > 0:
                    result.status = SendStatus.SUCCESS
                    result.message = "已发送（未验证）"

            # 7. 返回主界面（已禁用 - 保持微信窗口状态不变）
            # self._return_to_main()

        except Exception as e:
            logger.error(f"发送消息时出错: {e}")
            result.status = SendStatus.FAILED
            result.message = str(e)
            self._take_screenshot(f"send_error_{group_name}")

        result.end_time = datetime.now()
        logger.info(f"群 [{group_name}] 发送结果: {result.status.value}, 耗时: {result.duration:.2f}s")

        return result

    def send_text_to_group(self, group_name: str, text: str) -> bool:
        """
        向单个群发送文本消息（需要先搜索群）

        Args:
            group_name: 群名称
            text: 文本内容

        Returns:
            是否发送成功
        """
        if not text or not text.strip():
            return True  # 空文本视为成功

        try:
            # 确保微信就绪
            if not self._ensure_wechat_ready():
                logger.error("微信未就绪，无法发送额外消息")
                return False

            # 搜索群
            if not self._search_group(group_name):
                logger.error(f"未找到群: {group_name}")
                return False

            # 进入聊天
            if not self._enter_chat(group_name):
                logger.error(f"无法进入群聊: {group_name}")
                return False

            # 发送文本
            if self._send_text(text):
                logger.info(f"额外消息发送成功: {group_name}")
                return True
            else:
                logger.warning(f"额外消息发送失败: {group_name}")
                return False

        except Exception as e:
            logger.error(f"发送额外消息异常: {e}")
            return False

    def send_text_in_current_chat(self, text: str) -> bool:
        """
        在当前已打开的聊天窗口发送文本消息（不搜索群）

        用于小程序发布后直接在当前窗口发送额外消息，
        无需再次搜索群对象。

        Args:
            text: 文本内容

        Returns:
            是否发送成功
        """
        if not text or not text.strip():
            return True  # 空文本视为成功

        try:
            # 确保主窗口存在
            if not self._main_window:
                # 尝试获取主窗口
                self._main_window = self._controller.get_main_window()
                if not self._main_window:
                    logger.error("无法获取微信主窗口")
                    return False

            # 直接发送文本（当前窗口已是目标群聊）
            if self._send_text(text):
                logger.info("额外消息发送成功（当前窗口）")
                return True
            else:
                logger.warning("额外消息发送失败（当前窗口）")
                return False

        except Exception as e:
            logger.error(f"发送额外消息异常: {e}")
            return False

    def send_to_groups(
        self,
        group_names: List[str],
        content: Content,
        folder_path: Optional[str] = None,
        interval: Optional[tuple[int, int]] = None,
        stop_on_error: bool = False,
        progress_callback: Optional[callable] = None,
        stage_callback: Optional[Callable[[str, str], None]] = None
    ) -> BatchSendResult:
        """
        批量向多个群发送消息

        Args:
            group_names: 群名称列表
            content: 发送内容
            folder_path: 图片所在文件夹路径（用于文件对话框导航，仅v4）
            interval: 发送间隔范围 (min_seconds, max_seconds)，默认使用配置
            stop_on_error: 遇到错误是否停止
            progress_callback: 进度回调函数，签名: (current, total, result) -> bool
                              返回 False 可中止发送
            stage_callback: 阶段回调，签名: (group_name, stage_name) -> None

        Returns:
            批量发送结果
        """
        # 保存文件夹路径
        self._folder_path = folder_path
        logger.info(f"send_to_groups folder_path: {folder_path}")

        batch_result = BatchSendResult(start_time=datetime.now())

        if not group_names:
            batch_result.end_time = datetime.now()
            return batch_result

        # 验证内容
        valid, error_msg = _validate_group_content(content)
        if not valid:
            logger.error(f"内容验证失败: {error_msg}")
            for name in group_names:
                batch_result.results.append(SendResult(
                    group_name=name,
                    status=SendStatus.FAILED,
                    message=error_msg,
                    total_images=len(content.image_paths)
                ))
            batch_result.end_time = datetime.now()
            return batch_result

        # 设置间隔
        if interval is None:
            interval = (self._group_interval_min, self._group_interval_max)

        total = len(group_names)
        logger.info(f"开始批量发送，共 {total} 个群")

        for i, group_name in enumerate(group_names):
            logger.info(f"[{i+1}/{total}] 正在发送到群: {group_name}")

            # 发送到当前群
            result = self.send_to_group(
                group_name,
                content,
                folder_path=self._folder_path,
                stage_callback=stage_callback
            )
            batch_result.results.append(result)

            # 进度回调
            if progress_callback:
                try:
                    should_continue = progress_callback(i + 1, total, result)
                    if should_continue is False:
                        logger.info("用户取消批量发送")
                        # 标记剩余群为已取消
                        for remaining in group_names[i+1:]:
                            batch_result.results.append(SendResult(
                                group_name=remaining,
                                status=SendStatus.CANCELLED,
                                message="用户取消",
                                total_images=len(content.image_paths)
                            ))
                        break
                except Exception as e:
                    logger.error(f"进度回调出错: {e}")

            # 检查是否遇到错误需要停止
            if stop_on_error and not result.is_success:
                logger.warning(f"遇到错误停止发送: {result.message}")
                break

            # 等待间隔（最后一个不等待）
            if i < total - 1:
                wait_time = random.uniform(interval[0], interval[1])
                logger.debug(f"等待 {wait_time:.1f} 秒后发送下一个...")
                time.sleep(wait_time)

        batch_result.end_time = datetime.now()

        logger.info(
            f"批量发送完成: 成功 {batch_result.success_count}/{batch_result.total}, "
            f"成功率 {batch_result.success_rate:.1f}%, 耗时 {batch_result.duration:.1f}s"
        )

        return batch_result

    # ========================================================
    # 内部方法
    # ========================================================
    # 注意：_ensure_wechat_ready、_take_screenshot、_wait_for_send_complete、_return_to_main
    # 等方法已在基类 BaseSender 中实现

    def _find_input_box(self) -> Optional[auto.EditControl]:
        """
        查找消息输入框（支持 v3 和 v4）

        Returns:
            输入框控件，未找到返回 None
        """
        if not self._main_window:
            return None

        # 微信 4.0 使用 mmui::XTextEdit
        if self._is_v4:
            input_box = self._main_window.EditControl(
                searchDepth=15,
                ClassName=INPUT_BOX_CLASS_V4
            )
            if input_box.Exists(self._element_timeout, 1):
                return input_box
            logger.debug("v4 输入框未找到，尝试 v3 方式")

        # 微信 3.x 使用 RichEdit20W
        input_box = self._main_window.EditControl(
            searchDepth=15,
            ClassName=INPUT_BOX_CLASS_V3
        )
        if input_box.Exists(self._element_timeout, 1):
            return input_box

        # 最后尝试通用查找
        input_box = self._main_window.EditControl(
            searchDepth=15
        )
        if input_box.Exists(self._element_timeout, 1):
            return input_box

        return None

    def _find_search_box(self) -> Optional[auto.EditControl]:
        """
        查找搜索框（支持 v3 和 v4）

        Returns:
            搜索框控件，未找到返回 None
        """
        if not self._main_window:
            return None

        # 首先尝试按名称查找（通用）
        search_box = self._main_window.EditControl(
            searchDepth=10,
            Name="搜索"
        )
        if search_box.Exists(self._element_timeout, 1):
            return search_box

        # 微信 4.0 使用 mmui::XLineEdit
        if self._is_v4:
            search_box = self._main_window.EditControl(
                searchDepth=10,
                ClassName=SEARCH_BOX_CLASS_V4
            )
            if search_box.Exists(self._element_timeout, 1):
                return search_box

        # 微信 3.x 使用 SearchEdit
        search_box = self._main_window.EditControl(
            searchDepth=10,
            ClassName=SEARCH_BOX_CLASS_V3
        )
        if search_box.Exists(self._element_timeout, 1):
            return search_box

        return None

    # 注意：基类的 _ensure_wechat_ready 方法已提供通用实现
    # 这里提供群发器特定的版本，需要额外获取主窗口并更新版本信息
    def _ensure_wechat_ready(self) -> bool:
        """确保微信已就绪（群发器增强版）"""
        # 调用基类方法
        if not super()._ensure_wechat_ready():
            return False

        # 获取主窗口（群发器需要）
        self._main_window = self._controller.get_main_window()
        if not self._main_window:
            logger.error("无法获取微信主窗口")
            return False

        # 更新版本信息
        self._is_v4 = self._wechat_version == "v4" if self._wechat_version else False
        logger.info(f"微信版本检测: {self._wechat_version}, is_v4={self._is_v4}")

        time.sleep(self._action_delay)
        return True

    def _search_group(self, group_name: str) -> bool:
        """
        搜索群（支持 v3 和 v4）

        Args:
            group_name: 群名称

        Returns:
            是否找到匹配的群
        """
        if not self._main_window:
            return False

        try:
            # 使用 Ctrl+F 打开搜索
            auto.SendKeys("{Ctrl}f")
            time.sleep(self._action_delay)

            # 点击搜索框坐标，确保焦点正确
            pyautogui.click(self._search_box_pos[0], self._search_box_pos[1])  # 搜索框坐标
            time.sleep(self._click_delay)

            # 清空并输入群名
            # 使用剪贴板输入（支持中文）
            self._clipboard.backup()
            try:
                self._clipboard.set_text(group_name)
                time.sleep(0.1)
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.1)
                pyautogui.hotkey("ctrl", "v")
            finally:
                self._clipboard.restore()

            time.sleep(self._action_delay * 2)  # 等待搜索结果

            # 检查是否有搜索结果
            no_result = self._main_window.TextControl(
                searchDepth=10,
                Name="无搜索结果"
            )

            if no_result.Exists(1, 0):
                logger.warning(f"搜索无结果: {group_name}")
                # 关闭搜索
                auto.SendKeys("{Escape}")
                return False

            return True

        except Exception as e:
            logger.error(f"搜索群时出错: {e}")
            return False

    def _enter_chat(self, group_name: str) -> bool:
        """
        进入群聊（支持 v3 和 v4）

        Args:
            group_name: 群名称（用于验证）

        Returns:
            是否成功进入
        """
        if not self._main_window:
            return False

        try:
            # 在搜索结果中查找匹配项
            # 等待搜索结果列表出现
            time.sleep(self._action_delay)

            # 查找包含群名的列表项
            list_items = self._main_window.ListItemControl(
                searchDepth=10
            )

            # 遍历查找精确匹配的群
            found_item = None
            for i in range(20):  # 最多检查前20个结果
                try:
                    item = self._main_window.ListItemControl(
                        searchDepth=10,
                        foundIndex=i + 1
                    )
                    if not item.Exists(0.5, 0):
                        break

                    # 检查名称是否匹配
                    item_name = item.Name
                    if item_name and group_name in item_name:
                        # 优先精确匹配
                        if item_name == group_name:
                            found_item = item
                            break
                        elif found_item is None:
                            found_item = item

                except Exception:
                    continue

            if found_item is None:
                # 尝试直接按 Enter 选择第一个结果
                logger.debug("未找到精确匹配，尝试选择第一个结果")
                auto.SendKeys("{Enter}")
                time.sleep(self._action_delay)
            else:
                # 点击找到的群
                found_item.Click()
                time.sleep(self._action_delay)

            # 直接用坐标点击输入框
            time.sleep(self._action_delay)
            pyautogui.click(self._input_box_pos[0], self._input_box_pos[1])  # 输入框坐标
            time.sleep(self._click_delay)
            logger.info(f"已进入群聊: {group_name}")
            return True

        except Exception as e:
            logger.error(f"进入群聊时出错: {e}")
            return False

    def _find_send_file_button(self, max_retries: int = 2) -> Optional[auto.ButtonControl]:
        """
        查找'发送文件'按钮（微信v4）

        位于聊天输入框左侧工具栏

        Args:
            max_retries: 最大重试次数

        Returns:
            按钮控件，未找到返回None
        """
        if not self._main_window:
            logger.warning("_find_send_file_button: 主窗口为空")
            return None

        logger.debug(f"开始查找'发送文件'按钮, 最大重试次数: {max_retries}")

        # 重试机制
        for retry in range(max_retries):
            if retry > 0:
                logger.debug(f"第 {retry + 1} 次重试查找'发送文件'按钮...")
                time.sleep(0.5)  # 重试前等待（缩短）

            # 优先使用最可能成功的组合：Name="发送文件" + ClassName
            try:
                btn = self._main_window.ButtonControl(
                    searchDepth=25,
                    ClassName="mmui::XButton",
                    Name="发送文件"
                )
                if btn.Exists(1, 0.3):  # 缩短超时：1秒
                    logger.info(f"找到'发送文件'按钮 (ClassName+Name), 重试次数={retry}")
                    return btn
            except Exception as e:
                logger.debug(f"通过ClassName+Name查找按钮时出错: {e}")

            # 备选：只用 Name 查找
            try:
                btn = self._main_window.ButtonControl(searchDepth=25, Name="发送文件")
                if btn.Exists(1, 0.3):  # 缩短超时：1秒
                    logger.info(f"找到'发送文件'按钮 (Name only), 重试次数={retry}")
                    return btn
            except Exception as e:
                logger.debug(f"通过Name查找按钮时出错: {e}")

        logger.error(f"未找到'发送文件'按钮, 已重试 {max_retries} 次")
        return None

    def _navigate_to_folder(self, file_dialog: auto.WindowControl, folder_path: str) -> None:
        path_obj = Path(folder_path)
        if not path_obj.exists():
            logger.debug(f"文件夹不存在，跳过导航: {folder_path}")
            return

        try:
            file_dialog.SetFocus()
            time.sleep(1.0)
        except Exception:
            pass

        def paste_and_enter() -> None:
            pyperclip.copy(str(path_obj))
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(1.0)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(1.0)
            pyautogui.press('enter')
            time.sleep(2.0)

        try:
            pyautogui.hotkey('alt', 'd')
            time.sleep(1.0)
            paste_and_enter()
        except Exception as e:
            logger.debug(f"地址栏导航失败，继续尝试: {folder_path}, 错误: {e}")

            try:
                pyautogui.hotkey('ctrl', 'l')
                time.sleep(1.0)
                paste_and_enter()
            except Exception as e2:
                logger.debug(f"导航到文件夹失败，继续使用默认目录: {folder_path}, 错误: {e2}")


    def _send_images_v4(self, image_paths: List[str]) -> int:
        """
        微信v4 - 通过文件对话框发送图片（与朋友圈v4一致）

        Args:
            image_paths: 图片路径列表

        Returns:
            成功发送的图片数量
        """
        if not self._main_window or not image_paths:
            return 0

        # 过滤有效路径
        valid_paths = [p for p in image_paths if Path(p).exists()]
        if not valid_paths:
            logger.warning("没有有效的图片路径")
            return 0

        logger.info(f"开始 v4 方式发送 {len(valid_paths)} 张图片")

        try:
            # 0. 确保 UI 状态正确
            # 0.1 先激活主窗口（重要：必须先激活窗口再发送按键）
            logger.debug("激活微信主窗口...")
            self._main_window.SetFocus()
            time.sleep(0.3)  # 缩短：0.5 -> 0.3

            # 0.2 激活聊天输入框（坐标定位）
            logger.debug("激活聊天输入框（坐标定位）...")
            pyautogui.click(self._input_box_pos[0], self._input_box_pos[1])  # 输入框坐标
            time.sleep(0.3)

            # 等待 UI 稳定
            time.sleep(0.5)  # 缩短：1.0 -> 0.5

            # 1. 点击"发送文件"按钮（坐标定位）
            logger.debug("点击'发送文件'按钮（坐标定位）...")
            pyautogui.click(self._upload_button_pos[0], self._upload_button_pos[1])  # 发送文件按钮坐标
            time.sleep(self._action_delay)

            # 2. 等待文件对话框出现
            file_dialog = auto.WindowControl(searchDepth=2, Name="打开")
            if not file_dialog.Exists(5, 1):
                file_dialog = auto.WindowControl(searchDepth=2, ClassName="#32770")

            if not file_dialog.Exists(5, 1):
                logger.error("文件对话框未出现，改用剪贴板发送")
                auto.SendKeys("{Escape}")
                return self._send_images_v3(valid_paths)

            logger.debug("文件对话框已打开")
            file_dialog.SetFocus()
            time.sleep(SHORT_DELAY)
            logger.info("file dialog opened, wait 1s before navigation")
            time.sleep(1.0)

            # 3. 导航到文件夹（如果指定了folder_path）
            if self._folder_path:
                logger.info(f"navigate to folder: {self._folder_path}")
                self._navigate_to_folder(file_dialog, self._folder_path)

            # 4. 批量输入文件名（只需文件名，不含扩展名）
            files_str = " ".join(f'"{Path(path).stem}"' for path in valid_paths)
            logger.debug(f"输入文件名: {files_str}")

            # 查找文件名输入框
            edit = file_dialog.ComboBoxControl(searchDepth=10, Name="文件名(N):")
            if not edit.Exists(3, 1):
                edit = file_dialog.EditControl(searchDepth=10)

            if not edit.Exists(3, 1):
                logger.error("未找到文件名输入框")
                file_dialog.SendKeys("{Escape}")
                return 0

            # 点击输入框
            edit.Click()
            time.sleep(SHORT_DELAY)

            # 粘贴所有文件名
            pyperclip.copy(files_str)
            time.sleep(SHORT_DELAY)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(SHORT_DELAY)

            # 5. 点击打开按钮
            open_btn = file_dialog.ButtonControl(searchDepth=10, Name="打开(O)")
            if open_btn.Exists(3, 1):
                open_btn.Click()
                logger.debug("已点击'打开'按钮")
            else:
                file_dialog.SendKeys("{Enter}")
                logger.debug("已按Enter确认")

            time.sleep(LONG_DELAY)

            # 6. 等待图片加载（可选验证）
            time.sleep(self._action_delay)

            # 7. 点击发送按钮（图片已自动附加到发送框）
            # 注意：微信群聊可能会自动发送，或需要手动点击发送
            # 这里我们尝试按Enter发送
            auto.SendKeys("{Enter}")
            logger.debug("已按Enter发送")

            time.sleep(self._action_delay * 2)

            logger.info(f"图片发送完成 (v4): 一次性发送 {len(valid_paths)} 张图片")
            return len(valid_paths)

        except Exception as e:
            logger.exception(f"v4文件对话框发送图片失败: {e}")
            return 0

    def _send_images_v3(self, image_paths: List[str]) -> int:
        """
        微信v3 - 通过剪贴板发送图片（原实现）

        Args:
            image_paths: 图片路径列表

        Returns:
            成功发送的图片数量
        """
        if not self._main_window:
            return 0

        sent_count = 0

        for path in image_paths:
            try:
                if not Path(path).exists():
                    logger.warning(f"图片不存在: {path}")
                    continue

                # 通过剪贴板发送图片
                self._clipboard.backup()
                try:
                    if self._clipboard.set_image(path):
                        # 使用坐标定位输入框
                        pyautogui.click(self._input_box_pos[0], self._input_box_pos[1])  # 输入框坐标
                        time.sleep(self._click_delay)
                        pyautogui.hotkey("ctrl", "v")
                        time.sleep(self._action_delay)

                        # 按 Enter 发送图片
                        pyautogui.press("enter")
                        time.sleep(self._action_delay * 2)

                        sent_count += 1
                        logger.debug(f"图片已发送: {path}")
                    else:
                        logger.warning(f"设置剪贴板图片失败: {path}")

                finally:
                    self._clipboard.restore()

            except Exception as e:
                logger.error(f"发送图片失败 [{path}]: {e}")

        return sent_count

    def _send_images(self, image_paths: List[str]) -> int:
        """
        发送图片（版本分发器）

        v4: 使用文件对话框方式（点击"发送文件"按钮）
        v3: 使用剪贴板粘贴方式

        Args:
            image_paths: 图片路径列表

        Returns:
            成功发送的图片数量
        """
        if not self._main_window or not image_paths:
            return 0

        # 版本分发
        logger.info(f"发送图片: 版本={self._wechat_version}, is_v4={self._is_v4}, 图片数={len(image_paths)}")
        if self._is_v4:
            logger.info("使用 v4 方式发送图片（点击'发送文件'按钮）")
            return self._send_images_v4(image_paths)
        else:
            logger.info("使用 v3 方式发送图片（剪贴板粘贴）")
            return self._send_images_v3(image_paths)

    def _send_text(self, text: str) -> bool:
        """
        发送文本（支持 v3 和 v4）

        Args:
            text: 文本内容

        Returns:
            是否成功
        """
        if not self._main_window or not text.strip():
            return False

        try:
            # 使用坐标定位输入框
            pyautogui.click(self._input_box_pos[0], self._input_box_pos[1])  # 输入框坐标
            time.sleep(self._click_delay)

            # 通过剪贴板输入文本
            self._clipboard.backup()
            try:
                self._clipboard.set_text(text)
                time.sleep(0.1)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(self._action_delay)
            finally:
                self._clipboard.restore()

            # 按 Enter 发送
            pyautogui.press("enter")
            time.sleep(self._action_delay)

            logger.debug("文本已发送")
            return True

        except Exception as e:
            logger.error(f"发送文本失败: {e}")
            return False

    # 注意：_wait_for_send_complete、_return_to_main、_take_screenshot 方法
    # 已在基类 BaseSender 中实现，如需自定义可以重写


# ============================================================
# 便捷函数
# ============================================================

_sender: Optional[GroupSender] = None


def get_group_sender() -> GroupSender:
    """获取群发消息器单例"""
    global _sender
    if _sender is None:
        _sender = GroupSender()
    return _sender


def send_message(
    group_name: str,
    text: str = "",
    images: Optional[List[str]] = None
) -> SendResult:
    """
    快捷发送消息

    Args:
        group_name: 群名称
        text: 文本内容
        images: 图片路径列表

    Returns:
        发送结果
    """
    content = Content(text=text, image_paths=images or [])
    return get_group_sender().send_to_group(group_name, content)


def batch_send(
    group_names: List[str],
    text: str = "",
    images: Optional[List[str]] = None
) -> BatchSendResult:
    """
    快捷批量发送

    Args:
        group_names: 群名称列表
        text: 文本内容
        images: 图片路径列表

    Returns:
        批量发送结果
    """
    content = Content(text=text, image_paths=images or [])
    return get_group_sender().send_to_groups(group_names, content)


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=== 群发消息器测试 ===\n")

    sender = GroupSender()

    # 测试发送内容
    test_content = Content(
        text="这是一条测试消息，请忽略。",
        image_paths=[]
    )

    # 验证内容
    valid, error = _validate_group_content(test_content)
    print(f"内容验证: {'通过' if valid else error}")
    print(f"有文本: {bool(test_content.text)}, 有图片: {test_content.has_images}")

    # 测试单群发送
    print("\n--- 单群发送测试 ---")
    test_group = "文件传输助手"  # 使用文件传输助手测试

    result = sender.send_to_group(test_group, test_content)
    print(f"发送结果: {result.status.value}")
    print(f"消息: {result.message}")
    print(f"耗时: {result.duration:.2f}s")

    # 测试批量发送
    print("\n--- 批量发送测试 ---")
    test_groups = ["文件传输助手"]

    def progress_callback(current, total, result):
        print(f"  进度: {current}/{total} - {result.group_name}: {result.status.value}")
        return True  # 继续

    batch_result = sender.send_to_groups(
        test_groups,
        test_content,
        interval=(1, 2),
        progress_callback=progress_callback
    )

    print(f"\n批量发送完成:")
    print(f"  总数: {batch_result.total}")
    print(f"  成功: {batch_result.success_count}")
    print(f"  失败: {batch_result.failed_count}")
    print(f"  成功率: {batch_result.success_rate:.1f}%")
    print(f"  总耗时: {batch_result.duration:.1f}s")

    print("\n测试完成")
