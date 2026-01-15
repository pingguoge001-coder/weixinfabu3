"""
激活码服务模块

功能:
- 生成设备唯一标识 (device_id)
- 检查激活状态 API
- 激活设备 API
- 本地缓存激活状态
- 激活状态验证
"""

import json
import logging
import platform
import uuid
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# API 配置
ACTIVATION_API = "https://pingguoge.zeabur.app/api"
REQUEST_TIMEOUT = 30  # 秒

# 本地缓存文件
CACHE_FILE = ".activation_cache.json"


@dataclass
class ActivationStatus:
    """激活状态"""
    activated: bool
    expires_at: Optional[str] = None
    days_remaining: Optional[int] = None
    device_id: Optional[str] = None
    last_check: Optional[str] = None
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """检查激活是否有效（已激活且未过期）"""
        if not self.activated:
            return False
        if self.days_remaining is not None and self.days_remaining <= 0:
            return False
        return True

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "activated": self.activated,
            "expires_at": self.expires_at,
            "days_remaining": self.days_remaining,
            "device_id": self.device_id,
            "last_check": self.last_check,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActivationStatus":
        """从字典创建"""
        return cls(
            activated=data.get("activated", False),
            expires_at=data.get("expires_at"),
            days_remaining=data.get("days_remaining"),
            device_id=data.get("device_id"),
            last_check=data.get("last_check"),
            error=data.get("error"),
        )


@dataclass
class ActivationResult:
    """激活结果"""
    success: bool
    message: str
    expires_at: Optional[str] = None
    days: Optional[int] = None


def get_device_id() -> str:
    """
    生成设备唯一标识

    使用机器名称和 UUID 命名空间生成稳定的设备 ID
    """
    node = platform.node()
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, node))


