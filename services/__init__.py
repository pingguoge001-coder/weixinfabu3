# Services package
"""
服务层模块

包含:
- config_manager: 配置管理（YAML加载、加密、热重载）
- email_notifier: 邮件通知服务
- notification_manager: 统一通知管理
- time_service: 时间服务（时区处理、格式化）
- stats_service: 统计服务（日统计、周统计、趋势分析）
"""

from services.config_manager import (
    ConfigManager,
    get_config,
    EncryptionManager,
)

from services.email_notifier import (
    EmailNotifier,
    EmailResult,
    get_email_notifier,
)

from services.notification_manager import (
    NotificationManager,
    NotificationChannel,
    NotificationStatus,
    EventType,
    Notification,
    get_notification_manager,
    notify,
    notify_failure,
    notify_circuit_break,
    notify_risk,
)

from services.time_service import (
    TimeService,
    get_time_service,
    now,
    today,
    format_datetime,
    parse_datetime,
    is_within_active_hours,
)

from services.stats_service import (
    StatsService,
)

__all__ = [
    # Config
    "ConfigManager",
    "get_config",
    "EncryptionManager",
    # Email
    "EmailNotifier",
    "EmailResult",
    "get_email_notifier",
    # Notification
    "NotificationManager",
    "NotificationChannel",
    "NotificationStatus",
    "EventType",
    "Notification",
    "get_notification_manager",
    "notify",
    "notify_failure",
    "notify_circuit_break",
    "notify_risk",
    # Time Service
    "TimeService",
    "get_time_service",
    "now",
    "today",
    "format_datetime",
    "parse_datetime",
    "is_within_active_hours",
    # Stats Service
    "StatsService",
]
