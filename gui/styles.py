"""
统一样式定义模块

提供 GUI 组件的统一样式和主题配置。
"""

from models.enums import TaskStatus


# 状态颜色映射
STATUS_COLORS = {
    TaskStatus.pending: "#9E9E9E",      # 灰色 - 待执行
    TaskStatus.scheduled: "#2196F3",    # 蓝色 - 已调度
    TaskStatus.running: "#FF9800",      # 橙色 - 执行中
    TaskStatus.success: "#4CAF50",      # 绿色 - 成功
    TaskStatus.failed: "#F44336",       # 红色 - 失败
    TaskStatus.skipped: "#795548",      # 棕色 - 跳过
    TaskStatus.cancelled: "#607D8B",    # 蓝灰 - 取消
    TaskStatus.paused: "#9C27B0",       # 紫色 - 暂停
}

# 状态中文名称
STATUS_NAMES = {
    TaskStatus.pending: "待执行",
    TaskStatus.scheduled: "已调度",
    TaskStatus.running: "执行中",
    TaskStatus.success: "成功",
    TaskStatus.failed: "失败",
    TaskStatus.skipped: "跳过",
    TaskStatus.cancelled: "已取消",
    TaskStatus.paused: "已暂停",
}

# 状态图标（使用 Unicode 符号，可替换为实际图标路径）
STATUS_ICONS = {
    TaskStatus.pending: "⏳",
    TaskStatus.scheduled: "📅",
    TaskStatus.running: "▶️",
    TaskStatus.success: "✅",
    TaskStatus.failed: "❌",
    TaskStatus.skipped: "⏭️",
    TaskStatus.cancelled: "🚫",
    TaskStatus.paused: "⏸️",
}


# 主题配置
class Theme:
    """主题基类"""
    # 主色调
    PRIMARY = "#1976D2"
    PRIMARY_LIGHT = "#42A5F5"
    PRIMARY_DARK = "#1565C0"

    # 辅助色
    ACCENT = "#FF4081"

    # 背景色
    BACKGROUND = "#FAFAFA"
    SURFACE = "#FFFFFF"

    # 文字颜色
    TEXT_PRIMARY = "#212121"
    TEXT_SECONDARY = "#757575"
    TEXT_DISABLED = "#BDBDBD"

    # 边框颜色
    BORDER = "#E0E0E0"
    BORDER_FOCUS = "#1976D2"

    # 状态颜色
    SUCCESS = "#4CAF50"
    WARNING = "#FF9800"
    ERROR = "#F44336"
    INFO = "#2196F3"


class DarkTheme(Theme):
    """深色主题"""
    PRIMARY = "#90CAF9"
    PRIMARY_LIGHT = "#E3F2FD"
    PRIMARY_DARK = "#42A5F5"

    BACKGROUND = "#121212"
    SURFACE = "#1E1E1E"

    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#B0B0B0"
    TEXT_DISABLED = "#666666"

    BORDER = "#333333"
    BORDER_FOCUS = "#90CAF9"


# 当前主题
current_theme = Theme


def set_theme(dark: bool = False):
    """设置主题"""
    global current_theme
    current_theme = DarkTheme if dark else Theme


# 按钮样式
BUTTON_STYLE = """
QPushButton {
    background-color: #1976D2;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    min-height: 32px;
}
QPushButton:hover {
    background-color: #1565C0;
}
QPushButton:pressed {
    background-color: #0D47A1;
}
QPushButton:disabled {
    background-color: #BDBDBD;
    color: #757575;
}
"""

BUTTON_SECONDARY_STYLE = """
QPushButton {
    background-color: transparent;
    color: #1976D2;
    border: 1px solid #1976D2;
    border-radius: 4px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    min-height: 32px;
}
QPushButton:hover {
    background-color: rgba(25, 118, 210, 0.08);
}
QPushButton:pressed {
    background-color: rgba(25, 118, 210, 0.16);
}
QPushButton:disabled {
    border-color: #BDBDBD;
    color: #BDBDBD;
}
"""

BUTTON_DANGER_STYLE = """
QPushButton {
    background-color: #F44336;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    min-height: 32px;
}
QPushButton:hover {
    background-color: #D32F2F;
}
QPushButton:pressed {
    background-color: #B71C1C;
}
"""

BUTTON_SUCCESS_STYLE = """
QPushButton {
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    min-height: 32px;
}
QPushButton:hover {
    background-color: #388E3C;
}
QPushButton:pressed {
    background-color: #1B5E20;
}
"""

