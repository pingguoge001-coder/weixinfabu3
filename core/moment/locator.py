"""
朋友圈元素定位模块

功能:
- 混合定位策略（UI自动化 + 图像识别 + 坐标后备）
- 图像识别辅助定位
- 相对位置计算
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import re

import pyautogui
import uiautomation as auto
from PIL import Image, ImageDraw

from services.config_manager import get_config

logger = logging.getLogger(__name__)


def get_base_path() -> Path:
    """
    获取程序基础路径
    - 打包后: 返回 _MEIPASS 目录（PyInstaller 解压资源的临时目录）
    - 开发时: 返回项目根目录
    """
    if getattr(sys, 'frozen', False):
        # 打包后运行：优先可执行文件目录，其次 _MEIPASS
        exe_dir = Path(sys.executable).parent
        internal_dir = exe_dir / "_internal"
        meipass_dir = Path(getattr(sys, "_MEIPASS", exe_dir))
        candidates = [exe_dir, internal_dir, meipass_dir]
        for base in candidates:
            if (base / "data" / "templates").exists():
                return base
        return candidates[0]
    # 开发环境，从当前文件往上找到项目根目录
    return Path(__file__).parent.parent.parent


# 模板图片目录
TEMPLATE_DIR = get_base_path() / "data" / "templates"


class ElementLocator:
    """朋友圈元素定位器"""

    def __init__(self, sns_window: Optional[auto.WindowControl] = None):
        """
        初始化元素定位器

        Args:
            sns_window: 朋友圈窗口控件
        """
        self.sns_window = sns_window

    def set_window(self, sns_window: auto.WindowControl):
        """设置朋友圈窗口"""
        self.sns_window = sns_window

    # ========================================================
    # 图像识别方法
    # ========================================================

    def find_button_by_image(
        self,
        template_name: str,
        region: Optional[tuple] = None,
        confidence: float = 0.8
    ) -> Optional[Tuple[int, int]]:
        """
        使用图像识别查找按钮

        Args:
            template_name: 模板图片名称（不含路径）
            region: 搜索区域 (left, top, width, height)，None 表示全屏
            confidence: 匹配置信度 (0.0-1.0)

        Returns:
            (center_x, center_y) 或 None
        """
        template_path = TEMPLATE_DIR / template_name

        if not template_path.exists():
            logger.warning(f"模板图片不存在: {template_path}")
            return None

        safe_region = None
        if region:
            try:
                safe_region = self._clamp_region(region)
                if not safe_region:
                    logger.warning(f"搜索区域无效或超出屏幕: {region}")
                    return None
                if safe_region != region:
                    logger.debug(f"搜索区域已裁剪: {region} -> {safe_region}")
            except Exception as clamp_err:
                logger.warning(f"裁剪搜索区域失败: {clamp_err}")
                safe_region = region

        try:
            location = pyautogui.locateOnScreen(
                str(template_path),
                region=safe_region,
                confidence=confidence
            )
            if location:
                center = pyautogui.center(location)
                logger.debug(f"图像识别成功: {template_name} @ ({center.x}, {center.y})")
                return (center.x, center.y)
        except Exception as e:
            logger.warning(f"图像识别失败: {type(e).__name__} {repr(e)}")

        return None

    @staticmethod
    def _clamp_region(region: tuple) -> Optional[tuple]:
        """将搜索区域裁剪到主屏幕范围内，避免截图异常。"""
        try:
            left, top, width, height = region
        except Exception:
            return None

        if width <= 0 or height <= 0:
            return None

        screen_w, screen_h = pyautogui.size()
        right = left + width
        bottom = top + height

        left = max(0, left)
        top = max(0, top)
        right = min(screen_w, right)
        bottom = min(screen_h, bottom)

        new_width = right - left
        new_height = bottom - top
        if new_width <= 0 or new_height <= 0:
            return None

        return (left, top, new_width, new_height)

    def find_button_by_image_multi_confidence(
        self,
        template_name: str,
        region: Optional[tuple] = None
    ) -> Optional[Tuple[int, int]]:
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
            pos = self.find_button_by_image(template_name, region, confidence)
            if pos:
                logger.debug(f"图像识别成功 (confidence={confidence}): {template_name}")
                return pos

        logger.warning(f"图像识别失败 (尝试了 {confidence_levels}): {template_name}")
        return None

    # ========================================================
    # 混合定位方法
    # ========================================================

    def _find_right_edge_button_by_row(self, window_rect, row_center_y: int):
        """Find a right-edge button near the given row center Y."""
        if not self.sns_window or not window_rect:
            return None

        band = get_config("ui_location.dots_row_band", 40)
        right_margin = get_config("ui_location.dots_right_margin", 90)
        candidates = []

        def collect(ctrl, depth=0):
            if depth > 12:
                return
            try:
                if ctrl.ControlTypeName in (
                    "ButtonControl",
                    "ImageControl",
                    "TextControl",
                    "HyperlinkControl",
                ):
                    rect = ctrl.BoundingRectangle
                    if rect:
                        center_y = (rect.top + rect.bottom) // 2
                        if abs(center_y - row_center_y) <= band and (window_rect.right - rect.right) <= right_margin:
                            candidates.append(rect)
                for child in ctrl.GetChildren():
                    collect(child, depth + 1)
            except Exception:
                pass

        collect(self.sns_window)
        if candidates:
            rect = max(candidates, key=lambda r: r.right)
            return ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)

        return None

    def _debug_save_region(self, label: str, region: tuple, match=None) -> None:
        """Save debug screenshot for a search region."""
        if not get_config("ui_location.dots_debug_save", False):
            return

        safe_region = self._clamp_region(region)
        if not safe_region:
            return

        debug_dir = Path(get_config("ui_location.dots_debug_dir", "./data/debug"))
        debug_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{label}_{timestamp}_{safe_region[0]}_{safe_region[1]}_{safe_region[2]}_{safe_region[3]}.png"
        filepath = debug_dir / filename

        try:
            img = pyautogui.screenshot(region=safe_region)
            if match:
                try:
                    left = int(match.left - safe_region[0])
                    top = int(match.top - safe_region[1])
                    right = left + int(match.width)
                    bottom = top + int(match.height)
                    draw = ImageDraw.Draw(img)
                    draw.rectangle([left, top, right, bottom], outline="red", width=2)
                except Exception:
                    pass
            img.save(str(filepath))
        except Exception:
            pass

    def find_dots_by_image(self) -> Optional[Tuple[int, int]]:
        """Find the '...' button via template matching."""
        if not self.sns_window or not self.sns_window.Exists(0, 0):
            return None

        rect = self.sns_window.BoundingRectangle
        if not rect:
            return None

        template_path = TEMPLATE_DIR / "dots_btn.png"
        if not template_path.exists():
            return None

        try:
            template_img = Image.open(template_path)
        except Exception as e:
            logger.debug("Failed to load dots template: %s", e)
            return None

        # Prefer bottom-right area (comment bar row), then fall back to right strip.
        regions = []

        box_w = get_config("ui_location.dots_image_bottom_box_width", 260)
        box_h = get_config("ui_location.dots_image_bottom_box_height", 220)
        box_right_pad = get_config("ui_location.dots_image_bottom_box_right_pad", 40)
        box_bottom_pad = get_config("ui_location.dots_image_bottom_box_bottom_pad", 120)
        bottom_box = (
            rect.right - int(box_right_pad) - int(box_w),
            rect.bottom - int(box_bottom_pad) - int(box_h),
            int(box_w),
            int(box_h),
        )
        regions.append(bottom_box)

        right_strip = get_config("ui_location.dots_image_search_width", 140)
        top_pad = get_config("ui_location.dots_image_search_top_pad", 120)
        bottom_pad = get_config("ui_location.dots_image_search_bottom_pad", 160)
        right_strip_region = (
            rect.right - int(right_strip),
            rect.top + int(top_pad),
            int(right_strip),
            max(10, rect.bottom - rect.top - int(top_pad) - int(bottom_pad)),
        )
        regions.append(right_strip_region)

        scales = get_config("ui_location.dots_btn_scales", [1.0, 1.25, 1.5])
        scales = [s for s in scales if isinstance(s, (int, float)) and s > 0]
        if not scales:
            scales = [1.0]

        confidence_levels = get_config(
            "ui_location.dots_btn_confidence_levels",
            [0.8, 0.6, 0.4]
        )
        confidence_levels = [
            c for c in confidence_levels if isinstance(c, (int, float)) and c > 0
        ]
        if not confidence_levels:
            confidence_levels = [0.6]

        grayscale = bool(get_config("ui_location.dots_btn_grayscale", True))
        offset_x = int(get_config("ui_location.dots_btn_click_offset_x", 0))
        offset_y = int(get_config("ui_location.dots_btn_click_offset_y", 0))
        use_all = bool(get_config("ui_location.dots_btn_use_all_matches", True))

        for region in regions:
            region = self._clamp_region(region)
            if not region:
                continue
            self._debug_save_region("dots_region", region)
            for confidence in confidence_levels:
                for scale in scales:
                    try:
                        if scale == 1.0:
                            img = template_img
                        else:
                            new_w = max(1, int(template_img.width * scale))
                            new_h = max(1, int(template_img.height * scale))
                            img = template_img.resize((new_w, new_h), Image.LANCZOS)
                        if use_all:
                            locations = list(
                                pyautogui.locateAllOnScreen(
                                    img,
                                    region=region,
                                    confidence=confidence,
                                    grayscale=grayscale,
                                )
                            )
                            if locations:
                                best = max(locations, key=lambda r: r.top)
                                self._debug_save_region("dots_match", region, match=best)
                                center = pyautogui.center(best)
                                return (center.x + offset_x, center.y + offset_y)

                        location = pyautogui.locateOnScreen(
                            img,
                            region=region,
                            confidence=confidence,
                            grayscale=grayscale,
                        )
                        if location:
                            self._debug_save_region("dots_match", region, match=location)
                            center = pyautogui.center(location)
                            return (center.x + offset_x, center.y + offset_y)
                    except Exception:
                        pass

        return None

    def find_dots_by_delete_btn(self) -> Optional[Tuple[int, int]]:
        """
        通过识别删除按钮（垃圾桶）来定位 "..." 按钮

        原理：删除按钮和 "..." 按钮在同一行
        - 找到删除按钮获取 Y 坐标
        - "..." 按钮的 X 坐标固定（距窗口右边 55px）

        Returns:
            (center_x, center_y) 或 None
        """
        if not self.sns_window or not self.sns_window.Exists(0, 0):
            return None

        rect = self.sns_window.BoundingRectangle
        if not rect:
            return None

        # 用图像识别找删除按钮
        template_path = TEMPLATE_DIR / "delete_btn.png"
        if not template_path.exists():
            logger.warning(f"删除按钮模板不存在: {template_path}")
            return None

        # 尝试不同置信度
        try:
            template_img = Image.open(template_path)
        except Exception as e:
            logger.warning("Failed to load delete button template: %s", e)
            return None

        scales = get_config("ui_location.delete_btn_scales", [1.0, 1.25, 1.5])
        scales = [s for s in scales if isinstance(s, (int, float)) and s > 0]
        if not scales:
            scales = [1.0]

        # Try confidence + scale to adapt to DPI.
        for confidence in [0.8, 0.7, 0.6, 0.5]:
            for scale in scales:
                try:
                    if scale == 1.0:
                        img = template_img
                    else:
                        new_w = max(1, int(template_img.width * scale))
                        new_h = max(1, int(template_img.height * scale))
                        img = template_img.resize((new_w, new_h), Image.LANCZOS)
                    location = pyautogui.locateOnScreen(img, confidence=confidence)
                    if location:
                        center = pyautogui.center(location)
                        # "..." X is fixed to right edge, Y aligns with delete button.
                        row_pos = self._find_right_edge_button_by_row(rect, center.y)
                        if row_pos:
                            logger.debug(f"Row button found near delete anchor @ {row_pos}")
                            return row_pos
                        dots_x_offset = get_config("ui_location.dots_btn_right_offset", 55)
                        dots_x = rect.right - dots_x_offset
                        dots_y = center.y
                        logger.debug(
                            f"Delete anchor found: delete=({center.x}, {center.y}), "
                            f"dots=({dots_x}, {dots_y}), scale={scale}"
                        )
                        return (dots_x, dots_y)
                except Exception as e:
                    logger.debug(
                        f"Delete button match failed (confidence={confidence}, scale={scale}): {e}"
                    )
        return None

    def find_dots_by_timestamp(self) -> Optional[Tuple[int, int]]:
        """
        通过时间戳控件相对定位 "..." 按钮
        时间戳格式: HH:MM, 昨天, X小时前, X分钟前 等

        Returns:
            (center_x, center_y) 或 None
        """
        if not self.sns_window or not self.sns_window.Exists(0, 0):
            return None

        rect = self.sns_window.BoundingRectangle
        if not rect:
            return None

        # 时间戳匹配模式
        time_patterns = [
            r'^\d{1,2}:\d{2}$',
            r'^\d{4}\u5e74\d{1,2}\u6708\d{1,2}\u65e5\s+\d{1,2}:\d{2}$',
            r'^\d{1,2}\u6708\d{1,2}\u65e5\s+\d{1,2}:\d{2}$',
            r'^\u6628\u5929$',
            r'^\u4eca\u5929$',
            r'^\d+\u5c0f\u65f6\u524d$',
            r'^\d+\u5c0f\u65f6\u4ee5\u524d$',
            r'^\d+\u5206\u949f\u524d$',
            r'^\d+\u5206\u949f\u4ee5\u524d$',
            r'^\d+\u5929\u524d$',
        ]

        def is_timestamp(text):
            if not text:
                return False
            text = text.strip()
            for p in time_patterns:
                if re.search(p, text):
                    return True
            return False

        # 遍历查找时间戳控件
        candidates = []

        def collect_timestamp_controls(ctrl, depth=0):
            if depth > 20:
                return
            try:
                if ctrl.ControlTypeName == 'TextControl' and is_timestamp(ctrl.Name):
                    ctrl_rect = ctrl.BoundingRectangle
                    if ctrl_rect and rect.top + 150 < ctrl_rect.top < rect.bottom - 60:
                        candidates.append(ctrl)
                for child in ctrl.GetChildren():
                    collect_timestamp_controls(child, depth + 1)
            except Exception:
                pass
        collect_timestamp_controls(self.sns_window)
        if candidates:
            candidates = [c for c in candidates if getattr(c, "BoundingRectangle", None)]
            timestamp_ctrl = max(candidates, key=lambda c: c.BoundingRectangle.top)
            ts_rect = timestamp_ctrl.BoundingRectangle
            right_offset = get_config("ui_location.dots_btn_right_offset", 55)
            dots_x = rect.right - right_offset
            dots_y = (ts_rect.top + ts_rect.bottom) // 2
            row_pos = self._find_right_edge_button_by_row(rect, dots_y)
            if row_pos:
                logger.debug(f"Row button found near timestamp @ {row_pos}")
                return row_pos
            logger.debug(f"Timestamp anchor found: '{timestamp_ctrl.Name}' @ ({dots_x}, {dots_y})")
            return (dots_x, dots_y)
        return None

    def find_dots_button_hybrid(self) -> Optional[Tuple[int, int]]:
        """
        混合定位策略查找 "..." 按钮
        优先级: 图片模板 > 删除按钮定位 > 时间戳相对定位 > 坐标后备

        Returns:
            (center_x, center_y) 或 None
        """
        if not self.sns_window or not self.sns_window.Exists(0, 0):
            return None

        rect = self.sns_window.BoundingRectangle

        # 1. 图片模板定位（高 DPI 兼容）
        pos = self.find_dots_by_image()
        if pos:
            return pos

        # 2. 通过删除按钮（垃圾桶）定位（最可靠，Y坐标随内容变化）
        pos = self.find_dots_by_delete_btn()
        if pos:
            return pos

        # 3. 时间戳相对定位
        pos = self.find_dots_by_timestamp()
        if pos:
            return pos

        # 4. 坐标后备（基于窗口位置计算）
        if rect:
            right_offset = get_config("ui_location.dots_btn_right_offset", 55)
            top_offset = get_config("ui_location.dots_btn_top_offset", 864)
            logger.debug(f"使用坐标后备: ({rect.right - right_offset}, {rect.top + top_offset})")
            return (rect.right - right_offset, rect.top + top_offset)

        return None


# ============================================================
# 便捷函数
# ============================================================

def create_locator(sns_window: Optional[auto.WindowControl] = None) -> ElementLocator:
    """
    创建元素定位器实例

    Args:
        sns_window: 朋友圈窗口控件

    Returns:
        ElementLocator 实例
    """
    return ElementLocator(sns_window)
