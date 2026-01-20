"""
系统设置标签页模块

功能:
- 路径设置
- 发布设置
- 邮件通知配置
- 熔断器设置
- 显示设置
- 高级设置
- 配置保存/加载
- 配置验证
"""

import re
import smtplib
from pathlib import Path
from typing import List
from email.mime.text import MIMEText

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QFormLayout, QFileDialog, QMessageBox, QScrollArea,
    QFrame
)
from PySide6.QtCore import Qt, Signal

from services.config_manager import get_config_manager, DEFAULT_CONFIG
from services.voice_notifier import get_voice_notifier


class PathSelector(QWidget):
    """路径选择器组件"""

    path_changed = Signal(str)

    def __init__(self, placeholder: str = "", is_file: bool = False, parent=None):
        super().__init__(parent)
        self.is_file = is_file

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText(placeholder)
        self.line_edit.textChanged.connect(self.path_changed.emit)
        layout.addWidget(self.line_edit)

        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.setFixedWidth(70)
        self.btn_browse.clicked.connect(self._browse)
        layout.addWidget(self.btn_browse)

    def _browse(self) -> None:
        """打开浏览对话框"""
        if self.is_file:
            path, _ = QFileDialog.getOpenFileName(
                self, "选择文件", self.line_edit.text()
            )
        else:
            path = QFileDialog.getExistingDirectory(
                self, "选择文件夹", self.line_edit.text()
            )

        if path:
            self.line_edit.setText(path)

    def text(self) -> str:
        return self.line_edit.text()

    def setText(self, text: str) -> None:
        self.line_edit.setText(text)


