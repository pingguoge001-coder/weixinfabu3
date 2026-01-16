"""
配置管理器模块

功能:
- 加载 YAML 配置文件
- 配置验证与默认值
- 敏感信息加密存储
- 配置热更新监听
"""

import os
import re
import sys
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Callable, List
from dataclasses import dataclass, field
from copy import deepcopy

import yaml
from cryptography.fernet import Fernet, InvalidToken
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent


logger = logging.getLogger(__name__)


# ============================================================
# 默认配置
# ============================================================

DEFAULT_CONFIG: Dict[str, Any] = {
    "activation": {
        "app_key": "",
        "app_secret": "",
    },
    "paths": {
        "shared_folder": "D:/wechat-publish/shared",
        "cache_dir": "D:/wechat-publish/cache",
        "receipts_dir": "D:/wechat-publish/receipts",
        "logs_dir": "D:/wechat-publish/logs",
        "wechat_path": "",
    },
    "schedule": {
        "default_interval": 180,
        "channels": {
            "moment": {
                "enabled": True,
                "mode": "interval",
                "interval_value": 3,
                "interval_unit": "minutes",
                "fixed_times": ["09:00", "12:00", "18:00"],
                "daily_start_time": "08:00",
                "daily_end_time": "22:00",
            },
            "agent_group": {
                "enabled": True,
                "mode": "interval",
                "interval_value": 1,
                "interval_unit": "minutes",
                "fixed_times": ["09:00", "14:00", "19:00"],
                "daily_start_time": "08:00",
                "daily_end_time": "22:00",
                "extra_message": "",
                "global_group_names": [],
            },
            "customer_group": {
                "enabled": True,
                "mode": "interval",
                "interval_value": 1,
                "interval_unit": "minutes",
                "fixed_times": ["10:00", "15:00", "20:00"],
                "daily_start_time": "08:00",
                "daily_end_time": "22:00",
                "extra_message": "",
                "global_group_names": [],
            },
        },
        "random_delay_min": 0,
        "random_delay_max": 60,
        "daily_limit": 50,
        "active_hours": {"start": "08:00", "end": "22:00"},
        "work_days": [1, 2, 3, 4, 5, 6, 7],
    },
    "email": {
        "enabled": False,
        "smtp": {
            "host": "smtp.qq.com",
            "port": 465,
            "use_ssl": True,
            "use_tls": False,
        },
        "sender": {
            "address": "",
            "password": "",
            "name": "微信发布助手",
        },
        "recipients": [],
        "notify_on": {
            "success": False,
            "failure": True,
            "daily_summary": True,
            "circuit_break": True,
        },
    },
    "voice": {
        "moment_complete_enabled": False,
        "moment_complete_text": "又发了一条朋友圈，还剩{remaining}条朋友圈待发，日拱一卒，财务自由。",
        "agent_group_complete_enabled": False,
        "agent_group_complete_text": "代理群发送成功，还有{remaining}个待发送",
        "customer_group_complete_enabled": False,
        "customer_group_complete_text": "客户群发送成功，还有{remaining}个待发送",
    },
    "circuit_breaker": {
        "enabled": True,
        "failure_threshold": 3,
        "recovery_timeout": 300,
        "half_open_attempts": 1,
        "failure_count_reset": 600,
    },
    "resend": {
        "auto_resend_missed": True,
        "max_retry_count": 3,
        "retry_interval": 60,
        "exponential_backoff": True,
        "max_retry_interval": 600,
    },
    "display": {
        "min_resolution": {"width": 1920, "height": 1080},
        "primary_monitor_only": True,
        "check_dpi_scaling": True,
        "recommended_dpi": 100,
    },
    "image_processing": {
        "auto_compress": True,
        "compress_quality": 85,
        "max_size": {"width": 2048, "height": 2048},
        "max_file_size_mb": 10,
        "supported_formats": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
        "convert_heic": True,
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "max_file_size_mb": 10,
        "backup_count": 30,
        "console_output": True,
    },
    "automation": {
        "wechat_version": "v3.9.11",
        "timeout": {
            "element_wait": 10,
            "window_wait": 15,
            "upload_wait": 30,
            "publish_wait": 20,
        },
        "delay": {
            "click": 100,
            "type": 50,
            "scroll": 200,
            "action": 500,
        },
        "wait": {
            "moment_upload_dialog_step": 1.0,
            "moment_upload_dialog_post_enter": 2.0,
            "moment_view_load": 1.0,
        },
    },
    "security": {
        "key_file": ".secret.key",
        "allow_plain_password": False,
    },
    "advanced": {
        "debug_mode": False,
        "save_screenshots": False,
        "screenshot_dir": "D:/wechat-publish/screenshots",
        "max_concurrent_tasks": 1,
        "process_priority": "normal",
    },
}

DEFAULT_SELECTORS: Dict[str, Any] = {
    "default_version": "v3.9.11",
    "search_strategy": {
        "priority": ["automation_id", "name", "class_name", "control_type", "index"],
        "fuzzy_match": {"enabled": True, "threshold": 0.8},
        "timeout": 10,
        "retry_interval": 500,
        "max_retries": 3,
    },
}


