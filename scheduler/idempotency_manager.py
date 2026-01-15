"""
幂等性管理器

负责生成幂等键、检查任务是否已执行，防止重复发送
"""
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from models.task import Task
from data.database import Database


logger = logging.getLogger("wechat_auto_sender.idempotency")


class IdempotencyManager:
    """
    幂等性管理器

    幂等键生成规则: content_code + channel + group_name + date
    确保同一内容在同一天只向同一目标发送一次
    """

    def __init__(self, db: Database, config: dict = None):
        """
        初始化幂等性管理器

        Args:
            db: 数据库实例
            config: 配置字典（可选）
        """
        self._db = db
        self._config = config or {}
        logger.info("幂等性管理器初始化完成")

    def generate_key(self, task: Task, date: datetime = None) -> str:
        """
        生成幂等键

        Args:
            task: 任务对象
            date: 指定日期，为 None 则使用任务的调度时间或当前日期

        Returns:
            幂等键 (MD5 哈希值)
        """
        # 确定日期
        if date:
            date_str = date.strftime("%Y-%m-%d")
        elif task.scheduled_time:
            date_str = task.scheduled_time.strftime("%Y-%m-%d")
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")

        # 组装键的各部分
        key_parts = [
            task.content_code or "",
            task.channel.value,
            task.group_name or "",
            date_str
        ]

        # 生成哈希
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode("utf-8")).hexdigest()

    def is_duplicate(self, task: Task) -> bool:
        """
        检查任务是否为重复任务

        Args:
            task: 任务对象

        Returns:
            True 表示已执行过（重复），False 表示未执行
        """
        # 使用任务自带的幂等键，或重新生成
        key = getattr(task, 'idempotent_key', None) or self.generate_key(task)

        # 检查数据库
        exists = self._db.check_idempotent_key(key)

        if exists:
            logger.debug(f"幂等检查: 任务 {task.id} 已执行过 (key: {key[:8]}...)")

        return exists

    def record(self, task: Task) -> bool:
        """
        记录任务的幂等键

        Args:
            task: 任务对象

        Returns:
            是否记录成功
        """
        key = getattr(task, 'idempotent_key', None) or self.generate_key(task)
        success = self._db.create_idempotent_key(key, task.id)

        if success:
            logger.debug(f"幂等键已记录: {task.id} (key: {key[:8]}...)")
        else:
            logger.warning(f"幂等键记录失败: {task.id}")

        return success

    def check_and_record(self, task: Task) -> bool:
        """
        事务性检查并记录幂等键

        这是最常用的方法，在执行任务前调用：
        1. 如果键不存在，记录并返回 True（可以执行）
        2. 如果键已存在，返回 False（应跳过执行）

        Args:
            task: 任务对象

        Returns:
            True: 可以执行（首次）
            False: 应跳过（重复）
        """
        key = getattr(task, 'idempotent_key', None) or self.generate_key(task)

        # 确保任务对象有幂等键（如果Task支持该属性）
        if hasattr(task, 'idempotent_key') and not task.idempotent_key:
            task.idempotent_key = key

        # 先检查是否存在
        if self._db.check_idempotent_key(key):
            logger.info(f"幂等检查拦截: {task.id} 任务已执行过")
            return False

        # 尝试创建记录
        can_execute = self._db.create_idempotent_key(key, task.id)

        if can_execute:
            logger.debug(f"幂等检查通过: {task.id} (key: {key[:8]}...)")
        else:
            logger.info(f"幂等检查拦截: {task.id} 任务已执行过")

        return can_execute

    def remove(self, task: Task) -> bool:
        """
        移除幂等键记录（用于回滚失败的任务）

        注意：此方法应谨慎使用，仅在任务执行失败且需要重试时调用

        Args:
            task: 任务对象

        Returns:
            是否移除成功
        """
        key = getattr(task, 'idempotent_key', None) or self.generate_key(task)

        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "DELETE FROM idempotent_keys WHERE idempotent_key = ?",
                    (key,)
                )
            logger.info(f"幂等键已移除: {task.id}")
            return True
        except Exception as e:
            logger.error(f"移除幂等键失败: {e}")
            return False

    def get_key_info(self, key: str) -> Optional[dict]:
        """
        获取幂等键信息

        Args:
            key: 幂等键

        Returns:
            键信息字典，不存在则返回 None
        """
        try:
            with self._db.cursor() as cur:
                cur.execute("""
                    SELECT idempotent_key, task_id, status, created_at
                    FROM idempotent_keys
                    WHERE idempotent_key = ?
                """, (key,))
                row = cur.fetchone()
                if row:
                    return dict(row)
            return None
        except Exception as e:
            logger.error(f"获取幂等键信息失败: {e}")
            return None

    def cleanup_old_keys(self, days: int = 30) -> int:
        """
        清理过期的幂等键记录

        Args:
            days: 保留天数

        Returns:
            清理的记录数
        """
        # 使用数据库提供的清理方法
        return self._db.cleanup_expired_keys()


class IdempotencyContext:
    """
    幂等性上下文管理器

    用于在 with 语句中自动处理幂等检查和记录

    使用示例:
        with IdempotencyContext(manager, task) as can_execute:
            if can_execute:
                # 执行任务
                pass
    """

    def __init__(self, manager: IdempotencyManager, task: Task):
        self._manager = manager
        self._task = task
        self._can_execute = False
        self._executed = False

    def __enter__(self) -> bool:
        """进入上下文，执行幂等检查"""
        self._can_execute = self._manager.check_and_record(self._task)
        return self._can_execute

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        # 如果发生异常且已记录，移除记录以允许重试
        if exc_type is not None and self._can_execute:
            logger.warning(f"任务执行异常，移除幂等记录: {self._task.id}")
            self._manager.remove(self._task)

        return False  # 不抑制异常
