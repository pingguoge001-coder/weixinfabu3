"""
朋友圈窗口处理模块

功能:
- 打开朋友圈窗口（支持微信 3.x 和 4.0）
- 关闭朋友圈窗口
- 检测朋友圈窗口状态
- 调整窗口位置和大小
"""

import time
import logging
from typing import Optional

import pyautogui
import uiautomation as auto

from services.config_manager import get_config

logger = logging.getLogger(__name__)


# ============================================================
# 配置常量
# ============================================================

# 操作间隔时间（秒）
STEP_DELAY = 0.8
SHORT_DELAY = 0.3
PAGE_LOAD_DELAY = 2.0

# 超时设置（秒）
ELEMENT_TIMEOUT = 10

# 窗口类名
MOMENTS_WINDOW_CLASS_V3 = "SnsWnd"
SNS_WINDOW_CLASS_V4 = "mmui::SNSWindow"
MAIN_WINDOW_CLASS_V4 = "mmui::MainWindow"


class WindowHandler:
    """朋友圈窗口处理器"""

    def __init__(self, wechat_controller):
        """
        初始化窗口处理器

        Args:
            wechat_controller: 微信控制器实例
        """
        self._controller = wechat_controller
        self._moments_window: Optional[auto.WindowControl] = None
        self._sns_window: Optional[auto.WindowControl] = None
        self._wechat_version: Optional[str] = None

    @property
    def moments_window(self) -> Optional[auto.WindowControl]:
        """获取朋友圈窗口"""
        return self._moments_window

    @property
    def sns_window(self) -> Optional[auto.WindowControl]:
        """获取朋友圈独立窗口（4.0）"""
        return self._sns_window

    @property
    def wechat_version(self) -> Optional[str]:
        """获取微信版本"""
        return self._wechat_version

    # ========================================================
    # 窗口导航方法
    # ========================================================

    def navigate_to_moment(self) -> bool:
        """
        导航到朋友圈 (支持 3.x 和 4.0)

        Returns:
            是否成功
        """
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
        existing_sns = self._controller.find_moments_window(timeout=2)
        if existing_sns:
            # 直接使用已存在的窗口，不再关闭
            logger.info("使用已存在的朋友圈窗口 (v4)")
            self._attach_sns_window(existing_sns, log_entry=False)
            return True

        prefer_coord = get_config("ui_location.moments_button.prefer_coord", True)
        if prefer_coord and self._has_moments_button_coord_config():
            if self._click_moments_button_by_coord(main_window):
                fast_timeout = get_config("automation.timeout.moments_window_fast", 2)
                sns_window = self._controller.find_moments_window(timeout=fast_timeout)
                if sns_window:
                    self._attach_sns_window(sns_window)
                    return True
                logger.debug("坐标点击未打开朋友圈窗口，回退到控件查找")

        # 4.0 中朋友圈按钮在左侧导航栏
        moment_btn = main_window.ButtonControl(
            searchDepth=10,
            Name="朋友圈"
        )

        btn_timeout = get_config("automation.timeout.moments_button", ELEMENT_TIMEOUT)
        if not moment_btn.Exists(btn_timeout, 1):
            # 尝试其他定位方式
            moment_btn = main_window.Control(
                searchDepth=10,
                Name="朋友圈",
                ClassName="mmui::XTabBarItem"
            )

        if not moment_btn.Exists(btn_timeout, 1):
            logger.warning("未找到'朋友圈'导航按钮 (v4)，尝试坐标点击")
            if not self._click_moments_button_by_coord(main_window):
                logger.error("坐标点击'朋友圈'失败 (v4)")
                return False
            time.sleep(PAGE_LOAD_DELAY)
        else:
            # 双击打开独立朋友圈窗口
            moment_btn.DoubleClick()
            logger.debug("已双击'朋友圈'导航按钮 (v4)")
            time.sleep(PAGE_LOAD_DELAY)

        # 等待独立朋友圈窗口出现
        self._sns_window = self._controller.find_moments_window(timeout=ELEMENT_TIMEOUT)
        if not self._sns_window:
            logger.error("朋友圈窗口未打开 (v4)")
            return False

        self._attach_sns_window(self._sns_window)
        return True

    def _attach_sns_window(self, window: auto.WindowControl, log_entry: bool = True) -> None:
        self._sns_window = window
        self._sns_window.SetFocus()
        self._moments_window = self._sns_window
        if log_entry:
            logger.info("已进入朋友圈 (v4)")
        self.adjust_sns_window_position()

    def _has_moments_button_coord_config(self) -> bool:
        abs_x = get_config("ui_location.moments_button.absolute_x", None)
        abs_y = get_config("ui_location.moments_button.absolute_y", None)
        if isinstance(abs_x, int) and abs_x > 0 and isinstance(abs_y, int) and abs_y > 0:
            return True

        x_off = get_config("ui_location.moments_button.x_offset", None)
        y_off = get_config("ui_location.moments_button.y_offset", None)
        return (
            isinstance(x_off, int)
            and x_off > 0
            and isinstance(y_off, int)
            and y_off > 0
        )

    def _click_moments_button_by_coord(self, main_window: auto.WindowControl) -> bool:
        """使用坐标点击左侧导航栏的朋友圈入口"""
        try:
            self._controller.activate_window(main_window)

            rect = self._controller.get_window_rect(main_window)
            if not rect:
                logger.error("无法获取主窗口位置，坐标点击失败")
                return False

            abs_x = get_config("ui_location.moments_button.absolute_x", None)
            abs_y = get_config("ui_location.moments_button.absolute_y", None)
            x_off = get_config("ui_location.moments_button.x_offset", None)
            y_off = get_config("ui_location.moments_button.y_offset", None)
            double_click = get_config("ui_location.moments_button.double_click", True)

            x = None
            y = None
            if isinstance(abs_x, int) and isinstance(abs_y, int) and abs_x > 0 and abs_y > 0:
                x, y = abs_x, abs_y
            elif isinstance(x_off, int) and isinstance(y_off, int) and x_off > 0 and y_off > 0:
                x, y = rect.left + x_off, rect.top + y_off

            if x is None or y is None:
                logger.error("坐标未配置，请设置 ui_location.moments_button")
                return False

            logger.info(f"使用坐标点击朋友圈入口: ({x}, {y})")
            if double_click:
                pyautogui.doubleClick(x, y, interval=0.1)
            else:
                pyautogui.click(x, y)
            return True

        except Exception as e:
            logger.error(f"坐标点击朋友圈入口异常: {e}")
            return False

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
            ClassName=MOMENTS_WINDOW_CLASS_V3
        )

        if not self._moments_window.Exists(ELEMENT_TIMEOUT, 1):
            logger.error("朋友圈窗口未出现 (v3)")
            return False

        logger.info("已进入朋友圈 (v3)")
        return True

    # ========================================================
    # 窗口调整方法
    # ========================================================

    def adjust_sns_window_position(self) -> bool:
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

    # ========================================================
    # 窗口关闭方法
    # ========================================================

    def return_to_main(self) -> bool:
        """
        返回主界面

        Returns:
            是否成功
        """
        if self._wechat_version == "v4":
            return self._return_to_main_v4()
        else:
            return self._return_to_main_v3()

    def _return_to_main_v4(self) -> bool:
        """微信 4.0 返回主界面 - 关闭朋友圈窗口"""
        window = self._sns_window or self._moments_window
        if not window or not window.Exists(0, 0):
            window = self._controller.find_moments_window(timeout=2)

        if window and window.Exists(0, 0):
            try:
                window.SetFocus()
            except Exception:
                pass

            abs_x = get_config("ui_location.moments_close_button.absolute_x", None)
            abs_y = get_config("ui_location.moments_close_button.absolute_y", None)
            x_off = get_config("ui_location.moments_close_button.x_offset", None)
            y_off = get_config("ui_location.moments_close_button.y_offset", None)

            x = None
            y = None
            if isinstance(abs_x, int) and isinstance(abs_y, int) and abs_x > 0 and abs_y > 0:
                x, y = abs_x, abs_y
            else:
                rect = window.BoundingRectangle
                if (
                    rect
                    and isinstance(x_off, int)
                    and isinstance(y_off, int)
                    and x_off > 0
                    and y_off > 0
                ):
                    x, y = rect.left + x_off, rect.top + y_off

            if x is None or y is None:
                logger.warning("未配置朋友圈关闭按钮坐标，跳过关闭 (v4)")
            else:
                pyautogui.click(x, y)
                logger.debug(f"已点击朋友圈关闭按钮 (v4): {x}, {y}")
                time.sleep(SHORT_DELAY)

        # 确认返回到主窗口
        main_window = self._controller.get_main_window()
        if main_window and main_window.Exists(0, 0):
            self._controller.activate_window(main_window)
            logger.debug("已返回主界面 (v4)")
            return True

        return False

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

    # ========================================================
    # 窗口状态检测
    # ========================================================

    def is_moment_window_open(self) -> bool:
        """检查朋友圈窗口是否打开"""
        window = self._controller.find_moments_window(timeout=2)
        return window is not None


# ============================================================
# 便捷函数
# ============================================================

def create_window_handler(wechat_controller) -> WindowHandler:
    """
    创建窗口处理器实例

    Args:
        wechat_controller: 微信控制器实例

    Returns:
        WindowHandler 实例
    """
    return WindowHandler(wechat_controller)
