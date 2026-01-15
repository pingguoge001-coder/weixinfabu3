"""
自适应速率限制器模块

根据失败率动态调整发送间隔
"""
import logging
import threading
import random
from datetime import datetime, date, timedelta
from typing import List
from collections import deque
from dataclasses import dataclass

from data.database import Database


logger = logging.getLogger("wechat_auto_sender.rate_limiter")


@dataclass
class ExecutionRecord:
    """执行记录"""
    timestamp: datetime
    success: bool


class RateLimiter:
    """
    自适应速率限制器

    特性：
    - 基础间隔从配置读取
    - 根据失败率动态调整间隔：
      - 失败率 < 10%: 基础间隔
      - 失败率 10-30%: 间隔 * 1.5
      - 失败率 > 30%: 间隔 * 2
    - 随机抖动防止规律性检测
    - 每日限额检查
    """

    def __init__(self, db: Database, config: dict = None):
        """
        初始化速率限制器

        Args:
            db: 数据库实例
            config: 配置
        """
        self._db = db
        self._config = config or {}

        # 基础配置
        schedule_config = self._config.get("schedule", {})
        self._base_interval = schedule_config.get("default_interval", 180)
        self._daily_limit = schedule_config.get("daily_limit", 500)

        # 速率限制配置
        rate_config = self._config.get("rate_limit", {})
        self._jitter_min = rate_config.get("jitter_min", -30)
        self._jitter_max = rate_config.get("jitter_max", 60)
        self._failure_rate_low = rate_config.get("failure_rate_low", 0.1)
        self._failure_rate_high = rate_config.get("failure_rate_high", 0.3)
        self._window_size = rate_config.get("window_size", 20)

        # 执行记录（滑动窗口）
        self._records: deque = deque(maxlen=self._window_size)
        self._records_lock = threading.Lock()

        # 今日计数
        self._today_count = 0
        self._today_date: date = date.today()
        self._count_lock = threading.Lock()

        # 从数据库加载今日计数
        self._load_today_count()

        logger.info(f"速率限制器初始化完成 (基础间隔: {self._base_interval}s, "
                   f"每日限额: {self._daily_limit})")

    # ==================== 核心方法 ====================

    def get_next_delay(self) -> int:
        """
        获取下一次执行的延迟时间

        根据失败率动态调整：
        - 失败率 < 10%: 基础间隔
        - 失败率 10-30%: 间隔 * 1.5
        - 失败率 > 30%: 间隔 * 2

        Returns:
            延迟秒数（含随机抖动）
        """
        # 计算失败率
        failure_rate = self._get_failure_rate()

        # 根据失败率调整间隔
        if failure_rate < self._failure_rate_low:
            multiplier = 1.0
        elif failure_rate < self._failure_rate_high:
            multiplier = 1.5
        else:
            multiplier = 2.0

        # 计算基础延迟
        base_delay = int(self._base_interval * multiplier)

        # 添加随机抖动
        jitter = random.randint(self._jitter_min, self._jitter_max)
        delay = max(1, base_delay + jitter)  # 确保至少1秒

        logger.debug(f"计算延迟: 失败率={failure_rate:.2%}, "
                    f"倍率={multiplier}, 延迟={delay}s")

        return delay

    def record_result(self, success: bool) -> None:
        """
        记录执行结果

        Args:
            success: 是否成功
        """
        now = datetime.now()

        with self._records_lock:
            self._records.append(ExecutionRecord(timestamp=now, success=success))

        # 更新今日计数
        if success:
            self._increment_today_count()

        logger.debug(f"记录执行结果: {'成功' if success else '失败'}")

    def can_send_today(self) -> bool:
        """
        检查今日是否还可以发送

        Returns:
            True: 可以发送
            False: 已达每日限额
        """
        self._check_date_rollover()

        with self._count_lock:
            return self._today_count < self._daily_limit

    def get_today_count(self) -> int:
        """获取今日已发送数量"""
        self._check_date_rollover()

        with self._count_lock:
            return self._today_count

    def get_remaining_quota(self) -> int:
        """获取今日剩余配额"""
        self._check_date_rollover()

        with self._count_lock:
            return max(0, self._daily_limit - self._today_count)

    # ==================== 内部方法 ====================

    def _get_failure_rate(self) -> float:
        """
        计算滑动窗口内的失败率

        Returns:
            失败率 (0.0 - 1.0)
        """
        with self._records_lock:
            if not self._records:
                return 0.0

            total = len(self._records)
            failures = sum(1 for r in self._records if not r.success)

            return failures / total

    def _load_today_count(self):
        """从数据库加载今日已执行数量"""
        with self._count_lock:
            self._today_count = self._db.get_today_task_count()
            self._today_date = date.today()
            logger.debug(f"加载今日计数: {self._today_count}")

    def _increment_today_count(self):
        """增加今日计数"""
        self._check_date_rollover()

        with self._count_lock:
            self._today_count += 1

    def _check_date_rollover(self):
        """检查日期是否变更（跨天重置）"""
        today = date.today()

        with self._count_lock:
            if today != self._today_date:
                logger.info(f"日期变更: {self._today_date} -> {today}, 重置计数")
                self._today_count = 0
                self._today_date = today

                # 清空执行记录
                with self._records_lock:
                    self._records.clear()

    # ==================== 高级功能 ====================

    def get_adaptive_interval(self, consecutive_failures: int = 0) -> int:
        """
        获取自适应间隔（考虑连续失败次数）

        Args:
            consecutive_failures: 连续失败次数

        Returns:
            延迟秒数
        """
        base_delay = self.get_next_delay()

        # 连续失败时额外增加间隔
        if consecutive_failures > 0:
            extra_multiplier = min(2 ** consecutive_failures, 8)  # 最大8倍
            base_delay = int(base_delay * extra_multiplier)

        return base_delay

    def get_optimal_send_time(self) -> datetime:
        """
        获取最佳发送时间

        Returns:
            建议的下次发送时间
        """
        delay = self.get_next_delay()
        return datetime.now() + timedelta(seconds=delay)

    def should_slow_down(self) -> bool:
        """
        判断是否应该降速

        Returns:
            True: 应该降速
            False: 正常速度
        """
        failure_rate = self._get_failure_rate()
        return failure_rate >= self._failure_rate_low

    # ==================== 状态查询 ====================

    def get_status(self) -> dict:
        """获取速率限制器状态"""
        self._check_date_rollover()
        failure_rate = self._get_failure_rate()

        with self._count_lock:
            today_count = self._today_count

        with self._records_lock:
            recent_records = [
                {"time": r.timestamp.isoformat(), "success": r.success}
                for r in list(self._records)[-10:]
            ]

        return {
            "base_interval": self._base_interval,
            "current_delay": self.get_next_delay(),
            "failure_rate": failure_rate,
            "daily_limit": self._daily_limit,
            "today_count": today_count,
            "remaining_quota": max(0, self._daily_limit - today_count),
            "window_size": self._window_size,
            "records_count": len(self._records),
            "should_slow_down": self.should_slow_down(),
            "recent_records": recent_records
        }

    def get_rate_multiplier(self) -> float:
        """获取当前速率倍率"""
        failure_rate = self._get_failure_rate()

        if failure_rate < self._failure_rate_low:
            return 1.0
        elif failure_rate < self._failure_rate_high:
            return 1.5
        else:
            return 2.0


