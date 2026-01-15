"""Test cases for Database class (data/database.py)"""

import pytest
from datetime import datetime, date, timedelta
from pathlib import Path
import threading
import time

from models.task import Task
from models.content import Content
from models.enums import TaskStatus, Channel


# ==================== Task CRUD Tests ====================

def test_create_task(temp_db, sample_task):
    """Test creating a task and returning its ID"""
    task_id = temp_db.create_task(sample_task)

    assert task_id is not None
    assert task_id > 0

    # Verify task was created
    retrieved_task = temp_db.get_task(task_id)
    assert retrieved_task is not None
    assert retrieved_task.content_code == sample_task.content_code


def test_get_task(temp_db, sample_task):
    """Test getting a single task"""
    task_id = temp_db.create_task(sample_task)

    task = temp_db.get_task(task_id)

    assert task is not None
    assert task.id == task_id
    assert task.content_code == sample_task.content_code
    assert task.product_name == sample_task.product_name
    assert task.channel == sample_task.channel
    assert task.status == sample_task.status


def test_get_task_not_found(temp_db):
    """Test getting a non-existent task returns None"""
    task = temp_db.get_task(99999)

    assert task is None


def test_update_task(temp_db, sample_task):
    """Test updating a task"""
    task_id = temp_db.create_task(sample_task)
    task = temp_db.get_task(task_id)

    # Update task
    task.status = TaskStatus.running
    task.product_name = "Updated Product"
    task.priority = 10

    result = temp_db.update_task(task)

    assert result is True

    # Verify update
    updated_task = temp_db.get_task(task_id)
    assert updated_task.status == TaskStatus.running
    assert updated_task.product_name == "Updated Product"
    assert updated_task.priority == 10


def test_delete_task(temp_db, sample_task):
    """Test deleting a task"""
    task_id = temp_db.create_task(sample_task)

    result = temp_db.delete_task(task_id)

    assert result is True

    # Verify deletion
    task = temp_db.get_task(task_id)
    assert task is None


def test_list_tasks(temp_db):
    """Test querying task list"""
    # Create multiple tasks
    for i in range(5):
        task = Task(
            content_code=f"TEST{i:03d}",
            product_name=f"Product {i}",
            channel=Channel.moment,
            status=TaskStatus.pending,
            scheduled_time=datetime.now() + timedelta(hours=i),
            priority=i,
        )
        temp_db.create_task(task)

    tasks = temp_db.list_tasks(limit=10)

    assert len(tasks) == 5
    # Should be ordered by priority DESC, scheduled_time ASC
    assert tasks[0].priority >= tasks[-1].priority


def test_list_tasks_with_filters(temp_db):
    """Test filtering tasks by status, channel, and date"""
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Create tasks with different statuses and channels
    task1 = Task(
        content_code="TEST001",
        channel=Channel.moment,
        status=TaskStatus.pending,
        scheduled_time=datetime.combine(today, datetime.min.time()),
    )
    task2 = Task(
        content_code="TEST002",
        channel=Channel.group,
        status=TaskStatus.success,
        scheduled_time=datetime.combine(today, datetime.min.time()),
    )
    task3 = Task(
        content_code="TEST003",
        channel=Channel.moment,
        status=TaskStatus.pending,
        scheduled_time=datetime.combine(tomorrow, datetime.min.time()),
    )

    temp_db.create_task(task1)
    temp_db.create_task(task2)
    temp_db.create_task(task3)

    # Filter by status
    pending_tasks = temp_db.list_tasks(status=TaskStatus.pending)
    assert len(pending_tasks) == 2

    # Filter by channel
    moment_tasks = temp_db.list_tasks(channel=Channel.moment)
    assert len(moment_tasks) == 2

    # Filter by date
    today_tasks = temp_db.list_tasks(scheduled_date=today)
    assert len(today_tasks) == 2

    # Combine filters
    today_pending = temp_db.list_tasks(status=TaskStatus.pending, scheduled_date=today)
    assert len(today_pending) == 1
    assert today_pending[0].content_code == "TEST001"