# ============================================================
# 加密管理器
# ============================================================

class EncryptionManager:
    """敏感信息加密管理器"""

    # 加密值的前缀标识
    ENCRYPTED_PREFIX = "ENC("
    ENCRYPTED_SUFFIX = ")"

    def __init__(self, key_file: str = ".secret.key"):
        """
        初始化加密管理器

        Args:
            key_file: 密钥文件路径
        """
        self.key_file = Path(key_file)
        self._fernet: Optional[Fernet] = None
        self._load_or_create_key()

    def _load_or_create_key(self) -> None:
        """加载或创建加密密钥"""
        if self.key_file.exists():
            try:
                key = self.key_file.read_bytes()
                self._fernet = Fernet(key)
                logger.debug(f"已加载加密密钥: {self.key_file}")
            except Exception as e:
                logger.error(f"加载密钥失败: {e}")
                self._create_new_key()
        else:
            self._create_new_key()

    def _create_new_key(self) -> None:
        """创建新的加密密钥"""
        key = Fernet.generate_key()
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        self.key_file.write_bytes(key)
        self._fernet = Fernet(key)
        logger.info(f"已创建新的加密密钥: {self.key_file}")

    def encrypt(self, value: str) -> str:
        """
        加密字符串

        Args:
            value: 原始字符串

        Returns:
            加密后的字符串，格式: ENC(xxx)
        """
        if not value:
            return value

        if self.is_encrypted(value):
            return value  # 已经加密

        encrypted = self._fernet.encrypt(value.encode()).decode()
        return f"{self.ENCRYPTED_PREFIX}{encrypted}{self.ENCRYPTED_SUFFIX}"

    def decrypt(self, value: str) -> str:
        """
        解密字符串

        Args:
            value: 加密字符串，格式: ENC(xxx)

        Returns:
            解密后的原始字符串
        """
        if not value or not self.is_encrypted(value):
            return value

        # 提取加密内容
        encrypted = value[len(self.ENCRYPTED_PREFIX):-len(self.ENCRYPTED_SUFFIX)]

        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except InvalidToken:
            logger.error("解密失败: 无效的加密数据或密钥不匹配")
            return ""

    def is_encrypted(self, value: str) -> bool:
        """检查值是否已加密"""
        return (
            isinstance(value, str)
            and value.startswith(self.ENCRYPTED_PREFIX)
            and value.endswith(self.ENCRYPTED_SUFFIX)
        )


# ============================================================
# 配置验证器
# ============================================================

@dataclass
class ValidationError:
    """配置验证错误"""
    path: str
    message: str
    value: Any = None


class ConfigValidator:
    """配置验证器"""

    def __init__(self):
        self.errors: List[ValidationError] = []

    def validate(self, config: Dict[str, Any]) -> List[ValidationError]:
        """
        验证配置

        Args:
            config: 配置字典

        Returns:
            验证错误列表
        """
        self.errors = []

        # 验证路径
        self._validate_paths(config.get("paths", {}))

        # 验证调度配置
        self._validate_schedule(config.get("schedule", {}))

        # 验证邮件配置
        self._validate_email(config.get("email", {}))

        # 验证熔断器配置
        self._validate_circuit_breaker(config.get("circuit_breaker", {}))

        # 验证图片处理配置
        self._validate_image_processing(config.get("image_processing", {}))

        return self.errors

    def _validate_paths(self, paths: Dict[str, Any]) -> None:
        """验证路径配置，自动创建不存在的目录"""
        for key in ["shared_folder", "cache_dir", "receipts_dir", "logs_dir"]:
            if key in paths and paths[key]:
                path = Path(paths[key])
                # 自动创建目录（包括父目录）
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    logger.debug(f"已确保目录存在: {path}")
                except Exception as e:
                    self.errors.append(ValidationError(
                        path=f"paths.{key}",
                        message=f"无法创建目录: {e}",
                        value=paths[key]
                    ))

    def _validate_schedule(self, schedule: Dict[str, Any]) -> None:
        """验证调度配置"""
        if "default_interval" in schedule:
            interval = schedule["default_interval"]
            if not isinstance(interval, (int, float)) or interval < 10:
                self.errors.append(ValidationError(
                    path="schedule.default_interval",
                    message="检查间隔必须大于等于10秒",
                    value=interval
                ))

        if "daily_limit" in schedule:
            limit = schedule["daily_limit"]
            if not isinstance(limit, int) or limit < 0:
                self.errors.append(ValidationError(
                    path="schedule.daily_limit",
                    message="每日限制必须是非负整数",
                    value=limit
                ))

        # 验证时间格式
        active_hours = schedule.get("active_hours", {})
        time_pattern = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
        for key in ["start", "end"]:
            if key in active_hours:
                if not time_pattern.match(active_hours[key]):
                    self.errors.append(ValidationError(
                        path=f"schedule.active_hours.{key}",
                        message="时间格式无效，应为 HH:MM",
                        value=active_hours[key]
                    ))

    def _validate_email(self, email: Dict[str, Any]) -> None:
        """验证邮件配置"""
        if not email.get("enabled", False):
            return

        smtp = email.get("smtp", {})
        if "port" in smtp:
            port = smtp["port"]
            if not isinstance(port, int) or port < 1 or port > 65535:
                self.errors.append(ValidationError(
                    path="email.smtp.port",
                    message="端口号必须在 1-65535 之间",
                    value=port
                ))

        sender = email.get("sender", {})
        if sender.get("address"):
            email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
            if not email_pattern.match(sender["address"]):
                self.errors.append(ValidationError(
                    path="email.sender.address",
                    message="邮箱地址格式无效",
                    value=sender["address"]
                ))

    def _validate_circuit_breaker(self, cb: Dict[str, Any]) -> None:
        """验证熔断器配置"""
        if "failure_threshold" in cb:
            threshold = cb["failure_threshold"]
            if not isinstance(threshold, int) or threshold < 1:
                self.errors.append(ValidationError(
                    path="circuit_breaker.failure_threshold",
                    message="失败阈值必须是正整数",
                    value=threshold
                ))

        if "recovery_timeout" in cb:
            timeout = cb["recovery_timeout"]
            if not isinstance(timeout, (int, float)) or timeout < 0:
                self.errors.append(ValidationError(
                    path="circuit_breaker.recovery_timeout",
                    message="恢复超时必须是非负数",
                    value=timeout
                ))

    def _validate_image_processing(self, img: Dict[str, Any]) -> None:
        """验证图片处理配置"""
        if "compress_quality" in img:
            quality = img["compress_quality"]
            if not isinstance(quality, int) or quality < 1 or quality > 100:
                self.errors.append(ValidationError(
                    path="image_processing.compress_quality",
                    message="压缩质量必须在 1-100 之间",
                    value=quality
                ))


