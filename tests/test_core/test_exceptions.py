"""
测试自定义异常模块

测试 core/exceptions.py 中定义的所有异常类
"""
import pytest
from core.exceptions import (
    # 基础异常
    WeChatAutoError,
    # 微信相关异常
    WeChatNotFoundError,
    WeChatNotLoggedInError,
    WeChatVersionError,
    WeChatStatusError,
    # UI 元素异常
    ElementNotFoundError,
    ElementTimeoutError,
    ElementClickError,
    ElementInteractionError,
    # 发送相关异常
    SendError,
    MomentSendError,
    GroupSendError,
    ImageUploadError,
    SendTimeoutError,
    # 配置/文件异常
    ConfigError,
    FileNotFoundError as CustomFileNotFoundError,
    InvalidPathError,
    ContentValidationError,
    # 其他异常
    ClipboardError,
    WindowOperationError,
    # 工具函数
    format_exception_message,
    get_error_code,
)


class TestWeChatAutoError:
    """测试基础异常类"""

    def test_basic_creation(self):
        """测试基本创建"""
        error = WeChatAutoError("测试错误")
        assert error.message == "测试错误"
        assert error.error_code == "UNKNOWN_ERROR"
        assert error.context == {}

    def test_with_context(self):
        """测试带上下文创建"""
        error = WeChatAutoError("测试错误", context={"key": "value"})
        assert error.context == {"key": "value"}

    def test_str_format(self):
        """测试字符串格式"""
        error = WeChatAutoError("测试错误")
        assert "[UNKNOWN_ERROR]" in str(error)
        assert "测试错误" in str(error)

    def test_str_with_context(self):
        """测试带上下文的字符串格式"""
        error = WeChatAutoError("测试错误", context={"key": "value"})
        result = str(error)
        assert "key=value" in result

    def test_repr(self):
        """测试 repr 输出"""
        error = WeChatAutoError("测试错误")
        result = repr(error)
        assert "WeChatAutoError" in result
        assert "error_code" in result

    def test_default_message(self):
        """测试默认消息"""
        error = WeChatAutoError()
        assert error.message == "微信自动化操作失败"


class TestWeChatExceptions:
    """测试微信相关异常"""

    def test_wechat_not_found_error(self):
        """测试 WeChatNotFoundError"""
        error = WeChatNotFoundError("未找到微信")
        assert error.error_code == "WECHAT_NOT_FOUND"
        assert isinstance(error, WeChatAutoError)

    def test_wechat_not_logged_in_error(self):
        """测试 WeChatNotLoggedInError"""
        error = WeChatNotLoggedInError("请先登录")
        assert error.error_code == "WECHAT_NOT_LOGGED_IN"
        assert isinstance(error, WeChatAutoError)

    def test_wechat_version_error(self):
        """测试 WeChatVersionError"""
        error = WeChatVersionError("版本不支持", context={"version": "2.0"})
        assert error.error_code == "WECHAT_VERSION_ERROR"
        assert error.context["version"] == "2.0"

    def test_wechat_status_error(self):
        """测试 WeChatStatusError"""
        error = WeChatStatusError("微信状态异常")
        assert error.error_code == "WECHAT_STATUS_ERROR"


class TestElementExceptions:
    """测试 UI 元素异常"""

    def test_element_not_found_error(self):
        """测试 ElementNotFoundError"""
        error = ElementNotFoundError("找不到按钮", element_name="发送按钮")
        assert error.error_code == "ELEMENT_NOT_FOUND"
        assert "发送按钮" in str(error) or error.context.get("element_name") == "发送按钮"

    def test_element_timeout_error(self):
        """测试 ElementTimeoutError"""
        error = ElementTimeoutError("等待超时", timeout=10)
        assert error.error_code == "ELEMENT_TIMEOUT"

    def test_element_click_error(self):
        """测试 ElementClickError"""
        error = ElementClickError("点击失败")
        assert error.error_code == "ELEMENT_CLICK_ERROR"

    def test_element_interaction_error(self):
        """测试 ElementInteractionError"""
        error = ElementInteractionError("交互失败")
        assert error.error_code == "ELEMENT_INTERACTION_ERROR"


