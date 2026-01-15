"""统计标签页 - 数据可视化和报表导出"""

from datetime import datetime
from typing import Optional, List
import math

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QDateEdit,
    QFrame, QHeaderView, QFileDialog, QMessageBox, QGroupBox,
)
from PySide6.QtCore import Qt, QDate, Signal

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# 配置 matplotlib 中文字体
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

from models.stats import DailyStats, TaskSummary


# 深色主题颜色
class DarkColors:
    BACKGROUND = "#1E1E1E"
    SURFACE = "#2D2D2D"
    CARD_BG = "#252525"
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#B0B0B0"
    BORDER = "#404040"
    PRIMARY = "#90CAF9"
    SUCCESS = "#4CAF50"
    ERROR = "#F44336"
    WARNING = "#FF9800"
    PENDING = "#9E9E9E"


class StatCard(QFrame):
    """统计卡片组件"""

    def __init__(
        self,
        title: str,
        value: int = 0,
        color: str = DarkColors.PRIMARY,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._title = title
        self._value = value
        self._color = color
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setStyleSheet(f"""
            StatCard {{
                background-color: {DarkColors.CARD_BG};
                border: 1px solid {DarkColors.BORDER};
                border-left: 4px solid {self._color};
                border-radius: 8px;
            }}
        """)
        self.setMinimumWidth(180)
        self.setMinimumHeight(100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 标题
        self._title_label = QLabel(self._title)
        self._title_label.setStyleSheet(f"""
            QLabel {{
                color: {DarkColors.TEXT_SECONDARY};
                font-size: 13px;
                background: transparent;
            }}
        """)
        layout.addWidget(self._title_label)

        # 数值
        self._value_label = QLabel(str(self._value))
        self._value_label.setStyleSheet(f"""
            QLabel {{
                color: {self._color};
                font-size: 32px;
                font-weight: bold;
                background: transparent;
            }}
        """)
        layout.addWidget(self._value_label)

        layout.addStretch()

    def set_value(self, value: int):
        """更新数值"""
        self._value = value
        self._value_label.setText(str(value))


class TrendChart(QWidget):
    """趋势折线图组件"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._figure = None
        self._canvas = None
        self._ax = None
        self._stats_list = []  # 保存原始数据
        self._lines = []  # 存储绑定的 Line2D 对象
        self._annotation = None  # tooltip annotation
        self._highlight_point = None  # 高亮数据点
        self._setup_ui()

    def closeEvent(self, event):
        """清理 matplotlib 资源"""
        if self._figure is not None:
            plt.close(self._figure)
        super().closeEvent(event)

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建matplotlib图表 - 深色主题
        self._figure = Figure(figsize=(6, 4), dpi=100)
        self._figure.patch.set_facecolor(DarkColors.SURFACE)
        self._canvas = FigureCanvas(self._figure)
        self._ax = self._figure.add_subplot(111)

        layout.addWidget(self._canvas)

        # 初始化空图表
        self._init_chart()

        # 创建 tooltip annotation
        self._annotation = self._ax.annotate(
            "", xy=(0, 0), xytext=(15, 15),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#424242", edgecolor="none", alpha=0.9),
            color="white",
            fontsize=10,
            visible=False,
            zorder=100
        )

        # 创建高亮点（初始隐藏）
        self._highlight_point, = self._ax.plot([], [], 'o',
            color='white', markersize=12, markeredgecolor='white',
            markerfacecolor='none', markeredgewidth=2, visible=False, zorder=99)

        # 绑定鼠标移动事件
        self._canvas.mpl_connect('motion_notify_event', self._on_mouse_move)

    def _init_chart(self):
        """初始化图表样式 - 深色主题"""
        self._ax.set_facecolor(DarkColors.SURFACE)
        self._ax.tick_params(colors=DarkColors.TEXT_SECONDARY, labelsize=9)
        self._ax.spines['bottom'].set_color(DarkColors.BORDER)
        self._ax.spines['top'].set_visible(False)
        self._ax.spines['right'].set_visible(False)
        self._ax.spines['left'].set_color(DarkColors.BORDER)
        self._ax.set_title('近7天发布趋势', color=DarkColors.TEXT_PRIMARY, fontsize=12, pad=10)
        self._ax.set_xlabel('日期', color=DarkColors.TEXT_SECONDARY, fontsize=10)
        self._ax.set_ylabel('任务数', color=DarkColors.TEXT_SECONDARY, fontsize=10)

    def _on_mouse_move(self, event):
        """处理鼠标移动事件，显示tooltip和高亮"""
        if event.inaxes != self._ax or not self._stats_list or not self._lines:
            # 鼠标不在图表区域内或无数据，隐藏tooltip
            if self._annotation and self._annotation.get_visible():
                self._annotation.set_visible(False)
                self._highlight_point.set_visible(False)
                self._canvas.draw_idle()
            return

        # 查找最近的数据点
        min_dist = float('inf')
        closest_idx = -1
        closest_line_idx = -1
        closest_x = None
        closest_y = None

        for line_idx, line in enumerate(self._lines):
            xdata = line.get_xdata()
            ydata = line.get_ydata()

            for i in range(len(xdata)):
                # 将数据坐标转换为显示坐标
                try:
                    display_coords = self._ax.transData.transform((i, ydata[i]))
                    mouse_coords = (event.x, event.y)
                    dist = ((display_coords[0] - mouse_coords[0]) ** 2 +
                           (display_coords[1] - mouse_coords[1]) ** 2) ** 0.5
                    if dist < min_dist:
                        min_dist = dist
                        closest_idx = i
                        closest_line_idx = line_idx
                        closest_x = i
                        closest_y = ydata[i]
                except (ValueError, IndexError):
                    continue

        # 如果距离小于阈值（30像素），显示tooltip
        if min_dist < 30 and closest_idx >= 0 and closest_idx < len(self._stats_list):
            stats = self._stats_list[closest_idx]
            date_str = stats.stat_date.strftime('%Y-%m-%d') if hasattr(stats.stat_date, 'strftime') else str(stats.stat_date)
            tooltip_text = f"{date_str}\n总数: {stats.total_tasks}\n成功: {stats.success_count}\n失败: {stats.failed_count}"

            # 更新annotation位置和文本
            self._annotation.xy = (closest_x, closest_y)
            self._annotation.set_text(tooltip_text)
            self._annotation.set_visible(True)

            # 更新高亮点位置
            self._highlight_point.set_data([closest_x], [closest_y])
            self._highlight_point.set_visible(True)

            self._canvas.draw_idle()
        else:
            # 隐藏tooltip和高亮点
            if self._annotation.get_visible():
                self._annotation.set_visible(False)
                self._highlight_point.set_visible(False)
                self._canvas.draw_idle()

    def update_data(self, stats_list: List[DailyStats]):
        """更新图表数据"""
        self._ax.clear()
        self._init_chart()
        self._lines = []  # 清空之前的线条引用
        self._stats_list = stats_list  # 保存数据供tooltip使用

        if not stats_list:
            self._ax.text(0.5, 0.5, '暂无数据', ha='center', va='center',
                         transform=self._ax.transAxes, color=DarkColors.TEXT_SECONDARY, fontsize=14)
            self._canvas.draw()
            return

        # 提取数据 - 使用索引作为x轴
        total = [s.total_tasks for s in stats_list]
        success = [s.success_count for s in stats_list]
        failed = [s.failed_count for s in stats_list]
        x_indices = list(range(len(stats_list)))

        # 绘制折线 - 使用明亮的颜色，保存线条引用
        line1, = self._ax.plot(x_indices, total, 'o-', color=DarkColors.PRIMARY, label='总数', linewidth=2, markersize=6)
        line2, = self._ax.plot(x_indices, success, 's-', color=DarkColors.SUCCESS, label='成功', linewidth=2, markersize=6)
        line3, = self._ax.plot(x_indices, failed, '^-', color=DarkColors.ERROR, label='失败', linewidth=2, markersize=6)
        self._lines = [line1, line2, line3]

        # 设置x轴标签为日期
        date_labels = [s.stat_date.strftime('%Y-%m-%d') if hasattr(s.stat_date, 'strftime') else str(s.stat_date) for s in stats_list]
        self._ax.set_xticks(x_indices)
        self._ax.set_xticklabels(date_labels)

        # 设置图例 - 深色主题
        legend = self._ax.legend(loc='upper left', framealpha=0.8, facecolor=DarkColors.SURFACE,
                                  edgecolor=DarkColors.BORDER, labelcolor=DarkColors.TEXT_PRIMARY)

        # 旋转x轴标签
        plt.setp(self._ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # 重新创建 tooltip annotation（因为 clear() 会清除它）
        self._annotation = self._ax.annotate(
            "", xy=(0, 0), xytext=(15, 15),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#424242", edgecolor="none", alpha=0.9),
            color="white",
            fontsize=10,
            visible=False,
            zorder=100
        )

        # 重新创建高亮点
        self._highlight_point, = self._ax.plot([], [], 'o',
            color='white', markersize=12, markeredgecolor='white',
            markerfacecolor='none', markeredgewidth=2, visible=False, zorder=99)

        self._figure.tight_layout()
        self._canvas.draw()


class CombinedTrendChart(QWidget):
    """合并趋势图组件 - 支持切换显示任务趋势或渠道趋势"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._figure = None
        self._canvas = None
        self._ax = None
        self._stats_list = []  # 保存原始数据
        self._lines = []  # 存储绑定的 Line2D 对象
        self._annotation = None  # tooltip annotation
        self._highlight_point = None  # 高亮数据点
        self._mode = 'task'  # 当前模式: 'task' 或 'channel'
        self._show_channel_success = False  # 渠道模式下是否显示成功数
        self._setup_ui()

    def closeEvent(self, event):
        """清理 matplotlib 资源"""
        if self._figure is not None:
            plt.close(self._figure)
        super().closeEvent(event)

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 切换按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._btn_task = QPushButton("任务趋势")
        self._btn_channel = QPushButton("渠道趋势")

        self._btn_task.setFixedHeight(28)
        self._btn_channel.setFixedHeight(28)
        self._btn_task.setCursor(Qt.PointingHandCursor)
        self._btn_channel.setCursor(Qt.PointingHandCursor)

        self._btn_task.clicked.connect(lambda: self._switch_mode('task'))
        self._btn_channel.clicked.connect(lambda: self._switch_mode('channel'))

        btn_layout.addWidget(self._btn_task)
        btn_layout.addWidget(self._btn_channel)

        # 渠道模式下的总数/成功切换按钮
        btn_layout.addSpacing(20)
        self._btn_channel_total = QPushButton("总数")
        self._btn_channel_success = QPushButton("成功")
        self._btn_channel_total.setFixedHeight(28)
        self._btn_channel_success.setFixedHeight(28)
        self._btn_channel_total.setCursor(Qt.PointingHandCursor)
        self._btn_channel_success.setCursor(Qt.PointingHandCursor)
        self._btn_channel_total.clicked.connect(lambda: self._switch_channel_data(False))
        self._btn_channel_success.clicked.connect(lambda: self._switch_channel_data(True))
        btn_layout.addWidget(self._btn_channel_total)
        btn_layout.addWidget(self._btn_channel_success)
        # 初始隐藏渠道数据切换按钮
        self._btn_channel_total.setVisible(False)
        self._btn_channel_success.setVisible(False)

        # 按钮样式（必须在所有按钮创建后调用）
        self._update_button_styles()

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        # 创建matplotlib图表 - 深色主题
        self._figure = Figure(figsize=(6, 4), dpi=100)
        self._figure.patch.set_facecolor(DarkColors.SURFACE)
        self._canvas = FigureCanvas(self._figure)
        self._ax = self._figure.add_subplot(111)

        layout.addWidget(self._canvas)

        # 初始化空图表
        self._init_chart()

        # 创建 tooltip annotation
        self._annotation = self._ax.annotate(
            "", xy=(0, 0), xytext=(15, 15),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#424242", edgecolor="none", alpha=0.9),
            color="white",
            fontsize=10,
            visible=False,
            zorder=100
        )

        # 创建高亮点（初始隐藏）
        self._highlight_point, = self._ax.plot([], [], 'o',
            color='white', markersize=12, markeredgecolor='white',
            markerfacecolor='none', markeredgewidth=2, visible=False, zorder=99)

        # 绑定鼠标移动事件
        self._canvas.mpl_connect('motion_notify_event', self._on_mouse_move)

    def _update_button_styles(self):
        """更新按钮样式"""
        active_style = f"""
            QPushButton {{
                background-color: {DarkColors.PRIMARY};
                color: #000000;
                padding: 4px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background-color: {DarkColors.BORDER};
                color: {DarkColors.TEXT_SECONDARY};
                padding: 4px 16px;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #505050;
            }}
        """

        if self._mode == 'task':
            self._btn_task.setStyleSheet(active_style)
            self._btn_channel.setStyleSheet(inactive_style)
        else:
            self._btn_task.setStyleSheet(inactive_style)
            self._btn_channel.setStyleSheet(active_style)

        # 渠道数据按钮样式
        if self._show_channel_success:
            self._btn_channel_total.setStyleSheet(inactive_style)
            self._btn_channel_success.setStyleSheet(active_style)
        else:
            self._btn_channel_total.setStyleSheet(active_style)
            self._btn_channel_success.setStyleSheet(inactive_style)

    def _switch_mode(self, mode: str):
        """切换显示模式"""
        if self._mode != mode:
            self._mode = mode
            self._update_button_styles()
            # 显示/隐藏渠道数据切换按钮
            self._btn_channel_total.setVisible(mode == 'channel')
            self._btn_channel_success.setVisible(mode == 'channel')
            self._redraw_chart()

    def _switch_channel_data(self, show_success: bool):
        """切换渠道数据显示模式（总数/成功）"""
        if self._show_channel_success != show_success:
            self._show_channel_success = show_success
            self._update_button_styles()
            self._redraw_chart()

    def _init_chart(self):
        """初始化图表样式 - 深色主题"""
        self._ax.set_facecolor(DarkColors.SURFACE)
        self._ax.tick_params(colors=DarkColors.TEXT_SECONDARY, labelsize=9)
        self._ax.spines['bottom'].set_color(DarkColors.BORDER)
        self._ax.spines['top'].set_visible(False)
        self._ax.spines['right'].set_visible(False)
        self._ax.spines['left'].set_color(DarkColors.BORDER)

        title = '近7天发布趋势' if self._mode == 'task' else '渠道趋势对比'
        self._ax.set_title(title, color=DarkColors.TEXT_PRIMARY, fontsize=12, pad=10)
        self._ax.set_xlabel('日期', color=DarkColors.TEXT_SECONDARY, fontsize=10)
        self._ax.set_ylabel('任务数', color=DarkColors.TEXT_SECONDARY, fontsize=10)

    def _on_mouse_move(self, event):
        """处理鼠标移动事件，显示tooltip和高亮"""
        if event.inaxes != self._ax or not self._stats_list or not self._lines:
            if self._annotation and self._annotation.get_visible():
                self._annotation.set_visible(False)
                self._highlight_point.set_visible(False)
                self._canvas.draw_idle()
            return

        # 查找最近的数据点
        min_dist = float('inf')
        closest_idx = -1
        closest_x = None
        closest_y = None

        for line in self._lines:
            xdata = line.get_xdata()
            ydata = line.get_ydata()

            for i in range(len(xdata)):
                try:
                    display_coords = self._ax.transData.transform((i, ydata[i]))
                    mouse_coords = (event.x, event.y)
                    dist = ((display_coords[0] - mouse_coords[0]) ** 2 +
                           (display_coords[1] - mouse_coords[1]) ** 2) ** 0.5
                    if dist < min_dist:
                        min_dist = dist
                        closest_idx = i
                        closest_x = i
                        closest_y = ydata[i]
                except (ValueError, IndexError):
                    continue

        if min_dist < 30 and closest_idx >= 0 and closest_idx < len(self._stats_list):
            stats = self._stats_list[closest_idx]
            date_str = stats.stat_date.strftime('%Y-%m-%d') if hasattr(stats.stat_date, 'strftime') else str(stats.stat_date)

            if self._mode == 'task':
                tooltip_text = f"{date_str}\n总数: {stats.total_tasks}\n成功: {stats.success_count}\n失败: {stats.failed_count}"
            else:
                if self._show_channel_success:
                    tooltip_text = f"{date_str}\n朋友圈(成功): {stats.moment_success_count}\n代理群(成功): {stats.agent_group_success_count}\n客户群(成功): {stats.customer_group_success_count}"
                else:
                    tooltip_text = f"{date_str}\n朋友圈: {stats.moment_count}\n代理群: {stats.agent_group_count}\n客户群: {stats.customer_group_count}"

            # 根据数据点位置动态调整 tooltip 方向，避免被遮挡
            total_points = len(self._stats_list)
            if total_points > 1 and closest_idx >= total_points - 2:
                # 右侧数据点：tooltip 显示在左侧
                self._annotation.set_anncoords("offset points")
                self._annotation.xyann = (-100, 15)
            else:
                # 左侧/中间数据点：tooltip 显示在右侧
                self._annotation.set_anncoords("offset points")
                self._annotation.xyann = (15, 15)

            self._annotation.xy = (closest_x, closest_y)
            self._annotation.set_text(tooltip_text)
            self._annotation.set_visible(True)
            self._highlight_point.set_data([closest_x], [closest_y])
            self._highlight_point.set_visible(True)
            self._canvas.draw_idle()
        else:
            if self._annotation.get_visible():
                self._annotation.set_visible(False)
                self._highlight_point.set_visible(False)
                self._canvas.draw_idle()

    def _redraw_chart(self):
        """重绘图表"""
        if self._stats_list:
            self.update_data(self._stats_list)

    def update_data(self, stats_list: List[DailyStats]):
        """更新图表数据"""
        self._ax.clear()
        self._init_chart()
        self._lines = []
        self._stats_list = stats_list

        if not stats_list:
            self._ax.text(0.5, 0.5, '暂无数据', ha='center', va='center',
                         transform=self._ax.transAxes, color=DarkColors.TEXT_SECONDARY, fontsize=14)
            self._canvas.draw()
            return

        x_indices = list(range(len(stats_list)))

        if self._mode == 'task':
            # 任务趋势: 总数、成功、失败
            total = [s.total_tasks for s in stats_list]
            success = [s.success_count for s in stats_list]
            failed = [s.failed_count for s in stats_list]

            line1, = self._ax.plot(x_indices, total, 'o-', color=DarkColors.PRIMARY, label='总数', linewidth=2, markersize=6)
            line2, = self._ax.plot(x_indices, success, 's-', color=DarkColors.SUCCESS, label='成功', linewidth=2, markersize=6)
            line3, = self._ax.plot(x_indices, failed, '^-', color=DarkColors.ERROR, label='失败', linewidth=2, markersize=6)
            self._lines = [line1, line2, line3]
        else:
            # 渠道趋势: 朋友圈、代理群、客户群
            if self._show_channel_success:
                # 显示成功数
                moment = [s.moment_success_count for s in stats_list]
                agent_group = [s.agent_group_success_count for s in stats_list]
                customer_group = [s.customer_group_success_count for s in stats_list]
                suffix = "(成功)"
            else:
                # 显示总数
                moment = [s.moment_count for s in stats_list]
                agent_group = [s.agent_group_count for s in stats_list]
                customer_group = [s.customer_group_count for s in stats_list]
                suffix = ""

            line1, = self._ax.plot(x_indices, moment, 'o-', color=DarkColors.WARNING, label=f'朋友圈{suffix}', linewidth=2, markersize=6)
            line2, = self._ax.plot(x_indices, agent_group, 's-', color=DarkColors.PRIMARY, label=f'代理群{suffix}', linewidth=2, markersize=6)
            line3, = self._ax.plot(x_indices, customer_group, '^-', color=DarkColors.SUCCESS, label=f'客户群{suffix}', linewidth=2, markersize=6)
            self._lines = [line1, line2, line3]

        # 设置x轴标签为日期
        date_labels = [s.stat_date.strftime('%Y-%m-%d') if hasattr(s.stat_date, 'strftime') else str(s.stat_date) for s in stats_list]
        self._ax.set_xticks(x_indices)
        self._ax.set_xticklabels(date_labels)

        # 设置图例
        self._ax.legend(loc='upper left', framealpha=0.8, facecolor=DarkColors.SURFACE,
                        edgecolor=DarkColors.BORDER, labelcolor=DarkColors.TEXT_PRIMARY)

        plt.setp(self._ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # 重新创建 tooltip annotation
        self._annotation = self._ax.annotate(
            "", xy=(0, 0), xytext=(15, 15),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#424242", edgecolor="none", alpha=0.9),
            color="white",
            fontsize=10,
            visible=False,
            zorder=100
        )

        # 重新创建高亮点
        self._highlight_point, = self._ax.plot([], [], 'o',
            color='white', markersize=12, markeredgecolor='white',
            markerfacecolor='none', markeredgewidth=2, visible=False, zorder=99)

        self._figure.tight_layout()
        self._canvas.draw()


class ChannelPieChart(QWidget):
    """渠道分布饼图组件"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._figure = None
        self._canvas = None
        self._ax = None
        self._wedges = []  # 存储饼图扇形对象
        self._labels = []  # ['朋友圈', '群发']
        self._sizes = []   # [7, 14]
        self._annotation = None  # tooltip annotation
        self._hovered_index = -1  # 当前悬浮的扇形索引
        self._setup_ui()

    def closeEvent(self, event):
        """清理 matplotlib 资源"""
        if self._figure is not None:
            plt.close(self._figure)
        super().closeEvent(event)

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建matplotlib图表 - 深色主题
        self._figure = Figure(figsize=(4, 4), dpi=100)
        self._figure.patch.set_facecolor(DarkColors.SURFACE)
        self._canvas = FigureCanvas(self._figure)
        self._ax = self._figure.add_subplot(111)

        layout.addWidget(self._canvas)

        # 初始化空图表
        self._init_chart()

        # 创建 tooltip annotation
        self._annotation = self._ax.annotate(
            "", xy=(0, 0), xytext=(15, 15),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#424242", edgecolor="none", alpha=0.9),
            color="white",
            fontsize=10,
            visible=False,
            zorder=100
        )

        # 绑定鼠标移动事件
        self._canvas.mpl_connect('motion_notify_event', self._on_mouse_move)

    def _init_chart(self):
        """初始化图表 - 深色主题"""
        self._ax.set_facecolor(DarkColors.SURFACE)
        self._ax.set_title('渠道分布', color=DarkColors.TEXT_PRIMARY, fontsize=12, pad=10)

    def _on_mouse_move(self, event):
        """处理鼠标移动事件，显示tooltip和高亮"""
        if event.inaxes != self._ax or not self._wedges:
            # 鼠标不在图表区域内或无数据，隐藏tooltip并恢复样式
            if self._annotation and self._annotation.get_visible():
                self._annotation.set_visible(False)
                # 恢复所有扇形的边框
                for wedge in self._wedges:
                    wedge.set_edgecolor('none')
                    wedge.set_linewidth(0)
                self._hovered_index = -1
                self._canvas.draw_idle()
            return

        # 检测鼠标在哪个扇形上
        for i, wedge in enumerate(self._wedges):
            if wedge.contains_point([event.x, event.y]):
                if self._hovered_index != i:
                    # 切换到新的扇形
                    self._hovered_index = i

                    # 恢复所有扇形的默认样式
                    for w in self._wedges:
                        w.set_edgecolor('none')
                        w.set_linewidth(0)

                    # 高亮当前扇形（添加白色边框）
                    wedge.set_edgecolor('white')
                    wedge.set_linewidth(3)

                    # 计算tooltip内容
                    total = sum(self._sizes)
                    pct = self._sizes[i] / total * 100 if total > 0 else 0
                    tooltip_text = f"{self._labels[i]}: {self._sizes[i]} ({pct:.1f}%)"

                    # 获取扇形中心位置用于tooltip
                    theta = (wedge.theta1 + wedge.theta2) / 2
                    r = 0.5  # 饼图半径
                    x = r * math.cos(math.radians(theta))
                    y = r * math.sin(math.radians(theta))

                    # 更新annotation
                    self._annotation.xy = (x, y)
                    self._annotation.set_text(tooltip_text)
                    self._annotation.set_visible(True)

                    self._canvas.draw_idle()
                return

        # 鼠标不在任何扇形上
        if self._hovered_index != -1:
            self._hovered_index = -1
            self._annotation.set_visible(False)
            for wedge in self._wedges:
                wedge.set_edgecolor('none')
                wedge.set_linewidth(0)
            self._canvas.draw_idle()

    def update_data(self, moment_count: int, agent_group_count: int, customer_group_count: int):
        """更新饼图数据"""
        self._ax.clear()
        self._init_chart()
        self._wedges = []  # 清空之前的扇形引用
        self._hovered_index = -1

        total = moment_count + agent_group_count + customer_group_count
        if total == 0:
            # 没有数据时显示提示
            self._labels = []
            self._sizes = []
            self._ax.text(0.5, 0.5, '暂无数据', ha='center', va='center',
                         transform=self._ax.transAxes, color=DarkColors.TEXT_SECONDARY, fontsize=14)
            self._canvas.draw()
            return

        # 保存数据供tooltip使用 - 3个渠道
        self._labels = ['朋友圈', '代理群', '客户群']
        self._sizes = [moment_count, agent_group_count, customer_group_count]

        # 过滤掉数量为0的渠道
        valid_data = [(label, size) for label, size in zip(self._labels, self._sizes) if size > 0]
        if not valid_data:
            self._ax.text(0.5, 0.5, '暂无数据', ha='center', va='center',
                         transform=self._ax.transAxes, color=DarkColors.TEXT_SECONDARY, fontsize=14)
            self._canvas.draw()
            return

        self._labels = [d[0] for d in valid_data]
        self._sizes = [d[1] for d in valid_data]

        # 颜色映射: 朋友圈-橙色, 代理群-蓝色, 客户群-绿色
        color_map = {'朋友圈': DarkColors.WARNING, '代理群': DarkColors.PRIMARY, '客户群': DarkColors.SUCCESS}
        colors = [color_map[label] for label in self._labels]

        # 第一个扇形稍微突出
        explode = tuple([0.05 if i == 0 else 0 for i in range(len(self._sizes))])

        wedges, texts, autotexts = self._ax.pie(
            self._sizes,
            explode=explode,
            labels=self._labels,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            textprops={'color': DarkColors.TEXT_PRIMARY}
        )

        # 保存扇形对象供悬浮检测使用
        self._wedges = list(wedges)

        # 设置百分比文字颜色
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')

        self._ax.axis('equal')

        # 重新创建 tooltip annotation（因为 clear() 会清除它）
        self._annotation = self._ax.annotate(
            "", xy=(0, 0), xytext=(15, 15),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#424242", edgecolor="none", alpha=0.9),
            color="white",
            fontsize=10,
            visible=False,
            zorder=100
        )

        self._figure.tight_layout()
        self._canvas.draw()


class ChannelTrendChart(QWidget):
    """渠道趋势折线图组件 - 显示朋友圈、代理群、客户群三条折线"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._figure = None
        self._canvas = None
        self._ax = None
        self._stats_list = []  # 保存原始数据
        self._lines = []  # 存储绑定的 Line2D 对象
        self._annotation = None  # tooltip annotation
        self._highlight_point = None  # 高亮数据点
        self._setup_ui()

    def closeEvent(self, event):
        """清理 matplotlib 资源"""
        if self._figure is not None:
            plt.close(self._figure)
        super().closeEvent(event)

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建matplotlib图表 - 深色主题
        self._figure = Figure(figsize=(6, 4), dpi=100)
        self._figure.patch.set_facecolor(DarkColors.SURFACE)
        self._canvas = FigureCanvas(self._figure)
        self._ax = self._figure.add_subplot(111)

        layout.addWidget(self._canvas)

        # 初始化空图表
        self._init_chart()

        # 创建 tooltip annotation
        self._annotation = self._ax.annotate(
            "", xy=(0, 0), xytext=(15, 15),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#424242", edgecolor="none", alpha=0.9),
            color="white",
            fontsize=10,
            visible=False,
            zorder=100
        )

        # 创建高亮点（初始隐藏）
        self._highlight_point, = self._ax.plot([], [], 'o',
            color='white', markersize=12, markeredgecolor='white',
            markerfacecolor='none', markeredgewidth=2, visible=False, zorder=99)

        # 绑定鼠标移动事件
        self._canvas.mpl_connect('motion_notify_event', self._on_mouse_move)

    def _init_chart(self):
        """初始化图表样式 - 深色主题"""
        self._ax.set_facecolor(DarkColors.SURFACE)
        self._ax.tick_params(colors=DarkColors.TEXT_SECONDARY, labelsize=9)
        self._ax.spines['bottom'].set_color(DarkColors.BORDER)
        self._ax.spines['top'].set_visible(False)
        self._ax.spines['right'].set_visible(False)
        self._ax.spines['left'].set_color(DarkColors.BORDER)
        self._ax.set_title('渠道趋势对比', color=DarkColors.TEXT_PRIMARY, fontsize=12, pad=10)
        self._ax.set_xlabel('日期', color=DarkColors.TEXT_SECONDARY, fontsize=10)
        self._ax.set_ylabel('任务数', color=DarkColors.TEXT_SECONDARY, fontsize=10)

    def _on_mouse_move(self, event):
        """处理鼠标移动事件，显示tooltip和高亮"""
        if event.inaxes != self._ax or not self._stats_list or not self._lines:
            # 鼠标不在图表区域内或无数据，隐藏tooltip
            if self._annotation and self._annotation.get_visible():
                self._annotation.set_visible(False)
                self._highlight_point.set_visible(False)
                self._canvas.draw_idle()
            return

        # 查找最近的数据点
        min_dist = float('inf')
        closest_idx = -1
        closest_line_idx = -1
        closest_x = None
        closest_y = None

        for line_idx, line in enumerate(self._lines):
            xdata = line.get_xdata()
            ydata = line.get_ydata()

            for i in range(len(xdata)):
                # 将数据坐标转换为显示坐标
                try:
                    display_coords = self._ax.transData.transform((i, ydata[i]))
                    mouse_coords = (event.x, event.y)
                    dist = ((display_coords[0] - mouse_coords[0]) ** 2 +
                           (display_coords[1] - mouse_coords[1]) ** 2) ** 0.5
                    if dist < min_dist:
                        min_dist = dist
                        closest_idx = i
                        closest_line_idx = line_idx
                        closest_x = i
                        closest_y = ydata[i]
                except (ValueError, IndexError):
                    continue

        # 如果距离小于阈值（30像素），显示tooltip
        if min_dist < 30 and closest_idx >= 0 and closest_idx < len(self._stats_list):
            stats = self._stats_list[closest_idx]
            date_str = stats.stat_date.strftime('%Y-%m-%d') if hasattr(stats.stat_date, 'strftime') else str(stats.stat_date)
            tooltip_text = f"{date_str}\n朋友圈: {stats.moment_count}\n代理群: {stats.agent_group_count}\n客户群: {stats.customer_group_count}"

            # 更新annotation位置和文本
            self._annotation.xy = (closest_x, closest_y)
            self._annotation.set_text(tooltip_text)
            self._annotation.set_visible(True)

            # 更新高亮点位置
            self._highlight_point.set_data([closest_x], [closest_y])
            self._highlight_point.set_visible(True)

            self._canvas.draw_idle()
        else:
            # 隐藏tooltip和高亮点
            if self._annotation.get_visible():
                self._annotation.set_visible(False)
                self._highlight_point.set_visible(False)
                self._canvas.draw_idle()

    def update_data(self, stats_list: List[DailyStats]):
        """更新图表数据"""
        self._ax.clear()
        self._init_chart()
        self._lines = []  # 清空之前的线条引用
        self._stats_list = stats_list  # 保存数据供tooltip使用

        if not stats_list:
            self._ax.text(0.5, 0.5, '暂无数据', ha='center', va='center',
                         transform=self._ax.transAxes, color=DarkColors.TEXT_SECONDARY, fontsize=14)
            self._canvas.draw()
            return

        # 提取数据 - 使用索引作为x轴
        moment = [s.moment_count for s in stats_list]
        agent_group = [s.agent_group_count for s in stats_list]
        customer_group = [s.customer_group_count for s in stats_list]
        x_indices = list(range(len(stats_list)))

        # 绘制折线 - 朋友圈(橙色)、代理群(蓝色)、客户群(绿色)
        line1, = self._ax.plot(x_indices, moment, 'o-', color=DarkColors.WARNING, label='朋友圈', linewidth=2, markersize=6)
        line2, = self._ax.plot(x_indices, agent_group, 's-', color=DarkColors.PRIMARY, label='代理群', linewidth=2, markersize=6)
        line3, = self._ax.plot(x_indices, customer_group, '^-', color=DarkColors.SUCCESS, label='客户群', linewidth=2, markersize=6)
        self._lines = [line1, line2, line3]

        # 设置x轴标签为日期
        date_labels = [s.stat_date.strftime('%Y-%m-%d') if hasattr(s.stat_date, 'strftime') else str(s.stat_date) for s in stats_list]
        self._ax.set_xticks(x_indices)
        self._ax.set_xticklabels(date_labels)

        # 设置图例 - 深色主题
        legend = self._ax.legend(loc='upper left', framealpha=0.8, facecolor=DarkColors.SURFACE,
                                  edgecolor=DarkColors.BORDER, labelcolor=DarkColors.TEXT_PRIMARY)

        # 旋转x轴标签
        plt.setp(self._ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # 重新创建 tooltip annotation（因为 clear() 会清除它）
        self._annotation = self._ax.annotate(
            "", xy=(0, 0), xytext=(15, 15),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#424242", edgecolor="none", alpha=0.9),
            color="white",
            fontsize=10,
            visible=False,
            zorder=100
        )

        # 重新创建高亮点
        self._highlight_point, = self._ax.plot([], [], 'o',
            color='white', markersize=12, markeredgecolor='white',
            markerfacecolor='none', markeredgewidth=2, visible=False, zorder=99)

        self._figure.tight_layout()
        self._canvas.draw()


class StatsTab(QWidget):
    """统计标签页"""

    # 信号
    export_requested = Signal(str)  # 导出文件路径

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._daily_stats: List[DailyStats] = []
        self._combined_chart = None
        self._pie_chart = None
        self._show_success_only = False  # 是否只显示成功数
        self._setup_ui()
        self._connect_signals()

    def closeEvent(self, event):
        """清理子组件的 matplotlib 资源"""
        if self._combined_chart is not None:
            self._combined_chart.close()
        if self._pie_chart is not None:
            self._pie_chart.close()
        super().closeEvent(event)

    def _setup_ui(self):
        """设置UI布局"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # 设置整体深色样式
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {DarkColors.BACKGROUND};
                color: {DarkColors.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {DarkColors.TEXT_SECONDARY};
                background: transparent;
            }}
        """)

        # === 顶部：统计卡片 ===
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self._card_total = StatCard("今日总数", 0, DarkColors.PRIMARY)
        self._card_success = StatCard("成功", 0, DarkColors.SUCCESS)
        self._card_failed = StatCard("失败", 0, DarkColors.ERROR)
        self._card_pending = StatCard("待发布", 0, DarkColors.PENDING)

        cards_layout.addWidget(self._card_total)
        cards_layout.addWidget(self._card_success)
        cards_layout.addWidget(self._card_failed)
        cards_layout.addWidget(self._card_pending)
        cards_layout.addStretch()

        main_layout.addLayout(cards_layout)

        # === 中部：图表区域 ===
        # 分组框深色样式
        group_style = f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                color: {DarkColors.PRIMARY};
                background-color: {DarkColors.SURFACE};
                border: 1px solid {DarkColors.BORDER};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
            }}
        """

        # 图表区域：合并趋势图 + 饼图
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(16)

        # 合并趋势图（支持切换任务趋势/渠道趋势）
        trend_group = QGroupBox("趋势图")
        trend_group.setStyleSheet(group_style)
        trend_layout = QVBoxLayout(trend_group)
        self._combined_chart = CombinedTrendChart()
        trend_layout.addWidget(self._combined_chart)

        # 饼图
        pie_group = QGroupBox("渠道分布")
        pie_group.setStyleSheet(group_style)
        pie_layout = QVBoxLayout(pie_group)
        self._pie_chart = ChannelPieChart()
        pie_layout.addWidget(self._pie_chart)

        charts_layout.addWidget(trend_group, stretch=2)
        charts_layout.addWidget(pie_group, stretch=1)

        main_layout.addLayout(charts_layout)

        # === 底部：历史记录表格 ===
        history_group = QGroupBox("历史记录")
        history_group.setStyleSheet(group_style)
        history_layout = QVBoxLayout(history_group)

        # 筛选工具栏
        filter_layout = QHBoxLayout()

        # 日期选择器深色样式
        date_style = f"""
            QDateEdit {{
                padding: 6px 12px;
                border: 1px solid {DarkColors.BORDER};
                border-radius: 4px;
                background-color: {DarkColors.SURFACE};
                color: {DarkColors.TEXT_PRIMARY};
            }}
            QDateEdit:focus {{
                border-color: {DarkColors.PRIMARY};
            }}
            QDateEdit::drop-down {{
                border: none;
                width: 20px;
            }}
        """

        filter_layout.addWidget(QLabel("起始日期:"))
        self._start_date = QDateEdit()
        self._start_date.setCalendarPopup(True)
        self._start_date.setDate(QDate.currentDate().addDays(-30))
        self._start_date.setStyleSheet(date_style)
        filter_layout.addWidget(self._start_date)

        filter_layout.addWidget(QLabel("结束日期:"))
        self._end_date = QDateEdit()
        self._end_date.setCalendarPopup(True)
        self._end_date.setDate(QDate.currentDate())
        self._end_date.setStyleSheet(date_style)
        filter_layout.addWidget(self._end_date)

        # 按钮深色样式
        self._btn_filter = QPushButton("筛选")
        self._btn_filter.setStyleSheet(f"""
            QPushButton {{
                background-color: {DarkColors.PRIMARY};
                color: #000000;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #64B5F6;
            }}
            QPushButton:pressed {{
                background-color: #42A5F5;
            }}
        """)
        self._btn_filter.setFixedWidth(80)
        filter_layout.addWidget(self._btn_filter)

        # 渠道数据切换按钮
        filter_layout.addSpacing(20)
        filter_layout.addWidget(QLabel("渠道数据:"))

        self._btn_show_total = QPushButton("显示总数")
        self._btn_show_success = QPushButton("显示成功")

        self._btn_show_total.setFixedHeight(28)
        self._btn_show_success.setFixedHeight(28)
        self._btn_show_total.setCursor(Qt.PointingHandCursor)
        self._btn_show_success.setCursor(Qt.PointingHandCursor)

        self._update_channel_button_styles()

        filter_layout.addWidget(self._btn_show_total)
        filter_layout.addWidget(self._btn_show_success)

        filter_layout.addStretch()

        self._btn_export = QPushButton("导出报表")
        self._btn_export.setStyleSheet(f"""
            QPushButton {{
                background-color: {DarkColors.SUCCESS};
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #66BB6A;
            }}
            QPushButton:pressed {{
                background-color: #43A047;
            }}
        """)
        filter_layout.addWidget(self._btn_export)

        history_layout.addLayout(filter_layout)

        # 表格 - 深色样式
        self._history_table = QTableWidget()
        self._history_table.setColumnCount(8)
        self._history_table.setHorizontalHeaderLabels([
            "日期", "总数", "成功", "失败", "待发布", "朋友圈", "代理群", "客户群"
        ])
        self._history_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {DarkColors.SURFACE};
                alternate-background-color: {DarkColors.CARD_BG};
                border: 1px solid {DarkColors.BORDER};
                border-radius: 4px;
                gridline-color: {DarkColors.BORDER};
                color: {DarkColors.TEXT_PRIMARY};
            }}
            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {DarkColors.BORDER};
            }}
            QTableWidget::item:selected {{
                background-color: rgba(144, 202, 249, 0.3);
                color: {DarkColors.TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background-color: {DarkColors.CARD_BG};
                color: {DarkColors.TEXT_PRIMARY};
                padding: 10px;
                border: none;
                border-bottom: 2px solid {DarkColors.PRIMARY};
                font-weight: bold;
            }}
        """)
        self._history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._history_table.setAlternatingRowColors(True)
        self._history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._history_table.verticalHeader().setVisible(False)

        history_layout.addWidget(self._history_table)

        main_layout.addWidget(history_group)

    def _connect_signals(self):
        """连接信号"""
        self._btn_filter.clicked.connect(self._on_filter_clicked)
        self._btn_export.clicked.connect(self._on_export_clicked)
        self._btn_show_total.clicked.connect(lambda: self._switch_channel_mode(False))
        self._btn_show_success.clicked.connect(lambda: self._switch_channel_mode(True))

    def _update_channel_button_styles(self):
        """更新渠道切换按钮样式"""
        active_style = f"""
            QPushButton {{
                background-color: {DarkColors.PRIMARY};
                color: #000000;
                padding: 4px 12px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background-color: {DarkColors.BORDER};
                color: {DarkColors.TEXT_SECONDARY};
                padding: 4px 12px;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #505050;
            }}
        """

        if self._show_success_only:
            self._btn_show_total.setStyleSheet(inactive_style)
            self._btn_show_success.setStyleSheet(active_style)
        else:
            self._btn_show_total.setStyleSheet(active_style)
            self._btn_show_success.setStyleSheet(inactive_style)

    def _switch_channel_mode(self, show_success: bool):
        """切换渠道数据显示模式"""
        if self._show_success_only != show_success:
            self._show_success_only = show_success
            self._update_channel_button_styles()
            self._update_table(self._daily_stats)

    def _on_filter_clicked(self):
        """筛选按钮点击"""
        # 触发数据刷新，由外部处理
        start = self._start_date.date().toPython()
        end = self._end_date.date().toPython()
        self.filter_stats(start, end)

    def _on_export_clicked(self):
        """导出报表按钮点击"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出报表",
            f"统计报表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV文件 (*.csv);;所有文件 (*.*)"
        )

        if file_path:
            self._export_to_csv(file_path)

    def _export_to_csv(self, file_path: str):
        """导出CSV文件"""
        try:
            with open(file_path, 'w', encoding='utf-8-sig') as f:
                # 写入表头
                f.write("日期,总数,成功,失败,待发布,朋友圈,代理群,客户群\n")

                # 写入数据
                for stats in self._daily_stats:
                    # stat_date 是 date 对象，需要格式化为字符串
                    date_str = stats.stat_date.strftime('%Y-%m-%d') if hasattr(stats.stat_date, 'strftime') else str(stats.stat_date)
                    f.write(f"{date_str},{stats.total_tasks},"
                           f"{stats.success_count},{stats.failed_count},"
                           f"{stats.pending_count},{stats.moment_count},"
                           f"{stats.agent_group_count},{stats.customer_group_count}\n")

            QMessageBox.information(self, "导出成功", f"报表已导出到:\n{file_path}")
            self.export_requested.emit(file_path)

        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出报表时出错:\n{str(e)}")

    def update_summary(self, summary: TaskSummary):
        """更新今日统计卡片"""
        self._card_total.set_value(summary.today_total)
        self._card_success.set_value(summary.today_success)
        self._card_failed.set_value(summary.today_failed)
        self._card_pending.set_value(summary.today_pending)

    def update_daily_stats(self, stats_list: List[DailyStats]):
        """更新每日统计数据"""
        self._daily_stats = stats_list

        # 更新合并趋势图（最近7天）
        recent_stats = stats_list[-7:] if len(stats_list) > 7 else stats_list
        self._combined_chart.update_data(recent_stats)

        # 更新饼图（汇总所有数据）- 3个渠道
        total_moment = sum(s.moment_count for s in stats_list)
        total_agent_group = sum(s.agent_group_count for s in stats_list)
        total_customer_group = sum(s.customer_group_count for s in stats_list)
        self._pie_chart.update_data(total_moment, total_agent_group, total_customer_group)

        # 更新表格
        self._update_table(stats_list)

    def _update_table(self, stats_list: List[DailyStats]):
        """更新历史记录表格"""
        self._history_table.setRowCount(len(stats_list))

        for row, stats in enumerate(reversed(stats_list)):  # 最新日期在前
            # stat_date 是 date 对象，需要转换为字符串
            date_str = stats.stat_date.strftime('%Y-%m-%d') if hasattr(stats.stat_date, 'strftime') else str(stats.stat_date)
            self._history_table.setItem(row, 0, QTableWidgetItem(date_str))
            self._history_table.setItem(row, 1, QTableWidgetItem(str(stats.total_tasks)))
            self._history_table.setItem(row, 2, QTableWidgetItem(str(stats.success_count)))
            self._history_table.setItem(row, 3, QTableWidgetItem(str(stats.failed_count)))
            self._history_table.setItem(row, 4, QTableWidgetItem(str(stats.pending_count)))

            # 根据模式显示总数或成功数
            if self._show_success_only:
                self._history_table.setItem(row, 5, QTableWidgetItem(str(stats.moment_success_count)))
                self._history_table.setItem(row, 6, QTableWidgetItem(str(stats.agent_group_success_count)))
                self._history_table.setItem(row, 7, QTableWidgetItem(str(stats.customer_group_success_count)))
            else:
                self._history_table.setItem(row, 5, QTableWidgetItem(str(stats.moment_count)))
                self._history_table.setItem(row, 6, QTableWidgetItem(str(stats.agent_group_count)))
                self._history_table.setItem(row, 7, QTableWidgetItem(str(stats.customer_group_count)))

            # 居中对齐
            for col in range(8):
                item = self._history_table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignCenter)

    def filter_stats(self, start_date: datetime, end_date: datetime):
        """筛选指定日期范围的统计数据"""
        if not self._daily_stats:
            return

        # 将 datetime 转换为 date 进行比较
        start_d = start_date.date() if hasattr(start_date, 'date') else start_date
        end_d = end_date.date() if hasattr(end_date, 'date') else end_date

        filtered = [
            s for s in self._daily_stats
            if start_d <= s.stat_date <= end_d
        ]

        self._update_table(filtered)

        # 更新饼图显示筛选范围的数据 - 3个渠道
        total_moment = sum(s.moment_count for s in filtered)
        total_agent_group = sum(s.agent_group_count for s in filtered)
        total_customer_group = sum(s.customer_group_count for s in filtered)
        self._pie_chart.update_data(total_moment, total_agent_group, total_customer_group)
