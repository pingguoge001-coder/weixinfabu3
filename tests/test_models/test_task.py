"""Tests for Task model"""
import pytest
from datetime import datetime, timedelta
from models.task import Task
from models.enums import TaskStatus, Channel


class TestTaskCreation:
    """Test Task creation and default values"""

    def test_task_creation_defaults(self):
        """Test Task creation with default values"""
        task = Task()

        assert task.id is None
        assert task.content_code == ""
        assert task.product_name == ""
        assert task.channel == Channel.moment
        assert task.group_name is None
        assert task.status == TaskStatus.pending
        assert task.scheduled_time is None
        assert task.priority == 0
        assert task.retry_count == 0
        assert task.max_retry == 3
        assert task.executed_time is None
        assert task.error_message is None
        assert task.screenshot_path is None
        assert task.failure_reason is None
        assert task.pause_reason is None
        assert task.note is None
        assert isinstance(task.created_at, datetime)
        assert isinstance(task.updated_at, datetime)

    def test_task_creation_with_values(self, sample_task):
        """Test Task creation with provided values"""
        assert sample_task.content_code == "TEST001"
        assert sample_task.product_name == "Test Product"
        assert sample_task.channel == Channel.moment
        assert sample_task.status == TaskStatus.pending
        assert sample_task.priority == 5
        assert sample_task.scheduled_time is not None

    def test_task_creation_with_group_channel(self):
        """Test Task creation with group channel"""
        task = Task(
            content_code="TEST002",
            channel=Channel.group,
            group_name="Test Group"
        )

        assert task.channel == Channel.group
        assert task.group_name == "Test Group"


class TestTaskRetryMechanism:
    """Test Task retry mechanism"""

    def test_task_can_retry_default(self):
        """Test can_retry returns True when retry_count < max_retry"""
        task = Task(retry_count=0, max_retry=3)
        assert task.can_retry is True

    def test_task_can_retry_partial(self):
        """Test can_retry returns True when retry_count < max_retry"""
        task = Task(retry_count=2, max_retry=3)
        assert task.can_retry is True

    def test_task_cannot_retry_exceeded(self):
        """Test can_retry returns False when retry_count >= max_retry"""
        task = Task(retry_count=3, max_retry=3)
        assert task.can_retry is False

    def test_task_cannot_retry_over_exceeded(self):
        """Test can_retry returns False when retry_count > max_retry"""
        task = Task(retry_count=5, max_retry=3)
        assert task.can_retry is False

    def test_task_increment_retry(self):
        """Test increment_retry increases retry_count"""
        task = Task(retry_count=0)
        original_updated_at = task.updated_at

        task.increment_retry()

        assert task.retry_count == 1
        assert task.updated_at >= original_updated_at  # Use >= due to timing precision

    def test_task_increment_retry_multiple(self):
        """Test increment_retry works multiple times"""
        task = Task(retry_count=0)

        task.increment_retry()
        assert task.retry_count == 1

        task.increment_retry()
        assert task.retry_count == 2

        task.increment_retry()
        assert task.retry_count == 3


