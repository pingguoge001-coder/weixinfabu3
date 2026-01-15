"""枚举定义模块"""

from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    pending = "pending"          # 待执行
    scheduled = "scheduled"      # 已调度
    running = "running"          # 执行中
    success = "success"          # 成功
    failed = "failed"            # 失败
    skipped = "skipped"          # 跳过
    cancelled = "cancelled"      # 已取消
    paused = "paused"            # 已暂停

    @classmethod
    def can_execute(cls, status: "TaskStatus") -> bool:
        """检查状态是否可以执行（pending 或 scheduled 可执行）"""
        return status in (cls.pending, cls.scheduled)


class TaskPriority(Enum):
    """任务优先级枚举"""
    URGENT = 1      # 紧急
    HIGH = 3        # 高
    NORMAL = 5      # 正常
    LOW = 7         # 低
    LOWEST = 9      # 最低


class Channel(str, Enum):
    """发布渠道枚举"""
    moment = "moment"                # 朋友圈
    agent_group = "agent_group"      # 代理群
    customer_group = "customer_group"  # 客户群

    @classmethod
    def is_group_channel(cls, channel) -> bool:
        """检查是否为群发渠道（包括自定义渠道）"""
        # 自定义渠道都是群发渠道
        if cls.is_custom_channel(channel):
            return True
        # 内置渠道检查
        if isinstance(channel, cls):
            return channel in (cls.agent_group, cls.customer_group)
        return False

    @classmethod
    def is_custom_channel(cls, channel_id) -> bool:
        """检查是否为自定义渠道"""
        return isinstance(channel_id, str) and channel_id.startswith("custom_")

    @classmethod
    def get_display_name(cls, channel) -> str:
        """获取渠道显示名称（支持自定义渠道）"""
        # 自定义渠道从配置获取名称
        if cls.is_custom_channel(channel):
            from services.config_manager import get_config_manager
            return get_config_manager().get_custom_channel_name(channel)
        # 内置渠道
        names = {
            cls.moment: "朋友圈",
            cls.agent_group: "代理群",
            cls.customer_group: "客户群",
        }
        if isinstance(channel, cls):
            return names.get(channel, channel.value)
        return str(channel)


class RiskLevel(str, Enum):
    """风险等级枚举"""
    low = "low"          # 低风险
    medium = "medium"    # 中风险
    high = "high"        # 高风险
    critical = "critical"  # 严重风险


class CircuitState(str, Enum):
    """熔断器状态枚举"""
    closed = "closed"      # 关闭（正常）
    open = "open"          # 打开（熔断）
    half_open = "half_open"  # 半开（试探）


class SendStatus(str, Enum):
    """发送状态枚举（统一用于朋友圈和群发）"""
    SUCCESS = "success"                  # 发送成功
    FAILED = "failed"                    # 发送失败
    PARTIAL = "partial"                  # 部分成功
    TIMEOUT = "timeout"                  # 超时
    CANCELLED = "cancelled"              # 已取消
    GROUP_NOT_FOUND = "group_not_found"  # 群不存在
    WECHAT_ERROR = "wechat_error"        # 微信异常
