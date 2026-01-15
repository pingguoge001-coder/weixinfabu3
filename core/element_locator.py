"""
元素定位器模块

功能:
- 读取 selectors.yaml 配置
- 按微信版本匹配选择器
- 支持多种定位方式：AutomationId, Name, ClassName, ControlType
- 元素等待和超时处理
- 自动检测当前微信版本
- 支持选择器热更新
"""

import re
import sys
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Union
from dataclasses import dataclass
from enum import Enum
from difflib import SequenceMatcher

import uiautomation as auto

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.config_manager import get_config_manager, get_config, get_selector


logger = logging.getLogger(__name__)


# ============================================================
# 类型定义
# ============================================================

class ControlType(Enum):
    """UI 控件类型映射"""
    Button = auto.ButtonControl
    Edit = auto.EditControl
    Text = auto.TextControl
    List = auto.ListControl
    ListItem = auto.ListItemControl
    Window = auto.WindowControl
    Pane = auto.PaneControl
    Menu = auto.MenuControl
    MenuItem = auto.MenuItemControl
    Tree = auto.TreeControl
    TreeItem = auto.TreeItemControl
    Tab = auto.TabControl
    TabItem = auto.TabItemControl
    Image = auto.ImageControl
    CheckBox = auto.CheckBoxControl
    RadioButton = auto.RadioButtonControl
    ComboBox = auto.ComboBoxControl
    ScrollBar = auto.ScrollBarControl
    ProgressBar = auto.ProgressBarControl
    Slider = auto.SliderControl
    Hyperlink = auto.HyperlinkControl
    ToolBar = auto.ToolBarControl
    Custom = auto.CustomControl
    Group = auto.GroupControl
    Document = auto.DocumentControl


@dataclass
class ElementInfo:
    """元素信息"""
    control: auto.Control
    selector_name: str
    found_by: str  # 找到元素使用的定位方式
    search_time: float  # 查找耗时（秒）


@dataclass
class LocatorResult:
    """定位结果"""
    success: bool
    element: Optional[auto.Control] = None
    error: Optional[str] = None
    screenshot_path: Optional[str] = None


# ============================================================
# 元素定位器
# ============================================================

