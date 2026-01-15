"""
熔断器模块

实现服务熔断保护，防止系统在异常情况下持续失败
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable, List
from dataclasses import dataclass, field

from models.enums import CircuitState


logger = logging.getLogger("wechat_auto_sender.circuit_breaker")


@dataclass
class FailureRecord:
    """失败记录"""
    timestamp: datetime
    error: str


class CircuitBreaker:
    """
    熔断器

    三种状态：
    - CLOSED: 正常运行，记录失败次数
    - OPEN: 熔断状态，拒绝所有请求
    - HALF_OPEN: 半开状态，允许试探性请求

    状态转换：
    - CLOSED -> OPEN: 连续失败次数 >= failure_threshold
    - OPEN -> HALF_OPEN: 经过 recovery_timeout 时间
    - HALF_OPEN -> CLOSED: 试探请求成功
    - HALF_OPEN -> OPEN: 试探请求失败
    """

    def __init__(self, config: dict = None,
                 on_open: Callable = None,
                 on_close: Callable = None,
                 on_half_open: Callable = None):
        """
        初始化熔断器

        Args:
            config: 熔断器配置
            on_open: 熔断触发回调
            on_close: 熔断恢复回调
            on_half_open: 进入半开状态回调
        """
        self._config = config or {}
        cb_config = self._config.get("circuit_breaker", {})

        # 配置参数
        self._failure_threshold = cb_config.get("failure_threshold", 3)
        self._recovery_timeout = cb_config.get("recovery_timeout", 300)
        self._half_open_max_calls = cb_config.get("half_open_max_calls", 1)
        self._enabled = cb_config.get("enabled", True)

        # 状态
        self._state = CircuitState.CLOSED
        self._state_lock = threading.Lock()

        # 失败计数
        self._consecutive_failures = 0
        self._failure_records: List[FailureRecord] = []

        # 时间记录
        self._last_failure_time: Optional[datetime] = None
        self._open_time: Optional[datetime] = None

        # 半开状态计数
        self._half_open_calls = 0

        # 回调函数
        self._on_open = on_open
        self._on_close = on_close
        self._on_half_open = on_half_open

        # 通知回调（预留邮件通知接口）
        self._notification_callbacks: List[Callable] = []

        logger.info(f"熔断器初始化完成 (阈值: {self._failure_threshold}, "
                   f"恢复超时: {self._recovery_timeout}s)")

    def add_notification_callback(self, callback: Callable):
        """添加通知回调（用于邮件通知等）"""
        self._notification_callbacks.append(callback)

    # ==================== 核心方法 ====================

    def record_success(self) -> None:
        """
        记录成功执行

        在 CLOSED 状态：重置失败计数
        在 HALF_OPEN 状态：恢复到 CLOSED
        """
        if not self._enabled:
            return

        with self._state_lock:
            if self._state == CircuitState.CLOSED:
                # 重置连续失败计数
                self._consecutive_failures = 0

            elif self._state == CircuitState.HALF_OPEN:
                # 试探成功，恢复正常
                logger.info("熔断器: 试探成功，恢复正常运行")
                self._transition_to_closed()

    def record_failure(self, error: str = "") -> None:
        """
        记录执行失败

        Args:
            error: 错误信息
        """
        if not self._enabled:
            return

        with self._state_lock:
            now = datetime.now()

            # 记录失败
            self._consecutive_failures += 1
            self._last_failure_time = now
            self._failure_records.append(FailureRecord(timestamp=now, error=error))

            # 保留最近的失败记录
            if len(self._failure_records) > 100:
                self._failure_records = self._failure_records[-50:]

            logger.warning(f"熔断器: 记录失败 ({self._consecutive_failures}/"
                          f"{self._failure_threshold}), 错误: {error}")

            if self._state == CircuitState.CLOSED:
                # 检查是否需要熔断
                if self._consecutive_failures >= self._failure_threshold:
                    self._transition_to_open()

            elif self._state == CircuitState.HALF_OPEN:
                # 试探失败，重新熔断
                logger.warning("熔断器: 试探失败，重新进入熔断状态")
                self._transition_to_open()

    def can_execute(self) -> bool:
        """
        检查是否可以执行任务

        Returns:
            True: 可以执行
            False: 熔断中，不可执行
        """
        if not self._enabled:
            return True

        with self._state_lock:
            if self._state == CircuitState.CLOSED:
                return True

            elif self._state == CircuitState.OPEN:
                # 检查是否可以进入半开状态
                if self._should_try_reset():
                    self._transition_to_half_open()
                    return True
                return False

            elif self._state == CircuitState.HALF_OPEN:
                # 半开状态下限制调用次数
                if self._half_open_calls < self._half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

            return False

    def force_reset(self) -> None:
        """强制重置熔断器到 CLOSED 状态"""
        with self._state_lock:
            logger.info("熔断器: 强制重置")
            self._transition_to_closed()

    def get_state(self) -> CircuitState:
        """获取当前状态"""
        with self._state_lock:
            return self._state

    def get_status(self) -> dict:
        """
        获取熔断器详细状态

        Returns:
            状态字典
        """
        with self._state_lock:
            remaining_time = 0
            if self._state == CircuitState.OPEN and self._open_time:
                elapsed = (datetime.now() - self._open_time).total_seconds()
                remaining_time = max(0, self._recovery_timeout - elapsed)

            return {
                "enabled": self._enabled,
                "state": self._state.value,
                "consecutive_failures": self._consecutive_failures,
                "failure_threshold": self._failure_threshold,
                "recovery_timeout": self._recovery_timeout,
                "remaining_recovery_time": remaining_time,
                "last_failure_time": self._last_failure_time.isoformat()
                    if self._last_failure_time else None,
                "open_time": self._open_time.isoformat()
                    if self._open_time else None,
                "recent_failures": [
                    {"time": r.timestamp.isoformat(), "error": r.error}
                    for r in self._failure_records[-5:]
                ]
            }

    # ==================== 状态转换 ====================

    def _transition_to_open(self):
        """转换到 OPEN 状态（熔断）"""
        prev_state = self._state
        self._state = CircuitState.OPEN
        self._open_time = datetime.now()

        logger.error(f"熔断器: 触发熔断! 连续失败 {self._consecutive_failures} 次")

        # 调用回调
        if self._on_open:
            try:
                self._on_open()
            except Exception as e:
                logger.error(f"熔断触发回调异常: {e}")

        # 发送通知
        self._send_notification(
            event="circuit_open",
            message=f"熔断器触发: 连续失败 {self._consecutive_failures} 次",
            details=self.get_status()
        )

    def _transition_to_closed(self):
        """转换到 CLOSED 状态（恢复）"""
        prev_state = self._state
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._open_time = None
        self._half_open_calls = 0

        logger.info("熔断器: 恢复正常运行")

        # 调用回调
        if self._on_close:
            try:
                self._on_close()
            except Exception as e:
                logger.error(f"熔断恢复回调异常: {e}")

        # 发送通知
        if prev_state != CircuitState.CLOSED:
            self._send_notification(
                event="circuit_closed",
                message="熔断器恢复: 系统恢复正常运行",
                details=self.get_status()
            )

    def _transition_to_half_open(self):
        """转换到 HALF_OPEN 状态（试探）"""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0

        logger.info("熔断器: 进入半开状态，开始试探")

        # 调用回调
        if self._on_half_open:
            try:
                self._on_half_open()
            except Exception as e:
                logger.error(f"半开状态回调异常: {e}")

    def _should_try_reset(self) -> bool:
        """检查是否应该尝试恢复"""
        if not self._open_time:
            return True

        elapsed = (datetime.now() - self._open_time).total_seconds()
        return elapsed >= self._recovery_timeout

    def _send_notification(self, event: str, message: str, details: dict = None):
        """发送通知"""
        for callback in self._notification_callbacks:
            try:
                callback(event=event, message=message, details=details or {})
            except Exception as e:
                logger.error(f"通知回调异常: {e}")

    # ==================== 与队列管理器集成 ====================

    @classmethod
    def create_with_queue_manager(cls, config: dict,
                                  queue_manager) -> "CircuitBreaker":
        """
        创建与队列管理器集成的熔断器

        熔断时暂停队列，恢复时恢复队列

        Args:
            config: 配置
            queue_manager: QueueManager 实例

        Returns:
            配置好的熔断器实例
        """
        def on_open():
            logger.info("熔断触发，暂停任务队列")
            queue_manager.pause_queue()

        def on_close():
            logger.info("熔断恢复，恢复任务队列")
            queue_manager.resume_queue()

        return cls(
            config=config,
            on_open=on_open,
            on_close=on_close
        )


class CircuitBreakerContext:
    """
    熔断器上下文管理器

    用于在 with 语句中自动记录成功/失败

    使用示例:
        with CircuitBreakerContext(breaker) as can_execute:
            if can_execute:
                # 执行任务
                do_work()
            else:
                # 熔断中
                pass
    """

    def __init__(self, breaker: CircuitBreaker):
        self._breaker = breaker
        self._can_execute = False
        self._error: Optional[str] = None

    def __enter__(self) -> bool:
        """进入上下文，检查是否可执行"""
        self._can_execute = self._breaker.can_execute()
        return self._can_execute

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文，记录结果"""
        if not self._can_execute:
            return False

        if exc_type is not None:
            # 发生异常，记录失败
            self._breaker.record_failure(str(exc_val))
        else:
            # 正常完成，记录成功
            self._breaker.record_success()

        return False  # 不抑制异常

    def set_error(self, error: str):
        """手动设置错误（用于非异常的失败情况）"""
        self._error = error
        self._breaker.record_failure(error)
