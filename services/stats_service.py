"""
统计服务模块

提供任务执行统计、趋势分析等功能
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

from data.database import Database
from models.stats import DailyStats, WeeklyStats, HourlyDistribution, ChannelStats, GroupStats
from models.enums import TaskStatus, Channel
from .time_service import TimeService, get_time_service

logger = logging.getLogger("wechat_auto_sender.stats_service")


class StatsService:
    """
    统计服务

    提供日统计、周统计、渠道统计、趋势数据等功能
    使用 SQL 聚合查询提高效率
    """

    def __init__(self, db: Database, time_service: TimeService = None):
        """
        初始化统计服务

        Args:
            db: 数据库实例
            time_service: 时间服务实例
        """
        self._db = db
        self._time_service = time_service or get_time_service()

        # 简单缓存
        self._cache: Dict[str, tuple] = {}  # key -> (data, expire_time)
        self._cache_ttl = 60  # 缓存60秒

    # ==================== 日统计 ====================

    def get_today_stats(self) -> DailyStats:
        """
        获取今日统计

        Returns:
            今日统计数据
        """
        return self.get_daily_stats(self._time_service.today())

    def get_daily_stats(self, target_date: date) -> DailyStats:
        """
        获取指定日期的统计

        Args:
            target_date: 目标日期

        Returns:
            日统计数据
        """
        cache_key = f"daily_{target_date.isoformat()}"

        # 检查缓存（今天的数据不缓存太久）
        if target_date != self._time_service.today():
            cached = self._get_cache(cache_key)
            if cached:
                return cached

        date_str = target_date.isoformat()

        try:
            with self._db.connection() as conn:
                # 基础统计
                cursor = conn.execute("""
                    SELECT
                        status,
                        COUNT(*) as count
                    FROM tasks
                    WHERE DATE(COALESCE(scheduled_time, created_at)) = ?
                    GROUP BY status
                """, (date_str,))

                status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

                # 按渠道统计（总数）
                cursor = conn.execute("""
                    SELECT
                        channel,
                        COUNT(*) as count
                    FROM tasks
                    WHERE DATE(COALESCE(scheduled_time, created_at)) = ?
                    GROUP BY channel
                """, (date_str,))

                by_channel = {row["channel"]: row["count"] for row in cursor.fetchall()}

                # 按渠道统计（成功数）
                cursor = conn.execute("""
                    SELECT
                        channel,
                        COUNT(*) as count
                    FROM tasks
                    WHERE DATE(COALESCE(scheduled_time, created_at)) = ?
                    AND status = 'success'
                    GROUP BY channel
                """, (date_str,))

                by_channel_success = {row["channel"]: row["count"] for row in cursor.fetchall()}

                # 按群统计
                cursor = conn.execute("""
                    SELECT
                        group_name,
                        COUNT(*) as count
                    FROM tasks
                    WHERE DATE(COALESCE(scheduled_time, created_at)) = ?
                    AND group_name != ''
                    GROUP BY group_name
                    ORDER BY count DESC
                    LIMIT 50
                """, (date_str,))

                by_group = {row["group_name"]: row["count"] for row in cursor.fetchall()}

                # 高峰时段
                cursor = conn.execute("""
                    SELECT
                        CAST(strftime('%H', executed_time) AS INTEGER) as hour,
                        COUNT(*) as count
                    FROM tasks
                    WHERE DATE(executed_time) = ?
                    AND executed_time IS NOT NULL
                    GROUP BY hour
                    ORDER BY count DESC
                    LIMIT 1
                """, (date_str,))

                peak_row = cursor.fetchone()
                peak_hour = peak_row["hour"] if peak_row else None

                # 平均执行时间（从调度时间到执行时间）
                cursor = conn.execute("""
                    SELECT
                        AVG(
                            CAST((julianday(executed_time) - julianday(scheduled_time)) * 86400 AS INTEGER)
                        ) as avg_time
                    FROM tasks
                    WHERE DATE(executed_time) = ?
                    AND executed_time IS NOT NULL
                    AND scheduled_time IS NOT NULL
                    AND status = 'success'
                """, (date_str,))

                avg_row = cursor.fetchone()
                avg_execution_time = avg_row["avg_time"] if avg_row and avg_row["avg_time"] else 0

            # 构建统计对象
            stats = DailyStats(
                stat_date=target_date,
                total_tasks=sum(status_counts.values()),
                success_count=status_counts.get("success", 0),
                failed_count=status_counts.get("failed", 0),
                skipped_count=status_counts.get("skipped", 0),
                pending_count=status_counts.get("pending", 0) + status_counts.get("scheduled", 0),
                cancelled_count=status_counts.get("cancelled", 0),
                paused_count=status_counts.get("paused", 0),
                moment_count=by_channel.get("moment", 0),
                agent_group_count=by_channel.get("agent_group", 0),
                customer_group_count=by_channel.get("customer_group", 0),
                moment_success_count=by_channel_success.get("moment", 0),
                agent_group_success_count=by_channel_success.get("agent_group", 0),
                customer_group_success_count=by_channel_success.get("customer_group", 0),
            )

            # 缓存非今天的数据
            if target_date != self._time_service.today():
                self._set_cache(cache_key, stats)

            return stats

        except Exception as e:
            logger.error(f"获取日统计失败: {e}")
            return DailyStats(stat_date=target_date)

    # ==================== 周统计 ====================

    def get_weekly_stats(self, week_start: date = None) -> WeeklyStats:
        """
        获取周统计

        Args:
            week_start: 周开始日期（周一），为 None 则使用本周

        Returns:
            周统计数据
        """
        if week_start is None:
            week_start, week_end = self._time_service.get_week_range()
        else:
            week_end = week_start + timedelta(days=6)

        cache_key = f"weekly_{week_start.isoformat()}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        # 获取每日统计
        daily_stats_list = []
        current_date = week_start
        while current_date <= week_end:
            daily_stats_list.append(self.get_daily_stats(current_date))
            current_date += timedelta(days=1)

        # 创建 WeeklyStats 并聚合
        stats = WeeklyStats(
            start_date=week_start,
            end_date=week_end,
            daily_stats=daily_stats_list,
        )
        stats.aggregate_from_daily()

        # 缓存（如果不是本周）
        today = self._time_service.today()
        if not (week_start <= today <= week_end):
            self._set_cache(cache_key, stats)

        return stats

    # ==================== 渠道和群统计 ====================

    def get_stats_by_channel(self, start_date: date, end_date: date) -> Dict[str, ChannelStats]:
        """
        按渠道统计

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            渠道 -> 统计数据
        """
        try:
            with self._db.connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        channel,
                        status,
                        COUNT(*) as count
                    FROM tasks
                    WHERE DATE(COALESCE(scheduled_time, created_at)) BETWEEN ? AND ?
                    GROUP BY channel, status
                """, (start_date.isoformat(), end_date.isoformat()))

                # 汇总
                channel_data: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
                for row in cursor.fetchall():
                    channel_data[row["channel"]][row["status"]] = row["count"]

                result = {}
                for channel, status_counts in channel_data.items():
                    total = sum(status_counts.values())
                    result[channel] = ChannelStats(
                        channel=channel,
                        total=total,
                        success=status_counts.get("success", 0),
                        failed=status_counts.get("failed", 0)
                    )

                return result

        except Exception as e:
            logger.error(f"获取渠道统计失败: {e}")
            return {}

    def get_stats_by_group(self, start_date: date, end_date: date) -> Dict[str, GroupStats]:
        """
        按群统计

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            群名 -> 统计数据
        """
        try:
            with self._db.connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        group_name,
                        status,
                        COUNT(*) as count,
                        MAX(executed_time) as last_send
                    FROM tasks
                    WHERE DATE(COALESCE(scheduled_time, created_at)) BETWEEN ? AND ?
                    AND group_name != ''
                    GROUP BY group_name, status
                """, (start_date.isoformat(), end_date.isoformat()))

                # 汇总
                group_data: Dict[str, Dict] = defaultdict(lambda: {
                    "total": 0, "success": 0, "failed": 0, "last_send": None
                })

                for row in cursor.fetchall():
                    gname = row["group_name"]
                    status = row["status"]
                    count = row["count"]

                    group_data[gname]["total"] += count
                    if status == "success":
                        group_data[gname]["success"] += count
                    elif status == "failed":
                        group_data[gname]["failed"] += count

                    if row["last_send"]:
                        current_last = group_data[gname]["last_send"]
                        if current_last is None or row["last_send"] > current_last:
                            group_data[gname]["last_send"] = row["last_send"]

                result = {}
                for gname, data in group_data.items():
                    last_send = None
                    if data["last_send"]:
                        last_send = self._time_service.parse_datetime(data["last_send"])

                    result[gname] = GroupStats(
                        group_name=gname,
                        total=data["total"],
                        success=data["success"],
                        failed=data["failed"],
                        last_send_time=last_send
                    )

                return result

        except Exception as e:
            logger.error(f"获取群统计失败: {e}")
            return {}

    # ==================== 趋势数据 ====================

    def get_trend_data(self, days: int = 7) -> List[DailyStats]:
        """
        获取趋势数据

        Args:
            days: 天数

        Returns:
            每日统计列表
        """
        end_date = self._time_service.today()
        start_date = end_date - timedelta(days=days - 1)

        result = []
        current_date = start_date
        while current_date <= end_date:
            result.append(self.get_daily_stats(current_date))
            current_date += timedelta(days=1)

        return result

    def get_success_rate(self, start_date: date, end_date: date) -> float:
        """
        计算成功率

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            成功率 (0.0 - 1.0)
        """
        try:
            with self._db.connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                        SUM(CASE WHEN status IN ('success', 'failed') THEN 1 ELSE 0 END) as executed
                    FROM tasks
                    WHERE DATE(COALESCE(scheduled_time, created_at)) BETWEEN ? AND ?
                """, (start_date.isoformat(), end_date.isoformat()))

                row = cursor.fetchone()
                if row and row["executed"] and row["executed"] > 0:
                    return row["success"] / row["executed"]
                return 0.0

        except Exception as e:
            logger.error(f"计算成功率失败: {e}")
            return 0.0

    # ==================== 时段分析 ====================

    def get_peak_hours(self, days: int = 30) -> HourlyDistribution:
        """
        统计发布高峰时段

        Args:
            days: 统计天数

        Returns:
            小时分布数据
        """
        end_date = self._time_service.today()
        start_date = end_date - timedelta(days=days - 1)

        try:
            with self._db.connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        CAST(strftime('%H', executed_time) AS INTEGER) as hour,
                        COUNT(*) as count
                    FROM tasks
                    WHERE DATE(executed_time) BETWEEN ? AND ?
                    AND executed_time IS NOT NULL
                    AND status = 'success'
                    GROUP BY hour
                    ORDER BY hour
                """, (start_date.isoformat(), end_date.isoformat()))

                distribution = {row["hour"]: row["count"] for row in cursor.fetchall()}

                return HourlyDistribution(distribution=distribution)

        except Exception as e:
            logger.error(f"获取高峰时段失败: {e}")
            return HourlyDistribution()

    # ==================== 综合报告 ====================

    def get_summary_report(self) -> dict:
        """
        获取综合统计报告

        Returns:
            综合报告字典
        """
        today = self._time_service.today()
        week_start, week_end = self._time_service.get_week_range()

        return {
            "generated_at": self._time_service.now().isoformat(),
            "today": self.get_today_stats().to_dict(),
            "week": self.get_weekly_stats(week_start).to_dict(),
            "trend_7days": [ds.to_dict() for ds in self.get_trend_data(7)],
            "success_rate_7days": round(self.get_success_rate(
                today - timedelta(days=6), today
            ), 4),
            "peak_hours": self.get_peak_hours(30).to_dict()
        }

    # ==================== 缓存管理 ====================

    def _get_cache(self, key: str):
        """获取缓存"""
        if key in self._cache:
            data, expire_time = self._cache[key]
            # 使用 TimeService 获取当前时间，保持时区一致性
            if self._time_service.now() < expire_time:
                return data
            del self._cache[key]
        return None

    def _set_cache(self, key: str, data, ttl: int = None):
        """设置缓存"""
        if ttl is None:
            ttl = self._cache_ttl
        # 使用 TimeService 获取当前时间，保持时区一致性
        expire_time = self._time_service.now() + timedelta(seconds=ttl)
        self._cache[key] = (data, expire_time)

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.debug("统计缓存已清空")
