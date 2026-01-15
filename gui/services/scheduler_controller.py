"""
调度器控制器模块

负责调度器的启动、暂停、状态检查等控制逻辑。
"""

import logging
from typing import Optional, Callable, Dict

from PySide6.QtCore import QObject, Signal, QTimer

from models.task import Task
from models.enums import Channel
from data.database import Database
from scheduler.task_scheduler import TaskScheduler
from scheduler.queue_manager import QueueManager
from scheduler.idempotency_manager import IdempotencyManager
from services.config_manager import get_config_manager

logger = logging.getLogger(__name__)


class SchedulerController(QObject):
    """
    调度器控制器

    功能：
    - 管理调度器的生命周期（启动/暂停/停止）
    - 检查调度器状态和队列状态
    - 管理调度配置（每小时定点分钟、时间窗口等）
    """

    # 信号定义
    status_changed = Signal(str)  # 状态消息
    queue_status_updated = Signal(dict)  # 队列状态信息
    scheduler_started = Signal()
    scheduler_paused = Signal()
    scheduler_stopped = Signal()

    def __init__(self, db: Database, config: dict = None, parent=None):
        super().__init__(parent)

        self._db = db
        self._config = config or {}
        self._is_publishing = False

        # 初始化调度器组件
        self._init_scheduler()

        # 定时器 - 检查调度器状态
        self._status_check_timer = QTimer(self)
        self._status_check_timer.timeout.connect(self._check_status)
        self._status_check_interval = 5000  # 5秒

    def _init_scheduler(self):
        """初始化调度器组件"""
        # 队列管理器
        self._queue_manager = QueueManager(self._db, self._config)

        # 幂等性管理器
        self._idempotency_manager = IdempotencyManager(self._db, self._config)

        # 任务调度器
        self._scheduler = TaskScheduler(
            self._db,
            self._queue_manager,
            self._idempotency_manager,
            self._config
        )

        logger.info("调度器组件初始化完成")

    def set_task_executor(self, executor: Callable[[Task], None]):
        """
        设置任务执行器

        Args:
            executor: 任务执行函数，接收Task参数
        """
        self._scheduler.set_task_executor(executor)

    def set_task_callbacks(self, on_complete: Callable = None, on_failed: Callable = None):
        """
        设置任务回调

        Args:
            on_complete: 任务完成回调
            on_failed: 任务失败回调
        """
        self._queue_manager.set_callbacks(
            on_complete=on_complete,
            on_failed=on_failed
        )

    def _ensure_scheduler_started(self) -> bool:
        """确保调度器已启动"""
        if not self._scheduler.is_running():
            self._scheduler.start_scheduler()
            return True
        return False

    def _has_running_channels(self) -> bool:
        """检查是否有渠道处于运行状态"""
        return any(cq.is_running for cq in self._queue_manager.channel_queues.values())

    def _set_publishing_state(self, is_publishing: bool):
        """更新发布状态并同步状态检查计时器"""
        self._is_publishing = is_publishing
        if is_publishing:
            self._status_check_timer.start(self._status_check_interval)
        else:
            self._status_check_timer.stop()

    def start(self):
        """启动调度器"""
        try:
            # 启动调度器
            self._ensure_scheduler_started()

            # 恢复队列
            self._queue_manager.resume_queue()

            self._set_publishing_state(True)
            self.scheduler_started.emit()
            self.status_changed.emit("自动发布已启动，正在检查待执行任务...")

            # 显示调度器状态
            status = self._scheduler.get_scheduler_status()
            logger.info(f"调度器已启动: {status}")

        except Exception as e:
            logger.exception(f"启动发布失败: {e}")
            raise

    def pause(self):
        """暂停调度器"""
        try:
            # 暂停队列（不停止调度器，只暂停任务获取）
            self._queue_manager.pause_queue()

            self._set_publishing_state(False)
            self.scheduler_paused.emit()
            self.status_changed.emit("自动发布已暂停")

            logger.info("自动发布已暂停")

        except Exception as e:
            logger.exception(f"暂停发布失败: {e}")
            raise

    def stop(self):
        """停止调度器"""
        try:
            if self._scheduler.is_running():
                logger.info("正在停止调度器...")
                self._scheduler.stop_scheduler()

            self._set_publishing_state(False)
            self.scheduler_stopped.emit()

            logger.info("调度器已停止")

        except Exception as e:
            logger.exception(f"停止调度器失败: {e}")
            raise

    def is_running(self) -> bool:
        """检查调度器是否运行中"""
        return self._is_publishing and self._scheduler.is_running()

    def has_running_channels(self) -> bool:
        """检查是否有渠道处于运行状态"""
        return self._has_running_channels()

    def start_channel(self, channel):
        """启动指定渠道"""
        try:
            started_scheduler = self._ensure_scheduler_started()

            channel_queue = self._queue_manager.get_channel_queue(channel)
            if not channel_queue:
                logger.warning(f"启动渠道失败，未找到队列: {channel}")
                return

            channel_queue.resume()
            if started_scheduler:
                self.scheduler_started.emit()

            self._set_publishing_state(self._has_running_channels())
            channel_name = Channel.get_display_name(channel)
            self.status_changed.emit(f"{channel_name} 渠道已启动")

        except Exception as e:
            logger.exception(f"启动渠道失败: {e}")
            raise

    def pause_channel(self, channel):
        """暂停指定渠道"""
        try:
            channel_queue = self._queue_manager.get_channel_queue(channel)
            if not channel_queue:
                logger.warning(f"暂停渠道失败，未找到队列: {channel}")
                return

            channel_queue.pause()
            has_running = self._has_running_channels()
            self._set_publishing_state(has_running)

            if not has_running:
                self.scheduler_paused.emit()
                self.status_changed.emit("自动发布已暂停")
            else:
                channel_name = Channel.get_display_name(channel)
                self.status_changed.emit(f"{channel_name} 渠道已暂停")

        except Exception as e:
            logger.exception(f"暂停渠道失败: {e}")
            raise

    def _check_status(self):
        """定时检查调度器和队列状态"""
        if not self._is_publishing:
            return

        # 检查队列状态
        queue_status = self._queue_manager.get_queue_status()
        queue_size = queue_status.get("queue_size", 0)

        # 发送队列状态更新信号
        self.queue_status_updated.emit(queue_status)

        # 更新状态消息
        if queue_status.get("is_executing"):
            current_task_id = queue_status.get("current_task_id")
            self.status_changed.emit(f"正在执行任务: {current_task_id}")
        elif queue_size > 0:
            self.status_changed.emit(f"队列中有 {queue_size} 个待执行任务")
        else:
            scheduler_status = self._scheduler.get_scheduler_status()
            scheduled_jobs = scheduler_status.get("scheduled_jobs", 0)
            if scheduled_jobs > 0:
                self.status_changed.emit(f"等待中: {scheduled_jobs} 个计划任务")
            else:
                self.status_changed.emit("自动发布运行中，等待新任务...")

    def get_scheduler_status(self) -> Dict:
        """获取调度器状态信息"""
        return self._scheduler.get_scheduler_status()

    def get_queue_status(self) -> Dict:
        """获取队列状态信息"""
        return self._queue_manager.get_queue_status()

    def get_queue_size(self, channel: Channel) -> int:
        """获取指定渠道的队列大小"""
        return self._queue_manager.get_queue_size(channel)

    def add_task(self, task: Task) -> bool:
        """
        添加任务到队列

        Args:
            task: 任务对象

        Returns:
            bool: 是否成功添加
        """
        return self._queue_manager.add_task(task)

    def remove_task(self, task_id: int, channel: Channel):
        """
        从队列中移除任务

        Args:
            task_id: 任务ID
            channel: 渠道
        """
        self._queue_manager.remove_task(task_id, channel)

    def mark_task_success(self, task: Task):
        """标记任务成功"""
        self._queue_manager.mark_task_success(task)

    def mark_task_failed(self, task: Task, error: str):
        """标记任务失败"""
        self._queue_manager.mark_task_failed(task, error)

    def set_channel_minute_of_hour(self, channel: Channel, minute: int):
        """
        设置渠道的每小时定点分钟

        Args:
            channel: 渠道
            minute: 分钟数（0-59）
        """
        logger.info(f"设置渠道 {channel.value} 每小时定点分钟: {minute}")
        self._queue_manager.set_channel_minute_of_hour(channel, minute)
        self._scheduler.refresh_channel_jobs(channel)

    def set_channel_schedule_mode(self, channel: Channel, mode: str):
        """
        设置渠道的调度模式

        Args:
            channel: 渠道
            mode: 调度模式 ("interval"/"fixed_time")
        """
        logger.info(f"设置渠道 {channel.value} 调度模式: {mode}")
        self._queue_manager.set_channel_schedule_mode(channel, mode)
        self._scheduler.refresh_channel_jobs(channel)

    def set_channel_interval(self, channel: Channel, value: int, unit: str):
        """
        设置渠道的发布间隔

        Args:
            channel: 渠道
            value: 间隔值
            unit: 间隔单位
        """
        logger.info(f"设置渠道 {channel.value} 发布间隔: {value} {unit}")
        self._queue_manager.set_channel_interval(channel, value, unit)

    def set_channel_daily_window(self, channel: Channel, start: str, end: str):
        """
        设置渠道的每日时间窗口

        Args:
            channel: 渠道
            start: 开始时间（HH:MM格式）
            end: 结束时间（HH:MM格式）
        """
        logger.info(f"设置渠道 {channel.value} 时间窗口: {start} - {end}")
        self._queue_manager.set_channel_daily_window(channel, start, end)

    def get_queue_manager(self) -> QueueManager:
        """获取队列管理器实例"""
        return self._queue_manager

    def get_scheduler(self) -> TaskScheduler:
        """获取任务调度器实例"""
        return self._scheduler

    def clear_tasks_by_channel(self, channel) -> int:
        """
        清空指定渠道的所有任务

        Args:
            channel: Channel枚举或自定义渠道ID字符串

        Returns:
            删除的任务数量
        """
        # 1. 清空调度队列
        channel_queue = self._queue_manager.get_channel_queue(channel)
        if channel_queue:
            channel_queue.clear_queue()

        # 2. 从数据库删除
        channel_value = channel.value if isinstance(channel, Channel) else channel
        deleted_count = self._db.delete_tasks_by_channel(channel_value)

        logger.info(f"已清空渠道 {channel_value} 的所有任务，删除 {deleted_count} 条")
        return deleted_count

    def clear_all_tasks(self) -> int:
        """
        清空所有渠道的所有任务

        Returns:
            删除的任务数量
        """
        # 1. 清空所有调度队列
        self._queue_manager.clear_queue()

        # 2. 从数据库删除所有任务
        deleted_count = self._db.delete_all_tasks()

        logger.info(f"已清空所有任务，删除 {deleted_count} 条")
        return deleted_count
