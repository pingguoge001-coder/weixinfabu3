"""内容模型模块"""

import json
from dataclasses import dataclass, field
from typing import List, Optional

from .enums import Channel


@dataclass
class Content:
    """内容模型"""

    content_code: str = ""  # 内容唯一编码
    text: str = ""  # 发布文本内容
    image_paths: List[str] = field(default_factory=list)  # 图片路径列表
    channel: Channel = Channel.moment  # 发布渠道
    product_link: str = ""  # 产品链接（用于评论）
    product_name: str = ""  # 产品名称
    category: str = ""  # 分类

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "content_code": self.content_code,
            "text": self.text,
            "image_paths": self.image_paths,
            "channel": self.channel.value if isinstance(self.channel, Channel) else self.channel,
            "product_link": self.product_link,
            "product_name": self.product_name,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Content":
        """从字典创建实例"""
        # 处理枚举类型（兼容旧数据 "group" -> "agent_group"）
        if "channel" in data and data["channel"]:
            if isinstance(data["channel"], str):
                channel_value = data["channel"]
                if channel_value == "group":
                    channel_value = "agent_group"
                data["channel"] = Channel(channel_value)

        # 处理图片路径（可能是 JSON 字符串）
        if "image_paths" in data:
            if isinstance(data["image_paths"], str):
                try:
                    data["image_paths"] = json.loads(data["image_paths"])
                except json.JSONDecodeError:
                    data["image_paths"] = []

        return cls(**data)

    @property
    def has_images(self) -> bool:
        """是否包含图片"""
        return len(self.image_paths) > 0

    @property
    def full_text(self) -> str:
        """获取完整文案（包含 #产品名称  #分类 标签）"""
        parts = [self.text] if self.text else []

        # 添加标签
        tags = []
        if self.product_name:
            tags.append(f"#{self.product_name}")
        if self.category:
            tags.append(f"#{self.category}")

        if tags:
            parts.append("  ".join(tags))

        return "\n".join(parts) if parts else ""

    @property
    def image_count(self) -> int:
        """图片数量"""
        return len(self.image_paths)

    def image_paths_json(self) -> str:
        """返回图片路径的 JSON 字符串（用于数据库存储）"""
        return json.dumps(self.image_paths, ensure_ascii=False)

    def add_image(self, path: str) -> None:
        """添加图片路径"""
        if path and path not in self.image_paths:
            self.image_paths.append(path)

    def remove_image(self, path: str) -> bool:
        """移除图片路径"""
        if path in self.image_paths:
            self.image_paths.remove(path)
            return True
        return False

    def clear_images(self) -> None:
        """清空图片列表"""
        self.image_paths.clear()

    def validate(self) -> tuple[bool, Optional[str]]:
        """验证内容有效性"""
        if not self.content_code:
            return False, "内容编码不能为空"

        if not self.text and not self.image_paths:
            return False, "文本和图片不能同时为空"

        # 朋友圈最多 9 张图片
        if self.channel == Channel.moment and len(self.image_paths) > 9:
            return False, "朋友圈最多支持 9 张图片"

        return True, None
