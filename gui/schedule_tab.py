"""
任务完成列表标签页模块

功能:
- 日期选择器选择日期
- 显示指定日期已完成的任务列表
- 任务统计信息
"""

from datetime import datetime, date
from typing import List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QDateEdit, QMessageBox
)
from PySide6.QtCore import QDate, Signal
from PySide6.QtGui import QColor, QBrush

from data.database import get_database
from models.task import Task
from models.enums import TaskStatus


class TaskListItem(QListWidgetItem):
    """任务列表项"""

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self._update_display()

    def _update_display(self) -> None:
        """更新显示"""
        time_str = ""
        if self.task.executed_time:
            time_str = self.task.executed_time.strftime("%H:%M")
        elif self.task.scheduled_time:
            time_str = self.task.scheduled_time.strftime("%H:%M")

        status_icons = {
            TaskStatus.pending: "[待发布]",
            TaskStatus.scheduled: "[已排期]",
            TaskStatus.running: "[执行中]",
            TaskStatus.success: "[已完成]",
            TaskStatus.failed: "[失败]",
            TaskStatus.paused: "[暂停]",
            TaskStatus.cancelled: "[取消]",
            TaskStatus.skipped: "[跳过]",
        }
        status_str = status_icons.get(self.task.status, "[未知]")

        text = f"{time_str} {status_str} {self.task.content_code}"
        if self.task.product_name:
            text += f" - {self.task.product_name}"

        self.setText(text)

        # 设置颜色
        color_map = {
            TaskStatus.success: QColor("#27ae60"),
            TaskStatus.failed: QColor("#e74c3c"),
            TaskStatus.running: QColor("#3498db"),
            TaskStatus.paused: QColor("#f39c12"),
            TaskStatus.cancelled: QColor("#95a5a6"),
        }
        if self.task.status in color_map:
            self.setForeground(QBrush(color_map[self.task.status]))


