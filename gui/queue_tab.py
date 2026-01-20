"""
发布队列标签页

提供任务队列的可视化管理，支持多渠道独立队列、拖拽排序和实时状态更新。
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton,
    QComboBox, QLabel, QMenu, QFileDialog, QMessageBox,
    QHeaderView, QAbstractItemView, QStyledItemDelegate,
    QStyleOptionViewItem, QApplication, QFrame, QDialog,
    QDialogButtonBox, QFormLayout, QTabWidget, QSpinBox, QStackedWidget,
    QSizePolicy, QProgressBar,
    QDateEdit, QTimeEdit, QPlainTextEdit, QLineEdit, QInputDialog
)
from PySide6.QtCore import (
    Qt, Signal, QAbstractTableModel, QModelIndex, QMimeData,
    QByteArray, QDataStream, QIODevice, QSortFilterProxyModel,
    QDate, QTime, QTimer
)
from PySide6.QtGui import QColor, QPainter, QDrag, QPixmap

from models.task import Task
from models.enums import TaskStatus, Channel
from .styles import (
    STATUS_COLORS, STATUS_NAMES, STATUS_ICONS,
    TABLE_STYLE, BUTTON_STYLE, BUTTON_SECONDARY_STYLE,
    BUTTON_SUCCESS_STYLE, BUTTON_DANGER_STYLE, INPUT_STYLE
)

# ============================================================
# 队列标签页常量
# ============================================================

# 拖拽预览相关
DRAG_PREVIEW_WIDTH = 400
DRAG_PREVIEW_COLUMN_WIDTH = 100
DRAG_TEXT_MAX_LENGTH = 15

# 表格列宽
COLUMN_WIDTH_STATUS = 90
COLUMN_WIDTH_CONTENT_CODE = 120
COLUMN_WIDTH_PRODUCT_NAME = 150
COLUMN_WIDTH_TEXT = 200
COLUMN_WIDTH_CHANNEL = 80
COLUMN_WIDTH_GROUP_NAME = 150
COLUMN_WIDTH_SCHEDULED_TIME = 160
COLUMN_WIDTH_EXECUTED_TIME = 180
COLUMN_WIDTH_RETRY = 70

# 对话框尺寸
DIALOG_MIN_WIDTH = 450
DIALOG_MIN_WIDTH_LARGE = 460

# 文本截断长度
TEXT_DISPLAY_MAX_LENGTH = 50
TEXT_PREVIEW_MAX_LENGTH = 100

# 布局间距
LAYOUT_SPACING_SMALL = 10
LAYOUT_SPACING_MEDIUM = 12
LAYOUT_SPACING_LARGE = 16

# 控件最小宽度
INPUT_MIN_WIDTH_SMALL = 50
INPUT_MIN_WIDTH_MEDIUM = 70
INPUT_MIN_WIDTH_LARGE = 90
INPUT_MIN_WIDTH_DATE = 120
INPUT_MIN_WIDTH_GROUP_BTN = 120

# 表格行高
TABLE_ROW_HEIGHT = 56
TABLE_MIN_SECTION_SIZE = 50

# 添加按钮尺寸
ADD_CHANNEL_BTN_SIZE = 28
EXTRA_MESSAGE_DEBOUNCE_MS = 400


class DraggableTableView(QTableView):
    """
    支持行拖拽排序的表格视图

    完全手动实现拖拽，避免 Qt 内置拖拽的数据丢失问题
    """

    row_moved = Signal(int, int)  # source_row, target_row

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_row = -1
        self._drag_start_pos = None

        # 禁用 Qt 内置拖拽
        self.setDragEnabled(False)
        self.setAcceptDrops(False)
        self.setDragDropMode(QAbstractItemView.NoDragDrop)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                self._drag_row = index.row()
                self._drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_row >= 0 and self._drag_start_pos:
            diff = event.position().toPoint() - self._drag_start_pos
            if diff.manhattanLength() > QApplication.startDragDistance():
                self._start_drag()
        super().mouseMoveEvent(event)

    def _start_drag(self):
        """开始拖拽"""
        if self._drag_row < 0:
            return

        # 获取源行在源模型中的实际行号
        proxy_model = self.model()
        if hasattr(proxy_model, 'mapToSource'):
            source_index = proxy_model.mapToSource(proxy_model.index(self._drag_row, 0))
            actual_row = source_index.row()
        else:
            actual_row = self._drag_row

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(actual_row))
        drag.setMimeData(mime_data)

        # 创建拖拽预览图
        row_height = self.rowHeight(self._drag_row)
        width = min(self.viewport().width(), DRAG_PREVIEW_WIDTH)
        pixmap = QPixmap(width, row_height)
        pixmap.fill(QColor(60, 60, 60))

        painter = QPainter(pixmap)
        painter.setPen(QColor(200, 200, 200))
        model = self.model()
        x = 5
        for col in range(min(model.columnCount(), 4)):
            index = model.index(self._drag_row, col)
            text = str(model.data(index, Qt.DisplayRole) or "")
            if len(text) > DRAG_TEXT_MAX_LENGTH:
                text = text[:DRAG_TEXT_MAX_LENGTH] + "..."
            painter.drawText(x, row_height // 2 + 5, text)
            x += DRAG_PREVIEW_COLUMN_WIDTH
        painter.end()

        drag.setPixmap(pixmap)

        # 执行拖拽
        self.setAcceptDrops(True)
        drag.exec(Qt.MoveAction)
        self.setAcceptDrops(False)

        self._drag_row = -1
        self._drag_start_pos = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            # 更新选中行以显示插入位置
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                self.selectRow(index.row())

    def dropEvent(self, event):
        """处理放置"""
        if not event.mimeData().hasText():
            event.ignore()
            return

        try:
            source_row = int(event.mimeData().text())
        except:
            event.ignore()
            return

        # 获取目标位置
        pos = event.position().toPoint()
        target_index = self.indexAt(pos)

        if not target_index.isValid():
            target_row = self.model().rowCount()
        else:
            target_row = target_index.row()
            # 检查鼠标在目标行的上半部还是下半部
            rect = self.visualRect(target_index)
            if pos.y() > rect.center().y():
                target_row += 1

        # 转换代理模型行号到源模型行号
        proxy_model = self.model()
        if hasattr(proxy_model, 'mapToSource'):
            if target_row < proxy_model.rowCount():
                target_index = proxy_model.mapToSource(proxy_model.index(target_row, 0))
                actual_target = target_index.row()
            else:
                actual_target = proxy_model.sourceModel().rowCount()
        else:
            actual_target = target_row

        # 发出信号通知移动
        if source_row != actual_target and source_row + 1 != actual_target:
            self.row_moved.emit(source_row, actual_target)

        event.acceptProposedAction()

    def mouseReleaseEvent(self, event):
        self._drag_row = -1
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)


class TaskTableModel(QAbstractTableModel):
    """
    任务表格模型

    使用 Model-View 模式管理任务数据
    """

    COLUMNS = [
        ("status", "状态", COLUMN_WIDTH_STATUS),
        ("content_code", "文案编号", COLUMN_WIDTH_CONTENT_CODE),
        ("product_name", "产品名称", COLUMN_WIDTH_PRODUCT_NAME),
        ("text", "文案内容", COLUMN_WIDTH_TEXT),
        ("channel", "渠道", COLUMN_WIDTH_CHANNEL),
        ("group_name", "群名", COLUMN_WIDTH_GROUP_NAME),
        ("scheduled_time", "排期时间", COLUMN_WIDTH_SCHEDULED_TIME),
        ("executed_time", "执行时间", COLUMN_WIDTH_EXECUTED_TIME),
        ("retry_count", "重试", COLUMN_WIDTH_RETRY),
    ]

    # 信号
    dataChanged_custom = Signal(int, TaskStatus)  # task_id, new_status
    order_changed = Signal(list)  # 拖拽重排后发送任务列表

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: list[Task] = []
        self._next_task_id: Optional[int] = None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._tasks)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._tasks):
            return None

        task = self._tasks[index.row()]
        col_key = self.COLUMNS[index.column()][0]

        if role == Qt.DisplayRole:
            return self._get_display_value(task, col_key)

        elif role == Qt.TextAlignmentRole:
            if col_key in ("status", "channel", "retry_count"):
                return Qt.AlignCenter
            return Qt.AlignVCenter | Qt.AlignLeft

        elif role == Qt.ForegroundRole:
            if col_key == "status":
                color = STATUS_COLORS.get(task.status, "#9E9E9E")
                return QColor(color)

        elif role == Qt.BackgroundRole:
            if task.status == TaskStatus.running:
                return QColor("#FFF8E1")  # 浅黄背景
            elif task.status == TaskStatus.failed:
                return QColor("#FFEBEE")  # 浅红背景
            elif self._next_task_id and task.id == self._next_task_id:
                return QColor("#FFFDE7")  # 下一任务高亮

        elif role == Qt.UserRole:
            # 返回任务对象
            return task

        return None

    def _get_display_value(self, task: Task, col_key: str) -> str:
        """获取显示值"""
        if col_key == "status":
            icon = STATUS_ICONS.get(task.status, "")
            name = STATUS_NAMES.get(task.status, task.status.value)
            return f"{icon} {name}"

        elif col_key == "channel":
            return Channel.get_display_name(task.channel)

        elif col_key == "scheduled_time":
            if task.scheduled_time:
                return task.scheduled_time.strftime("%Y-%m-%d %H:%M")
            return "-"

        elif col_key == "executed_time":
            if task.executed_time:
                return task.executed_time.strftime("%Y-%m-%d %H:%M:%S")
            return "-"

        elif col_key == "retry_count":
            return f"{task.retry_count}/{task.max_retry}"

        elif col_key == "group_name":
            return task.group_name or "-"

        elif col_key == "text":
            # 文案内容：截断显示 + #产品名称 #分类
            text = task.text or ""
            if len(text) > TEXT_DISPLAY_MAX_LENGTH:
                text = text[:TEXT_DISPLAY_MAX_LENGTH] + "..."

            # 添加 #产品名称 #分类 标签
            tags = []
            if task.product_name:
                tags.append(f"#{task.product_name}")
            if task.category:
                tags.append(f"#{task.category}")

            if tags:
                return f"{text or '-'}\n{' '.join(tags)}"
            return text or "-"

        return getattr(task, col_key, "")

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section][1]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        default_flags = super().flags(index)
        if index.isValid():
            return default_flags | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        return default_flags | Qt.ItemIsDropEnabled

    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.MoveAction

    def mimeTypes(self) -> list[str]:
        return ["application/x-task-row"]

    def canDropMimeData(self, data: QMimeData, action: Qt.DropAction,
                        row: int, column: int, parent: QModelIndex) -> bool:
        """检查是否可以放置"""
        return data.hasFormat("application/x-task-row")

    def mimeData(self, indexes: list[QModelIndex]) -> QMimeData:
        """生成拖拽数据"""
        print(f"[TaskTableModel] mimeData called, indexes={[i.row() for i in indexes]}")
        mime_data = QMimeData()
        rows = sorted(set(index.row() for index in indexes))

        data = QByteArray()
        stream = QDataStream(data, QIODevice.WriteOnly)
        for row in rows:
            stream.writeInt32(row)

        mime_data.setData("application/x-task-row", data)
        return mime_data

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction,
                     row: int, column: int, parent: QModelIndex) -> bool:
        """处理拖拽放置 - 插入式（不覆盖）"""
        print(f"[TaskTableModel] dropMimeData: row={row}, parent.row={parent.row() if parent.isValid() else -1}")
        if action == Qt.IgnoreAction:
            return True

        if not data.hasFormat("application/x-task-row"):
            return False

        # 解析源行号
        byte_array = data.data("application/x-task-row")
        stream = QDataStream(byte_array, QIODevice.ReadOnly)
        source_rows = []
        while not stream.atEnd():
            source_rows.append(stream.readInt32())

        if not source_rows:
            return False

        source_row = source_rows[0]  # 只处理单行拖拽

        # 确定目标插入位置
        # row >= 0: 插入到该行之前
        # row == -1 且 parent.isValid(): 放在 parent 行的位置（之后）
        # row == -1 且 parent 无效: 放到末尾
        if row >= 0:
            target_row = row
        elif parent.isValid():
            target_row = parent.row() + 1  # 插入到目标行之后
        else:
            target_row = len(self._tasks)

        print(f"[TaskTableModel] Moving row {source_row} -> {target_row}")

        # 如果源和目标相同，不需要移动
        if source_row == target_row or source_row + 1 == target_row:
            return False

        # 执行移动
        task = self._tasks.pop(source_row)
        # 如果源在目标之前，目标位置需要减1
        if source_row < target_row:
            target_row -= 1
        self._tasks.insert(target_row, task)

        # 重新计算 priority（位置越靠前，priority 越高）
        for i, t in enumerate(self._tasks):
            t.priority = len(self._tasks) - i

        self.layoutChanged.emit()
        self.order_changed.emit(self._tasks)
        return True

    # 数据操作方法

    def load_tasks(self, tasks: list[Task]):
        """加载任务列表"""
        self.beginResetModel()
        self._tasks = list(tasks)
        self.endResetModel()

    def add_task(self, task: Task):
        """添加单个任务"""
        row = len(self._tasks)
        self.beginInsertRows(QModelIndex(), row, row)
        self._tasks.append(task)
        self.endInsertRows()

    def remove_task(self, row: int) -> Optional[Task]:
        """移除任务"""
        if 0 <= row < len(self._tasks):
            self.beginRemoveRows(QModelIndex(), row, row)
            task = self._tasks.pop(row)
            self.endRemoveRows()
            return task
        return None

    def update_task_status(self, task_id: int, status: TaskStatus):
        """更新任务状态"""
        found = False
        for row, task in enumerate(self._tasks):
            if task.id == task_id:
                task.status = status
                task.updated_at = datetime.now()

                # 发出数据变更信号
                top_left = self.index(row, 0)
                bottom_right = self.index(row, self.columnCount() - 1)
                self.dataChanged.emit(top_left, bottom_right)
                self.dataChanged_custom.emit(task_id, status)
                found = True
                break

        # 如果找不到任务，触发视图刷新以从数据库重新加载
        if not found:
            self.layoutChanged.emit()

    def update_task_by_code(
        self,
        content_code: str,
        status: TaskStatus,
        executed_time: Optional[datetime] = None
    ) -> bool:
        """通过 content_code 更新任务状态"""
        for row, task in enumerate(self._tasks):
            if task.content_code == content_code:
                task.status = status
                if executed_time is not None:
                    task.executed_time = executed_time
                task.updated_at = datetime.now()

                top_left = self.index(row, 0)
                bottom_right = self.index(row, self.columnCount() - 1)
                self.dataChanged.emit(top_left, bottom_right)
                return True
        return False

    def set_next_task_id(self, task_id: Optional[int]):
        """设置下一任务用于高亮"""
        if self._next_task_id == task_id:
            return

        old_task_id = self._next_task_id
        self._next_task_id = task_id

        if task_id is None and old_task_id is None:
            return

        rows_to_update = set()
        for row, task in enumerate(self._tasks):
            if task.id in (old_task_id, task_id):
                rows_to_update.add(row)

        if not rows_to_update:
            self.layoutChanged.emit()
            return

        for row in rows_to_update:
            top_left = self.index(row, 0)
            bottom_right = self.index(row, self.columnCount() - 1)
            self.dataChanged.emit(top_left, bottom_right)

    def get_task(self, row: int) -> Optional[Task]:
        """获取指定行的任务"""
        if 0 <= row < len(self._tasks):
            return self._tasks[row]
        return None

    def move_task(self, from_row: int, to_row: int):
        """
        移动任务到新位置（插入式，不覆盖）

        Args:
            from_row: 源行号
            to_row: 目标插入位置
        """
        if from_row < 0 or from_row >= len(self._tasks):
            return
        if to_row < 0:
            to_row = 0
        if to_row > len(self._tasks):
            to_row = len(self._tasks)

        # 相同位置不移动
        if from_row == to_row or from_row + 1 == to_row:
            return

        print(f"[TaskTableModel] move_task: {from_row} -> {to_row}")

        # 计算实际插入位置
        if from_row < to_row:
            insert_row = to_row - 1
        else:
            insert_row = to_row

        # 执行移动
        task = self._tasks.pop(from_row)
        self._tasks.insert(insert_row, task)

        # 重新计算 priority
        for i, t in enumerate(self._tasks):
            t.priority = len(self._tasks) - i

        self.layoutChanged.emit()
        self.order_changed.emit(self._tasks)

    def get_all_tasks(self) -> list[Task]:
        """获取所有任务"""
        return list(self._tasks)

    def clear(self):
        """清空所有任务"""
        self.beginResetModel()
        self._tasks.clear()
        self._next_task_id = None
        self.endResetModel()


class StatusDelegate(QStyledItemDelegate):
    """状态列自定义绘制"""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        task = index.data(Qt.UserRole)
        if task and index.column() == 0:
            # 获取状态颜色
            color = QColor(STATUS_COLORS.get(task.status, "#9E9E9E"))

            # 绘制背景圆角矩形
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)

            # 计算居中位置
            text = index.data(Qt.DisplayRole)
            rect = option.rect.adjusted(8, 4, -8, -4)

            # 绘制背景
            bg_color = QColor(color)
            bg_color.setAlpha(30)
            painter.setBrush(bg_color)
            painter.setPen(color)
            painter.drawRoundedRect(rect, 4, 4)

            # 绘制文字
            painter.setPen(color)
            painter.drawText(rect, Qt.AlignCenter, text)

            painter.restore()
        else:
            super().paint(painter, option, index)


class TaskEditDialog(QDialog):
    """任务编辑对话框"""

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setWindowTitle(f"编辑任务 - {task.content_code}")
        self.setMinimumWidth(450)
        self.setModal(True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # 任务信息显示
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #F8F9FA;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        info_layout = QFormLayout(info_frame)
        info_layout.setSpacing(8)

        # 显示任务基本信息
        info_layout.addRow("文案编号:", QLabel(f"<b>{self.task.content_code}</b>"))
        info_layout.addRow("产品名称:", QLabel(self.task.product_name or "-"))
        # 显示文案内容（截断）
        text_display = self.task.text[:100] + "..." if len(self.task.text or "") > 100 else (self.task.text or "-")
        info_layout.addRow("文案内容:", QLabel(text_display))
        channel_text = Channel.get_display_name(self.task.channel)
        info_layout.addRow("发布渠道:", QLabel(channel_text))
        if self.task.group_name:
            info_layout.addRow("群名:", QLabel(self.task.group_name))

        layout.addWidget(info_frame)

        # 排期时间设置
        schedule_frame = QFrame()
        schedule_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #DEE2E6;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        schedule_main_layout = QVBoxLayout(schedule_frame)
        schedule_main_layout.setSpacing(12)

        # 快捷按钮样式
        quick_btn_style = """
            QPushButton {
                background-color: #E3F2FD;
                color: #1976D2;
                border: 1px solid #90CAF9;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #BBDEFB;
                border-color: #64B5F6;
            }
            QPushButton:pressed {
                background-color: #90CAF9;
            }
        """

        # 第一行：时间快捷按钮
        time_quick_layout = QHBoxLayout()
        time_quick_layout.setSpacing(8)

        time_label = QLabel("快捷时间:")
        time_label.setStyleSheet("color: #495057; font-size: 12px;")
        time_quick_layout.addWidget(time_label)

        self.add_30min_btn = QPushButton("+30分")
        self.add_30min_btn.setStyleSheet(quick_btn_style)
        self.add_30min_btn.setCursor(Qt.PointingHandCursor)
        self.add_30min_btn.clicked.connect(lambda: self._add_time(minutes=30))
        time_quick_layout.addWidget(self.add_30min_btn)

        self.add_1hour_btn = QPushButton("+1时")
        self.add_1hour_btn.setStyleSheet(quick_btn_style)
        self.add_1hour_btn.setCursor(Qt.PointingHandCursor)
        self.add_1hour_btn.clicked.connect(lambda: self._add_time(hours=1))
        time_quick_layout.addWidget(self.add_1hour_btn)

        self.add_2hour_btn = QPushButton("+2时")
        self.add_2hour_btn.setStyleSheet(quick_btn_style)
        self.add_2hour_btn.setCursor(Qt.PointingHandCursor)
        self.add_2hour_btn.clicked.connect(lambda: self._add_time(hours=2))
        time_quick_layout.addWidget(self.add_2hour_btn)

        # 分隔符
        separator = QLabel("|")
        separator.setStyleSheet("color: #ADB5BD; font-size: 14px;")
        time_quick_layout.addWidget(separator)

        # 日期快捷按钮
        self.today_btn = QPushButton("今天")
        self.today_btn.setStyleSheet(quick_btn_style)
        self.today_btn.setCursor(Qt.PointingHandCursor)
        self.today_btn.clicked.connect(lambda: self._set_date_offset(0))
        time_quick_layout.addWidget(self.today_btn)

        self.tomorrow_btn = QPushButton("明天")
        self.tomorrow_btn.setStyleSheet(quick_btn_style)
        self.tomorrow_btn.setCursor(Qt.PointingHandCursor)
        self.tomorrow_btn.clicked.connect(lambda: self._set_date_offset(1))
        time_quick_layout.addWidget(self.tomorrow_btn)

        self.day_after_btn = QPushButton("后天")
        self.day_after_btn.setStyleSheet(quick_btn_style)
        self.day_after_btn.setCursor(Qt.PointingHandCursor)
        self.day_after_btn.clicked.connect(lambda: self._set_date_offset(2))
        time_quick_layout.addWidget(self.day_after_btn)

        time_quick_layout.addStretch()
        schedule_main_layout.addLayout(time_quick_layout)

        # 第二行：日期和时间选择
        datetime_layout = QHBoxLayout()
        datetime_layout.setSpacing(16)

        # 日期选择
        date_label = QLabel("日期:")
        date_label.setStyleSheet("color: #495057; font-size: 13px;")
        datetime_layout.addWidget(date_label)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setMinimumWidth(120)
        self.date_edit.setStyleSheet("""
            QDateEdit {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QDateEdit:focus {
                border-color: #1976D2;
            }
            QDateEdit::drop-down {
                border: none;
                width: 20px;
            }
        """)
        datetime_layout.addWidget(self.date_edit)

        datetime_layout.addSpacing(20)

        # 时间选择
        time_label2 = QLabel("时间:")
        time_label2.setStyleSheet("color: #495057; font-size: 13px;")
        datetime_layout.addWidget(time_label2)

        spinbox_style = """
            QSpinBox {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
                min-width: 50px;
            }
            QSpinBox:focus {
                border-color: #1976D2;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 16px;
            }
        """

        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setStyleSheet(spinbox_style)
        self.hour_spin.setWrapping(True)
        datetime_layout.addWidget(self.hour_spin)

        hour_label = QLabel("时")
        hour_label.setStyleSheet("color: #495057; font-size: 13px;")
        datetime_layout.addWidget(hour_label)

        self.minute_spin = QSpinBox()
        self.minute_spin.setRange(0, 59)
        self.minute_spin.setSingleStep(5)
        self.minute_spin.setStyleSheet(spinbox_style)
        self.minute_spin.setWrapping(True)
        datetime_layout.addWidget(self.minute_spin)

        minute_label = QLabel("分")
        minute_label.setStyleSheet("color: #495057; font-size: 13px;")
        datetime_layout.addWidget(minute_label)

        datetime_layout.addStretch()
        schedule_main_layout.addLayout(datetime_layout)

        # 第三行：设为现在按钮
        now_layout = QHBoxLayout()
        self.now_btn = QPushButton("📍 设为现在")
        self.now_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFF3E0;
                color: #E65100;
                border: 1px solid #FFB74D;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #FFE0B2;
                border-color: #FFA726;
            }
            QPushButton:pressed {
                background-color: #FFCC80;
            }
        """)
        self.now_btn.setCursor(Qt.PointingHandCursor)
        self.now_btn.clicked.connect(self._set_now)
        now_layout.addWidget(self.now_btn)
        now_layout.addStretch()
        schedule_main_layout.addLayout(now_layout)

        layout.addWidget(schedule_frame)

        # 设置初始值
        self._init_datetime_values()

        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # 设置按钮文字
        button_box.button(QDialogButtonBox.Ok).setText("保存")
        button_box.button(QDialogButtonBox.Cancel).setText("取消")

        layout.addWidget(button_box)

    def _init_datetime_values(self):
        """初始化日期时间值"""
        if self.task.scheduled_time:
            # 使用任务的排期时间
            dt = self.task.scheduled_time
        else:
            # 默认：当前时间 + 1小时
            dt = datetime.now() + timedelta(hours=1)

        self.date_edit.setDate(QDate(dt.year, dt.month, dt.day))
        self.hour_spin.setValue(dt.hour)
        self.minute_spin.setValue(dt.minute)

    def _set_now(self):
        """设置为当前时间"""
        now = datetime.now()
        self.date_edit.setDate(QDate(now.year, now.month, now.day))
        self.hour_spin.setValue(now.hour)
        self.minute_spin.setValue(now.minute)

    def _add_time(self, minutes: int = 0, hours: int = 0):
        """在当前时间基础上增加时间"""
        # 获取当前设置的时间
        current_dt = self.get_scheduled_time()
        # 增加时间
        new_dt = current_dt + timedelta(minutes=minutes, hours=hours)
        # 更新控件
        self.date_edit.setDate(QDate(new_dt.year, new_dt.month, new_dt.day))
        self.hour_spin.setValue(new_dt.hour)
        self.minute_spin.setValue(new_dt.minute)

    def _set_date_offset(self, days: int):
        """设置日期偏移（保持时间不变）"""
        today = datetime.now().date()
        target_date = today + timedelta(days=days)
        self.date_edit.setDate(QDate(target_date.year, target_date.month, target_date.day))

    def get_scheduled_time(self) -> datetime:
        """获取设置的排期时间"""
        qdate = self.date_edit.date()
        return datetime(
            qdate.year(),
            qdate.month(),
            qdate.day(),
            self.hour_spin.value(),
            self.minute_spin.value()
        )