# 工具栏按钮样式
TOOLBAR_BUTTON_STYLE = """
QPushButton {
    background-color: transparent;
    color: #424242;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 12px;
    min-height: 28px;
}
QPushButton:hover {
    background-color: rgba(0, 0, 0, 0.08);
}
QPushButton:pressed {
    background-color: rgba(0, 0, 0, 0.12);
}
QPushButton:checked {
    background-color: rgba(25, 118, 210, 0.12);
    color: #1976D2;
}
"""

# 表格样式
TABLE_STYLE = """
QTableView {
    background-color: #FFFFFF;
    alternate-background-color: #F8F9FA;
    border: 1px solid #DEE2E6;
    border-radius: 8px;
    gridline-color: #E9ECEF;
    selection-background-color: #E3F2FD;
    selection-color: #212121;
    font-size: 14px;
    outline: none;
}
QTableView::item {
    padding: 10px 12px;
    border-bottom: 1px solid #E9ECEF;
}
QTableView::item:selected {
    background-color: #BBDEFB;
    color: #212121;
}
QTableView::item:hover {
    background-color: #E3F2FD;
}
QTableView::item:focus {
    outline: none;
    border: none;
}
QHeaderView::section {
    background-color: #F1F3F4;
    color: #495057;
    padding: 12px 12px;
    border: none;
    border-bottom: 2px solid #DEE2E6;
    border-right: 1px solid #E9ECEF;
    font-weight: 600;
    font-size: 13px;
}
QHeaderView::section:last {
    border-right: none;
}
QHeaderView::section:hover {
    background-color: #E9ECEF;
}
QHeaderView::section:pressed {
    background-color: #DEE2E6;
}
"""

# 标签页样式
TAB_STYLE = """
QTabWidget::pane {
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    background-color: #FFFFFF;
    margin-top: -1px;
}
QTabBar::tab {
    background-color: transparent;
    color: #757575;
    padding: 12px 24px;
    margin-right: 4px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    font-weight: 500;
}
QTabBar::tab:selected {
    color: #1976D2;
    border-bottom: 2px solid #1976D2;
}
QTabBar::tab:hover:!selected {
    color: #424242;
    background-color: rgba(0, 0, 0, 0.04);
}
"""

# 输入框样式
INPUT_STYLE = """
QLineEdit, QComboBox, QSpinBox, QDateTimeEdit {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 13px;
    color: #212121;
    min-height: 20px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateTimeEdit:focus {
    border-color: #1976D2;
    border-width: 2px;
    padding: 7px 11px;
}
QLineEdit:disabled, QComboBox:disabled {
    background-color: #F5F5F5;
    color: #9E9E9E;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    width: 12px;
    height: 12px;
}
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    selection-background-color: #E3F2FD;
    selection-color: #212121;
}
"""

# 状态栏样式
STATUSBAR_STYLE = """
QStatusBar {
    background-color: #FAFAFA;
    border-top: 1px solid #E0E0E0;
    color: #757575;
    font-size: 12px;
    padding: 4px 8px;
}
QStatusBar::item {
    border: none;
}
"""

# 工具栏样式
TOOLBAR_STYLE = """
QToolBar {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E0E0E0;
    spacing: 8px;
    padding: 8px;
}
QToolBar::separator {
    background-color: #E0E0E0;
    width: 1px;
    margin: 4px 8px;
}
"""

# 菜单样式
MENU_STYLE = """
QMenu {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 4px 0;
}
QMenu::item {
    padding: 8px 32px 8px 16px;
    color: #212121;
}
QMenu::item:selected {
    background-color: #E3F2FD;
}
QMenu::item:disabled {
    color: #BDBDBD;
}
QMenu::separator {
    height: 1px;
    background-color: #E0E0E0;
    margin: 4px 8px;
}
"""

# 滚动条样式
SCROLLBAR_STYLE = """
QScrollBar:vertical {
    background-color: transparent;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #BDBDBD;
    border-radius: 6px;
    min-height: 40px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background-color: #9E9E9E;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background-color: transparent;
    height: 12px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #BDBDBD;
    border-radius: 6px;
    min-width: 40px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #9E9E9E;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
"""

# 进度条样式
PROGRESSBAR_STYLE = """
QProgressBar {
    background-color: #E0E0E0;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #1976D2;
    border-radius: 4px;
}
"""