class ActivationService:
    """
    激活码服务

    提供激活状态检查、设备激活、本地缓存等功能
    """

    def __init__(self, app_key: str, app_secret: str, cache_dir: str = "."):
        """
        初始化激活服务

        Args:
            app_key: 应用密钥
            app_secret: 应用密钥
            cache_dir: 缓存目录
        """
        self.app_key = app_key
        self.app_secret = app_secret
        self.cache_file = Path(cache_dir) / CACHE_FILE
        self.device_id = get_device_id()

        logger.info(f"激活服务初始化完成，设备ID: {self.device_id[:8]}...")

    def _make_request(self, method: str, path: str, data: dict = None) -> dict:
        """
        发送 HTTP 请求

        Args:
            method: HTTP 方法
            path: API 路径
            data: 请求数据

        Returns:
            响应 JSON

        Raises:
            Exception: 请求失败
        """
        url = f"{ACTIVATION_API}{path}"

        headers = {
            "Content-Type": "application/json",
            "X-App-Key": self.app_key,
            "X-App-Secret": self.app_secret,
        }

        if method == "GET" and data:
            # GET 请求使用查询参数
            query = urllib.parse.urlencode(data)
            url = f"{url}?{query}"
            request_data = None
        else:
            request_data = json.dumps(data).encode() if data else None

        req = urllib.request.Request(
            url,
            data=request_data,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            logger.error(f"HTTP 错误 {e.code}: {error_body}")
            try:
                return json.loads(error_body)
            except json.JSONDecodeError:
                raise Exception(f"HTTP 错误 {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            logger.error(f"网络错误: {e.reason}")
            raise Exception(f"网络错误: {e.reason}")
        except Exception as e:
            logger.error(f"请求失败: {e}")
            raise

    def check_activation(self, use_cache: bool = True) -> ActivationStatus:
        """
        检查激活状态

        Args:
            use_cache: 网络失败时是否使用缓存

        Returns:
            激活状态
        """
        try:
            result = self._make_request(
                "GET",
                "/activation/check",
                {"device_id": self.device_id}
            )

            status = ActivationStatus(
                activated=result.get("activated", False),
                expires_at=result.get("expiresAt"),
                days_remaining=result.get("daysRemaining"),
                device_id=self.device_id,
                last_check=datetime.now().isoformat(),
            )

            # 保存到缓存
            self._save_cache(status)

            logger.info(f"激活状态检查成功: activated={status.activated}, days={status.days_remaining}")
            return status

        except Exception as e:
            logger.warning(f"检查激活状态失败: {e}")

            if use_cache:
                cached = self._load_cache()
                if cached:
                    cached.error = f"使用缓存 (原因: {str(e)})"
                    logger.info("使用本地缓存的激活状态")
                    return cached

            return ActivationStatus(
                activated=False,
                device_id=self.device_id,
                error=str(e),
            )

    def activate(self, code: str, user_name: str = None, phone: str = None) -> ActivationResult:
        """
        激活设备

        Args:
            code: 激活码
            user_name: 用户名（可选）
            phone: 手机号（可选）

        Returns:
            激活结果
        """
        try:
            data = {
                "code": code,
                "device_id": self.device_id,
            }
            if user_name:
                data["user_name"] = user_name
            if phone:
                data["phone"] = phone

            result = self._make_request("POST", "/activation/activate", data)

            if result.get("success"):
                # 激活成功，更新缓存
                status = ActivationStatus(
                    activated=True,
                    expires_at=result.get("expiresAt"),
                    days_remaining=result.get("days"),
                    device_id=self.device_id,
                    last_check=datetime.now().isoformat(),
                )
                self._save_cache(status)

                logger.info(f"激活成功，有效期至: {result.get('expiresAt')}")
                return ActivationResult(
                    success=True,
                    message=result.get("message", "激活成功"),
                    expires_at=result.get("expiresAt"),
                    days=result.get("days"),
                )
            else:
                logger.warning(f"激活失败: {result.get('message')}")
                return ActivationResult(
                    success=False,
                    message=result.get("message", "激活失败"),
                )

        except Exception as e:
            logger.error(f"激活请求失败: {e}")
            return ActivationResult(
                success=False,
                message=f"网络错误: {str(e)}",
            )

    def _load_cache(self) -> Optional[ActivationStatus]:
        """加载本地缓存"""
        try:
            if self.cache_file.exists():
                data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                return ActivationStatus.from_dict(data)
        except Exception as e:
            logger.warning(f"加载缓存失败: {e}")
        return None

    def _save_cache(self, status: ActivationStatus) -> bool:
        """保存到本地缓存"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(
                json.dumps(status.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            return True
        except Exception as e:
            logger.warning(f"保存缓存失败: {e}")
            return False

    def clear_cache(self) -> bool:
        """清除本地缓存"""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
            return True
        except Exception as e:
            logger.warning(f"清除缓存失败: {e}")
            return False


# 全局实例
_activation_service: Optional[ActivationService] = None


def get_activation_service(
    app_key: str = None,
    app_secret: str = None,
    cache_dir: str = "."
) -> ActivationService:
    """
    获取激活服务实例（单例）

    Args:
        app_key: 应用密钥（首次调用必须）
        app_secret: 应用密钥（首次调用必须）
        cache_dir: 缓存目录

    Returns:
        ActivationService 实例
    """
    global _activation_service
    if _activation_service is None:
        if not app_key or not app_secret:
            raise ValueError("首次初始化必须提供 app_key 和 app_secret")
        _activation_service = ActivationService(app_key, app_secret, cache_dir)
    return _activation_service


def init_activation_service(app_key: str, app_secret: str, cache_dir: str = ".") -> ActivationService:
    """
    初始化激活服务

    Args:
        app_key: 应用密钥
        app_secret: 应用密钥
        cache_dir: 缓存目录

    Returns:
        ActivationService 实例
    """
    global _activation_service
    _activation_service = ActivationService(app_key, app_secret, cache_dir)
    return _activation_service
