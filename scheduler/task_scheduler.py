"""
定时任务调度器

基于 APScheduler 实现，负责检查到期任务并触发执行
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Callable, List
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from models.task import Task
from models.enums import TaskStatus, Channel
from data.database import Database
from .queue_manager import QueueManager
from .idempotency_manager import IdempotencyManager


logger = logging.getLogger("wechat_auto_sender.task_scheduler")


class TaskScheduler:
    """
    定时任务调度器

    特性：
    - 基于 APScheduler BackgroundScheduler
    - 检查 scheduled_time 到期的任务
    - 支持启动时恢复未完成任务
    - 漏发检测和处理
    """

    def __init__(self, db: Database, queue_manager: QueueManager,
                 idempotency_manager: IdempotencyManager,
                 config: dict = None):
        """
        初始化调度器

        Args:
            db: 数据库实例
            queue_manager: 队列管理器
            idempotency_manager: 幂等性管理器
            config: 调度配置
        """
        self._db = db
        self._queue_manager = queue_manager
        self._idempotency_manager = idempotency_manager
        self._config = config or {}

        # 调度配置
        schedule_config = self._config.get("schedule", {})
        self._check_interval = schedule_config.get("queue_check_interval", 10)
        self._daily_limit = schedule_config.get("daily_limit", 500)
        self._missed_window = schedule_config.get("missed_task_window", 30)
        self._enable_missed_recovery = schedule_config.get("enable_missed_recovery", True)

        # 工作时间配置
        active_hours = schedule_config.get("active_hours", {})
        self._work_start = active_hours.get("start", "09:00")
        self._work_end = active_hours.get("end", "18:00")
        self._work_days = schedule_config.get("work_days")

        # 兼容旧配置: scheduler.work_hours / weekend_work
        scheduler_config = self._config.get("scheduler", {})
        work_hours = scheduler_config.get("work_hours", {})
        if work_hours:
            self._work_start = work_hours.get("start", self._work_start)
            self._work_end = work_hours.get("end", self._work_end)
        self._weekend_work = scheduler_config.get("weekend_work", False)

        # APScheduler 实例
        self._scheduler = BackgroundScheduler(
            timezone="Asia/Shanghai",
            job_defaults={
                "coalesce": True,  # 合并错过的执行
                "max_instances": 1  # 最大实例数
            }
        )

        # 调度跟踪日志（用于排查定时任务不触发的问题）
        self._trace_enabled = schedule_config.get("debug_trace", True)
        self._trace_logger = logging.getLogger("wechat_auto_sender.scheduler_trace")
        if not self._trace_logger.handlers:
            log_dir = self._config.get("paths", {}).get("logs_dir", "./data/logs")
            os.makedirs(log_dir, exist_ok=True)
            handler = logging.FileHandler(
                os.path.join(log_dir, "scheduler_trace.log"),
                encoding="utf-8"
            )
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self._trace_logger.addHandler(handler)
            self._trace_logger.setLevel(logging.INFO)
            self._trace_logger.propagate = False

        # 任务执行回调
        self._task_executor: Optional[Callable] = None

        # 运行状态
        self._running = False
        self._lock = threading.Lock()

        # 注册事件监听
        self._scheduler.add_listener(self._on_job_event,
                                     EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

        logger.info("定时任务调度器初始化完成")
        self._trace(
            "init: check_interval=%s, daily_limit=%s, work_hours=%s-%s, work_days=%s",
            self._check_interval,
            self._daily_limit,
            self._work_start,
            self._work_end,
            self._work_days,
        )

    def set_task_executor(self, executor: Callable):
        """
        设置任务执行器

        Args:
            executor: 接收 Task 参数的回调函数
        """
        self._task_executor = executor

    # ==================== 调度器控制 ====================

    def start_scheduler(self):
        """启动调度器"""
        with self._lock:
            if self._running:
                logger.warning("调度器已在运行")
                return

            # 恢复未完成任务
            self._recover_tasks()

            # 检查漏发任务
            if self._enable_missed_recovery:
                self._check_missed_tasks()

            # 添加定时检查任务（基础检查）
            self._scheduler.add_job(
                self._check_scheduled_tasks,
                trigger=IntervalTrigger(seconds=self._check_interval),
                id="check_scheduled_tasks",
                replace_existing=True
            )

            # 为每个渠道设置调度任务
            self._setup_channel_jobs()

            # 启动调度器
            self._scheduler.start()
            self._running = True

            logger.info("调度器已启动")
            self._trace("start_scheduler: running=True, jobs=%s", len(self._scheduler.get_jobs()))

    def _setup_channel_jobs(self):
        """为每个渠道设置调度任务（每小时定点模式）"""
        for channel, cq in self._queue_manager.channel_queues.items():
            if cq.schedule_mode != "fixed_time":
                continue
            # 每小时定点模式：使用 CronTrigger 在每小时的指定分钟执行
            minute = cq.minute_of_hour
            self._scheduler.add_job(
                self._check_channel_queue,
                trigger=CronTrigger(minute=minute),
                args=[channel],
                id=f"channel_{channel.value}_hourly",
                replace_existing=True
            )
            logger.info(f"[{channel.value}] 已设置每小时定点模式: 每小时第 {minute} 分钟执行")

    def refresh_channel_jobs(self, channel: Channel = None):
        """
        刷新渠道调度任务（当调度配置变更时调用）

        Args:
            channel: 指定渠道，None表示刷新所有渠道
        """
        channels_to_refresh = [channel] if channel else list(self._queue_manager.channel_queues.keys())

        for ch in channels_to_refresh:
            # 移除旧的调度任务
            self._remove_channel_jobs(ch)

            # 添加新的调度任务（每小时定点模式）
            cq = self._queue_manager.channel_queues.get(ch)
            if not cq:
                continue
            if cq.schedule_mode != "fixed_time":
                continue

            minute = cq.minute_of_hour
            self._scheduler.add_job(
                self._check_channel_queue,
                trigger=CronTrigger(minute=minute),
                args=[ch],
                id=f"channel_{ch.value}_hourly",
                replace_existing=True
            )
            logger.info(f"[{ch.value}] 刷新每小时定点模式: 每小时第 {minute} 分钟执行")

    def _remove_channel_jobs(self, channel: Channel):
        """移除指定渠道的所有调度任务"""
        job_ids_to_remove = []

        for job in self._scheduler.get_jobs():
            if job.id.startswith(f"channel_{channel.value}_"):
                job_ids_to_remove.append(job.id)

        for job_id in job_ids_to_remove:
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass

    def _check_channel_queue(self, channel: Channel):
        """
        间隔模式：检查并执行渠道队列任务

        Args:
            channel: 渠道
        """
        try:
            logger.info(f"[{channel.value}] 定点任务触发，开始检查队列")

            cq = self._queue_manager.channel_queues.get(channel)
            if not cq:
                logger.warning(f"[{channel.value}] 未找到渠道队列")
                return
            if not cq.is_running:
                logger.info(f"[{channel.value}] 队列未运行，跳过")
                self._trace("[%s] channel_skip: not_running", channel.value)
                return

            # 检查是否在每日时间窗口内
            if not cq.is_within_daily_window():
                logger.info(f"[{channel.value}] 不在每日时间窗口内，跳过")
                self._trace("[%s] channel_skip: out_of_daily_window", channel.value)
                return

            logger.info(f"[{channel.value}] 准备执行任务，队列大小: {cq.get_queue_size()}")
            # 尝试执行下一个任务
            self._try_execute_channel_task(channel)

        except Exception as e:
            logger.exception(f"检查渠道队列异常 [{channel.value}]: {e}")

    def _execute_fixed_time_task(self, channel: Channel):
        """
        定点模式：在固定时间执行一个任务

        Args:
            channel: 渠道
        """
        try:
            cq = self._queue_manager.channel_queues.get(channel)
            if not cq or not cq.is_running:
                return

            # 检查是否在每日时间窗口内
            if not cq.is_within_daily_window():
                logger.debug(f"[{channel.value}] 定点任务跳过: 不在每日时间窗口内")
                return

            logger.info(f"[{channel.value}] 定点任务触发")
            self._try_execute_channel_task(channel)

        except Exception as e:
            logger.exception(f"定点任务执行异常 [{channel.value}]: {e}")

    def _try_execute_channel_task(self, channel: Channel):
        """尝试执行指定渠道的下一个任务"""
        cq = self._queue_manager.channel_queues.get(channel)
        if not cq:
            logger.warning(f"[{channel.value}] 未找到渠道队列")
            self._trace("[%s] try_execute: no_channel_queue", channel.value)
            return False

        # 检查是否已有任务在执行
        if cq.is_executing():
            logger.info(f"[{channel.value}] 已有任务在执行，跳过")
            self._trace("[%s] try_execute: already_executing", channel.value)
            return False

        # 循环获取任务，跳过已执行的任务
        max_skip = 100  # 防止无限循环
        skipped = 0

        while skipped < max_skip:
            # 获取下一个任务
            task = cq.get_next_task()
            if not task:
                logger.info(f"[{channel.value}] 没有可执行的任务")
                self._trace("[%s] try_execute: no_task", channel.value)
                return False

            # 获取执行锁
            if not cq.acquire_execution_lock(task, timeout=1):
                # 放回队列
                cq.add_task(task)
                self._trace("[%s] try_execute: lock_failed task_id=%s", channel.value, task.id)
                return False

            # 幂等性检查
            if self._idempotency_manager.is_duplicate(task):
                cq.mark_task_skipped(task, "幂等检查: 任务已执行")
                cq.release_execution_lock(update_execution_time=False)  # 跳过时不更新执行时间
                skipped += 1
                logger.info(f"[{channel.value}] 任务 {task.id} 已执行，继续下一个 (跳过 {skipped})")
                self._trace("[%s] try_execute: duplicate task_id=%s", channel.value, task.id)
                continue  # 继续尝试下一个任务

            # 幂等性记录
            if not self._idempotency_manager.check_and_record(task):
                cq.mark_task_skipped(task, "幂等检查: 任务已执行")
                cq.release_execution_lock(update_execution_time=False)  # 跳过时不更新执行时间
                skipped += 1
                logger.info(f"[{channel.value}] 任务 {task.id} 记录失败，继续下一个 (跳过 {skipped})")
                self._trace("[%s] try_execute: idempotent_block task_id=%s", channel.value, task.id)
                continue  # 继续尝试下一个任务

            # 执行任务
            try:
                if self._task_executor:
                    logger.info(f"[{channel.value}] 开始执行任务: {task.id}")
                    self._trace("[%s] try_execute: run task_id=%s", channel.value, task.id)
                    self._task_executor(task)
                else:
                    logger.warning("未设置任务执行器")
                    self._trace("[%s] try_execute: no_executor task_id=%s", channel.value, task.id)
                return True  # 成功执行，退出

            except Exception as e:
                logger.exception(f"任务执行异常: {e}")
                cq.mark_task_failed(task, str(e))
                self._trace("[%s] try_execute: exception task_id=%s error=%s", channel.value, task.id, e)

                # 移除幂等记录，允许重试
                self._idempotency_manager.remove(task)

                # 尝试重试
                if task.can_retry:
                    cq.retry_task(task)
                return True

            finally:
                cq.release_execution_lock()

        logger.warning(f"[{channel.value}] 跳过了 {skipped} 个已执行任务，可能需要清理队列")
        self._trace("[%s] try_execute: skipped_limit=%s", channel.value, skipped)
        return False

    def stop_scheduler(self):
        """停止调度器"""
        with self._lock:
            if not self._running:
                logger.warning("调度器未运行")
                return

            self._scheduler.shutdown(wait=True)
            self._running = False

            logger.info("调度器已停止")

    def is_running(self) -> bool:
        """调度器是否运行中"""
        return self._running

    # ==================== 任务调度 ====================

    def schedule_task(self, task: Task, scheduled_time: datetime = None) -> bool:
        """
        调度单个任务

        Args:
            task: 任务对象
            scheduled_time: 计划执行时间，为 None 则使用任务自带时间

        Returns:
            是否调度成功
        """
        if scheduled_time:
            task.scheduled_time = scheduled_time

        if not task.scheduled_time:
            logger.warning(f"任务无调度时间: {task.id}")
            return False

        # 检查是否在工作时间内
        if not self._is_work_time(task.scheduled_time):
            logger.warning(f"任务调度时间不在工作时间内: {task.id}")

        # 更新任务状态
        task.status = TaskStatus.scheduled
        self._db.update_task(task)

        # 如果时间已到期，直接加入队列
        if task.scheduled_time <= datetime.now():
            self._queue_manager.add_task(task)
            logger.info(f"任务已到期，直接加入队列: {task.id}")
        else:
            # 添加到 APScheduler
            self._scheduler.add_job(
                self._trigger_task,
                trigger=DateTrigger(run_date=task.scheduled_time),
                args=[task.id],
                id=f"task_{task.id}",
                replace_existing=True
            )
            logger.info(f"任务已调度: {task.id} -> {task.scheduled_time}")

        return True

    def cancel_task(self, task_id: str) -> bool:
        """
        取消调度的任务

        Args:
            task_id: 任务ID

        Returns:
            是否取消成功
        """
        job_id = f"task_{task_id}"

        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"任务调度已取消: {task_id}")
        except Exception:
            pass  # 任务可能不在调度器中

        # 从队列移除
        self._queue_manager.remove_task(task_id)

        # 更新数据库状态
        task = self._db.get_task_by_id(task_id)
        if task and TaskStatus.can_execute(task.status):
            task.status = TaskStatus.CANCELLED
            self._db.update_task(task)

        return True

    def reschedule_task(self, task_id: str, new_time: datetime) -> bool:
        """
        重新调度任务

        Args:
            task_id: 任务ID
            new_time: 新的执行时间

        Returns:
            是否重新调度成功
        """
        task = self._db.get_task_by_id(task_id)
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return False

        # 取消原调度
        self.cancel_task(task_id)

        # 重新调度
        task.status = TaskStatus.PENDING
        return self.schedule_task(task, new_time)

    # ==================== 漏发检测 ====================

    def check_missed_tasks(self) -> List[Task]:
        """
        检查漏发任务

        Returns:
            漏发任务列表
        """
        return self._check_missed_tasks()

    def _check_missed_tasks(self) -> List[Task]:
        """内部漏发检查方法"""
        missed_tasks = []
        window_start = datetime.now() - timedelta(minutes=self._missed_window)

        # 查询在时间窗口内且未执行的任务
        all_tasks = self._db.get_scheduled_tasks(before_time=datetime.now())

        for task in all_tasks:
            if task.scheduled_time and task.scheduled_time >= window_start:
                # 在窗口内的漏发任务
                missed_tasks.append(task)
                logger.warning(f"检测到漏发任务: {task.id}, "
                             f"计划时间: {task.scheduled_time}")

        if missed_tasks and self._enable_missed_recovery:
            # 自动补发
            for task in missed_tasks:
                self._queue_manager.add_task(task)
            logger.info(f"已将 {len(missed_tasks)} 个漏发任务加入队列")

        return missed_tasks

    # ==================== 内部方法 ====================

    def _check_scheduled_tasks(self):
        """定时检查到期任务"""
        try:
            now = datetime.now()
            # 检查是否在工作时间
            if not self._is_work_time():
                self._trace("tick: now=%s skip=not_work_time", now.isoformat())
                return

            # 检查每日限制
            today_count = self._db.get_today_task_count()
            if today_count >= self._daily_limit:
                logger.warning(f"已达每日任务上限: {today_count}/{self._daily_limit}")
                self._trace(
                    "tick: now=%s skip=daily_limit today_count=%s limit=%s",
                    now.isoformat(),
                    today_count,
                    self._daily_limit,
                )
                return

            # 获取到期任务
            due_tasks = self._db.get_scheduled_tasks()
            queue_size = self._queue_manager.get_queue_size()
            if due_tasks or queue_size:
                due_ids = [str(t.id) for t in due_tasks[:10]]
                self._trace(
                    "tick: now=%s due_tasks=%s queue_size=%s due_ids=%s",
                    now.isoformat(),
                    len(due_tasks),
                    queue_size,
                    ",".join(due_ids),
                )

            for task in due_tasks:
                # 幂等性检查
                if self._idempotency_manager.is_duplicate(task):
                    self._queue_manager.mark_task_skipped(task, "幂等检查: 任务已执行")
                    self._trace("due_skip: duplicate task_id=%s", task.id)
                    continue

                # 加入队列
                added = self._queue_manager.add_task(task)
                if added:
                    logger.debug(f"到期任务已加入队列: {task.id}")
                    self._trace("due_add: task_id=%s status=%s", task.id, task.status)
                else:
                    self._trace("due_add_failed: task_id=%s status=%s", task.id, task.status)

            # 尝试执行队列中的任务
            self._try_execute_next()

        except Exception as e:
            logger.exception(f"检查定时任务异常: {e}")
            self._trace("tick_error: %s", e)

    def _trigger_task(self, task_id: str):
        """APScheduler 触发任务回调"""
        try:
            task = self._db.get_task_by_id(task_id)
            if not task:
                logger.error(f"触发的任务不存在: {task_id}")
                return

            if not TaskStatus.can_execute(task.status):
                logger.warning(f"任务状态不可执行: {task_id} ({task.status.value})")
                return

            # 幂等性检查
            if self._idempotency_manager.is_duplicate(task):
                self._queue_manager.mark_task_skipped(task, "幂等检查: 任务已执行")
                return

            # 加入队列
            self._queue_manager.add_task(task)
            logger.info(f"定时任务已触发: {task_id}")

            # 尝试执行
            self._try_execute_next()

        except Exception as e:
            logger.exception(f"触发任务异常: {e}")

    def _try_execute_next(self):
        """尝试执行下一个任务"""
        if not self._task_executor:
            logger.warning("未设置任务执行器")
            return

        # 检查是否已有任务在执行
        if self._queue_manager.is_executing():
            return

        # 按渠道尝试执行一个任务
        for channel, cq in self._queue_manager.channel_queues.items():
            if not cq.is_running:
                continue
            if self._try_execute_channel_task(channel):
                return

    def _recover_tasks(self):
        """恢复未完成任务"""
        # 将所有 running 状态的任务标记为失败
        count = self._db.mark_running_tasks_as_failed()
        if count > 0:
            logger.warning(f"已将 {count} 个异常中断的任务标记为失败")
            self._trace("recover: marked_failed=%s", count)

        # 加载待执行任务到队列
        loaded = self._queue_manager.load_pending_tasks()
        logger.info(f"恢复 {loaded} 个待执行任务")
        self._trace("recover: loaded_pending=%s", loaded)

    def _is_work_time(self, check_time: datetime = None) -> bool:
        """检查是否在工作时间内"""
        if check_time is None:
            check_time = datetime.now()

        # 按配置工作日过滤（优先 schedule.work_days）
        if self._work_days:
            normalized_days = set()
            for day in self._work_days:
                if isinstance(day, int):
                    if 1 <= day <= 7:
                        normalized_days.add(day - 1)  # 1-7 -> 0-6
                    elif 0 <= day <= 6:
                        normalized_days.add(day)
            if normalized_days and check_time.weekday() not in normalized_days:
                return False
        else:
            # 兼容旧逻辑：是否允许周末
            if not self._weekend_work and check_time.weekday() >= 5:
                return False

        # 解析工作时间
        try:
            start_parts = self._work_start.split(":")
            end_parts = self._work_end.split(":")

            start_time = check_time.replace(
                hour=int(start_parts[0]),
                minute=int(start_parts[1]),
                second=0, microsecond=0
            )
            end_time = check_time.replace(
                hour=int(end_parts[0]),
                minute=int(end_parts[1]),
                second=0, microsecond=0
            )

            return start_time <= check_time <= end_time

        except Exception as e:
            logger.error(f"解析工作时间失败: {e}")
            return True  # 解析失败时不限制

    def _on_job_event(self, event):
        """APScheduler 任务事件回调"""
        if event.exception:
            logger.error(f"调度任务执行错误: {event.job_id}, {event.exception}")
            self._trace("job_error: job_id=%s error=%s", event.job_id, event.exception)

    def _trace(self, msg: str, *args):
        if not self._trace_enabled:
            return
        try:
            self._trace_logger.info(msg, *args)
        except Exception:
            pass

    # ==================== 状态查询 ====================

    def get_scheduler_status(self) -> dict:
        """获取调度器状态"""
        jobs = self._scheduler.get_jobs()
        job_info = []
        for job in jobs:
            job_info.append({
                "id": job.id,
                "next_run_time": job.next_run_time.isoformat()
                    if job.next_run_time else None
            })

        return {
            "running": self._running,
            "is_work_time": self._is_work_time(),
            "today_executed": self._db.get_today_task_count(),
            "daily_limit": self._daily_limit,
            "scheduled_jobs": len(jobs),
            "jobs": job_info
        }
