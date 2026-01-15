"""SQLite 数据库操作模块"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Optional, Generator, Any

from models.enums import TaskStatus, Channel
from models.task import Task
from models.content import Content
from models.stats import DailyStats, WeeklyStats, TaskSummary

# 默认数据库路径
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "wechat_publish.db"

# 亚洲/上海时区偏移（UTC+8）
TIMEZONE_OFFSET = "+08:00"


class Database:
    """SQLite 数据库操作类"""

    _local = threading.local()

    def __init__(self, db_path: Optional[Path] = None):
        """初始化数据库"""
        if db_path is None:
            self.db_path = DEFAULT_DB_PATH
        elif isinstance(db_path, str):
            self.db_path = Path(db_path)
        else:
            self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # 启用 WAL 模式
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.connection = conn
        return self._local.connection

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """数据库连接上下文管理器"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @contextmanager
    def cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """游标上下文管理器"""
        with self.connection() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
            finally:
                cursor.close()

    def _init_db(self) -> None:
        """初始化数据库表结构"""
        with self.cursor() as cur:
            # 任务表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_code TEXT NOT NULL,
                    product_name TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    product_link TEXT DEFAULT '',
                    channel TEXT NOT NULL DEFAULT 'moment',
                    group_name TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    scheduled_time TEXT,
                    scheduled_date TEXT GENERATED ALWAYS AS (DATE(scheduled_time)) STORED,
                    priority INTEGER DEFAULT 0,
                    retry_count INTEGER DEFAULT 0,
                    max_retry INTEGER DEFAULT 3,
                    executed_time TEXT,
                    error_message TEXT,
                    screenshot_path TEXT,
                    failure_reason TEXT,
                    pause_reason TEXT,
                    note TEXT,
                    source_folder TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
                    UNIQUE(content_code, channel, group_name, scheduled_date)
                )
            """)

            try:
                cur.execute("ALTER TABLE tasks ADD COLUMN source_folder TEXT")
            except sqlite3.OperationalError:
                pass  # 列已存在，忽略

            # 幂等键表（用于防止重复执行）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS idempotent_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    idempotent_key TEXT NOT NULL UNIQUE,
                    task_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
                    expires_at TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                )
            """)

            # 内容表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS contents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_code TEXT NOT NULL UNIQUE,
                    text TEXT DEFAULT '',
                    image_paths TEXT DEFAULT '[]',
                    channel TEXT NOT NULL DEFAULT 'moment',
                    product_name TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now', '+8 hours'))
                )
            """)

            # 创建索引
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_time ON tasks(scheduled_time)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_date ON tasks(scheduled_date)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_channel ON tasks(channel)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_idempotent_keys_key ON idempotent_keys(idempotent_key)")

            # 数据库迁移：为现有表添加 category 列
            try:
                cur.execute("ALTER TABLE tasks ADD COLUMN category TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # 列已存在，忽略

            # 数据库迁移：为 tasks 表添加 image_paths 列（存储图片路径JSON）
            try:
                cur.execute("ALTER TABLE tasks ADD COLUMN image_paths TEXT DEFAULT '[]'")
            except sqlite3.OperationalError:
                pass  # 列已存在，忽略
            # 数据库迁移：为 tasks 表添加 product_link 列
            try:
                cur.execute("ALTER TABLE tasks ADD COLUMN product_link TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # 列已存在，忽略

            # 数据库迁移：为 contents 表添加 product_name 和 category 列
            try:
                cur.execute("ALTER TABLE contents ADD COLUMN product_name TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # 列已存在，忽略

            try:
                cur.execute("ALTER TABLE contents ADD COLUMN category TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # 列已存在，忽略

    def close(self) -> None:
        """关闭数据库连接"""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

    # ==================== 任务 CRUD ====================

    def create_task(self, task: Task) -> int:
        """创建任务"""
        with self.cursor() as cur:
            cur.execute("""
                INSERT INTO tasks (
                    content_code, product_name, category, product_link, image_paths, channel, group_name,
                    status, scheduled_time, priority, retry_count, max_retry,
                    error_message, screenshot_path, failure_reason, pause_reason, note, source_folder
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.content_code,
                task.product_name,
                task.category,
                task.product_link,
                task.image_paths_json(),
                task.channel.value if isinstance(task.channel, Channel) else task.channel,
                task.group_name,
                task.status.value if isinstance(task.status, TaskStatus) else task.status,
                task.scheduled_time.isoformat() if task.scheduled_time else None,
                task.priority,
                task.retry_count,
                task.max_retry,
                task.error_message,
                task.screenshot_path,
                task.failure_reason,
                task.pause_reason,
                task.note,
                task.source_folder,
            ))
            return cur.lastrowid

    def get_task(self, task_id: int) -> Optional[Task]:
        """获取单个任务"""
        with self.cursor() as cur:
            cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cur.fetchone()
            if row:
                return self._row_to_task(row)
            return None

    def update_task(self, task: Task) -> bool:
        """更新任务"""
        if not task.id:
            return False

        with self.cursor() as cur:
            cur.execute("""
                UPDATE tasks SET
                    content_code = ?,
                    product_name = ?,
                    category = ?,
                    product_link = ?,
                    image_paths = ?,
                    channel = ?,
                    group_name = ?,
                    status = ?,
                    scheduled_time = ?,
                    priority = ?,
                    retry_count = ?,
                    max_retry = ?,
                    executed_time = ?,
                    error_message = ?,
                    screenshot_path = ?,
                    failure_reason = ?,
                    pause_reason = ?,
                    note = ?,
                    source_folder = ?,
                    updated_at = datetime('now', '+8 hours')
                WHERE id = ?
            """, (
                task.content_code,
                task.product_name,
                task.category,
                task.product_link,
                task.image_paths_json(),
                task.channel.value if isinstance(task.channel, Channel) else task.channel,
                task.group_name,
                task.status.value if isinstance(task.status, TaskStatus) else task.status,
                task.scheduled_time.isoformat() if task.scheduled_time else None,
                task.priority,
                task.retry_count,
                task.max_retry,
                task.executed_time.isoformat() if task.executed_time else None,
                task.error_message,
                task.screenshot_path,
                task.failure_reason,
                task.pause_reason,
                task.note,
                task.source_folder,
                task.id,
            ))
            return cur.rowcount > 0

    def delete_task(self, task_id: int) -> bool:
        """删除任务"""
        with self.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cur.rowcount > 0

    def delete_tasks_by_channel(self, channel: str) -> int:
        """删除指定渠道的所有任务

        Args:
            channel: 渠道标识（Channel枚举值或自定义渠道ID如 'custom_1'）

        Returns:
            删除的任务数量
        """
        channel_value = channel.value if isinstance(channel, Channel) else channel
        with self.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE channel = ?", (channel_value,))
            return cur.rowcount

    def delete_all_tasks(self) -> int:
        """删除所有任务

        Returns:
            删除的任务数量
        """
        with self.cursor() as cur:
            cur.execute("DELETE FROM tasks")
            return cur.rowcount

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        channel: Optional[Channel] = None,
        scheduled_date: Optional[date] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Task]:
        """查询任务列表"""
        query = "SELECT * FROM tasks WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.value if isinstance(status, TaskStatus) else status)

        if channel:
            query += " AND channel = ?"
            params.append(channel.value if isinstance(channel, Channel) else channel)

        if scheduled_date:
            query += " AND scheduled_date = ?"
            params.append(scheduled_date.isoformat())

        query += " ORDER BY priority DESC, scheduled_time ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return [self._row_to_task(row) for row in rows]

    def get_pending_tasks(self, before_time: Optional[datetime] = None) -> List[Task]:
        """获取待执行任务"""
        query = "SELECT * FROM tasks WHERE status IN ('pending', 'scheduled')"
        params: List[Any] = []

        if before_time:
            query += " AND scheduled_time <= ?"
            params.append(before_time.isoformat())

        query += " ORDER BY priority DESC, scheduled_time ASC"

        with self.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return [self._row_to_task(row) for row in rows]

    def get_task_by_id(self, task_id: int) -> Optional[Task]:
        """根据ID获取任务（get_task的别名）"""
        return self.get_task(task_id)

    def get_scheduled_tasks(self, before_time: Optional[datetime] = None) -> List[Task]:
        """获取已调度的任务（状态为 scheduled 且时间已到）"""
        now = datetime.now()
        target_time = before_time or now

        query = """
            SELECT * FROM tasks
            WHERE status IN ('pending', 'scheduled')
            AND (scheduled_time IS NULL OR scheduled_time <= ?)
            ORDER BY priority DESC, scheduled_time ASC
        """

        with self.cursor() as cur:
            cur.execute(query, (target_time.isoformat(),))
            rows = cur.fetchall()
            return [self._row_to_task(row) for row in rows]

    def get_today_task_count(self) -> int:
        """获取今日任务执行数量"""
        today = date.today().isoformat()

        with self.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as count FROM tasks
                WHERE scheduled_date = ?
                AND status IN ('success', 'failed', 'running')
            """, (today,))
            row = cur.fetchone()
            return row["count"] if row else 0

    def mark_running_tasks_as_failed(self) -> int:
        """将所有运行中的任务标记为失败（用于异常恢复）"""
        with self.cursor() as cur:
            cur.execute("""
                UPDATE tasks SET
                    status = 'failed',
                    error_message = '任务异常中断',
                    updated_at = datetime('now', '+8 hours')
                WHERE status = 'running'
            """)
            return cur.rowcount

    def update_task_status(
        self,
        task_id: int,
        status: TaskStatus,
        error_message: Optional[str] = None,
        screenshot_path: Optional[str] = None,
    ) -> bool:
        """更新任务状态"""
        with self.cursor() as cur:
            if status == TaskStatus.success:
                cur.execute("""
                    UPDATE tasks SET
                        status = ?,
                        executed_time = datetime('now', '+8 hours'),
                        screenshot_path = ?,
                        updated_at = datetime('now', '+8 hours')
                    WHERE id = ?
                """, (status.value, screenshot_path, task_id))
            elif status == TaskStatus.failed:
                cur.execute("""
                    UPDATE tasks SET
                        status = ?,
                        executed_time = datetime('now', '+8 hours'),
                        error_message = ?,
                        updated_at = datetime('now', '+8 hours')
                    WHERE id = ?
                """, (status.value, error_message, task_id))
            else:
                cur.execute("""
                    UPDATE tasks SET
                        status = ?,
                        updated_at = datetime('now', '+8 hours')
                    WHERE id = ?
                """, (status.value, task_id))
            return cur.rowcount > 0

    def increment_retry(self, task_id: int) -> bool:
        """增加重试次数"""
        with self.cursor() as cur:
            cur.execute("""
                UPDATE tasks SET
                    retry_count = retry_count + 1,
                    updated_at = datetime('now', '+8 hours')
                WHERE id = ?
            """, (task_id,))
            return cur.rowcount > 0

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """将数据库行转换为 Task 对象"""
        data = dict(row)

        # 转换枚举（兼容旧数据 "group" -> "agent_group"，支持自定义渠道）
        if data.get("channel"):
            channel_value = data["channel"]
            if channel_value == "group":
                channel_value = "agent_group"
            # 自定义渠道保持字符串，内置渠道转换为枚举
            if Channel.is_custom_channel(channel_value):
                data["channel"] = channel_value  # 保持字符串
            else:
                data["channel"] = Channel(channel_value)
        if data.get("status"):
            data["status"] = TaskStatus(data["status"])

        # 转换时间
        for field in ["scheduled_time", "executed_time", "created_at", "updated_at"]:
            if data.get(field) and isinstance(data[field], str):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except ValueError:
                    data[field] = None

        # 转换图片路径（JSON字符串 -> 列表）
        if data.get("image_paths"):
            if isinstance(data["image_paths"], str):
                try:
                    data["image_paths"] = json.loads(data["image_paths"])
                except json.JSONDecodeError:
                    data["image_paths"] = []
        else:
            data["image_paths"] = []

        # 移除 scheduled_date（这是生成列）
        data.pop("scheduled_date", None)

        return Task(**data)

    # ==================== 幂等键操作 ====================

    def check_idempotent_key(self, key: str) -> bool:
        """检查幂等键是否存在且未过期"""
        with self.cursor() as cur:
            cur.execute("""
                SELECT id FROM idempotent_keys
                WHERE idempotent_key = ?
                AND (expires_at IS NULL OR expires_at > datetime('now', '+8 hours'))
            """, (key,))
            return cur.fetchone() is not None

    def create_idempotent_key(
        self,
        key: str,
        task_id: Optional[int] = None,
        expires_hours: int = 24,
    ) -> bool:
        """创建幂等键"""
        try:
            with self.cursor() as cur:
                expires_at = (datetime.now() + timedelta(hours=expires_hours)).isoformat()
                cur.execute("""
                    INSERT INTO idempotent_keys (idempotent_key, task_id, expires_at)
                    VALUES (?, ?, ?)
                """, (key, task_id, expires_at))
                return True
        except sqlite3.IntegrityError:
            return False

    def update_idempotent_key_status(self, key: str, status: str) -> bool:
        """更新幂等键状态"""
        with self.cursor() as cur:
            cur.execute("""
                UPDATE idempotent_keys SET status = ? WHERE idempotent_key = ?
            """, (status, key))
            return cur.rowcount > 0

    def cleanup_expired_keys(self) -> int:
        """清理过期的幂等键"""
        with self.cursor() as cur:
            cur.execute("""
                DELETE FROM idempotent_keys
                WHERE expires_at IS NOT NULL
                AND expires_at < datetime('now', '+8 hours')
            """)
            return cur.rowcount

    def generate_idempotent_key(self, task: Task) -> str:
        """生成任务的幂等键"""
        scheduled_date = task.scheduled_date or date.today().isoformat()
        group_name = task.group_name or ""
        channel = task.channel.value if isinstance(task.channel, Channel) else task.channel
        return f"{task.content_code}:{channel}:{group_name}:{scheduled_date}"

    # ==================== 内容 CRUD ====================

    def create_content(self, content: Content) -> bool:
        """创建内容"""
        try:
            with self.cursor() as cur:
                cur.execute("""
                    INSERT INTO contents (content_code, text, image_paths, channel, product_name, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    content.content_code,
                    content.text,
                    content.image_paths_json(),
                    content.channel.value if isinstance(content.channel, Channel) else content.channel,
                    content.product_name,
                    content.category,
                ))
                return True
        except sqlite3.IntegrityError:
            return False

    def get_content(self, content_code: str) -> Optional[Content]:
        """获取内容"""
        with self.cursor() as cur:
            cur.execute("SELECT * FROM contents WHERE content_code = ?", (content_code,))
            row = cur.fetchone()
            if row:
                return self._row_to_content(row)
            return None

    def update_content(self, content: Content) -> bool:
        """更新内容"""
        with self.cursor() as cur:
            cur.execute("""
                UPDATE contents SET
                    text = ?,
                    image_paths = ?,
                    channel = ?,
                    product_name = ?,
                    category = ?,
                    updated_at = datetime('now', '+8 hours')
                WHERE content_code = ?
            """, (
                content.text,
                content.image_paths_json(),
                content.channel.value if isinstance(content.channel, Channel) else content.channel,
                content.product_name,
                content.category,
                content.content_code,
            ))
            return cur.rowcount > 0

    def delete_content(self, content_code: str) -> bool:
        """删除内容"""
        with self.cursor() as cur:
            cur.execute("DELETE FROM contents WHERE content_code = ?", (content_code,))
            return cur.rowcount > 0

    def _row_to_content(self, row: sqlite3.Row) -> Content:
        """将数据库行转换为 Content 对象"""
        data = dict(row)

        # 转换枚举（兼容旧数据 "group" -> "agent_group"，支持自定义渠道）
        if data.get("channel"):
            channel_value = data["channel"]
            if channel_value == "group":
                channel_value = "agent_group"
            # 自定义渠道保持字符串，内置渠道转换为枚举
            if Channel.is_custom_channel(channel_value):
                data["channel"] = channel_value  # 保持字符串
            else:
                data["channel"] = Channel(channel_value)

        # 转换图片路径
        if data.get("image_paths"):
            if isinstance(data["image_paths"], str):
                try:
                    data["image_paths"] = json.loads(data["image_paths"])
                except json.JSONDecodeError:
                    data["image_paths"] = []

        # 移除不需要的字段
        data.pop("id", None)
        data.pop("created_at", None)
        data.pop("updated_at", None)

        return Content(**data)

    # ==================== 统计查询 ====================

    def get_daily_stats(self, stat_date: Optional[date] = None) -> DailyStats:
        """获取日统计"""
        target_date = stat_date or date.today()
        stats = DailyStats(stat_date=target_date)

        with self.cursor() as cur:
            # 状态计数
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM tasks
                WHERE scheduled_date = ?
                GROUP BY status
            """, (target_date.isoformat(),))

            for row in cur.fetchall():
                status = row["status"]
                count = row["count"]
                stats.total_tasks += count

                if status == TaskStatus.success.value:
                    stats.success_count = count
                elif status == TaskStatus.failed.value:
                    stats.failed_count = count
                elif status == TaskStatus.pending.value:
                    stats.pending_count = count
                elif status == TaskStatus.skipped.value:
                    stats.skipped_count = count
                elif status == TaskStatus.cancelled.value:
                    stats.cancelled_count = count
                elif status == TaskStatus.paused.value:
                    stats.paused_count = count

            # 渠道计数
            cur.execute("""
                SELECT channel, COUNT(*) as count
                FROM tasks
                WHERE scheduled_date = ?
                GROUP BY channel
            """, (target_date.isoformat(),))

            for row in cur.fetchall():
                if row["channel"] == Channel.moment.value:
                    stats.moment_count = row["count"]
                elif row["channel"] == Channel.agent_group.value:
                    stats.agent_group_count = row["count"]
                elif row["channel"] == Channel.customer_group.value:
                    stats.customer_group_count = row["count"]

            # 重试统计
            cur.execute("""
                SELECT SUM(retry_count) as total_retries
                FROM tasks
                WHERE scheduled_date = ?
            """, (target_date.isoformat(),))
            row = cur.fetchone()
            if row and row["total_retries"]:
                stats.total_retries = row["total_retries"]

            # 时间统计
            cur.execute("""
                SELECT MIN(executed_time) as first_time, MAX(executed_time) as last_time
                FROM tasks
                WHERE scheduled_date = ? AND executed_time IS NOT NULL
            """, (target_date.isoformat(),))
            row = cur.fetchone()
            if row:
                if row["first_time"]:
                    stats.first_task_time = datetime.fromisoformat(row["first_time"])
                if row["last_time"]:
                    stats.last_task_time = datetime.fromisoformat(row["last_time"])

        return stats

    def get_weekly_stats(self, start_date: Optional[date] = None) -> WeeklyStats:
        """获取周统计"""
        if start_date is None:
            today = date.today()
            start_date = today - timedelta(days=today.weekday())

        end_date = start_date + timedelta(days=6)
        stats = WeeklyStats(start_date=start_date, end_date=end_date)

        # 获取每日统计
        current = start_date
        while current <= end_date:
            daily = self.get_daily_stats(current)
            stats.daily_stats.append(daily)
            current += timedelta(days=1)

        # 聚合统计
        stats.aggregate_from_daily()

        # 产品统计
        with self.cursor() as cur:
            cur.execute("""
                SELECT product_name, COUNT(*) as count
                FROM tasks
                WHERE scheduled_date BETWEEN ? AND ?
                GROUP BY product_name
                ORDER BY count DESC
            """, (start_date.isoformat(), end_date.isoformat()))
            stats.product_stats = {row["product_name"]: row["count"] for row in cur.fetchall()}

            # 失败原因统计
            cur.execute("""
                SELECT failure_reason, COUNT(*) as count
                FROM tasks
                WHERE scheduled_date BETWEEN ? AND ?
                AND status = 'failed'
                AND failure_reason IS NOT NULL
                GROUP BY failure_reason
                ORDER BY count DESC
            """, (start_date.isoformat(), end_date.isoformat()))
            stats.failure_reasons = {row["failure_reason"]: row["count"] for row in cur.fetchall()}

        return stats

    def get_task_summary(self) -> TaskSummary:
        """获取任务概览"""
        summary = TaskSummary()
        today = date.today().isoformat()

        with self.cursor() as cur:
            # 今日统计
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM tasks
                WHERE scheduled_date = ?
                GROUP BY status
            """, (today,))

            for row in cur.fetchall():
                status = row["status"]
                count = row["count"]
                summary.today_total += count

                if status == TaskStatus.success.value:
                    summary.today_success = count
                elif status == TaskStatus.failed.value:
                    summary.today_failed = count
                elif status == TaskStatus.pending.value:
                    summary.today_pending = count

            # 总体统计
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM tasks
                GROUP BY status
            """)

            for row in cur.fetchall():
                status = row["status"]
                count = row["count"]
                summary.total_tasks += count

                if status == TaskStatus.success.value:
                    summary.total_success = count
                elif status == TaskStatus.failed.value:
                    summary.total_failed = count
                elif status == TaskStatus.running.value:
                    summary.running_count = count
                elif status == TaskStatus.scheduled.value:
                    summary.scheduled_count = count
                elif status == TaskStatus.paused.value:
                    summary.paused_count = count

        return summary


# 全局数据库实例
_db_instance: Optional[Database] = None


def get_database(db_path: Optional[Path] = None) -> Database:
    """获取数据库实例（单例模式）"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance


def reset_database() -> None:
    """重置数据库实例"""
    global _db_instance
    if _db_instance:
        _db_instance.close()
        _db_instance = None


def clear_contents_on_startup() -> int:
    """
    启动时清空文案内容表

    保留 tasks 表（用于统计）和 idempotent_keys 表（防重复执行）
    只清空 contents 表（文案数据每天重新从Excel导入）

    Returns:
        清空的记录数
    """
    db = get_database()
    with db.cursor() as cur:
        cur.execute("DELETE FROM contents")
        count = cur.rowcount
    return count


def clear_tasks_on_startup() -> int:
    """
    启动时清空任务表

    清空 tasks 表和 idempotent_keys 表
    每次启动程序时重新导入任务，不保留历史数据

    Returns:
        清空的记录数
    """
    db = get_database()
    with db.cursor() as cur:
        # 清空幂等键表
        cur.execute("DELETE FROM idempotent_keys")
        # 清空任务表
        cur.execute("DELETE FROM tasks")
        count = cur.rowcount
    return count
