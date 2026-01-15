"""Tests for statistics models"""
import pytest
from datetime import datetime, date, timedelta
from models.stats import DailyStats, WeeklyStats, TaskSummary
from models.enums import Channel


class TestDailyStats:
    """Test DailyStats model"""

    def test_daily_stats_creation_defaults(self):
        """Test DailyStats creation with default values"""
        stats = DailyStats()

        assert stats.stat_date == date.today()
        assert stats.total_tasks == 0
        assert stats.success_count == 0
        assert stats.failed_count == 0
        assert stats.pending_count == 0
        assert stats.skipped_count == 0
        assert stats.cancelled_count == 0
        assert stats.paused_count == 0
        assert stats.moment_count == 0
        assert stats.group_count == 0
        assert stats.total_retries == 0
        assert stats.first_task_time is None
        assert stats.last_task_time is None

    def test_daily_stats_creation_with_values(self, sample_daily_stats):
        """Test DailyStats creation with provided values"""
        assert sample_daily_stats.total_tasks == 100
        assert sample_daily_stats.success_count == 80
        assert sample_daily_stats.failed_count == 10
        assert sample_daily_stats.pending_count == 10

    def test_daily_stats_success_rate(self, sample_daily_stats):
        """Test success rate calculation"""
        # success_count=80, failed_count=10
        # success_rate = 80 / (80+10) * 100 = 88.89%
        expected_rate = 80 / 90 * 100
        assert abs(sample_daily_stats.success_rate - expected_rate) < 0.01

    def test_daily_stats_success_rate_perfect(self):
        """Test success rate with 100% success"""
        stats = DailyStats(
            total_tasks=50,
            success_count=50,
            failed_count=0
        )
        assert stats.success_rate == 100.0

    def test_daily_stats_success_rate_zero(self):
        """Test success rate with 0% success"""
        stats = DailyStats(
            total_tasks=50,
            success_count=0,
            failed_count=50
        )
        assert stats.success_rate == 0.0

    def test_daily_stats_success_rate_no_completed(self):
        """Test success rate when no tasks completed"""
        stats = DailyStats(
            total_tasks=100,
            success_count=0,
            failed_count=0,
            pending_count=100
        )
        assert stats.success_rate == 0.0

    def test_daily_stats_completion_rate(self, sample_daily_stats):
        """Test completion rate calculation"""
        # total_tasks=100, success_count=80, failed_count=10
        # completion_rate = (80+10) / 100 * 100 = 90%
        expected_rate = 90.0
        assert abs(sample_daily_stats.completion_rate - expected_rate) < 0.01

    def test_daily_stats_completion_rate_full(self):
        """Test completion rate with all tasks completed"""
        stats = DailyStats(
            total_tasks=100,
            success_count=80,
            failed_count=20
        )
        assert stats.completion_rate == 100.0

    def test_daily_stats_completion_rate_partial(self):
        """Test completion rate with partial completion"""
        stats = DailyStats(
            total_tasks=100,
            success_count=30,
            failed_count=20,
            pending_count=50
        )
        # (30+20) / 100 * 100 = 50%
        assert stats.completion_rate == 50.0

    def test_daily_stats_zero_division(self):
        """Test that 0 tasks returns 0.0 rates"""
        stats = DailyStats(total_tasks=0)
        assert stats.success_rate == 0.0
        assert stats.completion_rate == 0.0

    def test_daily_stats_to_dict(self, sample_daily_stats):
        """Test to_dict serialization"""
        stats_dict = sample_daily_stats.to_dict()

        assert isinstance(stats_dict, dict)
        assert stats_dict["total_tasks"] == 100
        assert stats_dict["success_count"] == 80
        assert stats_dict["failed_count"] == 10
        assert stats_dict["pending_count"] == 10
        assert "success_rate" in stats_dict
        assert "completion_rate" in stats_dict
        assert isinstance(stats_dict["success_rate"], float)
        assert isinstance(stats_dict["completion_rate"], float)

    def test_daily_stats_to_dict_with_times(self):
        """Test to_dict with time fields"""
        first_time = datetime(2025, 12, 5, 8, 0, 0)
        last_time = datetime(2025, 12, 5, 18, 0, 0)

        stats = DailyStats(
            stat_date=date(2025, 12, 5),
            first_task_time=first_time,
            last_task_time=last_time
        )
        stats_dict = stats.to_dict()

        assert stats_dict["stat_date"] == "2025-12-05"
        assert stats_dict["first_task_time"] == first_time.isoformat()
        assert stats_dict["last_task_time"] == last_time.isoformat()

    def test_daily_stats_to_dict_none_times(self):
        """Test to_dict with None time fields"""
        stats = DailyStats()
        stats_dict = stats.to_dict()

        assert stats_dict["first_task_time"] is None
        assert stats_dict["last_task_time"] is None

    def test_daily_stats_channel_distribution(self):
        """Test channel distribution tracking"""
        stats = DailyStats(
            total_tasks=150,
            moment_count=100,
            group_count=50
        )

        assert stats.moment_count == 100
        assert stats.group_count == 50
        assert stats.moment_count + stats.group_count == 150


