"""
通知管理器模块

功能:
- 统一调度各类通知渠道（邮件、系统托盘等）
- 通知去重（同一事件5分钟内不重复通知）
- 通知队列（异步处理）
- 根据配置启用/禁用通知渠道
- 通知历史记录
"""

import sys
import time
import uuid
import copy
import logging
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.config_manager import get_config
from services.email_notifier import get_email_notifier, EmailNotifier


logger = logging.getLogger(__name__)


# ============================================================
# 类型定义
# ============================================================

class NotificationChannel(Enum):
    """通知渠道"""
    EMAIL = "email"
    SYSTEM_TRAY = "system_tray"
    SOUND = "sound"
    LOG = "log"


class NotificationStatus(Enum):
    """通知状态"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class EventType(Enum):
    """事件类型"""
    SUCCESS = "success"              # 任务成功
    FAILURE = "failure"              # 任务失败
    CIRCUIT_BREAK = "circuit_break"  # 熔断触发
    RISK_DETECTED = "risk_detected"  # 风控检测
    DAILY_SUMMARY = "daily_summary"  # 每日汇总
    SYSTEM_ERROR = "system_error"    # 系统错误
    STARTUP = "startup"              # 程序启动
    SHUTDOWN = "shutdown"            # 程序关闭


@dataclass
class Notification:
    """通知数据类"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    event_type: str = ""
    title: str = ""
    content: str = ""
    channel: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None
    status: NotificationStatus = NotificationStatus.PENDING
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "title": self.title,
            "content": self.content,
            "channel": self.channel,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "status": self.status.value,
            "error_message": self.error_message,
        }


@dataclass
class DedupeKey:
    """去重键"""
    event_type: str
    event_key: str
    timestamp: datetime = field(default_factory=datetime.now)


# ============================================================
# 通知管理器
# ============================================================