def test_get_pending_tasks(temp_db):
    """Test getting pending tasks"""
    now = datetime.now()

    # Create tasks with different times
    past_task = Task(
        content_code="PAST",
        status=TaskStatus.pending,
        scheduled_time=now - timedelta(hours=1),
    )
    current_task = Task(
        content_code="CURRENT",
        status=TaskStatus.scheduled,
        scheduled_time=now,
    )
    future_task = Task(
        content_code="FUTURE",
        status=TaskStatus.pending,
        scheduled_time=now + timedelta(hours=1),
    )
    completed_task = Task(
        content_code="COMPLETED",
        status=TaskStatus.success,
        scheduled_time=now - timedelta(hours=2),
    )

    temp_db.create_task(past_task)
    temp_db.create_task(current_task)
    temp_db.create_task(future_task)
    temp_db.create_task(completed_task)

    # Get all pending tasks
    all_pending = temp_db.get_pending_tasks()
    assert len(all_pending) == 3

    # Get pending tasks before specific time
    pending_before_now = temp_db.get_pending_tasks(before_time=now)
    assert len(pending_before_now) == 2


def test_update_task_status_success(temp_db, sample_task):
    """Test updating task to success status"""
    task_id = temp_db.create_task(sample_task)
    screenshot_path = "screenshots/success.png"

    result = temp_db.update_task_status(
        task_id,
        TaskStatus.success,
        screenshot_path=screenshot_path
    )

    assert result is True

    # Verify update
    task = temp_db.get_task(task_id)
    assert task.status == TaskStatus.success
    assert task.screenshot_path == screenshot_path
    assert task.executed_time is not None


def test_update_task_status_failed(temp_db, sample_task):
    """Test updating task to failed status"""
    task_id = temp_db.create_task(sample_task)
    error_msg = "Test error message"

    result = temp_db.update_task_status(
        task_id,
        TaskStatus.failed,
        error_message=error_msg
    )

    assert result is True

    # Verify update
    task = temp_db.get_task(task_id)
    assert task.status == TaskStatus.failed
    assert task.error_message == error_msg
    assert task.executed_time is not None


def test_increment_retry(temp_db, sample_task):
    """Test incrementing retry count"""
    task_id = temp_db.create_task(sample_task)

    # Increment retry count
    result = temp_db.increment_retry(task_id)
    assert result is True

    # Verify increment
    task = temp_db.get_task(task_id)
    assert task.retry_count == 1

    # Increment again
    temp_db.increment_retry(task_id)
    task = temp_db.get_task(task_id)
    assert task.retry_count == 2


# ==================== Idempotent Key Tests ====================

def test_check_idempotent_key_not_exists(temp_db):
    """Test checking a non-existent idempotent key returns False"""
    exists = temp_db.check_idempotent_key("non_existent_key")

    assert exists is False


def test_create_idempotent_key(temp_db, sample_task):
    """Test creating an idempotent key"""
    task_id = temp_db.create_task(sample_task)
    key = temp_db.generate_idempotent_key(sample_task)

    result = temp_db.create_idempotent_key(key, task_id)

    assert result is True


def test_check_idempotent_key_exists(temp_db, sample_task):
    """Test checking an existing idempotent key returns True"""
    task_id = temp_db.create_task(sample_task)
    key = temp_db.generate_idempotent_key(sample_task)

    temp_db.create_idempotent_key(key, task_id)

    exists = temp_db.check_idempotent_key(key)

    assert exists is True


def test_create_duplicate_key(temp_db, sample_task):
    """Test creating duplicate idempotent key returns False"""
    task_id = temp_db.create_task(sample_task)
    key = temp_db.generate_idempotent_key(sample_task)

    # Create key first time
    result1 = temp_db.create_idempotent_key(key, task_id)
    assert result1 is True

    # Try to create same key again
    result2 = temp_db.create_idempotent_key(key, task_id)
    assert result2 is False