# ============================================================
# 配置文件监听器
# ============================================================

class ConfigFileHandler(FileSystemEventHandler):
    """配置文件变更处理器"""

    def __init__(self, config_manager: "ConfigManager", config_file: str):
        super().__init__()
        self.config_manager = config_manager
        self.config_file = Path(config_file).name
        self._last_modified = 0
        self._debounce_interval = 1.0  # 防抖间隔(秒)

    def on_modified(self, event: FileModifiedEvent) -> None:
        """文件修改事件"""
        if event.is_directory:
            return

        if Path(event.src_path).name == self.config_file:
            current_time = time.time()
            # 防抖处理
            if current_time - self._last_modified > self._debounce_interval:
                self._last_modified = current_time
                logger.info(f"检测到配置文件变更: {self.config_file}")
                self.config_manager._on_config_changed(self.config_file)


class SelectorFileHandler(FileSystemEventHandler):
    """选择器配置文件变更处理器"""

    def __init__(self, config_manager: "ConfigManager", selectors_file: str):
        super().__init__()
        self.config_manager = config_manager
        self.selectors_file = Path(selectors_file).name
        self._last_modified = 0
        self._debounce_interval = 1.0

    def on_modified(self, event: FileModifiedEvent) -> None:
        """文件修改事件"""
        if event.is_directory:
            return

        if Path(event.src_path).name == self.selectors_file:
            current_time = time.time()
            if current_time - self._last_modified > self._debounce_interval:
                self._last_modified = current_time
                logger.info(f"检测到选择器配置变更: {self.selectors_file}")
                self.config_manager._on_selectors_changed(self.selectors_file)


# ============================================================
# 配置管理器
# ============================================================

