"""Integration tests for database workflows"""

import pytest
from datetime import datetime, date, timedelta

from models.task import Task
from models.content import Content
from models.enums import TaskStatus, Channel


@pytest.mark.integration
class TestDatabaseWorkflow:
    """Test complete database workflows"""

    def test_task_lifecycle(self, temp_db):
        """Test complete task lifecycle: create -> schedule -> run -> complete"""
        # 1. Create a pending task
        task = Task(
            content_code="LIFECYCLE001",
            product_name="Lifecycle Test",
            channel=Channel.moment,
            status=TaskStatus.pending,
            scheduled_time=datetime.now() + timedelta(hours=1),
        )
        task_id = temp_db.create_task(task)
        assert task_id > 0

        # 2. Verify task is pending
        created_task = temp_db.get_task(task_id)
        assert created_task.status == TaskStatus.pending

        # 3. Update to scheduled
        temp_db.update_task_status(task_id, TaskStatus.scheduled)
        scheduled_task = temp_db.get_task(task_id)
        assert scheduled_task.status == TaskStatus.scheduled

        # 4. Update to running
        temp_db.update_task_status(task_id, TaskStatus.running)
        running_task = temp_db.get_task(task_id)
        assert running_task.status == TaskStatus.running

        # 5. Complete successfully
        screenshot = "screenshots/success.png"
        temp_db.update_task_status(task_id, TaskStatus.success, screenshot_path=screenshot)

        completed_task = temp_db.get_task(task_id)
        assert completed_task.status == TaskStatus.success
        assert completed_task.screenshot_path == screenshot
        assert completed_task.executed_time is not None

    def test_task_failure_flow(self, temp_db):
        """Test task failure workflow"""
        # Create and run task
        task = Task(
            content_code="FAIL001",
            status=TaskStatus.pending,
        )
        task_id = temp_db.create_task(task)

        # Mark as failed
        error_msg = "WeChat connection timeout"
        temp_db.update_task_status(task_id, TaskStatus.failed, error_message=error_msg)

        failed_task = temp_db.get_task(task_id)
        assert failed_task.status == TaskStatus.failed
        assert failed_task.error_message == error_msg

    def test_content_to_task_flow(self, temp_db):
        """Test creating content and associated tasks"""
        # 1. Create content
        content = Content(
            content_code="CONTENT001",
            text="Test marketing content",
            image_paths=["images/1.jpg", "images/2.jpg"],
            channel=Channel.moment,
        )
        temp_db.create_content(content)

        # 2. Create tasks for this content
        for i in range(3):
            task = Task(
                content_code="CONTENT001",
                product_name=f"Product {i}",
                channel=Channel.moment,
                status=TaskStatus.pending,
                scheduled_time=datetime.now() + timedelta(hours=i+1),
            )
            temp_db.create_task(task)

        # 3. Verify content retrieval
        retrieved_content = temp_db.get_content("CONTENT001")
        assert retrieved_content is not None
        assert retrieved_content.text == "Test marketing content"
        assert len(retrieved_content.image_paths) == 2

        # 4. Verify tasks
        tasks = temp_db.list_tasks()
        assert len(tasks) == 3
        for t in tasks:
            assert t.content_code == "CONTENT001"

    def test_idempotent_execution(self, temp_db):
        """Test idempotent key prevents duplicate execution"""
        # Create task
        task = Task(
            content_code="IDEMPOTENT001",
            channel=Channel.moment,
            scheduled_time=datetime.now(),
        )
        task_id = temp_db.create_task(task)
        task.id = task_id

        # Generate and create idempotent key
        key = temp_db.generate_idempotent_key(task)
        result1 = temp_db.create_idempotent_key(key, task_id)
        assert result1 is True

        # Try to create same key again
        result2 = temp_db.create_idempotent_key(key, task_id)
        assert result2 is False

        # Verify key exists
        exists = temp_db.check_idempotent_key(key)
        assert exists is True

    def test_batch_import_and_stats(self, temp_db):
        """Test batch task import and statistics"""
        today = date.today()
        today_time = datetime.combine(today, datetime.min.time())

        # Batch create tasks with various statuses
        status_distribution = [
            (TaskStatus.success, 40),
            (TaskStatus.failed, 10),
            (TaskStatus.pending, 30),
            (TaskStatus.skipped, 10),
            (TaskStatus.cancelled, 10),
        ]

        for status, count in status_distribution:
            for i in range(count):
                task = Task(
                    content_code=f"{status.value}_{i:03d}",
                    channel=Channel.moment if i % 2 == 0 else Channel.group,
                    status=status,
                    scheduled_time=today_time + timedelta(hours=i % 12),
                )
                temp_db.create_task(task)

        # Verify daily stats
        stats = temp_db.get_daily_stats(today)
        assert stats.total_tasks == 100
        assert stats.success_count == 40
        assert stats.failed_count == 10
        assert stats.pending_count == 30
        assert stats.skipped_count == 10
        assert stats.cancelled_count == 10
        assert stats.success_rate == 80.0  # 40/(40+10)*100

        # Verify task summary
        summary = temp_db.get_task_summary()
        assert summary.today_total == 100
        assert summary.today_success == 40
        assert summary.today_failed == 10

    def test_retry_workflow(self, temp_db):
        """Test task retry workflow with database updates"""
        # Create task
        task = Task(
            content_code="RETRY001",
            status=TaskStatus.pending,
            retry_count=0,
            max_retry=3,
        )
        task_id = temp_db.create_task(task)

        # Simulate failure and retry
        for retry in range(3):
            temp_db.update_task_status(task_id, TaskStatus.failed, error_message=f"Attempt {retry+1}")
            temp_db.increment_retry(task_id)

            retried_task = temp_db.get_task(task_id)
            assert retried_task.retry_count == retry + 1

        # Final task state
        final_task = temp_db.get_task(task_id)
        assert final_task.retry_count == 3
        assert final_task.status == TaskStatus.failed

    def test_multi_day_stats(self, temp_db):
        """Test statistics across multiple days"""
        start_date = date.today() - timedelta(days=6)

        # Create tasks across 7 days
        for day_offset in range(7):
            day = start_date + timedelta(days=day_offset)
            day_time = datetime.combine(day, datetime.min.time())

            # Create 10 tasks per day: 7 success, 2 failed, 1 pending
            for i in range(10):
                status = TaskStatus.success if i < 7 else (TaskStatus.failed if i < 9 else TaskStatus.pending)
                task = Task(
                    content_code=f"DAY{day_offset}_{i}",
                    status=status,
                    scheduled_time=day_time + timedelta(hours=i),
                )
                temp_db.create_task(task)

        # Get weekly stats
        weekly = temp_db.get_weekly_stats(start_date)
        assert weekly.total_tasks == 70  # 7 days * 10 tasks
        assert weekly.success_count == 49  # 7 days * 7 success
        assert weekly.failed_count == 14  # 7 days * 2 failed
        assert len(weekly.daily_stats) == 7


@pytest.mark.integration
class TestDatabaseConcurrency:
    """Test database concurrent access"""

    def test_concurrent_task_creation(self, temp_db):
        """Test creating tasks from multiple threads"""
        import threading

        errors = []
        task_ids = []

        def create_tasks(start_idx, count):
            try:
                for i in range(count):
                    task = Task(
                        content_code=f"CONCURRENT_{start_idx}_{i}",
                        status=TaskStatus.pending,
                    )
                    task_id = temp_db.create_task(task)
                    task_ids.append(task_id)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            t = threading.Thread(target=create_tasks, args=(i * 20, 20))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(task_ids) == 100

        # Verify all tasks created
        tasks = temp_db.list_tasks(limit=200)
        assert len(tasks) == 100
