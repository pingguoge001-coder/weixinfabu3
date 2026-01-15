"""统计模型模块"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional

from .enums import TaskStatus, Channel


@dataclass
class DailyStats:
    """日统计模型"""

    stat_date: date = field(default_factory=date.today)

    # 任务计数
    total_tasks: int = 0
    success_count: int = 0
    failed_count: int = 0
    pending_count: int = 0
    skipped_count: int = 0
    cancelled_count: int = 0
    paused_count: int = 0

    # 渠道分布（总数）
    moment_count: int = 0           # 朋友圈任务数
    agent_group_count: int = 0      # 代理群任务数
    customer_group_count: int = 0   # 客户群任务数

    # 渠道分布（成功数）
    moment_success_count: int = 0        # 朋友圈成功数
    agent_group_success_count: int = 0   # 代理群成功数
    customer_group_success_count: int = 0 # 客户群成功数

    @property
    def group_count(self) -> int:
        """群发总数（兼容旧代码）"""
        return self.agent_group_count + self.customer_group_count

    # 重试统计
    total_retries: int = 0

    # 时间统计
    first_task_time: Optional[datetime] = None
    last_task_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """成功率"""
        completed = self.success_count + self.failed_count
        if completed == 0:
            return 0.0
        return self.success_count / completed * 100

    @property
    def completion_rate(self) -> float:
        """完成率（成功+失败/总数）"""
        if self.total_tasks == 0:
            return 0.0
        completed = self.success_count + self.failed_count
        return completed / self.total_tasks * 100

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "stat_date": self.stat_date.isoformat(),
            "total_tasks": self.total_tasks,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "pending_count": self.pending_count,
            "skipped_count": self.skipped_count,
            "cancelled_count": self.cancelled_count,
            "paused_count": self.paused_count,
            "moment_count": self.moment_count,
            "agent_group_count": self.agent_group_count,
            "customer_group_count": self.customer_group_count,
            "moment_success_count": self.moment_success_count,
            "agent_group_success_count": self.agent_group_success_count,
            "customer_group_success_count": self.customer_group_success_count,
            "group_count": self.group_count,
            "total_retries": self.total_retries,
            "success_rate": round(self.success_rate, 2),
            "completion_rate": round(self.completion_rate, 2),
            "first_task_time": self.first_task_time.isoformat() if self.first_task_time else None,
            "last_task_time": self.last_task_time.isoformat() if self.last_task_time else None,
        }


@dataclass
class WeeklyStats:
    """周统计模型"""

    start_date: date = field(default_factory=date.today)
    end_date: date = field(default_factory=date.today)

    # 日统计列表
    daily_stats: List[DailyStats] = field(default_factory=list)

    # 聚合统计
    total_tasks: int = 0
    success_count: int = 0
    failed_count: int = 0

    # 按渠道统计
    channel_stats: Dict[str, int] = field(default_factory=dict)

    # 按产品统计
    product_stats: Dict[str, int] = field(default_factory=dict)

    # 失败原因统计
    failure_reasons: Dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """周成功率"""
        completed = self.success_count + self.failed_count
        if completed == 0:
            return 0.0
        return self.success_count / completed * 100

    @property
    def avg_daily_tasks(self) -> float:
        """日均任务数"""
        days = len(self.daily_stats)
        if days == 0:
            return 0.0
        return self.total_tasks / days

    def aggregate_from_daily(self) -> None:
        """从日统计聚合数据"""
        self.total_tasks = sum(d.total_tasks for d in self.daily_stats)
        self.success_count = sum(d.success_count for d in self.daily_stats)
        self.failed_count = sum(d.failed_count for d in self.daily_stats)

        # 聚合渠道统计
        self.channel_stats = {
            Channel.moment.value: sum(d.moment_count for d in self.daily_stats),
            Channel.agent_group.value: sum(d.agent_group_count for d in self.daily_stats),
            Channel.customer_group.value: sum(d.customer_group_count for d in self.daily_stats),
        }

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "total_tasks": self.total_tasks,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "success_rate": round(self.success_rate, 2),
            "avg_daily_tasks": round(self.avg_daily_tasks, 2),
            "channel_stats": self.channel_stats,
            "product_stats": self.product_stats,
            "failure_reasons": self.failure_reasons,
            "daily_stats": [d.to_dict() for d in self.daily_stats],
        }


@dataclass
class TaskSummary:
    """任务概览模型（用于仪表盘）"""

    # 今日统计
    today_total: int = 0
    today_success: int = 0
    today_failed: int = 0
    today_pending: int = 0

    # 历史统计
    total_tasks: int = 0
    total_success: int = 0
    total_failed: int = 0

    # 当前状态
    running_count: int = 0
    scheduled_count: int = 0
    paused_count: int = 0

    # 更新时间
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def today_success_rate(self) -> float:
        """今日成功率"""
        completed = self.today_success + self.today_failed
        if completed == 0:
            return 0.0
        return self.today_success / completed * 100

    @property
    def overall_success_rate(self) -> float:
        """总体成功率"""
        completed = self.total_success + self.total_failed
        if completed == 0:
            return 0.0
        return self.total_success / completed * 100

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "today_total": self.today_total,
            "today_success": self.today_success,
            "today_failed": self.today_failed,
            "today_pending": self.today_pending,
            "today_success_rate": round(self.today_success_rate, 2),
            "total_tasks": self.total_tasks,
            "total_success": self.total_success,
            "total_failed": self.total_failed,
            "overall_success_rate": round(self.overall_success_rate, 2),
            "running_count": self.running_count,
            "scheduled_count": self.scheduled_count,
            "paused_count": self.paused_count,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class HourlyDistribution:
    """小时分布统计"""
    # 小时 -> 任务数
    distribution: Dict[int, int] = field(default_factory=dict)

    # 高峰时段
    peak_hour: Optional[int] = None
    peak_count: int = 0

    def __post_init__(self):
        """计算高峰时段"""
        if self.distribution:
            self.peak_hour = max(self.distribution, key=self.distribution.get)
            self.peak_count = self.distribution[self.peak_hour]

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "distribution": self.distribution,
            "peak_hour": self.peak_hour,
            "peak_count": self.peak_count
        }


@dataclass
class ChannelStats:
    """渠道统计"""
    channel: str
    total: int = 0
    success: int = 0
    failed: int = 0
    success_rate: float = 0.0

    def __post_init__(self):
        """计算成功率"""
        executed = self.success + self.failed
        if executed > 0:
            self.success_rate = self.success / executed

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "channel": self.channel,
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "success_rate": round(self.success_rate, 4)
        }


@dataclass
class GroupStats:
    """群统计"""
    group_name: str
    total: int = 0
    success: int = 0
    failed: int = 0
    success_rate: float = 0.0
    last_send_time: Optional[datetime] = None

    def __post_init__(self):
        """计算成功率"""
        executed = self.success + self.failed
        if executed > 0:
            self.success_rate = self.success / executed

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "group_name": self.group_name,
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "success_rate": round(self.success_rate, 4),
            "last_send_time": self.last_send_time.isoformat() if self.last_send_time else None
        }
