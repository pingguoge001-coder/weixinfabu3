"""GUI 模块"""

from .main_window import MainWindow, StatusIndicator
from .queue_tab import QueueTab, TaskTableModel, StatusDelegate
from .schedule_tab import ScheduleTab
from .settings_tab import SettingsTab
from .stats_tab import StatsTab, StatCard, TrendChart, ChannelPieChart
from .preview_dialog import PreviewDialog, ThumbnailLabel, ImageGrid
from .log_panel import (
    LogPanel,
    LogDockWidget,
    LogHandler,
    LogRecord,
    setup_gui_logging,
)
from .styles import (
    # 颜色和图标
    STATUS_COLORS,
    STATUS_NAMES,
    STATUS_ICONS,
    # 主题
    Theme,
    DarkTheme,
    current_theme,
    set_theme,
    # 样式
    GLOBAL_STYLE,
    BUTTON_STYLE,
    BUTTON_SECONDARY_STYLE,
    BUTTON_DANGER_STYLE,
    BUTTON_SUCCESS_STYLE,
    TOOLBAR_BUTTON_STYLE,
    TABLE_STYLE,
    TAB_STYLE,
    INPUT_STYLE,
    STATUSBAR_STYLE,
    TOOLBAR_STYLE,
    MENU_STYLE,
    SCROLLBAR_STYLE,
    PROGRESSBAR_STYLE,
    # 工具函数
    get_status_style,
    get_status_badge_html,
)

__all__ = [
    # main_window
    "MainWindow",
    "StatusIndicator",
    # queue_tab
    "QueueTab",
    "TaskTableModel",
    "StatusDelegate",
    # schedule_tab
    "ScheduleTab",
    # settings_tab
    "SettingsTab",
    # stats_tab
    "StatsTab",
    "StatCard",
    "TrendChart",
    "ChannelPieChart",
    # preview_dialog
    "PreviewDialog",
    "ThumbnailLabel",
    "ImageGrid",
    # log_panel
    "LogPanel",
    "LogDockWidget",
    "LogHandler",
    "LogRecord",
    "setup_gui_logging",
    # styles - colors and icons
    "STATUS_COLORS",
    "STATUS_NAMES",
    "STATUS_ICONS",
    # styles - themes
    "Theme",
    "DarkTheme",
    "current_theme",
    "set_theme",
    # styles - stylesheets
    "GLOBAL_STYLE",
    "BUTTON_STYLE",
    "BUTTON_SECONDARY_STYLE",
    "BUTTON_DANGER_STYLE",
    "BUTTON_SUCCESS_STYLE",
    "TOOLBAR_BUTTON_STYLE",
    "TABLE_STYLE",
    "TAB_STYLE",
    "INPUT_STYLE",
    "STATUSBAR_STYLE",
    "TOOLBAR_STYLE",
    "MENU_STYLE",
    "SCROLLBAR_STYLE",
    "PROGRESSBAR_STYLE",
    # styles - utilities
    "get_status_style",
    "get_status_badge_html",
]
