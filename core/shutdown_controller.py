"""
停机控制器模块

功能:
- 处理不同级别的风控事件
- 写入停机标记文件
- 发送告警通知
- 保存状态快照
- 启动时检查停机标记
"""

import sys
import json
import time
import atexit
import signal
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.config_manager import get_config
from models.enums import RiskLevel
from core.risk_detector import RiskDetectionResult, RiskSource, get_risk_detector


logger = logging.getLogger(__name__)


# ============================================================
# 类型定义
# ============================================================

class ShutdownReason(Enum):
    """停机原因"""
    RISK_DETECTED = "risk_detected"          # 风控检测
    USER_REQUEST = "user_request"            # 用户请求
    CIRCUIT_BREAK = "circuit_break"          # 熔断触发
    SYSTEM_ERROR = "system_error"            # 系统错误
    MAINTENANCE = "maintenance"              # 维护模式


@dataclass
class ShutdownInfo:
    """停机信息"""
    shutdown_time: str
    risk_level: str
    reason: str
    event_type: str
    detail: str = ""
    screenshot_path: Optional[str] = None
    recovery_hint: str = "请检查微信账号状态后删除此文件以恢复运行"
    auto_recovery: bool = False
    recovery_after: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShutdownInfo":
        return cls(
            shutdown_time=data.get("shutdown_time", ""),
            risk_level=data.get("risk_level", "unknown"),
            reason=data.get("reason", "unknown"),
            event_type=data.get("event_type", ""),
            detail=data.get("detail", ""),
            screenshot_path=data.get("screenshot_path"),
            recovery_hint=data.get("recovery_hint", ""),
            auto_recovery=data.get("auto_recovery", False),
            recovery_after=data.get("recovery_after"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def can_auto_recover(self) -> bool:
        """是否可以自动恢复"""
        if not self.auto_recovery or not self.recovery_after:
            return False

        try:
            recovery_time = datetime.fromisoformat(self.recovery_after)
            return datetime.now() >= recovery_time
        except:
            return False


@dataclass
class StateSnapshot:
    """状态快照"""
    timestamp: str
    risk_detection: Optional[Dict[str, Any]] = None
    pending_tasks: List[str] = field(default_factory=list)
    current_task: Optional[str] = None
    statistics: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# 停机控制器
# ============================================================

class ShutdownController:
    """
    停机控制器

    负责处理风控事件、管理停机标记、发送告警
    """

    # 停机标记文件名
    SHUTDOWN_FLAG_FILE = ".shutdown_flag"

    # 状态快照文件名
    STATE_SNAPSHOT_FILE = ".state_snapshot.json"

    def __init__(self):
        """初始化停机控制器"""
        self._cache_dir = Path(get_config("paths.cache_dir", "cache"))
        self._screenshot_dir = Path(get_config("advanced.screenshot_dir", "screenshots"))

        # 确保目录存在
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # 停机标记文件路径
        self._flag_file = self._cache_dir / self.SHUTDOWN_FLAG_FILE
        self._snapshot_file = self._cache_dir / self.STATE_SNAPSHOT_FILE

        # 回调函数
        self._shutdown_callbacks: List[Callable[[ShutdownInfo], None]] = []
        self._alert_callbacks: List[Callable[[RiskDetectionResult], None]] = []

        # 风控检测器
        self._risk_detector = get_risk_detector()

        # 注册风控回调
        self._risk_detector.register_callback(self._on_risk_detected)

        # 注册退出处理
        atexit.register(self._on_exit)

        logger.debug("停机控制器初始化完成")

    # ========================================================
    # 停机标记管理
    # ========================================================

    def check_shutdown_flag(self) -> Optional[ShutdownInfo]:
        """
        检查停机标记文件

        Returns:
            停机信息，如果没有标记则返回 None
        """
        if not self._flag_file.exists():
            return None

        try:
            with open(self._flag_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            shutdown_info = ShutdownInfo.from_dict(data)

            # 检查是否可以自动恢复
            if shutdown_info.can_auto_recover:
                logger.info("停机标记已过期，自动清除")
                self.clear_shutdown_flag()
                return None

            logger.warning(
                f"检测到停机标记: 原因={shutdown_info.reason}, "
                f"级别={shutdown_info.risk_level}, "
                f"时间={shutdown_info.shutdown_time}"
            )

            return shutdown_info

        except Exception as e:
            logger.error(f"读取停机标记失败: {e}")
            return None

    def create_shutdown_flag(
        self,
        reason: str,
        level: RiskLevel,
        event_type: str = "",
        detail: str = "",
        screenshot_path: Optional[str] = None,
        auto_recovery_minutes: Optional[int] = None
    ) -> bool:
        """
        创建停机标记文件

        Args:
            reason: 停机原因
            level: 风险等级
            event_type: 事件类型
            detail: 详细信息
            screenshot_path: 截图路径
            auto_recovery_minutes: 自动恢复时间（分钟），None 表示不自动恢复

        Returns:
            是否成功创建
        """
        try:
            # 计算恢复时间
            recovery_after = None
            auto_recovery = False
            if auto_recovery_minutes and level == RiskLevel.low:
                from datetime import timedelta
                recovery_time = datetime.now() + timedelta(minutes=auto_recovery_minutes)
                recovery_after = recovery_time.isoformat()
                auto_recovery = True

            # 根据风险等级设置提示
            recovery_hints = {
                RiskLevel.critical: "账号可能已被封禁，请登录微信官网检查账号状态",
                RiskLevel.high: "检测到安全验证，请手动完成验证后删除此文件",
                RiskLevel.medium: "操作频率过高，建议等待一段时间后删除此文件恢复",
                RiskLevel.low: "发生临时错误，可尝试删除此文件重新启动",
            }

            shutdown_info = ShutdownInfo(
                shutdown_time=datetime.now().isoformat(),
                risk_level=level.value,
                reason=reason,
                event_type=event_type,
                detail=detail,
                screenshot_path=screenshot_path,
                recovery_hint=recovery_hints.get(level, "请检查微信状态后删除此文件"),
                auto_recovery=auto_recovery,
                recovery_after=recovery_after,
            )

            with open(self._flag_file, "w", encoding="utf-8") as f:
                json.dump(shutdown_info.to_dict(), f, ensure_ascii=False, indent=2)

            logger.warning(f"已创建停机标记: {self._flag_file}")
            logger.warning(f"停机原因: {reason}, 级别: {level.value}")

            # 触发回调
            for callback in self._shutdown_callbacks:
                try:
                    callback(shutdown_info)
                except Exception as e:
                    logger.error(f"停机回调执行失败: {e}")

            return True

        except Exception as e:
            logger.error(f"创建停机标记失败: {e}")
            return False

    def clear_shutdown_flag(self) -> bool:
        """
        清除停机标记文件

        Returns:
            是否成功清除
        """
        if not self._flag_file.exists():
            return True

        try:
            self._flag_file.unlink()
            logger.info("停机标记已清除")
            return True

        except Exception as e:
            logger.error(f"清除停机标记失败: {e}")
            return False

    def is_shutdown_required(self) -> bool:
        """检查是否需要停机"""
        return self._flag_file.exists()

    # ========================================================
    # 风控事件处理
    # ========================================================

    def handle_risk_event(self, risk: RiskDetectionResult) -> None:
        """
        处理风控事件

        Args:
            risk: 风控检测结果
        """
        if not risk.detected:
            return

        logger.warning(
            f"处理风控事件: 级别={risk.risk_level.value if risk.risk_level else 'unknown'}, "
            f"来源={risk.source.value if risk.source else 'unknown'}, "
            f"关键词='{risk.keyword}'"
        )

        # 保存状态快照
        self._save_state_snapshot(risk)

        # 发送告警
        self._send_alert(risk)

        # 根据风险等级决定是否停机
        if risk.requires_shutdown:
            event_type = risk.source.value if risk.source else "unknown"
            self.create_shutdown_flag(
                reason=ShutdownReason.RISK_DETECTED.value,
                level=risk.risk_level,
                event_type=event_type,
                detail=risk.detail,
                screenshot_path=risk.screenshot_path,
            )

            # 执行优雅停机
            self._graceful_shutdown(risk)

    def _on_risk_detected(self, risk: RiskDetectionResult) -> None:
        """风控检测回调"""
        if risk.detected and risk.requires_shutdown:
            self.handle_risk_event(risk)

    # ========================================================
    # 告警通知
    # ========================================================

    def _send_alert(self, risk: RiskDetectionResult) -> None:
        """发送告警通知"""
        # 触发告警回调
        for callback in self._alert_callbacks:
            try:
                callback(risk)
            except Exception as e:
                logger.error(f"告警回调执行失败: {e}")

        # 记录告警日志
        logger.critical(
            f"[风控告警] 级别: {risk.risk_level.value if risk.risk_level else 'unknown'}, "
            f"关键词: '{risk.keyword}', 详情: {risk.detail}"
        )

        # TODO: 集成邮件通知
        # 这里可以调用 notification_manager 发送邮件
        # from services.notification_manager import send_risk_alert
        # send_risk_alert(risk)

    def register_alert_callback(
        self,
        callback: Callable[[RiskDetectionResult], None]
    ) -> None:
        """注册告警回调"""
        self._alert_callbacks.append(callback)

    def register_shutdown_callback(
        self,
        callback: Callable[[ShutdownInfo], None]
    ) -> None:
        """注册停机回调"""
        self._shutdown_callbacks.append(callback)

    # ========================================================
    # 状态快照
    # ========================================================

    def _save_state_snapshot(self, risk: Optional[RiskDetectionResult] = None) -> bool:
        """
        保存状态快照

        Args:
            risk: 风控检测结果

        Returns:
            是否成功保存
        """
        try:
            snapshot = StateSnapshot(
                timestamp=datetime.now().isoformat(),
                risk_detection=risk.to_dict() if risk else None,
                pending_tasks=[],  # TODO: 从任务管理器获取
                current_task=None,  # TODO: 从任务管理器获取
                statistics={},      # TODO: 从统计管理器获取
            )

            with open(self._snapshot_file, "w", encoding="utf-8") as f:
                json.dump(asdict(snapshot), f, ensure_ascii=False, indent=2)

            logger.debug(f"状态快照已保存: {self._snapshot_file}")
            return True

        except Exception as e:
            logger.error(f"保存状态快照失败: {e}")
            return False

    def load_state_snapshot(self) -> Optional[StateSnapshot]:
        """加载状态快照"""
        if not self._snapshot_file.exists():
            return None

        try:
            with open(self._snapshot_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            return StateSnapshot(**data)

        except Exception as e:
            logger.error(f"加载状态快照失败: {e}")
            return None

    def clear_state_snapshot(self) -> bool:
        """清除状态快照"""
        if not self._snapshot_file.exists():
            return True

        try:
            self._snapshot_file.unlink()
            return True
        except Exception as e:
            logger.error(f"清除状态快照失败: {e}")
            return False

    # ========================================================
    # 优雅停机
    # ========================================================

    def _graceful_shutdown(self, risk: RiskDetectionResult) -> None:
        """
        执行优雅停机

        Args:
            risk: 触发停机的风控事件
        """
        logger.warning("正在执行优雅停机...")

        try:
            # 1. 保存当前状态
            self._save_state_snapshot(risk)

            # 2. 停止所有正在进行的操作
            # TODO: 通知任务调度器停止

            # 3. 关闭弹窗（如果有）
            if risk.popup_info and risk.popup_info.window:
                try:
                    # 尝试按 Escape 关闭
                    risk.popup_info.window.SendKeys("{Escape}")
                except:
                    pass

            # 4. 记录停机日志
            logger.critical(
                f"程序已停机 - 原因: {risk.detail}, "
                f"级别: {risk.risk_level.value if risk.risk_level else 'unknown'}"
            )

        except Exception as e:
            logger.error(f"优雅停机过程中出错: {e}")

    def _on_exit(self) -> None:
        """程序退出时的清理"""
        logger.debug("程序退出，执行清理...")
        # 这里可以添加退出前的清理逻辑

    def request_shutdown(
        self,
        reason: ShutdownReason = ShutdownReason.USER_REQUEST,
        detail: str = ""
    ) -> None:
        """
        请求停机

        Args:
            reason: 停机原因
            detail: 详细信息
        """
        logger.info(f"收到停机请求: {reason.value}")

        self.create_shutdown_flag(
            reason=reason.value,
            level=RiskLevel.low,
            event_type=reason.value,
            detail=detail or f"用户请求停机: {reason.value}",
        )

    # ========================================================
    # 启动检查
    # ========================================================

    def startup_check(self) -> tuple[bool, Optional[ShutdownInfo]]:
        """
        启动时检查

        Returns:
            (是否可以启动, 停机信息)
        """
        shutdown_info = self.check_shutdown_flag()

        if shutdown_info:
            logger.error(
                f"检测到停机标记，程序无法启动。\n"
                f"停机时间: {shutdown_info.shutdown_time}\n"
                f"停机原因: {shutdown_info.reason}\n"
                f"风险等级: {shutdown_info.risk_level}\n"
                f"恢复提示: {shutdown_info.recovery_hint}\n"
                f"标记文件: {self._flag_file}"
            )
            return False, shutdown_info

        logger.info("启动检查通过，无停机标记")
        return True, None

    def force_start(self) -> bool:
        """
        强制启动（清除停机标记）

        Returns:
            是否成功
        """
        logger.warning("强制启动，清除停机标记")
        return self.clear_shutdown_flag()


# ============================================================
# 便捷函数
# ============================================================

_controller: Optional[ShutdownController] = None


def get_shutdown_controller() -> ShutdownController:
    """获取停机控制器单例"""
    global _controller
    if _controller is None:
        _controller = ShutdownController()
    return _controller


def check_can_start() -> tuple[bool, Optional[ShutdownInfo]]:
    """检查是否可以启动"""
    return get_shutdown_controller().startup_check()


def create_shutdown_flag(
    reason: str,
    level: RiskLevel,
    detail: str = ""
) -> bool:
    """创建停机标记"""
    return get_shutdown_controller().create_shutdown_flag(
        reason=reason,
        level=level,
        detail=detail,
    )


def clear_shutdown_flag() -> bool:
    """清除停机标记"""
    return get_shutdown_controller().clear_shutdown_flag()


def handle_risk(risk: RiskDetectionResult) -> None:
    """处理风控事件"""
    get_shutdown_controller().handle_risk_event(risk)


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=== 停机控制器测试 ===\n")

    controller = ShutdownController()

    # 1. 启动检查
    print("1. 启动检查...")
    can_start, info = controller.startup_check()
    print(f"   可以启动: {can_start}")
    if info:
        print(f"   停机信息: {info.to_dict()}")

    # 2. 创建停机标记测试
    print("\n2. 创建停机标记...")
    controller.create_shutdown_flag(
        reason="test",
        level=RiskLevel.medium,
        event_type="测试事件",
        detail="这是一个测试停机标记",
    )

    # 3. 检查停机标记
    print("\n3. 检查停机标记...")
    info = controller.check_shutdown_flag()
    if info:
        print(f"   停机信息: {json.dumps(info.to_dict(), ensure_ascii=False, indent=2)}")

    # 4. 清除停机标记
    print("\n4. 清除停机标记...")
    controller.clear_shutdown_flag()

    # 5. 再次检查
    print("\n5. 再次检查...")
    can_start, info = controller.startup_check()
    print(f"   可以启动: {can_start}")

    # 6. 测试风控事件处理
    print("\n6. 测试风控事件处理...")
    test_risk = RiskDetectionResult(
        detected=True,
        risk_level=RiskLevel.high,
        source=RiskSource.POPUP_CONTENT,
        keyword="安全验证",
        detail="检测到安全验证弹窗",
    )
    controller.handle_risk_event(test_risk)

    # 7. 最终检查
    print("\n7. 最终状态...")
    info = controller.check_shutdown_flag()
    if info:
        print(f"   已创建停机标记: {info.reason}")
        print(f"   恢复提示: {info.recovery_hint}")

    # 清理测试
    print("\n8. 清理测试标记...")
    controller.clear_shutdown_flag()
    print("   已清理")

    print("\n测试完成")