class TestWeeklyStats:
    """Test WeeklyStats model"""

    def test_weekly_stats_creation_defaults(self):
        """Test WeeklyStats creation with default values"""
        stats = WeeklyStats()

        assert stats.start_date == date.today()
        assert stats.end_date == date.today()
        assert stats.daily_stats == []
        assert stats.total_tasks == 0
        assert stats.success_count == 0
        assert stats.failed_count == 0
        assert stats.channel_stats == {}
        assert stats.product_stats == {}
        assert stats.failure_reasons == {}

    def test_weekly_stats_creation_with_dates(self):
        """Test WeeklyStats creation with specific dates"""
        start = date(2025, 12, 1)
        end = date(2025, 12, 7)

        stats = WeeklyStats(start_date=start, end_date=end)

        assert stats.start_date == start
        assert stats.end_date == end

    def test_weekly_stats_aggregate_from_daily(self):
        """Test aggregate_from_daily aggregates correctly"""
        daily1 = DailyStats(
            stat_date=date(2025, 12, 1),
            total_tasks=50,
            success_count=40,
            failed_count=10,
            moment_count=30,
            group_count=20
        )
        daily2 = DailyStats(
            stat_date=date(2025, 12, 2),
            total_tasks=60,
            success_count=50,
            failed_count=10,
            moment_count=40,
            group_count=20
        )

        stats = WeeklyStats(
            start_date=date(2025, 12, 1),
            end_date=date(2025, 12, 2),
            daily_stats=[daily1, daily2]
        )

        stats.aggregate_from_daily()

        assert stats.total_tasks == 110  # 50 + 60
        assert stats.success_count == 90  # 40 + 50
        assert stats.failed_count == 20  # 10 + 10
        assert stats.channel_stats[Channel.moment.value] == 70  # 30 + 40
        assert stats.channel_stats[Channel.group.value] == 40  # 20 + 20

    def test_weekly_stats_aggregate_empty_daily(self):
        """Test aggregate_from_daily with empty daily list"""
        stats = WeeklyStats(daily_stats=[])
        stats.aggregate_from_daily()

        assert stats.total_tasks == 0
        assert stats.success_count == 0
        assert stats.failed_count == 0

    def test_weekly_stats_avg_daily_tasks(self):
        """Test avg_daily_tasks calculation"""
        daily1 = DailyStats(total_tasks=50)
        daily2 = DailyStats(total_tasks=60)
        daily3 = DailyStats(total_tasks=70)

        stats = WeeklyStats(daily_stats=[daily1, daily2, daily3])
        stats.aggregate_from_daily()

        # total = 180, days = 3, avg = 60.0
        assert stats.avg_daily_tasks == 60.0

    def test_weekly_stats_avg_daily_tasks_uneven(self):
        """Test avg_daily_tasks with uneven distribution"""
        daily1 = DailyStats(total_tasks=100)
        daily2 = DailyStats(total_tasks=50)
        daily3 = DailyStats(total_tasks=25)

        stats = WeeklyStats(daily_stats=[daily1, daily2, daily3])
        stats.aggregate_from_daily()

        # total = 175, days = 3, avg = 58.33...
        expected_avg = 175 / 3
        assert abs(stats.avg_daily_tasks - expected_avg) < 0.01

    def test_weekly_stats_avg_daily_tasks_zero_days(self):
        """Test avg_daily_tasks returns 0.0 when no days"""
        stats = WeeklyStats(daily_stats=[])
        assert stats.avg_daily_tasks == 0.0

    def test_weekly_stats_success_rate(self):
        """Test weekly success rate calculation"""
        daily1 = DailyStats(success_count=40, failed_count=10)
        daily2 = DailyStats(success_count=50, failed_count=10)

        stats = WeeklyStats(daily_stats=[daily1, daily2])
        stats.aggregate_from_daily()

        # success=90, failed=20, rate = 90/110 * 100 = 81.82%
        expected_rate = 90 / 110 * 100
        assert abs(stats.success_rate - expected_rate) < 0.01

    def test_weekly_stats_success_rate_no_completed(self):
        """Test weekly success rate when no tasks completed"""
        stats = WeeklyStats()
        assert stats.success_rate == 0.0

    def test_weekly_stats_to_dict(self):
        """Test to_dict serialization"""
        daily = DailyStats(
            stat_date=date(2025, 12, 5),
            total_tasks=50,
            success_count=40,
            failed_count=10
        )

        stats = WeeklyStats(
            start_date=date(2025, 12, 1),
            end_date=date(2025, 12, 7),
            daily_stats=[daily]
        )
        stats.aggregate_from_daily()

        stats_dict = stats.to_dict()

        assert isinstance(stats_dict, dict)
        assert stats_dict["start_date"] == "2025-12-01"
        assert stats_dict["end_date"] == "2025-12-07"
        assert stats_dict["total_tasks"] == 50
        assert "success_rate" in stats_dict
        assert "avg_daily_tasks" in stats_dict
        assert "daily_stats" in stats_dict
        assert len(stats_dict["daily_stats"]) == 1

    def test_weekly_stats_channel_stats(self):
        """Test channel stats aggregation"""
        daily1 = DailyStats(moment_count=30, group_count=20)
        daily2 = DailyStats(moment_count=40, group_count=10)
        daily3 = DailyStats(moment_count=50, group_count=30)

        stats = WeeklyStats(daily_stats=[daily1, daily2, daily3])
        stats.aggregate_from_daily()

        assert stats.channel_stats[Channel.moment.value] == 120  # 30+40+50
        assert stats.channel_stats[Channel.group.value] == 60  # 20+10+30