class ThrottledExecutor:
    """
    节流执行器

    封装速率限制逻辑，提供简单的执行接口

    使用示例:
        executor = ThrottledExecutor(rate_limiter)

        if executor.can_execute():
            try:
                do_work()
                executor.record_success()
            except Exception as e:
                executor.record_failure()
    """

    def __init__(self, rate_limiter: RateLimiter):
        self._limiter = rate_limiter
        self._last_execution: datetime = None
        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        """检查是否可以执行"""
        # 检查每日限额
        if not self._limiter.can_send_today():
            logger.warning("已达每日限额，无法执行")
            return False

        # 检查执行间隔
        with self._lock:
            if self._last_execution:
                elapsed = (datetime.now() - self._last_execution).total_seconds()
                required_delay = self._limiter.get_next_delay()

                if elapsed < required_delay:
                    logger.debug(f"执行间隔不足: {elapsed:.1f}s < {required_delay}s")
                    return False

        return True

    def record_success(self):
        """记录执行成功"""
        with self._lock:
            self._last_execution = datetime.now()
        self._limiter.record_result(success=True)

    def record_failure(self):
        """记录执行失败"""
        with self._lock:
            self._last_execution = datetime.now()
        self._limiter.record_result(success=False)

    def get_wait_time(self) -> int:
        """获取需要等待的时间（秒）"""
        with self._lock:
            if not self._last_execution:
                return 0

            elapsed = (datetime.now() - self._last_execution).total_seconds()
            required_delay = self._limiter.get_next_delay()

            return max(0, int(required_delay - elapsed))
