"""
剪贴板安全管理器

提供剪贴板的安全操作，包括备份、恢复、设置和验证功能。
使用 pywin32 的 win32clipboard 模块进行底层操作。
"""

import io
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum

try:
    import win32clipboard
    import win32con
except ImportError:
    raise ImportError("请安装 pywin32: pip install pywin32")

try:
    from PIL import Image
except ImportError:
    Image = None  # PIL 是可选的

logger = logging.getLogger(__name__)


class ClipboardFormat(Enum):
    """剪贴板格式枚举"""
    TEXT = win32con.CF_UNICODETEXT
    BITMAP = win32con.CF_DIB
    FILES = win32con.CF_HDROP
    HTML = 49461  # HTML Format (需要注册)
    UNKNOWN = 0


@dataclass
class ClipboardContent:
    """剪贴板内容"""
    format: ClipboardFormat
    data: Any
    raw_formats: list[int] = field(default_factory=list)

    def is_text(self) -> bool:
        return self.format == ClipboardFormat.TEXT

    def is_image(self) -> bool:
        return self.format == ClipboardFormat.BITMAP

    def is_empty(self) -> bool:
        return self.data is None


class ClipboardError(Exception):
    """剪贴板操作异常"""
    pass


class ClipboardManager:
    """
    剪贴板安全管理器

    功能：
    - 备份当前剪贴板内容
    - 设置文本/图片内容
    - 验证内容未被篡改
    - 恢复原始剪贴板内容

    使用示例:
        manager = ClipboardManager()
        try:
            manager.backup()
            manager.set_text("要发送的内容")
            if manager.verify_text("要发送的内容"):
                # 执行粘贴操作
                pass
        finally:
            manager.restore()
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 0.1):
        """
        初始化剪贴板管理器

        Args:
            max_retries: 操作最大重试次数
            retry_delay: 重试间隔（秒）
        """
        self._backup_content: Optional[ClipboardContent] = None
        self._has_backup: bool = False
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    def _open_clipboard(self) -> bool:
        """
        打开剪贴板（带重试）

        Returns:
            是否成功打开
        """
        for attempt in range(self._max_retries):
            try:
                win32clipboard.OpenClipboard()
                return True
            except Exception as e:
                if attempt < self._max_retries - 1:
                    time.sleep(self._retry_delay)
                else:
                    logger.error(f"无法打开剪贴板: {e}")
                    return False
        return False

    def _close_clipboard(self):
        """关闭剪贴板"""
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass

    def _get_available_formats(self) -> list[int]:
        """获取剪贴板中所有可用的格式"""
        formats = []
        fmt = 0
        while True:
            fmt = win32clipboard.EnumClipboardFormats(fmt)
            if fmt == 0:
                break
            formats.append(fmt)
        return formats

    def backup(self) -> bool:
        """
        备份当前剪贴板内容

        Returns:
            是否成功备份
        """
        if not self._open_clipboard():
            raise ClipboardError("无法打开剪贴板进行备份")

        try:
            formats = self._get_available_formats()

            if not formats:
                # 剪贴板为空
                self._backup_content = ClipboardContent(
                    format=ClipboardFormat.UNKNOWN,
                    data=None,
                    raw_formats=[]
                )
                self._has_backup = True
                logger.debug("剪贴板为空，备份完成")
                return True

            # 优先备份文本
            if win32con.CF_UNICODETEXT in formats:
                try:
                    data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    self._backup_content = ClipboardContent(
                        format=ClipboardFormat.TEXT,
                        data=data,
                        raw_formats=formats
                    )
                    self._has_backup = True
                    logger.debug(f"已备份文本内容，长度: {len(data)}")
                    return True
                except Exception as e:
                    logger.warning(f"备份文本内容失败: {e}")

            # 尝试备份位图
            if win32con.CF_DIB in formats:
                try:
                    data = win32clipboard.GetClipboardData(win32con.CF_DIB)
                    self._backup_content = ClipboardContent(
                        format=ClipboardFormat.BITMAP,
                        data=bytes(data),
                        raw_formats=formats
                    )
                    self._has_backup = True
                    logger.debug("已备份位图内容")
                    return True
                except Exception as e:
                    logger.warning(f"备份位图内容失败: {e}")

            # 无法备份的格式
            self._backup_content = ClipboardContent(
                format=ClipboardFormat.UNKNOWN,
                data=None,
                raw_formats=formats
            )
            self._has_backup = True
            logger.warning(f"剪贴板包含不支持备份的格式: {formats}")
            return True

        finally:
            self._close_clipboard()

    def restore(self) -> bool:
        """
        恢复原始剪贴板内容

        Returns:
            是否成功恢复
        """
        if not self._has_backup:
            logger.warning("没有可恢复的备份内容")
            return False

        if not self._open_clipboard():
            raise ClipboardError("无法打开剪贴板进行恢复")

        try:
            # 清空剪贴板
            win32clipboard.EmptyClipboard()

            if self._backup_content is None or self._backup_content.is_empty():
                logger.debug("恢复空剪贴板")
                return True

            if self._backup_content.format == ClipboardFormat.TEXT:
                win32clipboard.SetClipboardData(
                    win32con.CF_UNICODETEXT,
                    self._backup_content.data
                )
                logger.debug("已恢复文本内容")

            elif self._backup_content.format == ClipboardFormat.BITMAP:
                win32clipboard.SetClipboardData(
                    win32con.CF_DIB,
                    self._backup_content.data
                )
                logger.debug("已恢复位图内容")

            else:
                logger.warning("备份格式不支持恢复")
                return False

            return True

        except Exception as e:
            logger.error(f"恢复剪贴板内容失败: {e}")
            return False

        finally:
            self._close_clipboard()
            self._has_backup = False
            self._backup_content = None

    def set_text(self, text: str) -> bool:
        """
        设置剪贴板文本内容

        Args:
            text: 要设置的文本

        Returns:
            是否成功
        """
        if not text:
            logger.warning("尝试设置空文本")
            return False

        if not self._open_clipboard():
            raise ClipboardError("无法打开剪贴板")

        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            logger.debug(f"已设置剪贴板文本，长度: {len(text)}")
            return True

        except Exception as e:
            logger.error(f"设置剪贴板文本失败: {e}")
            return False

        finally:
            self._close_clipboard()

    def set_image(self, image_path: str) -> bool:
        """
        设置剪贴板图片内容

        Args:
            image_path: 图片文件路径

        Returns:
            是否成功
        """
        if Image is None:
            raise ClipboardError("需要安装 Pillow 库: pip install Pillow")

        path = Path(image_path)
        if not path.exists():
            logger.error(f"图片文件不存在: {image_path}")
            return False

        try:
            # 读取并转换图片
            with Image.open(path) as img:
                # 转换为 RGB 模式（如果需要）
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # 转换为 BMP 格式的字节数据
                output = io.BytesIO()
                img.save(output, format='BMP')
                bmp_data = output.getvalue()

                # BMP 文件头是 14 字节，DIB 数据从第 14 字节开始
                dib_data = bmp_data[14:]

        except Exception as e:
            logger.error(f"读取图片文件失败: {e}")
            return False

        if not self._open_clipboard():
            raise ClipboardError("无法打开剪贴板")

        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_DIB, dib_data)
            logger.debug(f"已设置剪贴板图片: {image_path}")
            return True

        except Exception as e:
            logger.error(f"设置剪贴板图片失败: {e}")
            return False

        finally:
            self._close_clipboard()

    def get_text(self) -> Optional[str]:
        """
        获取剪贴板文本内容

        Returns:
            文本内容，如果不是文本则返回 None
        """
        if not self._open_clipboard():
            raise ClipboardError("无法打开剪贴板")

        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return None

        except Exception as e:
            logger.error(f"获取剪贴板文本失败: {e}")
            return None

        finally:
            self._close_clipboard()

    def verify_text(self, expected: str) -> bool:
        """
        验证剪贴板文本未被篡改

        Args:
            expected: 期望的文本内容

        Returns:
            内容是否匹配
        """
        current = self.get_text()

        if current is None:
            logger.warning("剪贴板不包含文本内容")
            return False

        if current == expected:
            logger.debug("剪贴板内容验证通过")
            return True
        else:
            logger.warning("剪贴板内容与期望不符")
            logger.debug(f"期望长度: {len(expected)}, 实际长度: {len(current)}")
            return False

    def verify_has_image(self) -> bool:
        """
        验证剪贴板包含图片

        Returns:
            是否包含图片
        """
        if not self._open_clipboard():
            raise ClipboardError("无法打开剪贴板")

        try:
            has_image = win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB)
            if has_image:
                logger.debug("剪贴板包含图片")
            else:
                logger.debug("剪贴板不包含图片")
            return has_image

        finally:
            self._close_clipboard()

    def clear(self) -> bool:
        """
        清空剪贴板

        Returns:
            是否成功
        """
        if not self._open_clipboard():
            raise ClipboardError("无法打开剪贴板")

        try:
            win32clipboard.EmptyClipboard()
            logger.debug("已清空剪贴板")
            return True

        except Exception as e:
            logger.error(f"清空剪贴板失败: {e}")
            return False

        finally:
            self._close_clipboard()

    def has_backup(self) -> bool:
        """检查是否有备份"""
        return self._has_backup

    def __enter__(self):
        """上下文管理器入口 - 自动备份"""
        self.backup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口 - 自动恢复"""
        self.restore()
        return False  # 不抑制异常


# 便捷函数

def copy_text(text: str) -> bool:
    """
    复制文本到剪贴板（简便函数）

    Args:
        text: 要复制的文本

    Returns:
        是否成功
    """
    manager = ClipboardManager()
    return manager.set_text(text)


def copy_image(image_path: str) -> bool:
    """
    复制图片到剪贴板（简便函数）

    Args:
        image_path: 图片文件路径

    Returns:
        是否成功
    """
    manager = ClipboardManager()
    return manager.set_image(image_path)


def get_clipboard_text() -> Optional[str]:
    """
    获取剪贴板文本（简便函数）

    Returns:
        剪贴板文本，如果不是文本则返回 None
    """
    manager = ClipboardManager()
    return manager.get_text()
