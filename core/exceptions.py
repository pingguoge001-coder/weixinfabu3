"""
自定义异常模块

为微信自动化项目定义完整的异常层次结构，包括：
- 微信相关异常（进程、窗口、登录状态、版本）
- UI 元素异常（查找失败、超时、点击失败）
- 发送相关异常（朋友圈、群发、图片上传）
- 配置和文件异常

每个异常类包含：
- 清晰的文档说明
- error_code 属性用于日志和错误追踪
- 上下文信息支持（元素名称、文件路径等）
- 友好的错误消息格式化
"""

from typing import Optional, Any, Dict


# ============================================================
# 基础异常类
# ============================================================

class WeChatAutoError(Exception):
    """
    微信自动化基础异常类

    所有自定义异常的基类，提供统一的错误处理接口。

    Attributes:
        error_code: 错误代码，用于日志记录和错误追踪
        message: 错误消息
        context: 额外的上下文信息字典
    """

    error_code: str = "UNKNOWN_ERROR"

    def __init__(self, message: str = "", context: Optional[Dict[str, Any]] = None):
        """
        初始化异常

        Args:
            message: 错误消息
            context: 上下文信息字典（可选）
        """
        self.message = message or self.get_default_message()
        self.context = context or {}
        super().__init__(self.message)

    def get_default_message(self) -> str:
        """获取默认错误消息"""
        return "微信自动化操作失败"

    def __str__(self) -> str:
        """返回友好的错误消息"""
        parts = [f"[{self.error_code}] {self.message}"]

        # 添加上下文信息
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"({context_str})")

        return " ".join(parts)

    def __repr__(self) -> str:
        """返回详细的异常表示"""
        return f"{self.__class__.__name__}(error_code='{self.error_code}', message='{self.message}', context={self.context})"


# ============================================================
# 微信相关异常
# ============================================================

class WeChatNotFoundError(WeChatAutoError):
    """
    微信进程或窗口未找到异常

    当无法找到微信进程或主窗口时抛出。

    Example:
        raise WeChatNotFoundError("未找到微信主窗口", context={"class_name": "WeChatMainWndForPC"})
    """

    error_code = "WECHAT_NOT_FOUND"

    def get_default_message(self) -> str:
        return "未找到微信进程或窗口"


class WeChatNotLoggedInError(WeChatAutoError):
    """
    微信未登录异常

    当检测到微信未登录状态时抛出。

    Example:
        raise WeChatNotLoggedInError("请先登录微信", context={"status": "NOT_LOGGED_IN"})
    """

    error_code = "WECHAT_NOT_LOGGED_IN"

    def get_default_message(self) -> str:
        return "微信未登录，请先登录"


class WeChatVersionError(WeChatAutoError):
    """
    微信版本不支持异常

    当检测到微信版本不支持当前操作时抛出。

    Example:
        raise WeChatVersionError("不支持的微信版本", context={"version": "2.x", "required": "3.x+"})
    """

    error_code = "WECHAT_VERSION_ERROR"

    def get_default_message(self) -> str:
        return "微信版本不支持"


class WeChatStatusError(WeChatAutoError):
    """
    微信状态异常

    当微信处于异常状态（如锁定、崩溃等）时抛出。

    Example:
        raise WeChatStatusError("微信已锁定", context={"status": "LOCKED"})
    """

    error_code = "WECHAT_STATUS_ERROR"

    def get_default_message(self) -> str:
        return "微信状态异常"


# ============================================================
# UI 元素异常
# ============================================================

