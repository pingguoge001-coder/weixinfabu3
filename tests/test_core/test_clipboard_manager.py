"""
测试剪贴板管理模块

测试 core/clipboard_manager.py 中定义的 ClipboardManager 类
使用 mock 模拟 win32clipboard 和 PIL
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import io

# Mock win32clipboard and win32con before importing
import sys
mock_win32clipboard = MagicMock()
mock_win32con = MagicMock()
mock_win32con.CF_UNICODETEXT = 13
mock_win32con.CF_DIB = 8
mock_win32con.CF_HDROP = 15

sys.modules['win32clipboard'] = mock_win32clipboard
sys.modules['win32con'] = mock_win32con

from core.clipboard_manager import (
    ClipboardManager,
    ClipboardFormat,
    ClipboardContent,
    ClipboardError,
    copy_text,
    copy_image,
    get_clipboard_text,
)


class TestClipboardFormat:
    """测试剪贴板格式枚举"""

    def test_format_values(self):
        """测试格式枚举值"""
        assert ClipboardFormat.TEXT.value == 13
        assert ClipboardFormat.BITMAP.value == 8
        assert ClipboardFormat.FILES.value == 15
        assert ClipboardFormat.HTML.value == 49461
        assert ClipboardFormat.UNKNOWN.value == 0


class TestClipboardContent:
    """测试剪贴板内容数据类"""

    def test_is_text(self):
        """测试文本判断"""
        content = ClipboardContent(format=ClipboardFormat.TEXT, data="test")
        assert content.is_text() is True

        content = ClipboardContent(format=ClipboardFormat.BITMAP, data=b"data")
        assert content.is_text() is False

    def test_is_image(self):
        """测试图片判断"""
        content = ClipboardContent(format=ClipboardFormat.BITMAP, data=b"data")
        assert content.is_image() is True

        content = ClipboardContent(format=ClipboardFormat.TEXT, data="test")
        assert content.is_image() is False

    def test_is_empty(self):
        """测试空内容判断"""
        content = ClipboardContent(format=ClipboardFormat.UNKNOWN, data=None)
        assert content.is_empty() is True

        content = ClipboardContent(format=ClipboardFormat.TEXT, data="test")
        assert content.is_empty() is False


class TestClipboardManagerInit:
    """测试 ClipboardManager 初始化"""

    def test_default_init(self):
        """测试默认初始化"""
        manager = ClipboardManager()
        assert manager._backup_content is None
        assert manager._has_backup is False
        assert manager._max_retries == 3
        assert manager._retry_delay == 0.1

    def test_custom_init(self):
        """测试自定义初始化参数"""
        manager = ClipboardManager(max_retries=5, retry_delay=0.2)
        assert manager._max_retries == 5
        assert manager._retry_delay == 0.2


class TestClipboardOpen:
    """测试剪贴板打开操作"""

    @patch('core.clipboard_manager.win32clipboard')
    def test_open_success(self, mock_clipboard):
        """测试打开剪贴板成功"""
        mock_clipboard.OpenClipboard.return_value = None
        manager = ClipboardManager()
        result = manager._open_clipboard()
        assert result is True
        mock_clipboard.OpenClipboard.assert_called_once()

    @patch('core.clipboard_manager.win32clipboard')
    @patch('core.clipboard_manager.time')
    def test_open_retry_success(self, mock_time, mock_clipboard):
        """测试打开剪贴板重试成功"""
        # 第一次失败，第二次成功
        mock_clipboard.OpenClipboard.side_effect = [Exception("busy"), None]
        manager = ClipboardManager(max_retries=3, retry_delay=0.01)
        result = manager._open_clipboard()
        assert result is True
        assert mock_clipboard.OpenClipboard.call_count == 2

    @patch('core.clipboard_manager.win32clipboard')
    @patch('core.clipboard_manager.time')
    def test_open_all_retries_failed(self, mock_time, mock_clipboard):
        """测试打开剪贴板所有重试都失败"""
        mock_clipboard.OpenClipboard.side_effect = Exception("busy")
        manager = ClipboardManager(max_retries=2, retry_delay=0.01)
        result = manager._open_clipboard()
        assert result is False
        assert mock_clipboard.OpenClipboard.call_count == 2

    @patch('core.clipboard_manager.win32clipboard')
    def test_close_clipboard(self, mock_clipboard):
        """测试关闭剪贴板"""
        manager = ClipboardManager()
        manager._close_clipboard()
        mock_clipboard.CloseClipboard.assert_called_once()

    @patch('core.clipboard_manager.win32clipboard')
    def test_close_clipboard_handles_exception(self, mock_clipboard):
        """测试关闭剪贴板异常处理"""
        mock_clipboard.CloseClipboard.side_effect = Exception("error")
        manager = ClipboardManager()
        # 不应抛出异常
        manager._close_clipboard()


class TestBackupRestore:
    """测试备份和恢复功能"""

    @patch('core.clipboard_manager.win32clipboard')
    def test_backup_empty_clipboard(self, mock_clipboard):
        """测试备份空剪贴板"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.EnumClipboardFormats.return_value = 0

        manager = ClipboardManager()
        result = manager.backup()

        assert result is True
        assert manager._has_backup is True
        assert manager._backup_content.is_empty() is True
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_backup_text_content(self, mock_clipboard):
        """测试备份文本内容"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.EnumClipboardFormats.side_effect = [13, 0]  # CF_UNICODETEXT, then done
        mock_clipboard.GetClipboardData.return_value = "测试文本"

        manager = ClipboardManager()
        result = manager.backup()

        assert result is True
        assert manager._has_backup is True
        assert manager._backup_content.format == ClipboardFormat.TEXT
        assert manager._backup_content.data == "测试文本"
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_backup_bitmap_content(self, mock_clipboard):
        """测试备份位图内容"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.EnumClipboardFormats.side_effect = [8, 0]  # CF_DIB, then done
        mock_clipboard.GetClipboardData.return_value = b"bitmap_data"

        manager = ClipboardManager()
        result = manager.backup()

        assert result is True
        assert manager._has_backup is True
        assert manager._backup_content.format == ClipboardFormat.BITMAP
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_backup_open_failed(self, mock_clipboard):
        """测试备份时打开剪贴板失败"""
        mock_clipboard.OpenClipboard.side_effect = Exception("busy")

        manager = ClipboardManager(max_retries=1)

        with pytest.raises(ClipboardError, match="无法打开剪贴板进行备份"):
            manager.backup()

    @patch('core.clipboard_manager.win32clipboard')
    def test_restore_without_backup(self, mock_clipboard):
        """测试没有备份时恢复"""
        manager = ClipboardManager()
        result = manager.restore()

        assert result is False
        mock_clipboard.OpenClipboard.assert_not_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_restore_empty_clipboard(self, mock_clipboard):
        """测试恢复空剪贴板"""
        mock_clipboard.OpenClipboard.return_value = None

        manager = ClipboardManager()
        manager._has_backup = True
        manager._backup_content = ClipboardContent(
            format=ClipboardFormat.UNKNOWN,
            data=None
        )

        result = manager.restore()

        assert result is True
        assert manager._has_backup is False
        assert manager._backup_content is None
        mock_clipboard.EmptyClipboard.assert_called_once()
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_restore_text_content(self, mock_clipboard):
        """测试恢复文本内容"""
        mock_clipboard.OpenClipboard.return_value = None

        manager = ClipboardManager()
        manager._has_backup = True
        manager._backup_content = ClipboardContent(
            format=ClipboardFormat.TEXT,
            data="原始文本"
        )

        result = manager.restore()

        assert result is True
        assert manager._has_backup is False
        mock_clipboard.SetClipboardData.assert_called_with(13, "原始文本")
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_restore_bitmap_content(self, mock_clipboard):
        """测试恢复位图内容"""
        mock_clipboard.OpenClipboard.return_value = None

        manager = ClipboardManager()
        manager._has_backup = True
        manager._backup_content = ClipboardContent(
            format=ClipboardFormat.BITMAP,
            data=b"bitmap_data"
        )

        result = manager.restore()

        assert result is True
        assert manager._has_backup is False
        mock_clipboard.SetClipboardData.assert_called_with(8, b"bitmap_data")
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_restore_open_failed(self, mock_clipboard):
        """测试恢复时打开剪贴板失败"""
        mock_clipboard.OpenClipboard.side_effect = Exception("busy")

        manager = ClipboardManager(max_retries=1)
        manager._has_backup = True
        manager._backup_content = ClipboardContent(
            format=ClipboardFormat.TEXT,
            data="test"
        )

        with pytest.raises(ClipboardError, match="无法打开剪贴板进行恢复"):
            manager.restore()

    @patch('core.clipboard_manager.win32clipboard')
    def test_restore_handles_exception(self, mock_clipboard):
        """测试恢复时异常处理"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.SetClipboardData.side_effect = Exception("error")

        manager = ClipboardManager()
        manager._has_backup = True
        manager._backup_content = ClipboardContent(
            format=ClipboardFormat.TEXT,
            data="test"
        )

        result = manager.restore()
        assert result is False
        assert manager._has_backup is False  # 确保清理状态


class TestSetGetText:
    """测试文本设置和获取"""

    @patch('core.clipboard_manager.win32clipboard')
    def test_set_text_success(self, mock_clipboard):
        """测试设置文本成功"""
        mock_clipboard.OpenClipboard.return_value = None

        manager = ClipboardManager()
        result = manager.set_text("测试文本")

        assert result is True
        mock_clipboard.EmptyClipboard.assert_called_once()
        mock_clipboard.SetClipboardData.assert_called_with(13, "测试文本")
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_set_empty_text(self, mock_clipboard):
        """测试设置空文本"""
        manager = ClipboardManager()
        result = manager.set_text("")

        assert result is False
        mock_clipboard.OpenClipboard.assert_not_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_set_text_open_failed(self, mock_clipboard):
        """测试设置文本时打开剪贴板失败"""
        mock_clipboard.OpenClipboard.side_effect = Exception("busy")

        manager = ClipboardManager(max_retries=1)

        with pytest.raises(ClipboardError, match="无法打开剪贴板"):
            manager.set_text("test")

    @patch('core.clipboard_manager.win32clipboard')
    def test_set_text_handles_exception(self, mock_clipboard):
        """测试设置文本异常处理"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.SetClipboardData.side_effect = Exception("error")

        manager = ClipboardManager()
        result = manager.set_text("test")

        assert result is False
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_get_text_success(self, mock_clipboard):
        """测试获取文本成功"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.IsClipboardFormatAvailable.return_value = True
        mock_clipboard.GetClipboardData.return_value = "剪贴板文本"

        manager = ClipboardManager()
        result = manager.get_text()

        assert result == "剪贴板文本"
        mock_clipboard.IsClipboardFormatAvailable.assert_called_with(13)
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_get_text_not_available(self, mock_clipboard):
        """测试获取文本时无文本格式"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.IsClipboardFormatAvailable.return_value = False

        manager = ClipboardManager()
        result = manager.get_text()

        assert result is None
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_get_text_open_failed(self, mock_clipboard):
        """测试获取文本时打开剪贴板失败"""
        mock_clipboard.OpenClipboard.side_effect = Exception("busy")

        manager = ClipboardManager(max_retries=1)

        with pytest.raises(ClipboardError, match="无法打开剪贴板"):
            manager.get_text()

    @patch('core.clipboard_manager.win32clipboard')
    def test_get_text_handles_exception(self, mock_clipboard):
        """测试获取文本异常处理"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.IsClipboardFormatAvailable.side_effect = Exception("error")

        manager = ClipboardManager()
        result = manager.get_text()

        assert result is None
        mock_clipboard.CloseClipboard.assert_called()


class TestSetImage:
    """测试图片设置"""

    @patch('core.clipboard_manager.win32clipboard')
    @patch('core.clipboard_manager.Image')
    @patch('core.clipboard_manager.Path')
    def test_set_image_success(self, mock_path_class, mock_pil, mock_clipboard):
        """测试设置图片成功"""
        # Mock Path
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path

        # Mock PIL Image
        mock_img = Mock()
        mock_img.mode = 'RGB'
        mock_output = io.BytesIO()
        # 创建一个简单的 BMP 文件头 + 数据
        bmp_data = b'BM' + b'\x00' * 12 + b'image_data'
        mock_output.write(bmp_data)
        mock_output.seek(0)

        mock_img.save = lambda f, format: f.write(bmp_data)
        mock_pil.open.return_value.__enter__.return_value = mock_img

        # Mock clipboard
        mock_clipboard.OpenClipboard.return_value = None

        manager = ClipboardManager()
        result = manager.set_image("/path/to/image.jpg")

        assert result is True
        mock_clipboard.EmptyClipboard.assert_called_once()
        mock_clipboard.SetClipboardData.assert_called_once()
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.Image', None)
    def test_set_image_no_pil(self):
        """测试没有安装 PIL 时设置图片"""
        manager = ClipboardManager()

        with pytest.raises(ClipboardError, match="需要安装 Pillow 库"):
            manager.set_image("/path/to/image.jpg")

    @patch('core.clipboard_manager.Image')
    @patch('core.clipboard_manager.Path')
    def test_set_image_file_not_exists(self, mock_path_class, mock_pil):
        """测试设置不存在的图片文件"""
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path

        manager = ClipboardManager()
        result = manager.set_image("/path/to/nonexistent.jpg")

        assert result is False

    @patch('core.clipboard_manager.win32clipboard')
    @patch('core.clipboard_manager.Image')
    @patch('core.clipboard_manager.Path')
    def test_set_image_convert_mode(self, mock_path_class, mock_pil, mock_clipboard):
        """测试设置图片时转换模式"""
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path

        # Mock PNG image (RGBA mode)
        mock_img = Mock()
        mock_img.mode = 'RGBA'
        mock_rgb_img = Mock()
        mock_rgb_img.mode = 'RGB'
        mock_img.convert.return_value = mock_rgb_img

        bmp_data = b'BM' + b'\x00' * 12 + b'image_data'
        mock_rgb_img.save = lambda f, format: f.write(bmp_data)

        mock_pil.open.return_value.__enter__.return_value = mock_img
        mock_clipboard.OpenClipboard.return_value = None

        manager = ClipboardManager()
        result = manager.set_image("/path/to/image.png")

        assert result is True
        mock_img.convert.assert_called_with('RGB')

    @patch('core.clipboard_manager.Image')
    @patch('core.clipboard_manager.Path')
    def test_set_image_read_error(self, mock_path_class, mock_pil):
        """测试读取图片文件失败"""
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path

        mock_pil.open.side_effect = Exception("读取失败")

        manager = ClipboardManager()
        result = manager.set_image("/path/to/image.jpg")

        assert result is False

    @patch('core.clipboard_manager.win32clipboard')
    @patch('core.clipboard_manager.Image')
    @patch('core.clipboard_manager.Path')
    def test_set_image_clipboard_error(self, mock_path_class, mock_pil, mock_clipboard):
        """测试设置图片到剪贴板失败"""
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path

        mock_img = Mock()
        mock_img.mode = 'RGB'
        bmp_data = b'BM' + b'\x00' * 12 + b'image_data'
        mock_img.save = lambda f, format: f.write(bmp_data)
        mock_pil.open.return_value.__enter__.return_value = mock_img

        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.SetClipboardData.side_effect = Exception("error")

        manager = ClipboardManager()
        result = manager.set_image("/path/to/image.jpg")

        assert result is False
        mock_clipboard.CloseClipboard.assert_called()


class TestVerifyMethods:
    """测试验证方法"""

    @patch('core.clipboard_manager.win32clipboard')
    def test_verify_text_success(self, mock_clipboard):
        """测试验证文本成功"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.IsClipboardFormatAvailable.return_value = True
        mock_clipboard.GetClipboardData.return_value = "expected text"

        manager = ClipboardManager()
        result = manager.verify_text("expected text")

        assert result is True
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_verify_text_mismatch(self, mock_clipboard):
        """测试验证文本不匹配"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.IsClipboardFormatAvailable.return_value = True
        mock_clipboard.GetClipboardData.return_value = "actual text"

        manager = ClipboardManager()
        result = manager.verify_text("expected text")

        assert result is False

    @patch('core.clipboard_manager.win32clipboard')
    def test_verify_text_no_text(self, mock_clipboard):
        """测试验证文本时无文本内容"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.IsClipboardFormatAvailable.return_value = False

        manager = ClipboardManager()
        result = manager.verify_text("expected")

        assert result is False

    @patch('core.clipboard_manager.win32clipboard')
    def test_verify_has_image_true(self, mock_clipboard):
        """测试验证包含图片 - 有图片"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.IsClipboardFormatAvailable.return_value = True

        manager = ClipboardManager()
        result = manager.verify_has_image()

        assert result is True
        mock_clipboard.IsClipboardFormatAvailable.assert_called_with(8)
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_verify_has_image_false(self, mock_clipboard):
        """测试验证包含图片 - 无图片"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.IsClipboardFormatAvailable.return_value = False

        manager = ClipboardManager()
        result = manager.verify_has_image()

        assert result is False

    @patch('core.clipboard_manager.win32clipboard')
    def test_verify_has_image_open_failed(self, mock_clipboard):
        """测试验证图片时打开剪贴板失败"""
        mock_clipboard.OpenClipboard.side_effect = Exception("busy")

        manager = ClipboardManager(max_retries=1)

        with pytest.raises(ClipboardError, match="无法打开剪贴板"):
            manager.verify_has_image()


