"""
主窗口模块

提供应用程序的主窗口框架，包含标签页、状态栏和系统托盘。
"""

import logging
from typing import Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QStatusBar, QLabel, QMenu, QMessageBox, QSystemTrayIcon,
    QApplication, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIcon, QAction, QCloseEvent, QPixmap, QPainter, QColor

from models.task import Task
from models.content import Content
from models.enums import TaskStatus, Channel
from data.database import get_database
from core.moment_sender import SendResult
from services.config_manager import get_config_manager
from .queue_tab import QueueTab
from .schedule_tab import ScheduleTab
from .settings_tab import SettingsTab
from .stats_tab import StatsTab
from .styles import GLOBAL_STYLE, TAB_STYLE, STATUSBAR_STYLE, MENU_STYLE, STATUS_NAMES
from .services import TaskExecutor, SchedulerController, ImportHandler

logger = logging.getLogger(__name__)

# ============================================================
# 窗口常量
# ============================================================

# 窗口尺寸
WINDOW_MIN_WIDTH = 1024
WINDOW_MIN_HEIGHT = 700

# 状态指示器尺寸
STATUS_INDICATOR_SIZE = 12

# 托盘图标尺寸
TRAY_ICON_SIZE = 32

# 定时器间隔（毫秒）
TIME_UPDATE_INTERVAL_MS = 1000

# 消息框自动关闭时间（毫秒）
AUTO_CLOSE_TIMEOUT_MS = 3000

# 托盘通知默认显示时长（毫秒）
TRAY_NOTIFICATION_DURATION_MS = 3000


