"""
时间服务模块

提供统一的时区处理、时间格式化和活动时间段判断
"""
import logging
from datetime import datetime, date, time, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from .config_manager import get_config

logger = logging.getLogger("wechat_auto_sender.time_service")


# 常量
TIMEZONE = ZoneInfo("Asia/Shanghai")
DEFAULT_ACTIVE_START = "08:00"
DEFAULT_ACTIVE_END = "22:00"
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_TIME_FORMAT = "%H:%M"
DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class TimeService:
    """
    时间服务

    统一处理应用中的所有时间相关操作
    所有时间使用 Asia/Shanghai 时区
    """

    def __init__(self, config: dict = None):
        """
        初始化时间服务

        Args:
            config: 配置字典（可选）
        """
        self._config = config or {}

        # 从配置读取活动时间段
        scheduler_config = self._config.get("scheduler", {})
        work_hours = scheduler_config.get("work_hours", {})

        self._active_start = work_hours.get("start", DEFAULT_ACTIVE_START)
        self._active_end = work_hours.get("end", DEFAULT_ACTIVE_END)
        self._weekend_work = scheduler_config.get("weekend_work", False)

    # ==================== 当前时间 ====================

    def now(self) -> datetime:
        """
        获取当前时间 (Asia/Shanghai 时区)

        Returns:
            当前时间
        """
        return datetime.now(TIMEZONE)

    def today(self) -> date:
        """
        获取今天日期

        Returns:
            今天日期
        """
        return self.now().date()

    def current_hour(self) -> int:
        """
        获取当前小时 (0-23)

        Returns:
            当前小时
        """
        return self.now().hour

    # ==================== 格式化 ====================

    def format_datetime(self, dt: datetime,
                       fmt: str = DEFAULT_DATETIME_FORMAT) -> str:
        """
        格式化日期时间

        Args:
            dt: 日期时间对象
            fmt: 格式字符串

        Returns:
            格式化后的字符串
        """
        if dt is None:
            return ""
        return dt.strftime(fmt)

    def format_date(self, d: date,
                   fmt: str = DEFAULT_DATE_FORMAT) -> str:
        """
        格式化日期

        Args:
            d: 日期对象
            fmt: 格式字符串

        Returns:
            格式化后的字符串
        """
        if d is None:
            return ""
        return d.strftime(fmt)

    def format_time(self, t: time,
                   fmt: str = DEFAULT_TIME_FORMAT) -> str:
        """
        格式化时间

        Args:
            t: 时间对象
            fmt: 格式字符串

        Returns:
            格式化后的字符串
        """
        if t is None:
            return ""
        return t.strftime(fmt)

    def format_duration(self, seconds: int) -> str:
        """
        格式化时长

        Args:
            seconds: 秒数

        Returns:
            人类可读的时长字符串
        """
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            if secs:
                return f"{minutes}分{secs}秒"
            return f"{minutes}分钟"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes:
                return f"{hours}小时{minutes}分钟"
            return f"{hours}小时"

    # ==================== 解析 ====================

    def parse_datetime(self, s: str,
                      fmt: str = None) -> Optional[datetime]:
        """
        解析日期时间字符串

        Args:
            s: 日期时间字符串
            fmt: 格式字符串（可选，自动检测）

        Returns:
            日期时间对象，解析失败返回 None
        """
        if not s:
            return None

        formats = [fmt] if fmt else [
            DEFAULT_DATETIME_FORMAT,
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y/%m/%d %H:%M:%S",
            DEFAULT_DATE_FORMAT
        ]

        for f in formats:
            try:
                dt = datetime.strptime(s, f)
                # 添加时区信息
                return dt.replace(tzinfo=TIMEZONE)
            except ValueError:
                continue

        logger.warning(f"无法解析日期时间: {s}")
        return None

    def parse_date(self, s: str,
                  fmt: str = DEFAULT_DATE_FORMAT) -> Optional[date]:
        """
        解析日期字符串

        Args:
            s: 日期字符串
            fmt: 格式字符串

        Returns:
            日期对象，解析失败返回 None
        """
        if not s:
            return None

        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            logger.warning(f"无法解析日期: {s}")
            return None

    def parse_time(self, s: str) -> Optional[time]:
        """
        解析时间字符串 (HH:MM 格式)

        Args:
            s: 时间字符串 (如 "08:30")

        Returns:
            时间对象，解析失败返回 None
        """
        if not s:
            return None

        try:
            parts = s.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            second = int(parts[2]) if len(parts) > 2 else 0
            return time(hour, minute, second, tzinfo=TIMEZONE)
        except (ValueError, IndexError):
            logger.warning(f"无法解析时间: {s}")
            return None

    # ==================== 活动时间判断 ====================

    def is_within_active_hours(self, dt: datetime = None) -> bool:
        """
        检查是否在活动时间段内

        Args:
            dt: 要检查的时间，为 None 则使用当前时间

        Returns:
            是否在活动时间段内
        """
        if dt is None:
            dt = self.now()

        # 检查周末
        if not self._weekend_work and dt.weekday() >= 5:
            return False

        # 解析活动时间
        start_time = self.parse_time(self._active_start)
        end_time = self.parse_time(self._active_end)

        if start_time is None or end_time is None:
            logger.warning("活动时间配置无效，默认允许")
            return True

        current_time = dt.time()

        # 比较时间（去除时区信息进行比较）
        start = time(start_time.hour, start_time.minute)
        end = time(end_time.hour, end_time.minute)
        current = time(current_time.hour, current_time.minute)

        return start <= current <= end

    def get_next_active_time(self) -> datetime:
        """
        获取下一个活动时间段开始时间

        如果当前在活动时间内，返回当前时间
        如果当前在活动时间外，返回下一个活动时间段开始

        Returns:
            下一个活动时间
        """
        now = self.now()

        # 当前在活动时间内
        if self.is_within_active_hours(now):
            return now

        # 解析活动开始时间
        start_time = self.parse_time(self._active_start)
        if start_time is None:
            start_time = time(8, 0)

        # 今天的活动开始时间
        today_start = now.replace(
            hour=start_time.hour,
            minute=start_time.minute,
            second=0,
            microsecond=0
        )

        # 如果今天的活动时间还没开始
        if now < today_start and (self._weekend_work or now.weekday() < 5):
            return today_start

        # 否则找下一个工作日
        next_day = now + timedelta(days=1)
        while True:
            if self._weekend_work or next_day.weekday() < 5:
                return next_day.replace(
                    hour=start_time.hour,
                    minute=start_time.minute,
                    second=0,
                    microsecond=0
                )
            next_day += timedelta(days=1)

    # ==================== 时间计算 ====================

    def seconds_until(self, target: datetime) -> int:
        """
        计算距离目标时间的秒数

        Args:
            target: 目标时间

        Returns:
            秒数（如果目标时间已过，返回负数）
        """
        if target is None:
            return 0

        now = self.now()

        # 确保 target 有时区信息
        if target.tzinfo is None:
            target = target.replace(tzinfo=TIMEZONE)

        delta = target - now
        return int(delta.total_seconds())

    def add_seconds(self, dt: datetime, seconds: int) -> datetime:
        """
        添加秒数到日期时间

        Args:
            dt: 原始日期时间
            seconds: 要添加的秒数

        Returns:
            新的日期时间
        """
        return dt + timedelta(seconds=seconds)

    def add_days(self, d: date, days: int) -> date:
        """
        添加天数到日期

        Args:
            d: 原始日期
            days: 要添加的天数

        Returns:
            新的日期
        """
        return d + timedelta(days=days)

    # ==================== 周期计算 ====================

    def get_week_range(self, dt: datetime = None) -> Tuple[date, date]:
        """
        获取所在周的起止日期

        Args:
            dt: 日期时间，为 None 则使用当前时间

        Returns:
            (周一日期, 周日日期)
        """
        if dt is None:
            dt = self.now()

        d = dt.date() if isinstance(dt, datetime) else dt

        # 计算周一
        monday = d - timedelta(days=d.weekday())
        # 计算周日
        sunday = monday + timedelta(days=6)

        return monday, sunday

    def get_month_range(self, dt: datetime = None) -> Tuple[date, date]:
        """
        获取所在月的起止日期

        Args:
            dt: 日期时间，为 None 则使用当前时间

        Returns:
            (月初日期, 月末日期)
        """
        if dt is None:
            dt = self.now()

        d = dt.date() if isinstance(dt, datetime) else dt

        # 月初
        month_start = d.replace(day=1)

        # 月末（下个月1号减1天）
        if d.month == 12:
            next_month = d.replace(year=d.year + 1, month=1, day=1)
        else:
            next_month = d.replace(month=d.month + 1, day=1)
        month_end = next_month - timedelta(days=1)

        return month_start, month_end

    def get_date_range(self, days: int) -> Tuple[date, date]:
        """
        获取最近N天的日期范围

        Args:
            days: 天数

        Returns:
            (开始日期, 结束日期)
        """
        end_date = self.today()
        start_date = end_date - timedelta(days=days - 1)
        return start_date, end_date

    # ==================== 比较 ====================

    def is_same_day(self, dt1: datetime, dt2: datetime) -> bool:
        """判断两个时间是否同一天"""
        if dt1 is None or dt2 is None:
            return False
        return dt1.date() == dt2.date()

    def is_today(self, dt: datetime) -> bool:
        """判断是否是今天"""
        if dt is None:
            return False
        return dt.date() == self.today()

    def is_past(self, dt: datetime) -> bool:
        """判断时间是否已过"""
        if dt is None:
            return False
        return dt < self.now()

    def is_future(self, dt: datetime) -> bool:
        """判断时间是否在未来"""
        if dt is None:
            return False
        return dt > self.now()


# 创建全局实例
_time_service: Optional[TimeService] = None


def get_time_service(config: dict = None) -> TimeService:
    """获取时间服务实例"""
    global _time_service
    if _time_service is None:
        _time_service = TimeService(config)
    return _time_service


# 便捷函数
def now() -> datetime:
    """获取当前时间"""
    return get_time_service().now()


def today() -> date:
    """获取今天日期"""
    return get_time_service().today()


def format_datetime(dt: datetime, fmt: str = DEFAULT_DATETIME_FORMAT) -> str:
    """格式化日期时间"""
    return get_time_service().format_datetime(dt, fmt)


def parse_datetime(s: str, fmt: str = None) -> Optional[datetime]:
    """解析日期时间"""
    return get_time_service().parse_datetime(s, fmt)


def is_within_active_hours(dt: datetime = None) -> bool:
    """检查是否在活动时间段"""
    return get_time_service().is_within_active_hours(dt)
