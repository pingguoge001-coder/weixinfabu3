"""任务模型模块"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from .enums import TaskStatus, Channel


@dataclass
class Task:
    """任务模型"""

    # 基础标识
    id: Optional[int] = None
    content_code: str = ""  # 文案编号
    product_name: str = ""
    category: str = ""  # 分类
    product_link: str = ""  # 产品链接（用于评论）
    text: str = ""  # 文案内容
    image_paths: List[str] = field(default_factory=list)  # 图片路径列表

    # 渠道信息
    channel: Channel = Channel.moment
    group_name: Optional[str] = None  # 群发时的群名称

    # 状态与调度
    status: TaskStatus = TaskStatus.pending
    scheduled_time: Optional[datetime] = None
    priority: int = 0  # 优先级，数值越大优先级越高

    # 重试机制
    retry_count: int = 0
    max_retry: int = 3

    # 执行结果
    executed_time: Optional[datetime] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None

    # 附加信息
    failure_reason: Optional[str] = None
    pause_reason: Optional[str] = None
    note: Optional[str] = None
    source_folder: Optional[str] = None

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "content_code": self.content_code,
            "product_name": self.product_name,
            "category": self.category,
            "product_link": self.product_link,
            "text": self.text,
            "image_paths": self.image_paths,
            "channel": self.channel.value if isinstance(self.channel, Channel) else self.channel,
            "group_name": self.group_name,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "priority": self.priority,
            "retry_count": self.retry_count,
            "max_retry": self.max_retry,
            "executed_time": self.executed_time.isoformat() if self.executed_time else None,
            "error_message": self.error_message,
            "screenshot_path": self.screenshot_path,
            "failure_reason": self.failure_reason,
            "pause_reason": self.pause_reason,
            "note": self.note,
            "source_folder": self.source_folder,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def image_paths_json(self) -> str:
        """返回图片路径的 JSON 字符串（用于数据库存储）"""
        return json.dumps(self.image_paths, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """从字典创建实例"""
        # 处理枚举类型（兼容旧数据 "group" -> "agent_group"）
        if "channel" in data and data["channel"]:
            if isinstance(data["channel"], str):
                channel_value = data["channel"]
                if channel_value == "group":
                    channel_value = "agent_group"
                data["channel"] = Channel(channel_value)

        if "status" in data and data["status"]:
            if isinstance(data["status"], str):
                data["status"] = TaskStatus(data["status"])

        # 处理时间类型
        for time_field in ["scheduled_time", "executed_time", "created_at", "updated_at"]:
            if time_field in data and data[time_field]:
                if isinstance(data[time_field], str):
                    data[time_field] = datetime.fromisoformat(data[time_field])

        # 处理图片路径（可能是 JSON 字符串）
        if "image_paths" in data:
            if isinstance(data["image_paths"], str):
                try:
                    data["image_paths"] = json.loads(data["image_paths"])
                except json.JSONDecodeError:
                    data["image_paths"] = []
            elif data["image_paths"] is None:
                data["image_paths"] = []

        return cls(**data)

    @property
    def can_retry(self) -> bool:
        """是否可以重试"""
        return self.retry_count < self.max_retry

    @property
    def scheduled_date(self) -> Optional[str]:
        """获取调度日期 (YYYY-MM-DD)"""
        if self.scheduled_time:
            return self.scheduled_time.strftime("%Y-%m-%d")
        return None

    def increment_retry(self) -> None:
        """增加重试次数"""
        self.retry_count += 1
        self.updated_at = datetime.now()

    def mark_success(self, screenshot_path: Optional[str] = None) -> None:
        """标记为成功"""
        self.status = TaskStatus.success
        self.executed_time = datetime.now()
        self.screenshot_path = screenshot_path
        self.updated_at = datetime.now()

    def mark_failed(self, error_message: str, failure_reason: Optional[str] = None) -> None:
        """标记为失败"""
        self.status = TaskStatus.failed
        self.error_message = error_message
        self.failure_reason = failure_reason
        self.executed_time = datetime.now()
        self.updated_at = datetime.now()

    def mark_running(self) -> None:
        """标记为执行中"""
        self.status = TaskStatus.running
        self.updated_at = datetime.now()

    def mark_paused(self, reason: str) -> None:
        """标记为暂停"""
        self.status = TaskStatus.paused
        self.pause_reason = reason
        self.updated_at = datetime.now()

    def mark_skipped(self, reason: str = "") -> None:
        """标记为跳过"""
        self.status = TaskStatus.skipped
        self.note = reason if reason else self.note
        self.updated_at = datetime.now()

    def mark_cancelled(self) -> None:
        """标记为取消"""
        self.status = TaskStatus.cancelled
        self.updated_at = datetime.now()