class TestTaskSummary:
    """Test TaskSummary model"""

    def test_task_summary_creation_defaults(self):
        """Test TaskSummary creation with default values"""
        summary = TaskSummary()

        assert summary.today_total == 0
        assert summary.today_success == 0
        assert summary.today_failed == 0
        assert summary.today_pending == 0
        assert summary.total_tasks == 0
        assert summary.total_success == 0
        assert summary.total_failed == 0
        assert summary.running_count == 0
        assert summary.scheduled_count == 0
        assert summary.paused_count == 0
        assert isinstance(summary.updated_at, datetime)

    def test_task_summary_creation_with_values(self):
        """Test TaskSummary creation with provided values"""
        summary = TaskSummary(
            today_total=100,
            today_success=80,
            today_failed=10,
            today_pending=10,
            total_tasks=1000,
            total_success=800,
            total_failed=150
        )

        assert summary.today_total == 100
        assert summary.today_success == 80
        assert summary.total_tasks == 1000
        assert summary.total_success == 800

    def test_task_summary_today_success_rate(self):
        """Test today success rate calculation"""
        summary = TaskSummary(
            today_success=80,
            today_failed=20
        )
        # 80 / (80+20) * 100 = 80%
        assert summary.today_success_rate == 80.0

    def test_task_summary_today_success_rate_perfect(self):
        """Test today success rate with 100% success"""
        summary = TaskSummary(
            today_success=100,
            today_failed=0
        )
        assert summary.today_success_rate == 100.0

    def test_task_summary_today_success_rate_zero(self):
        """Test today success rate with 0% success"""
        summary = TaskSummary(
            today_success=0,
            today_failed=50
        )
        assert summary.today_success_rate == 0.0

    def test_task_summary_today_success_rate_no_completed(self):
        """Test today success rate when no tasks completed"""
        summary = TaskSummary(
            today_success=0,
            today_failed=0,
            today_pending=100
        )
        assert summary.today_success_rate == 0.0

    def test_task_summary_overall_success_rate(self):
        """Test overall success rate calculation"""
        summary = TaskSummary(
            total_success=850,
            total_failed=150
        )
        # 850 / (850+150) * 100 = 85%
        assert summary.overall_success_rate == 85.0

    def test_task_summary_overall_success_rate_high(self):
        """Test overall success rate with high success"""
        summary = TaskSummary(
            total_success=950,
            total_failed=50
        )
        # 950 / 1000 * 100 = 95%
        assert summary.overall_success_rate == 95.0

    def test_task_summary_overall_success_rate_no_completed(self):
        """Test overall success rate when no tasks completed"""
        summary = TaskSummary(
            total_success=0,
            total_failed=0
        )
        assert summary.overall_success_rate == 0.0

    def test_task_summary_to_dict(self):
        """Test to_dict serialization"""
        summary = TaskSummary(
            today_total=100,
            today_success=80,
            today_failed=10,
            today_pending=10,
            total_tasks=1000,
            total_success=800,
            total_failed=150,
            running_count=5,
            scheduled_count=20,
            paused_count=3
        )

        summary_dict = summary.to_dict()

        assert isinstance(summary_dict, dict)
        assert summary_dict["today_total"] == 100
        assert summary_dict["today_success"] == 80
        assert summary_dict["today_failed"] == 10
        assert summary_dict["today_pending"] == 10
        assert summary_dict["total_tasks"] == 1000
        assert summary_dict["total_success"] == 800
        assert summary_dict["total_failed"] == 150
        assert "today_success_rate" in summary_dict
        assert "overall_success_rate" in summary_dict
        assert summary_dict["running_count"] == 5
        assert summary_dict["scheduled_count"] == 20
        assert summary_dict["paused_count"] == 3
        assert "updated_at" in summary_dict

    def test_task_summary_to_dict_rate_rounding(self):
        """Test to_dict rounds rates to 2 decimal places"""
        summary = TaskSummary(
            today_success=2,
            today_failed=3,
            total_success=123,
            total_failed=456
        )

        summary_dict = summary.to_dict()

        # today: 2/(2+3) = 40.00%
        assert summary_dict["today_success_rate"] == 40.0

        # overall: 123/(123+456) = 21.24...%
        assert isinstance(summary_dict["overall_success_rate"], float)
        # Check that it's rounded to 2 decimal places
        assert summary_dict["overall_success_rate"] == round(123 / 579 * 100, 2)


