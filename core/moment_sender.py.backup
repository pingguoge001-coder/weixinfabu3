"""
朋友圈发布器模块

功能:
- 自动发布朋友圈（图文/纯文字）
- 支持微信 3.x 和 4.0 版本
- 通过剪贴板粘贴图片和文案
- 每步操作验证和失败截图
- 详细日志记录

微信 4.0 朋友圈发布流程:
1. 双击导航栏"朋友圈"按钮 -> 打开独立窗口 (mmui::SNSWindow)
2. 点击顶部"发表"按钮 -> 进入发布界面
3. 点击"添加图片"按钮 (mmui::PublishImageAddGridCell) -> 弹出文件对话框
4. 在文件对话框中选择图片
5. 输入文案到输入框 (mmui::ReplyInputField)
6. 点击"发表"按钮完成发布
"""

import time
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable

import pyautogui
import pyperclip
import uiautomation as auto

from models.content import Content
from models.enums import Channel, SendStatus
from services.config_manager import get_config
from .wechat_controller import WeChatController, get_wechat_controller, WeChatStatus
from .clipboard_manager import ClipboardManager
from .base_sender import BaseSender, STEP_DELAY, SHORT_DELAY, LONG_DELAY, PAGE_LOAD_DELAY, ELEMENT_TIMEOUT

logger = logging.getLogger(__name__)


# ============================================================
# 配置常量
# ============================================================

# 朋友圈特定配置
PUBLISH_WAIT = 3.0        # 发布等待时间
PUBLISH_TIMEOUT = 30      # 发布超时
MAX_IMAGES = 9            # 最大图片数量


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