class ElementLocator:
    """
    元素定位器

    基于 selectors.yaml 配置定位微信 UI 元素
    支持多版本选择器、热更新、模糊匹配
    """

    # 控件类型字符串映射
    CONTROL_TYPE_MAP = {
        "Button": auto.ButtonControl,
        "Edit": auto.EditControl,
        "Text": auto.TextControl,
        "List": auto.ListControl,
        "ListItem": auto.ListItemControl,
        "Window": auto.WindowControl,
        "Pane": auto.PaneControl,
        "Menu": auto.MenuControl,
        "MenuItem": auto.MenuItemControl,
        "Tree": auto.TreeControl,
        "TreeItem": auto.TreeItemControl,
        "Tab": auto.TabControl,
        "TabItem": auto.TabItemControl,
        "Image": auto.ImageControl,
        "CheckBox": auto.CheckBoxControl,
        "RadioButton": auto.RadioButtonControl,
        "ComboBox": auto.ComboBoxControl,
        "ScrollBar": auto.ScrollBarControl,
        "ProgressBar": auto.ProgressBarControl,
        "Slider": auto.SliderControl,
        "Hyperlink": auto.HyperlinkControl,
        "ToolBar": auto.ToolBarControl,
        "Custom": auto.CustomControl,
        "Group": auto.GroupControl,
        "Document": auto.DocumentControl,
    }

    def __init__(self, version: Optional[str] = None):
        """
        初始化元素定位器

        Args:
            version: 微信版本，默认从配置读取或自动检测
        """
        self._config = get_config_manager()
        self._version = version or get_config("automation.wechat_version", "v4.0")
        self._selectors: Dict[str, Any] = {}
        self._search_strategy: Dict[str, Any] = {}

        self._screenshot_dir = Path(get_config("advanced.screenshot_dir", "screenshots"))
        self._save_screenshots = get_config("advanced.save_screenshots", False)

        # 加载选择器
        self._load_selectors()

        # 注册配置变更回调
        self._config.register_callback(self._on_config_changed)

        logger.debug(f"元素定位器初始化完成，微信版本: {self._version}")

    def _load_selectors(self) -> None:
        """加载选择器配置"""
        all_selectors = self._config.get_all_selectors()

        # 获取当前版本的选择器
        self._selectors = all_selectors.get(self._version, {})

        # 获取搜索策略
        self._search_strategy = all_selectors.get("search_strategy", {
            "priority": ["automation_id", "name", "class_name", "control_type"],
            "timeout": 10,
            "retry_interval": 500,
            "max_retries": 3,
            "fuzzy_match": {"enabled": True, "threshold": 0.8}
        })

        logger.debug(f"已加载选择器配置，版本: {self._version}")

    def _on_config_changed(self, change_type: str, new_config: Dict) -> None:
        """配置变更回调"""
        if change_type == "selectors":
            self._load_selectors()
            logger.info("选择器配置已热更新")

    # ========================================================
    # 版本检测
    # ========================================================

    def detect_wechat_version(self, window: Optional[auto.WindowControl] = None) -> str:
        """
        自动检测当前微信版本 (支持 3.x 和 4.0+)

        Args:
            window: 微信主窗口

        Returns:
            检测到的版本号 (如 "v4.0" 或 "v3.9.11")
        """
        # 方法1: 通过窗口类名判断大版本
        if window is None:
            # 优先检测 4.0 版本窗口
            window_v4 = auto.WindowControl(
                searchDepth=1,
                ClassName="mmui::MainWindow"
            )
            if window_v4.Exists(2, 1):
                window = window_v4
                logger.info("检测到微信 4.0+ 窗口 (mmui::MainWindow)")
                # 继续获取详细版本号
            else:
                # 检测 3.x 版本窗口
                window_v3 = auto.WindowControl(
                    searchDepth=1,
                    ClassName="WeChatMainWndForPC"
                )
                if window_v3.Exists(2, 1):
                    window = window_v3
                    logger.info("检测到微信 3.x 窗口 (WeChatMainWndForPC)")
                else:
                    logger.warning("未找到微信窗口，使用默认版本")
                    return self._version

        # 通过窗口类名判断大版本
        if window.ClassName == "mmui::MainWindow":
            base_version = "v4.0"
        else:
            base_version = "v3.9.11"

        # 方法2: 从进程信息获取详细版本号
        try:
            import subprocess
            result = subprocess.run(
                ["wmic", "process", "where", "name='WeChat.exe'", "get", "ExecutablePath"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if "WeChat.exe" in result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line and "WeChat.exe" in line:
                        exe_path = Path(line)
                        if exe_path.exists():
                            # 尝试获取文件版本
                            version = self._get_file_version(exe_path)
                            if version:
                                logger.info(f"检测到微信详细版本: {version}")
                                # 根据主版本号决定使用哪个配置
                                major_version = version.split('.')[0]
                                if int(major_version) >= 4:
                                    return "v4.0"  # 4.x 版本统一用 v4.0 配置
                                else:
                                    return f"v{version}"

        except Exception as e:
            logger.debug(f"详细版本检测失败: {e}")

        return base_version

    def _get_file_version(self, file_path: Path) -> Optional[str]:
        """
        获取文件版本信息

        Args:
            file_path: 文件路径

        Returns:
            版本号
        """
        try:
            import ctypes
            from ctypes import wintypes

            # GetFileVersionInfoSize
            version_dll = ctypes.windll.version
            size = version_dll.GetFileVersionInfoSizeW(str(file_path), None)

            if size == 0:
                return None

            # GetFileVersionInfo
            buffer = ctypes.create_string_buffer(size)
            if not version_dll.GetFileVersionInfoW(str(file_path), 0, size, buffer):
                return None

            # VerQueryValue
            p_buffer = ctypes.c_void_p()
            length = ctypes.c_uint()

            if not version_dll.VerQueryValueW(
                buffer,
                "\\",
                ctypes.byref(p_buffer),
                ctypes.byref(length)
            ):
                return None

            # 解析版本信息结构
            class VS_FIXEDFILEINFO(ctypes.Structure):
                _fields_ = [
                    ("dwSignature", wintypes.DWORD),
                    ("dwStrucVersion", wintypes.DWORD),
                    ("dwFileVersionMS", wintypes.DWORD),
                    ("dwFileVersionLS", wintypes.DWORD),
                    ("dwProductVersionMS", wintypes.DWORD),
                    ("dwProductVersionLS", wintypes.DWORD),
                    ("dwFileFlagsMask", wintypes.DWORD),
                    ("dwFileFlags", wintypes.DWORD),
                    ("dwFileOS", wintypes.DWORD),
                    ("dwFileType", wintypes.DWORD),
                    ("dwFileSubtype", wintypes.DWORD),
                    ("dwFileDateMS", wintypes.DWORD),
                    ("dwFileDateLS", wintypes.DWORD),
                ]

            info = ctypes.cast(p_buffer, ctypes.POINTER(VS_FIXEDFILEINFO)).contents

            version = (
                f"{(info.dwFileVersionMS >> 16) & 0xFFFF}."
                f"{info.dwFileVersionMS & 0xFFFF}."
                f"{(info.dwFileVersionLS >> 16) & 0xFFFF}"
            )

            return version

        except Exception as e:
            logger.debug(f"获取文件版本失败: {e}")
            return None

    def set_version(self, version: str) -> None:
        """
        设置微信版本

        Args:
            version: 版本号
        """
        self._version = version
        self._load_selectors()
        logger.info(f"已切换到版本: {version}")

    # ========================================================
    # 选择器获取
    # ========================================================

    def get_selector_config(self, selector_path: str) -> Optional[Dict[str, Any]]:
        """
        获取选择器配置

        Args:
            selector_path: 选择器路径，如 "navigation.discover_button"

        Returns:
            选择器配置字典
        """
        keys = selector_path.split(".")
        value = self._selectors

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                logger.warning(f"选择器不存在: {selector_path}")
                return None

        if isinstance(value, dict):
            return value

        return None

    # ========================================================
    # 元素查找
    # ========================================================

    def find_element(
        self,
        selector_name: str,
        parent: Optional[auto.Control] = None,
        timeout: Optional[int] = None,
        raise_error: bool = False
    ) -> Optional[auto.Control]:
        """
        根据选择器名称查找元素

        Args:
            selector_name: 选择器路径，如 "navigation.discover_button"
            parent: 父元素，默认从桌面开始查找
            timeout: 超时时间（秒）
            raise_error: 未找到时是否抛出异常

        Returns:
            找到的控件
        """
        if timeout is None:
            timeout = self._search_strategy.get("timeout", 10)

        selector = self.get_selector_config(selector_name)
        if selector is None:
            if raise_error:
                raise ValueError(f"选择器不存在: {selector_name}")
            return None

        start_time = time.time()
        element = None
        found_by = None

        # 设置搜索起点
        search_from = parent or auto.GetRootControl()

        # 确定控件类型
        control_class = self._get_control_class(selector)

        while time.time() - start_time < timeout:
            try:
                # 按优先级尝试不同定位方式
                element, found_by = self._find_by_priority(
                    selector, control_class, search_from
                )

                if element and element.Exists(0, 0):
                    search_time = time.time() - start_time
                    logger.debug(
                        f"找到元素: {selector_name}, 方式: {found_by}, "
                        f"耗时: {search_time:.2f}s"
                    )
                    return element

            except Exception as e:
                logger.debug(f"查找元素时出错: {e}")

            # 等待后重试
            retry_interval = self._search_strategy.get("retry_interval", 500) / 1000
            time.sleep(retry_interval)

        # 超时处理
        error_msg = f"元素查找超时: {selector_name} (超时 {timeout}s)"
        logger.warning(error_msg)

        # 截图保存
        if self._save_screenshots:
            self._take_error_screenshot(selector_name)

        if raise_error:
            raise TimeoutError(error_msg)

        return None

    def _get_control_class(self, selector: Dict[str, Any]) -> type:
        """
        获取控件类

        Args:
            selector: 选择器配置

        Returns:
            控件类
        """
        control_type = selector.get("control_type", "")

        if control_type and control_type in self.CONTROL_TYPE_MAP:
            return self.CONTROL_TYPE_MAP[control_type]

        return auto.Control

    def _find_by_priority(
        self,
        selector: Dict[str, Any],
        control_class: type,
        parent: auto.Control
    ) -> tuple[Optional[auto.Control], Optional[str]]:
        """
        按优先级查找元素

        Args:
            selector: 选择器配置
            control_class: 控件类
            parent: 父元素

        Returns:
            (找到的元素, 定位方式)
        """
        priority = self._search_strategy.get(
            "priority",
            ["automation_id", "name", "class_name", "control_type"]
        )

        search_depth = selector.get("search_depth", 10)
        search_kwargs = {"searchDepth": search_depth}

        # 构建搜索条件
        for method in priority:
            if method == "automation_id" and selector.get("automation_id"):
                search_kwargs["AutomationId"] = selector["automation_id"]
            elif method == "name" and selector.get("name"):
                search_kwargs["Name"] = selector["name"]
            elif method == "class_name" and selector.get("class_name"):
                search_kwargs["ClassName"] = selector["class_name"]

        # 执行查找
        try:
            if control_class == auto.Control:
                element = parent.Control(**search_kwargs)
            else:
                element = control_class(parent=parent, **search_kwargs)

            if element.Exists(0, 0):
                return element, self._get_found_by(search_kwargs)

        except Exception as e:
            logger.debug(f"主查找失败: {e}")

        # 尝试模糊匹配
        if self._search_strategy.get("fuzzy_match", {}).get("enabled", True):
            element = self._fuzzy_find(selector, parent, search_depth)
            if element:
                return element, "fuzzy_match"

        # 尝试备用选择器
        fallback = selector.get("fallback")
        if fallback:
            element, method = self._find_by_priority(fallback, control_class, parent)
            if element:
                return element, f"fallback.{method}"

        return None, None

    def _get_found_by(self, search_kwargs: Dict) -> str:
        """获取定位方式描述"""
        methods = []
        if "AutomationId" in search_kwargs:
            methods.append("AutomationId")
        if "Name" in search_kwargs:
            methods.append("Name")
        if "ClassName" in search_kwargs:
            methods.append("ClassName")
        return "+".join(methods) if methods else "unknown"

    def _fuzzy_find(
        self,
        selector: Dict[str, Any],
        parent: auto.Control,
        search_depth: int
    ) -> Optional[auto.Control]:
        """
        模糊匹配查找

        Args:
            selector: 选择器配置
            parent: 父元素
            search_depth: 搜索深度

        Returns:
            找到的元素
        """
        target_name = selector.get("name", "")
        if not target_name:
            return None

        threshold = self._search_strategy.get("fuzzy_match", {}).get("threshold", 0.8)

        try:
            # 获取所有子元素
            control_type = selector.get("control_type", "")
            if control_type and control_type in self.CONTROL_TYPE_MAP:
                children = parent.GetChildren()
            else:
                children = parent.GetChildren()

            best_match = None
            best_ratio = 0

            for child in children:
                try:
                    child_name = child.Name
                    if child_name:
                        ratio = SequenceMatcher(None, target_name, child_name).ratio()
                        if ratio > best_ratio and ratio >= threshold:
                            best_ratio = ratio
                            best_match = child
                except:
                    continue

            if best_match:
                logger.debug(f"模糊匹配成功: '{target_name}' -> '{best_match.Name}' "
                           f"(相似度: {best_ratio:.2f})")
                return best_match

        except Exception as e:
            logger.debug(f"模糊匹配失败: {e}")

        return None

    # ========================================================
    # 元素等待
    # ========================================================

    def wait_for_element(
        self,
        selector_name: str,
        timeout: Optional[int] = None,
        parent: Optional[auto.Control] = None,
        visible: bool = True
    ) -> bool:
        """
        等待元素出现

        Args:
            selector_name: 选择器名称
            timeout: 超时时间（秒）
            parent: 父元素
            visible: 是否需要可见

        Returns:
            元素是否出现
        """
        if timeout is None:
            timeout = self._search_strategy.get("timeout", 10)

        start_time = time.time()

        while time.time() - start_time < timeout:
            element = self.find_element(
                selector_name,
                parent=parent,
                timeout=1,
                raise_error=False
            )

            if element:
                if visible:
                    # 检查是否可见
                    try:
                        rect = element.BoundingRectangle
                        if rect.width() > 0 and rect.height() > 0:
                            return True
                    except:
                        pass
                else:
                    return True

            time.sleep(0.5)

        return False

    def wait_for_element_disappear(
        self,
        selector_name: str,
        timeout: Optional[int] = None,
        parent: Optional[auto.Control] = None
    ) -> bool:
        """
        等待元素消失

        Args:
            selector_name: 选择器名称
            timeout: 超时时间（秒）
            parent: 父元素

        Returns:
            元素是否已消失
        """
        if timeout is None:
            timeout = self._search_strategy.get("timeout", 10)

        start_time = time.time()

        while time.time() - start_time < timeout:
            element = self.find_element(
                selector_name,
                parent=parent,
                timeout=1,
                raise_error=False
            )

            if element is None or not element.Exists(0, 0):
                return True

            time.sleep(0.5)

        return False

    # ========================================================
    # 批量查找
    # ========================================================

    def find_elements(
        self,
        selector_name: str,
        parent: Optional[auto.Control] = None,
        timeout: Optional[int] = None
    ) -> List[auto.Control]:
        """
        查找所有匹配的元素

        Args:
            selector_name: 选择器名称
            parent: 父元素
            timeout: 超时时间

        Returns:
            匹配元素列表
        """
        if timeout is None:
            timeout = self._search_strategy.get("timeout", 10)

        selector = self.get_selector_config(selector_name)
        if selector is None:
            return []

        search_from = parent or auto.GetRootControl()
        control_class = self._get_control_class(selector)

        results = []
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # 构建搜索条件
                search_kwargs = {}
                if selector.get("name"):
                    search_kwargs["Name"] = selector["name"]
                if selector.get("class_name"):
                    search_kwargs["ClassName"] = selector["class_name"]
                if selector.get("automation_id"):
                    search_kwargs["AutomationId"] = selector["automation_id"]

                # 遍历查找
                for child in search_from.GetChildren():
                    try:
                        match = True
                        for key, value in search_kwargs.items():
                            attr = getattr(child, key, None)
                            if attr != value:
                                match = False
                                break

                        if match:
                            results.append(child)
                    except:
                        continue

                if results:
                    break

            except Exception as e:
                logger.debug(f"批量查找出错: {e}")

            time.sleep(0.5)

        return results

    # ========================================================
    # 索引查找
    # ========================================================

    def find_by_index(
        self,
        selector_name: str,
        index: int,
        parent: Optional[auto.Control] = None,
        timeout: Optional[int] = None
    ) -> Optional[auto.Control]:
        """
        按索引查找元素

        Args:
            selector_name: 选择器名称
            index: 元素索引（0开始）
            parent: 父元素
            timeout: 超时时间

        Returns:
            找到的元素
        """
        elements = self.find_elements(selector_name, parent, timeout)

        if 0 <= index < len(elements):
            return elements[index]

        return None

    # ========================================================
    # 错误处理
    # ========================================================

    def _take_error_screenshot(self, context: str) -> Optional[str]:
        """
        发生错误时截图

        Args:
            context: 上下文描述

        Returns:
            截图路径
        """
        try:
            self._screenshot_dir.mkdir(parents=True, exist_ok=True)

            filename = f"error_{context.replace('.', '_')}_{int(time.time())}.png"
            filepath = self._screenshot_dir / filename

            # 截取桌面
            auto.GetRootControl().CaptureToImage(str(filepath))

            logger.info(f"错误截图已保存: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"保存错误截图失败: {e}")
            return None

    # ========================================================
    # 调试辅助
    # ========================================================

    def print_element_tree(
        self,
        element: Optional[auto.Control] = None,
        max_depth: int = 3,
        current_depth: int = 0
    ) -> None:
        """
        打印元素树（调试用）

        Args:
            element: 起始元素
            max_depth: 最大深度
            current_depth: 当前深度
        """
        if current_depth >= max_depth:
            return

        if element is None:
            element = auto.GetRootControl()

        indent = "  " * current_depth

        try:
            info = (
                f"{indent}[{element.ControlTypeName}] "
                f"Name='{element.Name}' "
                f"Class='{element.ClassName}' "
                f"AutoId='{element.AutomationId}'"
            )
            print(info)

            for child in element.GetChildren():
                self.print_element_tree(child, max_depth, current_depth + 1)

        except Exception as e:
            print(f"{indent}Error: {e}")

    def validate_selectors(self) -> Dict[str, bool]:
        """
        验证所有选择器是否能找到元素

        Returns:
            选择器名称 -> 是否有效
        """
        results = {}

        def validate_recursive(selectors: Dict, prefix: str = ""):
            for key, value in selectors.items():
                if isinstance(value, dict):
                    # 检查是否是选择器配置
                    if any(k in value for k in ["name", "class_name", "automation_id", "control_type"]):
                        path = f"{prefix}.{key}" if prefix else key
                        element = self.find_element(path, timeout=2)
                        results[path] = element is not None
                    else:
                        # 递归检查子选择器
                        new_prefix = f"{prefix}.{key}" if prefix else key
                        validate_recursive(value, new_prefix)

        validate_recursive(self._selectors)
        return results

    # ========================================================
    # 上下文管理
    # ========================================================

    def __enter__(self) -> "ElementLocator":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._config.unregister_callback(self._on_config_changed)


# ============================================================
# 便捷函数
# ============================================================

_locator: Optional[ElementLocator] = None


def get_element_locator(version: Optional[str] = None) -> ElementLocator:
    """获取元素定位器单例"""
    global _locator
    if _locator is None:
        _locator = ElementLocator(version)
    return _locator


def find_element(
    selector_name: str,
    parent: Optional[auto.Control] = None,
    timeout: Optional[int] = None
) -> Optional[auto.Control]:
    """快捷查找元素"""
    return get_element_locator().find_element(selector_name, parent, timeout)


def wait_for_element(
    selector_name: str,
    timeout: Optional[int] = None,
    parent: Optional[auto.Control] = None
) -> bool:
    """快捷等待元素"""
    return get_element_locator().wait_for_element(selector_name, timeout, parent)


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    locator = ElementLocator()

    print("=== 元素定位器测试 ===\n")

    # 版本检测
    print("1. 检测微信版本...")
    version = locator.detect_wechat_version()
    print(f"   当前版本: {version}")

    # 切换到检测到的版本
    locator.set_version(version)

    # 查找主窗口
    print("\n2. 查找微信主窗口...")
    main_window = locator.find_element("main_window", timeout=5)
    if main_window:
        print(f"   找到窗口: {main_window.Name}")
        print(f"   类名: {main_window.ClassName}")

        # 根据版本查找不同的导航按钮
        if version.startswith("v4"):
            # 微信 4.0: 直接查找朋友圈按钮
            print("\n3. 查找朋友圈按钮 (v4.0 导航栏)...")
            moments_btn = locator.find_element(
                "navigation.moments_button",
                parent=main_window,
                timeout=5
            )
            if moments_btn:
                print(f"   找到按钮: {moments_btn.Name}")
                print(f"   类名: {moments_btn.ClassName}")
            else:
                print("   未找到朋友圈按钮")
        else:
            # 微信 3.x: 查找发现按钮
            print("\n3. 查找发现按钮 (v3.x)...")
            discover_btn = locator.find_element(
                "navigation.discover_button",
                parent=main_window,
                timeout=5
            )
            if discover_btn:
                print(f"   找到按钮: {discover_btn.Name}")
            else:
                print("   未找到发现按钮")

        # 打印元素树
        print("\n4. 主窗口元素树 (深度2):")
        locator.print_element_tree(main_window, max_depth=2)

    else:
        print("   未找到微信主窗口")

    # 验证选择器
    print("\n5. 验证部分选择器配置...")
    # 只验证关键选择器，避免全量验证太慢
    key_selectors = [
        "main_window",
        "navigation.moments_button" if version.startswith("v4") else "navigation.discover_button",
    ]
    for selector in key_selectors:
        element = locator.find_element(selector, timeout=3)
        status = "有效" if element else "无效"
        print(f"   {selector}: {status}")

    print("\n测试完成")
