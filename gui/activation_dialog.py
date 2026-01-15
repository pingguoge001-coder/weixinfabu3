"""
激活对话框模块

提供软件激活界面，包括：
- 显示激活状态
- 输入激活码
- 激活/续期功能
"""

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCloseEvent

from services.activation_service import ActivationService, ActivationStatus

logger = logging.getLogger(__name__)


# 样式常量
DIALOG_MIN_WIDTH = 450
DIALOG_MIN_HEIGHT = 350

# 状态颜色
COLOR_SUCCESS = "#4CAF50"
COLOR_WARNING = "#FF9800"
COLOR_ERROR = "#F44336"
COLOR_INFO = "#2196F3"


class ActivationDialog(QDialog):
    """
    激活对话框

    用于显示激活状态、输入激活码、执行激活操作
    """

    # 信号：激活成功
    activation_success = Signal()

    def __init__(
        self,
        activation_service: ActivationService,
        status: Optional[ActivationStatus] = None,
        parent=None
    ):
        """
        初始化激活对话框

        Args:
            activation_service: 激活服务实例
            status: 当前激活状态（可选）
            parent: 父窗口
        """
        super().__init__(parent)

        self._service = activation_service
        self._status = status
        self._is_activated = False

        self._setup_ui()
        self._connect_signals()

        # 更新状态显示
        if status:
            self._update_status_display(status)

    def _setup_ui(self):
        """设置 UI"""
        self.setWindowTitle("软件激活")
        self.setMinimumSize(DIALOG_MIN_WIDTH, DIALOG_MIN_HEIGHT)
        self.setModal(True)

        # 禁止关闭按钮（未激活时）
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )

        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # 标题
        title_label = QLabel("微信自动发布工具")
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #1976D2; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # 状态区域
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #F5F5F5;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(16, 16, 16, 16)
        status_layout.setSpacing(8)

        # 激活状态标签
        self.status_label = QLabel("检查激活状态...")
        self.status_label.setFont(QFont("Microsoft YaHei", 14))
        self.status_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.status_label)

        # 到期时间/剩余天数
        self.expire_label = QLabel("")
        self.expire_label.setFont(QFont("Microsoft YaHei", 12))
        self.expire_label.setAlignment(Qt.AlignCenter)
        self.expire_label.setStyleSheet("color: #757575;")
        status_layout.addWidget(self.expire_label)

        # 设备ID
        self.device_label = QLabel(f"设备ID: {self._service.device_id[:16]}...")
        self.device_label.setFont(QFont("Microsoft YaHei", 10))
        self.device_label.setAlignment(Qt.AlignCenter)
        self.device_label.setStyleSheet("color: #9E9E9E;")
        status_layout.addWidget(self.device_label)

        layout.addWidget(status_frame)

        # 激活码输入区域
        input_frame = QFrame()
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(10)

        input_label = QLabel("请输入激活码:")
        input_label.setFont(QFont("Microsoft YaHei", 12))
        input_layout.addWidget(input_label)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("ACTV-XXX-XXXXXXXX")
        self.code_input.setFont(QFont("Consolas", 14))
        self.code_input.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                padding: 12px 16px;
                font-size: 16px;
            }
            QLineEdit:focus {
                border-color: #1976D2;
            }
        """)
        input_layout.addWidget(self.code_input)

        layout.addWidget(input_frame)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        # 退出按钮
        self.exit_btn = QPushButton("退出程序")
        self.exit_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5;
                color: #757575;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #EEEEEE;
            }
        """)
        button_layout.addWidget(self.exit_btn)

        # 激活按钮
        self.activate_btn = QPushButton("立即激活")
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 32px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        button_layout.addWidget(self.activate_btn)

        layout.addLayout(button_layout)

        # 进入按钮（激活成功后显示）
        self.enter_btn = QPushButton("进入程序")
        self.enter_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 32px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        self.enter_btn.hide()
        layout.addWidget(self.enter_btn)

        # 弹性空间
        layout.addStretch()

        # 提示文字
        tip_label = QLabel("激活码可在管理后台获取，如有问题请联系管理员")
        tip_label.setFont(QFont("Microsoft YaHei", 10))
        tip_label.setAlignment(Qt.AlignCenter)
        tip_label.setStyleSheet("color: #9E9E9E;")
        layout.addWidget(tip_label)

    def _connect_signals(self):
        """连接信号"""
        self.activate_btn.clicked.connect(self._on_activate)
        self.exit_btn.clicked.connect(self._on_exit)
        self.enter_btn.clicked.connect(self._on_enter)
        self.code_input.returnPressed.connect(self._on_activate)

    def _update_status_display(self, status: ActivationStatus):
        """更新状态显示"""
        self._status = status

        if status.is_valid:
            # 已激活
            self._is_activated = True
            self.status_label.setText("已激活")
            self.status_label.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: bold;")

            if status.days_remaining is not None:
                if status.days_remaining > 30:
                    self.expire_label.setText(f"剩余 {status.days_remaining} 天")
                    self.expire_label.setStyleSheet(f"color: {COLOR_SUCCESS};")
                elif status.days_remaining > 7:
                    self.expire_label.setText(f"剩余 {status.days_remaining} 天")
                    self.expire_label.setStyleSheet(f"color: {COLOR_WARNING};")
                else:
                    self.expire_label.setText(f"剩余 {status.days_remaining} 天，即将到期！")
                    self.expire_label.setStyleSheet(f"color: {COLOR_ERROR};")

            if status.expires_at:
                expire_date = status.expires_at[:10] if len(status.expires_at) > 10 else status.expires_at
                self.expire_label.setText(self.expire_label.text() + f"\n到期时间: {expire_date}")

            # 显示进入按钮，隐藏激活区域
            self.code_input.setPlaceholderText("输入新激活码可续期")
            self.activate_btn.setText("续期")
            self.enter_btn.show()

        else:
            # 未激活
            self._is_activated = False
            self.status_label.setText("未激活")
            self.status_label.setStyleSheet(f"color: {COLOR_ERROR}; font-weight: bold;")

            if status.error:
                self.expire_label.setText(f"({status.error})")
                self.expire_label.setStyleSheet(f"color: {COLOR_WARNING};")
            else:
                self.expire_label.setText("请输入激活码激活软件")
                self.expire_label.setStyleSheet("color: #757575;")

            self.enter_btn.hide()

    def _on_activate(self):
        """点击激活按钮"""
        code = self.code_input.text().strip()
        if not code:
            QMessageBox.warning(self, "提示", "请输入激活码")
            self.code_input.setFocus()
            return

        # 禁用按钮
        self.activate_btn.setEnabled(False)
        self.activate_btn.setText("激活中...")
        QApplication.processEvents()

        try:
            result = self._service.activate(code)

            if result.success:
                # 激活成功
                QMessageBox.information(
                    self,
                    "激活成功",
                    f"{result.message}\n\n有效期: {result.days} 天"
                )

                # 更新状态
                status = self._service.check_activation(use_cache=False)
                self._update_status_display(status)

                # 发射信号
                self.activation_success.emit()

                # 清空输入框
                self.code_input.clear()

                # 激活成功后直接进入程序
                self.accept()

            else:
                QMessageBox.warning(self, "激活失败", result.message)

        except Exception as e:
            logger.exception(f"激活异常: {e}")
            QMessageBox.critical(self, "错误", f"激活失败: {str(e)}")

        finally:
            self.activate_btn.setEnabled(True)
            self.activate_btn.setText("续期" if self._is_activated else "立即激活")

    def _on_exit(self):
        """点击退出按钮"""
        if self._is_activated:
            self.reject()
        else:
            reply = QMessageBox.question(
                self,
                "确认退出",
                "软件尚未激活，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.reject()
                QApplication.quit()

    def _on_enter(self):
        """点击进入程序按钮"""
        self.accept()

    def closeEvent(self, event: QCloseEvent):
        """关闭事件"""
        if not self._is_activated:
            event.ignore()
            self._on_exit()
        else:
            event.accept()

    def is_activated(self) -> bool:
        """返回是否已激活"""
        return self._is_activated

    @staticmethod
    def check_and_show(
        activation_service: ActivationService,
        parent=None
    ) -> bool:
        """
        检查激活状态并显示对话框

        Args:
            activation_service: 激活服务
            parent: 父窗口

        Returns:
            是否激活成功（True=可以继续使用）
        """
        # 检查激活状态
        status = activation_service.check_activation(use_cache=True)

        if status.is_valid:
            logger.info(f"软件已激活，剩余 {status.days_remaining} 天")
            return True

        # 显示激活对话框
        dialog = ActivationDialog(activation_service, status, parent)
        result = dialog.exec()

        return result == QDialog.Accepted and dialog.is_activated()
