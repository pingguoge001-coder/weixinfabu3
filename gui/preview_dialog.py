"""发布预览对话框 - 展示待发布内容的详细预览"""

from typing import Optional, List
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTextEdit, QFrame, QScrollArea,
    QGroupBox, QSizePolicy, QWidget,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap, QImage, QFont

from .styles import Theme, BUTTON_STYLE, get_status_badge_html
from models.content import Content
from models.task import Task
from models.enums import Channel


class ThumbnailLabel(QLabel):
    """缩略图标签组件"""

    clicked = Signal(str)  # 点击时发送图片路径

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._image_path: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setFixedSize(200, 200)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
            }}
        """)
        self.setScaledContents(False)
        self._show_placeholder()

    def _show_placeholder(self):
        """显示占位符"""
        self.setText("暂无图片")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {Theme.SURFACE};
                border: 1px dashed {Theme.BORDER};
                border-radius: 8px;
                color: {Theme.TEXT_SECONDARY};
                font-size: 14px;
            }}
        """)

    def set_image(self, image_path: str):
        """设置图片"""
        self._image_path = image_path
        path = Path(image_path)

        if not path.exists():
            self._show_placeholder()
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._show_placeholder()
            return

        # 缩放到适合大小，保持比例
        scaled = pixmap.scaled(
            190, 190,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.setPixmap(scaled)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
                padding: 4px;
            }}
        """)

    def clear_image(self):
        """清除图片"""
        self._image_path = None
        self.clear()
        self._show_placeholder()

    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if self._image_path:
            self.clicked.emit(self._image_path)
        super().mousePressEvent(event)


class ImageGrid(QWidget):
    """3x3图片网格组件"""

    image_clicked = Signal(str)  # 图片点击信号

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._thumbnails: List[ThumbnailLabel] = []
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QGridLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # 创建3x3网格
        for row in range(3):
            for col in range(3):
                thumbnail = ThumbnailLabel()
                thumbnail.clicked.connect(self.image_clicked.emit)
                self._thumbnails.append(thumbnail)
                layout.addWidget(thumbnail, row, col)

    def set_images(self, image_paths: List[str]):
        """设置图片列表"""
        # 清空所有缩略图
        for thumb in self._thumbnails:
            thumb.clear_image()

        # 设置新图片（最多9张）
        for i, path in enumerate(image_paths[:9]):
            self._thumbnails[i].set_image(path)

    def clear(self):
        """清空所有图片"""
        for thumb in self._thumbnails:
            thumb.clear_image()


class PreviewDialog(QDialog):
    """发布预览对话框"""

    # 信号
    confirmed = Signal()  # 确认发布
    cancelled = Signal()  # 取消发布

    def __init__(
        self,
        content: Optional[Content] = None,
        task: Optional[Task] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._content = content
        self._task = task
        self._setup_ui()
        self._connect_signals()

        if content:
            self.set_content(content)
        if task:
            self.set_task(task)

    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("发布预览")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.BACKGROUND};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # === 内容区域（左右分栏）===
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # --- 左侧：文本内容和发布信息 ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        # 发布信息区
        info_group = QGroupBox("发布信息")
        info_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid {Theme.BORDER};
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px;
                background-color: {Theme.SURFACE};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
            }}
        """)
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(8)

        # 内容编码
        info_layout.addWidget(self._create_label("内容编码:"), 0, 0)
        self._lbl_content_code = QLabel("-")
        self._lbl_content_code.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-weight: bold;")
        info_layout.addWidget(self._lbl_content_code, 0, 1)

        # 发布渠道
        info_layout.addWidget(self._create_label("发布渠道:"), 1, 0)
        self._lbl_channel = QLabel("-")
        info_layout.addWidget(self._lbl_channel, 1, 1)

        # 目标群组
        info_layout.addWidget(self._create_label("目标群组:"), 2, 0)
        self._lbl_group = QLabel("-")
        info_layout.addWidget(self._lbl_group, 2, 1)

        # 计划时间
        info_layout.addWidget(self._create_label("计划时间:"), 3, 0)
        self._lbl_scheduled_time = QLabel("-")
        info_layout.addWidget(self._lbl_scheduled_time, 3, 1)

        # 状态
        info_layout.addWidget(self._create_label("当前状态:"), 4, 0)
        self._lbl_status = QLabel("-")
        info_layout.addWidget(self._lbl_status, 4, 1)

        # 图片数量
        info_layout.addWidget(self._create_label("图片数量:"), 5, 0)
        self._lbl_image_count = QLabel("0")
        info_layout.addWidget(self._lbl_image_count, 5, 1)

        left_layout.addWidget(info_group)

        # 文本内容区
        text_group = QGroupBox("发布文案")
        text_group.setStyleSheet(info_group.styleSheet())
        text_layout = QVBoxLayout(text_group)

        self._text_content = QTextEdit()
        self._text_content.setReadOnly(True)
        self._text_content.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Theme.BACKGROUND};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 8px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 14px;
                line-height: 1.6;
            }}
        """)
        self._text_content.setMinimumHeight(200)
        text_layout.addWidget(self._text_content)

        left_layout.addWidget(text_group)
        left_layout.addStretch()

        content_layout.addWidget(left_panel, stretch=1)

        # --- 右侧：图片预览网格 ---
        right_panel = QGroupBox("图片预览")
        right_panel.setStyleSheet(info_group.styleSheet())
        right_layout = QVBoxLayout(right_panel)

        self._image_grid = ImageGrid()
        right_layout.addWidget(self._image_grid)

        # 图片提示
        hint_label = QLabel("点击图片可查看大图")
        hint_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        hint_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(hint_label)

        content_layout.addWidget(right_panel, stretch=1)

        main_layout.addLayout(content_layout)

        # === 底部按钮区域 ===
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.SURFACE};
                color: {Theme.TEXT_PRIMARY};
                padding: 10px 24px;
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {Theme.HOVER};
            }}
        """)
        self._btn_cancel.setMinimumWidth(100)
        button_layout.addWidget(self._btn_cancel)

        self._btn_confirm = QPushButton("确认发布")
        self._btn_confirm.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.PRIMARY};
                color: white;
                padding: 10px 24px;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #1976D2;
            }}
            QPushButton:pressed {{
                background-color: #1565C0;
            }}
        """)
        self._btn_confirm.setMinimumWidth(120)
        button_layout.addWidget(self._btn_confirm)

        main_layout.addLayout(button_layout)

    def _create_label(self, text: str) -> QLabel:
        """创建标签"""
        label = QLabel(text)
        label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
        return label

    def _connect_signals(self):
        """连接信号"""
        self._btn_confirm.clicked.connect(self._on_confirm)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._image_grid.image_clicked.connect(self._on_image_clicked)

    def _on_confirm(self):
        """确认按钮点击"""
        self.confirmed.emit()
        self.accept()

    def _on_cancel(self):
        """取消按钮点击"""
        self.cancelled.emit()
        self.reject()

    def _on_image_clicked(self, image_path: str):
        """图片点击，显示大图"""
        dialog = QDialog(self)
        dialog.setWindowTitle("图片预览")
        dialog.setMinimumSize(800, 600)

        layout = QVBoxLayout(dialog)

        # 图片标签
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)

        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            # 缩放到对话框大小
            scaled = pixmap.scaled(
                780, 560,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            label.setPixmap(scaled)

        layout.addWidget(label)

        # 关闭按钮
        btn_close = QPushButton("关闭")
        btn_close.setStyleSheet(BUTTON_STYLE)
        btn_close.clicked.connect(dialog.close)
        layout.addWidget(btn_close, alignment=Qt.AlignCenter)

        dialog.exec()

    def set_content(self, content: Content):
        """设置内容对象"""
        self._content = content

        self._lbl_content_code.setText(content.content_code)
        self._text_content.setText(content.text or "（无文案）")

        # 设置图片
        if content.image_paths:
            self._image_grid.set_images(content.image_paths)
            self._lbl_image_count.setText(str(len(content.image_paths)))
        else:
            self._image_grid.clear()
            self._lbl_image_count.setText("0")

    def set_task(self, task: Task):
        """设置任务对象"""
        self._task = task

        self._lbl_content_code.setText(task.content_code)

        # 渠道
        channel_text = "朋友圈" if task.channel == Channel.moment else "群发"
        self._lbl_channel.setText(channel_text)

        # 群组
        self._lbl_group.setText(task.group_name or "-")

        # 计划时间
        if task.scheduled_time:
            self._lbl_scheduled_time.setText(
                task.scheduled_time.strftime("%Y-%m-%d %H:%M")
            )
        else:
            self._lbl_scheduled_time.setText("-")

        # 状态（使用HTML badge）
        self._lbl_status.setText(get_status_badge_html(task.status))
        self._lbl_status.setTextFormat(Qt.RichText)

    def set_preview_data(
        self,
        content_code: str = "",
        channel: str = "",
        group_name: str = "",
        scheduled_time: str = "",
        status_html: str = "",
        text: str = "",
        images: Optional[List[str]] = None
    ):
        """直接设置预览数据（不通过Content/Task对象）"""
        self._lbl_content_code.setText(content_code or "-")
        self._lbl_channel.setText(channel or "-")
        self._lbl_group.setText(group_name or "-")
        self._lbl_scheduled_time.setText(scheduled_time or "-")

        if status_html:
            self._lbl_status.setText(status_html)
            self._lbl_status.setTextFormat(Qt.RichText)
        else:
            self._lbl_status.setText("-")

        self._text_content.setText(text or "（无文案）")

        if images:
            self._image_grid.set_images(images)
            self._lbl_image_count.setText(str(len(images)))
        else:
            self._image_grid.clear()
            self._lbl_image_count.setText("0")