class TestTaskStatusMarking:
    """Test Task status marking methods"""

    def test_task_mark_success(self):
        """Test mark_success sets status and executed_time"""
        task = Task(status=TaskStatus.pending)
        before_mark = datetime.now()

        task.mark_success()

        assert task.status == TaskStatus.success
        assert task.executed_time is not None
        assert task.executed_time >= before_mark
        assert task.screenshot_path is None

    def test_task_mark_success_with_screenshot(self):
        """Test mark_success with screenshot path"""
        task = Task(status=TaskStatus.pending)
        screenshot_path = "/path/to/screenshot.png"

        task.mark_success(screenshot_path=screenshot_path)

        assert task.status == TaskStatus.success
        assert task.executed_time is not None
        assert task.screenshot_path == screenshot_path

    def test_task_mark_failed(self):
        """Test mark_failed sets status and error message"""
        task = Task(status=TaskStatus.running)
        error_msg = "WeChat timeout"

        task.mark_failed(error_message=error_msg)

        assert task.status == TaskStatus.failed
        assert task.error_message == error_msg
        assert task.executed_time is not None
        assert task.failure_reason is None

    def test_task_mark_failed_with_reason(self):
        """Test mark_failed with failure reason"""
        task = Task(status=TaskStatus.running)
        error_msg = "Connection error"
        failure_reason = "Network timeout"

        task.mark_failed(error_message=error_msg, failure_reason=failure_reason)

        assert task.status == TaskStatus.failed
        assert task.error_message == error_msg
        assert task.failure_reason == failure_reason
        assert task.executed_time is not None

    def test_task_mark_paused(self):
        """Test mark_paused sets status and pause reason"""
        task = Task(status=TaskStatus.running)
        pause_reason = "Manual pause by user"

        task.mark_paused(reason=pause_reason)

        assert task.status == TaskStatus.paused
        assert task.pause_reason == pause_reason

    def test_task_mark_cancelled(self):
        """Test mark_cancelled sets status"""
        task = Task(status=TaskStatus.pending)
        original_updated_at = task.updated_at

        task.mark_cancelled()

        assert task.status == TaskStatus.cancelled
        assert task.updated_at >= original_updated_at  # Use >= due to timing precision


