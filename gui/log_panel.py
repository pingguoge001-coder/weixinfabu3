"""实时日志面板 - 日志显示和过滤"""

import logging
from typing import Optional
from datetime import datetime
from collections import deque

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QComboBox, QLineEdit,
    QCheckBox, QLabel, QDockWidget, QFrame,
)
from PySide6.QtCore import Qt, Signal, QObject, Slot
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor, QFont

from .styles import Theme, BUTTON_STYLE


# 日志级别颜色映射
LOG_LEVEL_COLORS = {
    logging.DEBUG: "#9E9E9E",      # 灰色
    logging.INFO: "#2196F3",       # 蓝色
    logging.WARNING: "#FF9800",    # 橙色
    logging.ERROR: "#F44336",      # 红色
    logging.CRITICAL: "#9C27B0",   # 紫色
}

# 日志级别名称
LOG_LEVEL_NAMES = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRITICAL",
}


class LogRecord:
    """日志记录"""

    def __init__(
        self,
        level: int,
        message: str,
        timestamp: Optional[datetime] = None,
        logger_name: str = ""
    ):
        self.level = level
        self.message = message
        self.timestamp = timestamp or datetime.now()
        self.logger_name = logger_name

    def format(self) -> str:
        """格式化日志记录"""
        time_str = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        level_str = LOG_LEVEL_NAMES.get(self.level, "UNKNOWN")
        name_str = f"[{self.logger_name}]" if self.logger_name else ""
        return f"{time_str} {level_str:8} {name_str} {self.message}"


class LogSignalEmitter(QObject):
    """日志信号发射器 - 用于跨线程通信"""
    log_received = Signal(object)  # LogRecord


class LogHandler(logging.Handler):
    """Qt日志处理器 - 将日志转发到GUI"""

    def __init__(self):
        super().__init__()
        self._emitter = LogSignalEmitter()
        self.setFormatter(logging.Formatter('%(message)s'))

    @property
    def signal(self) -> Signal:
        """获取日志信号"""
        return self._emitter.log_received

    def emit(self, record: logging.LogRecord):
        """处理日志记录"""
        try:
            log_record = LogRecord(
                level=record.levelno,
                message=self.format(record),
                timestamp=datetime.fromtimestamp(record.created),
                logger_name=record.name
            )
            self._emitter.log_received.emit(log_record)
        except Exception:
            self.handleError(record)