class TestClearMethod:
    """测试清空方法"""

    @patch('core.clipboard_manager.win32clipboard')
    def test_clear_success(self, mock_clipboard):
        """测试清空剪贴板成功"""
        mock_clipboard.OpenClipboard.return_value = None

        manager = ClipboardManager()
        result = manager.clear()

        assert result is True
        mock_clipboard.EmptyClipboard.assert_called_once()
        mock_clipboard.CloseClipboard.assert_called()

    @patch('core.clipboard_manager.win32clipboard')
    def test_clear_open_failed(self, mock_clipboard):
        """测试清空时打开剪贴板失败"""
        mock_clipboard.OpenClipboard.side_effect = Exception("busy")

        manager = ClipboardManager(max_retries=1)

        with pytest.raises(ClipboardError, match="无法打开剪贴板"):
            manager.clear()

    @patch('core.clipboard_manager.win32clipboard')
    def test_clear_handles_exception(self, mock_clipboard):
        """测试清空时异常处理"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.EmptyClipboard.side_effect = Exception("error")

        manager = ClipboardManager()
        result = manager.clear()

        assert result is False
        mock_clipboard.CloseClipboard.assert_called()


class TestContextManager:
    """测试上下文管理器"""

    @patch('core.clipboard_manager.win32clipboard')
    def test_context_manager_normal(self, mock_clipboard):
        """测试上下文管理器正常流程"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.EnumClipboardFormats.return_value = 0

        manager = ClipboardManager()

        with manager as m:
            assert m is manager
            assert manager._has_backup is True

        # 退出后应该恢复
        assert manager._has_backup is False

    @patch('core.clipboard_manager.win32clipboard')
    def test_context_manager_with_exception(self, mock_clipboard):
        """测试上下文管理器异常处理"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.EnumClipboardFormats.side_effect = [13, 0]
        mock_clipboard.GetClipboardData.return_value = "backup text"

        manager = ClipboardManager()

        with pytest.raises(ValueError):
            with manager:
                assert manager._has_backup is True
                raise ValueError("test error")

        # 即使有异常，也应该恢复
        assert manager._has_backup is False


class TestHasBackup:
    """测试备份状态检查"""

    def test_has_backup_false(self):
        """测试没有备份"""
        manager = ClipboardManager()
        assert manager.has_backup() is False

    @patch('core.clipboard_manager.win32clipboard')
    def test_has_backup_true(self, mock_clipboard):
        """测试有备份"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.EnumClipboardFormats.return_value = 0

        manager = ClipboardManager()
        manager.backup()

        assert manager.has_backup() is True