class TestTaskSerialization:
    """Test Task serialization and deserialization"""

    def test_task_to_dict(self, sample_task):
        """Test to_dict serialization"""
        task_dict = sample_task.to_dict()

        assert isinstance(task_dict, dict)
        assert task_dict["content_code"] == "TEST001"
        assert task_dict["product_name"] == "Test Product"
        assert task_dict["channel"] == "moment"
        assert task_dict["status"] == "pending"
        assert task_dict["priority"] == 5
        assert task_dict["retry_count"] == 0
        assert task_dict["max_retry"] == 3

    def test_task_to_dict_with_datetime(self):
        """Test to_dict with datetime fields"""
        scheduled_time = datetime(2025, 12, 5, 10, 30, 0)
        task = Task(
            content_code="TEST001",
            scheduled_time=scheduled_time
        )

        task_dict = task.to_dict()

        assert task_dict["scheduled_time"] == scheduled_time.isoformat()
        assert task_dict["created_at"] is not None
        assert task_dict["updated_at"] is not None

    def test_task_to_dict_with_none_values(self):
        """Test to_dict with None values"""
        task = Task()
        task_dict = task.to_dict()

        assert task_dict["scheduled_time"] is None
        assert task_dict["executed_time"] is None
        assert task_dict["group_name"] is None
        assert task_dict["error_message"] is None

    def test_task_from_dict(self):
        """Test from_dict deserialization"""
        data = {
            "id": 1,
            "content_code": "TEST001",
            "product_name": "Test Product",
            "channel": "moment",
            "status": "pending",
            "priority": 5,
            "retry_count": 0,
            "max_retry": 3,
        }

        task = Task.from_dict(data)

        assert task.id == 1
        assert task.content_code == "TEST001"
        assert task.product_name == "Test Product"
        assert task.channel == Channel.moment
        assert task.status == TaskStatus.pending
        assert task.priority == 5

    def test_task_from_dict_with_datetime_strings(self):
        """Test from_dict with datetime strings"""
        scheduled_time = datetime(2025, 12, 5, 10, 30, 0)
        data = {
            "content_code": "TEST001",
            "scheduled_time": scheduled_time.isoformat(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        task = Task.from_dict(data)

        assert isinstance(task.scheduled_time, datetime)
        assert task.scheduled_time == scheduled_time
        assert isinstance(task.created_at, datetime)
        assert isinstance(task.updated_at, datetime)

    def test_task_from_dict_with_enum_objects(self):
        """Test from_dict with enum objects (not strings)"""
        data = {
            "content_code": "TEST001",
            "channel": Channel.group,
            "status": TaskStatus.success,
        }

        task = Task.from_dict(data)

        assert task.channel == Channel.group
        assert task.status == TaskStatus.success

    def test_task_round_trip_serialization(self, sample_task):
        """Test round-trip serialization (to_dict -> from_dict)"""
        task_dict = sample_task.to_dict()
        restored_task = Task.from_dict(task_dict)

        assert restored_task.content_code == sample_task.content_code
        assert restored_task.product_name == sample_task.product_name
        assert restored_task.channel == sample_task.channel
        assert restored_task.status == sample_task.status
        assert restored_task.priority == sample_task.priority


class TestTaskProperties:
    """Test Task properties"""

    def test_task_scheduled_date_property(self):
        """Test scheduled_date property returns correct date string"""
        scheduled_time = datetime(2025, 12, 5, 10, 30, 0)
        task = Task(scheduled_time=scheduled_time)

        assert task.scheduled_date == "2025-12-05"

    def test_task_scheduled_date_none(self):
        """Test scheduled_date returns None when scheduled_time is None"""
        task = Task(scheduled_time=None)

        assert task.scheduled_date is None

    def test_task_scheduled_date_different_times(self):
        """Test scheduled_date returns same date for different times"""
        task1 = Task(scheduled_time=datetime(2025, 12, 5, 8, 0, 0))
        task2 = Task(scheduled_time=datetime(2025, 12, 5, 23, 59, 59))

        assert task1.scheduled_date == task2.scheduled_date
        assert task1.scheduled_date == "2025-12-05"


class TestTaskEdgeCases:
    """Test Task edge cases and boundary conditions"""

    def test_task_with_zero_max_retry(self):
        """Test task with max_retry set to 0"""
        task = Task(retry_count=0, max_retry=0)
        assert task.can_retry is False

    def test_task_with_negative_priority(self):
        """Test task with negative priority"""
        task = Task(priority=-10)
        assert task.priority == -10

    def test_task_with_very_high_priority(self):
        """Test task with very high priority"""
        task = Task(priority=999999)
        assert task.priority == 999999

    def test_task_multiple_status_changes(self):
        """Test multiple status changes in sequence"""
        task = Task(status=TaskStatus.pending)

        # pending -> running
        task.status = TaskStatus.running
        assert task.status == TaskStatus.running

        # running -> failed
        task.mark_failed("First failure")
        assert task.status == TaskStatus.failed
        assert task.error_message == "First failure"

        # failed -> pending (retry)
        task.status = TaskStatus.pending
        task.increment_retry()
        assert task.status == TaskStatus.pending
        assert task.retry_count == 1

        # pending -> success
        task.mark_success()
        assert task.status == TaskStatus.success

    def test_task_with_long_strings(self):
        """Test task with very long string values"""
        long_text = "x" * 10000
        task = Task(
            content_code=long_text,
            product_name=long_text,
            error_message=long_text,
            note=long_text,
        )

        assert task.content_code == long_text
        assert task.product_name == long_text
        assert task.error_message == long_text
        assert task.note == long_text

    def test_task_with_unicode_characters(self):
        """Test task with unicode characters"""
        task = Task(
            content_code="测试001",
            product_name="产品名称",
            note="这是备注信息 🎉",
        )

        assert task.content_code == "测试001"
        assert task.product_name == "产品名称"
        assert task.note == "这是备注信息 🎉"

    def test_task_timestamps_update(self):
        """Test that timestamps update correctly"""
        task = Task()
        original_updated_at = task.updated_at

        # Increment retry updates timestamp
        task.increment_retry()
        assert task.updated_at >= original_updated_at  # Use >= due to timing precision

        # Mark success updates timestamp
        updated_at_after_retry = task.updated_at
        task.mark_success()
        assert task.updated_at >= updated_at_after_retry  # Use >= due to timing precision