def test_cleanup_expired_keys(temp_db):
    """Test cleaning up expired idempotent keys"""
    # Create expired key
    expired_key = "expired_key"
    with temp_db.cursor() as cur:
        past_time = (datetime.now() - timedelta(hours=25)).isoformat()
        cur.execute("""
            INSERT INTO idempotent_keys (idempotent_key, expires_at)
            VALUES (?, ?)
        """, (expired_key, past_time))

    # Create non-expired key
    valid_key = "valid_key"
    future_time = (datetime.now() + timedelta(hours=1)).isoformat()
    with temp_db.cursor() as cur:
        cur.execute("""
            INSERT INTO idempotent_keys (idempotent_key, expires_at)
            VALUES (?, ?)
        """, (valid_key, future_time))

    # Cleanup
    count = temp_db.cleanup_expired_keys()

    assert count == 1
    assert not temp_db.check_idempotent_key(expired_key)
    assert temp_db.check_idempotent_key(valid_key)


def test_generate_idempotent_key(temp_db):
    """Test generating idempotent key with correct format"""
    task = Task(
        content_code="TEST001",
        channel=Channel.moment,
        group_name="TestGroup",
        scheduled_time=datetime(2025, 1, 15, 10, 30),
    )

    key = temp_db.generate_idempotent_key(task)

    assert key is not None
    assert isinstance(key, str)
    assert len(key) > 0

    # Same task should generate same key
    key2 = temp_db.generate_idempotent_key(task)
    assert key == key2

    # Different task should generate different key
    task.content_code = "TEST002"
    key3 = temp_db.generate_idempotent_key(task)
    assert key != key3


# ==================== Content CRUD Tests ====================

def test_create_content(temp_db, sample_content):
    """Test creating content"""
    result = temp_db.create_content(sample_content)

    assert result is True


def test_get_content(temp_db, sample_content):
    """Test getting content"""
    temp_db.create_content(sample_content)

    content = temp_db.get_content(sample_content.content_code)

    assert content is not None
    assert content.content_code == sample_content.content_code
    assert content.text == sample_content.text
    assert content.image_paths == sample_content.image_paths


def test_update_content(temp_db, sample_content):
    """Test updating content"""
    temp_db.create_content(sample_content)

    # Update content
    sample_content.text = "Updated text"
    sample_content.image_paths = ["new/path.jpg"]

    result = temp_db.update_content(sample_content)

    assert result is True

    # Verify update
    content = temp_db.get_content(sample_content.content_code)
    assert content.text == "Updated text"
    assert content.image_paths == ["new/path.jpg"]


def test_delete_content(temp_db, sample_content):
    """Test deleting content"""
    temp_db.create_content(sample_content)

    result = temp_db.delete_content(sample_content.content_code)

    assert result is True

    # Verify deletion
    content = temp_db.get_content(sample_content.content_code)
    assert content is None


def test_create_duplicate_content(temp_db, sample_content):
    """Test creating duplicate content returns False"""
    result1 = temp_db.create_content(sample_content)
    assert result1 is True

    result2 = temp_db.create_content(sample_content)
    assert result2 is False


# ==================== Statistics Tests ====================