class LogPanel(QWidget):
    """日志面板组件"""

    # 常量
    MAX_LINES = 10000  # 最大行数（增加到10000以避免频繁截断）

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._log_buffer: deque = deque(maxlen=self.MAX_LINES)
        self._filter_level = logging.DEBUG
        self._filter_keyword = ""
        self._auto_scroll = True
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # === 工具栏 ===
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        # 日志级别筛选
        toolbar.addWidget(QLabel("级别:"))
        self._combo_level = QComboBox()
        self._combo_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self._combo_level.setCurrentText("DEBUG")
        self._combo_level.setStyleSheet(f"""
            QComboBox {{
                padding: 4px 8px;
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                background-color: {Theme.SURFACE};
                color: {Theme.TEXT_PRIMARY};
                min-width: 100px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Theme.SURFACE};
                color: {Theme.TEXT_PRIMARY};
                selection-background-color: {Theme.PRIMARY};
            }}
        """)
        toolbar.addWidget(self._combo_level)

        # 关键词搜索
        toolbar.addWidget(QLabel("搜索:"))
        self._edit_search = QLineEdit()
        self._edit_search.setPlaceholderText("输入关键词...")
        self._edit_search.setStyleSheet(f"""
            QLineEdit {{
                padding: 4px 8px;
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                background-color: {Theme.SURFACE};
                color: {Theme.TEXT_PRIMARY};
                min-width: 150px;
            }}
            QLineEdit:focus {{
                border-color: {Theme.PRIMARY};
            }}
        """)
        toolbar.addWidget(self._edit_search)

        # 自动滚动复选框
        self._check_auto_scroll = QCheckBox("自动滚动")
        self._check_auto_scroll.setChecked(True)
        self._check_auto_scroll.setStyleSheet(f"""
            QCheckBox {{
                color: {Theme.TEXT_PRIMARY};
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
        """)
        toolbar.addWidget(self._check_auto_scroll)

        toolbar.addStretch()

        # 清空按钮
        self._btn_clear = QPushButton("清空")
        self._btn_clear.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.SURFACE};
                color: {Theme.TEXT_PRIMARY};
                padding: 4px 12px;
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {Theme.HOVER};
            }}
        """)
        toolbar.addWidget(self._btn_clear)

        layout.addLayout(toolbar)

        # === 日志显示区域 ===
        self._text_log = QTextEdit()
        self._text_log.setReadOnly(True)
        self._text_log.setFont(QFont("Consolas", 10))
        self._text_log.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        self._text_log.setLineWrapMode(QTextEdit.NoWrap)
        layout.addWidget(self._text_log)

        # === 状态栏 ===
        status_layout = QHBoxLayout()
        self._lbl_status = QLabel("共 0 条日志")
        self._lbl_status.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        status_layout.addWidget(self._lbl_status)
        status_layout.addStretch()
        layout.addLayout(status_layout)

    def _connect_signals(self):
        """连接信号"""
        self._combo_level.currentTextChanged.connect(self._on_level_changed)
        self._edit_search.textChanged.connect(self._on_search_changed)
        self._check_auto_scroll.toggled.connect(self._on_auto_scroll_toggled)
        self._btn_clear.clicked.connect(self.clear)

    def _on_level_changed(self, level_text: str):
        """日志级别改变"""
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        self._filter_level = level_map.get(level_text, logging.DEBUG)
        self._refresh_display()

    def _on_search_changed(self, keyword: str):
        """搜索关键词改变"""
        self._filter_keyword = keyword.strip()
        self._refresh_display()

    def _on_auto_scroll_toggled(self, checked: bool):
        """自动滚动切换"""
        self._auto_scroll = checked

    @Slot(object)
    def append_log(self, record: LogRecord):
        """添加日志记录"""
        self._log_buffer.append(record)

        # 检查是否需要显示
        if self._should_display(record):
            self._append_to_display(record)
            self._update_status()

            # 自动滚动
            if self._auto_scroll:
                self._text_log.verticalScrollBar().setValue(
                    self._text_log.verticalScrollBar().maximum()
                )

    def _should_display(self, record: LogRecord) -> bool:
        """检查日志是否应该显示"""
        # 级别过滤
        if record.level < self._filter_level:
            return False

        # 关键词过滤
        if self._filter_keyword:
            if self._filter_keyword.lower() not in record.message.lower():
                return False

        return True

    def _append_to_display(self, record: LogRecord):
        """追加到显示区域"""
        cursor = self._text_log.textCursor()
        cursor.movePosition(QTextCursor.End)

        # 设置颜色
        fmt = QTextCharFormat()
        color = LOG_LEVEL_COLORS.get(record.level, "#D4D4D4")
        fmt.setForeground(QColor(color))

        # 插入文本
        formatted_text = record.format()

        # 高亮关键词
        if self._filter_keyword:
            formatted_text = self._highlight_keyword(formatted_text, self._filter_keyword)

        cursor.insertText(formatted_text + "\n", fmt)

    def _highlight_keyword(self, text: str, keyword: str) -> str:
        """高亮关键词（在终端显示中不实际高亮，但保持逻辑）"""
        # 在纯文本中无法真正高亮，这里保持原样
        # 如果需要可以使用HTML格式
        return text

    def _refresh_display(self):
        """刷新显示（优化性能：禁用更新信号后批量处理）"""
        # 禁用 UI 更新以提升批量操作性能
        self._text_log.setUpdatesEnabled(False)
        try:
            self._text_log.clear()

            for record in self._log_buffer:
                if self._should_display(record):
                    self._append_to_display(record)

            self._update_status()
        finally:
            # 恢复 UI 更新
            self._text_log.setUpdatesEnabled(True)

        # 滚动到底部
        if self._auto_scroll:
            self._text_log.verticalScrollBar().setValue(
                self._text_log.verticalScrollBar().maximum()
            )

    def _update_status(self):
        """更新状态栏"""
        total = len(self._log_buffer)
        displayed = sum(1 for r in self._log_buffer if self._should_display(r))
        self._lbl_status.setText(f"显示 {displayed} / 共 {total} 条日志")

    def clear(self):
        """清空日志"""
        self._log_buffer.clear()
        self._text_log.clear()
        self._update_status()

    def add_info(self, message: str):
        """添加INFO级别日志"""
        record = LogRecord(logging.INFO, message)
        self.append_log(record)

    def add_warning(self, message: str):
        """添加WARNING级别日志"""
        record = LogRecord(logging.WARNING, message)
        self.append_log(record)

    def add_error(self, message: str):
        """添加ERROR级别日志"""
        record = LogRecord(logging.ERROR, message)
        self.append_log(record)

    def add_debug(self, message: str):
        """添加DEBUG级别日志"""
        record = LogRecord(logging.DEBUG, message)
        self.append_log(record)

    def connect_handler(self, handler: LogHandler):
        """连接日志处理器"""
        handler.signal.connect(self.append_log)


class LogDockWidget(QDockWidget):
    """可停靠的日志面板"""

    def __init__(self, title: str = "日志", parent: Optional[QWidget] = None):
        super().__init__(title, parent)
        self._log_panel = LogPanel()
        self.setWidget(self._log_panel)

        # 设置停靠属性
        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable
        )

        # 样式
        self.setStyleSheet(f"""
            QDockWidget {{
                color: {Theme.TEXT_PRIMARY};
                font-weight: bold;
            }}
            QDockWidget::title {{
                background-color: {Theme.SURFACE};
                padding: 8px;
                border-bottom: 1px solid {Theme.BORDER};
            }}
        """)

    @property
    def log_panel(self) -> LogPanel:
        """获取日志面板"""
        return self._log_panel


def setup_gui_logging(log_panel: LogPanel, logger_name: str = "") -> LogHandler:
    """设置GUI日志处理

    Args:
        log_panel: 日志面板组件
        logger_name: 日志器名称，空字符串表示根日志器

    Returns:
        LogHandler实例
    """
    handler = LogHandler()
    handler.setLevel(logging.DEBUG)

    # 获取日志器
    logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()

    # 添加处理器
    logger.addHandler(handler)

    # 连接到日志面板
    log_panel.connect_handler(handler)

    return handler