class ConfigManager:
    """
    配置管理器

    特性:
    - 加载 YAML 配置
    - 配置验证与默认值合并
    - 敏感信息加密存储
    - 配置热更新监听
    """

    _instance: Optional["ConfigManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        config_file: str = "config.yaml",
        selectors_file: str = "selectors.yaml",
        auto_watch: bool = True,
    ):
        """
        初始化配置管理器

        Args:
            config_file: 主配置文件路径
            selectors_file: 选择器配置文件路径
            auto_watch: 是否自动监听配置变更
        """
        # 避免重复初始化
        if hasattr(self, "_initialized") and self._initialized:
            return

        # 获取配置文件目录（兼容打包后的情况）
        if getattr(sys, 'frozen', False):
            # 打包后优先从可执行文件目录读取配置
            exe_dir = Path(sys.executable).parent
            internal_dir = exe_dir / "_internal"
            meipass_dir = Path(getattr(sys, "_MEIPASS", exe_dir))
            candidates = [exe_dir, internal_dir, meipass_dir]
        else:
            # 开发环境运行
            candidates = [Path(__file__).parent.parent]

        def resolve_path(filename: str) -> Path:
            for base in candidates:
                try:
                    candidate = base / filename
                    if candidate.exists():
                        return candidate
                except Exception:
                    continue
            # 找不到就回退到第一个候选
            return candidates[0] / filename

        self.config_file = resolve_path(config_file)
        self.selectors_file = resolve_path(selectors_file)

        self._config: Dict[str, Any] = {}
        self._selectors: Dict[str, Any] = {}
        self._config_lock = threading.RLock()
        self._selectors_lock = threading.RLock()

        self._encryption: Optional[EncryptionManager] = None
        self._validator = ConfigValidator()

        self._observers: List[Observer] = []
        self._change_callbacks: List[Callable[[str, Dict], None]] = []

        # 加载配置
        self._load_config()
        self._load_selectors()

        # 初始化加密管理器
        key_file = self._config.get("security", {}).get("key_file", ".secret.key")
        self._encryption = EncryptionManager(key_file)

        # 启动文件监听
        if auto_watch:
            self._start_watching()

        self._initialized = True
        logger.info("配置管理器初始化完成")

    def _load_config(self) -> None:
        """加载主配置文件"""
        with self._config_lock:
            # 从默认配置开始
            self._config = deepcopy(DEFAULT_CONFIG)

            if self.config_file.exists():
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        user_config = yaml.safe_load(f) or {}

                    # 合并用户配置
                    self._merge_config(self._config, user_config)
                    logger.info(f"已加载配置文件: {self.config_file}")

                except yaml.YAMLError as e:
                    logger.error(f"配置文件解析失败: {e}")
                except Exception as e:
                    logger.error(f"加载配置文件失败: {e}")
            else:
                logger.warning(f"配置文件不存在，使用默认配置: {self.config_file}")

            # 验证配置
            errors = self._validator.validate(self._config)
            for error in errors:
                logger.warning(f"配置验证警告 [{error.path}]: {error.message}")

    def _load_selectors(self) -> None:
        """加载选择器配置"""
        with self._selectors_lock:
            self._selectors = deepcopy(DEFAULT_SELECTORS)

            if self.selectors_file.exists():
                try:
                    with open(self.selectors_file, "r", encoding="utf-8") as f:
                        user_selectors = yaml.safe_load(f) or {}

                    # 处理版本继承
                    self._process_selector_inheritance(user_selectors)

                    # 合并选择器配置
                    self._merge_config(self._selectors, user_selectors)
                    logger.info(f"已加载选择器配置: {self.selectors_file}")

                except yaml.YAMLError as e:
                    logger.error(f"选择器配置解析失败: {e}")
                except Exception as e:
                    logger.error(f"加载选择器配置失败: {e}")
            else:
                logger.warning(f"选择器配置不存在: {self.selectors_file}")

    def _process_selector_inheritance(self, selectors: Dict[str, Any]) -> None:
        """处理选择器版本继承"""
        versions = [k for k in selectors.keys() if k.startswith("v")]

        for version in versions:
            version_config = selectors.get(version, {})
            inherit_from = version_config.pop("_inherit", None)

            if inherit_from and inherit_from in selectors:
                # 深度合并继承的配置
                parent_config = deepcopy(selectors[inherit_from])
                self._merge_config(parent_config, version_config)
                selectors[version] = parent_config

    def _merge_config(self, base: Dict, override: Dict) -> None:
        """递归合并配置"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _start_watching(self) -> None:
        """启动配置文件监听"""
        try:
            # 监听主配置文件
            if self.config_file.exists():
                config_observer = Observer()
                config_handler = ConfigFileHandler(self, str(self.config_file))
                config_observer.schedule(
                    config_handler,
                    str(self.config_file.parent),
                    recursive=False
                )
                config_observer.start()
                self._observers.append(config_observer)
                logger.debug(f"已启动配置文件监听: {self.config_file}")

            # 监听选择器配置文件
            if self.selectors_file.exists():
                selectors_observer = Observer()
                selectors_handler = SelectorFileHandler(self, str(self.selectors_file))
                selectors_observer.schedule(
                    selectors_handler,
                    str(self.selectors_file.parent),
                    recursive=False
                )
                selectors_observer.start()
                self._observers.append(selectors_observer)
                logger.debug(f"已启动选择器配置监听: {self.selectors_file}")

        except Exception as e:
            logger.error(f"启动文件监听失败: {e}")

    def _on_config_changed(self, filename: str) -> None:
        """配置文件变更回调"""
        old_config = deepcopy(self._config)
        self._load_config()
        logger.info("配置已热更新")

        # 触发回调
        for callback in self._change_callbacks:
            try:
                callback("config", self._config)
            except Exception as e:
                logger.error(f"配置变更回调执行失败: {e}")

    def _on_selectors_changed(self, filename: str) -> None:
        """选择器配置变更回调"""
        old_selectors = deepcopy(self._selectors)
        self._load_selectors()
        logger.info("选择器配置已热更新")

        # 触发回调
        for callback in self._change_callbacks:
            try:
                callback("selectors", self._selectors)
            except Exception as e:
                logger.error(f"选择器变更回调执行失败: {e}")

    # ========================================================
    # 公共接口
    # ========================================================

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键，支持点号分隔，如 "paths.shared_folder"
            default: 默认值

        Returns:
            配置值
        """
        with self._config_lock:
            keys = key.split(".")
            value = self._config

            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default

            return value

    def get_decrypted(self, key: str, default: str = "") -> str:
        """
        获取解密后的配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            解密后的值
        """
        value = self.get(key, default)
        if isinstance(value, str) and self._encryption:
            return self._encryption.decrypt(value)
        return value

    def set(self, key: str, value: Any, save: bool = False) -> None:
        """
        设置配置值

        Args:
            key: 配置键
            value: 配置值
            save: 是否保存到文件
        """
        with self._config_lock:
            keys = key.split(".")
            config = self._config

            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]

            old_value = config.get(keys[-1])
            config[keys[-1]] = value

            logger.debug(f"配置已更新: {key} = {value} (原值: {old_value})")

            if save:
                self.save()

    def get_selector(self, path: str, version: Optional[str] = None) -> Any:
        """
        获取UI选择器

        Args:
            path: 选择器路径，如 "main_window.class_name"
            version: 微信版本，默认使用配置的版本

        Returns:
            选择器配置
        """
        with self._selectors_lock:
            if version is None:
                version = self.get("automation.wechat_version", "v3.9.11")

            # 确保版本存在
            if version not in self._selectors:
                version = self._selectors.get("default_version", "v3.9.11")

            version_selectors = self._selectors.get(version, {})

            keys = path.split(".")
            value = version_selectors

            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return None

            return value

    def get_all_config(self) -> Dict[str, Any]:
        """获取完整配置（只读副本）"""
        with self._config_lock:
            return deepcopy(self._config)

    def get_all_selectors(self) -> Dict[str, Any]:
        """获取完整选择器配置（只读副本）"""
        with self._selectors_lock:
            return deepcopy(self._selectors)

    def encrypt_value(self, value: str) -> str:
        """
        加密敏感值

        Args:
            value: 原始值

        Returns:
            加密后的值
        """
        if self._encryption:
            return self._encryption.encrypt(value)
        return value

    def decrypt_value(self, value: str) -> str:
        """
        解密敏感值

        Args:
            value: 加密值

        Returns:
            解密后的值
        """
        if self._encryption:
            return self._encryption.decrypt(value)
        return value

    def is_value_encrypted(self, value: str) -> bool:
        """
        检查值是否已加密

        Args:
            value: 待检查的值

        Returns:
            是否已加密
        """
        if self._encryption:
            return self._encryption.is_encrypted(value)
        return False

    def save(self) -> bool:
        """
        保存配置到文件

        Returns:
            是否成功
        """
        with self._config_lock:
            try:
                with open(self.config_file, "w", encoding="utf-8") as f:
                    yaml.dump(
                        self._config,
                        f,
                        default_flow_style=False,
                        allow_unicode=True,
                        sort_keys=False,
                    )
                logger.info(f"配置已保存: {self.config_file}")
                return True
            except Exception as e:
                logger.error(f"保存配置失败: {e}")
                return False

    def register_callback(self, callback: Callable[[str, Dict], None]) -> None:
        """
        注册配置变更回调

        Args:
            callback: 回调函数，参数为 (变更类型, 新配置)
        """
        self._change_callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[str, Dict], None]) -> None:
        """注销配置变更回调"""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)

    def validate(self) -> List[ValidationError]:
        """
        验证当前配置

        Returns:
            验证错误列表
        """
        return self._validator.validate(self._config)

    def ensure_directories(self) -> None:
        """确保所有配置的目录存在"""
        paths = self.get("paths", {})
        for key, path in paths.items():
            if path and key != "wechat_path":
                Path(path).mkdir(parents=True, exist_ok=True)
                logger.debug(f"已创建目录: {path}")

    # ========================================================
    # 渠道配置接口
    # ========================================================

    # 间隔单位转换常量
    INTERVAL_UNIT_MULTIPLIERS = {
        "seconds": 1,
        "minutes": 60,
        "hours": 3600,
    }

    def get_channel_schedule_mode(self, channel: str) -> str:
        """
        获取指定渠道的调度模式

        Args:
            channel: 渠道名称 (moment, agent_group, customer_group)

        Returns:
            调度模式: "interval" 或 "fixed_time"
        """
        channel_config = self.get(f"schedule.channels.{channel}", {})
        return channel_config.get("mode", "interval")

    def set_channel_schedule_mode(self, channel: str, mode: str, save: bool = True) -> None:
        """
        设置指定渠道的调度模式

        Args:
            channel: 渠道名称
            mode: 调度模式 ("interval" 或 "fixed_time")
            save: 是否保存到文件
        """
        if mode not in ("interval", "fixed_time"):
            raise ValueError(f"无效的调度模式: {mode}")
        self.set(f"schedule.channels.{channel}.mode", mode, save=save)

    def get_channel_minute_of_hour(self, channel: str) -> int:
        """
        获取指定渠道的每小时定点分钟

        Args:
            channel: 渠道名称

        Returns:
            分钟数 (0-59)
        """
        channel_config = self.get(f"schedule.channels.{channel}", {})
        return channel_config.get("minute_of_hour", 0)

    def set_channel_minute_of_hour(self, channel: str, minute: int, save: bool = True) -> None:
        """
        设置指定渠道的每小时定点分钟

        Args:
            channel: 渠道名称
            minute: 分钟数 (0-59)
            save: 是否保存到文件
        """
        minute = max(0, min(59, int(minute)))
        self.set(f"schedule.channels.{channel}.minute_of_hour", minute, save=save)

    def get_channel_interval(self, channel: str) -> tuple:
        """
        获取指定渠道的发布间隔

        Args:
            channel: 渠道名称 (moment, agent_group, customer_group)

        Returns:
            (间隔值, 间隔单位) 元组，如 (3, "minutes")
        """
        channel_config = self.get(f"schedule.channels.{channel}", {})
        value = channel_config.get("interval_value", 3)
        unit = channel_config.get("interval_unit", "minutes")
        return (value, unit)

    def get_channel_interval_seconds(self, channel: str) -> int:
        """
        获取指定渠道的发布间隔（秒）

        Args:
            channel: 渠道名称

        Returns:
            发布间隔（秒）
        """
        value, unit = self.get_channel_interval(channel)
        multiplier = self.INTERVAL_UNIT_MULTIPLIERS.get(unit, 60)
        return value * multiplier

    def set_channel_interval(self, channel: str, value: int, unit: str, save: bool = True) -> None:
        """
        设置指定渠道的发布间隔

        Args:
            channel: 渠道名称
            value: 间隔值
            unit: 间隔单位 ("seconds", "minutes", "hours")
            save: 是否保存到文件
        """
        if unit not in self.INTERVAL_UNIT_MULTIPLIERS:
            raise ValueError(f"无效的间隔单位: {unit}")
        self.set(f"schedule.channels.{channel}.interval_value", value, save=False)
        self.set(f"schedule.channels.{channel}.interval_unit", unit, save=save)

    def get_channel_fixed_times(self, channel: str) -> List[str]:
        """
        获取指定渠道的定点发布时间列表

        Args:
            channel: 渠道名称

        Returns:
            时间列表，如 ["09:00", "12:00", "18:00"]
        """
        channel_config = self.get(f"schedule.channels.{channel}", {})
        return channel_config.get("fixed_times", [])

    def set_channel_fixed_times(self, channel: str, times: List[str], save: bool = True) -> None:
        """
        设置指定渠道的定点发布时间列表

        Args:
            channel: 渠道名称
            times: 时间列表，如 ["09:00", "12:00", "18:00"]
            save: 是否保存到文件
        """
        # 验证时间格式
        import re
        time_pattern = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
        for t in times:
            if not time_pattern.match(t):
                raise ValueError(f"无效的时间格式: {t}，应为 HH:MM")
        self.set(f"schedule.channels.{channel}.fixed_times", times, save=save)

    def get_channel_daily_window(self, channel: str) -> tuple:
        """
        获取指定渠道的每日时间窗口

        Args:
            channel: 渠道名称

        Returns:
            (开始时间, 结束时间) 元组，如 ("08:00", "22:00")
        """
        channel_config = self.get(f"schedule.channels.{channel}", {})
        start = channel_config.get("daily_start_time", "08:00")
        end = channel_config.get("daily_end_time", "22:00")
        return (start, end)

    def set_channel_daily_window(self, channel: str, start: str, end: str, save: bool = True) -> None:
        """
        设置指定渠道的每日时间窗口

        Args:
            channel: 渠道名称
            start: 开始时间，如 "08:00"
            end: 结束时间，如 "22:00"
            save: 是否保存到文件
        """
        import re
        time_pattern = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
        if not time_pattern.match(start):
            raise ValueError(f"无效的开始时间格式: {start}")
        if not time_pattern.match(end):
            raise ValueError(f"无效的结束时间格式: {end}")
        self.set(f"schedule.channels.{channel}.daily_start_time", start, save=False)
        self.set(f"schedule.channels.{channel}.daily_end_time", end, save=save)

    def is_channel_enabled(self, channel: str) -> bool:
        """
        检查指定渠道是否启用

        Args:
            channel: 渠道名称

        Returns:
            是否启用
        """
        channel_config = self.get(f"schedule.channels.{channel}", {})
        return channel_config.get("enabled", True)

    def set_channel_enabled(self, channel: str, enabled: bool, save: bool = True) -> None:
        """
        设置指定渠道的启用状态

        Args:
            channel: 渠道名称
            enabled: 是否启用
            save: 是否保存到文件
        """
        self.set(f"schedule.channels.{channel}.enabled", enabled, save=save)

    def get_channel_group_names(self, channel: str) -> List[str]:
        """
        获取指定渠道的全局群名列表

        Args:
            channel: 渠道名称 (agent_group, customer_group)

        Returns:
            群名列表
        """
        channel_config = self.get(f"schedule.channels.{channel}", {})
        return channel_config.get("global_group_names", [])

    def set_channel_group_names(self, channel: str, group_names: List[str], save: bool = True) -> None:
        """
        设置指定渠道的全局群名列表

        Args:
            channel: 渠道名称
            group_names: 群名列表
            save: 是否保存到文件
        """
        self.set(f"schedule.channels.{channel}.global_group_names", group_names, save=save)

    def get_channel_extra_message(self, channel: str) -> str:
        """
        Get extra message for a built-in group channel.
        """
        channel_config = self.get(f"schedule.channels.{channel}", {})
        return channel_config.get("extra_message", "")

    def set_channel_extra_message(self, channel: str, message: str, save: bool = True) -> None:
        """
        Set extra message for a built-in group channel.
        """
        self.set(f"schedule.channels.{channel}.extra_message", message or "", save=save)

    def get_all_channel_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有渠道的配置

        Returns:
            所有渠道的完整配置字典
        """
        return self.get("schedule.channels", {})

    # ========================================================
    # 自定义渠道接口
    # ========================================================

    def get_custom_channels(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有自定义渠道配置

        Returns:
            自定义渠道配置字典，如 {"custom_1": {"name": "VIP群", ...}}
        """
        return self.get("custom_channels", {})

    def add_custom_channel(self, channel_id: str, name: str) -> bool:
        """
        添加自定义渠道

        Args:
            channel_id: 渠道ID，如 "custom_1"
            name: 渠道显示名称

        Returns:
            是否成功
        """
        channels = self.get_custom_channels()
        channels[channel_id] = {
            "name": name,
            "enabled": True,
            "global_group_names": [],
            "extra_message": "",
            "daily_start_time": "08:00",
            "daily_end_time": "22:00",
            "minute_of_hour": 0,
            "mode": "interval",
            "interval_value": 3,
            "interval_unit": "minutes",
        }
        self.set("custom_channels", channels)
        return self.save()

    def remove_custom_channel(self, channel_id: str) -> bool:
        """
        删除自定义渠道

        Args:
            channel_id: 渠道ID

        Returns:
            是否成功
        """
        channels = self.get_custom_channels()
        if channel_id in channels:
            del channels[channel_id]
            self.set("custom_channels", channels)
            return self.save()
        return False

    def get_custom_channel_name(self, channel_id: str) -> str:
        """
        获取自定义渠道名称

        Args:
            channel_id: 渠道ID

        Returns:
            渠道显示名称
        """
        channels = self.get_custom_channels()
        return channels.get(channel_id, {}).get("name", channel_id)

    def set_custom_channel_name(self, channel_id: str, name: str, save: bool = True) -> None:
        """
        设置自定义渠道名称

        Args:
            channel_id: 渠道ID
            name: 新名称
            save: 是否保存到文件
        """
        self.set(f"custom_channels.{channel_id}.name", name, save=save)

    def generate_custom_channel_id(self) -> str:
        """
        生成新的自定义渠道ID

        Returns:
            新的渠道ID，如 "custom_1"
        """
        channels = self.get_custom_channels()
        i = 1
        while f"custom_{i}" in channels:
            i += 1
        return f"custom_{i}"

    def get_custom_channel_group_names(self, channel_id: str) -> List[str]:
        """
        获取自定义渠道的群名列表

        Args:
            channel_id: 渠道ID

        Returns:
            群名列表
        """
        return self.get(f"custom_channels.{channel_id}.global_group_names", [])

    def set_custom_channel_group_names(self, channel_id: str, group_names: List[str], save: bool = True) -> None:
        """
        设置自定义渠道的群名列表

        Args:
            channel_id: 渠道ID
            group_names: 群名列表
            save: 是否保存到文件
        """
        self.set(f"custom_channels.{channel_id}.global_group_names", group_names, save=save)

    def get_custom_channel_extra_message(self, channel_id: str) -> str:
        """
        Get extra message for a custom group channel.
        """
        return self.get(f"custom_channels.{channel_id}.extra_message", "")

    def set_custom_channel_extra_message(self, channel_id: str, message: str, save: bool = True) -> None:
        """
        Set extra message for a custom group channel.
        """
        self.set(f"custom_channels.{channel_id}.extra_message", message or "", save=save)

    def get_custom_channel_daily_window(self, channel_id: str) -> tuple:
        """
        获取自定义渠道的每日时间窗口

        Args:
            channel_id: 渠道ID

        Returns:
            (开始时间, 结束时间) 元组
        """
        start = self.get(f"custom_channels.{channel_id}.daily_start_time", "08:00")
        end = self.get(f"custom_channels.{channel_id}.daily_end_time", "22:00")
        return (start, end)

    def set_custom_channel_daily_window(self, channel_id: str, start: str, end: str, save: bool = True) -> None:
        """
        设置自定义渠道的每日时间窗口

        Args:
            channel_id: 渠道ID
            start: 开始时间
            end: 结束时间
            save: 是否保存到文件
        """
        self.set(f"custom_channels.{channel_id}.daily_start_time", start, save=False)
        self.set(f"custom_channels.{channel_id}.daily_end_time", end, save=save)

    def get_custom_channel_minute_of_hour(self, channel_id: str) -> int:
        """
        获取自定义渠道的每小时定点分钟

        Args:
            channel_id: 渠道ID

        Returns:
            分钟数 (0-59)
        """
        return self.get(f"custom_channels.{channel_id}.minute_of_hour", 0)

    def set_custom_channel_minute_of_hour(self, channel_id: str, minute: int, save: bool = True) -> None:
        """
        设置自定义渠道的每小时定点分钟

        Args:
            channel_id: 渠道ID
            minute: 分钟数 (0-59)
            save: 是否保存到文件
        """
        self.set(f"custom_channels.{channel_id}.minute_of_hour", minute, save=save)

    def get_custom_channel_schedule_mode(self, channel_id: str) -> str:
        """
        获取自定义渠道的调度模式

        Args:
            channel_id: 渠道ID

        Returns:
            调度模式: "interval" 或 "fixed_time"
        """
        return self.get(f"custom_channels.{channel_id}.mode", "interval")

    def set_custom_channel_schedule_mode(self, channel_id: str, mode: str, save: bool = True) -> None:
        """
        设置自定义渠道的调度模式

        Args:
            channel_id: 渠道ID
            mode: 调度模式 ("interval" 或 "fixed_time")
            save: 是否保存到文件
        """
        if mode not in ("interval", "fixed_time"):
            raise ValueError(f"无效的调度模式: {mode}")
        self.set(f"custom_channels.{channel_id}.mode", mode, save=save)

    def get_custom_channel_interval(self, channel_id: str) -> tuple:
        """
        获取自定义渠道的发布间隔

        Args:
            channel_id: 渠道ID

        Returns:
            (间隔值, 间隔单位) 元组
        """
        value = self.get(f"custom_channels.{channel_id}.interval_value", 3)
        unit = self.get(f"custom_channels.{channel_id}.interval_unit", "minutes")
        return (value, unit)

    def set_custom_channel_interval(self, channel_id: str, value: int, unit: str, save: bool = True) -> None:
        """
        设置自定义渠道的发布间隔

        Args:
            channel_id: 渠道ID
            value: 间隔值
            unit: 间隔单位 ("seconds", "minutes", "hours")
            save: 是否保存到文件
        """
        if unit not in self.INTERVAL_UNIT_MULTIPLIERS:
            raise ValueError(f"无效的间隔单位: {unit}")
        self.set(f"custom_channels.{channel_id}.interval_value", value, save=False)
        self.set(f"custom_channels.{channel_id}.interval_unit", unit, save=save)

    def stop(self) -> None:
        """停止配置管理器"""
        for observer in self._observers:
            observer.stop()
            observer.join()
        self._observers.clear()
        logger.info("配置管理器已停止")

    def __enter__(self) -> "ConfigManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


