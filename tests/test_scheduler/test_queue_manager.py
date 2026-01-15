"""Tests for QueueManager (scheduler/queue_manager.py)"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from models.task import Task
from models.enums import TaskStatus, Channel
from scheduler.queue_manager import QueueManager, PriorityTask


# ==================== Fixtures ====================

@pytest.fixture
def mock_db():
    """Mock database fixture"""
    db = Mock()
    db.update_task = Mock(return_value=True)
    db.get_pending_tasks = Mock(return_value=[])
    return db


@pytest.fixture
def queue_manager(mock_db):
    """QueueManager fixture"""
    return QueueManager(db=mock_db, config={})


@pytest.fixture
def sample_task():
    """Sample task for testing"""
    return Task(
        id=1,
        content_code="TEST001",
        product_name="Test Product",
        channel=Channel.moment,
        status=TaskStatus.pending,
        scheduled_time=datetime.now() + timedelta(hours=1),
        priority=5,
    )


@pytest.fixture
def high_priority_task():
    """High priority task for testing"""
    return Task(
        id=2,
        content_code="TEST002",
        product_name="High Priority",
        channel=Channel.moment,
        status=TaskStatus.pending,
        scheduled_time=datetime.now() + timedelta(hours=1),
        priority=1,  # Higher priority (lower number)
    )


@pytest.fixture
def low_priority_task():
    """Low priority task for testing"""
    return Task(
        id=3,
        content_code="TEST003",
        product_name="Low Priority",
        channel=Channel.moment,
        status=TaskStatus.pending,
        scheduled_time=datetime.now() + timedelta(hours=1),
        priority=9,  # Lower priority (higher number)
    )


# ==================== Queue Operations Tests ====================

class TestQueueOperations:
    """Test queue operations"""

    def test_add_task(self, queue_manager, sample_task):
        """Test adding a task to the queue"""
        result = queue_manager.add_task(sample_task)

        assert result is True
        assert queue_manager.get_queue_size() == 1

    def test_add_task_duplicate(self, queue_manager, sample_task):
        """Test adding the same task twice returns False"""
        queue_manager.add_task(sample_task)
        result = queue_manager.add_task(sample_task)

        assert result is False
        assert queue_manager.get_queue_size() == 1

    def test_add_task_invalid_status(self, queue_manager):
        """Test adding task with non-executable status fails"""
        task = Task(
            id=1,
            content_code="TEST001",
            status=TaskStatus.success,  # Not executable
        )

        result = queue_manager.add_task(task)

        assert result is False
        assert queue_manager.get_queue_size() == 0

    def test_add_tasks_batch(self, queue_manager):
        """Test batch adding tasks"""
        tasks = [
            Task(id=i, content_code=f"TEST{i:03d}", status=TaskStatus.pending)
            for i in range(1, 6)
        ]

        count = queue_manager.add_tasks(tasks)

        assert count == 5
        assert queue_manager.get_queue_size() == 5

    def test_get_next_task_empty(self, queue_manager):
        """Test getting next task from empty queue returns None"""
        task = queue_manager.get_next_task()

        assert task is None

    def test_peek_next_task(self, queue_manager, sample_task):
        """Test peeking next task without removing it"""
        queue_manager.add_task(sample_task)

        peeked = queue_manager.peek_next_task()

        assert peeked is not None
        assert peeked.id == sample_task.id
        assert queue_manager.get_queue_size() == 1  # Task not removed

    def test_remove_task(self, queue_manager, sample_task):
        """Test removing a task from the queue"""
        queue_manager.add_task(sample_task)
        assert queue_manager.get_queue_size() == 1

        result = queue_manager.remove_task(sample_task.id)

        assert result is True
        assert queue_manager.get_queue_size() == 0

    def test_remove_task_not_found(self, queue_manager):
        """Test removing non-existent task returns False"""
        result = queue_manager.remove_task(999)

        assert result is False

    def test_clear_queue(self, queue_manager):
        """Test clearing the queue"""
        tasks = [
            Task(id=i, content_code=f"TEST{i}", status=TaskStatus.pending)
            for i in range(1, 4)
        ]
        queue_manager.add_tasks(tasks)
        assert queue_manager.get_queue_size() == 3

        queue_manager.clear_queue()

        assert queue_manager.get_queue_size() == 0


# ==================== Priority Tests ====================

class TestPriorityOrdering:
    """Test priority ordering in queue"""

    def test_priority_ordering(self, queue_manager, high_priority_task, low_priority_task, sample_task):
        """Test that higher priority tasks come out first"""
        # Add in random order
        queue_manager.add_task(low_priority_task)
        queue_manager.add_task(sample_task)
        queue_manager.add_task(high_priority_task)

        # Should get high priority first (priority=1)
        peeked = queue_manager.peek_next_task()
        assert peeked.id == high_priority_task.id
        assert peeked.priority == 1

    def test_same_priority_time_ordering(self, queue_manager):
        """Test tasks with same priority are ordered by scheduled time"""
        now = datetime.now()

        task1 = Task(
            id=1,
            content_code="TEST001",
            status=TaskStatus.pending,
            priority=5,
            scheduled_time=now + timedelta(hours=2),
        )
        task2 = Task(
            id=2,
            content_code="TEST002",
            status=TaskStatus.pending,
            priority=5,
            scheduled_time=now + timedelta(hours=1),  # Earlier
        )

        queue_manager.add_task(task1)
        queue_manager.add_task(task2)

        # Task 2 should come first (earlier scheduled time)
        peeked = queue_manager.peek_next_task()
        assert peeked.id == task2.id


# ==================== Execution Lock Tests ====================

class TestExecutionLock:
    """Test execution lock functionality"""

    def test_acquire_execution_lock(self, queue_manager, mock_db, sample_task):
        """Test acquiring execution lock"""
        result = queue_manager.acquire_execution_lock(sample_task, timeout=1.0)

        assert result is True
        assert queue_manager.is_executing() is True
        assert queue_manager.get_current_task() == sample_task
        mock_db.update_task.assert_called_once()

    def test_release_execution_lock(self, queue_manager, sample_task):
        """Test releasing execution lock"""
        queue_manager.acquire_execution_lock(sample_task, timeout=1.0)
        assert queue_manager.is_executing() is True

        queue_manager.release_execution_lock()

        assert queue_manager.is_executing() is False
        assert queue_manager.get_current_task() is None

    def test_is_executing_initial(self, queue_manager):
        """Test is_executing returns False initially"""
        assert queue_manager.is_executing() is False

    def test_get_current_task_none(self, queue_manager):
        """Test get_current_task returns None when not executing"""
        assert queue_manager.get_current_task() is None


# ==================== Task Status Marking Tests ====================

class TestTaskStatusMarking:
    """Test task status marking"""

    def test_mark_task_success(self, queue_manager, mock_db, sample_task):
        """Test marking task as successful"""
        queue_manager.mark_task_success(sample_task)

        assert sample_task.status == TaskStatus.success
        mock_db.update_task.assert_called_once_with(sample_task)

    def test_mark_task_success_with_callback(self, queue_manager, mock_db, sample_task):
        """Test success callback is called"""
        callback = Mock()
        queue_manager.set_callbacks(on_complete=callback)

        queue_manager.mark_task_success(sample_task)

        callback.assert_called_once_with(sample_task)

    def test_mark_task_failed(self, queue_manager, mock_db, sample_task):
        """Test marking task as failed"""
        error_msg = "Test error"

        queue_manager.mark_task_failed(sample_task, error_msg)

        assert sample_task.status == TaskStatus.failed
        assert sample_task.error_message == error_msg
        mock_db.update_task.assert_called_once_with(sample_task)

    def test_mark_task_failed_with_callback(self, queue_manager, mock_db, sample_task):
        """Test failure callback is called"""
        callback = Mock()
        queue_manager.set_callbacks(on_failed=callback)
        error_msg = "Test error"

        queue_manager.mark_task_failed(sample_task, error_msg)

        callback.assert_called_once_with(sample_task, error_msg)

    def test_mark_task_skipped(self, queue_manager, mock_db, sample_task):
        """Test marking task as skipped"""
        reason = "Test reason"

        queue_manager.mark_task_skipped(sample_task, reason)

        assert sample_task.status == TaskStatus.skipped
        mock_db.update_task.assert_called_once_with(sample_task)


# ==================== Retry Tests ====================

class TestRetryMechanism:
    """Test task retry mechanism"""

    def test_retry_task(self, queue_manager, mock_db, sample_task):
        """Test retrying a task"""
        sample_task.retry_count = 0
        sample_task.max_retry = 3

        result = queue_manager.retry_task(sample_task)

        assert result is True
        assert sample_task.retry_count == 1
        assert sample_task.status == TaskStatus.pending
        assert queue_manager.get_queue_size() == 1

    def test_retry_task_max_reached(self, queue_manager, sample_task):
        """Test retry fails when max retries reached"""
        sample_task.retry_count = 3
        sample_task.max_retry = 3

        result = queue_manager.retry_task(sample_task)

        assert result is False
        assert queue_manager.get_queue_size() == 0


# ==================== Queue Control Tests ====================

class TestQueueControl:
    """Test queue pause/resume functionality"""

    def test_pause_queue(self, queue_manager):
        """Test pausing the queue"""
        queue_manager.pause_queue()

        assert queue_manager.is_paused() is True

    def test_resume_queue(self, queue_manager):
        """Test resuming the queue"""
        queue_manager.pause_queue()
        assert queue_manager.is_paused() is True

        queue_manager.resume_queue()

        assert queue_manager.is_paused() is False

    def test_get_next_task_when_paused(self, queue_manager, sample_task):
        """Test get_next_task returns None when paused"""
        queue_manager.add_task(sample_task)
        queue_manager.pause_queue()

        task = queue_manager.get_next_task()

        assert task is None

    def test_initial_not_paused(self, queue_manager):
        """Test queue is not paused initially"""
        assert queue_manager.is_paused() is False


# ==================== Status Query Tests ====================

class TestStatusQuery:
    """Test queue status queries"""

    def test_get_queue_size(self, queue_manager):
        """Test getting queue size"""
        assert queue_manager.get_queue_size() == 0

        tasks = [
            Task(id=i, content_code=f"TEST{i}", status=TaskStatus.pending)
            for i in range(1, 4)
        ]
        queue_manager.add_tasks(tasks)

        assert queue_manager.get_queue_size() == 3

    def test_get_queue_status(self, queue_manager):
        """Test getting complete queue status"""
        status = queue_manager.get_queue_status()

        assert "queue_size" in status
        assert "is_paused" in status
        assert "is_executing" in status
        assert "current_task_id" in status
        assert "priority_distribution" in status

    def test_get_queue_status_with_tasks(self, queue_manager, sample_task, high_priority_task):
        """Test queue status with tasks"""
        queue_manager.add_task(sample_task)
        queue_manager.add_task(high_priority_task)

        status = queue_manager.get_queue_status()

        assert status["queue_size"] == 2
        assert status["is_paused"] is False
        assert status["is_executing"] is False
        assert len(status["priority_distribution"]) == 2

    def test_load_pending_tasks(self, queue_manager, mock_db):
        """Test loading pending tasks from database"""
        pending_tasks = [
            Task(id=i, content_code=f"TEST{i}", status=TaskStatus.pending)
            for i in range(1, 4)
        ]
        mock_db.get_pending_tasks.return_value = pending_tasks

        count = queue_manager.load_pending_tasks()

        assert count == 3
        assert queue_manager.get_queue_size() == 3
        mock_db.get_pending_tasks.assert_called_once()


# ==================== PriorityTask Tests ====================

class TestPriorityTask:
    """Test PriorityTask dataclass"""

    def test_priority_task_creation(self, sample_task):
        """Test creating a PriorityTask"""
        pt = PriorityTask(
            priority=sample_task.priority,
            scheduled_time=sample_task.scheduled_time,
            created_at=sample_task.created_at,
            task=sample_task
        )

        assert pt.priority == sample_task.priority
        assert pt.task == sample_task

    def test_priority_task_ordering(self):
        """Test PriorityTask comparison"""
        now = datetime.now()

        pt1 = PriorityTask(
            priority=1,
            scheduled_time=now,
            created_at=now,
            task=Task(id=1, content_code="TEST1")
        )
        pt2 = PriorityTask(
            priority=5,
            scheduled_time=now,
            created_at=now,
            task=Task(id=2, content_code="TEST2")
        )

        # Lower priority number should be "less than" (come first in min-heap)
        assert pt1 < pt2