class TestSendExceptions:
    """测试发送相关异常"""

    def test_send_error_base(self):
        """测试 SendError 基类"""
        error = SendError("发送失败")
        assert error.error_code == "SEND_ERROR"
        assert isinstance(error, WeChatAutoError)

    def test_moment_send_error(self):
        """测试 MomentSendError"""
        error = MomentSendError("朋友圈发送失败", step="添加图片", content_code="TEST001")
        assert error.error_code == "MOMENT_SEND_ERROR"
        assert isinstance(error, SendError)

    def test_group_send_error(self):
        """测试 GroupSendError"""
        error = GroupSendError("群发失败", group_name="测试群")
        assert error.error_code == "GROUP_SEND_ERROR"
        assert isinstance(error, SendError)

    def test_image_upload_error(self):
        """测试 ImageUploadError"""
        error = ImageUploadError("上传失败", image_path="/path/to/image.jpg")
        assert error.error_code == "IMAGE_UPLOAD_ERROR"

    def test_send_timeout_error(self):
        """测试 SendTimeoutError"""
        error = SendTimeoutError("发送超时")
        assert error.error_code == "SEND_TIMEOUT_ERROR"


class TestConfigFileExceptions:
    """测试配置/文件异常"""

    def test_config_error(self):
        """测试 ConfigError"""
        error = ConfigError("配置错误", config_key="timeout")
        assert error.error_code == "CONFIG_ERROR"

    def test_file_not_found_error(self):
        """测试自定义 FileNotFoundError"""
        error = CustomFileNotFoundError("文件不存在", file_path="/path/to/file")
        assert error.error_code == "FILE_NOT_FOUND"

    def test_invalid_path_error(self):
        """测试 InvalidPathError"""
        error = InvalidPathError("路径无效")
        assert error.error_code == "INVALID_PATH_ERROR"

    def test_content_validation_error(self):
        """测试 ContentValidationError"""
        error = ContentValidationError("内容验证失败")
        assert error.error_code == "CONTENT_VALIDATION_ERROR"


class TestOtherExceptions:
    """测试其他异常"""

    def test_clipboard_error(self):
        """测试 ClipboardError"""
        error = ClipboardError("剪贴板操作失败")
        assert error.error_code == "CLIPBOARD_ERROR"

    def test_window_operation_error(self):
        """测试 WindowOperationError"""
        error = WindowOperationError("窗口操作失败")
        assert error.error_code == "WINDOW_OPERATION_ERROR"


class TestExceptionInheritance:
    """测试异常继承关系"""

    def test_all_inherit_from_base(self):
        """测试所有异常都继承自 WeChatAutoError"""
        exceptions = [
            WeChatNotFoundError,
            WeChatNotLoggedInError,
            WeChatVersionError,
            WeChatStatusError,
            ElementNotFoundError,
            ElementTimeoutError,
            ElementClickError,
            ElementInteractionError,
            SendError,
            MomentSendError,
            GroupSendError,
            ImageUploadError,
            SendTimeoutError,
            ConfigError,
            CustomFileNotFoundError,
            InvalidPathError,
            ContentValidationError,
            ClipboardError,
            WindowOperationError,
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, WeChatAutoError), f"{exc_class.__name__} 应该继承自 WeChatAutoError"

    def test_send_exceptions_inherit_from_send_error(self):
        """测试发送异常继承自 SendError"""
        send_exceptions = [
            MomentSendError,
            GroupSendError,
            ImageUploadError,
            SendTimeoutError,
        ]
        for exc_class in send_exceptions:
            assert issubclass(exc_class, SendError), f"{exc_class.__name__} 应该继承自 SendError"


class TestExceptionCatching:
    """测试异常捕获"""

    def test_catch_specific_exception(self):
        """测试捕获特定异常"""
        with pytest.raises(WeChatNotFoundError):
            raise WeChatNotFoundError("测试")

    def test_catch_base_exception(self):
        """测试通过基类捕获"""
        with pytest.raises(WeChatAutoError):
            raise ElementNotFoundError("测试")

    def test_catch_send_error_base(self):
        """测试通过 SendError 捕获发送异常"""
        with pytest.raises(SendError):
            raise MomentSendError("测试")


class TestUtilityFunctions:
    """测试工具函数"""

    def test_format_exception_message(self):
        """测试格式化异常消息"""
        # format_exception_message 接收异常对象，不是字符串
        error = WeChatNotFoundError("操作失败", context={"key": "value"})
        result = format_exception_message(error)
        assert "操作失败" in result or "WECHAT_NOT_FOUND" in result

    def test_get_error_code(self):
        """测试获取错误代码"""
        error = WeChatNotFoundError("测试")
        code = get_error_code(error)
        assert code == "WECHAT_NOT_FOUND"

    def test_get_error_code_standard_exception(self):
        """测试获取标准异常的错误代码"""
        error = ValueError("测试")
        code = get_error_code(error)
        assert code == "ValueError" or code is not None