# ============================================================
# 便捷函数
# ============================================================

_config_manager: Optional[ConfigManager] = None


def get_config_manager(
    config_file: str = "config.yaml",
    selectors_file: str = "selectors.yaml",
) -> ConfigManager:
    """
    获取配置管理器实例

    Args:
        config_file: 配置文件路径
        selectors_file: 选择器配置路径

    Returns:
        ConfigManager 实例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_file, selectors_file)
    return _config_manager


def get_config(key: str, default: Any = None) -> Any:
    """快捷获取配置值"""
    return get_config_manager().get(key, default)


def get_selector(path: str, version: Optional[str] = None) -> Any:
    """快捷获取选择器"""
    return get_config_manager().get_selector(path, version)


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 测试配置管理器
    config = ConfigManager()

    # 测试获取配置
    print("=== 配置测试 ===")
    print(f"共享文件夹: {config.get('paths.shared_folder')}")
    print(f"检查间隔: {config.get('schedule.default_interval')}秒")
    print(f"熔断阈值: {config.get('circuit_breaker.failure_threshold')}")

    # 测试加密
    print("\n=== 加密测试 ===")
    original = "my_secret_password"
    encrypted = config.encrypt_value(original)
    decrypted = config.decrypt_value(encrypted)
    print(f"原始值: {original}")
    print(f"加密后: {encrypted}")
    print(f"解密后: {decrypted}")
    print(f"加解密验证: {'通过' if original == decrypted else '失败'}")

    # 测试选择器
    print("\n=== 选择器测试 ===")
    print(f"主窗口类名: {config.get_selector('main_window.class_name')}")
    print(f"发现按钮: {config.get_selector('navigation.discover_button')}")

    # 测试验证
    print("\n=== 配置验证 ===")
    errors = config.validate()
    if errors:
        for error in errors:
            print(f"  {error.path}: {error.message}")
    else:
        print("  配置验证通过")

    # 等待热更新测试
    print("\n=== 热更新测试 ===")
    print("修改配置文件观察热更新效果 (按 Ctrl+C 退出)...")

    def on_config_change(change_type: str, new_config: Dict) -> None:
        print(f"配置已更新: {change_type}")

    config.register_callback(on_config_change)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        config.stop()
        print("\n测试结束")
