"""
微信导航操作模块

功能:
- 小程序窗口操作（查找、恢复、点击）
- 产品转发操作
- 转发对话框操作
"""

import os
import time
import ctypes
import logging
from typing import Optional, Tuple

import pyautogui
import pyperclip

from services.config_manager import get_config_manager
from models.enums import Channel


logger = logging.getLogger(__name__)


# ============================================================
# 导航操作器
# ============================================================

class NavigationOperator:
    """
    微信导航操作器

    负责小程序、转发等导航相关操作
    """

    def __init__(self):
        """初始化导航操作器"""
        self._config = get_config_manager()
        logger.debug("导航操作器初始化完成")

    def _get_miniprogram_config_key(self, channel: Channel = None) -> str:
        """
        根据渠道获取小程序配置键名

        Args:
            channel: 渠道类型

        Returns:
            配置键名（miniprogram 或 miniprogram_customer）
        """
        if channel == Channel.customer_group:
            return "miniprogram_customer"
        else:
            return "miniprogram"  # 代理群或默认

    # ========================================================
    # 小程序窗口操作
    # ========================================================

    def find_miniprogram_window(self) -> Optional[int]:
        """
        查找小程序窗口，返回窗口句柄

        Returns:
            窗口句柄，未找到返回 None
        """
        import win32gui
        import win32process

        result_hwnd = None

        def get_process_name(pid: int) -> str:
            try:
                import win32api
                import win32con

                handle = win32api.OpenProcess(
                    win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                    False,
                    pid,
                )
                try:
                    exe_path = win32process.GetModuleFileNameEx(handle, 0)
                    return os.path.basename(exe_path)
                finally:
                    win32api.CloseHandle(handle)
            except Exception:
                pass

            try:
                import ctypes.wintypes as wt

                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_QUERY_LIMITED_INFORMATION, False, pid
                )
                if not handle:
                    return ""
                try:
                    size = wt.DWORD(260)
                    buf = ctypes.create_unicode_buffer(size.value)
                    if ctypes.windll.kernel32.QueryFullProcessImageNameW(
                        handle, 0, buf, ctypes.byref(size)
                    ):
                        return os.path.basename(buf.value)
                finally:
                    ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                pass

            return ""

        def callback(hwnd, _):
            nonlocal result_hwnd
            if win32gui.IsWindowVisible(hwnd):
                try:
                    class_name = win32gui.GetClassName(hwnd)
                    if class_name == "Chrome_WidgetWin_0":
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        try:
                            proc_name = get_process_name(pid)
                            if proc_name.lower() == "wechatappex.exe":
                                result_hwnd = hwnd
                                return False  # 停止枚举
                        except:
                            pass
                except:
                    pass
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except:
            pass  # EnumWindows 在 callback 返回 False 时会抛异常，这是正常的

        if result_hwnd:
            logger.debug(f"找到小程序窗口: hwnd={result_hwnd}")
        else:
            logger.debug("未找到小程序窗口")

        return result_hwnd

    def restore_miniprogram_window(self, x: int, y: int) -> bool:
        """
        恢复小程序窗口位置并置顶（不改变大小）

        Args:
            x: 左上角 X 坐标
            y: 左上角 Y 坐标

        Returns:
            是否成功
        """
        import win32gui
        import win32con

        hwnd = self.find_miniprogram_window()
        if hwnd is None:
            logger.warning("未找到小程序窗口，无法恢复位置")
            return False

        try:
            user32 = ctypes.windll.user32

            # 获取当前窗口大小（保持不变）
            rect = win32gui.GetWindowRect(hwnd)
            current_width = rect[2] - rect[0]
            current_height = rect[3] - rect[1]

            # 恢复窗口（如果最小化）
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE

            # 设置窗口位置并置顶（保持原大小）
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                x, y, current_width, current_height,
                win32con.SWP_SHOWWINDOW
            )

            # 激活窗口到前台
            user32.SetForegroundWindow(hwnd)

            logger.info(f"小程序窗口已移动并置顶: 位置({x},{y}), 大小{current_width}x{current_height}（保持不变）")
            return True
        except Exception as e:
            logger.error(f"恢复小程序窗口失败: {e}")
            return False

    def cancel_miniprogram_topmost(self) -> bool:
        """
        取消小程序窗口置顶

        Returns:
            是否成功
        """
        import win32gui
        import win32con

        hwnd = self.find_miniprogram_window()
        if hwnd is None:
            logger.debug("未找到小程序窗口，无需取消置顶")
            return True

        try:
            # 获取当前窗口位置和大小
            rect = win32gui.GetWindowRect(hwnd)
            x, y = rect[0], rect[1]
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]

            # 取消置顶（使用 HWND_NOTOPMOST）
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_NOTOPMOST,
                x, y, width, height,
                win32con.SWP_SHOWWINDOW
            )

            logger.debug("小程序窗口已取消置顶")
            return True
        except Exception as e:
            logger.error(f"取消小程序窗口置顶失败: {e}")
            return False

    def get_miniprogram_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """
        获取小程序窗口位置和大小

        Returns:
            (x, y, width, height) 或 None
        """
        import win32gui

        hwnd = self.find_miniprogram_window()
        if hwnd is None:
            return None

        try:
            rect = win32gui.GetWindowRect(hwnd)
            x, y, x2, y2 = rect
            return (x, y, x2 - x, y2 - y)
        except:
            return None

    def click_miniprogram_button(self, x_offset: int, y_offset: int) -> bool:
        """
        点击小程序窗口内的按钮

        Args:
            x_offset: 相对于窗口左上角的X偏移
            y_offset: 相对于窗口左上角的Y偏移

        Returns:
            是否成功
        """
        rect = self.get_miniprogram_window_rect()
        if rect is None:
            logger.warning("未找到小程序窗口")
            return False

        win_x, win_y, _, _ = rect
        click_x = win_x + x_offset
        click_y = win_y + y_offset

        try:
            pyautogui.click(click_x, click_y)  # 小程序按钮坐标
            logger.debug(f"点击小程序按钮: ({click_x}, {click_y})")
            return True
        except Exception as e:
            logger.error(f"点击小程序按钮失败: {e}")
            return False

    def refresh_miniprogram(self, channel: Channel = None) -> bool:
        """
        刷新小程序（弹出窗口 -> 点击更多 -> 点击重新进入）

        Args:
            channel: 渠道类型（用于选择配置）

        Returns:
            是否成功
        """
        # 根据渠道获取配置
        config_key = self._get_miniprogram_config_key(channel)
        window_config = self._config.get(f"{config_key}.restore_window", {})
        buttons_config = self._config.get(f"{config_key}.buttons", {})

        # 1. 弹出小程序窗口（只调整位置，不改变大小）
        self.restore_miniprogram_window(
            window_config.get("x", 1493),
            window_config.get("y", 236)
        )
        time.sleep(3)  # 等待3秒

        # 2. 点击更多按钮（使用绝对坐标）
        more_btn = buttons_config.get("more", {})
        more_x = more_btn.get("absolute_x", 2150)
        more_y = more_btn.get("absolute_y", 323)
        try:
            pyautogui.click(more_x, more_y)  # 更多按钮坐标
            logger.debug(f"点击更多按钮: ({more_x}, {more_y})")
        except Exception as e:
            logger.error(f"点击更多按钮失败: {e}")
            return False
        time.sleep(3)  # 等待3秒

        # 3. 点击重新进入小程序（使用绝对坐标）
        reenter_btn = buttons_config.get("reenter", {})
        reenter_x = reenter_btn.get("absolute_x", 1871)
        reenter_y = reenter_btn.get("absolute_y", 835)
        try:
            pyautogui.click(reenter_x, reenter_y)  # 重新进入按钮坐标
            logger.debug(f"点击重新进入小程序: ({reenter_x}, {reenter_y})")
        except Exception as e:
            logger.error(f"点击重新进入小程序失败: {e}")
            return False
        time.sleep(3)  # 等待3秒

        # 4. 再次恢复小程序窗口位置（只调整位置，不改变大小）
        self.restore_miniprogram_window(
            window_config.get("x", 1493),
            window_config.get("y", 236)
        )
        time.sleep(3)  # 等待3秒

        # 5. 点击搜索按钮（使用绝对坐标）
        search_btn = buttons_config.get("search", {})
        search_x = search_btn.get("absolute_x", 2255)
        search_y = search_btn.get("absolute_y", 371)
        try:
            pyautogui.click(search_x, search_y)  # 搜索按钮坐标
            logger.debug(f"点击搜索按钮: ({search_x}, {search_y})")
        except Exception as e:
            logger.error(f"点击搜索按钮失败: {e}")
            return False
        time.sleep(3)  # 等待3秒

        logger.info("小程序刷新并点击搜索完成")
        return True

    # ========================================================
    # 转发对话框操作
    # ========================================================

    def find_forward_dialog(self) -> Optional[int]:
        """
        查找微信转发对话框

        Returns:
            窗口句柄，未找到返回 None
        """
        import win32gui

        result_hwnd = None

        def callback(hwnd, _):
            nonlocal result_hwnd
            if win32gui.IsWindowVisible(hwnd):
                try:
                    title = win32gui.GetWindowText(hwnd)
                    if '发送给' in title or '转发' in title:
                        result_hwnd = hwnd
                        return False
                except:
                    pass
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except:
            pass

        if result_hwnd:
            logger.debug(f"找到转发对话框: hwnd={result_hwnd}")

        return result_hwnd

    def forward_to_group(self, group_name: str) -> bool:
        """
        在转发对话框中选择群聊并发送

        Args:
            group_name: 群聊名称

        Returns:
            是否成功
        """
        import win32gui
        import win32con

        pyautogui.FAILSAFE = False

        # 获取配置
        forward_config = self._config.get("forward_dialog", {})
        group_option = forward_config.get("group_option", {})
        send_button = forward_config.get("send_button", {})

        # 等待转发对话框出现
        time.sleep(3)  # 等待3秒
        hwnd = self.find_forward_dialog()
        if hwnd is None:
            logger.error("未找到转发对话框")
            return False

        # 激活对话框
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(3)  # 等待3秒

        # 10. 输入群聊名称（对话框打开后光标自动在搜索框）
        pyperclip.copy(group_name)
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(3)  # 等待3秒

        # 获取对话框位置
        rect = win32gui.GetWindowRect(hwnd)
        dialog_x, dialog_y = rect[0], rect[1]

        # 11. 点击群聊选项（支持绝对坐标或对话框偏移坐标）
        if "absolute_x" in group_option and "absolute_y" in group_option:
            group_x = group_option.get("absolute_x")
            group_y = group_option.get("absolute_y")
        else:
            group_x = dialog_x + group_option.get("x_offset", 150)
            group_y = dialog_y + group_option.get("y_offset", 180)
        pyautogui.click(group_x, group_y)  # 群聊选项坐标
        logger.debug(f"点击群聊选项: ({group_x}, {group_y})")
        time.sleep(3)  # 等待3秒

        # 12. 点击发送按钮（支持绝对坐标或对话框偏移坐标）
        if "absolute_x" in send_button and "absolute_y" in send_button:
            send_x = send_button.get("absolute_x")
            send_y = send_button.get("absolute_y")
        else:
            send_x = dialog_x + send_button.get("x_offset", 663)
            send_y = dialog_y + send_button.get("y_offset", 778)
        pyautogui.click(send_x, send_y)  # 发送按钮坐标
        logger.debug(f"点击发送按钮: ({send_x}, {send_y})")
        time.sleep(3)  # 等待3秒

        logger.info(f"已转发到群聊: {group_name}")
        return True

    def open_product_forward(self, content_code: str, group_name: str = None, channel: Channel = None) -> bool:
        """
        打开产品转发页面并转发到群聊（完整流程）

        Args:
            content_code: 文案编号（如 F00619，前4位是产品编号）
            group_name: 要转发到的群聊名称（可选，如果提供则执行完整转发流程）
            channel: 渠道类型（用于选择配置）

        Returns:
            是否成功
        """
        pyautogui.FAILSAFE = False

        # 提取产品编号（前4位）
        product_code = content_code[:4] if len(content_code) >= 4 else content_code
        logger.info(f"产品编号: {product_code}, 渠道: {channel.value if channel else '默认'}")

        # 根据渠道获取配置
        config_key = self._get_miniprogram_config_key(channel)
        buttons_config = self._config.get(f"{config_key}.buttons", {})

        # 1-5. 刷新小程序并点击搜索
        if not self.refresh_miniprogram(channel):
            return False
        time.sleep(3)  # 等待3秒

        # 6. 输入产品编号
        pyperclip.copy(product_code)
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(3)  # 等待3秒

        # 7. 按 Enter 搜索
        pyautogui.press('enter')
        time.sleep(3)  # 等待3秒

        # 7.1 重新激活小程序窗口（防止焦点丢失）
        window_config = self._config.get(f"{config_key}.restore_window", {})
        self.restore_miniprogram_window(
            window_config.get("x", 1493),
            window_config.get("y", 236)
        )
        time.sleep(0.5)

        # 8. 点击产品链接（使用绝对坐标）
        product_btn = buttons_config.get("product", {})
        product_x = product_btn.get("absolute_x", 1950)
        product_y = product_btn.get("absolute_y", 554)
        try:
            pyautogui.click(product_x, product_y)  # 产品链接坐标
            logger.debug(f"点击产品链接: ({product_x}, {product_y})")
        except Exception as e:
            logger.error(f"点击产品链接失败: {e}")
            return False
        time.sleep(3)  # 等待3秒

        # 9. 点击转发按钮（使用绝对坐标）
        forward_btn = buttons_config.get("forward", {})
        forward_x = forward_btn.get("absolute_x", 2177)
        forward_y = forward_btn.get("absolute_y", 1110)
        try:
            pyautogui.click(forward_x, forward_y)  # 转发按钮坐标
            logger.debug(f"点击转发按钮: ({forward_x}, {forward_y})")
        except Exception as e:
            logger.error(f"点击转发按钮失败: {e}")
            return False
        time.sleep(3)  # 等待3秒

        logger.info(f"产品 {product_code} 转发页面已打开")

        # 如果提供了群聊名称，执行转发操作
        if group_name:
            time.sleep(3)  # 等待3秒
            result = self.forward_to_group(group_name)
            # 流程完成后取消小程序窗口置顶
            self.cancel_miniprogram_topmost()
            return result

        # 流程完成后取消小程序窗口置顶
        self.cancel_miniprogram_topmost()
        return True