def test_get_daily_stats(temp_db):
    """Test getting daily statistics"""
    today = date.today()
    today_time = datetime.combine(today, datetime.min.time())

    # Create tasks for today with different statuses
    for i in range(10):
        status = [
            TaskStatus.success, TaskStatus.success, TaskStatus.success,
            TaskStatus.failed, TaskStatus.failed,
            TaskStatus.pending, TaskStatus.pending,
            TaskStatus.skipped, TaskStatus.cancelled, TaskStatus.paused
        ][i]

        task = Task(
            content_code=f"TEST{i:03d}",
            channel=Channel.moment if i < 5 else Channel.group,
            status=status,
            scheduled_time=today_time + timedelta(hours=i),
        )
        temp_db.create_task(task)

    stats = temp_db.get_daily_stats(today)

    assert stats.total_tasks == 10
    assert stats.success_count == 3
    assert stats.failed_count == 2
    assert stats.pending_count == 2
    assert stats.skipped_count == 1
    assert stats.cancelled_count == 1
    assert stats.paused_count == 1
    assert stats.moment_count == 5
    assert stats.group_count == 5


def test_get_weekly_stats(temp_db):
    """Test getting weekly statistics"""
    start_date = date.today() - timedelta(days=3)

    # Create tasks across multiple days
    for day_offset in range(7):
        day = start_date + timedelta(days=day_offset)
        day_time = datetime.combine(day, datetime.min.time())

        for i in range(3):
            task = Task(
                content_code=f"DAY{day_offset}_{i}",
                status=TaskStatus.success if i < 2 else TaskStatus.failed,
                scheduled_time=day_time + timedelta(hours=i),
            )
            temp_db.create_task(task)

    stats = temp_db.get_weekly_stats(start_date)

    assert stats.total_tasks == 21
    assert stats.success_count == 14
    assert stats.failed_count == 7
    assert len(stats.daily_stats) == 7


def test_get_task_summary(temp_db):
    """Test getting task summary"""
    today = date.today()
    today_time = datetime.combine(today, datetime.min.time())

    # Create today's tasks
    for i in range(5):
        status = [TaskStatus.success, TaskStatus.success, TaskStatus.failed, TaskStatus.pending, TaskStatus.running][i]
        task = Task(
            content_code=f"TODAY{i}",
            status=status,
            scheduled_time=today_time + timedelta(hours=i),
        )
        temp_db.create_task(task)

    # Create historical tasks
    yesterday = today - timedelta(days=1)
    yesterday_time = datetime.combine(yesterday, datetime.min.time())
    for i in range(3):
        task = Task(
            content_code=f"HIST{i}",
            status=TaskStatus.success,
            scheduled_time=yesterday_time + timedelta(hours=i),
        )
        temp_db.create_task(task)

    summary = temp_db.get_task_summary()

    assert summary.today_total == 5
    assert summary.today_success == 2
    assert summary.today_failed == 1
    assert summary.today_pending == 1
    assert summary.total_tasks == 8
    assert summary.total_success == 5
    assert summary.running_count == 1


# ==================== Transaction and Concurrency Tests ====================

def test_transaction_rollback(temp_db, sample_task):
    """Test that transactions rollback on exception"""
    try:
        with temp_db.cursor() as cur:
            # Create a task
            cur.execute("""
                INSERT INTO tasks (content_code, channel, status)
                VALUES (?, ?, ?)
            """, (sample_task.content_code, sample_task.channel.value, sample_task.status.value))

            # Force an error
            raise Exception("Test error")
    except:
        pass

    # Verify task was not created
    tasks = temp_db.list_tasks()
    assert len(tasks) == 0


def test_concurrent_access(temp_db):
    """Test concurrent database access"""
    errors = []

    def create_tasks(start_idx):
        try:
            for i in range(start_idx, start_idx + 10):
                task = Task(
                    content_code=f"CONCURRENT{i:03d}",
                    status=TaskStatus.pending,
                )
                temp_db.create_task(task)
        except Exception as e:
            errors.append(e)

    # Create multiple threads
    threads = []
    for i in range(5):
        thread = threading.Thread(target=create_tasks, args=(i * 10,))
        threads.append(thread)
        thread.start()

    # Wait for all threads
    for thread in threads:
        thread.join()

    # Verify no errors
    assert len(errors) == 0

    # Verify all tasks were created
    tasks = temp_db.list_tasks(limit=100)
    assert len(tasks) == 50