class NotificationManager:
    """
    通知管理器

    统一管理各类通知的发送，支持多渠道、去重、异步处理
    """

    # 去重时间窗口（秒）
    DEDUPE_WINDOW = 300  # 5分钟

    def __init__(self):
        """初始化通知管理器"""
        # 通知配置
        self._notify_on = get_config("email.notify_on", {})

        # 邮件通知器
        self._email_notifier = get_email_notifier()

        # 通知队列
        self._queue: Queue[Notification] = Queue()

        # 通知历史
        self._history: List[Notification] = []
        self._max_history = 500

        # 去重缓存
        self._dedupe_cache: Dict[str, DedupeKey] = {}
        self._dedupe_lock = threading.Lock()

        # 线程池
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="notify_")

        # 处理线程
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        # 回调函数
        self._callbacks: Dict[str, List[Callable[[Notification], None]]] = {}

        # 启动处理线程
        self._start_worker()

        logger.debug("通知管理器初始化完成")

    def _start_worker(self) -> None:
        """启动工作线程"""
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="notification_worker"
        )
        self._worker_thread.start()

    def _process_queue(self) -> None:
        """处理通知队列"""
        while self._running:
            try:
                notification = self._queue.get(timeout=1)
            except Empty:
                continue

            # 确保 task_done() 始终被调用，避免 queue.join() 死锁
            try:
                self._send_notification(notification)
            except Exception as e:
                logger.error(f"处理通知时出错: {e}")
            finally:
                self._queue.task_done()

    # ========================================================
    # 主要接口
    # ========================================================

    def notify(
        self,
        event_type: str,
        data: Dict[str, Any],
        title: Optional[str] = None,
        content: Optional[str] = None,
        channels: Optional[List[str]] = None,
        dedupe_key: Optional[str] = None
    ) -> None:
        """
        发送通知

        Args:
            event_type: 事件类型
            data: 事件数据
            title: 通知标题
            content: 通知内容
            channels: 通知渠道列表
            dedupe_key: 去重键（用于去重检查）
        """
        # 检查是否应该通知
        if not self._should_notify(event_type):
            logger.debug(f"通知类型 {event_type} 已禁用")
            return

        # 去重检查
        if dedupe_key and not self._should_send(event_type, dedupe_key):
            logger.debug(f"通知已去重: {event_type}:{dedupe_key}")
            return

        # 默认渠道
        if channels is None:
            channels = self._get_default_channels(event_type)

        # 创建通知并加入队列
        for channel in channels:
            notification = Notification(
                event_type=event_type,
                title=title or self._generate_title(event_type, data),
                content=content or self._generate_content(event_type, data),
                channel=channel,
                data=data,
            )
            self._queue.put(notification)

    def notify_success(self, task: "Task") -> None:
        """
        通知任务成功

        Args:
            task: 成功的任务
        """
        self.notify(
            event_type=EventType.SUCCESS.value,
            data=task.to_dict() if hasattr(task, 'to_dict') else {"task": str(task)},
            dedupe_key=f"task_{task.id}" if hasattr(task, 'id') else None
        )

    def notify_failure(self, task: "Task", error: str) -> None:
        """
        通知任务失败

        Args:
            task: 失败的任务
            error: 错误信息
        """
        data = task.to_dict() if hasattr(task, 'to_dict') else {"task": str(task)}
        data["error"] = error

        self.notify(
            event_type=EventType.FAILURE.value,
            data=data,
            dedupe_key=f"task_{task.id}_failure" if hasattr(task, 'id') else None
        )

        # 同时发送邮件（使用深拷贝避免线程间数据竞争）
        if self._notify_on.get("failure", True):
            # 创建任务的深拷贝，避免在异步执行期间原任务被修改
            task_copy = copy.deepcopy(task)
            screenshot_path = getattr(task, 'screenshot_path', None)
            self._executor.submit(
                self._email_notifier.send_task_failure_notice,
                task_copy, error, screenshot_path
            )

    def notify_circuit_break(self, state: str, details: Dict[str, Any]) -> None:
        """
        通知熔断触发

        Args:
            state: 熔断状态
            details: 详细信息
        """
        data = {
            "circuit_state": state,
            **details
        }

        self.notify(
            event_type=EventType.CIRCUIT_BREAK.value,
            data=data,
            dedupe_key=f"circuit_break_{state}"
        )

        # 发送熔断邮件
        if self._notify_on.get("circuit_break", True):
            self._executor.submit(
                self._email_notifier.send_circuit_break_notice,
                details.get("failure_count", 0),
                details.get("last_error", ""),
                state,
                details.get("recovery_timeout", 300)
            )

    def notify_risk(self, risk_level: str, details: str, source: str = "") -> None:
        """
        通知风控检测

        Args:
            risk_level: 风险等级
            details: 详细信息
            source: 风险来源
        """
        data = {
            "risk_level": risk_level,
            "details": details,
            "source": source
        }

        self.notify(
            event_type=EventType.RISK_DETECTED.value,
            data=data,
            dedupe_key=f"risk_{risk_level}_{source}"
        )

        # 发送告警邮件
        # 动态导入避免循环依赖
        try:
            from models.enums import RiskLevel
            level = RiskLevel(risk_level)
        except:
            level = risk_level

        self._executor.submit(
            self._email_notifier.send_alert,
            level,
            f"风控检测 - {source}",
            details
        )

    def send_daily_summary(
        self,
        stats: "DailyStats",
        failed_tasks: Optional[List["Task"]] = None,
        tomorrow_count: int = 0
    ) -> None:
        """
        发送每日汇总

        Args:
            stats: 日统计数据
            failed_tasks: 失败任务列表
            tomorrow_count: 明日任务数
        """
        if not self._notify_on.get("daily_summary", True):
            logger.debug("每日汇总通知已禁用")
            return

        self.notify(
            event_type=EventType.DAILY_SUMMARY.value,
            data=stats.to_dict() if hasattr(stats, 'to_dict') else {}
        )

        # 发送日报邮件
        self._executor.submit(
            self._email_notifier.send_daily_report,
            stats, failed_tasks, tomorrow_count
        )

    # ========================================================
    # 内部方法
    # ========================================================

    def _should_notify(self, event_type: str) -> bool:
        """检查是否应该发送通知"""
        # 映射事件类型到配置键
        config_map = {
            EventType.SUCCESS.value: "success",
            EventType.FAILURE.value: "failure",
            EventType.CIRCUIT_BREAK.value: "circuit_break",
            EventType.RISK_DETECTED.value: "failure",  # 风控归类到失败
            EventType.DAILY_SUMMARY.value: "daily_summary",
        }

        config_key = config_map.get(event_type, event_type)
        return self._notify_on.get(config_key, True)

    def _should_send(self, event_type: str, event_key: str) -> bool:
        """
        检查是否应该发送（去重）

        Args:
            event_type: 事件类型
            event_key: 事件唯一键

        Returns:
            是否应该发送
        """
        cache_key = f"{event_type}:{event_key}"

        with self._dedupe_lock:
            # 清理过期的去重记录
            self._cleanup_dedupe_cache()

            # 检查是否存在
            if cache_key in self._dedupe_cache:
                existing = self._dedupe_cache[cache_key]
                if datetime.now() - existing.timestamp < timedelta(seconds=self.DEDUPE_WINDOW):
                    return False

            # 记录新的
            self._dedupe_cache[cache_key] = DedupeKey(
                event_type=event_type,
                event_key=event_key
            )
            return True

    def _cleanup_dedupe_cache(self) -> None:
        """清理过期的去重缓存"""
        now = datetime.now()
        expired = [
            key for key, value in self._dedupe_cache.items()
            if now - value.timestamp > timedelta(seconds=self.DEDUPE_WINDOW * 2)
        ]
        for key in expired:
            del self._dedupe_cache[key]

    def _get_default_channels(self, event_type: str) -> List[str]:
        """获取默认通知渠道"""
        # 高优先级事件使用所有渠道
        high_priority = [
            EventType.CIRCUIT_BREAK.value,
            EventType.RISK_DETECTED.value,
            EventType.SYSTEM_ERROR.value,
        ]

        if event_type in high_priority:
            return [
                NotificationChannel.EMAIL.value,
                NotificationChannel.SYSTEM_TRAY.value,
                NotificationChannel.LOG.value,
            ]

        # 普通事件只记录日志
        return [NotificationChannel.LOG.value]

    def _generate_title(self, event_type: str, data: Dict) -> str:
        """生成通知标题"""
        titles = {
            EventType.SUCCESS.value: "任务执行成功",
            EventType.FAILURE.value: "任务执行失败",
            EventType.CIRCUIT_BREAK.value: "熔断器触发",
            EventType.RISK_DETECTED.value: "风控检测告警",
            EventType.DAILY_SUMMARY.value: "每日发布汇总",
            EventType.SYSTEM_ERROR.value: "系统错误",
            EventType.STARTUP.value: "程序启动",
            EventType.SHUTDOWN.value: "程序关闭",
        }
        return titles.get(event_type, f"通知: {event_type}")

    def _generate_content(self, event_type: str, data: Dict) -> str:
        """生成通知内容"""
        if event_type == EventType.SUCCESS.value:
            return f"任务 {data.get('content_code', '')} 执行成功"

        if event_type == EventType.FAILURE.value:
            return f"任务 {data.get('content_code', '')} 执行失败: {data.get('error', '未知错误')}"

        if event_type == EventType.CIRCUIT_BREAK.value:
            return f"熔断器已触发，状态: {data.get('circuit_state', 'unknown')}"

        if event_type == EventType.RISK_DETECTED.value:
            return f"检测到风控: {data.get('details', '')}"

        if event_type == EventType.DAILY_SUMMARY.value:
            return f"今日完成 {data.get('total_tasks', 0)} 个任务，成功率 {data.get('success_rate', 0):.1f}%"

        return str(data)

    def _send_notification(self, notification: Notification) -> None:
        """发送单个通知"""
        try:
            channel = notification.channel

            if channel == NotificationChannel.EMAIL.value:
                self._send_email(notification)
            elif channel == NotificationChannel.SYSTEM_TRAY.value:
                self._send_system_tray(notification)
            elif channel == NotificationChannel.SOUND.value:
                self._send_sound(notification)
            elif channel == NotificationChannel.LOG.value:
                self._send_log(notification)
            else:
                logger.warning(f"未知的通知渠道: {channel}")

            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.now()

        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.error_message = str(e)
            logger.error(f"发送通知失败: {e}")

        finally:
            self._add_to_history(notification)
            self._trigger_callbacks(notification)

    def _send_email(self, notification: Notification) -> None:
        """通过邮件发送"""
        # 邮件发送已在具体的 notify_xxx 方法中处理
        # 这里只是占位
        logger.debug(f"邮件通知: {notification.title}")

    def _send_system_tray(self, notification: Notification) -> None:
        """发送系统托盘通知"""
        try:
            # Windows 系统托盘通知
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(
                notification.title,
                notification.content,
                duration=5,
                threaded=True
            )
        except ImportError:
            logger.debug("win10toast 未安装，跳过系统托盘通知")
        except Exception as e:
            logger.debug(f"系统托盘通知失败: {e}")

    def _send_sound(self, notification: Notification) -> None:
        """播放通知声音"""
        try:
            import winsound
            # 播放系统提示音
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception as e:
            logger.debug(f"播放声音失败: {e}")

    def _send_log(self, notification: Notification) -> None:
        """记录到日志"""
        level_map = {
            EventType.SUCCESS.value: logging.INFO,
            EventType.FAILURE.value: logging.WARNING,
            EventType.CIRCUIT_BREAK.value: logging.ERROR,
            EventType.RISK_DETECTED.value: logging.ERROR,
            EventType.SYSTEM_ERROR.value: logging.ERROR,
        }

        level = level_map.get(notification.event_type, logging.INFO)
        logger.log(level, f"[{notification.event_type}] {notification.title}: {notification.content}")

    # ========================================================
    # 历史记录
    # ========================================================

    def _add_to_history(self, notification: Notification) -> None:
        """添加到历史记录"""
        self._history.append(notification)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_notification_history(self, limit: int = 100) -> List[Notification]:
        """获取通知历史"""
        return self._history[-limit:]

    def get_history_by_type(self, event_type: str, limit: int = 50) -> List[Notification]:
        """按类型获取历史"""
        filtered = [n for n in self._history if n.event_type == event_type]
        return filtered[-limit:]

    def get_failed_notifications(self, limit: int = 50) -> List[Notification]:
        """获取失败的通知"""
        filtered = [n for n in self._history if n.status == NotificationStatus.FAILED]
        return filtered[-limit:]

    def clear_history(self) -> None:
        """清空历史记录"""
        self._history.clear()

    # ========================================================
    # 回调管理
    # ========================================================

    def register_callback(
        self,
        event_type: str,
        callback: Callable[[Notification], None]
    ) -> None:
        """注册通知回调"""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

    def unregister_callback(
        self,
        event_type: str,
        callback: Callable[[Notification], None]
    ) -> None:
        """注销通知回调"""
        if event_type in self._callbacks and callback in self._callbacks[event_type]:
            self._callbacks[event_type].remove(callback)

    def _trigger_callbacks(self, notification: Notification) -> None:
        """触发回调"""
        callbacks = self._callbacks.get(notification.event_type, [])
        callbacks += self._callbacks.get("*", [])  # 通配符回调

        for callback in callbacks:
            try:
                callback(notification)
            except Exception as e:
                logger.error(f"通知回调执行失败: {e}")

    # ========================================================
    # 生命周期
    # ========================================================

    def shutdown(self) -> None:
        """关闭通知管理器"""
        self._running = False

        # 等待队列处理完成
        if not self._queue.empty():
            logger.info("等待通知队列处理完成...")
            self._queue.join()

        # 关闭线程池
        self._executor.shutdown(wait=False)

        # 关闭邮件通知器
        self._email_notifier.shutdown()

        logger.info("通知管理器已关闭")

    def __enter__(self) -> "NotificationManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.shutdown()