class StatusIndicator(QLabel):
    """状态指示器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = "idle"
        self._colors = {
            "idle": "#9E9E9E",
            "ready": "#4CAF50",
            "running": "#FF9800",
            "paused": "#9C27B0",
            "error": "#F44336",
        }
        self.setFixedSize(STATUS_INDICATOR_SIZE, STATUS_INDICATOR_SIZE)
        self.set_status("idle")

    def set_status(self, status: str):
        """设置状态"""
        self._status = status
        color = self._colors.get(status, "#9E9E9E")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)
        self.setToolTip(self._get_tooltip())

    def _get_tooltip(self) -> str:
        tips = {
            "idle": "空闲",
            "ready": "就绪",
            "running": "运行中",
            "paused": "已暂停",
            "error": "错误",
        }
        return tips.get(self._status, "未知")


class MainWindow(QMainWindow):
    """
    主窗口

    功能：
    - 标签页容器（队列/定时/统计/设置）
    - 状态栏（状态指示、消息、队列数量、今日成功数）
    - 系统托盘（最小化到托盘、右键菜单）
    """

    # 信号定义
    window_shown = Signal()
    window_hidden = Signal()
    quit_requested = Signal()
    task_completed_signal = Signal(object, object)  # task, result
    scheduled_task_finished_signal = Signal(object, object)  # task, result

    def __init__(self, config: dict = None, selectors: dict = None, parent=None):
        super().__init__(parent)

        self.config = config or {}
        self.selectors = selectors or {}

        # 状态追踪
        self._queue_count = 0
        self._today_success = 0
        self._is_publishing = False
        self._close_to_tray = False  # 禁用最小化到托盘，避免影响自动化操作
        self._executing_task: Optional[Task] = None

        # 初始化数据库
        self._db = get_database()

        # 初始化服务层
        self._init_services()

        # 设置窗口属性
        self.setWindowTitle("微信自动发布工具")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # 应用全局样式
        self.setStyleSheet(GLOBAL_STYLE)

        # 初始化 UI
        self._setup_ui()
        self._setup_tray_icon()
        self._setup_menu_bar()
        self._connect_signals()

        # 定时器 - 更新时间显示
        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._update_time)
        self._time_timer.start(TIME_UPDATE_INTERVAL_MS)

        # 初始化 UI 调度设置
        self._init_schedule_settings_ui()

        # 初始化下一任务提示
        self._refresh_next_task_hint()

        logger.info("主窗口初始化完成")

    def _show_auto_close_message(
        self,
        title: str,
        text: str,
        icon: QMessageBox.Icon = QMessageBox.Information,
        timeout_ms: int = AUTO_CLOSE_TIMEOUT_MS,
    ):
        """显示自动关闭的消息框"""
        msg = QMessageBox(self)
        msg.setIcon(icon)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setDefaultButton(QMessageBox.Ok)
        msg.setModal(False)
        msg.show()
        QTimer.singleShot(timeout_ms, msg.accept)

    def _init_services(self):
        """初始化服务层组件"""
        # 任务执行器
        self._task_executor = TaskExecutor(self)
        self._task_executor.set_group_names_provider(self._get_channel_group_names)
        self._task_executor.set_extra_message_provider(self._get_channel_extra_message)
        self._task_executor.task_completed.connect(self._on_task_completed)
        self._task_executor.task_waiting.connect(self._on_task_waiting)
        self._task_executor.task_progress.connect(self._on_task_progress)

        # 调度器控制器
        self._scheduler_controller = SchedulerController(self._db, self.config, self)
        self._scheduler_controller.set_task_executor(self._execute_scheduled_task)
        self._scheduler_controller.set_task_callbacks(
            on_complete=self._on_scheduler_task_complete,
            on_failed=self._on_scheduler_task_failed
        )
        self._scheduler_controller.status_changed.connect(self._on_scheduler_status_changed)
        self._scheduler_controller.queue_status_updated.connect(self._on_queue_status_updated)
        self._scheduler_controller.scheduler_started.connect(self._on_scheduler_started)
        self._scheduler_controller.scheduler_paused.connect(self._on_scheduler_paused)

        # 导入处理器
        self._import_handler = ImportHandler(self._db, self)
        self._import_handler.import_completed.connect(self._on_import_completed)
        self._import_handler.import_failed.connect(self._on_import_failed)

        # 连接内部信号
        self.scheduled_task_finished_signal.connect(self._on_scheduled_task_finished)

        logger.info("服务层组件初始化完成")

    def _get_channel_group_names(self, channel: Channel) -> list:
        """获取渠道的全局群名列表"""
        widget = self.queue_tab.get_channel_widget(channel)
        if widget:
            return widget.get_global_group_names()
        return []

    def _get_channel_extra_message(self, channel: Channel) -> str:
        """获取渠道的额外消息"""
        widget = self.queue_tab.get_channel_widget(channel)
        if widget:
            return widget.get_extra_message()
        return ""

    def _check_task_config_warning(self, task: Task, content: Content) -> None:
        """
        检查配置并显示提醒（不阻断执行）

        Args:
            task: 任务对象
            content: 内容对象
        """
        warnings = []

        # 群发渠道：检查群名列表
        if Channel.is_group_channel(task.channel):
            group_names = self._get_channel_group_names(task.channel)
            if not group_names:
                warnings.append("未配置目标群名列表")

        # 朋友圈：检查图片数量
        if task.channel == Channel.moment:
            if content and content.image_paths and len(content.image_paths) > 9:
                warnings.append(f"图片有 {len(content.image_paths)} 张，超过9张将被截断")

        # 显示提醒（不阻断）
        if warnings:
            QMessageBox.warning(
                self,
                "配置提醒",
                "\n".join(warnings)
            )

    def _init_schedule_settings_ui(self):
        """初始化 UI 调度设置（从队列管理器加载配置）"""
        config_manager = get_config_manager()
        queue_manager = self._scheduler_controller.get_queue_manager()

        # 加载内置渠道配置
        for channel in Channel:
            channel_queue = queue_manager.channel_queues.get(channel)
            if channel_queue:
                # 设置每小时定点分钟
                minute = channel_queue.minute_of_hour
                self.queue_tab.set_channel_minute_of_hour(channel, minute)
                # 设置时间窗口
                start = channel_queue.daily_start
                end = channel_queue.daily_end
                self.queue_tab.set_channel_daily_window(channel, start, end)
                # 设置调度模式与间隔
                mode = config_manager.get_channel_schedule_mode(channel.value)
                interval_value, interval_unit = config_manager.get_channel_interval(channel.value)
                self.queue_tab.set_channel_schedule_mode(channel, mode)
                self.queue_tab.set_channel_interval(channel, interval_value, interval_unit)

            # 加载全局群名（仅群发渠道）
            if Channel.is_group_channel(channel):
                widget = self.queue_tab.get_channel_widget(channel)
                if widget:
                    group_names = config_manager.get_channel_group_names(channel.value)
                    widget.set_global_group_names(group_names)
                    extra_message = config_manager.get_channel_extra_message(channel.value)
                    widget.set_extra_message(extra_message)
                    logger.debug(f"渠道 {channel.value} 加载了 {len(group_names)} 个全局群名")

        # 加载自定义渠道
        custom_channels = config_manager.get_custom_channels()
        if custom_channels:
            self.queue_tab.load_custom_channels(custom_channels)
            logger.info(f"已加载 {len(custom_channels)} 个自定义渠道")

            # 为每个自定义渠道加载配置
            for channel_id, channel_config in custom_channels.items():
                widget = self.queue_tab.get_channel_widget(channel_id)
                if widget:
                    # 加载群名列表
                    group_names = channel_config.get("global_group_names", [])
                    widget.set_global_group_names(group_names)
                    extra_message = channel_config.get("extra_message", "")
                    widget.set_extra_message(extra_message)
                    # 加载时间窗口
                    start = channel_config.get("daily_start_time", "08:00")
                    end = channel_config.get("daily_end_time", "22:00")
                    widget.set_daily_window(start, end)
                    # 加载每小时定点分钟
                    minute = channel_config.get("minute_of_hour", 0)
                    widget.set_minute_of_hour(minute)
                    # 加载调度模式与间隔
                    mode = channel_config.get("mode", "interval")
                    interval_value = channel_config.get("interval_value", 3)
                    interval_unit = channel_config.get("interval_unit", "minutes")
                    widget.set_schedule_mode(mode)
                    widget.set_interval(interval_value, interval_unit)
                    logger.debug(f"自定义渠道 {channel_id} 配置已加载")

        logger.debug("UI 调度设置已从配置加载")

    def _setup_ui(self):
        """设置 UI"""
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(TAB_STYLE)
        self.tab_widget.setDocumentMode(True)

        # 创建标签页
        self.queue_tab = QueueTab()
        self.schedule_tab = ScheduleTab()
        self.stats_tab = StatsTab()
        self.settings_tab = SettingsTab()

        self.tab_widget.addTab(self.queue_tab, "📋 发布队列")
        self.tab_widget.addTab(self.schedule_tab, "✅ 完成列表")
        self.tab_widget.addTab(self.stats_tab, "📊 统计报表")
        self.tab_widget.addTab(self.settings_tab, "⚙️ 系统设置")

        layout.addWidget(self.tab_widget)

        # 状态栏
        self._setup_status_bar()

    def _create_placeholder_tab(self, name: str) -> QWidget:
        """创建占位标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel(f"{name}\n（开发中...）")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                color: #9E9E9E;
                font-size: 18px;
            }
        """)
        layout.addWidget(label)

        return tab

    def _setup_status_bar(self):
        """设置状态栏"""
        status_bar = QStatusBar()
        status_bar.setStyleSheet(STATUSBAR_STYLE)
        self.setStatusBar(status_bar)

        # 状态指示器
        self.status_indicator = StatusIndicator()
        status_bar.addWidget(self.status_indicator)

        # 状态消息
        self.status_message = QLabel("就绪")
        self.status_message.setStyleSheet("color: #424242; margin-left: 8px;")
        status_bar.addWidget(self.status_message)

        # 弹性空间
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        status_bar.addWidget(spacer)

        # 下一任务提示
        self.next_task_label = QLabel("下一任务: -")
        self.next_task_label.setStyleSheet("""
            QLabel {
                background-color: #FFFDE7;
                color: #5D4037;
                padding: 4px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
        """)
        status_bar.addPermanentWidget(self.next_task_label)

        # 队列数量
        self.queue_label = QLabel("队列: 0")
        self.queue_label.setStyleSheet("""
            QLabel {
                background-color: #E3F2FD;
                color: #1976D2;
                padding: 4px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
        """)
        status_bar.addPermanentWidget(self.queue_label)

        # 今日成功数
        self.success_label = QLabel("今日: 0")
        self.success_label.setStyleSheet("""
            QLabel {
                background-color: #E8F5E9;
                color: #388E3C;
                padding: 4px 12px;
                border-radius: 4px;
                font-size: 12px;
                margin-left: 8px;
            }
        """)
        status_bar.addPermanentWidget(self.success_label)

        # 当前时间
        self.time_label = QLabel()
        self.time_label.setStyleSheet("""
            QLabel {
                color: #757575;
                padding: 4px 12px;
                font-size: 12px;
            }
        """)
        status_bar.addPermanentWidget(self.time_label)
        self._update_time()

    def _setup_menu_bar(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        menubar.setStyleSheet(MENU_STYLE)

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        file_menu.setStyleSheet(MENU_STYLE)

        import_action = QAction("选取文件夹...", self)
        import_action.setShortcut("Ctrl+O")
        import_action.triggered.connect(self.queue_tab.import_folder)
        file_menu.addAction(import_action)

        export_action = QAction("导出回执...", self)
        export_action.setShortcut("Ctrl+E")
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self._on_quit)
        file_menu.addAction(exit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑(&E)")
        edit_menu.setStyleSheet(MENU_STYLE)

        settings_action = QAction("设置...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(lambda: self.tab_widget.setCurrentIndex(3))
        edit_menu.addAction(settings_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")
        view_menu.setStyleSheet(MENU_STYLE)

        queue_action = QAction("发布队列", self)
        queue_action.setShortcut("Ctrl+1")
        queue_action.triggered.connect(lambda: self.tab_widget.setCurrentIndex(0))
        view_menu.addAction(queue_action)

        schedule_action = QAction("完成列表", self)
        schedule_action.setShortcut("Ctrl+2")
        schedule_action.triggered.connect(lambda: self.tab_widget.setCurrentIndex(1))
        view_menu.addAction(schedule_action)

        stats_action = QAction("统计报表", self)
        stats_action.setShortcut("Ctrl+3")
        stats_action.triggered.connect(lambda: self.tab_widget.setCurrentIndex(2))
        view_menu.addAction(stats_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        help_menu.setStyleSheet(MENU_STYLE)

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_tray_icon(self):
        """设置系统托盘图标"""
        # 创建托盘图标（使用简单的像素图）
        self.tray_icon = QSystemTrayIcon(self)

        # 创建简单图标
        pixmap = QPixmap(TRAY_ICON_SIZE, TRAY_ICON_SIZE)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#1976D2"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 24, 24)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(10, 10, 12, 12)
        painter.end()

        self.tray_icon.setIcon(QIcon(pixmap))
        self.tray_icon.setToolTip("微信自动发布工具")

        # 托盘菜单
        tray_menu = QMenu()
        tray_menu.setStyleSheet(MENU_STYLE)

        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self._show_window)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        self.tray_pause_action = QAction("暂停发布", self)
        self.tray_pause_action.setCheckable(True)
        self.tray_pause_action.triggered.connect(self._on_tray_pause)
        tray_menu.addAction(self.tray_pause_action)

        tray_menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._on_quit)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)

        # 托盘图标双击
        self.tray_icon.activated.connect(self._on_tray_activated)

        # 显示托盘图标
        self.tray_icon.show()

    def _connect_signals(self):
        """连接信号"""
        # 队列标签页信号
        self.queue_tab.start_publishing_requested.connect(self._on_start_publishing)
        self.queue_tab.pause_publishing_requested.connect(self._on_pause_publishing)
        self.queue_tab.import_requested.connect(self._on_import_file)
        self.queue_tab.task_execute_requested.connect(self._on_execute_task)
        self.queue_tab.task_edit_requested.connect(self._on_edit_task_schedule)
        self.queue_tab.task_cancel_requested.connect(self._on_cancel_task)
        self.queue_tab.minute_of_hour_changed.connect(self._on_minute_of_hour_changed)
        self.queue_tab.schedule_mode_changed.connect(self._on_schedule_mode_changed)
        self.queue_tab.interval_changed.connect(self._on_interval_changed)
        self.queue_tab.daily_window_changed.connect(self._on_daily_window_changed)
        self.queue_tab.tasks_reordered.connect(self._on_tasks_reordered)
        self.queue_tab.group_names_changed.connect(self._on_group_names_changed)
        self.queue_tab.extra_message_changed.connect(self._on_extra_message_changed)

        # 自定义渠道信号
        self.queue_tab.add_channel_requested.connect(self._on_add_channel)
        self.queue_tab.remove_channel_requested.connect(self._on_remove_channel)

        # 清空任务信号
        self.queue_tab.clear_channel_requested.connect(self._on_clear_channel_tasks)
        self.queue_tab.clear_all_requested.connect(self._on_clear_all_tasks)

        # 标签页切换信号
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int):
        """标签页切换时刷新数据"""
        if index == 2:  # 统计报表是第3个标签页（索引2）
            self._load_stats_data()

    def _on_minute_of_hour_changed(self, channel, minute: int):
        """处理每小时定点分钟变更（支持内置渠道和自定义渠道）"""
        channel_id = channel.value if isinstance(channel, Channel) else channel
        logger.info(f"渠道 {channel_id} 每小时定点分钟变更: {minute}")

        # 自定义渠道保存到配置
        if Channel.is_custom_channel(channel_id):
            config = get_config_manager()
            config.set_custom_channel_minute_of_hour(channel_id, minute, save=True)
        else:
            config = get_config_manager()
            config.set_channel_minute_of_hour(channel_id, minute, save=True)
            # 内置渠道使用调度器控制器更新
            self._scheduler_controller.set_channel_minute_of_hour(channel, minute)

    def _on_schedule_mode_changed(self, channel, mode: str):
        """处理调度模式变更（支持内置渠道和自定义渠道）"""
        channel_id = channel.value if isinstance(channel, Channel) else channel
        logger.info(f"渠道 {channel_id} 调度模式变更: {mode}")

        if Channel.is_custom_channel(channel_id):
            config = get_config_manager()
            config.set_custom_channel_schedule_mode(channel_id, mode, save=True)
        else:
            config = get_config_manager()
            config.set_channel_schedule_mode(channel_id, mode, save=True)
            self._scheduler_controller.set_channel_schedule_mode(channel, mode)

    def _on_interval_changed(self, channel, value: int, unit: str):
        """处理发布间隔变更（支持内置渠道和自定义渠道）"""
        channel_id = channel.value if isinstance(channel, Channel) else channel
        logger.info(f"渠道 {channel_id} 发布间隔变更: {value} {unit}")

        if Channel.is_custom_channel(channel_id):
            config = get_config_manager()
            config.set_custom_channel_interval(channel_id, value, unit, save=True)
        else:
            config = get_config_manager()
            config.set_channel_interval(channel_id, value, unit, save=True)
            self._scheduler_controller.set_channel_interval(channel, value, unit)

    def _on_daily_window_changed(self, channel, start: str, end: str):
        """处理每日时间窗口变更（支持内置渠道和自定义渠道）"""
        channel_id = channel.value if isinstance(channel, Channel) else channel
        logger.info(f"渠道 {channel_id} 时间窗口变更: {start} - {end}")

        # 自定义渠道保存到配置
        if Channel.is_custom_channel(channel_id):
            config = get_config_manager()
            config.set_custom_channel_daily_window(channel_id, start, end, save=True)
        else:
            # 内置渠道使用调度器控制器更新
            self._scheduler_controller.set_channel_daily_window(channel, start, end)

    def _on_group_names_changed(self, channel, group_names: list):
        """处理全局群名变更（支持内置渠道和自定义渠道）"""
        channel_id = channel.value if isinstance(channel, Channel) else channel
        logger.info(f"渠道 {channel_id} 全局群名变更: {len(group_names)} 个")
        config_manager = get_config_manager()

        # 判断是内置渠道还是自定义渠道
        if Channel.is_custom_channel(channel_id):
            config_manager.set_custom_channel_group_names(channel_id, group_names, save=True)
        else:
            config_manager.set_channel_group_names(channel_id, group_names, save=True)
        logger.info(f"渠道 {channel_id} 全局群名已保存到配置")

    def _on_extra_message_changed(self, channel, message: str):
        """Handle extra message updates for group channels."""
        channel_id = channel.value if isinstance(channel, Channel) else channel
        config_manager = get_config_manager()

        if Channel.is_custom_channel(channel_id):
            config_manager.set_custom_channel_extra_message(channel_id, message, save=True)
        else:
            config_manager.set_channel_extra_message(channel_id, message, save=True)

        logger.info(f"channel {channel_id} extra message saved (len={len(message)})")

    def _on_add_channel(self, name: str):
        """处理添加自定义渠道"""
        config = get_config_manager()
        channel_id = config.generate_custom_channel_id()

        if config.add_custom_channel(channel_id, name):
            self.queue_tab.add_custom_channel(channel_id, name)
            logger.info(f"已添加自定义渠道: {name} ({channel_id})")

            # 显示成功提示
            self._show_auto_close_message(
                "渠道添加成功",
                f"已添加渠道「{name}」",
                QMessageBox.Information,
                timeout_ms=2000
            )
        else:
            QMessageBox.warning(self, "添加失败", "添加渠道失败，请重试")

    def _on_remove_channel(self, channel_id: str):
        """处理删除自定义渠道"""
        config = get_config_manager()

        # 删除该渠道的所有任务
        deleted_count = self._db.delete_tasks_by_channel(channel_id)
        logger.info(f"已删除渠道 {channel_id} 的 {deleted_count} 个任务")

        # 从配置中删除渠道
        if config.remove_custom_channel(channel_id):
            self.queue_tab.remove_custom_channel(channel_id)
            logger.info(f"已删除自定义渠道: {channel_id}")
        else:
            QMessageBox.warning(self, "删除失败", "删除渠道失败，请重试")

    def _on_clear_channel_tasks(self, channel):
        """清空指定渠道的所有任务"""
        try:
            # 1. 调用控制器清空
            deleted_count = self._scheduler_controller.clear_tasks_by_channel(channel)

            # 2. 清空UI显示
            widget = self.queue_tab.get_channel_widget(channel)
            if widget:
                widget.clear_tasks()

            # 3. 获取渠道显示名称
            channel_name = Channel.get_display_name(channel)

            # 4. 更新状态栏
            self.update_status_bar(f"已清空【{channel_name}】渠道的 {deleted_count} 个任务")

            # 5. 显示成功提示
            self._show_auto_close_message(
                "清空成功",
                f"已删除【{channel_name}】渠道的 {deleted_count} 个任务",
                QMessageBox.Information,
                timeout_ms=2000
            )

            logger.info(f"已清空渠道 {channel_name} 的 {deleted_count} 个任务")

            # 6. 刷新统计
            self._load_stats_data()
            self._refresh_next_task_hint()

        except Exception as e:
            logger.exception(f"清空渠道任务失败: {e}")
            QMessageBox.critical(self, "清空失败", f"清空任务失败: {str(e)}")

    def _on_clear_all_tasks(self):
        """清空所有渠道的所有任务"""
        try:
            # 1. 调用控制器清空
            deleted_count = self._scheduler_controller.clear_all_tasks()

            # 2. 清空所有UI显示
            for widget in self.queue_tab._channel_widgets.values():
                widget.clear_tasks()

            # 3. 更新状态栏
            self.update_status_bar(f"已清空全部 {deleted_count} 个任务", queue_count=0)

            # 4. 显示成功提示
            self._show_auto_close_message(
                "清空成功",
                f"已删除全部 {deleted_count} 个任务",
                QMessageBox.Information,
                timeout_ms=2000
            )

            logger.info(f"已清空全部 {deleted_count} 个任务")

            # 5. 刷新统计
            self._load_stats_data()
            self._refresh_next_task_hint()

        except Exception as e:
            logger.exception(f"清空全部任务失败: {e}")
            QMessageBox.critical(self, "清空失败", f"清空任务失败: {str(e)}")

    def _load_stats_data(self):
        """加载统计数据到统计页面"""
        try:
            from datetime import timedelta

            # 获取任务汇总（今日统计卡片）
            summary = self._db.get_task_summary()
            self.stats_tab.update_summary(summary)

            # 获取最近30天的每日统计
            daily_stats_list = []
            today = datetime.now().date()
            for i in range(30):
                stat_date = today - timedelta(days=29-i)
                daily_stats = self._db.get_daily_stats(stat_date)
                daily_stats_list.append(daily_stats)

            self.stats_tab.update_daily_stats(daily_stats_list)
            logger.debug(f"统计数据已加载: {len(daily_stats_list)} 天")

        except Exception as e:
            logger.warning(f"加载统计数据失败: {e}")

    def _update_time(self):
        """更新时间显示"""
        self.time_label.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def _show_window(self):
        """显示窗口"""
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.activateWindow()
        self.raise_()
        self.window_shown.emit()

    def _hide_window(self):
        """隐藏窗口到托盘"""
        self.hide()
        self.tray_icon.showMessage(
            "微信自动发布工具",
            "程序已最小化到系统托盘",
            QSystemTrayIcon.Information,
            TRAY_NOTIFICATION_DURATION_MS
        )
        self.window_hidden.emit()

    def _on_tray_activated(self, reason):
        """托盘图标激活"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self._hide_window()
            else:
                self._show_window()

    def _on_tray_pause(self, checked: bool):
        """托盘暂停切换"""
        if checked:
            self._on_pause_publishing()
        else:
            self._on_start_publishing()

    def _on_start_publishing(self, channel: Channel = None):
        """开始发布 - 启动调度器"""
        try:
            # 全局启动（托盘/菜单）
            if channel is None:
                self._scheduler_controller.start()

                self._is_publishing = True
                self.tray_pause_action.setChecked(False)
                self.queue_tab.set_publishing_state(True)

                self.show_tray_message("发布启动", "自动发布已开始运行")
                self._refresh_next_task_hint()
                return

            # 指定渠道启动
            self._scheduler_controller.start_channel(channel)
            self.queue_tab.set_publishing_state(channel, True)
            self._is_publishing = self._scheduler_controller.has_running_channels()
            self.tray_pause_action.setChecked(not self._is_publishing)

            channel_name = Channel.get_display_name(channel)
            self.show_tray_message("发布启动", f"{channel_name} 已开始运行")
            self._refresh_next_task_hint()

        except Exception as e:
            logger.exception(f"启动发布失败: {e}")
            QMessageBox.critical(self, "启动失败", f"无法启动自动发布: {str(e)}")

    def _on_pause_publishing(self, channel: Channel = None):
        """暂停发布 - 暂停调度器"""
        try:
            # 全局暂停（托盘/菜单）
            if channel is None:
                self._scheduler_controller.pause()

                self._is_publishing = False
                self.tray_pause_action.setChecked(True)
                self.queue_tab.set_publishing_state(False)

                self.show_tray_message("发布暂停", "自动发布已暂停")
                self._refresh_next_task_hint()
                return

            # 指定渠道暂停
            self._scheduler_controller.pause_channel(channel)
            self.queue_tab.set_publishing_state(channel, False)
            self._is_publishing = self._scheduler_controller.has_running_channels()
            self.tray_pause_action.setChecked(not self._is_publishing)

            channel_name = Channel.get_display_name(channel)
            self.show_tray_message("发布暂停", f"{channel_name} 已暂停")
            self._refresh_next_task_hint()

        except Exception as e:
            logger.exception(f"暂停发布失败: {e}")

    def _on_scheduler_status_changed(self, message: str):
        """调度器状态变更"""
        self.update_status_bar(message)

    def _on_queue_status_updated(self, _status: dict):
        """队列状态更新"""
        self._refresh_next_task_hint()

    def _on_scheduler_started(self):
        """调度器启动"""
        self.status_indicator.set_status("running")

    def _on_scheduler_paused(self):
        """调度器暂停"""
        self.status_indicator.set_status("paused")

    def _execute_scheduled_task(self, task: Task):
        """调度器执行任务的回调（在调度器线程中调用）"""
        logger.info(f"调度器触发任务执行: {task.content_code}")

        # 设置任务执行器的文件夹路径
        folder_path = task.source_folder or self._import_handler.get_folder_path()
        self._task_executor.set_folder_path(folder_path)

        # 直接从 task 对象构建 Content（图片路径已持久化到数据库）
        content = Content(
            content_code=task.content_code,
            text=task.text,
            image_paths=task.image_paths,  # 从数据库读取的图片路径
            channel=task.channel,
            product_name=task.product_name,
            category=task.category,
            product_link=task.product_link,
        )
        logger.info(f"任务 {task.content_code} 图片数量: {len(task.image_paths)}")

        try:
            # 使用任务执行器执行任务
            if task.channel == Channel.moment:
                result = self._task_executor.execute_moment_task(task, content)
            else:
                result = self._task_executor.execute_group_task(task, content)

            # 更新任务状态
            if result.is_success:
                self._scheduler_controller.mark_task_success(task)
            else:
                self._scheduler_controller.mark_task_failed(task, result.message)

            # 通知主线程更新UI
            self.scheduled_task_finished_signal.emit(task, result)

        except Exception as e:
            logger.exception(f"调度任务执行异常: {e}")
            self._scheduler_controller.mark_task_failed(task, str(e))

    def _on_scheduled_task_finished(self, task: Task, result: SendResult):
        """调度任务完成后更新UI（主线程）"""
        if result.is_success:
            self._today_success += 1
            self.update_status_bar(
                f"任务 {task.content_code} 执行成功",
                success_count=self._today_success
            )
            self.show_tray_message(
                "任务完成",
                f"任务 [{task.content_code}] 发布成功"
            )

            # 语音提醒
            self._notify_voice_complete(task)
        else:
            self.update_status_bar(f"任务 {task.content_code} 执行失败: {result.message}")
            self.show_tray_message(
                "任务失败",
                f"任务 [{task.content_code}] 发布失败",
                QSystemTrayIcon.Warning
            )

        status_text = "完成" if result.is_success else "失败"
        channel_name = Channel.get_display_name(task.channel)
        self.queue_tab.update_progress(
            f"{task.content_code} | {channel_name} | {status_text}",
            100
        )
        QTimer.singleShot(2000, self.queue_tab.clear_progress)

        # 刷新队列显示
        self.queue_tab.update_task_by_code(
            task.content_code,
            task.status,
            task.channel,
            task.executed_time
        )
        self._refresh_next_task_hint()

    def _on_scheduler_task_complete(self, task: Task):
        """调度器任务完成回调"""
        logger.info(f"调度器任务完成: {task.content_code}")

    def _on_scheduler_task_failed(self, task: Task, error: str):
        """调度器任务失败回调"""
        logger.error(f"调度器任务失败: {task.content_code}, 错误: {error}")

    def _format_next_task_hint(self, preview: dict) -> str:
        """格式化下一任务提示"""
        task = preview.get("task") if preview else None
        if not task:
            reason = preview.get("reason") if preview else None
            return f"下一任务: {reason or '暂无任务'}"

        channel_name = Channel.get_display_name(task.channel)
        scheduled_text = task.scheduled_time.strftime("%Y-%m-%d %H:%M") if task.scheduled_time else "-"
        next_time = preview.get("next_time") if preview else None
        if isinstance(next_time, datetime):
            next_time_text = next_time.strftime("%Y-%m-%d %H:%M")
        elif task.scheduled_time:
            next_time_text = scheduled_text
        else:
            next_time_text = "-"
        status_text = STATUS_NAMES.get(task.status, task.status.value)
        hint = (
            f"下一任务: {task.content_code} | "
            f"渠道: {channel_name} | "
            f"排期: {scheduled_text} | "
            f"发布时间: {next_time_text} | "
            f"状态: {status_text}"
        )
        reason = preview.get("reason")
        if reason:
            hint += f" | 提醒: {reason}"
        return hint

    def _refresh_next_task_hint(self):
        """刷新下一任务提示与高亮"""
        try:
            queue_manager = self._scheduler_controller.get_queue_manager()
            preview = queue_manager.get_next_task_preview()
        except Exception as exc:
            logger.exception(f"获取下一任务失败: {exc}")
            return

        hint = self._format_next_task_hint(preview)
        self.queue_tab.set_next_task_hint(hint)
        self.next_task_label.setText(hint)
        self.next_task_label.setToolTip(hint)
        self.queue_tab.set_next_task_highlight(preview.get("task"))

    def _on_cancel_task(self, task: Task):
        """取消任务"""
        logger.info(f"取消任务: {task.content_code}")

        try:
            # 更新任务状态为取消
            task.mark_cancelled()
            self._db.update_task(task)

            # 从队列中移除
            self._scheduler_controller.remove_task(task.id, task.channel)

            # 更新UI
            self.queue_tab.update_task_by_code(task.content_code, task.status, task.channel)

            self.update_status_bar(f"已取消任务: {task.content_code}")
            logger.info(f"任务已取消: {task.content_code}")
            self._refresh_next_task_hint()

        except Exception as e:
            logger.exception(f"取消任务失败: {e}")
            QMessageBox.warning(self, "取消失败", f"取消任务失败: {str(e)}")

    def _on_tasks_reordered(self, tasks: list):
        """处理任务顺序变更"""
        logger.info(f"任务顺序变更，共 {len(tasks)} 个任务")
        try:
            for task in tasks:
                self._db.update_task(task)
            logger.info("任务顺序已保存")
            self._refresh_next_task_hint()
        except Exception as e:
            logger.exception(f"保存任务顺序失败: {e}")

    def _on_execute_task(self, task: Task):
        """执行单个任务"""
        logger.info(f"开始执行任务: {task.content_code}")

        # 获取任务对应的内容
        content = self._import_handler.get_content(task.content_code)
        if not content:
            # 如果没有内容，创建一个空内容
            content = Content(
                content_code=task.content_code,
                text="",
                image_paths=[],
                channel=task.channel
            )
            logger.warning(f"任务 {task.content_code} 没有找到对应的内容数据")

        # 执行前配置检查提醒（不阻断执行）
        self._check_task_config_warning(task, content)

        # 更新任务状态并保存到数据库
        task.status = TaskStatus.running
        self._db.update_task(task)

        # 更新 UI 状态
        self._executing_task = task
        self.status_indicator.set_status("running")
        self.update_status_bar(f"正在执行: {task.content_code}")
        self.queue_tab.update_task_status(task.id if task.id else 0, task.status)

        # 设置任务执行器的文件夹路径
        folder_path = task.source_folder or self._import_handler.get_folder_path()
        self._task_executor.set_folder_path(folder_path)

        # 使用任务执行器异步执行
        self._task_executor.execute_task_async(task, content)

    def _on_edit_task_schedule(self, task: Task):
        """更新任务排期"""
        try:
            if task.id:
                self._db.update_task(task)
            else:
                logger.warning(f"任务 {task.content_code} 没有 id，无法更新排期到数据库")

            # 先从队列中移除旧任务，再重新添加（确保排期时间更新生效）
            if task.id:
                self._scheduler_controller.remove_task(task.id, task.channel)
            self._scheduler_controller.add_task(task)

            # 刷新 UI
            self.queue_tab.update_task_by_code(task.content_code, task.status, task.channel)

            time_str = task.scheduled_time.strftime("%Y-%m-%d %H:%M") if task.scheduled_time else "未设置"
            self.update_status_bar(f"任务 {task.content_code} 排期已更新: {time_str}")
            logger.info(f"任务 {task.content_code} 排期已更新: {time_str}")
            self._refresh_next_task_hint()

        except Exception as e:
            logger.exception(f"更新任务排期失败: {e}")
            QMessageBox.warning(self, "排期更新失败", f"排期更新失败: {str(e)}")

    def _on_task_completed(self, task: Task, result: SendResult):
        """任务完成回调"""
        logger.info(
            f"任务完成回调: code={task.content_code}, id={task.id}, status={task.status.value}"
        )
        self._executing_task = None

        if result.is_success:
            task.mark_success(screenshot_path=result.screenshot_path if hasattr(result, 'screenshot_path') else None)
            self._today_success += 1
            self.status_indicator.set_status("ready")
            self.update_status_bar(f"任务 {task.content_code} 执行成功", success_count=self._today_success)

            # 群渠道：延迟显示成功提示，等所有流程完成后再显示
            # 非群渠道：立即显示成功提示
            if task.channel not in (Channel.agent_group, Channel.customer_group):
                self._show_auto_close_message(
                    "执行成功",
                    f"任务 [{task.content_code}] 发布成功！\n"
                    f"耗时: {result.duration:.1f} 秒",
                    QMessageBox.Information,
                    timeout_ms=3000
                )

            # 群渠道的小程序转发/附加消息已在群发流程内逐群处理

            # 语音提醒
            self._notify_voice_complete(task)
        else:
            task.mark_failed(result.message)
            self.status_indicator.set_status("error")
            self.update_status_bar(f"任务 {task.content_code} 执行失败")

            self._show_auto_close_message(
                "执行失败",
                f"任务 [{task.content_code}] 发布失败\n\n"
                f"错误信息: {result.message}",
                QMessageBox.Warning,
                timeout_ms=3000
            )

        status_text = "完成" if result.is_success else "失败"
        channel_name = Channel.get_display_name(task.channel)
        self.queue_tab.update_progress(
            f"{task.content_code} | {channel_name} | {status_text}",
            100
        )
        QTimer.singleShot(2000, self.queue_tab.clear_progress)

        # 保存到数据库
        if task.id:
            self._db.update_task(task)
            logger.info(f"任务 {task.content_code} (id={task.id}) 状态已保存: {task.status.value}")
        else:
            logger.warning(f"任务 {task.content_code} 没有 id，无法保存到数据库")

        # 刷新队列显示
        self.queue_tab.update_task_by_code(
            task.content_code,
            task.status,
            task.channel,
            task.executed_time
        )

    def _on_task_waiting(self, task: Task, reason: str):
        """任务排队/等待锁提示"""
        channel_name = Channel.get_display_name(task.channel)
        self.update_status_bar(
            f"排队中: {task.content_code} | 渠道: {channel_name} | {reason}"
        )

        # 刷新队列显示
        self.queue_tab.update_task_by_code(task.content_code, task.status, task.channel)
        logger.info(f"任务 {task.content_code} 执行完成: {task.status.value}")

        # 刷新统计数据
        self._load_stats_data()
        self._refresh_next_task_hint()

    def _on_task_progress(self, task: Task, text: str, percent: int):
        """任务进度回调"""
        self.queue_tab.update_progress(text, percent)

    def _handle_group_post_publish(self, task: Task, result: SendResult) -> bool:
        """群渠道发送完成后执行小程序流程和额外消息"""
        if task.channel not in (Channel.agent_group, Channel.customer_group):
            return True
        if not result.is_success:
            return False

        import time

        agent_group_start_time = time.time()  # 记录开始时间，用于计算总耗时

        from core.wechat_controller import get_wechat_controller
        from core.group_sender import get_group_sender

        controller = get_wechat_controller()

        group_names = self._get_channel_group_names(task.channel)
        if not group_names:
            group_names = get_config_manager().get(
                f"schedule.channels.{task.channel.value}.global_group_names", []
            )
        group_name = group_names[0] if group_names else None

        content = self._import_handler.get_content(task.content_code)
        has_product_link = bool(task.product_link) or (content and content.product_link)
        forward_ok = True
        if has_product_link:
            forward_ok = controller.open_product_forward(task.content_code, group_name, task.channel)
            if not forward_ok:
                logger.warning(f"任务 {task.content_code} 小程序转发失败")
        else:
            logger.info(f"任务 {task.content_code} 没有产品链接，跳过小程序转发")

        # 发送额外消息（不受产品链接影响）
        extra_message = self._task_executor.get_extra_message(task.channel)
        if extra_message:
            logger.info("发送额外消息")
            sender = get_group_sender()
            sender.send_text_in_current_chat(extra_message)
            logger.info("额外消息发送完成")

        if not forward_ok:
            self._show_auto_close_message(
                "小程序转发失败",
                f"任务 [{task.content_code}] 已完成群发，但小程序转发失败。\n"
                "请检查坐标配置后重试。",
                QMessageBox.Warning,
                timeout_ms=4000
            )
            return False

        # 群渠道所有流程完成后，显示成功提示
        # 计算总耗时：原始发送耗时 + 小程序转发和附加消息耗时
        total_duration = result.duration + (time.time() - agent_group_start_time)
        self._show_auto_close_message(
            "执行成功",
            f"任务 [{task.content_code}] 发布成功！\n"
            f"耗时: {total_duration:.1f} 秒",
            QMessageBox.Information,
            timeout_ms=3000
        )

        # 群渠道语音提醒（根据渠道动态配置）
        self._notify_voice_complete(task)

        return True

    def _notify_voice_complete(self, task: Task) -> None:
        """任务完成后的语音提醒"""
        if isinstance(task.channel, Channel):
            channel_value = task.channel.value
            queue_channel = task.channel
        else:
            channel_value = str(task.channel)
            try:
                queue_channel = Channel(channel_value)
            except ValueError:
                queue_channel = None

        if channel_value == Channel.moment.value:
            voice_enabled = get_config_manager().get("voice.moment_complete_enabled", False)
            if voice_enabled:
                from services.voice_notifier import get_voice_notifier
                remaining = (
                    self._scheduler_controller.get_queue_size(queue_channel)
                    if queue_channel
                    else 0
                )
                get_voice_notifier().announce_moment_complete(remaining, task.content_code)
            return

        voice_key = f"voice.{channel_value}_complete_enabled"
        voice_enabled = get_config_manager().get(voice_key, None)
        if voice_enabled is None:
            voice_enabled = get_config_manager().get("voice.customer_group_complete_enabled", False)
        if not voice_enabled:
            return

        from services.voice_notifier import get_voice_notifier
        remaining = self._scheduler_controller.get_queue_size(queue_channel) if queue_channel else 0
        if channel_value == Channel.agent_group.value:
            get_voice_notifier().announce_group_complete(remaining, task.content_code)
        else:
            get_voice_notifier().announce_customer_group_complete(remaining, task.content_code)

    def _on_import_file(self, folder_path: str):
        """处理导入文件夹"""
        logger.info(f"导入文件夹: {folder_path}")

        # 使用导入处理器导入
        success, result = self._import_handler.import_folder(folder_path)

        if not success:
            # 显示错误信息
            error_messages = [f"行 {e.row}: {e.message}" for e in result.errors[:10]] if result.errors else []
            if len(result.errors) > 10:
                error_messages.append(f"... 还有 {len(result.errors) - 10} 个错误")

            if error_messages:
                QMessageBox.critical(
                    self,
                    "导入失败",
                    f"解析文件失败:\n\n" + "\n".join(error_messages)
                )
            else:
                QMessageBox.warning(
                    self,
                    "导入警告",
                    "文件中没有有效的任务数据"
                )

            self.update_status_bar("导入失败")
            return

        # 导入成功，由 _on_import_completed 处理后续逻辑

    def _on_import_completed(self, result):
        """导入完成回调"""
        # 保存任务到数据库并加入调度队列
        # Assign priority by channel based on list order (top to bottom).
        channel_counts = {}
        for task in result.tasks:
            channel_counts[task.channel] = channel_counts.get(task.channel, 0) + 1

        channel_offsets = {channel: 0 for channel in channel_counts}
        for task in result.tasks:
            channel = task.channel
            index = channel_offsets[channel]
            total = channel_counts[channel]
            task.priority = total - index
            channel_offsets[channel] = index + 1

        saved_count, total = self._import_handler.save_tasks_to_db(result.tasks)

        # 将任务添加到调度队列
        queued_count = 0
        for task in result.tasks:
            if task.id and self._scheduler_controller.add_task(task):
                queued_count += 1

        logger.info(f"保存 {saved_count}/{total} 个任务到数据库，{queued_count} 个加入调度队列")

        # 加载任务到UI队列
        self.queue_tab.load_tasks(result.tasks)

        # 显示导入结果
        message = f"成功导入 {result.valid_rows} 个任务"

        # 如果有警告，也显示
        if result.has_warnings:
            warning_count = len(result.warnings)
            message += f" (有 {warning_count} 个警告)"

            # 在日志中记录警告详情
            for w in result.warnings[:20]:
                logger.warning(f"导入警告 - 行 {w.row}, 列 {w.column}: {w.message}")

        self.update_status_bar(message, queue_count=len(result.tasks))
        self._refresh_next_task_hint()

        # 显示成功提示
        QMessageBox.information(
            self,
            "导入成功",
            f"成功导入 {result.valid_rows} 个任务\n"
            f"总行数: {result.total_rows}\n"
            f"有效行数: {result.valid_rows}" +
            (f"\n警告数: {len(result.warnings)}" if result.has_warnings else "")
        )

        logger.info(f"导入完成: {result.valid_rows}/{result.total_rows} 任务")

        # 刷新统计数据
        self._load_stats_data()

    def _on_import_failed(self, error_message: str):
        """导入失败回调"""
        logger.error(f"导入失败: {error_message}")

    def _on_quit(self):
        """退出程序"""
        self._close_to_tray = False
        self.quit_requested.emit()
        self.close()

    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于",
            "<h3>微信自动发布工具</h3>"
            "<p>版本: 1.0.0</p>"
            "<p>用于自动化发布微信朋友圈和群发消息</p>"
            "<hr>"
            "<p>技术栈: Python + PySide6 + SQLite + uiautomation</p>"
        )

    # 公共接口

    def update_status_bar(self, message: str = None, queue_count: int = None,
                          success_count: int = None):
        """
        更新状态栏

        Args:
            message: 状态消息
            queue_count: 队列数量
            success_count: 今日成功数
        """
        if message is not None:
            self.status_message.setText(message)

        if queue_count is not None:
            self._queue_count = queue_count
            self.queue_label.setText(f"队列: {queue_count}")

        if success_count is not None:
            self._today_success = success_count
            self.success_label.setText(f"今日: {success_count}")

    def set_status(self, status: str):
        """
        设置状态指示器

        Args:
            status: idle/ready/running/paused/error
        """
        self.status_indicator.set_status(status)

    def show_tray_message(self, title: str, message: str,
                          icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.Information,
                          duration: int = TRAY_NOTIFICATION_DURATION_MS):
        """
        显示托盘通知

        Args:
            title: 标题
            message: 消息内容
            icon: 图标类型
            duration: 显示时长（毫秒）
        """
        self.tray_icon.showMessage(title, message, icon, duration)

    def closeEvent(self, event: QCloseEvent):
        """关闭事件处理"""
        if self._close_to_tray and self.tray_icon.isVisible():
            event.ignore()
            self._hide_window()
        else:
            # 确认退出
            if self._is_publishing:
                reply = QMessageBox.question(
                    self,
                    "确认退出",
                    "当前正在发布任务，确定要退出吗？\n退出后任务将会中断。",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    event.ignore()
                    return

            # 停止调度器
            if self._scheduler_controller.is_running():
                logger.info("正在停止调度器...")
                self._scheduler_controller.stop()

            # 清理资源
            self.tray_icon.hide()
            self._time_timer.stop()
            event.accept()
            logger.info("主窗口关闭")


# 程序入口点
if __name__ == "__main__":
    import sys
    import os

    # 添加项目根目录到路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("微信自动发布工具")
    app.setOrganizationName("WeChatPublisher")

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    # 运行事件循环
    sys.exit(app.exec())