class TestStatsEdgeCases:
    """Test edge cases for stats models"""

    def test_daily_stats_all_status_types(self):
        """Test DailyStats with all status types populated"""
        stats = DailyStats(
            stat_date=date(2025, 12, 5),
            total_tasks=100,
            success_count=50,
            failed_count=20,
            pending_count=15,
            skipped_count=5,
            cancelled_count=5,
            paused_count=5
        )

        assert stats.total_tasks == 100
        # Success + failed = 70 completed
        assert stats.success_count + stats.failed_count == 70

    def test_daily_stats_with_retries(self):
        """Test DailyStats with retry tracking"""
        stats = DailyStats(
            total_tasks=50,
            success_count=40,
            failed_count=10,
            total_retries=25
        )

        assert stats.total_retries == 25
        # Average retries = 25/50 = 0.5
        avg_retries = stats.total_retries / stats.total_tasks
        assert avg_retries == 0.5

    def test_weekly_stats_seven_days(self):
        """Test WeeklyStats with full 7 days"""
        start = date(2025, 12, 1)
        daily_stats = []

        for i in range(7):
            daily = DailyStats(
                stat_date=start + timedelta(days=i),
                total_tasks=50,
                success_count=40,
                failed_count=10
            )
            daily_stats.append(daily)

        stats = WeeklyStats(
            start_date=start,
            end_date=start + timedelta(days=6),
            daily_stats=daily_stats
        )
        stats.aggregate_from_daily()

        assert len(stats.daily_stats) == 7
        assert stats.total_tasks == 350  # 50 * 7
        assert stats.avg_daily_tasks == 50.0

    def test_weekly_stats_product_distribution(self):
        """Test WeeklyStats product distribution"""
        stats = WeeklyStats(
            product_stats={
                "Product A": 100,
                "Product B": 50,
                "Product C": 25
            }
        )

        assert len(stats.product_stats) == 3
        assert stats.product_stats["Product A"] == 100
        assert stats.product_stats["Product B"] == 50
        assert stats.product_stats["Product C"] == 25

    def test_weekly_stats_failure_reasons(self):
        """Test WeeklyStats failure reasons tracking"""
        stats = WeeklyStats(
            failure_reasons={
                "Network timeout": 15,
                "WeChat not found": 10,
                "Permission denied": 5
            }
        )

        assert len(stats.failure_reasons) == 3
        assert stats.failure_reasons["Network timeout"] == 15
        assert stats.failure_reasons["WeChat not found"] == 10

    def test_task_summary_current_state(self):
        """Test TaskSummary current state tracking"""
        summary = TaskSummary(
            running_count=5,
            scheduled_count=20,
            paused_count=3
        )

        # Total active tasks
        active_tasks = summary.running_count + summary.scheduled_count + summary.paused_count
        assert active_tasks == 28

    def test_stats_zero_handling(self):
        """Test that all stats handle zero values correctly"""
        daily = DailyStats()
        assert daily.success_rate == 0.0
        assert daily.completion_rate == 0.0

        weekly = WeeklyStats()
        assert weekly.success_rate == 0.0
        assert weekly.avg_daily_tasks == 0.0

        summary = TaskSummary()
        assert summary.today_success_rate == 0.0
        assert summary.overall_success_rate == 0.0

    def test_stats_large_numbers(self):
        """Test stats with very large numbers"""
        stats = DailyStats(
            total_tasks=1000000,
            success_count=950000,
            failed_count=50000
        )

        # Should still calculate correctly
        assert stats.success_rate == 95.0
        assert stats.completion_rate == 100.0

    def test_stats_date_serialization(self):
        """Test that dates serialize correctly"""
        daily = DailyStats(stat_date=date(2025, 12, 5))
        daily_dict = daily.to_dict()
        assert daily_dict["stat_date"] == "2025-12-05"

        weekly = WeeklyStats(
            start_date=date(2025, 12, 1),
            end_date=date(2025, 12, 7)
        )
        weekly_dict = weekly.to_dict()
        assert weekly_dict["start_date"] == "2025-12-01"
        assert weekly_dict["end_date"] == "2025-12-07"
