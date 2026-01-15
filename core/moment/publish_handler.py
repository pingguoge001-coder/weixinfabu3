"""
朋友圈发布操作模块

功能:
- 打开编辑框（图文/纯文字）
- 点击发表按钮
- 等待发布完成
- 发布后查看和评论
- 取消编辑
"""

import time
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pyautogui
import pyperclip
import uiautomation as auto

from services.config_manager import get_config

logger = logging.getLogger(__name__)


# ============================================================
# 配置常量
# ============================================================

# 操作间隔时间（秒）
STEP_DELAY = 0.8
SHORT_DELAY = 0.3
PUBLISH_WAIT = 3.0

# 超时设置（秒）
PUBLISH_TIMEOUT = 30

# 微信 4.0 UI 元素类名
INPUT_FIELD_CLASS = "mmui::ReplyInputField"
ADD_IMAGE_CELL_CLASS = "mmui::PublishImageAddGridCell"


class PublishHandler:
    """朋友圈发布操作处理器"""

    def __init__(
        self,
        wechat_version: Optional[str] = None,
        locator=None
    ):
        """
        初始化发布处理器

        Args:
            wechat_version: 微信版本 ("v3" 或 "v4")
            locator: 元素定位器实例
        """
        self._wechat_version = wechat_version
        self._locator = locator
        self._compose_window: Optional[auto.WindowControl] = None

    def set_version(self, version: str):
        """设置微信版本"""
        self._wechat_version = version

    def set_locator(self, locator):
        """设置元素定位器"""
        self._locator = locator

    # ========================================================
    # 打开编辑框
    # ========================================================

    def open_compose_dialog(
        self,
        has_images: bool,
        moments_window: auto.WindowControl,
        sns_window: Optional[auto.WindowControl] = None
    ) -> bool:
        """
        打开编辑框 (支持 3.x 和 4.0)

        Args:
            has_images: 是否有图片（决定短按还是长按相机图标）
            moments_window: 朋友圈窗口
            sns_window: 朋友圈独立窗口（4.0）

        Returns:
            是否成功
        """
        if not moments_window or not moments_window.Exists(0, 0):
            logger.error("朋友圈窗口不存在")
            return False

        if self._wechat_version == "v4":
            result = self._open_compose_dialog_v4(has_images, sns_window)
            if result:
                self._compose_window = sns_window
            return result
        else:
            result = self._open_compose_dialog_v3(has_images, moments_window)
            if result:
                self._compose_window = moments_window
            return result

    def _open_compose_dialog_v4(
        self,
        has_images: bool,
        sns_window: auto.WindowControl
    ) -> bool:
        """
        微信 4.0 打开发布编辑框

        在朋友圈窗口顶部点击"发表"按钮进入发布界面
        """
        if not sns_window or not sns_window.Exists(0, 0):
            logger.error("朋友圈窗口不存在 (v4)")
            return False

        # 4.0 中发表按钮在朋友圈窗口顶部
        publish_btn = sns_window.Control(
            searchDepth=10,
            Name="发表"
        )

        if not publish_btn.Exists(5, 1):
            # 尝试通过 TabBarItem 查找
            publish_btn = sns_window.Control(
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
        input_field = sns_window.Control(
            searchDepth=15,
            ClassName=INPUT_FIELD_CLASS
        )
        add_image_btn = sns_window.ListItemControl(
            searchDepth=15,
            Name="添加图片",
            ClassName=ADD_IMAGE_CELL_CLASS
        )

        if input_field.Exists(5, 1) or add_image_btn.Exists(5, 1):
            logger.info("已打开发布界面 (v4)")
            return True

        logger.error("发布界面未出现 (v4)")
        return False

    def _open_compose_dialog_v3(
        self,
        has_images: bool,
        moments_window: auto.WindowControl
    ) -> bool:
        """微信 3.x 打开发布编辑框"""
        # 查找相机图标/发布按钮
        camera_btn = moments_window.ButtonControl(
            searchDepth=5,
            Name="拍照分享"
        )

        if not camera_btn.Exists(5, 1):
            # 尝试其他定位方式
            camera_btn = moments_window.ImageControl(
                searchDepth=5,
                AutomationId="camera"
            )

        if not camera_btn.Exists(5, 1):
            # 尝试通过工具栏查找
            toolbar = moments_window.ToolBarControl(searchDepth=5)
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
        compose_window = auto.WindowControl(
            searchDepth=1,
            ClassName="SnsUploadWnd"
        )

        if not compose_window.Exists(10, 1):
            # 可能是同一个窗口内的编辑区域
            logger.debug("查找内嵌编辑区域 (v3)")
            edit_area = moments_window.EditControl(searchDepth=10)
            if edit_area.Exists(5, 1):
                return True

            logger.error("编辑窗口未出现 (v3)")
            return False

        logger.info("已打开编辑框 (v3)")
        return True

    # ========================================================
    # 点击发表
    # ========================================================

    def click_publish(
        self,
        window: auto.WindowControl
    ) -> bool:
        """
        点击发表按钮

        Args:
            window: 编辑窗口

        Returns:
            是否成功
        """
        if not window or not window.Exists(0, 0):
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

            find_publish_controls(window)

            if all_publish_btns:
                # 选择 Y 坐标最大的（底部的按钮）
                publish_btn = max(
                    all_publish_btns,
                    key=lambda btn: btn.BoundingRectangle.top if btn.BoundingRectangle else 0
                )
                logger.debug(f"找到 {len(all_publish_btns)} 个'发表'按钮，选择底部的")

        if not publish_btn or not publish_btn.Exists(0, 0):
            # 回退到原有逻辑
            publish_btn = window.ButtonControl(
                searchDepth=10,
                Name="发表"
            )

            if not publish_btn.Exists(5, 1):
                publish_btn = window.TextControl(
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

    # ========================================================
    # 等待发布完成
    # ========================================================

    def wait_for_publish_complete(
        self,
        sns_window: Optional[auto.WindowControl] = None,
        compose_window: Optional[auto.WindowControl] = None
    ) -> bool:
        """
        等待发布完成

        Args:
            sns_window: 朋友圈窗口（4.0）
            compose_window: 编辑窗口（3.x）

        Returns:
            是否成功
        """
        start_time = time.time()

        if self._wechat_version == "v4":
            return self._wait_for_publish_complete_v4(sns_window, start_time)
        else:
            return self._wait_for_publish_complete_v3(compose_window, start_time)

    def _wait_for_publish_complete_v4(
        self,
        sns_window: auto.WindowControl,
        start_time: float
    ) -> bool:
        """微信 4.0 等待发布完成"""
        # 微信 4.0：发布后编辑区会消失，但朋友圈窗口保持打开
        # 检测方式：检查底部绿色"发表"按钮是否消失
        logger.debug("等待发布完成 (v4)...")

        # 先等待一段时间让发布动作开始
        time.sleep(PUBLISH_WAIT)

        # 检查发布按钮是否还存在（如果消失说明发布完成）
        while time.time() - start_time < PUBLISH_TIMEOUT:
            if sns_window and sns_window.Exists(0, 0):
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

                    find_publish_controls(sns_window)

                    # 检查是否有底部的发表按钮（Y 坐标较大的）
                    sns_rect = sns_window.BoundingRectangle
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

    def _wait_for_publish_complete_v3(
        self,
        compose_window: auto.WindowControl,
        start_time: float
    ) -> bool:
        """微信 3.x 等待发布完成"""
        while time.time() - start_time < PUBLISH_TIMEOUT:
            # 检查编辑窗口是否关闭
            if compose_window and not compose_window.Exists(0, 0):
                logger.debug("编辑窗口已关闭")
                time.sleep(PUBLISH_WAIT)
                return True

            time.sleep(1.0)

        logger.warning("等待发布完成超时")
        return False

    # ========================================================
    # 发布后查看和评论
    # ========================================================


    def _find_comment_button(self, sns_window: auto.WindowControl):
        comment_name = "\u8bc4\u8bba"

        if sns_window and sns_window.Exists(0, 0):
            comment_btn = sns_window.TextControl(searchDepth=20, Name=comment_name)
            if comment_btn.Exists(1, 0):
                return comment_btn
            comment_btn = sns_window.ButtonControl(searchDepth=20, Name=comment_name)
            if comment_btn.Exists(1, 0):
                return comment_btn

        try:
            root = auto.GetRootControl()
            comment_btn = root.TextControl(searchDepth=8, Name=comment_name)
            if comment_btn.Exists(1, 0):
                return comment_btn
            comment_btn = root.ButtonControl(searchDepth=8, Name=comment_name)
            if comment_btn.Exists(1, 0):
                return comment_btn
        except Exception:
            pass

        return None

    def _debug_save_region(self, label: str, region: tuple) -> None:
        if not get_config("ui_location.comment_debug_save", False):
            return
        try:
            left, top, width, height = region
        except Exception:
            return
        if width <= 0 or height <= 0:
            return
        screen_w, screen_h = pyautogui.size()
        right = min(screen_w, left + width)
        bottom = min(screen_h, top + height)
        left = max(0, left)
        top = max(0, top)
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            return

        debug_dir = Path(get_config("ui_location.comment_debug_dir", "./data/debug"))
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{label}_{timestamp}_{left}_{top}_{width}_{height}.png"
        try:
            img = pyautogui.screenshot(region=(left, top, width, height))
            img.save(str(debug_dir / filename))
        except Exception:
            pass

    def view_published_moment(
        self,
        sns_window: auto.WindowControl,
        product_link: str = ""
    ) -> bool:
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
            sns_window: 朋友圈窗口
            product_link: 产品链接（用于评论）

        Returns:
            是否成功
        """
        if not sns_window or not sns_window.Exists(0, 0):
            logger.warning("朋友圈窗口不存在，跳过查看操作")
            return True

        try:
            # 1. 等待 10 秒
            logger.debug("等待 10 秒...")
            time.sleep(10)

            # 2. 点击右上角头像按钮
            rect = sns_window.BoundingRectangle
            avatar_clicked = False
            if rect:
                # 优先尝试在窗口内找到右上区域的按钮/图片/超链接
                try:
                    candidates = [
                        c for c in sns_window.GetChildren()
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
                    # 使用测试确定的坐标（支持配置偏移）
                    avatar_x_offset = get_config("ui_location.avatar_x_offset", 110)
                    avatar_y_offset = get_config("ui_location.avatar_y_offset", 400)
                    avatar_x = rect.right - int(avatar_x_offset)
                    avatar_y = rect.top + int(avatar_y_offset)
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
            moment_x = avatar_x + 400
            moment_y = avatar_y + 200
            pyautogui.click(moment_x, moment_y)
            logger.debug(f"已点击'朋友圈'区域 (坐标: {moment_x}, {moment_y})")

            # 5. 等待个人朋友圈页面加载
            logger.debug("等待 3 秒...")
            time.sleep(3)

            # 6. 点击第一条朋友圈
            first_moment = sns_window.ListItemControl(
                searchDepth=15,
                ClassName="mmui::AlbumContentCell"
            )

            if first_moment.Exists(5, 1):
                first_moment.Click()
                logger.debug("已点击第一条朋友圈")
                time.sleep(2)
            else:
                logger.warning("未找到第一条朋友圈元素")
                return True

            # 7. 点击评论按钮（...按钮）
            dots_pos = None
            if self._locator:
                dots_pos = self._locator.find_dots_button_hybrid()
                if dots_pos:
                    pyautogui.click(dots_pos[0], dots_pos[1])
                    logger.debug(f"已点击 '...' 按钮 @ {dots_pos}")
                else:
                    logger.warning("无法定位 '...' 按钮")
                    return True
            else:
                logger.warning("未设置定位器，无法定位 '...' 按钮")
                return True

            # 等待菜单弹出
            time.sleep(0.5)

            # 8. 点击 "评论" 按钮

            comment_btn = self._find_comment_button(sns_window)
            if comment_btn:
                comment_btn.Click()
                logger.debug("Clicked comment button via UIAutomation")
            else:
                comment_clicked = False
                if self._locator and rect:
                    search_regions = []
                    if dots_pos:
                        region_w = get_config("ui_location.comment_btn_dots_search_width", 320)
                        region_h = get_config("ui_location.comment_btn_dots_search_height", 220)
                        left = int(dots_pos[0] - region_w // 2)
                        top = int(dots_pos[1] - region_h // 2)
                        search_regions.append((left, top, int(region_w), int(region_h)))

                    bottom_h = get_config("ui_location.comment_btn_bottom_search_height", 260)
                    bottom_top = max(rect.top, rect.bottom - int(bottom_h))
                    search_regions.append((rect.left, bottom_top, rect.right - rect.left, rect.bottom - bottom_top))

                    confidence_levels = get_config(
                        "ui_location.comment_btn_confidence_levels",
                        [0.8, 0.6, 0.4]
                    )
                    confidence_levels = [
                        c for c in confidence_levels if isinstance(c, (int, float)) and c > 0
                    ]
                    if not confidence_levels:
                        confidence_levels = [0.6]

                    for idx, region in enumerate(search_regions):
                        self._debug_save_region(f"comment_region_{idx}", region)
                        for confidence in confidence_levels:
                            pos = self._locator.find_button_by_image(
                                "comment_btn.png",
                                region=region,
                                confidence=confidence
                            )
                            if pos:
                                pyautogui.click(pos[0], pos[1])
                                logger.debug(f"Clicked comment button by image @ {pos}")
                                comment_clicked = True
                                break
                        if comment_clicked:
                            break

                if not comment_clicked:
                    logger.warning("Comment button not found")
                    return True
            time.sleep(STEP_DELAY)

            input_ctrl = None
            input_rect = None
            try:
                input_ctrl = sns_window.Control(searchDepth=20, ClassName=INPUT_FIELD_CLASS)
                if not input_ctrl.Exists(1, 0):
                    input_ctrl = sns_window.EditControl(searchDepth=20)
                if input_ctrl.Exists(1, 0):
                    input_rect = input_ctrl.BoundingRectangle
                    input_ctrl.Click()
                    time.sleep(SHORT_DELAY)
                    if input_rect:
                        logger.debug(
                            "已点击评论输入框: "
                            f"({input_rect.left},{input_rect.top})-({input_rect.right},{input_rect.bottom})"
                        )
            except Exception as focus_err:
                logger.debug(f"定位评论输入框失败: {focus_err}")

            # 9. 如果有产品链接，输入并发送
            send_clicked = False
            if product_link:
                logger.debug(f"准备输入产品链接: {product_link}")
                if input_ctrl and input_ctrl.Exists(0, 0):
                    input_ctrl.Click()
                    time.sleep(SHORT_DELAY)
                pyperclip.copy(product_link)
                time.sleep(SHORT_DELAY)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(STEP_DELAY)
                logger.debug("已输入产品链接")

                # 10. 点击 "发送" 按钮
                logger.info("=== 开始查找发送按钮 ===")

                # 先激活朋友圈窗口，确保焦点正确
                if sns_window and sns_window.Exists(0, 0):
                    sns_window.SetFocus()
                    time.sleep(0.3)
                    logger.info("已激活朋友圈窗口")

                # 方法1：图像识别（限制在朋友圈窗口范围内搜索）
                if self._locator and rect:
                    logger.info("尝试方法1: 图像识别...")
                    # 限制搜索区域为评论输入行附近，避免误点图片
                    search_region = None
                    if dots_pos:
                        dots_x_offset = get_config("ui_location.send_btn_dots_x_offset", None)
                        dots_y_offset = get_config("ui_location.send_btn_dots_y_offset", None)
                        if dots_x_offset is not None and dots_y_offset is not None:
                            expected_x = dots_pos[0] + int(dots_x_offset)
                            expected_y = dots_pos[1] + int(dots_y_offset)
                            region_w = get_config("ui_location.send_btn_dots_search_width", 260)
                            region_h = get_config("ui_location.send_btn_dots_search_height", 180)
                            left = int(expected_x - region_w // 2)
                            top = int(expected_y - region_h // 2)
                            # 搜索区域尽量保持在“...”按钮下方
                            top = max(top, dots_pos[1] + 10)
                            search_region = (left, top, int(region_w), int(region_h))
                            logger.debug(f"基于'...'的搜索区域: {search_region}")

                    if not search_region and not input_rect:
                        try:
                            input_ctrl = sns_window.Control(searchDepth=20, ClassName=INPUT_FIELD_CLASS)
                            if not input_ctrl.Exists(1, 0):
                                input_ctrl = sns_window.EditControl(searchDepth=20)
                            if input_ctrl.Exists(1, 0):
                                input_rect = input_ctrl.BoundingRectangle
                        except Exception as find_err:
                            logger.debug(f"查找评论输入框失败: {find_err}")

                    if input_rect:
                        pad = 40
                        top = max(rect.top, input_rect.top - pad)
                        bottom = min(rect.bottom, input_rect.bottom + pad)
                        if bottom > top:
                            search_region = (rect.left, top, rect.right - rect.left, bottom - top)

                    if not search_region:
                        # 无法定位输入框时，仅在发送按钮高度附近做窄带搜索
                        win_height = rect.bottom - rect.top
                        send_y_ratio = get_config("ui_location.send_btn_y_ratio", 0.52)
                        center_y = rect.top + int(win_height * send_y_ratio)
                        band_half = max(60, min(200, int(win_height * 0.12)))
                        top = max(rect.top, center_y - band_half)
                        bottom = min(rect.bottom, center_y + band_half)
                        search_region = (rect.left, top, rect.right - rect.left, bottom - top)

                    logger.info(f"搜索区域: {search_region}")
                    confidence_levels = get_config(
                        "ui_location.image_confidence_levels",
                        [0.8, 0.6, 0.4]
                    )
                    confidence_levels = [c for c in confidence_levels if c >= 0.6]
                    if not confidence_levels:
                        confidence_levels = [0.7]

                    send_pos = None
                    for confidence in confidence_levels:
                        send_pos = self._locator.find_button_by_image(
                            "send_btn.png",
                            region=search_region,
                            confidence=confidence
                        )
                        if send_pos:
                            logger.info(f"图像识别成功 (confidence={confidence})")
                            break
                    if send_pos:
                        pyautogui.click(send_pos[0], send_pos[1])
                        logger.info(f"已点击 '发送' 按钮 (图像识别) @ {send_pos}")
                        send_clicked = True
                    else:
                        logger.info("方法1失败: 图像识别未找到发送按钮")

                # 方法2：基于评论输入框的相对定位（两点固定相对位置）
                if not send_clicked and rect and input_rect:
                    logger.info("尝试方法2: 输入框相对定位...")
                    input_height = input_rect.bottom - input_rect.top
                    rel_x_offset = get_config("ui_location.send_btn_input_x_offset", None)
                    rel_x_ratio = get_config("ui_location.send_btn_input_x_ratio", 1.0)
                    if rel_x_offset is None:
                        rel_x_offset = max(10, int(input_height * rel_x_ratio))
                    rel_y_offset = get_config("ui_location.send_btn_input_y_offset", 0)

                    send_x = input_rect.right + rel_x_offset
                    send_y = input_rect.top + max(1, input_height // 2) + rel_y_offset
                    logger.info(
                        "输入框相对坐标: "
                        f"input=({input_rect.left},{input_rect.top})-({input_rect.right},{input_rect.bottom}), "
                        f"send=({send_x},{send_y})"
                    )

                    if rect.left <= send_x <= rect.right and rect.top <= send_y <= rect.bottom:
                        pyautogui.click(send_x, send_y)
                        logger.info(f"已点击 '发送' 按钮 (输入框相对: {send_x}, {send_y})")
                        send_clicked = True
                    else:
                        logger.warning(f"输入框相对坐标 ({send_x}, {send_y}) 超出窗口范围，跳过点击")

                # 方法2b：基于“...”按钮的相对定位
                if not send_clicked and rect and dots_pos:
                    logger.info("尝试方法2b: '...' 相对定位...")
                    dots_x_offset = get_config("ui_location.send_btn_dots_x_offset", None)
                    dots_y_offset = get_config("ui_location.send_btn_dots_y_offset", None)
                    if dots_x_offset is None or dots_y_offset is None:
                        logger.info("未配置 '...' 相对偏移，跳过")
                    else:
                        send_x = dots_pos[0] + int(dots_x_offset)
                        send_y = dots_pos[1] + int(dots_y_offset)
                        logger.info(
                            f"'...' 相对坐标: dots=({dots_pos[0]},{dots_pos[1]}), send=({send_x},{send_y})"
                        )
                        if rect.left <= send_x <= rect.right and rect.top <= send_y <= rect.bottom:
                            pyautogui.click(send_x, send_y)
                            logger.info(f"已点击 '发送' 按钮 ('...' 相对: {send_x}, {send_y})")
                            send_clicked = True
                        else:
                            logger.warning(f"'...' 相对坐标 ({send_x}, {send_y}) 超出窗口范围，跳过点击")

                # 方法3：后备坐标（仅当坐标在窗口内时才点击）
                if not send_clicked and rect:
                    logger.info("尝试方法3: 后备坐标...")
                    send_x_offset = get_config("ui_location.send_btn_x_offset", 80)
                    send_x = rect.right - send_x_offset
                    if input_rect:
                        send_y = input_rect.top + max(1, (input_rect.bottom - input_rect.top) // 2)
                        logger.info(f"后备坐标基于输入框: send_y={send_y}")
                    else:
                        win_height = rect.bottom - rect.top
                        send_y_ratio = get_config("ui_location.send_btn_y_ratio", 0.52)
                        send_y = rect.top + int(win_height * send_y_ratio)
                    logger.info(f"后备坐标计算: send_x={send_x}, send_y={send_y}, 窗口范围=({rect.left},{rect.top})-({rect.right},{rect.bottom})")

                    # 检查坐标是否在朋友圈窗口范围内
                    if rect.left <= send_x <= rect.right and rect.top <= send_y <= rect.bottom:
                        pyautogui.click(send_x, send_y)
                        logger.info(f"已点击 '发送' 按钮 (坐标后备: {send_x}, {send_y})")
                        send_clicked = True
                    else:
                        logger.warning(f"后备坐标 ({send_x}, {send_y}) 超出窗口范围，跳过点击")

                if send_clicked:
                    logger.info("=== 发送按钮点击成功 ===")
                    # 点击发送按钮后等待随机 5-8 秒
                    wait_time = random.uniform(5, 8)
                    logger.info(f"等待 {wait_time:.1f} 秒后进行下一步操作")
                    time.sleep(wait_time)
                else:
                    logger.warning("=== 三种方法都失败，未能点击发送按钮 ===")

            # 11. 关闭朋友圈窗口（有链接时仅在发送成功后关闭）
            should_close = (not product_link) or send_clicked
            if should_close:
                time.sleep(1)
                if rect:
                    close_offset = get_config("ui_location.close_btn_offset", 15)
                    close_x = rect.right - close_offset
                    close_y = rect.top + close_offset
                    pyautogui.click(close_x, close_y)
                    logger.debug(f"已点击关闭按钮 ({close_x}, {close_y})")
            else:
                logger.warning("产品链接未发送成功，保留朋友圈窗口")

            return True

        except Exception as e:
            logger.warning(f"查看朋友圈失败: {e}")
            return True

    # ========================================================
    # 取消编辑
    # ========================================================

    def cancel_compose(
        self,
        window: auto.WindowControl
    ) -> bool:
        """
        取消编辑

        Args:
            window: 编辑窗口

        Returns:
            是否成功
        """
        if self._wechat_version == "v4":
            return self._cancel_compose_v4(window)
        else:
            return self._cancel_compose_v3(window)

    def _cancel_compose_v4(self, sns_window: auto.WindowControl) -> bool:
        """微信 4.0 取消编辑"""
        if not sns_window or not sns_window.Exists(0, 0):
            return True

        # 查找取消按钮
        cancel_btn = sns_window.Control(
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
        sns_window.SendKeys("{Escape}")
        time.sleep(SHORT_DELAY)

        return True

    def _cancel_compose_v3(self, compose_window: auto.WindowControl) -> bool:
        """微信 3.x 取消编辑"""
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


# ============================================================
# 便捷函数
# ============================================================

def create_publish_handler(
    wechat_version: Optional[str] = None,
    locator=None
) -> PublishHandler:
    """
    创建发布处理器实例

    Args:
        wechat_version: 微信版本
        locator: 元素定位器实例

    Returns:
        PublishHandler 实例
    """
    return PublishHandler(wechat_version, locator)