class ElementNotFoundError(WeChatAutoError):
    """
    UI 元素未找到异常

    当无法找到指定的 UI 元素时抛出。

    Example:
        raise ElementNotFoundError(
            "未找到消息输入框",
            context={"class_name": "mmui::XTextEdit", "search_depth": 15}
        )
    """

    error_code = "ELEMENT_NOT_FOUND"

    def __init__(
        self,
        message: str = "",
        element_name: Optional[str] = None,
        element_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            element_name: 元素名称（如 "发表按钮"）
            element_type: 元素类型（如 "ButtonControl"）
            context: 额外上下文
        """
        ctx = context or {}
        if element_name:
            ctx["element_name"] = element_name
        if element_type:
            ctx["element_type"] = element_type

        super().__init__(message, ctx)

    def get_default_message(self) -> str:
        element_name = self.context.get("element_name", "UI 元素")
        return f"未找到 UI 元素: {element_name}"


class ElementTimeoutError(WeChatAutoError):
    """
    等待元素超时异常

    当等待 UI 元素出现超时时抛出。

    Example:
        raise ElementTimeoutError(
            "等待朋友圈窗口超时",
            timeout=10,
            context={"window_class": "mmui::SNSWindow"}
        )
    """

    error_code = "ELEMENT_TIMEOUT"

    def __init__(
        self,
        message: str = "",
        timeout: Optional[int] = None,
        element_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            timeout: 超时时间（秒）
            element_name: 元素名称
            context: 额外上下文
        """
        ctx = context or {}
        if timeout is not None:
            ctx["timeout"] = timeout
        if element_name:
            ctx["element_name"] = element_name

        super().__init__(message, ctx)

    def get_default_message(self) -> str:
        timeout = self.context.get("timeout", "未知")
        element_name = self.context.get("element_name", "元素")
        return f"等待 {element_name} 超时 ({timeout} 秒)"


class ElementClickError(WeChatAutoError):
    """
    点击元素失败异常

    当无法点击指定元素时抛出。

    Example:
        raise ElementClickError(
            "点击发表按钮失败",
            element_name="发表",
            context={"reason": "元素不可见"}
        )
    """

    error_code = "ELEMENT_CLICK_ERROR"

    def __init__(
        self,
        message: str = "",
        element_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            element_name: 元素名称
            context: 额外上下文
        """
        ctx = context or {}
        if element_name:
            ctx["element_name"] = element_name

        super().__init__(message, ctx)

    def get_default_message(self) -> str:
        element_name = self.context.get("element_name", "元素")
        return f"点击 {element_name} 失败"


class ElementInteractionError(WeChatAutoError):
    """
    元素交互失败异常

    当与 UI 元素交互失败时抛出（如输入文本、拖拽等）。

    Example:
        raise ElementInteractionError(
            "输入文本失败",
            action="输入",
            context={"element": "消息输入框"}
        )
    """

    error_code = "ELEMENT_INTERACTION_ERROR"

    def __init__(
        self,
        message: str = "",
        action: Optional[str] = None,
        element_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            action: 操作类型（如 "输入"、"拖拽"）
            element_name: 元素名称
            context: 额外上下文
        """
        ctx = context or {}
        if action:
            ctx["action"] = action
        if element_name:
            ctx["element_name"] = element_name

        super().__init__(message, ctx)

    def get_default_message(self) -> str:
        action = self.context.get("action", "交互")
        element_name = self.context.get("element_name", "元素")
        return f"{action} {element_name} 失败"


# ============================================================
# 发送相关异常
# ============================================================

class SendError(WeChatAutoError):
    """
    发送失败基类

    所有发送相关异常的基类。

    Attributes:
        step: 失败的步骤（如 "添加图片"、"输入文案"）
    """

    error_code = "SEND_ERROR"

    def __init__(
        self,
        message: str = "",
        step: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            step: 失败的步骤
            context: 额外上下文
        """
        ctx = context or {}
        if step:
            ctx["step"] = step

        super().__init__(message, ctx)

    def get_default_message(self) -> str:
        step = self.context.get("step", "未知步骤")
        return f"发送失败: {step}"


class MomentSendError(SendError):
    """
    朋友圈发送失败异常

    当朋友圈发布失败时抛出。

    Example:
        raise MomentSendError(
            "朋友圈发布失败",
            step="点击发表",
            context={"content_code": "TEST001"}
        )
    """

    error_code = "MOMENT_SEND_ERROR"

    def __init__(
        self,
        message: str = "",
        step: Optional[str] = None,
        content_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            step: 失败的步骤
            content_code: 内容编号
            context: 额外上下文
        """
        ctx = context or {}
        if content_code:
            ctx["content_code"] = content_code

        super().__init__(message, step, ctx)

    def get_default_message(self) -> str:
        step = self.context.get("step", "未知步骤")
        content_code = self.context.get("content_code", "")
        if content_code:
            return f"朋友圈发布失败 [{content_code}]: {step}"
        return f"朋友圈发布失败: {step}"


class GroupSendError(SendError):
    """
    群发消息失败异常

    当向群发送消息失败时抛出。

    Example:
        raise GroupSendError(
            "群发消息失败",
            step="搜索群",
            group_name="测试群",
            context={"reason": "未找到群"}
        )
    """

    error_code = "GROUP_SEND_ERROR"

    def __init__(
        self,
        message: str = "",
        step: Optional[str] = None,
        group_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            step: 失败的步骤
            group_name: 群名称
            context: 额外上下文
        """
        ctx = context or {}
        if group_name:
            ctx["group_name"] = group_name

        super().__init__(message, step, ctx)

    def get_default_message(self) -> str:
        step = self.context.get("step", "未知步骤")
        group_name = self.context.get("group_name", "")
        if group_name:
            return f"群发消息失败 [{group_name}]: {step}"
        return f"群发消息失败: {step}"


class ImageUploadError(SendError):
    """
    图片上传失败异常

    当图片上传或添加失败时抛出。

    Example:
        raise ImageUploadError(
            "图片上传失败",
            image_path="C:/images/test.jpg",
            context={"reason": "文件不存在", "index": 1, "total": 5}
        )
    """

    error_code = "IMAGE_UPLOAD_ERROR"

    def __init__(
        self,
        message: str = "",
        image_path: Optional[str] = None,
        step: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            image_path: 图片路径
            step: 失败的步骤
            context: 额外上下文
        """
        ctx = context or {}
        if image_path:
            ctx["image_path"] = image_path

        super().__init__(message, step, ctx)

    def get_default_message(self) -> str:
        image_path = self.context.get("image_path", "")
        if image_path:
            return f"图片上传失败: {image_path}"
        return "图片上传失败"


class SendTimeoutError(SendError):
    """
    发送超时异常

    当发送操作超时时抛出。

    Example:
        raise SendTimeoutError(
            "等待发送完成超时",
            timeout=30,
            context={"step": "等待发布完成"}
        )
    """

    error_code = "SEND_TIMEOUT_ERROR"

    def __init__(
        self,
        message: str = "",
        timeout: Optional[int] = None,
        step: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            timeout: 超时时间（秒）
            step: 失败的步骤
            context: 额外上下文
        """
        ctx = context or {}
        if timeout is not None:
            ctx["timeout"] = timeout

        super().__init__(message, step, ctx)

    def get_default_message(self) -> str:
        timeout = self.context.get("timeout", "未知")
        step = self.context.get("step", "发送操作")
        return f"{step} 超时 ({timeout} 秒)"


# ============================================================
# 配置/文件异常
# ============================================================

class ConfigError(WeChatAutoError):
    """
    配置错误异常

    当配置项缺失、格式错误或值无效时抛出。

    Example:
        raise ConfigError(
            "配置项缺失",
            config_key="automation.timeout.element_wait",
            context={"expected_type": "int"}
        )
    """

    error_code = "CONFIG_ERROR"

    def __init__(
        self,
        message: str = "",
        config_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            config_key: 配置键名
            context: 额外上下文
        """
        ctx = context or {}
        if config_key:
            ctx["config_key"] = config_key

        super().__init__(message, ctx)

    def get_default_message(self) -> str:
        config_key = self.context.get("config_key", "")
        if config_key:
            return f"配置错误: {config_key}"
        return "配置错误"


class FileNotFoundError(WeChatAutoError):
    """
    文件不存在异常

    当指定的文件不存在时抛出（自定义版本，不覆盖内置 FileNotFoundError）。

    Example:
        raise FileNotFoundError(
            "图片文件不存在",
            file_path="C:/images/test.jpg",
            context={"file_type": "image"}
        )
    """

    error_code = "FILE_NOT_FOUND"

    def __init__(
        self,
        message: str = "",
        file_path: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            file_path: 文件路径
            context: 额外上下文
        """
        ctx = context or {}
        if file_path:
            ctx["file_path"] = file_path

        super().__init__(message, ctx)

    def get_default_message(self) -> str:
        file_path = self.context.get("file_path", "")
        if file_path:
            return f"文件不存在: {file_path}"
        return "文件不存在"


class InvalidPathError(WeChatAutoError):
    """
    路径无效异常

    当路径格式无效或不可访问时抛出。

    Example:
        raise InvalidPathError(
            "图片路径无效",
            path="C:/invalid/<>path/test.jpg",
            context={"reason": "包含非法字符"}
        )
    """

    error_code = "INVALID_PATH_ERROR"

    def __init__(
        self,
        message: str = "",
        path: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            path: 路径
            context: 额外上下文
        """
        ctx = context or {}
        if path:
            ctx["path"] = path

        super().__init__(message, ctx)

    def get_default_message(self) -> str:
        path = self.context.get("path", "")
        if path:
            return f"路径无效: {path}"
        return "路径无效"


class ContentValidationError(WeChatAutoError):
    """
    内容验证失败异常

    当内容验证失败时抛出（如文本为空、图片超限等）。

    Example:
        raise ContentValidationError(
            "图片数量超过限制",
            context={"max_images": 9, "actual": 12, "content_code": "TEST001"}
        )
    """

    error_code = "CONTENT_VALIDATION_ERROR"

    def __init__(
        self,
        message: str = "",
        content_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            content_code: 内容编号
            context: 额外上下文
        """
        ctx = context or {}
        if content_code:
            ctx["content_code"] = content_code

        super().__init__(message, ctx)

    def get_default_message(self) -> str:
        content_code = self.context.get("content_code", "")
        if content_code:
            return f"内容验证失败 [{content_code}]"
        return "内容验证失败"


# ============================================================
# 剪贴板异常
# ============================================================

class ClipboardError(WeChatAutoError):
    """
    剪贴板操作失败异常

    当剪贴板读取或写入失败时抛出。

    Example:
        raise ClipboardError(
            "设置剪贴板图片失败",
            operation="set_image",
            context={"image_path": "test.jpg"}
        )
    """

    error_code = "CLIPBOARD_ERROR"

    def __init__(
        self,
        message: str = "",
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            operation: 操作类型（如 "set_text", "get_image"）
            context: 额外上下文
        """
        ctx = context or {}
        if operation:
            ctx["operation"] = operation

        super().__init__(message, ctx)

    def get_default_message(self) -> str:
        operation = self.context.get("operation", "操作")
        return f"剪贴板 {operation} 失败"


# ============================================================
# 窗口操作异常
# ============================================================

class WindowOperationError(WeChatAutoError):
    """
    窗口操作失败异常

    当窗口激活、移动、调整大小等操作失败时抛出。

    Example:
        raise WindowOperationError(
            "激活窗口失败",
            operation="activate",
            context={"window_title": "微信"}
        )
    """

    error_code = "WINDOW_OPERATION_ERROR"

    def __init__(
        self,
        message: str = "",
        operation: Optional[str] = None,
        window_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            operation: 操作类型（如 "activate", "move", "resize"）
            window_name: 窗口名称
            context: 额外上下文
        """
        ctx = context or {}
        if operation:
            ctx["operation"] = operation
        if window_name:
            ctx["window_name"] = window_name

        super().__init__(message, ctx)

    def get_default_message(self) -> str:
        operation = self.context.get("operation", "操作")
        window_name = self.context.get("window_name", "窗口")
        return f"窗口 {operation} 失败: {window_name}"


# ============================================================
# 便捷函数
# ============================================================

def format_exception_message(exc: Exception) -> str:
    """
    格式化异常消息为友好的日志格式

    Args:
        exc: 异常对象

    Returns:
        格式化的错误消息
    """
    if isinstance(exc, WeChatAutoError):
        return str(exc)
    return f"[UNHANDLED] {exc.__class__.__name__}: {str(exc)}"


def get_error_code(exc: Exception) -> str:
    """
    获取异常的错误代码

    Args:
        exc: 异常对象

    Returns:
        错误代码字符串
    """
    if isinstance(exc, WeChatAutoError):
        return exc.error_code
    return "UNHANDLED_ERROR"


# ============================================================
# 示例用法
# ============================================================

if __name__ == "__main__":
    """演示异常类的使用"""

    print("=== 自定义异常模块示例 ===\n")

    # 1. 微信相关异常
    print("1. 微信相关异常:")
    try:
        raise WeChatNotFoundError(
            "未找到微信主窗口",
            context={"class_name": "WeChatMainWndForPC", "timeout": 10}
        )
    except WeChatAutoError as e:
        print(f"   {e}")
        print(f"   错误代码: {e.error_code}")
        print(f"   上下文: {e.context}\n")

    # 2. UI 元素异常
    print("2. UI 元素异常:")
    try:
        raise ElementNotFoundError(
            element_name="发表按钮",
            element_type="ButtonControl",
            context={"search_depth": 10}
        )
    except WeChatAutoError as e:
        print(f"   {e}\n")

    # 3. 发送异常
    print("3. 发送异常:")
    try:
        raise MomentSendError(
            "朋友圈发布失败",
            step="添加图片",
            content_code="TEST001",
            context={"images_added": 3, "images_failed": 2}
        )
    except WeChatAutoError as e:
        print(f"   {e}\n")

    # 4. 文件异常
    print("4. 文件异常:")
    try:
        raise FileNotFoundError(
            "图片文件不存在",
            file_path="C:/images/test.jpg",
            context={"file_type": "image", "required": True}
        )
    except WeChatAutoError as e:
        print(f"   {e}\n")

    # 5. 配置异常
    print("5. 配置异常:")
    try:
        raise ConfigError(
            "配置项缺失",
            config_key="automation.timeout.element_wait",
            context={"expected_type": "int", "default": 10}
        )
    except WeChatAutoError as e:
        print(f"   {e}\n")

    # 6. 异常格式化
    print("6. 异常格式化:")
    try:
        raise GroupSendError(
            step="搜索群",
            group_name="测试群",
            context={"reason": "未找到匹配的群"}
        )
    except Exception as e:
        print(f"   格式化: {format_exception_message(e)}")
        print(f"   错误代码: {get_error_code(e)}\n")

    print("=== 示例完成 ===")