class SettingsTab(QWidget):
    """系统设置标签页"""

    # 信号
    settings_saved = Signal()
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config_manager()
        self._modified = False
        self._init_ui()
        self.load_settings()

    def _init_ui(self) -> None:
        """初始化界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 设置整个标签页的样式
        self.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
                color: #E0E0E0;
            }
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
            QLabel {
                color: #B0B0B0;
                font-size: 13px;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 6px 10px;
                min-height: 20px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border-color: #90CAF9;
            }
            QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {
                background-color: #1A1A1A;
                color: #666666;
            }
            QCheckBox {
                color: #E0E0E0;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 1px solid #404040;
                background-color: #2D2D2D;
            }
            QCheckBox::indicator:checked {
                background-color: #90CAF9;
                border-color: #90CAF9;
            }
            QPushButton {
                background-color: #404040;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                min-height: 32px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #606060;
            }
            QScrollArea {
                background-color: #1E1E1E;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #1E1E1E;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background-color: #404040;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        # 设置内容容器
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(15)

        # ========== 激活状态 ==========
        activation_group = self._create_activation_settings()
        content_layout.addWidget(activation_group)

        # ========== 路径设置 ==========
        path_group = self._create_path_settings()
        content_layout.addWidget(path_group)

        # ========== 发布设置 ==========
        publish_group = self._create_publish_settings()
        content_layout.addWidget(publish_group)

        # ========== 邮件通知 ==========
        email_group = self._create_email_settings()
        content_layout.addWidget(email_group)

        # ========== 语音提醒 ==========
        voice_group = self._create_voice_settings()
        content_layout.addWidget(voice_group)

        # ========== 熔断设置 ==========
        circuit_group = self._create_circuit_breaker_settings()
        content_layout.addWidget(circuit_group)

        # ========== 显示设置 ==========
        display_group = self._create_display_settings()
        content_layout.addWidget(display_group)

        # ========== UI 定位配置 ==========
        ui_location_group = self._create_ui_location_settings()
        content_layout.addWidget(ui_location_group)

        # ========== 朋友圈坐标配置 ==========
        moments_group = self._create_moments_settings()
        content_layout.addWidget(moments_group)

        # ========== 群发坐标配置 ==========
        group_chat_group = self._create_group_chat_settings()
        content_layout.addWidget(group_chat_group)

        # ========== 小程序坐标配置 ==========
        miniprogram_group = self._create_miniprogram_settings()
        content_layout.addWidget(miniprogram_group)

        # ========== 客户群小程序坐标配置 ==========
        miniprogram_customer_group = self._create_miniprogram_customer_settings()
        content_layout.addWidget(miniprogram_customer_group)

        # ========== 高级设置 ==========
        advanced_group = self._create_advanced_settings()
        content_layout.addWidget(advanced_group)

        content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # ========== 底部按钮 ==========
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_reset = QPushButton("恢复默认")
        self.btn_reset.clicked.connect(self.reset_to_defaults)
        btn_layout.addWidget(self.btn_reset)

        self.btn_save = QPushButton("保存设置")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 20px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:pressed { background-color: #1565C0; }
        """)
        self.btn_save.clicked.connect(self.save_settings)
        btn_layout.addWidget(self.btn_save)

        main_layout.addLayout(btn_layout)

    def _create_activation_settings(self) -> QGroupBox:
        """创建激活状态设置组"""
        group = QGroupBox("激活状态")
        layout = QFormLayout(group)

        # 激活状态标签
        self.label_activation_status = QLabel("检查中...")
        self.label_activation_status.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addRow("状态:", self.label_activation_status)

        # 剩余天数
        self.label_days_remaining = QLabel("-")
        layout.addRow("剩余天数:", self.label_days_remaining)

        # 到期时间
        self.label_expires_at = QLabel("-")
        layout.addRow("到期时间:", self.label_expires_at)

        # 设备ID
        self.label_device_id = QLabel("-")
        self.label_device_id.setStyleSheet("color: #808080; font-size: 11px;")
        layout.addRow("设备ID:", self.label_device_id)

        # 按钮区域
        btn_layout = QHBoxLayout()

        self.btn_refresh_activation = QPushButton("刷新状态")
        self.btn_refresh_activation.clicked.connect(self._on_refresh_activation)
        btn_layout.addWidget(self.btn_refresh_activation)

        self.btn_renew = QPushButton("续费/激活")
        self.btn_renew.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)
        self.btn_renew.clicked.connect(self._on_renew_activation)
        btn_layout.addWidget(self.btn_renew)

        btn_layout.addStretch()
        layout.addRow("", btn_layout)

        # 初始加载激活状态
        self._load_activation_status()

        return group

    def _load_activation_status(self) -> None:
        """加载激活状态"""
        try:
            from services.activation_service import get_activation_service
            service = get_activation_service()
            status = service.check_activation(use_cache=True)

            if status.is_valid:
                self.label_activation_status.setText("已激活")
                self.label_activation_status.setStyleSheet("color: #4CAF50; font-size: 14px; font-weight: bold;")

                if status.days_remaining is not None:
                    if status.days_remaining > 30:
                        self.label_days_remaining.setText(f"{status.days_remaining} 天")
                        self.label_days_remaining.setStyleSheet("color: #4CAF50;")
                    elif status.days_remaining > 7:
                        self.label_days_remaining.setText(f"{status.days_remaining} 天")
                        self.label_days_remaining.setStyleSheet("color: #FF9800;")
                    else:
                        self.label_days_remaining.setText(f"{status.days_remaining} 天 (即将到期)")
                        self.label_days_remaining.setStyleSheet("color: #F44336;")
                else:
                    self.label_days_remaining.setText("-")

                if status.expires_at:
                    expire_date = status.expires_at[:10] if len(status.expires_at) > 10 else status.expires_at
                    self.label_expires_at.setText(expire_date)
                else:
                    self.label_expires_at.setText("-")
            else:
                self.label_activation_status.setText("未激活")
                self.label_activation_status.setStyleSheet("color: #F44336; font-size: 14px; font-weight: bold;")
                self.label_days_remaining.setText("-")
                self.label_expires_at.setText("-")

            if status.device_id:
                self.label_device_id.setText(status.device_id[:16] + "...")

        except Exception as e:
            self.label_activation_status.setText(f"获取失败: {str(e)}")
            self.label_activation_status.setStyleSheet("color: #F44336; font-size: 14px;")

    def _on_refresh_activation(self) -> None:
        """刷新激活状态"""
        try:
            from services.activation_service import get_activation_service
            service = get_activation_service()
            # 强制从服务器获取最新状态
            status = service.check_activation(use_cache=False)
            self._load_activation_status()
            QMessageBox.information(self, "刷新成功", "激活状态已更新")
        except Exception as e:
            QMessageBox.warning(self, "刷新失败", f"无法刷新激活状态: {str(e)}")

    def _on_renew_activation(self) -> None:
        """打开续费对话框"""
        try:
            from services.activation_service import get_activation_service
            from gui.activation_dialog import ActivationDialog

            service = get_activation_service()
            status = service.check_activation(use_cache=True)

            dialog = ActivationDialog(service, status, self)
            if dialog.exec():
                # 续费成功，刷新状态
                self._load_activation_status()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开激活对话框: {str(e)}")

    def _create_path_settings(self) -> QGroupBox:
        """创建路径设置组"""
        group = QGroupBox("路径设置")
        layout = QFormLayout(group)

        # 共享文件夹
        self.path_shared = PathSelector("共享文件夹路径")
        self.path_shared.path_changed.connect(self._on_setting_changed)
        layout.addRow("共享文件夹:", self.path_shared)

        # 缓存目录
        self.path_cache = PathSelector("缓存目录路径")
        self.path_cache.path_changed.connect(self._on_setting_changed)
        layout.addRow("缓存目录:", self.path_cache)

        # 回执目录
        self.path_receipts = PathSelector("回执目录路径")
        self.path_receipts.path_changed.connect(self._on_setting_changed)
        layout.addRow("回执目录:", self.path_receipts)

        # 日志目录
        self.path_logs = PathSelector("日志目录路径")
        self.path_logs.path_changed.connect(self._on_setting_changed)
        layout.addRow("日志目录:", self.path_logs)

        # 微信路径
        self.path_wechat = PathSelector("微信安装路径 (可选)", is_file=True)
        self.path_wechat.path_changed.connect(self._on_setting_changed)
        layout.addRow("微信路径:", self.path_wechat)

        return group

    def _create_publish_settings(self) -> QGroupBox:
        """创建发布设置组"""
        group = QGroupBox("发布设置")
        layout = QFormLayout(group)

        # 默认间隔
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(10, 3600)
        self.spin_interval.setSuffix(" 秒")
        self.spin_interval.valueChanged.connect(self._on_setting_changed)
        layout.addRow("默认检查间隔:", self.spin_interval)

        # 每日限额
        self.spin_daily_limit = QSpinBox()
        self.spin_daily_limit.setRange(0, 1000)
        self.spin_daily_limit.setSpecialValueText("无限制")
        self.spin_daily_limit.valueChanged.connect(self._on_setting_changed)
        layout.addRow("每日发布限额:", self.spin_daily_limit)

        # 随机延迟
        delay_layout = QHBoxLayout()
        self.spin_delay_min = QSpinBox()
        self.spin_delay_min.setRange(0, 600)
        self.spin_delay_min.setSuffix(" 秒")
        self.spin_delay_min.valueChanged.connect(self._on_setting_changed)
        delay_layout.addWidget(self.spin_delay_min)
        delay_layout.addWidget(QLabel("至"))
        self.spin_delay_max = QSpinBox()
        self.spin_delay_max.setRange(0, 600)
        self.spin_delay_max.setSuffix(" 秒")
        self.spin_delay_max.valueChanged.connect(self._on_setting_changed)
        delay_layout.addWidget(self.spin_delay_max)
        delay_layout.addStretch()
        layout.addRow("随机延迟范围:", delay_layout)

        # 活动时间
        time_layout = QHBoxLayout()
        self.edit_active_start = QLineEdit()
        self.edit_active_start.setPlaceholderText("08:00")
        self.edit_active_start.setMaximumWidth(80)
        self.edit_active_start.textChanged.connect(self._on_setting_changed)
        time_layout.addWidget(self.edit_active_start)
        time_layout.addWidget(QLabel("至"))
        self.edit_active_end = QLineEdit()
        self.edit_active_end.setPlaceholderText("22:00")
        self.edit_active_end.setMaximumWidth(80)
        self.edit_active_end.textChanged.connect(self._on_setting_changed)
        time_layout.addWidget(self.edit_active_end)
        time_layout.addStretch()
        layout.addRow("活动时间段:", time_layout)

        return group

    def _create_email_settings(self) -> QGroupBox:
        """创建邮件通知设置组"""
        group = QGroupBox("邮件通知")
        layout = QFormLayout(group)

        # 启用邮件
        self.check_email_enabled = QCheckBox("启用邮件通知")
        self.check_email_enabled.stateChanged.connect(self._on_email_enabled_changed)
        self.check_email_enabled.stateChanged.connect(self._on_setting_changed)
        layout.addRow("", self.check_email_enabled)

        # SMTP 服务器
        self.edit_smtp_host = QLineEdit()
        self.edit_smtp_host.setPlaceholderText("smtp.qq.com")
        self.edit_smtp_host.textChanged.connect(self._on_setting_changed)
        layout.addRow("SMTP服务器:", self.edit_smtp_host)

        # SMTP 端口
        self.spin_smtp_port = QSpinBox()
        self.spin_smtp_port.setRange(1, 65535)
        self.spin_smtp_port.setValue(465)
        self.spin_smtp_port.valueChanged.connect(self._on_setting_changed)
        layout.addRow("SMTP端口:", self.spin_smtp_port)

        # SSL/TLS
        ssl_layout = QHBoxLayout()
        self.check_use_ssl = QCheckBox("使用 SSL")
        self.check_use_ssl.stateChanged.connect(self._on_setting_changed)
        ssl_layout.addWidget(self.check_use_ssl)
        self.check_use_tls = QCheckBox("使用 TLS")
        self.check_use_tls.stateChanged.connect(self._on_setting_changed)
        ssl_layout.addWidget(self.check_use_tls)
        ssl_layout.addStretch()
        layout.addRow("加密方式:", ssl_layout)

        # 发件人地址
        self.edit_sender_address = QLineEdit()
        self.edit_sender_address.setPlaceholderText("your-email@qq.com")
        self.edit_sender_address.textChanged.connect(self._on_setting_changed)
        layout.addRow("发件人地址:", self.edit_sender_address)

        # 发件人密码
        self.edit_sender_password = QLineEdit()
        self.edit_sender_password.setEchoMode(QLineEdit.Password)
        self.edit_sender_password.setPlaceholderText("授权码或密码")
        self.edit_sender_password.textChanged.connect(self._on_setting_changed)
        layout.addRow("发件人密码:", self.edit_sender_password)

        # 收件人
        self.edit_recipients = QLineEdit()
        self.edit_recipients.setPlaceholderText("多个邮箱用逗号分隔")
        self.edit_recipients.textChanged.connect(self._on_setting_changed)
        layout.addRow("收件人:", self.edit_recipients)

        # 测试连接按钮
        self.btn_test_email = QPushButton("测试邮件连接")
        self.btn_test_email.clicked.connect(self.test_email_connection)
        layout.addRow("", self.btn_test_email)

        # 通知选项
        notify_layout = QHBoxLayout()
        self.check_notify_success = QCheckBox("成功")
        self.check_notify_success.stateChanged.connect(self._on_setting_changed)
        notify_layout.addWidget(self.check_notify_success)
        self.check_notify_failure = QCheckBox("失败")
        self.check_notify_failure.stateChanged.connect(self._on_setting_changed)
        notify_layout.addWidget(self.check_notify_failure)
        self.check_notify_daily = QCheckBox("每日汇总")
        self.check_notify_daily.stateChanged.connect(self._on_setting_changed)
        notify_layout.addWidget(self.check_notify_daily)
        self.check_notify_circuit = QCheckBox("熔断通知")
        self.check_notify_circuit.stateChanged.connect(self._on_setting_changed)
        notify_layout.addWidget(self.check_notify_circuit)
        notify_layout.addStretch()
        layout.addRow("通知类型:", notify_layout)

        return group

    def _create_voice_settings(self) -> QGroupBox:
        """创建语音提醒设置组"""
        group = QGroupBox("语音提醒")
        layout = QFormLayout(group)

        # 朋友圈完成语音提醒
        self.check_voice_moment = QCheckBox("朋友圈发布完成后语音提醒")
        self.check_voice_moment.stateChanged.connect(self._on_setting_changed)
        layout.addRow("", self.check_voice_moment)

        self.edit_voice_template = QLineEdit()
        self.edit_voice_template.setPlaceholderText("又发了一条朋友圈，还剩{remaining}条朋友圈待发，日拱一卒，财务自由。")
        self.edit_voice_template.textChanged.connect(self._on_setting_changed)
        layout.addRow("朋友圈模板:", self.edit_voice_template)

        # 代理群完成语音提醒
        self.check_voice_agent_group = QCheckBox("代理群发布完成后语音提醒")
        self.check_voice_agent_group.stateChanged.connect(self._on_setting_changed)
        layout.addRow("", self.check_voice_agent_group)

        self.edit_voice_agent_group_template = QLineEdit()
        self.edit_voice_agent_group_template.setPlaceholderText("代理群发送成功，还有{remaining}个待发送")
        self.edit_voice_agent_group_template.textChanged.connect(self._on_setting_changed)
        layout.addRow("代理群模板:", self.edit_voice_agent_group_template)

        # 客户群完成语音提醒
        self.check_voice_customer_group = QCheckBox("客户群发布完成后语音提醒")
        self.check_voice_customer_group.stateChanged.connect(self._on_setting_changed)
        layout.addRow("", self.check_voice_customer_group)

        self.edit_voice_customer_group_template = QLineEdit()
        self.edit_voice_customer_group_template.setPlaceholderText("客户群发送成功，还有{remaining}个待发送")
        self.edit_voice_customer_group_template.textChanged.connect(self._on_setting_changed)
        layout.addRow("客户群模板:", self.edit_voice_customer_group_template)

        hint = QLabel("可用占位符: {code}, {remaining}")
        hint.setStyleSheet("color: #8a8a8a; font-size: 12px;")
        layout.addRow("", hint)

        self.btn_test_voice = QPushButton("测试播报")
        self.btn_test_voice.clicked.connect(self._on_test_voice)
        layout.addRow("", self.btn_test_voice)

        return group

    def _create_circuit_breaker_settings(self) -> QGroupBox:
        """创建熔断器设置组"""
        group = QGroupBox("熔断设置")
        layout = QFormLayout(group)

        # 启用熔断
        self.check_circuit_enabled = QCheckBox("启用熔断器")
        self.check_circuit_enabled.stateChanged.connect(self._on_setting_changed)
        layout.addRow("", self.check_circuit_enabled)

        # 失败阈值
        self.spin_failure_threshold = QSpinBox()
        self.spin_failure_threshold.setRange(1, 100)
        self.spin_failure_threshold.setSuffix(" 次")
        self.spin_failure_threshold.valueChanged.connect(self._on_setting_changed)
        layout.addRow("失败阈值:", self.spin_failure_threshold)

        # 恢复超时
        self.spin_recovery_timeout = QSpinBox()
        self.spin_recovery_timeout.setRange(10, 3600)
        self.spin_recovery_timeout.setSuffix(" 秒")
        self.spin_recovery_timeout.valueChanged.connect(self._on_setting_changed)
        layout.addRow("恢复超时:", self.spin_recovery_timeout)

        # 半开尝试次数
        self.spin_half_open = QSpinBox()
        self.spin_half_open.setRange(1, 10)
        self.spin_half_open.setSuffix(" 次")
        self.spin_half_open.valueChanged.connect(self._on_setting_changed)
        layout.addRow("半开尝试次数:", self.spin_half_open)

        # 计数重置时间
        self.spin_count_reset = QSpinBox()
        self.spin_count_reset.setRange(60, 7200)
        self.spin_count_reset.setSuffix(" 秒")
        self.spin_count_reset.valueChanged.connect(self._on_setting_changed)
        layout.addRow("计数重置时间:", self.spin_count_reset)

        return group

    def _create_display_settings(self) -> QGroupBox:
        """创建显示设置组"""
        group = QGroupBox("显示设置")
        layout = QFormLayout(group)

        # 最小分辨率
        res_layout = QHBoxLayout()
        self.spin_min_width = QSpinBox()
        self.spin_min_width.setRange(800, 7680)
        self.spin_min_width.setSuffix(" px")
        self.spin_min_width.valueChanged.connect(self._on_setting_changed)
        res_layout.addWidget(self.spin_min_width)
        res_layout.addWidget(QLabel("x"))
        self.spin_min_height = QSpinBox()
        self.spin_min_height.setRange(600, 4320)
        self.spin_min_height.setSuffix(" px")
        self.spin_min_height.valueChanged.connect(self._on_setting_changed)
        res_layout.addWidget(self.spin_min_height)
        res_layout.addStretch()
        layout.addRow("最小分辨率:", res_layout)

        # 仅使用主显示器
        self.check_primary_only = QCheckBox("仅使用主显示器")
        self.check_primary_only.stateChanged.connect(self._on_setting_changed)
        layout.addRow("", self.check_primary_only)

        # DPI 检查
        self.check_dpi = QCheckBox("检查 DPI 缩放")
        self.check_dpi.stateChanged.connect(self._on_setting_changed)
        layout.addRow("", self.check_dpi)

        # 推荐 DPI
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(100, 300)
        self.spin_dpi.setSuffix(" %")
        self.spin_dpi.valueChanged.connect(self._on_setting_changed)
        layout.addRow("推荐 DPI:", self.spin_dpi)

        return group

    def _create_ui_location_settings(self) -> QGroupBox:
        """创建通用配置组"""
        group = QGroupBox("通用配置")
        layout = QFormLayout(group)

        # 图像识别置信度
        confidence_layout = QHBoxLayout()
        self.check_confidence_08 = QCheckBox("0.8")
        self.check_confidence_08.stateChanged.connect(self._on_setting_changed)
        confidence_layout.addWidget(self.check_confidence_08)
        self.check_confidence_06 = QCheckBox("0.6")
        self.check_confidence_06.stateChanged.connect(self._on_setting_changed)
        confidence_layout.addWidget(self.check_confidence_06)
        self.check_confidence_04 = QCheckBox("0.4")
        self.check_confidence_04.stateChanged.connect(self._on_setting_changed)
        confidence_layout.addWidget(self.check_confidence_04)
        confidence_layout.addStretch()
        layout.addRow("图像识别置信度:", confidence_layout)

        # 说明标签
        hint_label = QLabel("(从高到低依次尝试)")
        hint_label.setStyleSheet("color: #808080; font-size: 11px;")
        layout.addRow("", hint_label)

        return group

    def _create_moments_settings(self) -> QGroupBox:
        """创建朋友圈发布流程配置组"""
        group = QGroupBox("朋友圈发布流程配置")
        layout = QFormLayout(group)

        # === 绝对坐标部分 ===
        abs_label = QLabel("绝对坐标:")
        abs_label.setStyleSheet("color: #4a9eff; font-weight: bold;")
        layout.addRow(abs_label)

        # 朋友圈入口按钮
        btn_layout = QHBoxLayout()
        self.spin_moments_btn_x = QSpinBox()
        self.spin_moments_btn_x.setRange(0, 9999)
        self.spin_moments_btn_x.valueChanged.connect(self._on_setting_changed)
        btn_layout.addWidget(QLabel("X:"))
        btn_layout.addWidget(self.spin_moments_btn_x)
        self.spin_moments_btn_y = QSpinBox()
        self.spin_moments_btn_y.setRange(0, 9999)
        self.spin_moments_btn_y.valueChanged.connect(self._on_setting_changed)
        btn_layout.addWidget(QLabel("Y:"))
        btn_layout.addWidget(self.spin_moments_btn_y)
        btn_layout.addStretch()
        layout.addRow("1. 朋友圈入口:", btn_layout)

        # 发布按钮（相机图标）
        publish_layout = QHBoxLayout()
        self.spin_moments_publish_x = QSpinBox()
        self.spin_moments_publish_x.setRange(0, 9999)
        self.spin_moments_publish_x.valueChanged.connect(self._on_setting_changed)
        publish_layout.addWidget(QLabel("X:"))
        publish_layout.addWidget(self.spin_moments_publish_x)
        self.spin_moments_publish_y = QSpinBox()
        self.spin_moments_publish_y.setRange(0, 9999)
        self.spin_moments_publish_y.valueChanged.connect(self._on_setting_changed)
        publish_layout.addWidget(QLabel("Y:"))
        publish_layout.addWidget(self.spin_moments_publish_y)
        publish_layout.addStretch()
        layout.addRow("2. 发布按钮(相机):", publish_layout)

        # 文案输入框
        input_layout = QHBoxLayout()
        self.spin_moments_input_x = QSpinBox()
        self.spin_moments_input_x.setRange(0, 9999)
        self.spin_moments_input_x.valueChanged.connect(self._on_setting_changed)
        input_layout.addWidget(QLabel("X:"))
        input_layout.addWidget(self.spin_moments_input_x)
        self.spin_moments_input_y = QSpinBox()
        self.spin_moments_input_y.setRange(0, 9999)
        self.spin_moments_input_y.valueChanged.connect(self._on_setting_changed)
        input_layout.addWidget(QLabel("Y:"))
        input_layout.addWidget(self.spin_moments_input_y)
        input_layout.addStretch()
        layout.addRow("3. 文案输入框:", input_layout)

        # 提交发布按钮
        submit_layout = QHBoxLayout()
        self.spin_moments_submit_x = QSpinBox()
        self.spin_moments_submit_x.setRange(0, 9999)
        self.spin_moments_submit_x.valueChanged.connect(self._on_setting_changed)
        submit_layout.addWidget(QLabel("X:"))
        submit_layout.addWidget(self.spin_moments_submit_x)
        self.spin_moments_submit_y = QSpinBox()
        self.spin_moments_submit_y.setRange(0, 9999)
        self.spin_moments_submit_y.valueChanged.connect(self._on_setting_changed)
        submit_layout.addWidget(QLabel("Y:"))
        submit_layout.addWidget(self.spin_moments_submit_y)
        submit_layout.addStretch()
        layout.addRow("4. 提交发布按钮:", submit_layout)

        # 第一条朋友圈位置
        first_layout = QHBoxLayout()
        self.spin_moments_first_x = QSpinBox()
        self.spin_moments_first_x.setRange(0, 9999)
        self.spin_moments_first_x.valueChanged.connect(self._on_setting_changed)
        first_layout.addWidget(QLabel("X:"))
        first_layout.addWidget(self.spin_moments_first_x)
        self.spin_moments_first_y = QSpinBox()
        self.spin_moments_first_y.setRange(0, 9999)
        self.spin_moments_first_y.valueChanged.connect(self._on_setting_changed)
        first_layout.addWidget(QLabel("Y:"))
        first_layout.addWidget(self.spin_moments_first_y)
        first_layout.addStretch()
        layout.addRow("5. 第一条朋友圈:", first_layout)

        # 关闭按钮（绝对坐标）
        close_layout = QHBoxLayout()
        self.spin_moments_close_x = QSpinBox()
        self.spin_moments_close_x.setRange(0, 9999)
        self.spin_moments_close_x.valueChanged.connect(self._on_setting_changed)
        close_layout.addWidget(QLabel("X:"))
        close_layout.addWidget(self.spin_moments_close_x)
        self.spin_moments_close_y = QSpinBox()
        self.spin_moments_close_y.setRange(0, 9999)
        self.spin_moments_close_y.valueChanged.connect(self._on_setting_changed)
        close_layout.addWidget(QLabel("Y:"))
        close_layout.addWidget(self.spin_moments_close_y)
        close_layout.addStretch()
        layout.addRow("9. 关闭按钮:", close_layout)

        # === 相对偏移部分 ===
        rel_label = QLabel("相对偏移 (基于...按钮):")
        rel_label.setStyleSheet("color: #4a9eff; font-weight: bold; margin-top: 10px;")
        layout.addRow(rel_label)

        # "..." 按钮 Y 偏移
        self.spin_dots_btn_y_offset = QSpinBox()
        self.spin_dots_btn_y_offset.setRange(0, 100)
        self.spin_dots_btn_y_offset.setSuffix(" px")
        self.spin_dots_btn_y_offset.valueChanged.connect(self._on_setting_changed)
        layout.addRow('6. "..." 按钮 Y 偏移:', self.spin_dots_btn_y_offset)

        # 发送按钮相对...按钮偏移
        send_btn_layout = QHBoxLayout()
        self.spin_send_btn_dots_x_offset = QSpinBox()
        self.spin_send_btn_dots_x_offset.setRange(-500, 500)
        self.spin_send_btn_dots_x_offset.setSuffix(" px")
        self.spin_send_btn_dots_x_offset.valueChanged.connect(self._on_setting_changed)
        send_btn_layout.addWidget(QLabel("X:"))
        send_btn_layout.addWidget(self.spin_send_btn_dots_x_offset)
        self.spin_send_btn_dots_y_offset = QSpinBox()
        self.spin_send_btn_dots_y_offset.setRange(-500, 500)
        self.spin_send_btn_dots_y_offset.setSuffix(" px")
        self.spin_send_btn_dots_y_offset.valueChanged.connect(self._on_setting_changed)
        send_btn_layout.addWidget(QLabel("Y:"))
        send_btn_layout.addWidget(self.spin_send_btn_dots_y_offset)
        send_btn_layout.addStretch()
        layout.addRow("7. 发送按钮相对偏移:", send_btn_layout)

        # 关闭按钮偏移
        self.spin_close_btn_offset = QSpinBox()
        self.spin_close_btn_offset.setRange(0, 50)
        self.spin_close_btn_offset.setSuffix(" px")
        self.spin_close_btn_offset.valueChanged.connect(self._on_setting_changed)
        layout.addRow("8. 关闭按钮偏移:", self.spin_close_btn_offset)

        # 说明标签
        hint_label = QLabel("提示: 绝对坐标用鼠标工具测量; 相对偏移基于...按钮位置计算")
        hint_label.setStyleSheet("color: #808080; font-size: 11px;")
        layout.addRow("", hint_label)

        return group

    def _create_group_chat_settings(self) -> QGroupBox:
        """创建群发/转发流程配置组"""
        group = QGroupBox("群发/转发流程配置")
        layout = QFormLayout(group)

        # === 群发绝对坐标 ===
        abs_label = QLabel("群发绝对坐标:")
        abs_label.setStyleSheet("color: #4a9eff; font-weight: bold;")
        layout.addRow(abs_label)

        # 搜索框坐标
        search_layout = QHBoxLayout()
        self.spin_group_search_x = QSpinBox()
        self.spin_group_search_x.setRange(0, 9999)
        self.spin_group_search_x.valueChanged.connect(self._on_setting_changed)
        search_layout.addWidget(QLabel("X:"))
        search_layout.addWidget(self.spin_group_search_x)
        self.spin_group_search_y = QSpinBox()
        self.spin_group_search_y.setRange(0, 9999)
        self.spin_group_search_y.valueChanged.connect(self._on_setting_changed)
        search_layout.addWidget(QLabel("Y:"))
        search_layout.addWidget(self.spin_group_search_y)
        search_layout.addStretch()
        layout.addRow("1. 搜索框:", search_layout)

        # 输入框坐标
        input_layout = QHBoxLayout()
        self.spin_group_input_x = QSpinBox()
        self.spin_group_input_x.setRange(0, 9999)
        self.spin_group_input_x.valueChanged.connect(self._on_setting_changed)
        input_layout.addWidget(QLabel("X:"))
        input_layout.addWidget(self.spin_group_input_x)
        self.spin_group_input_y = QSpinBox()
        self.spin_group_input_y.setRange(0, 9999)
        self.spin_group_input_y.valueChanged.connect(self._on_setting_changed)
        input_layout.addWidget(QLabel("Y:"))
        input_layout.addWidget(self.spin_group_input_y)
        input_layout.addStretch()
        layout.addRow("2. 输入框:", input_layout)

        # 发送文件按钮坐标
        upload_layout = QHBoxLayout()
        self.spin_group_upload_x = QSpinBox()
        self.spin_group_upload_x.setRange(0, 9999)
        self.spin_group_upload_x.valueChanged.connect(self._on_setting_changed)
        upload_layout.addWidget(QLabel("X:"))
        upload_layout.addWidget(self.spin_group_upload_x)
        self.spin_group_upload_y = QSpinBox()
        self.spin_group_upload_y.setRange(0, 9999)
        self.spin_group_upload_y.valueChanged.connect(self._on_setting_changed)
        upload_layout.addWidget(QLabel("Y:"))
        upload_layout.addWidget(self.spin_group_upload_y)
        upload_layout.addStretch()
        layout.addRow("3. 发送文件按钮:", upload_layout)

        # === 转发小程序到目标群 ===
        forward_label = QLabel("转发小程序到目标群:")
        forward_label.setStyleSheet("color: #4a9eff; font-weight: bold; margin-top: 10px;")
        layout.addRow(forward_label)

        # 转发对话框-目标群对象坐标
        forward_group_layout = QHBoxLayout()
        self.spin_forward_group_x_offset = QSpinBox()
        self.spin_forward_group_x_offset.setRange(0, 2000)
        self.spin_forward_group_x_offset.setSuffix(" px")
        self.spin_forward_group_x_offset.valueChanged.connect(self._on_setting_changed)
        forward_group_layout.addWidget(QLabel("X:"))
        forward_group_layout.addWidget(self.spin_forward_group_x_offset)
        self.spin_forward_group_y_offset = QSpinBox()
        self.spin_forward_group_y_offset.setRange(0, 2000)
        self.spin_forward_group_y_offset.setSuffix(" px")
        self.spin_forward_group_y_offset.valueChanged.connect(self._on_setting_changed)
        forward_group_layout.addWidget(QLabel("Y:"))
        forward_group_layout.addWidget(self.spin_forward_group_y_offset)
        forward_group_layout.addStretch()
        layout.addRow("4. 目标群对象坐标:", forward_group_layout)

        # 转发对话框-发送按钮偏移
        forward_send_layout = QHBoxLayout()
        self.spin_forward_send_x_offset = QSpinBox()
        self.spin_forward_send_x_offset.setRange(0, 2000)
        self.spin_forward_send_x_offset.setSuffix(" px")
        self.spin_forward_send_x_offset.valueChanged.connect(self._on_setting_changed)
        forward_send_layout.addWidget(QLabel("X:"))
        forward_send_layout.addWidget(self.spin_forward_send_x_offset)
        self.spin_forward_send_y_offset = QSpinBox()
        self.spin_forward_send_y_offset.setRange(0, 2000)
        self.spin_forward_send_y_offset.setSuffix(" px")
        self.spin_forward_send_y_offset.valueChanged.connect(self._on_setting_changed)
        forward_send_layout.addWidget(QLabel("Y:"))
        forward_send_layout.addWidget(self.spin_forward_send_y_offset)
        forward_send_layout.addStretch()
        layout.addRow("5. 发送按钮偏移:", forward_send_layout)

        # 说明标签
        hint_label = QLabel("提示: 群发坐标为绝对坐标; 转发对话框偏移相对于对话框左上角")
        hint_label.setStyleSheet("color: #808080; font-size: 11px;")
        layout.addRow("", hint_label)

        return group

    def _create_miniprogram_settings(self) -> QGroupBox:
        """创建小程序坐标配置组"""
        group = QGroupBox("小程序坐标配置 (绝对坐标)")
        layout = QFormLayout(group)

        # 窗口位置
        window_layout = QHBoxLayout()
        self.spin_miniprogram_window_x = QSpinBox()
        self.spin_miniprogram_window_x.setRange(0, 9999)
        self.spin_miniprogram_window_x.valueChanged.connect(self._on_setting_changed)
        window_layout.addWidget(QLabel("X:"))
        window_layout.addWidget(self.spin_miniprogram_window_x)
        self.spin_miniprogram_window_y = QSpinBox()
        self.spin_miniprogram_window_y.setRange(0, 9999)
        self.spin_miniprogram_window_y.valueChanged.connect(self._on_setting_changed)
        window_layout.addWidget(QLabel("Y:"))
        window_layout.addWidget(self.spin_miniprogram_window_y)
        window_layout.addStretch()
        layout.addRow("窗口位置:", window_layout)

        # 更多按钮
        more_layout = QHBoxLayout()
        self.spin_miniprogram_more_x = QSpinBox()
        self.spin_miniprogram_more_x.setRange(0, 9999)
        self.spin_miniprogram_more_x.valueChanged.connect(self._on_setting_changed)
        more_layout.addWidget(QLabel("X:"))
        more_layout.addWidget(self.spin_miniprogram_more_x)
        self.spin_miniprogram_more_y = QSpinBox()
        self.spin_miniprogram_more_y.setRange(0, 9999)
        self.spin_miniprogram_more_y.valueChanged.connect(self._on_setting_changed)
        more_layout.addWidget(QLabel("Y:"))
        more_layout.addWidget(self.spin_miniprogram_more_y)
        more_layout.addStretch()
        layout.addRow("更多按钮:", more_layout)

        # 重新进入小程序
        reenter_layout = QHBoxLayout()
        self.spin_miniprogram_reenter_x = QSpinBox()
        self.spin_miniprogram_reenter_x.setRange(0, 9999)
        self.spin_miniprogram_reenter_x.valueChanged.connect(self._on_setting_changed)
        reenter_layout.addWidget(QLabel("X:"))
        reenter_layout.addWidget(self.spin_miniprogram_reenter_x)
        self.spin_miniprogram_reenter_y = QSpinBox()
        self.spin_miniprogram_reenter_y.setRange(0, 9999)
        self.spin_miniprogram_reenter_y.valueChanged.connect(self._on_setting_changed)
        reenter_layout.addWidget(QLabel("Y:"))
        reenter_layout.addWidget(self.spin_miniprogram_reenter_y)
        reenter_layout.addStretch()
        layout.addRow("重新进入:", reenter_layout)

        # 搜索按钮
        search_layout = QHBoxLayout()
        self.spin_miniprogram_search_x = QSpinBox()
        self.spin_miniprogram_search_x.setRange(0, 9999)
        self.spin_miniprogram_search_x.valueChanged.connect(self._on_setting_changed)
        search_layout.addWidget(QLabel("X:"))
        search_layout.addWidget(self.spin_miniprogram_search_x)
        self.spin_miniprogram_search_y = QSpinBox()
        self.spin_miniprogram_search_y.setRange(0, 9999)
        self.spin_miniprogram_search_y.valueChanged.connect(self._on_setting_changed)
        search_layout.addWidget(QLabel("Y:"))
        search_layout.addWidget(self.spin_miniprogram_search_y)
        search_layout.addStretch()
        layout.addRow("搜索按钮:", search_layout)

        # 产品链接
        product_layout = QHBoxLayout()
        self.spin_miniprogram_product_x = QSpinBox()
        self.spin_miniprogram_product_x.setRange(0, 9999)
        self.spin_miniprogram_product_x.valueChanged.connect(self._on_setting_changed)
        product_layout.addWidget(QLabel("X:"))
        product_layout.addWidget(self.spin_miniprogram_product_x)
        self.spin_miniprogram_product_y = QSpinBox()
        self.spin_miniprogram_product_y.setRange(0, 9999)
        self.spin_miniprogram_product_y.valueChanged.connect(self._on_setting_changed)
        product_layout.addWidget(QLabel("Y:"))
        product_layout.addWidget(self.spin_miniprogram_product_y)
        product_layout.addStretch()
        layout.addRow("产品链接:", product_layout)

        # 转发按钮
        forward_layout = QHBoxLayout()
        self.spin_miniprogram_forward_x = QSpinBox()
        self.spin_miniprogram_forward_x.setRange(0, 9999)
        self.spin_miniprogram_forward_x.valueChanged.connect(self._on_setting_changed)
        forward_layout.addWidget(QLabel("X:"))
        forward_layout.addWidget(self.spin_miniprogram_forward_x)
        self.spin_miniprogram_forward_y = QSpinBox()
        self.spin_miniprogram_forward_y.setRange(0, 9999)
        self.spin_miniprogram_forward_y.valueChanged.connect(self._on_setting_changed)
        forward_layout.addWidget(QLabel("Y:"))
        forward_layout.addWidget(self.spin_miniprogram_forward_y)
        forward_layout.addStretch()
        layout.addRow("转发按钮:", forward_layout)

        # 说明标签
        hint_label = QLabel("提示: 使用鼠标工具测量各按钮的屏幕绝对坐标")
        hint_label.setStyleSheet("color: #808080; font-size: 11px;")
        layout.addRow("", hint_label)

        return group

    def _create_miniprogram_customer_settings(self) -> QGroupBox:
        """创建客户群小程序坐标配置组"""
        group = QGroupBox("客户群小程序坐标配置 (绝对坐标)")
        layout = QFormLayout(group)

        # 窗口位置
        window_layout = QHBoxLayout()
        self.spin_miniprogram_customer_window_x = QSpinBox()
        self.spin_miniprogram_customer_window_x.setRange(0, 9999)
        self.spin_miniprogram_customer_window_x.valueChanged.connect(self._on_setting_changed)
        window_layout.addWidget(QLabel("X:"))
        window_layout.addWidget(self.spin_miniprogram_customer_window_x)
        self.spin_miniprogram_customer_window_y = QSpinBox()
        self.spin_miniprogram_customer_window_y.setRange(0, 9999)
        self.spin_miniprogram_customer_window_y.valueChanged.connect(self._on_setting_changed)
        window_layout.addWidget(QLabel("Y:"))
        window_layout.addWidget(self.spin_miniprogram_customer_window_y)
        window_layout.addStretch()
        layout.addRow("窗口位置:", window_layout)

        # 更多按钮
        more_layout = QHBoxLayout()
        self.spin_miniprogram_customer_more_x = QSpinBox()
        self.spin_miniprogram_customer_more_x.setRange(0, 9999)
        self.spin_miniprogram_customer_more_x.valueChanged.connect(self._on_setting_changed)
        more_layout.addWidget(QLabel("X:"))
        more_layout.addWidget(self.spin_miniprogram_customer_more_x)
        self.spin_miniprogram_customer_more_y = QSpinBox()
        self.spin_miniprogram_customer_more_y.setRange(0, 9999)
        self.spin_miniprogram_customer_more_y.valueChanged.connect(self._on_setting_changed)
        more_layout.addWidget(QLabel("Y:"))
        more_layout.addWidget(self.spin_miniprogram_customer_more_y)
        more_layout.addStretch()
        layout.addRow("更多按钮:", more_layout)

        # 重新进入小程序
        reenter_layout = QHBoxLayout()
        self.spin_miniprogram_customer_reenter_x = QSpinBox()
        self.spin_miniprogram_customer_reenter_x.setRange(0, 9999)
        self.spin_miniprogram_customer_reenter_x.valueChanged.connect(self._on_setting_changed)
        reenter_layout.addWidget(QLabel("X:"))
        reenter_layout.addWidget(self.spin_miniprogram_customer_reenter_x)
        self.spin_miniprogram_customer_reenter_y = QSpinBox()
        self.spin_miniprogram_customer_reenter_y.setRange(0, 9999)
        self.spin_miniprogram_customer_reenter_y.valueChanged.connect(self._on_setting_changed)
        reenter_layout.addWidget(QLabel("Y:"))
        reenter_layout.addWidget(self.spin_miniprogram_customer_reenter_y)
        reenter_layout.addStretch()
        layout.addRow("重新进入:", reenter_layout)

        # 搜索按钮
        search_layout = QHBoxLayout()
        self.spin_miniprogram_customer_search_x = QSpinBox()
        self.spin_miniprogram_customer_search_x.setRange(0, 9999)
        self.spin_miniprogram_customer_search_x.valueChanged.connect(self._on_setting_changed)
        search_layout.addWidget(QLabel("X:"))
        search_layout.addWidget(self.spin_miniprogram_customer_search_x)
        self.spin_miniprogram_customer_search_y = QSpinBox()
        self.spin_miniprogram_customer_search_y.setRange(0, 9999)
        self.spin_miniprogram_customer_search_y.valueChanged.connect(self._on_setting_changed)
        search_layout.addWidget(QLabel("Y:"))
        search_layout.addWidget(self.spin_miniprogram_customer_search_y)
        search_layout.addStretch()
        layout.addRow("搜索按钮:", search_layout)

        # 产品链接
        product_layout = QHBoxLayout()
        self.spin_miniprogram_customer_product_x = QSpinBox()
        self.spin_miniprogram_customer_product_x.setRange(0, 9999)
        self.spin_miniprogram_customer_product_x.valueChanged.connect(self._on_setting_changed)
        product_layout.addWidget(QLabel("X:"))
        product_layout.addWidget(self.spin_miniprogram_customer_product_x)
        self.spin_miniprogram_customer_product_y = QSpinBox()
        self.spin_miniprogram_customer_product_y.setRange(0, 9999)
        self.spin_miniprogram_customer_product_y.valueChanged.connect(self._on_setting_changed)
        product_layout.addWidget(QLabel("Y:"))
        product_layout.addWidget(self.spin_miniprogram_customer_product_y)
        product_layout.addStretch()
        layout.addRow("产品链接:", product_layout)

        # 转发按钮
        forward_layout = QHBoxLayout()
        self.spin_miniprogram_customer_forward_x = QSpinBox()
        self.spin_miniprogram_customer_forward_x.setRange(0, 9999)
        self.spin_miniprogram_customer_forward_x.valueChanged.connect(self._on_setting_changed)
        forward_layout.addWidget(QLabel("X:"))
        forward_layout.addWidget(self.spin_miniprogram_customer_forward_x)
        self.spin_miniprogram_customer_forward_y = QSpinBox()
        self.spin_miniprogram_customer_forward_y.setRange(0, 9999)
        self.spin_miniprogram_customer_forward_y.valueChanged.connect(self._on_setting_changed)
        forward_layout.addWidget(QLabel("Y:"))
        forward_layout.addWidget(self.spin_miniprogram_customer_forward_y)
        forward_layout.addStretch()
        layout.addRow("转发按钮:", forward_layout)

        # 说明标签
        hint_label = QLabel("提示: 客户群使用独立的坐标配置")
        hint_label.setStyleSheet("color: #808080; font-size: 11px;")
        layout.addRow("", hint_label)

        return group

    def _create_advanced_settings(self) -> QGroupBox:
        """创建高级设置组"""
        group = QGroupBox("高级设置")
        layout = QFormLayout(group)

        # 日志级别
        self.combo_log_level = QComboBox()
        self.combo_log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.combo_log_level.currentTextChanged.connect(self._on_setting_changed)
        layout.addRow("日志级别:", self.combo_log_level)

        # 调试模式
        self.check_debug = QCheckBox("启用调试模式")
        self.check_debug.stateChanged.connect(self._on_setting_changed)
        layout.addRow("", self.check_debug)

        # 保存截图
        self.check_screenshots = QCheckBox("保存操作截图")
        self.check_screenshots.stateChanged.connect(self._on_setting_changed)
        layout.addRow("", self.check_screenshots)

        # 截图目录
        self.path_screenshots = PathSelector("截图保存目录")
        self.path_screenshots.path_changed.connect(self._on_setting_changed)
        layout.addRow("截图目录:", self.path_screenshots)

        # 控制台输出
        self.check_console = QCheckBox("输出到控制台")
        self.check_console.stateChanged.connect(self._on_setting_changed)
        layout.addRow("", self.check_console)

        return group

    def _on_setting_changed(self) -> None:
        """设置变更事件"""
        self._modified = True
        self.settings_changed.emit()

    def _on_test_voice(self) -> None:
        template = self.edit_voice_template.text().strip() or DEFAULT_CONFIG["voice"]["moment_complete_text"]
        try:
            sample_text = template.format(code="示例001", remaining=2)
        except Exception as e:
            QMessageBox.warning(self, "模板错误", f"模板格式化失败: {e}\n可用占位符: {{code}} {{remaining}}")
            return

        try:
            get_voice_notifier().speak(sample_text)
        except Exception as e:
            QMessageBox.warning(self, "播报失败", f"语音播放失败: {e}")

    def _on_email_enabled_changed(self, state: int) -> None:
        """邮件启用状态变更"""
        enabled = state == Qt.Checked
        self.edit_smtp_host.setEnabled(enabled)
        self.spin_smtp_port.setEnabled(enabled)
        self.check_use_ssl.setEnabled(enabled)
        self.check_use_tls.setEnabled(enabled)
        self.edit_sender_address.setEnabled(enabled)
        self.edit_sender_password.setEnabled(enabled)
        self.edit_recipients.setEnabled(enabled)
        self.btn_test_email.setEnabled(enabled)
        self.check_notify_success.setEnabled(enabled)
        self.check_notify_failure.setEnabled(enabled)
        self.check_notify_daily.setEnabled(enabled)
        self.check_notify_circuit.setEnabled(enabled)

    def load_settings(self) -> None:
        """加载配置"""
        # 路径设置
        self.path_shared.setText(self.config.get("paths.shared_folder", ""))
        self.path_cache.setText(self.config.get("paths.cache_dir", ""))
        self.path_receipts.setText(self.config.get("paths.receipts_dir", ""))
        self.path_logs.setText(self.config.get("paths.logs_dir", ""))
        self.path_wechat.setText(self.config.get("paths.wechat_path", ""))

        # 发布设置
        self.spin_interval.setValue(self.config.get("schedule.default_interval", 180))
        self.spin_daily_limit.setValue(self.config.get("schedule.daily_limit", 50))
        self.spin_delay_min.setValue(self.config.get("schedule.random_delay_min", 0))
        self.spin_delay_max.setValue(self.config.get("schedule.random_delay_max", 60))
        self.edit_active_start.setText(self.config.get("schedule.active_hours.start", "08:00"))
        self.edit_active_end.setText(self.config.get("schedule.active_hours.end", "22:00"))

        # 邮件设置
        self.check_email_enabled.setChecked(self.config.get("email.enabled", False))
        self.edit_smtp_host.setText(self.config.get("email.smtp.host", ""))
        self.spin_smtp_port.setValue(self.config.get("email.smtp.port", 465))
        self.check_use_ssl.setChecked(self.config.get("email.smtp.use_ssl", True))
        self.check_use_tls.setChecked(self.config.get("email.smtp.use_tls", False))
        self.edit_sender_address.setText(self.config.get("email.sender.address", ""))

        # 密码 - 使用脱敏显示
        password = self.config.get("email.sender.password", "")
        if password and self.config.is_value_encrypted(password):
            # 已加密的密码显示占位符
            self.edit_sender_password.setPlaceholderText("已设置 (输入新密码将覆盖)")
        else:
            self.edit_sender_password.setText(password)

        # 收件人列表
        recipients = self.config.get("email.recipients", [])
        self.edit_recipients.setText(", ".join(recipients))

        # 通知选项
        self.check_notify_success.setChecked(self.config.get("email.notify_on.success", False))
        self.check_notify_failure.setChecked(self.config.get("email.notify_on.failure", True))
        self.check_notify_daily.setChecked(self.config.get("email.notify_on.daily_summary", True))
        self.check_notify_circuit.setChecked(self.config.get("email.notify_on.circuit_break", True))

        # 触发邮件启用状态更新
        self._on_email_enabled_changed(
            Qt.Checked if self.config.get("email.enabled", False) else Qt.Unchecked
        )

        # 语音提醒设置
        self.check_voice_moment.setChecked(self.config.get("voice.moment_complete_enabled", False))
        self.edit_voice_template.setText(
            self.config.get(
                "voice.moment_complete_text",
                DEFAULT_CONFIG["voice"]["moment_complete_text"]
            )
        )
        self.check_voice_agent_group.setChecked(self.config.get("voice.agent_group_complete_enabled", False))
        self.edit_voice_agent_group_template.setText(
            self.config.get(
                "voice.agent_group_complete_text",
                "代理群发送成功，还有{remaining}个待发送"
            )
        )
        self.check_voice_customer_group.setChecked(self.config.get("voice.customer_group_complete_enabled", False))
        self.edit_voice_customer_group_template.setText(
            self.config.get(
                "voice.customer_group_complete_text",
                "客户群发送成功，还有{remaining}个待发送"
            )
        )

        # 熔断设置
        self.check_circuit_enabled.setChecked(self.config.get("circuit_breaker.enabled", True))
        self.spin_failure_threshold.setValue(self.config.get("circuit_breaker.failure_threshold", 3))
        self.spin_recovery_timeout.setValue(self.config.get("circuit_breaker.recovery_timeout", 300))
        self.spin_half_open.setValue(self.config.get("circuit_breaker.half_open_attempts", 1))
        self.spin_count_reset.setValue(self.config.get("circuit_breaker.failure_count_reset", 600))

        # 显示设置
        self.spin_min_width.setValue(self.config.get("display.min_resolution.width", 1920))
        self.spin_min_height.setValue(self.config.get("display.min_resolution.height", 1080))
        self.check_primary_only.setChecked(self.config.get("display.primary_monitor_only", True))
        self.check_dpi.setChecked(self.config.get("display.check_dpi_scaling", True))
        self.spin_dpi.setValue(self.config.get("display.recommended_dpi", 100))

        # 图像识别置信度（通用配置）
        confidence_levels = self.config.get("ui_location.image_confidence_levels", [0.8, 0.6, 0.4])
        self.check_confidence_08.setChecked(0.8 in confidence_levels)
        self.check_confidence_06.setChecked(0.6 in confidence_levels)
        self.check_confidence_04.setChecked(0.4 in confidence_levels)

        # 朋友圈发布流程配置
        self.spin_moments_btn_x.setValue(self.config.get("ui_location.moments_button.absolute_x", 140))
        self.spin_moments_btn_y.setValue(self.config.get("ui_location.moments_button.absolute_y", 482))
        self.spin_moments_publish_x.setValue(self.config.get("ui_location.moments_publish_button.absolute_x", 815))
        self.spin_moments_publish_y.setValue(self.config.get("ui_location.moments_publish_button.absolute_y", 216))
        self.spin_moments_input_x.setValue(self.config.get("ui_location.moments_input_box.absolute_x", 932))
        self.spin_moments_input_y.setValue(self.config.get("ui_location.moments_input_box.absolute_y", 602))
        self.spin_moments_submit_x.setValue(self.config.get("ui_location.moments_publish_submit_button.absolute_x", 1028))
        self.spin_moments_submit_y.setValue(self.config.get("ui_location.moments_publish_submit_button.absolute_y", 1301))
        self.spin_moments_first_x.setValue(self.config.get("ui_location.moments_first_item.absolute_x", 1130))
        self.spin_moments_first_y.setValue(self.config.get("ui_location.moments_first_item.absolute_y", 1230))
        self.spin_moments_close_x.setValue(self.config.get("ui_location.moments_close_button.absolute_x", 1493))
        self.spin_moments_close_y.setValue(self.config.get("ui_location.moments_close_button.absolute_y", 212))
        # 朋友圈相对偏移配置
        self.spin_dots_btn_y_offset.setValue(self.config.get("ui_location.dots_btn_y_offset", 25))
        self.spin_send_btn_dots_x_offset.setValue(self.config.get("ui_location.send_btn_dots_x_offset", 58))
        self.spin_send_btn_dots_y_offset.setValue(self.config.get("ui_location.send_btn_dots_y_offset", 210))
        self.spin_close_btn_offset.setValue(self.config.get("ui_location.close_btn_offset", 15))

        # 群发/转发流程配置
        self.spin_group_search_x.setValue(self.config.get("group_chat.search_box.x", 290))
        self.spin_group_search_y.setValue(self.config.get("group_chat.search_box.y", 185))
        self.spin_group_input_x.setValue(self.config.get("group_chat.input_box.x", 573))
        self.spin_group_input_y.setValue(self.config.get("group_chat.input_box.y", 1053))
        self.spin_group_upload_x.setValue(self.config.get("group_chat.upload_button.x", 666))
        self.spin_group_upload_y.setValue(self.config.get("group_chat.upload_button.y", 1004))
        # 转发对话框配置
        self.spin_forward_group_x_offset.setValue(self.config.get("forward_dialog.group_option.x_offset", 150))
        self.spin_forward_group_y_offset.setValue(self.config.get("forward_dialog.group_option.y_offset", 180))
        self.spin_forward_send_x_offset.setValue(self.config.get("forward_dialog.send_button.x_offset", 663))
        self.spin_forward_send_y_offset.setValue(self.config.get("forward_dialog.send_button.y_offset", 778))

        # 小程序坐标配置（代理群）
        self.spin_miniprogram_window_x.setValue(self.config.get("miniprogram.restore_window.x", 1493))
        self.spin_miniprogram_window_y.setValue(self.config.get("miniprogram.restore_window.y", 236))
        self.spin_miniprogram_more_x.setValue(self.config.get("miniprogram.buttons.more.absolute_x", 2150))
        self.spin_miniprogram_more_y.setValue(self.config.get("miniprogram.buttons.more.absolute_y", 323))
        self.spin_miniprogram_reenter_x.setValue(self.config.get("miniprogram.buttons.reenter.absolute_x", 1871))
        self.spin_miniprogram_reenter_y.setValue(self.config.get("miniprogram.buttons.reenter.absolute_y", 835))
        self.spin_miniprogram_search_x.setValue(self.config.get("miniprogram.buttons.search.absolute_x", 2255))
        self.spin_miniprogram_search_y.setValue(self.config.get("miniprogram.buttons.search.absolute_y", 371))
        self.spin_miniprogram_product_x.setValue(self.config.get("miniprogram.buttons.product.absolute_x", 1950))
        self.spin_miniprogram_product_y.setValue(self.config.get("miniprogram.buttons.product.absolute_y", 554))
        self.spin_miniprogram_forward_x.setValue(self.config.get("miniprogram.buttons.forward.absolute_x", 2177))
        self.spin_miniprogram_forward_y.setValue(self.config.get("miniprogram.buttons.forward.absolute_y", 1110))

        # 客户群小程序坐标配置
        self.spin_miniprogram_customer_window_x.setValue(self.config.get("miniprogram_customer.restore_window.x", 1493))
        self.spin_miniprogram_customer_window_y.setValue(self.config.get("miniprogram_customer.restore_window.y", 236))
        self.spin_miniprogram_customer_more_x.setValue(self.config.get("miniprogram_customer.buttons.more.absolute_x", 2150))
        self.spin_miniprogram_customer_more_y.setValue(self.config.get("miniprogram_customer.buttons.more.absolute_y", 323))
        self.spin_miniprogram_customer_reenter_x.setValue(self.config.get("miniprogram_customer.buttons.reenter.absolute_x", 1871))
        self.spin_miniprogram_customer_reenter_y.setValue(self.config.get("miniprogram_customer.buttons.reenter.absolute_y", 835))
        self.spin_miniprogram_customer_search_x.setValue(self.config.get("miniprogram_customer.buttons.search.absolute_x", 2255))
        self.spin_miniprogram_customer_search_y.setValue(self.config.get("miniprogram_customer.buttons.search.absolute_y", 371))
        self.spin_miniprogram_customer_product_x.setValue(self.config.get("miniprogram_customer.buttons.product.absolute_x", 1950))
        self.spin_miniprogram_customer_product_y.setValue(self.config.get("miniprogram_customer.buttons.product.absolute_y", 554))
        self.spin_miniprogram_customer_forward_x.setValue(self.config.get("miniprogram_customer.buttons.forward.absolute_x", 2177))
        self.spin_miniprogram_customer_forward_y.setValue(self.config.get("miniprogram_customer.buttons.forward.absolute_y", 1110))

        # 高级设置
        log_level = self.config.get("logging.level", "INFO")
        index = self.combo_log_level.findText(log_level)
        if index >= 0:
            self.combo_log_level.setCurrentIndex(index)
        self.check_debug.setChecked(self.config.get("advanced.debug_mode", False))
        self.check_screenshots.setChecked(self.config.get("advanced.save_screenshots", False))
        self.path_screenshots.setText(self.config.get("advanced.screenshot_dir", ""))
        self.check_console.setChecked(self.config.get("logging.console_output", True))

        self._modified = False

    def save_settings(self) -> None:
        """保存配置"""
        # 验证配置
        errors = self.validate_settings()
        if errors:
            QMessageBox.warning(
                self,
                "配置验证失败",
                "以下配置项有问题:\n\n" + "\n".join(f"- {e}" for e in errors)
            )
            return

        # 路径设置
        self.config.set("paths.shared_folder", self.path_shared.text())
        self.config.set("paths.cache_dir", self.path_cache.text())
        self.config.set("paths.receipts_dir", self.path_receipts.text())
        self.config.set("paths.logs_dir", self.path_logs.text())
        self.config.set("paths.wechat_path", self.path_wechat.text())

        # 发布设置
        self.config.set("schedule.default_interval", self.spin_interval.value())
        self.config.set("schedule.daily_limit", self.spin_daily_limit.value())
        self.config.set("schedule.random_delay_min", self.spin_delay_min.value())
        self.config.set("schedule.random_delay_max", self.spin_delay_max.value())
        self.config.set("schedule.active_hours.start", self.edit_active_start.text())
        self.config.set("schedule.active_hours.end", self.edit_active_end.text())

        # 邮件设置
        self.config.set("email.enabled", self.check_email_enabled.isChecked())
        self.config.set("email.smtp.host", self.edit_smtp_host.text())
        self.config.set("email.smtp.port", self.spin_smtp_port.value())
        self.config.set("email.smtp.use_ssl", self.check_use_ssl.isChecked())
        self.config.set("email.smtp.use_tls", self.check_use_tls.isChecked())
        self.config.set("email.sender.address", self.edit_sender_address.text())

        # 密码加密存储
        password = self.edit_sender_password.text()
        if password:  # 只有输入了新密码才更新
            encrypted_password = self.config.encrypt_value(password)
            self.config.set("email.sender.password", encrypted_password)

        # 收件人列表
        recipients_text = self.edit_recipients.text()
        recipients = [r.strip() for r in recipients_text.split(",") if r.strip()]
        self.config.set("email.recipients", recipients)

        # 通知选项
        self.config.set("email.notify_on.success", self.check_notify_success.isChecked())
        self.config.set("email.notify_on.failure", self.check_notify_failure.isChecked())
        self.config.set("email.notify_on.daily_summary", self.check_notify_daily.isChecked())
        self.config.set("email.notify_on.circuit_break", self.check_notify_circuit.isChecked())

        # 语音提醒设置
        self.config.set("voice.moment_complete_enabled", self.check_voice_moment.isChecked())
        self.config.set(
            "voice.moment_complete_text",
            self.edit_voice_template.text() or DEFAULT_CONFIG["voice"]["moment_complete_text"]
        )
        self.config.set("voice.agent_group_complete_enabled", self.check_voice_agent_group.isChecked())
        self.config.set(
            "voice.agent_group_complete_text",
            self.edit_voice_agent_group_template.text() or "代理群发送成功，还有{remaining}个待发送"
        )
        self.config.set("voice.customer_group_complete_enabled", self.check_voice_customer_group.isChecked())
        self.config.set(
            "voice.customer_group_complete_text",
            self.edit_voice_customer_group_template.text() or "客户群发送成功，还有{remaining}个待发送"
        )

        # 熔断设置
        self.config.set("circuit_breaker.enabled", self.check_circuit_enabled.isChecked())
        self.config.set("circuit_breaker.failure_threshold", self.spin_failure_threshold.value())
        self.config.set("circuit_breaker.recovery_timeout", self.spin_recovery_timeout.value())
        self.config.set("circuit_breaker.half_open_attempts", self.spin_half_open.value())
        self.config.set("circuit_breaker.failure_count_reset", self.spin_count_reset.value())

        # 显示设置
        self.config.set("display.min_resolution.width", self.spin_min_width.value())
        self.config.set("display.min_resolution.height", self.spin_min_height.value())
        self.config.set("display.primary_monitor_only", self.check_primary_only.isChecked())
        self.config.set("display.check_dpi_scaling", self.check_dpi.isChecked())
        self.config.set("display.recommended_dpi", self.spin_dpi.value())

        # 图像识别置信度（通用配置）
        confidence_levels = []
        if self.check_confidence_08.isChecked():
            confidence_levels.append(0.8)
        if self.check_confidence_06.isChecked():
            confidence_levels.append(0.6)
        if self.check_confidence_04.isChecked():
            confidence_levels.append(0.4)
        if not confidence_levels:
            confidence_levels = [0.8, 0.6, 0.4]  # 默认全选
        self.config.set("ui_location.image_confidence_levels", confidence_levels)

        # 朋友圈发布流程配置
        self.config.set("ui_location.moments_button.absolute_x", self.spin_moments_btn_x.value())
        self.config.set("ui_location.moments_button.absolute_y", self.spin_moments_btn_y.value())
        self.config.set("ui_location.moments_publish_button.absolute_x", self.spin_moments_publish_x.value())
        self.config.set("ui_location.moments_publish_button.absolute_y", self.spin_moments_publish_y.value())
        self.config.set("ui_location.moments_input_box.absolute_x", self.spin_moments_input_x.value())
        self.config.set("ui_location.moments_input_box.absolute_y", self.spin_moments_input_y.value())
        self.config.set("ui_location.moments_publish_submit_button.absolute_x", self.spin_moments_submit_x.value())
        self.config.set("ui_location.moments_publish_submit_button.absolute_y", self.spin_moments_submit_y.value())
        self.config.set("ui_location.moments_first_item.absolute_x", self.spin_moments_first_x.value())
        self.config.set("ui_location.moments_first_item.absolute_y", self.spin_moments_first_y.value())
        self.config.set("ui_location.moments_close_button.absolute_x", self.spin_moments_close_x.value())
        self.config.set("ui_location.moments_close_button.absolute_y", self.spin_moments_close_y.value())
        # 朋友圈相对偏移配置
        self.config.set("ui_location.dots_btn_y_offset", self.spin_dots_btn_y_offset.value())
        self.config.set("ui_location.send_btn_dots_x_offset", self.spin_send_btn_dots_x_offset.value())
        self.config.set("ui_location.send_btn_dots_y_offset", self.spin_send_btn_dots_y_offset.value())
        self.config.set("ui_location.close_btn_offset", self.spin_close_btn_offset.value())

        # 群发/转发流程配置
        self.config.set("group_chat.search_box.x", self.spin_group_search_x.value())
        self.config.set("group_chat.search_box.y", self.spin_group_search_y.value())
        self.config.set("group_chat.input_box.x", self.spin_group_input_x.value())
        self.config.set("group_chat.input_box.y", self.spin_group_input_y.value())
        self.config.set("group_chat.upload_button.x", self.spin_group_upload_x.value())
        self.config.set("group_chat.upload_button.y", self.spin_group_upload_y.value())
        # 转发对话框配置
        self.config.set("forward_dialog.group_option.x_offset", self.spin_forward_group_x_offset.value())
        self.config.set("forward_dialog.group_option.y_offset", self.spin_forward_group_y_offset.value())
        self.config.set("forward_dialog.send_button.x_offset", self.spin_forward_send_x_offset.value())
        self.config.set("forward_dialog.send_button.y_offset", self.spin_forward_send_y_offset.value())

        # 小程序坐标配置（代理群）
        self.config.set("miniprogram.restore_window.x", self.spin_miniprogram_window_x.value())
        self.config.set("miniprogram.restore_window.y", self.spin_miniprogram_window_y.value())
        self.config.set("miniprogram.buttons.more.absolute_x", self.spin_miniprogram_more_x.value())
        self.config.set("miniprogram.buttons.more.absolute_y", self.spin_miniprogram_more_y.value())
        self.config.set("miniprogram.buttons.reenter.absolute_x", self.spin_miniprogram_reenter_x.value())
        self.config.set("miniprogram.buttons.reenter.absolute_y", self.spin_miniprogram_reenter_y.value())
        self.config.set("miniprogram.buttons.search.absolute_x", self.spin_miniprogram_search_x.value())
        self.config.set("miniprogram.buttons.search.absolute_y", self.spin_miniprogram_search_y.value())
        self.config.set("miniprogram.buttons.product.absolute_x", self.spin_miniprogram_product_x.value())
        self.config.set("miniprogram.buttons.product.absolute_y", self.spin_miniprogram_product_y.value())
        self.config.set("miniprogram.buttons.forward.absolute_x", self.spin_miniprogram_forward_x.value())
        self.config.set("miniprogram.buttons.forward.absolute_y", self.spin_miniprogram_forward_y.value())

        # 客户群小程序坐标配置
        self.config.set("miniprogram_customer.restore_window.x", self.spin_miniprogram_customer_window_x.value())
        self.config.set("miniprogram_customer.restore_window.y", self.spin_miniprogram_customer_window_y.value())
        self.config.set("miniprogram_customer.buttons.more.absolute_x", self.spin_miniprogram_customer_more_x.value())
        self.config.set("miniprogram_customer.buttons.more.absolute_y", self.spin_miniprogram_customer_more_y.value())
        self.config.set("miniprogram_customer.buttons.reenter.absolute_x", self.spin_miniprogram_customer_reenter_x.value())
        self.config.set("miniprogram_customer.buttons.reenter.absolute_y", self.spin_miniprogram_customer_reenter_y.value())
        self.config.set("miniprogram_customer.buttons.search.absolute_x", self.spin_miniprogram_customer_search_x.value())
        self.config.set("miniprogram_customer.buttons.search.absolute_y", self.spin_miniprogram_customer_search_y.value())
        self.config.set("miniprogram_customer.buttons.product.absolute_x", self.spin_miniprogram_customer_product_x.value())
        self.config.set("miniprogram_customer.buttons.product.absolute_y", self.spin_miniprogram_customer_product_y.value())
        self.config.set("miniprogram_customer.buttons.forward.absolute_x", self.spin_miniprogram_customer_forward_x.value())
        self.config.set("miniprogram_customer.buttons.forward.absolute_y", self.spin_miniprogram_customer_forward_y.value())

        # 高级设置
        self.config.set("logging.level", self.combo_log_level.currentText())
        self.config.set("advanced.debug_mode", self.check_debug.isChecked())
        self.config.set("advanced.save_screenshots", self.check_screenshots.isChecked())
        self.config.set("advanced.screenshot_dir", self.path_screenshots.text())
        self.config.set("logging.console_output", self.check_console.isChecked())

        # 保存到文件
        if self.config.save():
            self._modified = False
            self.settings_saved.emit()
            QMessageBox.information(self, "成功", "配置已保存")
        else:
            QMessageBox.critical(self, "错误", "保存配置失败")

    def validate_settings(self) -> List[str]:
        """
        验证配置

        Returns:
            错误列表
        """
        errors = []

        # 验证路径
        paths_to_check = [
            ("共享文件夹", self.path_shared.text()),
            ("缓存目录", self.path_cache.text()),
            ("回执目录", self.path_receipts.text()),
            ("日志目录", self.path_logs.text()),
        ]

        for name, path in paths_to_check:
            if path:
                p = Path(path)
                # 检查父目录是否存在
                if not p.parent.exists():
                    errors.append(f"{name}的父目录不存在: {p.parent}")

        # 验证时间格式
        time_pattern = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
        if self.edit_active_start.text() and not time_pattern.match(self.edit_active_start.text()):
            errors.append("活动开始时间格式无效，应为 HH:MM")
        if self.edit_active_end.text() and not time_pattern.match(self.edit_active_end.text()):
            errors.append("活动结束时间格式无效，应为 HH:MM")

        # 验证随机延迟范围
        if self.spin_delay_min.value() > self.spin_delay_max.value():
            errors.append("随机延迟最小值不能大于最大值")

        # 验证邮箱格式
        if self.check_email_enabled.isChecked():
            email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

            sender = self.edit_sender_address.text()
            if sender and not email_pattern.match(sender):
                errors.append("发件人邮箱格式无效")

            recipients = self.edit_recipients.text()
            if recipients:
                for r in recipients.split(","):
                    r = r.strip()
                    if r and not email_pattern.match(r):
                        errors.append(f"收件人邮箱格式无效: {r}")

            # 必填项检查
            if not self.edit_smtp_host.text():
                errors.append("启用邮件通知时 SMTP 服务器不能为空")
            if not self.edit_sender_address.text():
                errors.append("启用邮件通知时发件人地址不能为空")

        return errors

    def reset_to_defaults(self) -> None:
        """恢复默认设置"""
        reply = QMessageBox.question(
            self,
            "确认恢复",
            "确定要恢复所有设置为默认值吗？\n此操作不会立即保存，需要点击保存按钮。",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 路径设置
            self.path_shared.setText(DEFAULT_CONFIG["paths"]["shared_folder"])
            self.path_cache.setText(DEFAULT_CONFIG["paths"]["cache_dir"])
            self.path_receipts.setText(DEFAULT_CONFIG["paths"]["receipts_dir"])
            self.path_logs.setText(DEFAULT_CONFIG["paths"]["logs_dir"])
            self.path_wechat.setText(DEFAULT_CONFIG["paths"]["wechat_path"])

            # 发布设置
            self.spin_interval.setValue(DEFAULT_CONFIG["schedule"]["default_interval"])
            self.spin_daily_limit.setValue(DEFAULT_CONFIG["schedule"]["daily_limit"])
            self.spin_delay_min.setValue(DEFAULT_CONFIG["schedule"]["random_delay_min"])
            self.spin_delay_max.setValue(DEFAULT_CONFIG["schedule"]["random_delay_max"])
            self.edit_active_start.setText(DEFAULT_CONFIG["schedule"]["active_hours"]["start"])
            self.edit_active_end.setText(DEFAULT_CONFIG["schedule"]["active_hours"]["end"])

            # 邮件设置
            self.check_email_enabled.setChecked(DEFAULT_CONFIG["email"]["enabled"])
            self.edit_smtp_host.setText(DEFAULT_CONFIG["email"]["smtp"]["host"])
            self.spin_smtp_port.setValue(DEFAULT_CONFIG["email"]["smtp"]["port"])
            self.check_use_ssl.setChecked(DEFAULT_CONFIG["email"]["smtp"]["use_ssl"])
            self.check_use_tls.setChecked(DEFAULT_CONFIG["email"]["smtp"]["use_tls"])
            self.edit_sender_address.setText(DEFAULT_CONFIG["email"]["sender"]["address"])
            self.edit_sender_password.clear()
            self.edit_recipients.clear()
            self.check_notify_success.setChecked(DEFAULT_CONFIG["email"]["notify_on"]["success"])
            self.check_notify_failure.setChecked(DEFAULT_CONFIG["email"]["notify_on"]["failure"])
            self.check_notify_daily.setChecked(DEFAULT_CONFIG["email"]["notify_on"]["daily_summary"])
            self.check_notify_circuit.setChecked(DEFAULT_CONFIG["email"]["notify_on"]["circuit_break"])

            # 熔断设置
            self.check_circuit_enabled.setChecked(DEFAULT_CONFIG["circuit_breaker"]["enabled"])
            self.spin_failure_threshold.setValue(DEFAULT_CONFIG["circuit_breaker"]["failure_threshold"])
            self.spin_recovery_timeout.setValue(DEFAULT_CONFIG["circuit_breaker"]["recovery_timeout"])
            self.spin_half_open.setValue(DEFAULT_CONFIG["circuit_breaker"]["half_open_attempts"])
            self.spin_count_reset.setValue(DEFAULT_CONFIG["circuit_breaker"]["failure_count_reset"])

            # 显示设置
            self.spin_min_width.setValue(DEFAULT_CONFIG["display"]["min_resolution"]["width"])
            self.spin_min_height.setValue(DEFAULT_CONFIG["display"]["min_resolution"]["height"])
            self.check_primary_only.setChecked(DEFAULT_CONFIG["display"]["primary_monitor_only"])
            self.check_dpi.setChecked(DEFAULT_CONFIG["display"]["check_dpi_scaling"])
            self.spin_dpi.setValue(DEFAULT_CONFIG["display"]["recommended_dpi"])

            # 通用配置（恢复默认值）
            self.check_confidence_08.setChecked(True)
            self.check_confidence_06.setChecked(True)
            self.check_confidence_04.setChecked(True)

            # 朋友圈发布流程配置（恢复默认值）
            self.spin_moments_btn_x.setValue(140)
            self.spin_moments_btn_y.setValue(482)
            self.spin_moments_publish_x.setValue(815)
            self.spin_moments_publish_y.setValue(216)
            self.spin_moments_input_x.setValue(932)
            self.spin_moments_input_y.setValue(602)
            self.spin_moments_submit_x.setValue(1028)
            self.spin_moments_submit_y.setValue(1301)
            self.spin_moments_first_x.setValue(1130)
            self.spin_moments_first_y.setValue(1230)
            self.spin_moments_close_x.setValue(1493)
            self.spin_moments_close_y.setValue(212)
            # 朋友圈相对偏移（恢复默认值）
            self.spin_dots_btn_y_offset.setValue(25)
            self.spin_send_btn_dots_x_offset.setValue(58)
            self.spin_send_btn_dots_y_offset.setValue(210)
            self.spin_close_btn_offset.setValue(15)

            # 群发/转发流程配置（恢复默认值）
            self.spin_group_search_x.setValue(290)
            self.spin_group_search_y.setValue(185)
            self.spin_group_input_x.setValue(573)
            self.spin_group_input_y.setValue(1053)
            self.spin_group_upload_x.setValue(666)
            self.spin_group_upload_y.setValue(1004)
            # 转发对话框（恢复默认值）
            self.spin_forward_group_x_offset.setValue(150)
            self.spin_forward_group_y_offset.setValue(180)
            self.spin_forward_send_x_offset.setValue(663)
            self.spin_forward_send_y_offset.setValue(778)

            # 小程序坐标配置（代理群，恢复默认值）
            self.spin_miniprogram_window_x.setValue(1493)
            self.spin_miniprogram_window_y.setValue(236)
            self.spin_miniprogram_more_x.setValue(2150)
            self.spin_miniprogram_more_y.setValue(323)
            self.spin_miniprogram_reenter_x.setValue(1871)
            self.spin_miniprogram_reenter_y.setValue(835)
            self.spin_miniprogram_search_x.setValue(2255)
            self.spin_miniprogram_search_y.setValue(371)
            self.spin_miniprogram_product_x.setValue(1950)
            self.spin_miniprogram_product_y.setValue(554)
            self.spin_miniprogram_forward_x.setValue(2177)
            self.spin_miniprogram_forward_y.setValue(1110)

            # 客户群小程序坐标配置（恢复默认值）
            self.spin_miniprogram_customer_window_x.setValue(1493)
            self.spin_miniprogram_customer_window_y.setValue(236)
            self.spin_miniprogram_customer_more_x.setValue(2150)
            self.spin_miniprogram_customer_more_y.setValue(323)
            self.spin_miniprogram_customer_reenter_x.setValue(1871)
            self.spin_miniprogram_customer_reenter_y.setValue(835)
            self.spin_miniprogram_customer_search_x.setValue(2255)
            self.spin_miniprogram_customer_search_y.setValue(371)
            self.spin_miniprogram_customer_product_x.setValue(1950)
            self.spin_miniprogram_customer_product_y.setValue(554)
            self.spin_miniprogram_customer_forward_x.setValue(2177)
            self.spin_miniprogram_customer_forward_y.setValue(1110)

            # 高级设置
            index = self.combo_log_level.findText(DEFAULT_CONFIG["logging"]["level"])
            if index >= 0:
                self.combo_log_level.setCurrentIndex(index)
            self.check_debug.setChecked(DEFAULT_CONFIG["advanced"]["debug_mode"])
            self.check_screenshots.setChecked(DEFAULT_CONFIG["advanced"]["save_screenshots"])
            self.path_screenshots.setText(DEFAULT_CONFIG["advanced"]["screenshot_dir"])
            self.check_console.setChecked(DEFAULT_CONFIG["logging"]["console_output"])

            self._modified = True
            QMessageBox.information(self, "已恢复", "已恢复为默认设置，请点击保存按钮确认。")

    def test_email_connection(self) -> None:
        """测试邮件连接"""
        # 验证必填项
        if not self.edit_smtp_host.text():
            QMessageBox.warning(self, "错误", "请输入 SMTP 服务器地址")
            return

        if not self.edit_sender_address.text():
            QMessageBox.warning(self, "错误", "请输入发件人邮箱地址")
            return

        # 获取密码
        password = self.edit_sender_password.text()
        if not password:
            # 尝试使用已保存的密码
            saved_password = self.config.get("email.sender.password", "")
            if saved_password:
                password = self.config.decrypt_value(saved_password)
            else:
                QMessageBox.warning(self, "错误", "请输入邮箱密码或授权码")
                return

        try:
            # 创建 SMTP 连接
            host = self.edit_smtp_host.text()
            port = self.spin_smtp_port.value()

            if self.check_use_ssl.isChecked():
                server = smtplib.SMTP_SSL(host, port, timeout=10)
            else:
                server = smtplib.SMTP(host, port, timeout=10)
                if self.check_use_tls.isChecked():
                    server.starttls()

            # 登录
            server.login(self.edit_sender_address.text(), password)

            # 发送测试邮件
            recipients = self.edit_recipients.text()
            if recipients:
                recipient = recipients.split(",")[0].strip()
                msg = MIMEText("这是一封测试邮件，来自微信发布助手。", "plain", "utf-8")
                msg["Subject"] = "微信发布助手 - 邮件测试"
                msg["From"] = self.edit_sender_address.text()
                msg["To"] = recipient
                server.sendmail(self.edit_sender_address.text(), [recipient], msg.as_string())
                QMessageBox.information(
                    self, "成功", f"邮件连接测试成功！\n已发送测试邮件到 {recipient}"
                )
            else:
                QMessageBox.information(self, "成功", "邮件服务器连接测试成功！")

            server.quit()

        except smtplib.SMTPAuthenticationError:
            QMessageBox.critical(self, "错误", "邮箱认证失败，请检查邮箱地址和密码（授权码）")
        except smtplib.SMTPConnectError:
            QMessageBox.critical(self, "错误", "无法连接到 SMTP 服务器，请检查服务器地址和端口")
        except TimeoutError:
            QMessageBox.critical(self, "错误", "连接超时，请检查网络或服务器地址")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"测试失败: {str(e)}")

    @property
    def is_modified(self) -> bool:
        """是否有未保存的修改"""
        return self._modified
