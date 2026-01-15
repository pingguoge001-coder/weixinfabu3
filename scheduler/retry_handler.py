"""
重试处理器模块

实现指数退避重试策略
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Callable

from models.task import Task
from models.enums import TaskStatus
from data.database import Database


logger = logging.getLogger("wechat_auto_sender.retry_handler")


class RetryHandler:
    """
    重试处理器

    特性：
    - 指数退避策略: delay = base_delay * (2 ** retry_count)
    - 默认间隔: 10min, 20min, 40min
    - 可配置的重试条件
    - 最大重试次数限制
    """

    # 默认可重试的错误类型
    DEFAULT_RETRYABLE_ERRORS = [
        "网络超时",
        "元素未找到",
        "窗口未响应",
        "发送失败",
        "连接失败",
        "操作超时",
        "TimeoutError",
        "ConnectionError",
        "ElementNotFoundError"
    ]

    def __init__(self, db: Database, config: dict = None):
        """
        初始化重试处理器

        Args:
            db: 数据库实例
            config: 重试配置
        """
        self._db = db
        self._config = config or {}
        retry_config = self._config.get("retry", {})

        # 配置参数
        self._base_delay = retry_config.get("base_delay", 600)  # 10分钟
        self._max_delay = retry_config.get("max_delay", 3600)   # 1小时
        self._retryable_errors = retry_config.get(
            "retryable_errors",
            self.DEFAULT_RETRYABLE_ERRORS
        )

        # 每日限额（从 schedule 配置读取）
        schedule_config = self._config.get("schedule", {})
        self._daily_limit = schedule_config.get("daily_limit", 500)

        # 重试回调
        self._on_retry_scheduled: Optional[Callable] = None

        # 线程锁
        self._lock = threading.Lock()

        logger.info(f"重试处理器初始化完成 (基础延迟: {self._base_delay}s, "
                   f"最大延迟: {self._max_delay}s)")

    def set_retry_callback(self, callback: Callable):
        """设置重试调度回调"""
        self._on_retry_scheduled = callback

    # ==================== 核心方法 ====================

    def should_retry(self, task: Task, error: str = "") -> bool:
        """
        判断任务是否应该重试

        Args:
            task: 任务对象
            error: 错误信息

        Returns:
            True: 应该重试
            False: 不应重试
        """
        # 检查重试次数
        if not task.can_retry():
            logger.debug(f"任务 {task.id} 已达最大重试次数 ({task.retry_count}/{task.max_retries})")
            return False

        # 检查每日限额
        if not self._check_daily_quota():
            logger.warning(f"任务 {task.id} 无法重试: 已达每日限额")
            return False

        # 检查错误是否可重试
        if error and not self._is_retryable_error(error):
            logger.debug(f"任务 {task.id} 错误类型不可重试: {error}")
            return False

        return True

    def get_retry_delay(self, task: Task) -> int:
        """
        计算重试延迟（指数退避）

        延迟公式: base_delay * (2 ** retry_count)
        例如: 600 * 2^0 = 600s (10min)
              600 * 2^1 = 1200s (20min)
              600 * 2^2 = 2400s (40min)

        Args:
            task: 任务对象

        Returns:
            延迟秒数
        """
        delay = self._base_delay * (2 ** task.retry_count)
        # 限制最大延迟
        delay = min(delay, self._max_delay)
        return int(delay)

    def schedule_retry(self, task: Task, error: str = "") -> bool:
        """
        调度任务重试

        Args:
            task: 任务对象
            error: 错误信息

        Returns:
            是否成功调度重试
        """
        with self._lock:
            # 检查是否可以重试
            if not self.should_retry(task, error):
                return False

            # 计算重试时间
            delay = self.get_retry_delay(task)
            retry_time = datetime.now() + timedelta(seconds=delay)

            # 更新任务
            task.increment_retry()
            task.status = TaskStatus.scheduled
            task.scheduled_time = retry_time
            task.error_message = f"重试 {task.retry_count}/{task.max_retries}: {error}"

            # 保存到数据库
            self._db.update_task(task)

            logger.info(f"任务 {task.id} 已调度重试 "
                       f"(第 {task.retry_count} 次, {delay}秒后执行)")

            # 调用回调
            if self._on_retry_scheduled:
                try:
                    self._on_retry_scheduled(task, retry_time)
                except Exception as e:
                    logger.error(f"重试调度回调异常: {e}")

            return True

    def get_retryable_errors(self) -> List[str]:
        """获取可重试的错误类型列表"""
        return self._retryable_errors.copy()

    def add_retryable_error(self, error_type: str):
        """添加可重试的错误类型"""
        if error_type not in self._retryable_errors:
            self._retryable_errors.append(error_type)
            logger.info(f"添加可重试错误类型: {error_type}")

    def remove_retryable_error(self, error_type: str):
        """移除可重试的错误类型"""
        if error_type in self._retryable_errors:
            self._retryable_errors.remove(error_type)
            logger.info(f"移除可重试错误类型: {error_type}")

    # ==================== 内部方法 ====================

    def _is_retryable_error(self, error: str) -> bool:
        """
        检查错误是否可重试

        Args:
            error: 错误信息

        Returns:
            是否可重试
        """
        if not error:
            return True  # 无错误信息时默认可重试

        error_lower = error.lower()

        # 检查是否匹配可重试的错误类型
        for retryable in self._retryable_errors:
            if retryable.lower() in error_lower:
                return True

        return False

    def _check_daily_quota(self) -> bool:
        """
        检查每日限额

        Returns:
            True: 未达限额
            False: 已达限额
        """
        today_count = self._db.get_today_task_count()
        return today_count < self._daily_limit

    # ==================== 状态查询 ====================

    def get_status(self) -> dict:
        """获取重试处理器状态"""
        today_count = self._db.get_today_task_count()
        return {
            "base_delay": self._base_delay,
            "max_delay": self._max_delay,
            "daily_limit": self._daily_limit,
            "today_executed": today_count,
            "remaining_quota": max(0, self._daily_limit - today_count),
            "retryable_errors": self._retryable_errors
        }

    def get_retry_schedule(self, max_retries: int = 3) -> List[dict]:
        """
        获取重试时间表（预览）

        Args:
            max_retries: 最大重试次数

        Returns:
            重试时间表
        """
        schedule = []
        for i in range(max_retries):
            delay = min(self._base_delay * (2 ** i), self._max_delay)
            schedule.append({
                "retry_number": i + 1,
                "delay_seconds": delay,
                "delay_human": self._format_duration(delay)
            })
        return schedule

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """格式化时间间隔"""
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            return f"{seconds // 60}分钟"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes:
                return f"{hours}小时{minutes}分钟"
            return f"{hours}小时"


class RetryContext:
    """
    重试上下文管理器

    使用示例:
        with RetryContext(handler, task) as ctx:
            try:
                do_work()
                ctx.mark_success()
            except Exception as e:
                ctx.mark_failure(str(e))
    """

    def __init__(self, handler: RetryHandler, task: Task):
        self._handler = handler
        self._task = task
        self._success = False
        self._error: Optional[str] = None

    def __enter__(self) -> "RetryContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # 发生异常
            self._handler.schedule_retry(self._task, str(exc_val))
        elif not self._success and self._error:
            # 手动标记失败
            self._handler.schedule_retry(self._task, self._error)

        return False  # 不抑制异常

    def mark_success(self):
        """标记执行成功"""
        self._success = True

    def mark_failure(self, error: str):
        """标记执行失败"""
        self._success = False
        self._error = error