class MomentSender(BaseSender):
    """
    朋友圈发布器

    发布流程 (微信 4.0):
    1. 激活微信窗口
    2. 点击导航栏"朋友圈"按钮 (4.0 直接在导航栏)
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

    # 朋友圈窗口类名 (3.x)
    MOMENTS_WINDOW_CLASS_V3 = "SnsWnd"

    # 发布窗口类名 (3.x)
    COMPOSE_WINDOW_CLASS_V3 = "SnsUploadWnd"

    # 微信 4.0 窗口类名
    MAIN_WINDOW_CLASS_V4 = "mmui::MainWindow"

    # 微信 4.0 朋友圈独立窗口类名
    SNS_WINDOW_CLASS_V4 = "mmui::SNSWindow"

    # 微信 4.0 文件对话框类名
    FILE_DIALOG_CLASS = "#32770"

    # 微信 4.0 UI 元素类名
    ADD_IMAGE_CELL_CLASS = "mmui::PublishImageAddGridCell"
    INPUT_FIELD_CLASS = "mmui::ReplyInputField"
    DRAG_GRID_VIEW_CLASS = "mmui::XDragGridView"

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
        # 调用基类初始化
        super().__init__(
            wechat_controller=wechat_controller,
            screenshot_dir=screenshot_dir,
            save_screenshots=save_screenshots,
            step_callback=step_callback,
        )

        # 朋友圈特定状态
        self._moments_window: Optional[auto.WindowControl] = None
        self._compose_window: Optional[auto.WindowControl] = None
        self._sns_window: Optional[auto.WindowControl] = None  # 4.0 独立朋友圈窗口
        self._folder_path: Optional[str] = None  # 图片文件夹路径（用于文件对话框导航）

        logger.debug("朋友圈发布器初始化完成")

    # ========================================================
    # 主发布方法（实现基类接口）
    # ========================================================

    def send(self, content: Content, folder_path: Optional[str] = None) -> SendResult:
        """
        发送入口（实现基类抽象方法）

        Args:
            content: 发布内容
            folder_path: 图片所在文件夹路径（用于文件对话框导航）

        Returns:
            SendResult
        """
        return self.send_moment(content, folder_path)

    def _do_send(self, content: Content, folder_path: Optional[str] = None) -> bool:
        """
        实际发送逻辑（实现基类抽象方法）

        Args:
            content: 发布内容
            folder_path: 图片所在文件夹路径

        Returns:
            是否发送成功
        """
        result = self.send_moment(content, folder_path)
        return result.is_success

    def send_moment(self, content: Content, folder_path: Optional[str] = None) -> SendResult:
        """
        发布朋友圈

        Args:
            content: 发布内容
            folder_path: 图片所在文件夹路径（用于文件对话框导航）

        Returns:
            SendResult
        """
        # 保存文件夹路径供 _add_images_v4 使用
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

            # Step 1: 激活微信窗口（使用基类方法）
            if not self._step("activate_wechat", self._ensure_wechat_ready):
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

            # Step 5: 输入文案（包含 #+产品名称 #+分类 标签）
            full_text = content.full_text  # 使用 full_text 属性获取带标签的完整文案
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

            # Step 8: 查看发布的朋友圈（点击头像→点击朋友圈链接→评论产品链接）
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
    # 注意：_step 和 _step_with_result 方法已在基类 BaseSender 中实现

    def _finalize_result(self, result: SendResult, start_time: float) -> SendResult:
        """完成结果处理"""
        result.duration = time.time() - start_time

        if result.status == SendStatus.FAILED and not result.screenshot_path:
            result.screenshot_path = self._take_error_screenshot(
                f"final_{result.content_code}_{result.error_step}"
            )

        return result

    # ========================================================
    # 核心操作方法
    # ========================================================
    # 注意：_ensure_wechat_ready 方法已在基类 BaseSender 中实现

    def _adjust_sns_window_position(self) -> bool:
        """
        调整朋友圈窗口到固定的位置和大小

        从配置文件 display.sns_window 读取目标位置和大小
        确保后续操作在可预测的窗口布局下进行
        """
        if not self._sns_window or not self._sns_window.Exists(0, 0):
            logger.warning("朋友圈窗口不存在，无法调整位置")
            return False

        # 从配置文件读取窗口位置和大小
        sns_x = get_config("display.sns_window.x", 693)
        sns_y = get_config("display.sns_window.y", 186)
        sns_width = get_config("display.sns_window.width", 825)
        sns_height = get_config("display.sns_window.height", 1552)

        try:
            result = self._controller.move_window(
                x=sns_x,
                y=sns_y,
                width=sns_width,
                height=sns_height,
                window=self._sns_window
            )
            if result:
                logger.info(f"已调整朋友圈窗口位置: ({sns_x}, {sns_y}), "
                           f"大小: {sns_width}x{sns_height}")
            else:
                logger.warning("调整朋友圈窗口位置失败")
            return result
        except Exception as e:
            logger.error(f"调整朋友圈窗口位置异常: {e}")
            return False

    def _navigate_to_moment(self) -> bool:
        """导航到朋友圈 (支持 3.x 和 4.0)"""
        main_window = self._controller.get_main_window()
        if not main_window:
            logger.error("未找到微信主窗口")
            return False

        # 检测微信版本
        self._wechat_version = self._controller.get_detected_version()
        logger.debug(f"检测到微信版本: {self._wechat_version}")

        if self._wechat_version == "v4":
            return self._navigate_to_moment_v4(main_window)
        else:
            return self._navigate_to_moment_v3(main_window)

    def _navigate_to_moment_v4(self, main_window: auto.WindowControl) -> bool:
        """
        微信 4.0 导航到朋友圈

        双击朋友圈按钮会打开独立的朋友圈窗口 (mmui::SNSWindow)
        """
        # 检查是否已有朋友圈窗口打开，如果有则直接使用
        existing_sns = auto.WindowControl(
            searchDepth=1,
            ClassName=self.SNS_WINDOW_CLASS_V4
        )
        if existing_sns.Exists(1, 0):
            # 直接使用已存在的窗口，不再关闭
            self._sns_window = existing_sns
            self._sns_window.SetFocus()
            self._moments_window = self._sns_window
            logger.info("使用已存在的朋友圈窗口 (v4)")
            # 调整窗口位置和大小
            self._adjust_sns_window_position()
            return True

        # 4.0 中朋友圈按钮在左侧导航栏
        moment_btn = main_window.ButtonControl(
            searchDepth=10,
            Name="朋友圈"
        )

        if not moment_btn.Exists(ELEMENT_TIMEOUT, 1):
            # 尝试其他定位方式
            moment_btn = main_window.Control(
                searchDepth=10,
                Name="朋友圈",
                ClassName="mmui::XTabBarItem"
            )

        if not moment_btn.Exists(ELEMENT_TIMEOUT, 1):
            logger.error("未找到'朋友圈'导航按钮 (v4)")
            return False

        # 双击打开独立朋友圈窗口
        moment_btn.DoubleClick()
        logger.debug("已双击'朋友圈'导航按钮 (v4)")
        time.sleep(PAGE_LOAD_DELAY)

        # 等待独立朋友圈窗口出现
        self._sns_window = auto.WindowControl(
            searchDepth=1,
            ClassName=self.SNS_WINDOW_CLASS_V4
        )

        if not self._sns_window.Exists(ELEMENT_TIMEOUT, 1):
            logger.error("朋友圈窗口未打开 (v4)")
            return False

        self._sns_window.SetFocus()
        self._moments_window = self._sns_window
        logger.info("已进入朋友圈 (v4)")
        # 调整窗口位置和大小
        self._adjust_sns_window_position()
        return True

    def _navigate_to_moment_v3(self, main_window: auto.WindowControl) -> bool:
        """微信 3.x 导航到朋友圈 - 通过发现标签"""
        # 点击"发现"标签
        discover_tab = main_window.ButtonControl(
            searchDepth=5,
            Name="发现"
        )

        if not discover_tab.Exists(ELEMENT_TIMEOUT, 1):
            # 尝试备用定位
            discover_tab = main_window.TextControl(
                searchDepth=5,
                Name="发现"
            )

        if not discover_tab.Exists(ELEMENT_TIMEOUT, 1):
            logger.error("未找到'发现'标签 (v3)")
            return False

        discover_tab.Click()
        logger.debug("已点击'发现'标签")
        time.sleep(STEP_DELAY)

        # 点击"朋友圈"
        moment_entry = main_window.ListItemControl(
            searchDepth=10,
            Name="朋友圈"
        )

        if not moment_entry.Exists(ELEMENT_TIMEOUT, 1):
            # 尝试其他定位方式
            moment_entry = main_window.TextControl(
                searchDepth=10,
                Name="朋友圈"
            )

        if not moment_entry.Exists(ELEMENT_TIMEOUT, 1):
            logger.error("未找到'朋友圈'入口 (v3)")
            return False

        moment_entry.Click()
        logger.debug("已点击'朋友圈'入口")
        time.sleep(PAGE_LOAD_DELAY)

        # 等待朋友圈窗口出现
        self._moments_window = auto.WindowControl(
            searchDepth=1,
            ClassName=self.MOMENTS_WINDOW_CLASS_V3
        )

        if not self._moments_window.Exists(ELEMENT_TIMEOUT, 1):
            logger.error("朋友圈窗口未出现 (v3)")
            return False

        logger.info("已进入朋友圈 (v3)")
        return True

    def _open_compose_dialog(self, has_images: bool) -> bool:
        """
        打开编辑框 (支持 3.x 和 4.0)

        Args:
            has_images: 是否有图片（决定短按还是长按相机图标）
        """
        if not self._moments_window or not self._moments_window.Exists(0, 0):
            logger.error("朋友圈窗口不存在")
            return False

        if self._wechat_version == "v4":
            return self._open_compose_dialog_v4(has_images)
        else:
            return self._open_compose_dialog_v3(has_images)

    def _open_compose_dialog_v4(self, has_images: bool) -> bool:
        """
        微信 4.0 打开发布编辑框

        在朋友圈窗口顶部点击"发表"按钮进入发布界面
        """
        if not self._sns_window or not self._sns_window.Exists(0, 0):
            logger.error("朋友圈窗口不存在 (v4)")
            return False

        # 4.0 中发表按钮在朋友圈窗口顶部
        publish_btn = self._sns_window.Control(
            searchDepth=10,
            Name="发表"
        )

        if not publish_btn.Exists(5, 1):
            # 尝试通过 TabBarItem 查找
            publish_btn = self._sns_window.Control(
                searchDepth=10,
                Name="发表",
                ClassName="mmui::XTabBarItem"
            )

        if not publish_btn.Exists(5, 1):
            logger.error("未找到'发表'按钮 (v4)")
            return False

        publish_btn.Click()
        logger.debug("已点击'发表'按钮 (v4)")
        time.sleep(STEP_DELAY)

        # 等待发布界面出现 - 检查输入框或添加图片按钮
        input_field = self._sns_window.Control(
            searchDepth=15,
            ClassName=self.INPUT_FIELD_CLASS
        )
        add_image_btn = self._sns_window.ListItemControl(
            searchDepth=15,
            Name="添加图片",
            ClassName=self.ADD_IMAGE_CELL_CLASS
        )

        if input_field.Exists(5, 1) or add_image_btn.Exists(5, 1):
            self._compose_window = self._sns_window
            logger.info("已打开发布界面 (v4)")
            return True

        logger.error("发布界面未出现 (v4)")
        return False

    def _open_compose_dialog_v3(self, has_images: bool) -> bool:
        """微信 3.x 打开发布编辑框"""
        # 查找相机图标/发布按钮
        camera_btn = self._moments_window.ButtonControl(
            searchDepth=5,
            Name="拍照分享"
        )

        if not camera_btn.Exists(5, 1):
            # 尝试其他定位方式
            camera_btn = self._moments_window.ImageControl(
                searchDepth=5,
                AutomationId="camera"
            )

        if not camera_btn.Exists(5, 1):
            # 尝试通过工具栏查找
            toolbar = self._moments_window.ToolBarControl(searchDepth=5)
            if toolbar.Exists(3, 1):
                camera_btn = toolbar.ButtonControl(searchDepth=3)

        if not camera_btn.Exists(5, 1):
            logger.error("未找到相机图标 (v3)")
            return False

        rect = camera_btn.BoundingRectangle
        center_x = (rect.left + rect.right) // 2
        center_y = (rect.top + rect.bottom) // 2

        if has_images:
            # 短按 - 图文消息
            pyautogui.click(center_x, center_y)
            logger.debug("短按相机图标（图文模式, v3）")
        else:
            # 长按 - 纯文字消息
            pyautogui.mouseDown(center_x, center_y)
            time.sleep(1.0)  # 长按 1 秒
            pyautogui.mouseUp(center_x, center_y)
            logger.debug("长按相机图标（纯文字模式, v3）")

        time.sleep(STEP_DELAY)

        # 等待编辑窗口出现
        self._compose_window = auto.WindowControl(
            searchDepth=1,
            ClassName=self.COMPOSE_WINDOW_CLASS_V3
        )

        if not self._compose_window.Exists(ELEMENT_TIMEOUT, 1):
            # 可能是同一个窗口内的编辑区域
            logger.debug("查找内嵌编辑区域 (v3)")
            edit_area = self._moments_window.EditControl(searchDepth=10)
            if edit_area.Exists(5, 1):
                self._compose_window = self._moments_window
                return True

            logger.error("编辑窗口未出现 (v3)")
            return False

        logger.info("已打开编辑框 (v3)")
        return True

    def _add_images(self, image_paths: List[str]) -> dict:
        """
        添加图片

        Args:
            image_paths: 图片路径列表

        Returns:
            {"success": bool, "added": int, "failed": int}
        """
        result = {"success": False, "added": 0, "failed": 0}

        if not image_paths:
            result["success"] = True
            return result

        # 限制图片数量
        if len(image_paths) > MAX_IMAGES:
            logger.warning(f"图片数量超限，只添加前 {MAX_IMAGES} 张")
            image_paths = image_paths[:MAX_IMAGES]

        # 根据版本选择不同的添加方式
        if self._wechat_version == "v4":
            return self._add_images_v4(image_paths)
        else:
            return self._add_images_v3(image_paths)

    def _add_images_v4(self, image_paths: List[str]) -> dict:
        """
        微信 4.0 添加图片

        一次性添加所有图片：在文件名输入框输入 "file1" "file2" "file3" 格式
        """
        result = {"success": False, "added": 0, "failed": 0}

        if not self._sns_window or not self._sns_window.Exists(0, 0):
            logger.error("朋友圈窗口不存在 (v4)")
            return result

        if not image_paths:
            result["success"] = True
            return result

        # 过滤存在的图片
        valid_paths = []
        for img_path in image_paths:
            if Path(img_path).exists():
                valid_paths.append(img_path)
            else:
                logger.warning(f"图片不存在: {img_path}")
                result["failed"] += 1

        if not valid_paths:
            logger.error("没有有效的图片路径")
            return result

        try:
            # 查找"添加图片"按钮
            add_btn = self._sns_window.ListItemControl(
                searchDepth=15,
                Name="添加图片",
                ClassName=self.ADD_IMAGE_CELL_CLASS
            )

            if not add_btn.Exists(5, 1):
                add_btn = self._sns_window.ListItemControl(
                    searchDepth=15,
                    Name="添加图片"
                )

            if not add_btn.Exists(5, 1):
                logger.error("未找到'添加图片'按钮 (v4)")
                return result

            # 点击添加图片按钮（只点击一次）
            add_btn.Click()
            logger.debug("已点击'添加图片'按钮")
            time.sleep(STEP_DELAY)

            # 等待文件对话框出现
            file_dialog = auto.WindowControl(
                searchDepth=2,
                Name="打开"
            )

            if not file_dialog.Exists(5, 1):
                file_dialog = self._sns_window.WindowControl(
                    searchDepth=5,
                    ClassName=self.FILE_DIALOG_CLASS
                )

            if not file_dialog.Exists(5, 1):
                logger.error("文件对话框未出现 (v4)")
                return result

            logger.debug("文件对话框已打开")
            file_dialog.SetFocus()
            time.sleep(SHORT_DELAY)

            # 导航到图片所在文件夹（如果指定了路径）
            if self._folder_path and Path(self._folder_path).exists():
                logger.debug(f"导航到文件夹: {self._folder_path}")
                # 使用 Ctrl+L 聚焦地址栏
                pyautogui.hotkey('ctrl', 'l')
                time.sleep(SHORT_DELAY)
                # 粘贴文件夹路径
                pyperclip.copy(self._folder_path)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(SHORT_DELAY)
                # 按 Enter 导航
                pyautogui.press('enter')
                time.sleep(STEP_DELAY)
                logger.debug("已导航到目标文件夹")

            # 构建多文件输入格式: "file1" "file2" "file3"（只需文件名，不含路径和扩展名）
            files_str = " ".join(f'"{Path(path).stem}"' for path in valid_paths)
            logger.debug(f"输入文件名: {files_str}")

            # 查找文件名输入框
            edit = file_dialog.ComboBoxControl(searchDepth=10, Name="文件名(N):")
            if not edit.Exists(3, 1):
                edit = file_dialog.EditControl(searchDepth=10)

            if not edit.Exists(3, 1):
                logger.error("未找到文件名输入框")
                file_dialog.SendKeys("{Escape}")
                return result

            # 点击输入框
            edit.Click()
            time.sleep(SHORT_DELAY)

            # 使用剪贴板粘贴所有文件路径
            pyperclip.copy(files_str)
            time.sleep(SHORT_DELAY)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(SHORT_DELAY)

            # 点击打开按钮
            open_btn = file_dialog.ButtonControl(
                searchDepth=10,
                Name="打开(O)"
            )

            if open_btn.Exists(3, 1):
                open_btn.Click()
                logger.debug("已点击'打开'按钮")
            else:
                file_dialog.SendKeys("{Enter}")
                logger.debug("已按 Enter 确认")

            time.sleep(LONG_DELAY)

            result["added"] = len(valid_paths)
            result["success"] = True
            logger.info(f"图片添加完成 (v4): 一次性添加 {len(valid_paths)} 张图片")

        except Exception as e:
            logger.warning(f"添加图片失败: {e}")
            result["failed"] = len(valid_paths)

        return result

    def _input_file_path_via_clipboard(self, file_dialog: auto.WindowControl, file_path: str) -> bool:
        """
        通过剪贴板输入文件路径 (避免中文乱码)

        Args:
            file_dialog: 文件对话框控件
            file_path: 文件路径

        Returns:
            是否成功
        """
        try:
            # 查找文件名输入框
            edit = auto.EditControl(
                searchDepth=15,
                Name="文件名(N):"
            )

            if not edit.Exists(3, 1):
                # 尝试其他方式
                edit = file_dialog.EditControl(searchDepth=10)

            if not edit.Exists(3, 1):
                logger.error("未找到文件名输入框")
                return False

            # 点击输入框
            edit.Click()
            time.sleep(SHORT_DELAY)

            # 使用剪贴板输入路径 (避免 SendKeys 中文乱码)
            pyperclip.copy(file_path)
            time.sleep(SHORT_DELAY)

            # 全选并粘贴
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(SHORT_DELAY)

            logger.debug(f"已通过剪贴板输入路径: {file_path}")
            return True

        except Exception as e:
            logger.error(f"输入文件路径失败: {e}")
            return False

    def _add_images_v3(self, image_paths: List[str]) -> dict:
        """
        微信 3.x 添加图片

        通过剪贴板粘贴图片
        """
        result = {"success": False, "added": 0, "failed": 0}

        compose_window = self._compose_window or self._moments_window

        if not compose_window or not compose_window.Exists(0, 0):
            logger.error("编辑窗口不存在")
            return result

        for i, img_path in enumerate(image_paths):
            logger.debug(f"添加图片 {i+1}/{len(image_paths)}: {img_path}")

            if not Path(img_path).exists():
                logger.warning(f"图片不存在: {img_path}")
                result["failed"] += 1
                continue

            try:
                # 查找添加图片区域
                add_img_btn = compose_window.ButtonControl(
                    searchDepth=10,
                    Name="添加图片"
                )

                if not add_img_btn.Exists(3, 1):
                    # 尝试其他定位
                    add_img_btn = compose_window.ImageControl(
                        searchDepth=10,
                        AutomationId="addImage"
                    )

                if not add_img_btn.Exists(3, 1):
                    # 可能需要点击已有图片区域
                    img_list = compose_window.ListControl(searchDepth=10)
                    if img_list.Exists(3, 1):
                        add_img_btn = img_list

                if not add_img_btn.Exists(3, 1):
                    logger.warning("未找到添加图片按钮")
                    # 尝试直接粘贴
                    pass

                # 将图片复制到剪贴板
                if not self._clipboard.set_image(img_path):
                    logger.warning(f"复制图片到剪贴板失败: {img_path}")
                    result["failed"] += 1
                    continue

                time.sleep(SHORT_DELAY)

                # 验证剪贴板
                if not self._clipboard.verify_has_image():
                    logger.warning("剪贴板中没有图片")
                    result["failed"] += 1
                    continue

                # 点击添加区域
                if add_img_btn.Exists(0, 0):
                    add_img_btn.Click()
                    time.sleep(SHORT_DELAY)

                # 粘贴图片 (Ctrl+V)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(STEP_DELAY)

                result["added"] += 1
                logger.debug(f"已添加图片: {img_path}")

            except Exception as e:
                logger.warning(f"添加图片失败: {img_path}, {e}")
                result["failed"] += 1

        result["success"] = result["added"] > 0
        logger.info(f"图片添加完成 (v3): 成功 {result['added']}, 失败 {result['failed']}")
        return result

    def _input_text(self, text: str) -> bool:
        """
        输入文案

        Args:
            text: 文案内容
        """
        if not text:
            return True

        compose_window = self._compose_window or self._moments_window

        if not compose_window or not compose_window.Exists(0, 0):
            logger.error("编辑窗口不存在")
            return False

        # 根据版本查找文本输入框
        text_edit = None

        if self._wechat_version == "v4":
            # 微信 4.0 使用 mmui::ReplyInputField 类名
            text_edit = compose_window.Control(
                searchDepth=15,
                ClassName=self.INPUT_FIELD_CLASS  # mmui::ReplyInputField
            )

            if not text_edit.Exists(5, 1):
                # 备用：通过 Name 查找
                text_edit = compose_window.Control(
                    searchDepth=15,
                    Name="这一刻的想法..."
                )

            if not text_edit.Exists(5, 1):
                # 再尝试 EditControl
                text_edit = compose_window.EditControl(searchDepth=15)
        else:
            # 微信 3.x 使用 EditControl
            text_edit = compose_window.EditControl(
                searchDepth=10,
                Name="这一刻的想法..."
            )

            if not text_edit.Exists(5, 1):
                text_edit = compose_window.EditControl(searchDepth=10)

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

    def _click_publish(self) -> bool:
        """点击发表按钮"""
        compose_window = self._compose_window or self._moments_window

        if not compose_window or not compose_window.Exists(0, 0):
            logger.error("编辑窗口不存在")
            return False

        publish_btn = None

        if self._wechat_version == "v4":
            # 微信 4.0：可能有多个"发表"按钮，需要选择底部的绿色按钮
            # 使用递归查找所有 Name="发表" 的控件
            all_publish_btns = []

            def find_publish_controls(control, depth=0):
                """递归查找所有发表按钮"""
                if depth > 15:
                    return
                try:
                    if control.Name == "发表":
                        all_publish_btns.append(control)
                    for child in control.GetChildren():
                        find_publish_controls(child, depth + 1)
                except Exception:
                    pass

            find_publish_controls(compose_window)

            if all_publish_btns:
                # 选择 Y 坐标最大的（底部的按钮）
                publish_btn = max(
                    all_publish_btns,
                    key=lambda btn: btn.BoundingRectangle.top if btn.BoundingRectangle else 0
                )
                logger.debug(f"找到 {len(all_publish_btns)} 个'发表'按钮，选择底部的")

        if not publish_btn or not publish_btn.Exists(0, 0):
            # 回退到原有逻辑
            publish_btn = compose_window.ButtonControl(
                searchDepth=10,
                Name="发表"
            )

            if not publish_btn.Exists(5, 1):
                publish_btn = compose_window.TextControl(
                    searchDepth=10,
                    Name="发表"
                )

        if not publish_btn or not publish_btn.Exists(5, 1):
            logger.error("未找到'发表'按钮")
            return False

        publish_btn.Click()
        logger.debug("已点击'发表'按钮")
        time.sleep(STEP_DELAY)

        return True

    def _wait_for_publish_complete(self) -> bool:
        """等待发布完成"""
        start_time = time.time()

        if self._wechat_version == "v4":
            # 微信 4.0：发布后编辑区会消失，但朋友圈窗口保持打开
            # 检测方式：检查底部绿色"发表"按钮是否消失
            logger.debug("等待发布完成 (v4)...")

            # 先等待一段时间让发布动作开始
            time.sleep(PUBLISH_WAIT)

            # 检查发布按钮是否还存在（如果消失说明发布完成）
            while time.time() - start_time < PUBLISH_TIMEOUT:
                if self._sns_window and self._sns_window.Exists(0, 0):
                    # 检查是否还有底部的"发表"按钮
                    publish_btn_exists = False
                    try:
                        all_publish_btns = []

                        def find_publish_controls(control, depth=0):
                            if depth > 15:
                                return
                            try:
                                if control.Name == "发表":
                                    all_publish_btns.append(control)
                                for child in control.GetChildren():
                                    find_publish_controls(child, depth + 1)
                            except Exception:
                                pass

                        find_publish_controls(self._sns_window)

                        # 检查是否有底部的发表按钮（Y 坐标较大的）
                        sns_rect = self._sns_window.BoundingRectangle
                        for btn in all_publish_btns:
                            rect = btn.BoundingRectangle
                            if rect and sns_rect and rect.top > sns_rect.top + 200:
                                publish_btn_exists = True
                                break
                    except Exception:
                        pass

                    if not publish_btn_exists:
                        logger.debug("发布按钮已消失，发布完成 (v4)")
                        return True

                time.sleep(1.0)

            # 超时也返回 True，不阻塞后续流程
            logger.warning("等待发布完成超时，继续执行 (v4)")
            return True

        # 微信 3.x 逻辑
        while time.time() - start_time < PUBLISH_TIMEOUT:
            # 检查编辑窗口是否关闭
            if self._compose_window and not self._compose_window.Exists(0, 0):
                logger.debug("编辑窗口已关闭")
                time.sleep(PUBLISH_WAIT)
                return True

            # 检查是否有发布中的提示
            if self._moments_window and self._moments_window.Exists(0, 0):
                uploading = self._moments_window.TextControl(
                    searchDepth=10,
                    Name="正在上传"
                )
                if not uploading.Exists(0, 0):
                    # 没有上传中提示，可能已完成
                    time.sleep(PUBLISH_WAIT)
                    return True

            time.sleep(1.0)

        logger.warning("等待发布完成超时")
        return False

    def _view_published_moment(self, product_link: str = "") -> bool:
        """
        发布后查看朋友圈并评论产品链接

        流程:
        1. 等待 10 秒
        2. 点击右上角头像按钮
        3. 等待 2 秒
        4. 点击弹出窗口中的"朋友圈"链接
        5. 点击第一条朋友圈
        6. 点击 "..." 按钮
        7. 点击 "评论" 按钮
        8. 如果有产品链接，输入并发送

        Args:
            product_link: 产品链接（用于评论）
        """
        if not self._sns_window or not self._sns_window.Exists(0, 0):
            logger.warning("朋友圈窗口不存在，跳过查看操作")
            return True

        try:
            # 1. 等待 10 秒
            logger.debug("等待 10 秒...")
            time.sleep(10)

            # 2. 点击右上角头像按钮
            # 头像按钮在朋友圈窗口的右上角，通过坐标定位
            rect = self._sns_window.BoundingRectangle
            avatar_clicked = False
            if rect:
                # 优先尝试在窗口内找到右上区域的按钮/图片/超链接，避免坐标误点关闭窗口
                try:
                    candidates = [
                        c for c in self._sns_window.GetChildren()
                        if getattr(c, "BoundingRectangle", None)
                    ]
                except Exception:
                    candidates = []

                for ctrl in candidates:
                    ctrl_rect = ctrl.BoundingRectangle
                    if not ctrl_rect:
                        continue
                    if (
                        ctrl_rect.right >= rect.right - 120
                        and ctrl_rect.top <= rect.top + 120
                        and ctrl.ControlTypeName in ("ButtonControl", "ImageControl", "HyperlinkControl")
                    ):
                        try:
                            ctrl.Click()
                            avatar_clicked = True
                            logger.debug(f"已点击头像候选控件 {ctrl.ControlTypeName} @ {ctrl_rect}")
                            break
                        except Exception as click_err:
                            logger.debug(f"点击头像候选失败: {click_err}")

                if not avatar_clicked:
                    # 使用测试确定的坐标：距离右边 110px，距离顶部 400px
                    avatar_x = rect.right - 110
                    avatar_y = rect.top + 400
                    pyautogui.click(avatar_x, avatar_y)
                    avatar_clicked = True
                    logger.debug(f"已点击头像 (坐标: {avatar_x}, {avatar_y})")
            else:
                logger.warning("无法获取窗口位置")
                return True

            if not avatar_clicked:
                return True

            # 3. 等待 20 秒让弹窗出现
            logger.debug("等待 20 秒...")
            time.sleep(20)

            # 4. 点击弹出窗口中的"朋友圈"区域
            # 使用测试确定的坐标：相对于头像位置 +400, +200
            moment_x = avatar_x + 400
            moment_y = avatar_y + 200
            pyautogui.click(moment_x, moment_y)
            logger.debug(f"已点击'朋友圈'区域 (坐标: {moment_x}, {moment_y})")

            # 5. 等待个人朋友圈页面加载
            logger.debug("等待 3 秒...")
            time.sleep(3)

            # 6. 点击第一条朋友圈 (mmui::AlbumContentCell)
            first_moment = self._sns_window.ListItemControl(
                searchDepth=15,
                ClassName="mmui::AlbumContentCell"
            )

            if first_moment.Exists(5, 1):
                first_moment.Click()
                logger.debug("已点击第一条朋友圈")
                time.sleep(2)  # 等待详情页加载
            else:
                logger.warning("未找到第一条朋友圈元素")
                return True

            # 7. 点击评论按钮（...按钮）打开评论输入框
            # 使用混合定位策略：动态图像识别 > 时间戳相对定位 > 坐标后备
            dots_pos = self._find_dots_button_hybrid()
            if dots_pos:
                pyautogui.click(dots_pos[0], dots_pos[1])
                logger.debug(f"已点击 '...' 按钮 @ {dots_pos}")
            else:
                logger.warning("无法定位 '...' 按钮")
                return True

            # 等待菜单弹出
            time.sleep(0.5)

            # 8. 点击 "评论" 按钮
            comment_btn = self._sns_window.TextControl(searchDepth=20, Name="评论")
            if comment_btn.Exists(2, 0):
                comment_btn.Click()
                logger.debug("已点击 '评论' 按钮 (UI 自动化)")
            else:
                # 备用：尝试 ButtonControl
                comment_btn = self._sns_window.ButtonControl(searchDepth=20, Name="评论")
                if comment_btn.Exists(1, 0):
                    comment_btn.Click()
                    logger.debug("已点击 '评论' 按钮 (ButtonControl)")
                else:
                    # 坐标后备：评论按钮在 "..." 左边大约 90 像素
                    if comment_pos:
                        pyautogui.click(click_x - 90, click_y)
                        logger.debug(f"已点击 '评论' 按钮 (坐标后备: {click_x - 90}, {click_y})")
                    else:
                        logger.warning("未找到 '评论' 按钮")
                        return True

            time.sleep(STEP_DELAY)

            # 9. 如果有产品链接，输入并发送
            # 点击"评论"后光标已在输入框中，直接粘贴即可
            if product_link:
                logger.debug(f"准备输入产品链接: {product_link}")

                # 直接通过剪贴板粘贴产品链接（光标已在输入框中）
                pyperclip.copy(product_link)
                time.sleep(SHORT_DELAY)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(STEP_DELAY)
                logger.debug("已输入产品链接")

                # 10. 点击 "发送" 按钮（使用多置信度图像识别）
                send_pos = self._find_button_by_image_multi_confidence("send_btn.png")
                if send_pos:
                    pyautogui.click(send_pos[0], send_pos[1])
                    logger.debug(f"已点击 '发送' 按钮 (图像识别: {send_pos})")
                    time.sleep(STEP_DELAY)
                else:
                    # 后备：相对坐标定位（从配置读取）
                    rect = self._sns_window.BoundingRectangle
                    if rect:
                        win_height = rect.bottom - rect.top
                        send_x_offset = get_config("ui_location.send_btn_x_offset", 80)
                        send_y_ratio = get_config("ui_location.send_btn_y_ratio", 0.52)
                        send_x = rect.right - send_x_offset
                        send_y = rect.top + int(win_height * send_y_ratio)
                        pyautogui.click(send_x, send_y)
                        logger.debug(f"已点击 '发送' 按钮 (坐标后备: {send_x}, {send_y})")
                        time.sleep(STEP_DELAY)

            # 11. 关闭朋友圈窗口
            time.sleep(1)  # 等待评论发送完成
            rect = self._sns_window.BoundingRectangle
            if rect:
                # 点击右上角关闭按钮 (×) - 从配置读取偏移量
                close_offset = get_config("ui_location.close_btn_offset", 15)
                close_x = rect.right - close_offset
                close_y = rect.top + close_offset
                pyautogui.click(close_x, close_y)
                logger.debug(f"已点击关闭按钮 ({close_x}, {close_y})")

            return True

        except Exception as e:
            logger.warning(f"查看朋友圈失败: {e}")
            return True

    def _return_to_main(self) -> bool:
        """返回主界面"""
        if self._wechat_version == "v4":
            return self._return_to_main_v4()
        else:
            return self._return_to_main_v3()

    def _return_to_main_v4(self) -> bool:
        """微信 4.0 返回主界面 - 暂时不关闭朋友圈窗口"""
        # 暂时不关闭朋友圈窗口，保持打开状态
        # 后续可能有其他操作需要在朋友圈窗口进行
        logger.debug("发布完成，保持朋友圈窗口打开 (v4)")
        return True

    def _return_to_main_v3(self) -> bool:
        """微信 3.x 返回主界面"""
        # 关闭朋友圈窗口
        if self._moments_window and self._moments_window.Exists(0, 0):
            # 尝试点击关闭按钮
            close_btn = self._moments_window.ButtonControl(
                searchDepth=5,
                Name="关闭"
            )

            if close_btn.Exists(3, 1):
                close_btn.Click()
                logger.debug("已点击关闭按钮 (v3)")
            else:
                # 使用快捷键关闭
                pyautogui.hotkey('alt', 'F4')
                logger.debug("使用 Alt+F4 关闭窗口 (v3)")

            time.sleep(SHORT_DELAY)

        # 确认回到主窗口
        main_window = self._controller.get_main_window()
        if main_window and main_window.Exists(0, 0):
            self._controller.activate_window(main_window)
            logger.debug("已返回主界面 (v3)")
            return True

        return False

    def _cancel_compose(self) -> bool:
        """取消编辑"""
        if self._wechat_version == "v4":
            return self._cancel_compose_v4()
        else:
            return self._cancel_compose_v3()

    def _cancel_compose_v4(self) -> bool:
        """微信 4.0 取消编辑"""
        if not self._sns_window or not self._sns_window.Exists(0, 0):
            return True

        # 查找取消按钮
        cancel_btn = self._sns_window.Control(
            searchDepth=15,
            Name="取消"
        )

        if cancel_btn.Exists(3, 1):
            cancel_btn.Click()
            logger.debug("已点击'取消'按钮 (v4)")
            time.sleep(STEP_DELAY)

            # 处理确认放弃对话框
            for _ in range(5):
                discard_btn = auto.ButtonControl(
                    searchDepth=10,
                    Name="放弃"
                )
                if discard_btn.Exists(0.5, 0):
                    discard_btn.Click()
                    logger.debug("已确认放弃 (v4)")
                    break
                time.sleep(SHORT_DELAY)

            return True

        # 使用 ESC 键
        self._sns_window.SendKeys("{Escape}")
        time.sleep(SHORT_DELAY)

        return True

    def _cancel_compose_v3(self) -> bool:
        """微信 3.x 取消编辑"""
        compose_window = self._compose_window or self._moments_window

        if not compose_window or not compose_window.Exists(0, 0):
            return True

        # 查找取消按钮
        cancel_btn = compose_window.ButtonControl(
            searchDepth=10,
            Name="取消"
        )

        if cancel_btn.Exists(3, 1):
            cancel_btn.Click()
            time.sleep(SHORT_DELAY)

            # 可能有确认对话框
            confirm_btn = auto.ButtonControl(
                searchDepth=5,
                Name="确定"
            )
            if confirm_btn.Exists(2, 1):
                confirm_btn.Click()

            logger.debug("已取消编辑 (v3)")
            return True

        # 使用 ESC 键
        pyautogui.press('escape')
        time.sleep(SHORT_DELAY)

        return True

    # ========================================================
    # 辅助方法
    # ========================================================
    # 注意：_take_screenshot 方法已在基类 BaseSender 中实现

    # 模板图片目录
    TEMPLATE_DIR = Path(__file__).parent.parent / "data" / "templates"

    def _find_button_by_image(
        self,
        template_name: str,
        region: Optional[tuple] = None,
        confidence: float = 0.8
    ) -> Optional[tuple]:
        """
        使用图像识别查找按钮

        Args:
            template_name: 模板图片名称（不含路径）
            region: 搜索区域 (left, top, width, height)，None 表示全屏
            confidence: 匹配置信度 (0.0-1.0)

        Returns:
            (center_x, center_y) 或 None
        """
        template_path = self.TEMPLATE_DIR / template_name

        if not template_path.exists():
            logger.warning(f"模板图片不存在: {template_path}")
            return None

        try:
            location = pyautogui.locateOnScreen(
                str(template_path),
                region=region,
                confidence=confidence
            )
            if location:
                center = pyautogui.center(location)
                logger.debug(f"图像识别成功: {template_name} @ ({center.x}, {center.y})")
                return (center.x, center.y)
        except Exception as e:
            logger.warning(f"图像识别失败: {e}")

        return None

    def _find_button_by_image_multi_confidence(
        self,
        template_name: str,
        region: Optional[tuple] = None
    ) -> Optional[tuple]:
        """
        使用多置信度尝试图像识别

        从配置文件读取置信度列表，从高到低逐步尝试，
        提高跨电脑兼容性。

        Args:
            template_name: 模板图片名称
            region: 搜索区域

        Returns:
            (center_x, center_y) 或 None
        """
        confidence_levels = get_config(
            "ui_location.image_confidence_levels",
            [0.8, 0.6, 0.4]
        )

        for confidence in confidence_levels:
            pos = self._find_button_by_image(template_name, region, confidence)
            if pos:
                logger.debug(f"图像识别成功 (confidence={confidence}): {template_name}")
                return pos

        logger.warning(f"图像识别失败 (尝试了 {confidence_levels}): {template_name}")
        return None

    def _find_dots_by_delete_btn(self) -> Optional[tuple]:
        """
        通过识别删除按钮（垃圾桶）来定位 "..." 按钮

        原理：删除按钮和 "..." 按钮在同一行
        - 找到删除按钮获取 Y 坐标
        - "..." 按钮的 X 坐标固定（距窗口右边 55px）

        Returns:
            (center_x, center_y) 或 None
        """
        if not self._sns_window or not self._sns_window.Exists(0, 0):
            return None

        rect = self._sns_window.BoundingRectangle
        if not rect:
            return None

        # 用图像识别找删除按钮
        template_path = self.TEMPLATE_DIR / "delete_btn.png"
        if not template_path.exists():
            logger.warning(f"删除按钮模板不存在: {template_path}")
            return None

        # 尝试不同置信度
        for confidence in [0.8, 0.7, 0.6, 0.5]:
            try:
                location = pyautogui.locateOnScreen(str(template_path), confidence=confidence)
                if location:
                    center = pyautogui.center(location)
                    # "..." 按钮的 X 坐标固定，Y 坐标和删除按钮相同
                    dots_x_offset = get_config("ui_location.dots_btn_right_offset", 55)
                    dots_x = rect.right - dots_x_offset
                    dots_y = center.y
                    logger.debug(f"通过删除按钮定位成功: delete=({center.x}, {center.y}), dots=({dots_x}, {dots_y})")
                    return (dots_x, dots_y)
            except Exception as e:
                logger.debug(f"删除按钮识别失败 (confidence={confidence}): {e}")

        return None

    def _find_dots_by_timestamp(self) -> Optional[tuple]:
        """
        通过时间戳控件相对定位 "..." 按钮
        时间戳格式: HH:MM, 昨天, X小时前, X分钟前 等

        Returns:
            (center_x, center_y) 或 None
        """
        import re

        if not self._sns_window or not self._sns_window.Exists(0, 0):
            return None

        rect = self._sns_window.BoundingRectangle
        if not rect:
            return None

        # 时间戳匹配模式
        time_patterns = [
            r'^\d{1,2}:\d{2}$',           # HH:MM
            r'^昨天$',
            r'^\d+小时前$',
            r'^\d+分钟前$',
            r'^\d+天前$',
        ]

        def is_timestamp(text):
            if not text:
                return False
            return any(re.match(p, text) for p in time_patterns)

        # 遍历查找时间戳控件
        def find_timestamp_control(ctrl, depth=0):
            if depth > 20:
                return None
            try:
                if ctrl.ControlTypeName == 'TextControl' and is_timestamp(ctrl.Name):
                    ctrl_rect = ctrl.BoundingRectangle
                    # 确保在窗口中部区域（排除顶部和评论区的时间）
                    if ctrl_rect and rect.top + 400 < ctrl_rect.top < rect.bottom - 300:
                        return ctrl
                for child in ctrl.GetChildren():
                    result = find_timestamp_control(child, depth + 1)
                    if result:
                        return result
            except Exception:
                pass
            return None

        timestamp_ctrl = find_timestamp_control(self._sns_window)
        if timestamp_ctrl:
            ts_rect = timestamp_ctrl.BoundingRectangle
            offset = get_config("ui_location.dots_timestamp_offset", 40)
            dots_x = ts_rect.right + offset
            dots_y = (ts_rect.top + ts_rect.bottom) // 2
            logger.debug(f"时间戳定位成功: '{timestamp_ctrl.Name}' @ ({dots_x}, {dots_y})")
            return (dots_x, dots_y)

        return None

    def _find_dots_button_hybrid(self) -> Optional[tuple]:
        """
        混合定位策略查找 "..." 按钮
        优先级: 删除按钮定位 > 时间戳相对定位 > 坐标后备

        Returns:
            (center_x, center_y) 或 None
        """
        if not self._sns_window or not self._sns_window.Exists(0, 0):
            return None

        rect = self._sns_window.BoundingRectangle

        # 1. 通过删除按钮（垃圾桶）定位（最可靠，Y坐标随内容变化）
        pos = self._find_dots_by_delete_btn()
        if pos:
            return pos

        # 2. 时间戳相对定位
        pos = self._find_dots_by_timestamp()
        if pos:
            return pos

        # 3. 坐标后备（基于窗口位置计算）
        if rect:
            right_offset = get_config("ui_location.dots_btn_right_offset", 55)
            top_offset = get_config("ui_location.dots_btn_top_offset", 864)
            logger.debug(f"使用坐标后备: ({rect.right - right_offset}, {rect.top + top_offset})")
            return (rect.right - right_offset, rect.top + top_offset)

        return None

    # 注意：_take_error_screenshot 方法已在基类 BaseSender 中实现

    def is_moment_window_open(self) -> bool:
        """检查朋友圈窗口是否打开"""
        # 4.0 检查
        window_v4 = auto.WindowControl(
            searchDepth=1,
            ClassName=self.MAIN_WINDOW_CLASS_V4
        )
        if window_v4.Exists(1, 0):
            # 检查是否在朋友圈页面
            moment_content = window_v4.Control(searchDepth=5, Name="朋友圈")
            if moment_content.Exists(0, 0):
                return True

        # 3.x 检查
        window_v3 = auto.WindowControl(
            searchDepth=1,
            ClassName=self.MOMENTS_WINDOW_CLASS_V3
        )
        return window_v3.Exists(1, 0)

    def is_compose_window_open(self) -> bool:
        """检查编辑窗口是否打开"""
        # 3.x 检查
        window = auto.WindowControl(
            searchDepth=1,
            ClassName=self.COMPOSE_WINDOW_CLASS_V3
        )
        if window.Exists(1, 0):
            return True

        # 4.0 中编辑区域在主窗口内，检查是否有输入框
        if self._moments_window and self._moments_window.Exists(0, 0):
            edit = self._moments_window.EditControl(searchDepth=10)
            return edit.Exists(1, 0)

        return False


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


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=== 朋友圈发布器测试 ===\n")

    # 创建测试内容
    test_content = Content(
        content_code="TEST001",
        text="这是一条测试朋友圈消息 #自动发布测试",
        image_paths=[],  # 添加测试图片路径
        channel=Channel.moment,
    )

    print(f"测试内容: {test_content.content_code}")
    print(f"文案: {test_content.text}")
    print(f"图片数: {test_content.image_count}")

    # 确认执行
    confirm = input("\n确认发送测试消息? (y/N): ")
    if confirm.lower() != 'y':
        print("已取消")
        exit(0)

    # 发送
    sender = MomentSender()
    result = sender.send_moment(test_content)

    print(f"\n发送结果: {result.status.value}")
    print(f"消息: {result.message}")
    print(f"耗时: {result.duration:.2f} 秒")

    if result.screenshot_path:
        print(f"截图: {result.screenshot_path}")
