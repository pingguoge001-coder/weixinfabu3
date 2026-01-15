"""
任务队列管理器

负责维护待执行任务队列，实现优先级排序和全局执行锁
支持多渠道独立队列管理
"""
import logging
import threading
from datetime import datetime, timedelta, time as dt_time
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass, field
import heapq

from models.task import Task
from models.enums import TaskStatus, TaskPriority, Channel
from data.database import Database


logger = logging.getLogger("wechat_auto_sender.queue_manager")


@dataclass(order=True)
class PriorityTask:
    """带优先级的任务包装类，用于堆排序"""
    priority: int
    scheduled_time: datetime = field(compare=True)
    created_at: datetime = field(compare=True)
    task: Task = field(compare=False)


class ChannelQueueManager:
    """
    单个渠道的队列管理器

    每个渠道有独立的：
    - 任务队列
    - 执行锁
    - 暂停状态
    - 发布间隔/定点时间
    - 每日时间窗口
    """

    def __init__(self, channel: Channel, db: Database, config: dict = None):
        """
        初始化渠道队列管理器

        Args:
            channel: 渠道类型
            db: 数据库实例
            config: 渠道配置字典
        """
        self.channel = channel
        self._db = db

        # 解析配置
        config = config or {}
        self._schedule_mode = config.get("mode", "interval")  # interval / fixed_time
        self._minute_of_hour = config.get("minute_of_hour", 0)  # 每小时第几分钟执行 (0-59)
        self._daily_start = config.get("daily_start_time", "08:00")
        self._daily_end = config.get("daily_end_time", "22:00")
        interval_value = config.get("interval_value", 3)
        interval_unit = config.get("interval_unit", "minutes")
        self._interval_seconds = self._to_seconds(interval_value, interval_unit)

        # 任务队列 (最小堆)
        self._queue: List[PriorityTask] = []
        self._queue_lock = threading.Lock()

        # 执行锁
        self._execution_lock = threading.Lock()
        self._current_task: Optional[Task] = None

        # 队列状态
        self._paused = False
        self._paused_lock = threading.Lock()
        self._running = False

        # 任务ID集合 (防止重复添加)
        self._task_ids: set = set()

        # 上次执行时间
        self._last_execution_time: Optional[datetime] = None

        # 回调函数
        self._on_task_complete: Optional[Callable] = None
        self._on_task_failed: Optional[Callable] = None

        logger.debug(f"渠道队列管理器初始化: {channel.value}")

    @staticmethod
    def _to_seconds(value: int, unit: str) -> int:
        """将间隔配置转换为秒"""
        multipliers = {
            "seconds": 1,
            "minutes": 60,
            "hours": 3600,
        }
        try:
            unit = unit.lower()
            multiplier = multipliers.get(unit, 60)
            return max(0, int(value) * multiplier)
        except Exception:
            return 0

    @property
    def minute_of_hour(self) -> int:
        """获取每小时定点分钟 (0-59)"""
        return self._minute_of_hour

    @minute_of_hour.setter
    def minute_of_hour(self, value: int):
        """设置每小时定点分钟 (0-59)"""
        self._minute_of_hour = max(0, min(59, value))
        logger.info(f"[{self.channel.value}] 每小时定点分钟已设置为 {self._minute_of_hour}")

    @property
    def schedule_mode(self) -> str:
        """获取调度模式"""
        return self._schedule_mode

    def set_schedule_mode(self, mode: str):
        """设置调度模式 (interval/fixed_time)"""
        if mode not in ("interval", "fixed_time"):
            logger.warning(f"[{self.channel.value}] 无效调度模式: {mode}")
            return
        self._schedule_mode = mode
        logger.info(f"[{self.channel.value}] 调度模式已设置为 {self._schedule_mode}")

    def set_interval(self, value: int, unit: str):
        """设置发布间隔"""
        self._interval_seconds = self._to_seconds(value, unit)
        logger.info(f"[{self.channel.value}] 发布间隔已设置为 {self._interval_seconds}s")

    @property
    def daily_start(self) -> str:
        """获取每日开始时间"""
        return self._daily_start

    @property
    def daily_end(self) -> str:
        """获取每日结束时间"""
        return self._daily_end

    def set_daily_window(self, start: str, end: str):
        """设置每日时间窗口"""
        self._daily_start = start
        self._daily_end = end
        logger.info(f"[{self.channel.value}] 每日时间窗口已设置为 {start} - {end}")

    def is_within_daily_window(self) -> bool:
        """检查当前是否在每日时间窗口内"""
        try:
            now = datetime.now().time()
            start_parts = self._daily_start.split(":")
            end_parts = self._daily_end.split(":")

            from datetime import time as dt_time
            start_time = dt_time(int(start_parts[0]), int(start_parts[1]))
            end_time = dt_time(int(end_parts[0]), int(end_parts[1]))

            return start_time <= now <= end_time
        except Exception as e:
            logger.error(f"解析每日时间窗口失败: {e}")
            return True  # 解析失败时不限制

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running

    @is_running.setter
    def is_running(self, value: bool):
        self._running = value

    def set_callbacks(self,
                     on_complete: Callable = None,
                     on_failed: Callable = None):
        """设置回调函数"""
        self._on_task_complete = on_complete
        self._on_task_failed = on_failed

    # ==================== 队列操作 ====================

    def add_task(self, task: Task, priority: int = None) -> bool:
        """
        添加任务到队列

        Args:
            task: 任务对象
            priority: 优先级覆盖 (1-9, 1最高)

        Returns:
            是否添加成功
        """
        # 验证渠道
        if task.channel != self.channel:
            logger.warning(f"任务渠道不匹配: {task.channel} != {self.channel}")
            return False

        if priority is not None:
            task.priority = priority

        with self._queue_lock:
            # 检查是否已在队列中
            if task.id in self._task_ids:
                logger.warning(f"任务已在队列中: {task.id}")
                return False

            # 检查任务状态
            if not TaskStatus.can_execute(task.status):
                logger.warning(f"任务状态不可执行: {task.id} ({task.status.value})")
                return False

            # 创建优先级任务
            scheduled_time = task.scheduled_time or datetime.max
            priority_value = task.priority if task.priority is not None else 0
            priority_task = PriorityTask(
                priority=-priority_value,
                scheduled_time=scheduled_time,
                created_at=task.created_at,
                task=task
            )

            # 添加到堆
            heapq.heappush(self._queue, priority_task)
            self._task_ids.add(task.id)

            logger.debug(f"[{self.channel.value}] 任务已加入队列: {task.id}")
            return True

    def get_next_task(self) -> Optional[Task]:
        """
        获取下一个待执行任务

        Returns:
            下一个任务，如果队列为空或已暂停则返回 None
        """
        # 检查是否暂停
        with self._paused_lock:
            if self._paused:
                logger.info(f"[{self.channel.value}] get_next_task: 队列已暂停")
                return None

        # 检查是否在每日时间窗口内
        if not self.is_within_daily_window():
            logger.info(f"[{self.channel.value}] get_next_task: 不在每日时间窗口内")
            return None

        now = datetime.now()

        # 是否存在已到期的定时任务（到期任务应立即执行，不受每小时定点限制）
        with self._queue_lock:
            has_due_scheduled = any(
                pt.task.scheduled_time and pt.task.scheduled_time <= now
                for pt in self._queue
            )

        allow_unscheduled = False
        if not has_due_scheduled:
            if self._schedule_mode == "fixed_time":
                # 每小时定点：只在指定分钟执行，且同一小时只执行一次
                current_minute = now.minute
                if current_minute != self._minute_of_hour:
                    logger.info(
                        f"[{self.channel.value}] get_next_task: 当前分钟={current_minute}，期望分钟={self._minute_of_hour}"
                    )
                    return None

                # 检查当前小时是否已执行过
                if self._last_execution_time:
                    last_hour = self._last_execution_time.replace(minute=0, second=0, microsecond=0)
                    current_hour = now.replace(minute=0, second=0, microsecond=0)
                    if last_hour >= current_hour:
                        logger.info(f"[{self.channel.value}] get_next_task: 本小时已执行过")
                        return None
            else:
                # 间隔模式：距离上次执行未达到间隔则跳过
                if self._last_execution_time and self._interval_seconds > 0:
                    elapsed = (now - self._last_execution_time).total_seconds()
                    if elapsed < self._interval_seconds:
                        logger.info(
                            f"[{self.channel.value}] get_next_task: 间隔不足 {int(elapsed)}s < {self._interval_seconds}s"
                        )
                        return None

            allow_unscheduled = True

        with self._queue_lock:
            if not self._queue:
                logger.info(f"[{self.channel.value}] get_next_task: 队列为空")
                return None

            skipped: List[PriorityTask] = []

            def restore_skipped():
                for pt in skipped:
                    heapq.heappush(self._queue, pt)
                    self._task_ids.add(pt.task.id)

            while self._queue:
                priority_task = heapq.heappop(self._queue)
                task = priority_task.task
                self._task_ids.discard(task.id)

                # 检查任务是否仍可执行
                if TaskStatus.can_execute(task.status):
                    # 有排期时间的任务：未到期先跳过
                    if task.scheduled_time:
                        if task.scheduled_time > now:
                            logger.info(
                                f"[{self.channel.value}] get_next_task: 任务 {task.id} 未到期，scheduled_time={task.scheduled_time}"
                            )
                            skipped.append(priority_task)
                            continue
                        restore_skipped()
                        logger.info(f"[{self.channel.value}] get_next_task: 获取到到期任务 {task.id}")
                        return task

                    # 无排期时间的任务：仅在定点窗口执行
                    if not allow_unscheduled:
                        skipped.append(priority_task)
                        continue

                    restore_skipped()
                    logger.info(f"[{self.channel.value}] get_next_task: 获取到任务 {task.id}")
                    return task

                else:
                    logger.info(f"[{self.channel.value}] get_next_task: 任务 {task.id} 状态为 {task.status}，不可执行")

            restore_skipped()
            logger.info(f"[{self.channel.value}] get_next_task: 没有可执行的任务")
            return None

    def _get_sorted_queue_snapshot(self) -> List[PriorityTask]:
        """获取按优先级排序的队列快照"""
        with self._queue_lock:
            snapshot = list(self._queue)
        snapshot.sort()
        return snapshot

    def _get_task_priority_key(self, task: Task) -> tuple:
        """获取任务优先级排序键"""
        priority = task.priority if task.priority is not None else 0
        scheduled_time = task.scheduled_time or datetime.max
        created_at = task.created_at or datetime.max
        return (-priority, scheduled_time, created_at)

    def _get_daily_window_times(self) -> Optional[tuple]:
        """解析每日时间窗口"""
        try:
            start_parts = self._daily_start.split(":")
            end_parts = self._daily_end.split(":")
            start_time = dt_time(int(start_parts[0]), int(start_parts[1]))
            end_time = dt_time(int(end_parts[0]), int(end_parts[1]))
            return start_time, end_time
        except Exception:
            return None

    def _is_time_within_daily_window(self, value_time: dt_time) -> bool:
        """检查给定时间是否在每日时间窗口内"""
        window = self._get_daily_window_times()
        if not window:
            return True

        start_time, end_time = window
        if start_time <= end_time:
            return start_time <= value_time <= end_time
        return value_time >= start_time or value_time <= end_time

    def _get_next_fixed_time(self, now: datetime) -> datetime:
        """计算下一个定点执行时间"""
        minute = self._minute_of_hour
        candidate = now.replace(minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(hours=1)

        if self._last_execution_time:
            last_hour = self._last_execution_time.replace(minute=0, second=0, microsecond=0)
            candidate_hour = candidate.replace(minute=0, second=0, microsecond=0)
            if last_hour >= candidate_hour:
                candidate += timedelta(hours=1)

        if not self._is_time_within_daily_window(candidate.time()):
            for _ in range(48):
                if self._is_time_within_daily_window(candidate.time()):
                    break
                candidate += timedelta(hours=1)

        return candidate

    def _get_next_interval_time(self, now: datetime) -> datetime:
        """计算下次间隔执行时间"""
        if not self._last_execution_time or self._interval_seconds <= 0:
            return now
        candidate = self._last_execution_time + timedelta(seconds=self._interval_seconds)
        return candidate if candidate > now else now

    def _get_task_next_time(self, task: Task, now: datetime) -> datetime:
        """获取任务的下次执行时间"""
        if task.scheduled_time:
            return task.scheduled_time
        if self._schedule_mode == "interval":
            return self._get_next_interval_time(now)
        return self._get_next_fixed_time(now)

    def get_next_task_preview(self) -> dict:
        """获取下一任务预览信息（不取出）"""
        snapshot = self._get_sorted_queue_snapshot()
        if not snapshot:
            return {"task": None, "reason": "队列为空", "priority_key": None}

        now = datetime.now()
        candidates = []
        for pt in snapshot:
            task = pt.task
            if not TaskStatus.can_execute(task.status):
                continue
            candidates.append((self._get_task_next_time(task, now), task))

        if not candidates:
            return {"task": None, "reason": "暂无可执行任务", "priority_key": None}

        def sort_key(item: tuple) -> tuple:
            next_run, task = item
            priority = task.priority if task.priority is not None else 0
            created_at = task.created_at or datetime.max
            return (next_run, -priority, created_at)

        candidates.sort(key=sort_key)
        next_time, candidate = candidates[0]
        if not candidate:
            return {"task": None, "reason": "暂无可执行任务", "priority_key": None}

        reason = None
        if self.is_paused():
            reason = "已暂停"
        elif not self.is_running:
            reason = "未启动"
        else:
            if not self.is_within_daily_window():
                reason = "不在时间窗口"
            elif candidate.scheduled_time and candidate.scheduled_time > now:
                reason = "未到排期时间"
            elif not candidate.scheduled_time:
                if next_time > now:
                    if self._schedule_mode == "interval":
                        reason = "未到间隔"
                    else:
                        if self._last_execution_time:
                            last_hour = self._last_execution_time.replace(minute=0, second=0, microsecond=0)
                            current_hour = now.replace(minute=0, second=0, microsecond=0)
                            if last_hour >= current_hour:
                                reason = "本小时已执行"
                            else:
                                reason = "未到定点"
                        else:
                            reason = "未到定点"

        return {
            "task": candidate,
            "reason": reason,
            "next_time": next_time,
            "priority_key": self._get_task_priority_key(candidate),
        }

    def peek_next_task(self) -> Optional[Task]:
        """查看下一个任务 (不取出)"""
        preview = self.get_next_task_preview()
        return preview.get("task")

    def remove_task(self, task_id: int) -> bool:
        """从队列中移除任务"""
        with self._queue_lock:
            if task_id not in self._task_ids:
                return False

            self._queue = [pt for pt in self._queue if pt.task.id != task_id]
            heapq.heapify(self._queue)
            self._task_ids.discard(task_id)

            logger.debug(f"[{self.channel.value}] 任务已从队列移除: {task_id}")
            return True

    def clear_queue(self):
        """清空队列"""
        with self._queue_lock:
            self._queue.clear()
            self._task_ids.clear()
            logger.info(f"[{self.channel.value}] 队列已清空")

    # ==================== 执行锁操作 ====================

    def acquire_execution_lock(self, task: Task, timeout: float = None) -> bool:
        """获取执行锁"""
        acquired = self._execution_lock.acquire(timeout=timeout)
        if acquired:
            self._current_task = task
            task.mark_running()
            self._db.update_task(task)
            logger.debug(f"[{self.channel.value}] 获取执行锁: {task.id}")
        return acquired

    def release_execution_lock(self, update_execution_time: bool = True):
        """
        释放执行锁

        Args:
            update_execution_time: 是否更新执行时间（跳过任务时应为 False）
        """
        if self._execution_lock.locked():
            task = self._current_task
            self._current_task = None
            if update_execution_time:
                self._last_execution_time = datetime.now()
            self._execution_lock.release()
            if task:
                logger.debug(f"[{self.channel.value}] 释放执行锁: {task.id}")

    def is_executing(self) -> bool:
        """是否正在执行任务"""
        return self._execution_lock.locked()

    def get_current_task(self) -> Optional[Task]:
        """获取当前执行的任务"""
        return self._current_task

    # ==================== 任务状态转换 ====================

    def mark_task_success(self, task: Task):
        """标记任务成功"""
        task.mark_success()
        self._db.update_task(task)
        logger.info(f"[{self.channel.value}] 任务执行成功: {task.id}")

        if self._on_task_complete:
            try:
                self._on_task_complete(task)
            except Exception as e:
                logger.error(f"任务完成回调异常: {e}")

    def mark_task_failed(self, task: Task, error: str = ""):
        """标记任务失败"""
        task.mark_failed(error)
        self._db.update_task(task)
        logger.error(f"[{self.channel.value}] 任务执行失败: {task.id}, 错误: {error}")

        if self._on_task_failed:
            try:
                self._on_task_failed(task, error)
            except Exception as e:
                logger.error(f"任务失败回调异常: {e}")

    def mark_task_skipped(self, task: Task, reason: str = ""):
        """标记任务跳过"""
        task.mark_skipped(reason)
        self._db.update_task(task)
        logger.info(f"[{self.channel.value}] 任务已跳过: {task.id}, 原因: {reason}")

    def retry_task(self, task: Task) -> bool:
        """重试任务"""
        if not task.can_retry:
            logger.warning(f"任务已达最大重试次数: {task.id}")
            return False

        task.increment_retry()
        task.status = TaskStatus.pending
        self._db.update_task(task)

        self.add_task(task)
        logger.info(f"[{self.channel.value}] 任务重试: {task.id} (第 {task.retry_count} 次)")
        return True

    # ==================== 队列控制 ====================

    def pause(self):
        """暂停队列"""
        with self._paused_lock:
            self._paused = True
            self._running = False
            logger.info(f"[{self.channel.value}] 队列已暂停")

    def resume(self):
        """恢复队列"""
        with self._paused_lock:
            self._paused = False
            self._running = True
            logger.info(f"[{self.channel.value}] 队列已恢复")

    def start(self):
        """启动队列"""
        self._running = True
        self._paused = False
        logger.info(f"[{self.channel.value}] 队列已启动")

    def stop(self):
        """停止队列"""
        self._running = False
        logger.info(f"[{self.channel.value}] 队列已停止")

    def is_paused(self) -> bool:
        """队列是否暂停"""
        with self._paused_lock:
            return self._paused

    # ==================== 状态查询 ====================

    def get_queue_size(self) -> int:
        """获取队列长度"""
        with self._queue_lock:
            return len(self._queue)

    def get_all_tasks(self) -> List[Task]:
        """获取队列中所有任务"""
        with self._queue_lock:
            return [pt.task for pt in self._queue]

    def get_status(self) -> dict:
        """获取队列状态"""
        with self._queue_lock:
            queue_size = len(self._queue)

        return {
            "channel": self.channel.value,
            "queue_size": queue_size,
            "is_running": self._running,
            "is_paused": self.is_paused(),
            "is_executing": self.is_executing(),
            "schedule_mode": self._schedule_mode,
            "interval_seconds": self._interval_seconds,
            "minute_of_hour": self._minute_of_hour,
            "daily_start": self._daily_start,
            "daily_end": self._daily_end,
            "is_within_daily_window": self.is_within_daily_window(),
            "current_task_id": self._current_task.id if self._current_task else None,
            "last_execution": self._last_execution_time.isoformat() if self._last_execution_time else None,
        }


class QueueManager:
    """
    多渠道队列管理器

    特性：
    - 为每个渠道维护独立的队列
    - 支持按渠道启动/停止发布
    - 支持间隔模式和定点模式
    - 线程安全
    """

    def __init__(self, db: Database, config: dict = None):
        """
        初始化队列管理器

        Args:
            db: 数据库实例
            config: 调度配置
        """
        self._db = db
        self._config = config or {}

        # 获取渠道配置
        schedule_config = self._config.get("schedule", {})
        channel_configs = schedule_config.get("channels", {})

        # 为每个渠道创建独立的队列管理器
        self.channel_queues: Dict[Channel, ChannelQueueManager] = {}
        for channel in Channel:
            channel_config = channel_configs.get(channel.value, {})
            self.channel_queues[channel] = ChannelQueueManager(channel, db, channel_config)

        # 回调函数
        self._on_task_complete: Optional[Callable] = None
        self._on_task_failed: Optional[Callable] = None

        logger.info(f"多渠道队列管理器初始化完成，渠道数: {len(self.channel_queues)}")

    def set_callbacks(self,
                     on_complete: Callable = None,
                     on_failed: Callable = None):
        """设置回调函数（应用到所有渠道）"""
        self._on_task_complete = on_complete
        self._on_task_failed = on_failed
        for channel_queue in self.channel_queues.values():
            channel_queue.set_callbacks(on_complete, on_failed)

    def get_channel_queue(self, channel: Channel) -> ChannelQueueManager:
        """获取指定渠道的队列管理器"""
        return self.channel_queues.get(channel)

    # ==================== 队列操作 ====================

    def add_task(self, task: Task, priority: int = None) -> bool:
        """
        添加任务到对应渠道的队列

        Args:
            task: 任务对象
            priority: 优先级覆盖

        Returns:
            是否添加成功
        """
        channel_queue = self.channel_queues.get(task.channel)
        if channel_queue:
            return channel_queue.add_task(task, priority)
        else:
            logger.error(f"未知渠道: {task.channel}")
            return False

    def add_tasks(self, tasks: List[Task]) -> int:
        """批量添加任务"""
        count = 0
        for task in tasks:
            if self.add_task(task):
                count += 1
        return count

    def get_next_task(self, channel: Channel) -> Optional[Task]:
        """获取指定渠道的下一个待执行任务"""
        channel_queue = self.channel_queues.get(channel)
        if channel_queue:
            return channel_queue.get_next_task()
        return None

    def remove_task(self, task_id: int, channel: Channel) -> bool:
        """从指定渠道队列中移除任务"""
        channel_queue = self.channel_queues.get(channel)
        if channel_queue:
            return channel_queue.remove_task(task_id)
        return False

    def mark_task_success(self, task: Task):
        """标记任务成功"""
        channel_queue = self.channel_queues.get(task.channel)
        if channel_queue:
            channel_queue.mark_task_success(task)
        else:
            # 如果没有找到渠道队列，直接更新任务
            task.mark_success()
            self._db.update_task(task)
            logger.info(f"任务执行成功: {task.id}")

    def mark_task_failed(self, task: Task, error_message: str):
        """标记任务失败"""
        channel_queue = self.channel_queues.get(task.channel)
        if channel_queue:
            channel_queue.mark_task_failed(task, error_message)
        else:
            # 如果没有找到渠道队列，直接更新任务
            task.mark_failed(error_message)
            self._db.update_task(task)
            logger.error(f"任务执行失败: {task.id}, 错误: {error_message}")

    def mark_task_skipped(self, task: Task, reason: str = ""):
        """标记任务跳过"""
        channel_queue = self.channel_queues.get(task.channel)
        if channel_queue:
            channel_queue.mark_task_skipped(task, reason)
        else:
            # 如果没有找到渠道队列，直接更新任务
            task.mark_skipped(reason)
            self._db.update_task(task)
            logger.info(f"任务已跳过: {task.id}, 原因: {reason}")

    # ==================== 渠道控制 ====================

    def start_channel(self, channel: Channel):
        """启动指定渠道"""
        channel_queue = self.channel_queues.get(channel)
        if channel_queue:
            channel_queue.start()

    def stop_channel(self, channel: Channel):
        """停止指定渠道"""
        channel_queue = self.channel_queues.get(channel)
        if channel_queue:
            channel_queue.stop()

    def pause_channel(self, channel: Channel):
        """暂停指定渠道"""
        channel_queue = self.channel_queues.get(channel)
        if channel_queue:
            channel_queue.pause()

    def resume_channel(self, channel: Channel):
        """恢复指定渠道"""
        channel_queue = self.channel_queues.get(channel)
        if channel_queue:
            channel_queue.resume()

    def set_channel_minute_of_hour(self, channel: Channel, minute: int):
        """
        设置渠道每小时定点分钟

        Args:
            channel: 渠道
            minute: 分钟值 (0-59)
        """
        channel_queue = self.channel_queues.get(channel)
        if channel_queue:
            channel_queue.minute_of_hour = minute

    def set_channel_schedule_mode(self, channel: Channel, mode: str):
        """
        设置渠道调度模式

        Args:
            channel: 渠道
            mode: 调度模式 ("interval"/"fixed_time")
        """
        channel_queue = self.channel_queues.get(channel)
        if channel_queue:
            channel_queue.set_schedule_mode(mode)

    def set_channel_interval(self, channel: Channel, value: int, unit: str):
        """
        设置渠道发布间隔

        Args:
            channel: 渠道
            value: 间隔值
            unit: 间隔单位 ("seconds"/"minutes"/"hours")
        """
        channel_queue = self.channel_queues.get(channel)
        if channel_queue:
            channel_queue.set_interval(value, unit)

    def set_channel_daily_window(self, channel: Channel, start: str, end: str):
        """设置渠道每日时间窗口"""
        channel_queue = self.channel_queues.get(channel)
        if channel_queue:
            channel_queue.set_daily_window(start, end)

    def start_all(self):
        """启动所有渠道"""
        for channel_queue in self.channel_queues.values():
            channel_queue.start()
        logger.info("所有渠道队列已启动")

    def stop_all(self):
        """停止所有渠道"""
        for channel_queue in self.channel_queues.values():
            channel_queue.stop()
        logger.info("所有渠道队列已停止")

    def pause_all(self):
        """暂停所有渠道"""
        for channel_queue in self.channel_queues.values():
            channel_queue.pause()
        logger.info("所有渠道队列已暂停")

    def resume_all(self):
        """恢复所有渠道"""
        for channel_queue in self.channel_queues.values():
            channel_queue.resume()
        logger.info("所有渠道队列已恢复")

    # ==================== 兼容旧接口 ====================

    def pause_queue(self):
        """暂停所有队列（兼容旧接口）"""
        self.pause_all()

    def resume_queue(self):
        """恢复所有队列（兼容旧接口）"""
        self.resume_all()

    def is_paused(self) -> bool:
        """是否所有队列都暂停（兼容旧接口）"""
        return all(cq.is_paused() for cq in self.channel_queues.values())

    def clear_queue(self):
        """清空所有队列（兼容旧接口）"""
        for channel_queue in self.channel_queues.values():
            channel_queue.clear_queue()

    def is_executing(self) -> bool:
        """是否有任何渠道正在执行（兼容旧接口）"""
        return any(cq.is_executing() for cq in self.channel_queues.values())

    # ==================== 状态查询 ====================

    def get_queue_size(self, channel: Channel = None) -> int:
        """
        获取队列长度

        Args:
            channel: 指定渠道，None表示所有渠道总和
        """
        if channel:
            channel_queue = self.channel_queues.get(channel)
            return channel_queue.get_queue_size() if channel_queue else 0
        else:
            return sum(cq.get_queue_size() for cq in self.channel_queues.values())

    def get_channel_status(self, channel: Channel) -> dict:
        """获取指定渠道的状态"""
        channel_queue = self.channel_queues.get(channel)
        if channel_queue:
            return channel_queue.get_status()
        return {}

    def get_all_status(self) -> Dict[str, dict]:
        """获取所有渠道的状态"""
        return {
            channel.value: channel_queue.get_status()
            for channel, channel_queue in self.channel_queues.items()
        }

    def get_queue_status(self) -> dict:
        """获取队列总体状态（兼容旧接口）"""
        total_size = sum(cq.get_queue_size() for cq in self.channel_queues.values())
        is_paused = all(cq.is_paused() for cq in self.channel_queues.values())
        is_executing = any(cq.is_executing() for cq in self.channel_queues.values())

        return {
            "queue_size": total_size,
            "is_paused": is_paused,
            "is_executing": is_executing,
            "channels": self.get_all_status()
        }

    def get_next_task_preview(self) -> dict:
        """获取全局下一任务预览信息"""
        running_channels = [cq for cq in self.channel_queues.values() if cq.is_running]
        if not running_channels:
            return {"task": None, "reason": "未启动", "channel": None}

        previews = []
        fallback_reasons = []
        for channel_queue in running_channels:
            preview = channel_queue.get_next_task_preview()
            if preview.get("task"):
                preview["channel"] = channel_queue.channel
                previews.append(preview)
            else:
                reason = preview.get("reason")
                if reason:
                    fallback_reasons.append(reason)

        if not previews:
            reason = "暂无任务"
            if "暂无可执行任务" in fallback_reasons:
                reason = "暂无可执行任务"
            elif "队列为空" in fallback_reasons:
                reason = "队列为空"
            return {"task": None, "reason": reason, "channel": None}

        ready_previews = [p for p in previews if p.get("reason") is None]
        candidates = ready_previews if ready_previews else previews

        def sort_key(item: dict) -> tuple:
            next_time = item.get("next_time") or datetime.max
            priority_key = item.get("priority_key") or (0, datetime.max, datetime.max)
            return (next_time, priority_key)

        return min(candidates, key=sort_key)

    def load_pending_tasks(self, channel: Channel = None) -> int:
        """
        从数据库加载待执行任务到队列

        Args:
            channel: 指定渠道，None表示加载所有渠道

        Returns:
            加载的任务数量
        """
        tasks = self._db.get_pending_tasks()

        if channel:
            tasks = [t for t in tasks if t.channel == channel]

        count = self.add_tasks(tasks)
        logger.info(f"从数据库加载 {count} 个待执行任务")
        return count

    def get_tasks_by_channel(self, channel: Channel) -> List[Task]:
        """获取指定渠道的所有任务"""
        channel_queue = self.channel_queues.get(channel)
        if channel_queue:
            return channel_queue.get_all_tasks()
        return []