# ============================================================
# 便捷函数
# ============================================================

_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """获取通知管理器单例"""
    global _manager
    if _manager is None:
        _manager = NotificationManager()
    return _manager


def notify(event_type: str, data: Dict[str, Any], **kwargs) -> None:
    """快捷发送通知"""
    get_notification_manager().notify(event_type, data, **kwargs)


def notify_failure(task: "Task", error: str) -> None:
    """快捷通知任务失败"""
    get_notification_manager().notify_failure(task, error)


def notify_circuit_break(state: str, details: Dict) -> None:
    """快捷通知熔断"""
    get_notification_manager().notify_circuit_break(state, details)


def notify_risk(risk_level: str, details: str, source: str = "") -> None:
    """快捷通知风控"""
    get_notification_manager().notify_risk(risk_level, details, source)


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=== 通知管理器测试 ===\n")

    manager = NotificationManager()

    # 注册回调
    def on_notification(n: Notification):
        print(f"  收到通知: [{n.event_type}] {n.title}")

    manager.register_callback("*", on_notification)

    # 测试各类通知
    print("1. 测试普通通知...")
    manager.notify(
        event_type="test",
        data={"message": "测试消息"},
        title="测试通知",
        content="这是一条测试通知"
    )

    # 等待处理
    time.sleep(1)

    print("\n2. 测试去重...")
    manager.notify("test", {"id": 1}, dedupe_key="test_1")
    manager.notify("test", {"id": 1}, dedupe_key="test_1")  # 应该被去重
    manager.notify("test", {"id": 2}, dedupe_key="test_2")  # 不应该被去重

    time.sleep(1)

    print("\n3. 查看通知历史...")
    history = manager.get_notification_history(10)
    for n in history:
        print(f"  - {n.event_type}: {n.title} [{n.status.value}]")

    print("\n4. 关闭管理器...")
    manager.shutdown()

    print("\n测试完成")
