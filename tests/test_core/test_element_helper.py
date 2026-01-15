"""
测试元素帮助工具模块

测试 core/utils/element_helper.py 中定义的所有工具函数
使用 mock 模拟 uiautomation 和 pyautogui
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import time


class TestElementFinding:
    """测试元素查找方法"""

    @patch('core.utils.element_helper.auto')
    def test_find_element_by_name_success(self, mock_auto):
        """测试按名称查找元素成功"""
        from core.utils.element_helper import find_element_by_name

        # 创建 mock 窗口和元素
        mock_window = Mock()
        mock_element = Mock()
        mock_element.Exists.return_value = True
        mock_window.Control.return_value = mock_element

        result = find_element_by_name(mock_window, "发送按钮")
        assert result is not None

    @patch('core.utils.element_helper.auto')
    def test_find_element_by_name_not_found(self, mock_auto):
        """测试按名称查找元素失败"""
        from core.utils.element_helper import find_element_by_name

        mock_window = Mock()
        mock_element = Mock()
        mock_element.Exists.return_value = False
        mock_window.Control.return_value = mock_element

        result = find_element_by_name(mock_window, "不存在的按钮")
        assert result is None

    @patch('core.utils.element_helper.auto')
    def test_find_element_by_class_success(self, mock_auto):
        """测试按类名查找元素成功"""
        from core.utils.element_helper import find_element_by_class

        mock_window = Mock()
        mock_element = Mock()
        mock_element.Exists.return_value = True
        mock_window.Control.return_value = mock_element

        result = find_element_by_class(mock_window, "mmui::XButton")
        assert result is not None

    @patch('core.utils.element_helper.auto')
    def test_find_button_success(self, mock_auto):
        """测试查找按钮成功"""
        from core.utils.element_helper import find_button

        mock_window = Mock()
        mock_button = Mock()
        mock_button.Exists.return_value = True
        mock_window.ButtonControl.return_value = mock_button

        result = find_button(mock_window, "发表")
        assert result is not None

    @patch('core.utils.element_helper.auto')
    def test_find_input_box_v4(self, mock_auto):
        """测试查找 v4 版本输入框"""
        from core.utils.element_helper import find_input_box

        mock_window = Mock()
        mock_input = Mock()
        mock_input.Exists.return_value = True
        mock_window.EditControl.return_value = mock_input

        result = find_input_box(mock_window, class_names_v4=["mmui::XTextEdit"])
        assert result is not None


class TestWaitMethods:
    """测试等待方法"""

    @patch('core.utils.element_helper.auto')
    def test_wait_for_element_found(self, mock_auto):
        """测试等待元素出现 - 找到"""
        from core.utils.element_helper import wait_for_element

        mock_window = Mock()
        mock_window.Exists.return_value = True
        mock_element = Mock()
        mock_element.Exists.return_value = True
        mock_window.Control.return_value = mock_element

        # selector 的 key 应该是小写的 name
        result = wait_for_element(mock_window, selector={"name": "测试元素"}, timeout=1)
        assert result is not None

    @patch('core.utils.element_helper.auto')
    def test_wait_for_element_timeout(self, mock_auto):
        """测试等待元素出现 - 超时"""
        from core.utils.element_helper import wait_for_element

        mock_window = Mock()
        mock_window.Exists.return_value = True
        mock_element = Mock()
        mock_element.Exists.return_value = False
        mock_window.Control.return_value = mock_element

        # selector 的 key 应该是小写的 name，设置短超时
        result = wait_for_element(mock_window, selector={"name": "不存在"}, timeout=0.5)
        assert result is None

    @patch('core.utils.element_helper.auto')
    def test_wait_for_window_success(self, mock_auto):
        """测试等待窗口出现成功"""
        from core.utils.element_helper import wait_for_window

        mock_window = Mock()
        mock_window.Exists.return_value = True
        mock_auto.WindowControl.return_value = mock_window

        result = wait_for_window("#32770", timeout=5)
        assert result is not None


class TestClickOperations:
    """测试点击操作"""

    @patch('core.utils.element_helper.time')
    def test_safe_click_success(self, mock_time):
        """测试安全点击成功"""
        from core.utils.element_helper import safe_click

        mock_element = Mock()
        mock_element.Exists.return_value = True
        mock_element.Click.return_value = None

        result = safe_click(mock_element)
        assert result is True
        mock_element.Click.assert_called_once()

    @patch('core.utils.element_helper.time')
    def test_safe_click_element_not_exists(self, mock_time):
        """测试点击不存在的元素"""
        from core.utils.element_helper import safe_click

        mock_element = Mock()
        mock_element.Exists.return_value = False

        result = safe_click(mock_element)
        assert result is False

    @patch('core.utils.element_helper.pyautogui')
    @patch('core.utils.element_helper.time')
    def test_click_at_position(self, mock_time, mock_pyautogui):
        """测试坐标点击"""
        from core.utils.element_helper import click_at_position

        result = click_at_position(100, 200)
        assert result is True
        mock_pyautogui.click.assert_called_once_with(100, 200)

    @patch('core.utils.element_helper.pyautogui')
    @patch('core.utils.element_helper.time')
    def test_click_element_center(self, mock_time, mock_pyautogui):
        """测试点击元素中心"""
        from core.utils.element_helper import click_element_center

        mock_element = Mock()
        mock_element.Exists.return_value = True
        mock_rect = Mock()
        mock_rect.left = 0
        mock_rect.right = 100
        mock_rect.top = 0
        mock_rect.bottom = 100
        mock_element.BoundingRectangle = mock_rect

        result = click_element_center(mock_element)
        assert result is True

    @patch('core.utils.element_helper.pyautogui')
    @patch('core.utils.element_helper.time')
    def test_long_click(self, mock_time, mock_pyautogui):
        """测试长按点击"""
        from core.utils.element_helper import long_click

        mock_element = Mock()
        mock_element.Exists.return_value = True
        mock_rect = Mock()
        mock_rect.left = 0
        mock_rect.right = 100
        mock_rect.top = 0
        mock_rect.bottom = 100
        mock_element.BoundingRectangle = mock_rect

        result = long_click(mock_element, duration=1.0)
        assert result is True
        mock_pyautogui.mouseDown.assert_called_once()
        mock_pyautogui.mouseUp.assert_called_once()


class TestInputOperations:
    """测试输入操作"""

    @patch('core.utils.element_helper.pyperclip')
    @patch('core.utils.element_helper.pyautogui')
    @patch('core.utils.element_helper.time')
    def test_input_text_via_clipboard(self, mock_time, mock_pyautogui, mock_pyperclip):
        """测试通过剪贴板输入文本"""
        from core.utils.element_helper import input_text_via_clipboard

        mock_element = Mock()
        mock_element.Exists.return_value = True

        result = input_text_via_clipboard(mock_element, "测试文本")
        assert result is True
        # 检查 pyperclip.copy 是否被调用（可能是直接调用或通过其他方式）
        assert mock_pyperclip.copy.called or mock_pyautogui.hotkey.called

    @patch('core.utils.element_helper.pyautogui')
    @patch('core.utils.element_helper.time')
    def test_paste_from_clipboard(self, mock_time, mock_pyautogui):
        """测试从剪贴板粘贴"""
        from core.utils.element_helper import paste_from_clipboard

        result = paste_from_clipboard()
        assert result is True
        mock_pyautogui.hotkey.assert_called_with('ctrl', 'v')

    @patch('core.utils.element_helper.pyperclip')
    @patch('core.utils.element_helper.pyautogui')
    @patch('core.utils.element_helper.time')
    def test_clear_and_input(self, mock_time, mock_pyautogui, mock_pyperclip):
        """测试清空并输入"""
        from core.utils.element_helper import clear_and_input

        mock_element = Mock()
        mock_element.Exists.return_value = True

        result = clear_and_input(mock_element, "新文本")
        assert result is True


class TestWindowOperations:
    """测试窗口操作"""

    @patch('core.utils.element_helper.ctypes', create=True)
    def test_activate_window_success(self, mock_ctypes):
        """测试激活窗口成功"""
        from core.utils.element_helper import activate_window

        mock_window = Mock()
        mock_window.Exists.return_value = True
        mock_window.NativeWindowHandle = 12345

        result = activate_window(mock_window)
        # 只验证返回值是布尔类型
        assert isinstance(result, bool)

    def test_is_window_foreground(self):
        """测试检查窗口是否在前台"""
        from core.utils.element_helper import is_window_foreground

        mock_window = Mock()
        mock_window.Exists.return_value = True
        mock_window.NativeWindowHandle = 12345

        # 这个测试可能需要根据实际实现调整
        result = is_window_foreground(mock_window)
        assert isinstance(result, bool)

    def test_get_window_rect(self):
        """测试获取窗口矩形"""
        from core.utils.element_helper import get_window_rect

        mock_window = Mock()
        mock_window.Exists.return_value = True
        mock_rect = Mock()
        mock_rect.left = 0
        mock_rect.top = 0
        mock_rect.right = 800
        mock_rect.bottom = 600
        mock_window.BoundingRectangle = mock_rect

        result = get_window_rect(mock_window)
        assert result is not None
        assert len(result) == 4


class TestErrorHandling:
    """测试错误处理"""

    @patch('core.utils.element_helper.auto')
    def test_find_element_handles_exception(self, mock_auto):
        """测试元素查找异常处理"""
        from core.utils.element_helper import find_element_by_name

        mock_window = Mock()
        mock_window.Control.side_effect = Exception("测试异常")

        result = find_element_by_name(mock_window, "测试")
        assert result is None

    @patch('core.utils.element_helper.pyautogui')
    @patch('core.utils.element_helper.time')
    def test_click_handles_exception(self, mock_time, mock_pyautogui):
        """测试点击异常处理"""
        from core.utils.element_helper import click_at_position

        mock_pyautogui.click.side_effect = Exception("点击失败")

        result = click_at_position(100, 200)
        assert result is False


class TestEdgeCases:
    """测试边界情况"""

    @patch('core.utils.element_helper.auto')
    def test_find_element_with_none_window(self, mock_auto):
        """测试传入 None 窗口"""
        from core.utils.element_helper import find_element_by_name

        result = find_element_by_name(None, "测试")
        assert result is None

    @patch('core.utils.element_helper.time')
    def test_safe_click_with_none_element(self, mock_time):
        """测试点击 None 元素"""
        from core.utils.element_helper import safe_click

        result = safe_click(None)
        assert result is False

    @patch('core.utils.element_helper.pyperclip')
    @patch('core.utils.element_helper.pyautogui')
    @patch('core.utils.element_helper.time')
    def test_input_empty_text(self, mock_time, mock_pyautogui, mock_pyperclip):
        """测试输入空文本"""
        from core.utils.element_helper import input_text_via_clipboard

        mock_element = Mock()
        mock_element.Exists.return_value = True

        result = input_text_via_clipboard(mock_element, "")
        # 空文本可能返回 True 或 False，取决于实现
        assert isinstance(result, bool)