class TestConvenienceFunctions:
    """测试便捷函数"""

    @patch('core.clipboard_manager.win32clipboard')
    def test_copy_text(self, mock_clipboard):
        """测试 copy_text 函数"""
        mock_clipboard.OpenClipboard.return_value = None

        result = copy_text("测试文本")

        assert result is True
        mock_clipboard.SetClipboardData.assert_called_with(13, "测试文本")

    @patch('core.clipboard_manager.win32clipboard')
    @patch('core.clipboard_manager.Image')
    @patch('core.clipboard_manager.Path')
    def test_copy_image(self, mock_path_class, mock_pil, mock_clipboard):
        """测试 copy_image 函数"""
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path

        mock_img = Mock()
        mock_img.mode = 'RGB'
        bmp_data = b'BM' + b'\x00' * 12 + b'image_data'
        mock_img.save = lambda f, format: f.write(bmp_data)
        mock_pil.open.return_value.__enter__.return_value = mock_img

        mock_clipboard.OpenClipboard.return_value = None

        result = copy_image("/path/to/image.jpg")

        assert result is True

    @patch('core.clipboard_manager.win32clipboard')
    def test_get_clipboard_text(self, mock_clipboard):
        """测试 get_clipboard_text 函数"""
        mock_clipboard.OpenClipboard.return_value = None
        mock_clipboard.IsClipboardFormatAvailable.return_value = True
        mock_clipboard.GetClipboardData.return_value = "剪贴板内容"

        result = get_clipboard_text()

        assert result == "剪贴板内容"


class TestGetAvailableFormats:
    """测试获取可用格式"""

    @patch('core.clipboard_manager.win32clipboard')
    def test_get_available_formats_multiple(self, mock_clipboard):
        """测试获取多种格式"""
        # 模拟枚举返回多个格式
        mock_clipboard.EnumClipboardFormats.side_effect = [13, 8, 1, 0]

        manager = ClipboardManager()
        formats = manager._get_available_formats()

        assert formats == [13, 8, 1]

    @patch('core.clipboard_manager.win32clipboard')
    def test_get_available_formats_empty(self, mock_clipboard):
        """测试获取空格式列表"""
        mock_clipboard.EnumClipboardFormats.return_value = 0

        manager = ClipboardManager()
        formats = manager._get_available_formats()

        assert formats == []
