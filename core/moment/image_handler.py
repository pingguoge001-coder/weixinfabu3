"""
朋友圈图片处理模块

功能:
- 添加图片到朋友圈
- 文件对话框操作
- 图片验证和过滤
- 支持微信 3.x 和 4.0
"""

import time
import logging
from pathlib import Path
from typing import List, Dict, Optional

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
LONG_DELAY = 1.5

# 朋友圈限制
MAX_IMAGES = 9

# 微信 4.0 UI 元素类名
ADD_IMAGE_CELL_CLASS = "mmui::PublishImageAddGridCell"
FILE_DIALOG_CLASS = "#32770"
FILE_DIALOG_TITLES = ["选择文件", "打开"]


class ImageHandler:
    """朋友圈图片处理器"""

    def __init__(
        self,
        clipboard_manager,
        wechat_version: Optional[str] = None,
        folder_path: Optional[str] = None
    ):
        """
        初始化图片处理器

        Args:
            clipboard_manager: 剪贴板管理器实例
            wechat_version: 微信版本 ("v3" 或 "v4")
            folder_path: 图片所在文件夹路径（用于文件对话框导航）
        """
        self._clipboard = clipboard_manager
        self._wechat_version = wechat_version
        self._folder_path = folder_path

    def set_version(self, version: str):
        """设置微信版本"""
        self._wechat_version = version

    def set_folder_path(self, folder_path: Optional[str]):
        """设置图片文件夹路径"""
        self._folder_path = folder_path

    def _navigate_to_folder(self, file_dialog: auto.WindowControl, folder_path: str) -> None:
        path_obj = Path(folder_path)
        if not path_obj.exists():
            logger.debug(f"文件夹不存在，跳过导航: {folder_path}")
            return

        dialog_step_wait = get_config("automation.wait.moment_upload_dialog_step", 1.0)
        dialog_post_enter_wait = get_config("automation.wait.moment_upload_dialog_post_enter", 2.0)

        try:
            file_dialog.SetFocus()
            time.sleep(dialog_step_wait)
        except Exception:
            pass

        def paste_and_enter() -> None:
            pyperclip.copy(str(path_obj))
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(dialog_step_wait)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(dialog_step_wait)
            pyautogui.press('enter')
            time.sleep(dialog_post_enter_wait)

        try:
            pyautogui.hotkey('alt', 'd')
            time.sleep(dialog_step_wait)
            paste_and_enter()
        except Exception as e:
            logger.debug(f"地址栏导航失败，继续尝试: {folder_path}, 错误: {e}")

            try:
                pyautogui.hotkey('ctrl', 'l')
                time.sleep(dialog_step_wait)
                paste_and_enter()
            except Exception as e2:
                logger.debug(f"导航到文件夹失败，继续使用默认目录: {folder_path}, 错误: {e2}")

    def _find_file_dialog(self, timeout: float = 5.0) -> Optional[auto.WindowControl]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            for title in FILE_DIALOG_TITLES:
                dialog = auto.WindowControl(searchDepth=2, Name=title)
                if dialog.Exists(0.2, 0):
                    return dialog
            dialog = auto.WindowControl(searchDepth=2, ClassName=FILE_DIALOG_CLASS)
            if dialog.Exists(0.2, 0):
                return dialog
            time.sleep(0.2)
        return None


    # ========================================================
    # 图片添加方法
    # ========================================================

    def add_images(
        self,
        image_paths: List[str],
        window: auto.WindowControl
    ) -> Dict[str, any]:
        """
        添加图片

        Args:
            image_paths: 图片路径列表
            window: 朋友圈窗口控件

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
            return self._add_images_v4(image_paths, window)
        else:
            return self._add_images_v3(image_paths, window)

    def _add_images_v4(
        self,
        image_paths: List[str],
        sns_window: auto.WindowControl
    ) -> Dict[str, any]:
        """
        微信 4.0 添加图片

        一次性添加所有图片：在文件名输入框输入 "file1" "file2" "file3" 格式
        """
        result = {"success": False, "added": 0, "failed": 0}

        if not sns_window or not sns_window.Exists(0, 0):
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
            file_dialog = self._find_file_dialog(timeout=3.0)

            if not file_dialog:
                # 查找"添加图片"按钮
                add_btn = sns_window.ListItemControl(
                    searchDepth=15,
                    Name="添加图片",
                    ClassName=ADD_IMAGE_CELL_CLASS
                )

                if not add_btn.Exists(5, 1):
                    add_btn = sns_window.ListItemControl(
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
                file_dialog = self._find_file_dialog(timeout=5.0)

            if not file_dialog:
                logger.error("文件对话框未出现 (v4)")
                return result

            logger.debug("文件对话框已打开")
            file_dialog.SetFocus()
            time.sleep(SHORT_DELAY)
            dialog_step_wait = get_config("automation.wait.moment_upload_dialog_step", 1.0)
            logger.info(f"file dialog opened, wait {dialog_step_wait}s before navigation")
            time.sleep(dialog_step_wait)

            # 导航到图片所在文件夹（如果指定了路径）
            if self._folder_path:
                logger.info(f"navigate to folder: {self._folder_path}")
                self._navigate_to_folder(file_dialog, self._folder_path)

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

    def _add_images_v3(
        self,
        image_paths: List[str],
        compose_window: auto.WindowControl
    ) -> Dict[str, any]:
        """
        微信 3.x 添加图片

        通过剪贴板粘贴图片
        """
        result = {"success": False, "added": 0, "failed": 0}

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


# ============================================================
# 便捷函数
# ============================================================

def create_image_handler(
    clipboard_manager,
    wechat_version: Optional[str] = None,
    folder_path: Optional[str] = None
) -> ImageHandler:
    """
    创建图片处理器实例

    Args:
        clipboard_manager: 剪贴板管理器实例
        wechat_version: 微信版本
        folder_path: 图片文件夹路径

    Returns:
        ImageHandler 实例
    """
    return ImageHandler(clipboard_manager, wechat_version, folder_path)