class TaskFilterProxyModel(QSortFilterProxyModel):
    """任务筛选代理模型（支持拖拽排序）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_status: Optional[TaskStatus] = None

    def set_status_filter(self, status: Optional[TaskStatus]):
        """设置状态筛选"""
        self._filter_status = status
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """判断行是否符合筛选条件"""
        if self._filter_status is None:
            return True

        # 获取源模型中的任务
        source_model = self.sourceModel()
        if source_model:
            task = source_model.get_task(source_row)
            if task:
                return task.status == self._filter_status

        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        """支持拖拽"""
        default_flags = super().flags(index)
        if index.isValid():
            return default_flags | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        return default_flags | Qt.ItemIsDropEnabled

    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.MoveAction

    def mimeTypes(self) -> list:
        return ["application/x-task-row"]

    def canDropMimeData(self, data: QMimeData, action: Qt.DropAction,
                        row: int, column: int, parent: QModelIndex) -> bool:
        """检查是否可以放置"""
        return data.hasFormat("application/x-task-row")

    def mimeData(self, indexes: list) -> QMimeData:
        """生成拖拽数据（转换为源模型索引）"""
        print(f"[ProxyModel] mimeData called, indexes={[i.row() for i in indexes]}")
        mime_data = QMimeData()
        # 转换为源模型的行号
        source_rows = sorted(set(self.mapToSource(index).row() for index in indexes if index.isValid()))

        data = QByteArray()
        stream = QDataStream(data, QIODevice.WriteOnly)
        for row in source_rows:
            stream.writeInt32(row)

        mime_data.setData("application/x-task-row", data)
        return mime_data

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction,
                     row: int, column: int, parent: QModelIndex) -> bool:
        """处理拖拽放置（转换索引并传递给源模型）"""
        if action == Qt.IgnoreAction:
            return True

        # 转换目标行到源模型
        if row >= 0:
            # 获取目标位置对应的源模型行
            if row < self.rowCount():
                source_row = self.mapToSource(self.index(row, 0)).row()
            else:
                source_row = self.sourceModel().rowCount()
        elif parent.isValid():
            source_row = self.mapToSource(parent).row()
        else:
            source_row = self.sourceModel().rowCount()

        # 传递给源模型处理
        return self.sourceModel().dropMimeData(data, action, source_row, column, QModelIndex())


class ChannelQueueWidget(QWidget):
    """
    单个渠道的队列组件

    包含：
    - 发布间隔设置（支持秒/分钟/小时）
    - 每日时间窗口设置
    - 工具栏（开始/暂停）
    - 任务表格
    - 状态栏

    支持内置渠道（Channel枚举）和自定义渠道（字符串ID如 'custom_1'）
    """

    # 信号定义 - 使用 object 类型以支持 Channel 枚举和字符串
    task_execute_requested = Signal(Task)
    task_edit_requested = Signal(Task)
    task_cancel_requested = Signal(Task)
    task_delete_requested = Signal(Task)
    tasks_reordered = Signal(list)  # 任务顺序变更
    start_publishing_requested = Signal(object)  # channel (Channel枚举或字符串)
    pause_publishing_requested = Signal(object)  # channel
    stop_current_task_requested = Signal()  # 停止当前正在执行的任务
    pause_current_task_requested = Signal()  # 暂停/恢复当前正在执行的任务
    minute_of_hour_changed = Signal(object, int)  # channel, minute (0-59)
    schedule_mode_changed = Signal(object, str)  # channel, mode
    interval_changed = Signal(object, int, str)  # channel, value, unit
    daily_window_changed = Signal(object, str, str)  # channel, start, end
    group_names_changed = Signal(object, list)  # channel, group_names
    extra_message_changed = Signal(object, str)  # channel, extra_message
    clear_channel_requested = Signal(object)  # channel - 请求清空当前渠道的所有任务

    def __init__(self, channel, parent=None):
        """
        初始化渠道队列组件

        Args:
            channel: Channel枚举或自定义渠道ID字符串（如 'custom_1'）
            parent: 父组件
        """
        super().__init__(parent)
        self.channel = channel
        # 判断是否为自定义渠道
        self._is_custom = Channel.is_custom_channel(channel) if isinstance(channel, str) else False
        self._group_names: List[str] = []
        self._is_publishing = False
        self._is_task_paused = False  # 当前任务是否暂停
        self._extra_message_timer = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # 额外消息输入面板（群发渠道和自定义渠道显示）
        if self._is_custom or Channel.is_group_channel(self.channel):
            extra_msg_panel = self._create_extra_message_panel()
            layout.addWidget(extra_msg_panel)

        # 任务表格
        self._create_table()
        layout.addWidget(self.table_view)

        # 底部状态栏
        bottom_bar = self._create_bottom_bar()
        layout.addWidget(bottom_bar)

    def _create_toolbar(self) -> QFrame:
        """创建工具栏"""
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 2px;
            }
        """)
        toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar.setMaximumHeight(72)

        main_layout = QVBoxLayout(toolbar)
        main_layout.setContentsMargins(6, 4, 6, 4)
        main_layout.setSpacing(4)

        # SpinBox/TimeEdit 样式（水平按钮布局，使用内嵌SVG图标）
        spinbox_style = r"""
            QAbstractSpinBox {
                background: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 4px 8px;
                padding-right: 56px;
                font-size: 14px;
                min-height: 24px;
            }
            QAbstractSpinBox:focus {
                border-color: #1976D2;
            }
            QAbstractSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: center right;
                width: 28px;
                border-left: 1px solid #CED4DA;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
                background: #E3F2FD;
            }
            QAbstractSpinBox::up-button:hover {
                background: #BBDEFB;
            }
            QAbstractSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: center right;
                right: 28px;
                width: 28px;
                border-left: 1px solid #CED4DA;
                background: #E3F2FD;
            }
            QAbstractSpinBox::down-button:hover {
                background: #BBDEFB;
            }
            QAbstractSpinBox::up-arrow {
                width: 12px;
                height: 12px;
                image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBkPSJNMiA2aDhNNiAydjgiIHN0cm9rZT0iIzIyMiIgc3Ryb2tlLXdpZHRoPSIxLjYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPjwvc3ZnPg==");
            }
            QAbstractSpinBox::down-arrow {
                width: 12px;
                height: 12px;
                image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBkPSJNMiA2aDgiIHN0cm9rZT0iIzIyMiIgc3Ryb2tlLXdpZHRoPSIxLjYiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPjwvc3ZnPg==");
            }
            QAbstractSpinBox::up-arrow:disabled,
            QAbstractSpinBox::down-arrow:disabled {
                image: none;
            }
        """

        # QTimeEdit 简洁样式（无按钮）
        timeedit_style = """
            QTimeEdit {
                background: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
                min-height: 24px;
            }
            QTimeEdit:focus {
                border-color: #1976D2;
            }
            QTimeEdit::up-button, QTimeEdit::down-button {
                width: 0px;
                border: none;
            }
        """

        # 第一行：每小时定点执行和控制按钮
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(8)

        # 调度模式选择
        mode_label = QLabel("模式:")
        mode_label.setStyleSheet("color: #495057; font-size: 12px;")
        row1_layout.addWidget(mode_label)

        self.schedule_mode_combo = QComboBox()
        self.schedule_mode_combo.addItem("定点", "fixed_time")
        self.schedule_mode_combo.addItem("间隔", "interval")
        self.schedule_mode_combo.setStyleSheet("""
            QComboBox {
                background: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                min-height: 24px;
            }
            QComboBox:focus {
                border-color: #1976D2;
            }
        """)
        self.schedule_mode_combo.setMinimumWidth(90)
        row1_layout.addWidget(self.schedule_mode_combo)

        # 模式配置区域
        self.schedule_mode_stack = QStackedWidget()

        # 定点模式控件
        fixed_panel = QWidget()
        fixed_layout = QHBoxLayout(fixed_panel)
        fixed_layout.setContentsMargins(0, 0, 0, 0)
        fixed_layout.setSpacing(6)

        minute_label = QLabel("每小时第")
        minute_label.setStyleSheet("color: #495057; font-size: 12px;")
        fixed_layout.addWidget(minute_label)

        self.minute_spin = QSpinBox()
        self.minute_spin.setRange(0, 59)
        self.minute_spin.setValue(0)
        self.minute_spin.setMinimumWidth(50)
        self.minute_spin.setStyleSheet(timeedit_style)
        self.minute_spin.setButtonSymbols(QSpinBox.NoButtons)
        fixed_layout.addWidget(self.minute_spin)

        fixed_suffix_label = QLabel("分钟执行")
        fixed_suffix_label.setStyleSheet("color: #495057; font-size: 12px;")
        fixed_layout.addWidget(fixed_suffix_label)

        # 间隔模式控件
        interval_panel = QWidget()
        interval_layout = QHBoxLayout(interval_panel)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        interval_layout.setSpacing(6)

        interval_label = QLabel("间隔")
        interval_label.setStyleSheet("color: #495057; font-size: 12px;")
        interval_layout.addWidget(interval_label)

        self.interval_value_spin = QSpinBox()
        self.interval_value_spin.setRange(1, 3600)
        self.interval_value_spin.setValue(3)
        self.interval_value_spin.setMinimumWidth(60)
        self.interval_value_spin.setStyleSheet(timeedit_style)
        self.interval_value_spin.setButtonSymbols(QSpinBox.NoButtons)
        interval_layout.addWidget(self.interval_value_spin)

        self.interval_unit_combo = QComboBox()
        self.interval_unit_combo.addItem("秒", "seconds")
        self.interval_unit_combo.addItem("分钟", "minutes")
        self.interval_unit_combo.addItem("小时", "hours")
        self.interval_unit_combo.setStyleSheet("""
            QComboBox {
                background: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                min-height: 24px;
            }
            QComboBox:focus {
                border-color: #1976D2;
            }
        """)
        self.interval_unit_combo.setMinimumWidth(70)
        interval_layout.addWidget(self.interval_unit_combo)

        interval_suffix_label = QLabel("执行")
        interval_suffix_label.setStyleSheet("color: #495057; font-size: 12px;")
        interval_layout.addWidget(interval_suffix_label)

        self.schedule_mode_stack.addWidget(fixed_panel)
        self.schedule_mode_stack.addWidget(interval_panel)
        row1_layout.addWidget(self.schedule_mode_stack)
        self.schedule_mode_combo.setCurrentIndex(1)
        self.schedule_mode_stack.setCurrentIndex(1)
        self.schedule_mode_stack.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # 分隔符
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("background-color: #E0E0E0;")
        separator.setFixedWidth(1)
        row1_layout.addWidget(separator)

        # 每日时间窗口
        window_label = QLabel("时间窗口:")
        window_label.setStyleSheet("color: #495057; font-size: 12px;")
        row1_layout.addWidget(window_label)

        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setDisplayFormat("HH:mm")
        self.start_time_edit.setTime(QTime(8, 0))
        self.start_time_edit.setMinimumWidth(70)
        self.start_time_edit.setStyleSheet(timeedit_style)
        self.start_time_edit.setButtonSymbols(QTimeEdit.NoButtons)
        row1_layout.addWidget(self.start_time_edit)

        to_label = QLabel("-")
        to_label.setStyleSheet("color: #495057; font-size: 14px; font-weight: bold;")
        row1_layout.addWidget(to_label)

        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setDisplayFormat("HH:mm")
        self.end_time_edit.setTime(QTime(22, 0))
        self.end_time_edit.setMinimumWidth(70)
        self.end_time_edit.setStyleSheet(timeedit_style)
        self.end_time_edit.setButtonSymbols(QTimeEdit.NoButtons)
        row1_layout.addWidget(self.end_time_edit)

        # 分隔符
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setStyleSheet("background-color: #E0E0E0;")
        separator2.setFixedWidth(1)
        row1_layout.addWidget(separator2)

        # 发布控制区（突出显示）
        control_panel = QFrame()
        control_panel.setStyleSheet("""
            QFrame {
                background-color: #E8F5E9;
                border: 1px solid #A5D6A7;
                border-radius: 8px;
            }
        """)
        control_panel.setToolTip("发布控制只影响当前渠道")
        control_panel.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        control_layout = QHBoxLayout(control_panel)
        control_layout.setContentsMargins(8, 2, 8, 2)
        control_layout.setSpacing(6)

        control_label = QLabel("发布控制（本渠道）")
        control_label.setStyleSheet("color: #2E7D32; font-size: 11px; font-weight: 700;")
        control_layout.addWidget(control_label)

        start_btn_style = BUTTON_SUCCESS_STYLE + """
            QPushButton {
                font-size: 12px;
                font-weight: 700;
                padding: 6px 12px;
                min-height: 28px;
            }
        """

        pause_btn_style = """
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 700;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #EF6C00;
            }
            QPushButton:disabled {
                background-color: #FFE0B2;
                color: #BDBDBD;
            }
        """

        # 开始/暂停按钮
        self.start_btn = QPushButton("▶ 开始发布（本渠道）")
        self.start_btn.setStyleSheet(start_btn_style)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setMinimumWidth(130)
        self.start_btn.setToolTip("仅启动当前渠道任务")
        control_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("⏸ 暂停（本渠道）")
        self.pause_btn.setStyleSheet(pause_btn_style)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setMinimumWidth(110)
        self.pause_btn.setToolTip("仅暂停当前渠道任务")
        control_layout.addWidget(self.pause_btn)

        # 任务控制按钮样式
        task_control_style = """
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 700;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:pressed {
                background-color: #6A1B9A;
            }
            QPushButton:disabled {
                background-color: #E1BEE7;
                color: #BDBDBD;
            }
        """
        stop_task_style = """
            QPushButton {
                background-color: #F44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 700;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
            QPushButton:pressed {
                background-color: #C62828;
            }
            QPushButton:disabled {
                background-color: #FFCDD2;
                color: #BDBDBD;
            }
        """

        # 暂停/恢复当前任务按钮
        self.pause_task_btn = QPushButton("⏸ 暂停任务")
        self.pause_task_btn.setStyleSheet(task_control_style)
        self.pause_task_btn.setCursor(Qt.PointingHandCursor)
        self.pause_task_btn.setEnabled(False)
        self.pause_task_btn.setMinimumWidth(90)
        self.pause_task_btn.setToolTip("暂停/恢复当前正在执行的任务")
        control_layout.addWidget(self.pause_task_btn)

        # 停止当前任务按钮
        self.stop_task_btn = QPushButton("⏹ 停止任务")
        self.stop_task_btn.setStyleSheet(stop_task_style)
        self.stop_task_btn.setCursor(Qt.PointingHandCursor)
        self.stop_task_btn.setEnabled(False)
        self.stop_task_btn.setMinimumWidth(90)
        self.stop_task_btn.setToolTip("停止当前正在执行的任务")
        control_layout.addWidget(self.stop_task_btn)

        row1_layout.addWidget(control_panel)

        # 清空队列按钮
        self.clear_btn = QPushButton("🗑️ 清空队列")
        self.clear_btn.setStyleSheet(BUTTON_DANGER_STYLE + """
            QPushButton {
                padding: 6px 12px;
                font-size: 12px;
                min-height: 28px;
            }
        """)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setToolTip("清空当前渠道的所有任务")
        row1_layout.addWidget(self.clear_btn)

        # 群名配置按钮（群发渠道和自定义渠道显示）
        if self._is_custom or Channel.is_group_channel(self.channel):
            self.group_config_btn = QPushButton("⚙ 配置群名")
            self.group_config_btn.setStyleSheet(BUTTON_STYLE + """
                QPushButton {
                    padding: 6px 12px;
                    font-size: 12px;
                    min-height: 28px;
                }
            """)
            self.group_config_btn.setCursor(Qt.PointingHandCursor)
            self.group_config_btn.setMinimumWidth(110)
            self.group_config_btn.setToolTip("点击配置要群发的群名（每行一个）")
            row1_layout.addWidget(self.group_config_btn)
            self._update_group_button_label()

        row1_layout.addStretch()

        # 筛选下拉框
        filter_label = QLabel("筛选:")
        filter_label.setStyleSheet("color: #757575; font-size: 12px;")
        row1_layout.addWidget(filter_label)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("全部", None)
        self.filter_combo.addItem("待执行", TaskStatus.pending)
        self.filter_combo.addItem("已调度", TaskStatus.scheduled)
        self.filter_combo.addItem("执行中", TaskStatus.running)
        self.filter_combo.addItem("成功", TaskStatus.success)
        self.filter_combo.addItem("失败", TaskStatus.failed)
        self.filter_combo.setStyleSheet(INPUT_STYLE + """
            QComboBox {
                padding: 4px 8px;
                font-size: 12px;
                min-height: 24px;
            }
        """)
        self.filter_combo.setMinimumWidth(90)
        row1_layout.addWidget(self.filter_combo)

        main_layout.addLayout(row1_layout)

        return toolbar

    def _create_extra_message_panel(self) -> QFrame:
        """创建额外消息输入面板（仅群发渠道使用）"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 4px;
            }
        """)

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # 标签
        label = QLabel("群发后附加消息:")
        label.setStyleSheet("color: #495057; font-size: 12px;")
        layout.addWidget(label)

        # 输入框
        self.extra_message_edit = QLineEdit()
        self.extra_message_edit.setPlaceholderText("输入每个群发送完成后要附加的文字（可选）...")
        self.extra_message_edit.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #1976D2;
            }
        """)
        layout.addWidget(self.extra_message_edit, 1)  # stretch=1 让输入框占满剩余空间

        return panel

    def _create_table(self):
        """创建任务表格"""
        self.table_model = TaskTableModel(self)
        self.proxy_model = TaskFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.table_model)

        # 使用自定义的支持拖拽的表格视图
        self.table_view = DraggableTableView()
        self.table_view.setModel(self.proxy_model)

        # 连接拖拽信号
        self.table_view.row_moved.connect(self._on_row_moved)

        # 设置样式
        self.table_view.setStyleSheet(TABLE_STYLE)

        # 设置选择模式
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # 设置表头
        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Interactive)

        # 设置默认列宽
        for i, (_, _, width) in enumerate(TaskTableModel.COLUMNS):
            self.table_view.setColumnWidth(i, width)

        header.setMinimumSectionSize(50)

        # 隐藏行号
        v_header = self.table_view.verticalHeader()
        v_header.setVisible(False)
        v_header.setDefaultSectionSize(56)  # 增加行高以显示两行内容

        # 启用交替行颜色
        self.table_view.setAlternatingRowColors(True)

        # 设置状态列委托
        self.table_view.setItemDelegateForColumn(0, StatusDelegate(self))

        # 右键菜单
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)

        # 双击编辑
        self.table_view.doubleClicked.connect(self._on_double_click)

    def _create_bottom_bar(self) -> QFrame:
        """创建底部状态栏"""
        bar = QFrame()
        bar.setStyleSheet("""
            QFrame {
                background-color: #F8F9FA;
                border: 1px solid #E9ECEF;
                border-radius: 6px;
                padding: 6px;
            }
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(16)

        # 任务统计
        self.stats_label = QLabel("共 0 个任务")
        self.stats_label.setTextFormat(Qt.RichText)
        self.stats_label.setStyleSheet("""
            QLabel {
                color: #495057;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.stats_label)

        layout.addStretch()

        # 选中信息
        self.selection_label = QLabel("")
        self.selection_label.setStyleSheet("""
            QLabel {
                color: #1976D2;
                font-size: 12px;
                font-weight: 500;
                background-color: #E3F2FD;
                padding: 2px 8px;
                border-radius: 3px;
            }
        """)
        self.selection_label.setVisible(False)
        layout.addWidget(self.selection_label)

        return bar

    def _connect_signals(self):
        """连接信号"""
        self.start_btn.clicked.connect(self._on_start_clicked)
        self.pause_btn.clicked.connect(self._on_pause_clicked)
        self.pause_task_btn.clicked.connect(self._on_pause_task_clicked)
        self.stop_task_btn.clicked.connect(self._on_stop_task_clicked)
        self.clear_btn.clicked.connect(self._on_clear_channel_clicked)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)

        # 调度模式与间隔设置变化
        self.schedule_mode_combo.currentIndexChanged.connect(self._on_schedule_mode_changed)
        self.interval_value_spin.valueChanged.connect(self._on_interval_changed)
        self.interval_unit_combo.currentIndexChanged.connect(self._on_interval_changed)

        # 每小时定点设置变化
        self.minute_spin.valueChanged.connect(self._on_minute_changed)

        # 每日时间窗口变化
        self.start_time_edit.timeChanged.connect(self._on_daily_window_changed)
        self.end_time_edit.timeChanged.connect(self._on_daily_window_changed)

        # 群名相关信号（群发渠道和自定义渠道）
        if self._is_custom or Channel.is_group_channel(self.channel):
            self.group_config_btn.clicked.connect(self._open_group_names_dialog)

        # Extra message persistence (group/custom channels)
        if hasattr(self, "extra_message_edit"):
            self._extra_message_timer = QTimer(self)
            self._extra_message_timer.setSingleShot(True)
            self._extra_message_timer.timeout.connect(self._emit_extra_message_changed)
            self.extra_message_edit.textChanged.connect(self._on_extra_message_input_changed)

        # 选择变化
        self.table_view.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )

        # 模型数据变化
        self.table_model.rowsInserted.connect(self._update_stats)
        self.table_model.rowsRemoved.connect(self._update_stats)
        self.table_model.modelReset.connect(self._update_stats)
        self.table_model.dataChanged.connect(self._update_stats)

        # 任务顺序变更
        self.table_model.order_changed.connect(self._on_order_changed)

    def _on_order_changed(self, tasks):
        """处理任务顺序变更"""
        self.tasks_reordered.emit(tasks)

    def _on_row_moved(self, from_row: int, to_row: int):
        """处理行拖拽移动"""
        # DraggableTableView.dropEvent 已经将行号转换为源模型行号
        # 直接调用 move_task
        self.table_model.move_task(from_row, to_row)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        index = self.table_view.indexAt(pos)

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #E3F2FD;
            }
            QMenu::separator {
                height: 1px;
                background-color: #E0E0E0;
                margin: 4px 8px;
            }
        """)

        # 如果点击的是有效行，显示任务操作菜单
        if index.isValid():
            source_index = self.proxy_model.mapToSource(index)
            task = self.table_model.get_task(source_index.row())
            if task:
                # 立即执行（所有状态的任务都可以执行）
                execute_action = menu.addAction("▶ 立即执行")
                execute_action.triggered.connect(lambda checked, t=task: self._on_execute_task(t))

                # 编辑排期
                if task.status in (TaskStatus.pending, TaskStatus.scheduled):
                    edit_action = menu.addAction("✏️ 编辑排期")
                    edit_action.triggered.connect(lambda checked, t=task: self._on_edit_task(t))

                menu.addSeparator()

                # 取消任务
                if task.status in (TaskStatus.pending, TaskStatus.scheduled, TaskStatus.running):
                    cancel_action = menu.addAction("🚫 取消任务")
                    cancel_action.triggered.connect(lambda checked, t=task: self._on_cancel_task(t))

                # 删除任务
                delete_action = menu.addAction("🗑️ 删除任务")
                delete_action.triggered.connect(lambda checked, t=task: self._on_delete_task(t))

        # 分隔符和清空选项（始终显示）
        if menu.actions():  # 如果有其他菜单项
            menu.addSeparator()

        # 清空当前渠道
        task_count = self.table_model.rowCount()
        clear_action = menu.addAction(f"🗑️ 清空全部 ({task_count})")
        clear_action.setEnabled(task_count > 0)
        clear_action.triggered.connect(self._on_clear_channel_clicked)

        menu.exec_(self.table_view.viewport().mapToGlobal(pos))

    def _on_double_click(self, index: QModelIndex):
        """双击编辑"""
        source_index = self.proxy_model.mapToSource(index)
        task = self.table_model.get_task(source_index.row())
        if task and task.status in (TaskStatus.pending, TaskStatus.scheduled):
            self._on_edit_task(task)

    def _on_execute_task(self, task: Task):
        """立即执行任务"""
        reply = QMessageBox.question(
            self,
            "确认执行",
            f"确定要立即执行任务 [{task.content_code}] 吗？\n\n"
            f"产品: {task.product_name or '-'}\n"
            f"渠道: {Channel.get_display_name(task.channel)}\n\n"
            "请确保微信已打开并登录！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            task.status = TaskStatus.running
            task.scheduled_time = datetime.now()
            self._refresh_task_row(task)
            self.task_execute_requested.emit(task)

    def _on_edit_task(self, task: Task):
        """编辑任务排期"""
        dialog = TaskEditDialog(task, self)

        if dialog.exec() == QDialog.Accepted:
            task.scheduled_time = dialog.get_scheduled_time()
            task.status = TaskStatus.scheduled
            task.updated_at = datetime.now()
            self._refresh_task_row(task)
            self.task_edit_requested.emit(task)

    def _refresh_task_row(self, task: Task):
        """刷新指定任务的显示"""
        for row in range(self.table_model.rowCount()):
            t = self.table_model.get_task(row)
            if t and t.content_code == task.content_code:
                top_left = self.table_model.index(row, 0)
                bottom_right = self.table_model.index(row, self.table_model.columnCount() - 1)
                self.table_model.dataChanged.emit(top_left, bottom_right)
                break
        self._update_stats()

    def _on_cancel_task(self, task: Task):
        """请求取消任务"""
        reply = QMessageBox.question(
            self, "确认取消",
            f"确定要取消任务 [{task.product_name}] 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.task_cancel_requested.emit(task)

    def _on_delete_task(self, task: Task):
        """请求删除任务"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除任务 [{task.product_name}] 吗？\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.task_delete_requested.emit(task)
            for row in range(self.table_model.rowCount()):
                if self.table_model.get_task(row) and self.table_model.get_task(row).id == task.id:
                    self.table_model.remove_task(row)
                    break

    def _on_start_clicked(self):
        """开始发布"""
        self._is_publishing = True
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.start_publishing_requested.emit(self.channel)

    def _on_pause_clicked(self):
        """暂停发布"""
        self._is_publishing = False
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_publishing_requested.emit(self.channel)

    def _on_pause_task_clicked(self):
        """暂停/恢复当前任务"""
        self._is_task_paused = not self._is_task_paused
        if self._is_task_paused:
            self.pause_task_btn.setText("▶ 恢复任务")
            self.pause_task_btn.setToolTip("恢复当前暂停的任务")
        else:
            self.pause_task_btn.setText("⏸ 暂停任务")
            self.pause_task_btn.setToolTip("暂停当前正在执行的任务")
        self.pause_current_task_requested.emit()

    def _on_stop_task_clicked(self):
        """停止当前任务"""
        self.stop_current_task_requested.emit()
        # 重置暂停状态
        self._is_task_paused = False
        self.pause_task_btn.setText("⏸ 暂停任务")
        self.pause_task_btn.setToolTip("暂停当前正在执行的任务")

    def _on_clear_channel_clicked(self):
        """清空当前渠道所有任务"""
        task_count = self.table_model.rowCount()
        if task_count == 0:
            QMessageBox.information(
                self,
                "提示",
                "当前队列已经是空的",
                QMessageBox.Ok
            )
            return

        # 获取渠道显示名称
        channel_name = Channel.get_display_name(self.channel)

        # 确认对话框
        reply = QMessageBox.warning(
            self,
            "确认清空",
            f"确定要删除【{channel_name}】渠道的所有 {task_count} 个任务吗？\n\n"
            f"此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.clear_channel_requested.emit(self.channel)

    def _on_filter_changed(self, index: int):
        """筛选变化"""
        status = self.filter_combo.currentData()
        self.proxy_model.set_status_filter(status)
        self._update_stats()

    def _on_schedule_mode_changed(self, _=None):
        """调度模式变化"""
        mode = self.schedule_mode_combo.currentData()
        if mode == "fixed_time":
            self.schedule_mode_stack.setCurrentIndex(0)
        else:
            self.schedule_mode_stack.setCurrentIndex(1)
        self.schedule_mode_changed.emit(self.channel, mode)

    def _on_interval_changed(self, _=None):
        """间隔设置变化"""
        value = self.interval_value_spin.value()
        unit = self.interval_unit_combo.currentData()
        self.interval_changed.emit(self.channel, value, unit)

    def _on_minute_changed(self, _=None):
        """每小时定点分钟变化"""
        minute = self.minute_spin.value()
        self.minute_of_hour_changed.emit(self.channel, minute)

    def _on_daily_window_changed(self, _=None):
        """每日时间窗口变化"""
        start = self.start_time_edit.time().toString("HH:mm")
        end = self.end_time_edit.time().toString("HH:mm")
        self.daily_window_changed.emit(self.channel, start, end)

    def _on_extra_message_input_changed(self, _=None):
        if self._extra_message_timer:
            self._extra_message_timer.start(EXTRA_MESSAGE_DEBOUNCE_MS)

    def _emit_extra_message_changed(self):
        self.extra_message_changed.emit(self.channel, self.get_extra_message())

    def _open_group_names_dialog(self):
        """打开群名配置对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("配置群名")
        dialog.setModal(True)
        dialog.setMinimumWidth(460)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        hint_label = QLabel("输入群名，每行一个，保存后将应用到当前渠道。")
        hint_label.setStyleSheet("color: #6C757D; font-size: 12px;")
        layout.addWidget(hint_label)

        group_edit = QPlainTextEdit()
        group_edit.setPlaceholderText("输入群名，每行一个...\n例如：\n代理群1\n代理群2\nVIP群")
        group_edit.setPlainText('\n'.join(self._group_names))
        group_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #CED4DA;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                color: #212121;
            }
            QPlainTextEdit:focus {
                border-color: #1976D2;
                border-width: 2px;
            }
        """)
        layout.addWidget(group_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        save_btn = button_box.button(QDialogButtonBox.Save)
        cancel_btn = button_box.button(QDialogButtonBox.Cancel)
        if save_btn:
            save_btn.setText("保存")
        if cancel_btn:
            cancel_btn.setText("取消")

        clear_btn = QPushButton("清空")
        button_box.addButton(clear_btn, QDialogButtonBox.ActionRole)

        layout.addWidget(button_box)

        def _save_and_close():
            names = [name.strip() for name in group_edit.toPlainText().split('\n') if name.strip()]
            self._set_group_names(names, emit_change=True, show_message=True)
            dialog.accept()

        def _confirm_clear():
            reply = QMessageBox.question(
                self,
                "确认清空",
                "确定要清空所有群名吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                group_edit.clear()

        if save_btn:
            save_btn.clicked.connect(_save_and_close)
        clear_btn.clicked.connect(_confirm_clear)
        button_box.rejected.connect(dialog.reject)

        dialog.exec()

    def _set_group_names(self, names: List[str], *, emit_change: bool = False, show_message: bool = False):
        """更新群名列表并同步 UI/信号"""
        self._group_names = [name.strip() for name in names if name.strip()]
        self._update_group_button_label()

        if emit_change:
            self.group_names_changed.emit(self.channel, self._group_names)
            if show_message:
                QMessageBox.information(
                    self,
                    "保存成功",
                    f"已保存 {len(self._group_names)} 个群名",
                    QMessageBox.Ok
                )

    def _update_group_button_label(self):
        """更新群名配置按钮文案和提示"""
        if not hasattr(self, "group_config_btn"):
            return

        count = len(self._group_names)
        text = "⚙ 配置群名"
        if count:
            text += f" ({count})"
            preview = "\n".join(self._group_names[:3])
            if count > 3:
                preview += "\n..."
            tooltip = f"已配置 {count} 个群名:\n{preview}"
        else:
            tooltip = "点击配置要群发的群名（每行一个）"

        self.group_config_btn.setText(text)
        self.group_config_btn.setToolTip(tooltip)

    def _on_selection_changed(self):
        """选择变化"""
        selected = self.table_view.selectionModel().selectedRows()
        if selected:
            self.selection_label.setText(f"已选择 {len(selected)} 项")
            self.selection_label.setVisible(True)
        else:
            self.selection_label.setText("")
            self.selection_label.setVisible(False)

    def _update_stats(self):
        """更新统计信息"""
        total = self.table_model.rowCount()
        tasks = self.table_model.get_all_tasks()

        pending = sum(1 for t in tasks if t.status == TaskStatus.pending)
        success = sum(1 for t in tasks if t.status == TaskStatus.success)
        failed = sum(1 for t in tasks if t.status == TaskStatus.failed)

        stats_html = f"""
            <span style="color: #495057;">共 <b>{total}</b> 个</span>
            <span style="color: #ADB5BD;"> | </span>
            <span style="color: #6C757D;">待执行 <b>{pending}</b></span>
            <span style="color: #ADB5BD;"> | </span>
            <span style="color: #198754;">成功 <b>{success}</b></span>
            <span style="color: #ADB5BD;"> | </span>
            <span style="color: #DC3545;">失败 <b>{failed}</b></span>
        """
        self.stats_label.setText(stats_html)

    # 公共接口

    def load_tasks(self, tasks: list[Task]):
        """加载任务列表"""
        self.table_model.load_tasks(tasks)
        self._update_stats()

    def add_task(self, task: Task):
        """添加任务"""
        self.table_model.add_task(task)
        self._update_stats()

    def update_task_status(self, task_id: int, status: TaskStatus):
        """更新任务状态"""
        self.table_model.update_task_status(task_id, status)
        self._update_stats()

    def update_task_by_code(
        self,
        content_code: str,
        status: TaskStatus,
        executed_time: Optional[datetime] = None
    ):
        """通过 content_code 更新任务状态"""
        if self.table_model.update_task_by_code(content_code, status, executed_time):
            self._update_stats()

    def set_next_task_id(self, task_id: Optional[int]):
        """设置下一任务高亮"""
        self.table_model.set_next_task_id(task_id)

    def set_schedule_mode(self, mode: str):
        """设置调度模式 (interval/fixed_time)"""
        target_index = 1
        for i in range(self.schedule_mode_combo.count()):
            if self.schedule_mode_combo.itemData(i) == mode:
                target_index = i
                break
        self.schedule_mode_combo.blockSignals(True)
        self.schedule_mode_combo.setCurrentIndex(target_index)
        self.schedule_mode_combo.blockSignals(False)
        self.schedule_mode_stack.setCurrentIndex(0 if mode == "fixed_time" else 1)

    def get_schedule_mode(self) -> str:
        """获取调度模式"""
        return self.schedule_mode_combo.currentData()

    def set_interval(self, value: int, unit: str):
        """设置发布间隔"""
        self.interval_value_spin.blockSignals(True)
        self.interval_unit_combo.blockSignals(True)
        self.interval_value_spin.setValue(max(1, value))
        for i in range(self.interval_unit_combo.count()):
            if self.interval_unit_combo.itemData(i) == unit:
                self.interval_unit_combo.setCurrentIndex(i)
                break
        self.interval_value_spin.blockSignals(False)
        self.interval_unit_combo.blockSignals(False)

    def get_interval(self) -> tuple:
        """获取发布间隔 (value, unit)"""
        return (self.interval_value_spin.value(), self.interval_unit_combo.currentData())

    def set_minute_of_hour(self, minute: int):
        """设置每小时定点分钟 (0-59)"""
        self.minute_spin.setValue(minute)

    def get_minute_of_hour(self) -> int:
        """获取每小时定点分钟"""
        return self.minute_spin.value()

    def set_daily_window(self, start: str, end: str):
        """设置每日时间窗口"""
        start_time = QTime.fromString(start, "HH:mm")
        end_time = QTime.fromString(end, "HH:mm")
        if start_time.isValid():
            self.start_time_edit.setTime(start_time)
        if end_time.isValid():
            self.end_time_edit.setTime(end_time)

    def get_daily_window(self) -> tuple:
        """获取每日时间窗口 (start, end)"""
        start = self.start_time_edit.time().toString("HH:mm")
        end = self.end_time_edit.time().toString("HH:mm")
        return (start, end)

    def get_global_group_names(self) -> List[str]:
        """获取全局群名列表"""
        return list(self._group_names)

    def set_global_group_names(self, names: List[str]):
        """设置全局群名列表"""
        self._set_group_names(names, emit_change=False)

    def set_extra_message(self, text: str):
        """Set extra message text for this channel."""
        if hasattr(self, "extra_message_edit"):
            self.extra_message_edit.blockSignals(True)
            self.extra_message_edit.setText(text or "")
            self.extra_message_edit.blockSignals(False)

    def get_extra_message(self) -> str:
        """获取额外消息内容（群发后附加的文字）"""
        if hasattr(self, 'extra_message_edit'):
            return self.extra_message_edit.text().strip()
        return ""

    def set_publishing_state(self, is_publishing: bool):
        """设置发布状态"""
        self._is_publishing = is_publishing
        self.start_btn.setEnabled(not is_publishing)
        self.pause_btn.setEnabled(is_publishing)
        # 任务控制按钮仅在发布中启用
        self.pause_task_btn.setEnabled(is_publishing)
        self.stop_task_btn.setEnabled(is_publishing)
        # 如果停止发布，重置暂停状态
        if not is_publishing:
            self._is_task_paused = False
            self.pause_task_btn.setText("⏸ 暂停任务")
            self.pause_task_btn.setToolTip("暂停当前正在执行的任务")

    def clear_tasks(self):
        """清空任务"""
        self.table_model.clear()
        self._update_stats()

    def get_all_tasks(self) -> list[Task]:
        """获取所有任务"""
        return self.table_model.get_all_tasks()


class QueueTab(QWidget):
    """
    发布队列标签页

    功能：
    - 多渠道独立队列（朋友圈、代理群、客户群 + 自定义渠道）
    - 每个渠道独立的发布间隔设置
    - 任务拖拽排序
    - 右键菜单操作
    - 导入 Excel
    - 动态添加/删除自定义渠道
    """

    # 信号定义 - 使用 object 类型以支持 Channel 枚举和字符串
    task_execute_requested = Signal(Task)
    task_edit_requested = Signal(Task)
    task_cancel_requested = Signal(Task)
    task_delete_requested = Signal(Task)
    tasks_reordered = Signal(list)  # 任务顺序变更
    import_requested = Signal(str)
    extra_message_changed = Signal(object, str)  # channel, extra_message
    start_publishing_requested = Signal(object)  # channel (Channel枚举或字符串)
    pause_publishing_requested = Signal(object)  # channel
    stop_current_task_requested = Signal()  # 停止当前正在执行的任务
    pause_current_task_requested = Signal()  # 暂停/恢复当前正在执行的任务
    minute_of_hour_changed = Signal(object, int)  # channel, minute (0-59)
    schedule_mode_changed = Signal(object, str)  # channel, mode
    interval_changed = Signal(object, int, str)  # channel, value, unit
    daily_window_changed = Signal(object, str, str)  # channel, start, end
    group_names_changed = Signal(object, list)  # channel, group_names
    # 自定义渠道信号
    add_channel_requested = Signal(str)  # 渠道名称
    remove_channel_requested = Signal(str)  # 渠道ID
    # 清空任务信号
    clear_channel_requested = Signal(object)  # channel - 请求清空指定渠道
    clear_all_requested = Signal()  # 请求清空所有渠道

    def __init__(self, parent=None):
        super().__init__(parent)
        # 使用字典存储渠道组件，键为 Channel 枚举或字符串
        self._channel_widgets: Dict = {}
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 渠道标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                background-color: #FFFFFF;
            }
            QTabBar::tab {
                padding: 8px 20px;
                margin-right: 4px;
                border: 1px solid #E0E0E0;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                background-color: #F8F9FA;
            }
            QTabBar::tab:selected {
                background-color: #FFFFFF;
                border-bottom: 1px solid #FFFFFF;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background-color: #E9ECEF;
            }
        """)

        # 创建每个渠道的标签页
        channel_names = {
            Channel.moment: "朋友圈",
            Channel.agent_group: "代理群",
            Channel.customer_group: "客户群",
        }

        for channel in Channel:
            widget = ChannelQueueWidget(channel)
            self._channel_widgets[channel] = widget
            self.tab_widget.addTab(widget, channel_names.get(channel, channel.value))

        # 添加"+"按钮用于创建自定义渠道
        self.add_channel_btn = QPushButton("+")
        self.add_channel_btn.setFixedSize(28, 28)
        self.add_channel_btn.setToolTip("添加新渠道")
        self.add_channel_btn.setStyleSheet("""
            QPushButton {
                background-color: #E3F2FD;
                color: #1976D2;
                border: 1px solid #90CAF9;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #BBDEFB;
                border-color: #64B5F6;
            }
            QPushButton:pressed {
                background-color: #90CAF9;
            }
        """)
        self.add_channel_btn.setCursor(Qt.PointingHandCursor)

        # 创建一个容器来放置"+"按钮和提醒标签
        right_corner_widget = QWidget()
        right_corner_layout = QHBoxLayout(right_corner_widget)
        right_corner_layout.setContentsMargins(4, 0, 4, 0)
        right_corner_layout.setSpacing(8)
        right_corner_layout.addWidget(self.add_channel_btn)

        # 下一任务提示标签
        self.next_task_label = QLabel("下一任务: -")
        self.next_task_label.setStyleSheet("""
            QLabel {
                color: #0D47A1;
                font-size: 12px;
                padding: 4px 10px;
                background-color: #E3F2FD;
                border: 1px solid #90CAF9;
                border-radius: 4px;
            }
        """)
        right_corner_layout.addWidget(self.next_task_label)

        # 小程序提醒标签
        reminder_label = QLabel("⚠️ 请确认花城农夫小程序已打开")
        reminder_label.setStyleSheet("""
            QLabel {
                color: #E65100;
                font-size: 13px;
                padding: 4px 12px;
                background-color: #FFF3E0;
                border: 1px solid #FFB74D;
                border-radius: 4px;
            }
        """)
        right_corner_layout.addWidget(reminder_label)

        self.tab_widget.setCornerWidget(right_corner_widget, Qt.TopRightCorner)

        # 标签页右键菜单（用于删除自定义渠道）
        self.tab_widget.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab_widget.tabBar().customContextMenuRequested.connect(self._on_tab_context_menu)

        # 选取文件夹按钮（标签栏左侧，橙色强调样式）
        self.import_btn = QPushButton("📁 选取文件夹")
        self.import_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)
        self.import_btn.setCursor(Qt.PointingHandCursor)
        self.tab_widget.setCornerWidget(self.import_btn, Qt.TopLeftCorner)

        layout.addWidget(self.tab_widget)

        # 底部总体状态栏
        bottom_bar = self._create_bottom_bar()
        layout.addWidget(bottom_bar)

    def _create_bottom_bar(self) -> QFrame:
        """创建底部总体状态栏"""
        bar = QFrame()
        bar.setStyleSheet("""
            QFrame {
                background-color: #F8F9FA;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                padding: 10px;
            }
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(20)

        # 总体统计
        self.total_stats_label = QLabel("总计 0 个任务")
        self.total_stats_label.setTextFormat(Qt.RichText)
        self.total_stats_label.setStyleSheet("""
            QLabel {
                color: #495057;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.total_stats_label)

        layout.addStretch()

        # 进度展示
        self.progress_label = QLabel("进度: -")
        self.progress_label.setStyleSheet("""
            QLabel {
                color: #495057;
                font-size: 12px;
            }
        """)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setMinimumWidth(220)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #E9ECEF;
                border: 1px solid #DEE2E6;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 4px;
            }
        """)

        progress_container = QWidget()
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar, 1)
        progress_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(progress_container, 1)

        layout.addStretch()

        # 清空全部任务按钮
        self.clear_all_btn = QPushButton("🗑️ 清空全部任务")
        self.clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #DC3545;
                border: 1px solid #DC3545;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #DC3545;
                color: white;
            }
            QPushButton:pressed {
                background-color: #C82333;
                color: white;
            }
            QPushButton:disabled {
                border-color: #BDBDBD;
                color: #BDBDBD;
            }
        """)
        self.clear_all_btn.setCursor(Qt.PointingHandCursor)
        self.clear_all_btn.setToolTip("清空所有渠道的所有任务")
        layout.addWidget(self.clear_all_btn)

        return bar

    def update_progress(self, text: str, percent: Optional[int] = None):
        """更新进度显示"""
        if not hasattr(self, "progress_label"):
            return
        display_text = text or "进度: -"
        self.progress_label.setText(display_text)
        if percent is None or percent < 0:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(max(0, min(100, percent)))

    def clear_progress(self):
        """清空进度显示"""
        self.update_progress("进度: -", 0)

    def _connect_signals(self):
        """连接信号"""
        self.import_btn.clicked.connect(self.import_folder)
        self.add_channel_btn.clicked.connect(self._on_add_channel_clicked)
        self.clear_all_btn.clicked.connect(self._on_clear_all_clicked)

        # 连接每个渠道组件的信号
        for channel, widget in self._channel_widgets.items():
            self._connect_channel_widget_signals(widget)

    def _connect_channel_widget_signals(self, widget: ChannelQueueWidget):
        """连接单个渠道组件的信号"""
        widget.task_execute_requested.connect(self.task_execute_requested.emit)
        widget.task_edit_requested.connect(self.task_edit_requested.emit)
        widget.task_cancel_requested.connect(self.task_cancel_requested.emit)
        widget.task_delete_requested.connect(self.task_delete_requested.emit)
        widget.tasks_reordered.connect(self.tasks_reordered.emit)
        widget.start_publishing_requested.connect(self.start_publishing_requested.emit)
        widget.pause_publishing_requested.connect(self.pause_publishing_requested.emit)
        widget.stop_current_task_requested.connect(self.stop_current_task_requested.emit)
        widget.pause_current_task_requested.connect(self.pause_current_task_requested.emit)
        widget.minute_of_hour_changed.connect(self.minute_of_hour_changed.emit)
        widget.schedule_mode_changed.connect(self.schedule_mode_changed.emit)
        widget.interval_changed.connect(self.interval_changed.emit)
        widget.daily_window_changed.connect(self.daily_window_changed.emit)
        widget.group_names_changed.connect(self.group_names_changed.emit)
        widget.extra_message_changed.connect(self.extra_message_changed.emit)
        widget.clear_channel_requested.connect(self._on_channel_clear_requested)

        # 监听统计更新
        widget.table_model.rowsInserted.connect(self._update_total_stats)
        widget.table_model.rowsRemoved.connect(self._update_total_stats)
        widget.table_model.modelReset.connect(self._update_total_stats)
        widget.table_model.dataChanged.connect(self._update_total_stats)

    def _update_total_stats(self):
        """更新总体统计"""
        total = 0
        pending = 0
        success = 0
        failed = 0

        for widget in self._channel_widgets.values():
            tasks = widget.get_all_tasks()
            total += len(tasks)
            pending += sum(1 for t in tasks if t.status == TaskStatus.pending)
            success += sum(1 for t in tasks if t.status == TaskStatus.success)
            failed += sum(1 for t in tasks if t.status == TaskStatus.failed)

        stats_html = f"""
            <span style="color: #495057;">总计 <b>{total}</b> 个任务</span>
            <span style="color: #ADB5BD;"> │ </span>
            <span style="color: #6C757D;">待执行: <b>{pending}</b></span>
            <span style="color: #ADB5BD;"> │ </span>
            <span style="color: #198754;">成功: <b>{success}</b></span>
            <span style="color: #ADB5BD;"> │ </span>
            <span style="color: #DC3545;">失败: <b>{failed}</b></span>
        """
        self.total_stats_label.setText(stats_html)

    # ==================== 清空任务处理 ====================

    def _on_channel_clear_requested(self, channel):
        """转发渠道清空请求"""
        self.clear_channel_requested.emit(channel)

    def _on_clear_all_clicked(self):
        """清空所有渠道的所有任务"""
        total_count = sum(
            widget.table_model.rowCount()
            for widget in self._channel_widgets.values()
        )

        if total_count == 0:
            QMessageBox.information(
                self,
                "提示",
                "所有队列已经是空的",
                QMessageBox.Ok
            )
            return

        # 构建详情文本
        details = []
        for channel, widget in self._channel_widgets.items():
            count = widget.table_model.rowCount()
            if count > 0:
                channel_name = Channel.get_display_name(channel)
                details.append(f"  • {channel_name}: {count} 个任务")

        # 确认对话框
        reply = QMessageBox.warning(
            self,
            "确认清空全部",
            f"确定要删除所有渠道的全部 {total_count} 个任务吗？\n\n"
            f"包含：\n" + "\n".join(details) + "\n\n"
            f"此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.clear_all_requested.emit()

    # ==================== 自定义渠道管理 ====================

    def _on_add_channel_clicked(self):
        """点击添加渠道按钮"""
        name, ok = QInputDialog.getText(
            self, "添加渠道", "请输入渠道名称:",
            QLineEdit.Normal, ""
        )
        if ok and name.strip():
            self.add_channel_requested.emit(name.strip())

    def _on_tab_context_menu(self, pos):
        """标签页右键菜单"""
        tab_index = self.tab_widget.tabBar().tabAt(pos)
        if tab_index < 0:
            return

        # 获取渠道ID
        widget = self.tab_widget.widget(tab_index)
        channel_id = self._get_channel_id_by_widget(widget)

        # 只有自定义渠道可以删除
        if not Channel.is_custom_channel(channel_id):
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #FFEBEE;
            }
        """)
        delete_action = menu.addAction("🗑️ 删除此渠道")
        action = menu.exec_(self.tab_widget.tabBar().mapToGlobal(pos))

        if action == delete_action:
            channel_name = self.tab_widget.tabText(tab_index)
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除渠道「{channel_name}」吗？\n该渠道的所有任务也将被删除。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.remove_channel_requested.emit(channel_id)

    def _get_channel_id_by_widget(self, widget):
        """根据组件获取渠道ID"""
        for channel_id, w in self._channel_widgets.items():
            if w == widget:
                return channel_id
        return None

    def add_custom_channel(self, channel_id: str, name: str):
        """添加自定义渠道标签页"""
        widget = ChannelQueueWidget(channel_id)
        self._channel_widgets[channel_id] = widget
        self.tab_widget.addTab(widget, name)
        # 连接信号
        self._connect_channel_signals(widget)

    def remove_custom_channel(self, channel_id: str):
        """移除自定义渠道标签页"""
        if channel_id in self._channel_widgets:
            widget = self._channel_widgets[channel_id]
            index = self.tab_widget.indexOf(widget)
            if index >= 0:
                self.tab_widget.removeTab(index)
            del self._channel_widgets[channel_id]
            self._update_total_stats()

    def _connect_channel_signals(self, widget: ChannelQueueWidget):
        """连接渠道组件的信号（用于动态添加的自定义渠道）"""
        self._connect_channel_widget_signals(widget)

    def load_custom_channels(self, custom_channels: dict):
        """加载已保存的自定义渠道

        Args:
            custom_channels: {channel_id: {"name": "渠道名", ...}, ...}
        """
        for channel_id, channel_config in custom_channels.items():
            name = channel_config.get("name", channel_id)
            self.add_custom_channel(channel_id, name)

    # 公共接口

    def load_tasks(self, tasks: list[Task]):
        """
        加载任务列表，自动分配到对应渠道（支持内置渠道和自定义渠道）

        Args:
            tasks: 任务列表
        """
        # 按渠道分组（支持 Channel 枚举和字符串）
        channel_tasks: Dict = {}
        for channel_id in self._channel_widgets.keys():
            channel_tasks[channel_id] = []

        for task in tasks:
            channel = task.channel
            # 兼容：Channel 枚举和字符串都可以
            if channel in channel_tasks:
                channel_tasks[channel].append(task)
            elif isinstance(channel, Channel) and channel in channel_tasks:
                channel_tasks[channel].append(task)

        # 加载到对应渠道
        for channel, ch_tasks in channel_tasks.items():
            if channel in self._channel_widgets:
                self._channel_widgets[channel].load_tasks(ch_tasks)

        self._update_total_stats()

    def add_task(self, task: Task):
        """添加任务到对应渠道"""
        if task.channel in self._channel_widgets:
            self._channel_widgets[task.channel].add_task(task)
        self._update_total_stats()

    def update_task_status(self, task_id: int, status: TaskStatus, channel: Channel = None):
        """更新任务状态"""
        if channel and channel in self._channel_widgets:
            self._channel_widgets[channel].update_task_status(task_id, status)
        else:
            # 如果未指定渠道，在所有渠道中查找
            for widget in self._channel_widgets.values():
                widget.update_task_status(task_id, status)
        self._update_total_stats()

    def update_task_by_code(
        self,
        content_code: str,
        status: TaskStatus,
        channel: Channel = None,
        executed_time: Optional[datetime] = None
    ):
        """通过 content_code 更新任务状态"""
        if channel and channel in self._channel_widgets:
            self._channel_widgets[channel].update_task_by_code(content_code, status, executed_time)
        else:
            for widget in self._channel_widgets.values():
                widget.update_task_by_code(content_code, status, executed_time)

    def set_next_task_hint(self, text: str):
        """设置下一任务提示文本"""
        if hasattr(self, "next_task_label"):
            self.next_task_label.setText(text)
            self.next_task_label.setToolTip(text)

    def set_next_task_highlight(self, task: Optional[Task]):
        """设置下一任务高亮"""
        for widget in self._channel_widgets.values():
            widget.set_next_task_id(None)

        if not task:
            return

        target_key = task.channel
        widget = self._channel_widgets.get(target_key)
        if widget:
            widget.set_next_task_id(task.id)
        self._update_total_stats()

    def get_channel_widget(self, channel: Channel) -> Optional[ChannelQueueWidget]:
        """获取指定渠道的组件"""
        return self._channel_widgets.get(channel)

    def set_channel_minute_of_hour(self, channel: Channel, minute: int):
        """设置渠道每小时定点分钟"""
        if channel in self._channel_widgets:
            self._channel_widgets[channel].set_minute_of_hour(minute)

    def set_channel_schedule_mode(self, channel: Channel, mode: str):
        """设置渠道调度模式"""
        if channel in self._channel_widgets:
            self._channel_widgets[channel].set_schedule_mode(mode)

    def set_channel_interval(self, channel: Channel, value: int, unit: str):
        """设置渠道发布间隔"""
        if channel in self._channel_widgets:
            self._channel_widgets[channel].set_interval(value, unit)

    def set_channel_daily_window(self, channel: Channel, start: str, end: str):
        """设置渠道每日时间窗口"""
        if channel in self._channel_widgets:
            self._channel_widgets[channel].set_daily_window(start, end)

    def set_publishing_state(self, channel_or_state=None, is_publishing: bool = None):
        """设置渠道发布状态

        支持两种调用方式：
        - set_publishing_state(True/False) - 设置所有渠道
        - set_publishing_state(channel, True/False) - 设置指定渠道
        """
        # 兼容旧调用方式：set_publishing_state(True)
        if isinstance(channel_or_state, bool):
            is_publishing = channel_or_state
            for widget in self._channel_widgets.values():
                widget.set_publishing_state(is_publishing)
        elif channel_or_state is None:
            # 设置所有渠道
            if is_publishing is not None:
                for widget in self._channel_widgets.values():
                    widget.set_publishing_state(is_publishing)
        elif channel_or_state in self._channel_widgets:
            # 设置指定渠道
            if is_publishing is not None:
                self._channel_widgets[channel_or_state].set_publishing_state(is_publishing)

    def import_folder(self):
        """选取文件夹导入（自动查找汇总Excel和匹配图片）"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择素材文件夹",
            ""
        )

        if folder_path:
            self.import_requested.emit(folder_path)

    def clear_tasks(self, channel: Channel = None):
        """清空任务"""
        if channel:
            if channel in self._channel_widgets:
                self._channel_widgets[channel].clear_tasks()
        else:
            for widget in self._channel_widgets.values():
                widget.clear_tasks()
        self._update_total_stats()

    def get_all_tasks(self) -> list[Task]:
        """获取所有渠道的任务"""
        tasks = []
        for widget in self._channel_widgets.values():
            tasks.extend(widget.get_all_tasks())
        return tasks

    def get_tasks_by_channel(self, channel: Channel) -> list[Task]:
        """获取指定渠道的任务"""
        if channel in self._channel_widgets:
            return self._channel_widgets[channel].get_all_tasks()
        return []