class ScheduleTab(QWidget):
    """任务完成列表标签页"""

    # 信号
    schedule_changed = Signal()  # 保持兼容

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = get_database()
        self._selected_date = date.today()
        self._init_ui()
        self._load_completed_tasks()

    def _init_ui(self) -> None:
        """初始化界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # ========== 顶部: 日期选择器 ==========
        date_panel = QWidget()
        date_layout = QHBoxLayout(date_panel)
        date_layout.setContentsMargins(0, 0, 0, 0)

        # 日期选择标签
        date_label = QLabel("选择日期:")
        date_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        date_layout.addWidget(date_label)

        # 日期选择器
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setMinimumWidth(150)
        self.date_edit.dateChanged.connect(self._on_date_changed)
        self.date_edit.setStyleSheet("""
            QDateEdit {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 14px;
            }
            QDateEdit:focus {
                border-color: #90CAF9;
            }
            QDateEdit::drop-down {
                border: none;
                width: 20px;
            }
            QDateEdit QAbstractItemView {
                background-color: #FFFFFF;
                color: #212121;
                selection-background-color: #BBDEFB;
            }
        """)
        date_layout.addWidget(self.date_edit)

        # 快捷按钮
        self.btn_today = QPushButton("今天")
        self.btn_today.setFixedWidth(60)
        self.btn_today.clicked.connect(self._go_today)
        self.btn_today.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        date_layout.addWidget(self.btn_today)

        self.btn_prev = QPushButton("<")
        self.btn_prev.setFixedWidth(40)
        self.btn_prev.clicked.connect(self._go_prev_day)
        self.btn_prev.setStyleSheet(self.btn_today.styleSheet())
        date_layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton(">")
        self.btn_next.setFixedWidth(40)
        self.btn_next.clicked.connect(self._go_next_day)
        self.btn_next.setStyleSheet(self.btn_today.styleSheet())
        date_layout.addWidget(self.btn_next)

        # 日期显示标签
        self.date_display = QLabel()
        self.date_display.setStyleSheet("font-size: 16px; font-weight: bold; color: #90CAF9;")
        date_layout.addWidget(self.date_display)

        date_layout.addStretch()

        # 刷新按钮
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.setFixedWidth(60)
        self.btn_refresh.clicked.connect(self._load_completed_tasks)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        date_layout.addWidget(self.btn_refresh)

        main_layout.addWidget(date_panel)

        # ========== 中间: 任务列表 ==========
        list_group = QGroupBox("已完成任务")
        list_group.setStyleSheet("""
            QGroupBox {
                color: #90CAF9;
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #333333;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        list_layout = QVBoxLayout(list_group)

        self.task_list = QListWidget()
        self.task_list.setAlternatingRowColors(True)
        self.task_list.itemDoubleClicked.connect(self._on_task_double_clicked)
        self.task_list.setStyleSheet("""
            QListWidget {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: 1px solid #333333;
                border-radius: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2D2D2D;
            }
            QListWidget::item:alternate {
                background-color: #252525;
            }
            QListWidget::item:selected {
                background-color: #37474F;
            }
            QListWidget::item:hover {
                background-color: #2D2D2D;
            }
        """)
        list_layout.addWidget(self.task_list)

        main_layout.addWidget(list_group, 1)

        # ========== 底部: 统计信息 ==========
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("""
            background-color: #2D2D2D;
            color: #B0B0B0;
            padding: 12px;
            border-radius: 6px;
            font-size: 13px;
        """)
        main_layout.addWidget(self.stats_label)

        # 初始化显示
        self._update_date_display()

    def _on_date_changed(self, qdate: QDate) -> None:
        """日期变更事件"""
        self._selected_date = qdate.toPython()
        self._update_date_display()
        self._load_completed_tasks()

    def _go_today(self) -> None:
        """跳转到今天"""
        self.date_edit.setDate(QDate.currentDate())

    def _go_prev_day(self) -> None:
        """前一天"""
        current = self.date_edit.date()
        self.date_edit.setDate(current.addDays(-1))

    def _go_next_day(self) -> None:
        """后一天"""
        current = self.date_edit.date()
        self.date_edit.setDate(current.addDays(1))

    def _update_date_display(self) -> None:
        """更新日期显示"""
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekday_names[self._selected_date.weekday()]
        self.date_display.setText(
            f"{self._selected_date.strftime('%Y年%m月%d日')} {weekday}"
        )

    def _load_completed_tasks(self) -> None:
        """加载已完成的任务"""
        # 从数据库获取指定日期的已完成任务
        tasks = self.db.list_tasks(
            scheduled_date=self._selected_date,
            status=TaskStatus.success,
            limit=500
        )

        # 按执行时间排序
        tasks.sort(key=lambda t: t.executed_time or t.scheduled_time or datetime.max)

        # 更新列表
        self.task_list.clear()
        for task in tasks:
            item = TaskListItem(task)
            self.task_list.addItem(item)

        # 更新统计
        self._update_stats(tasks)

    def _update_stats(self, tasks: List[Task]) -> None:
        """更新统计信息"""
        total = len(tasks)

        # 按渠道统计
        channel_stats = {}
        for task in tasks:
            channel = task.channel.value if task.channel else "未知"
            channel_stats[channel] = channel_stats.get(channel, 0) + 1

        stats_text = f"完成任务: {total} 个"
        if channel_stats:
            stats_text += "  |  "
            channel_parts = [f"{ch}: {cnt}" for ch, cnt in channel_stats.items()]
            stats_text += "  ".join(channel_parts)

        self.stats_label.setText(stats_text)

    def _on_task_double_clicked(self, item: QListWidgetItem) -> None:
        """任务双击事件"""
        if isinstance(item, TaskListItem):
            task = item.task
            executed_str = task.executed_time.strftime("%Y-%m-%d %H:%M:%S") if task.executed_time else "未执行"
            QMessageBox.information(
                self,
                "任务详情",
                f"内容编码: {task.content_code}\n"
                f"产品名称: {task.product_name or '无'}\n"
                f"渠道: {task.channel.value if task.channel else '未知'}\n"
                f"状态: {task.status.value}\n"
                f"计划时间: {task.scheduled_time}\n"
                f"执行时间: {executed_str}"
            )

    def refresh(self) -> None:
        """刷新视图"""
        self._load_completed_tasks()