# 日历样式
CALENDAR_STYLE = """
QCalendarWidget {
    background-color: #FFFFFF;
}
QCalendarWidget QAbstractItemView {
    background-color: #FFFFFF;
    color: #212121;
    selection-background-color: #E3F2FD;
    selection-color: #1976D2;
    alternate-background-color: #FAFAFA;
    font-size: 13px;
    outline: none;
}
QCalendarWidget QAbstractItemView:enabled {
    color: #212121;
}
QCalendarWidget QAbstractItemView:disabled {
    color: #9E9E9E;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: #F5F5F5;
    border-bottom: 1px solid #E0E0E0;
    padding: 4px;
}
QCalendarWidget QToolButton {
    color: #212121;
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 14px;
    font-weight: bold;
    min-width: 30px;
}
QCalendarWidget QToolButton:hover {
    background-color: #E0E0E0;
}
QCalendarWidget QToolButton#qt_calendar_prevmonth,
QCalendarWidget QToolButton#qt_calendar_nextmonth {
    qproperty-icon: none;
    min-width: 24px;
    font-size: 16px;
}
QCalendarWidget QToolButton#qt_calendar_prevmonth {
    qproperty-text: "<";
}
QCalendarWidget QToolButton#qt_calendar_nextmonth {
    qproperty-text: ">";
}
QCalendarWidget QMenu {
    background-color: #FFFFFF;
    color: #212121;
    border: 1px solid #E0E0E0;
}
QCalendarWidget QMenu::item {
    padding: 6px 20px;
}
QCalendarWidget QMenu::item:selected {
    background-color: #E3F2FD;
}
QCalendarWidget QSpinBox {
    background-color: #FFFFFF;
    color: #212121;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 2px 5px;
    min-width: 60px;
}
QCalendarWidget QSpinBox::up-button,
QCalendarWidget QSpinBox::down-button {
    width: 18px;
    background-color: #F5F5F5;
    border: none;
}
QCalendarWidget QWidget {
    alternate-background-color: #FFFFFF;
}
/* 表格视图 - 日期区域 */
QCalendarWidget QTableView {
    background-color: #FFFFFF;
    selection-background-color: #BBDEFB;
    selection-color: #1976D2;
    outline: none;
}
/* 星期标题行样式 - 必须用这种方式确保可见 */
QCalendarWidget QTableView QHeaderView::section {
    background-color: #F5F5F5;
    color: #424242;
    font-weight: 600;
    font-size: 12px;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #E0E0E0;
}
/* 日期单元格 */
QCalendarWidget QTableView::item {
    padding: 4px;
}
QCalendarWidget QTableView::item:selected {
    background-color: #BBDEFB;
    color: #1976D2;
}
QCalendarWidget QTableView::item:hover {
    background-color: #E3F2FD;
}
"""

# 对话框样式
DIALOG_STYLE = """
QDialog {
    background-color: #FFFFFF;
}
QDialog QLabel {
    color: #212121;
    font-size: 13px;
}
QDialog QPushButton {
    background-color: #1976D2;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 20px;
    font-size: 13px;
    min-width: 80px;
}
QDialog QPushButton:hover {
    background-color: #1565C0;
}
QDialog QDateTimeEdit {
    background-color: #FFFFFF;
    color: #212121;
    border: 1px solid #E0E0E0;
    border-radius: 4px;
    padding: 8px;
}
"""

# 消息框样式
MESSAGEBOX_STYLE = """
QMessageBox {
    background-color: #FFFFFF;
}
QMessageBox QLabel {
    color: #212121;
    font-size: 14px;
    min-width: 300px;
    padding: 10px;
}
QMessageBox QPushButton {
    background-color: #1976D2;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 24px;
    font-size: 13px;
    min-width: 90px;
    margin: 4px;
}
QMessageBox QPushButton:hover {
    background-color: #1565C0;
}
QMessageBox QPushButton:pressed {
    background-color: #0D47A1;
}
"""

# 全局应用样式
GLOBAL_STYLE = f"""
* {{
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
}}
QMainWindow {{
    background-color: #FAFAFA;
}}
QWidget {{
    background-color: transparent;
}}
QLabel {{
    color: #212121;
}}
QToolTip {{
    background-color: #424242;
    color: #FFFFFF;
    border: none;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 12px;
}}
{SCROLLBAR_STYLE}
{CALENDAR_STYLE}
{DIALOG_STYLE}
{MESSAGEBOX_STYLE}
"""


def get_status_style(status: TaskStatus) -> str:
    """
    获取状态标签样式

    Args:
        status: 任务状态

    Returns:
        样式字符串
    """
    color = STATUS_COLORS.get(status, "#9E9E9E")
    return f"""
        QLabel {{
            background-color: {color}20;
            color: {color};
            border: 1px solid {color};
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 11px;
            font-weight: 500;
        }}
    """


def get_status_badge_html(status: TaskStatus) -> str:
    """
    获取状态徽章 HTML

    Args:
        status: 任务状态

    Returns:
        HTML 字符串
    """
    color = STATUS_COLORS.get(status, "#9E9E9E")
    name = STATUS_NAMES.get(status, str(status.value))
    icon = STATUS_ICONS.get(status, "")

    return f'<span style="color: {color};">{icon} {name}</span>'
