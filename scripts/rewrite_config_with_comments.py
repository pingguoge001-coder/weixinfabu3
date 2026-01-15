# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

CONFIG_PATH = Path("config.yaml")


def _dump_scalar(value: Any) -> str:
    text = yaml.safe_dump(value, allow_unicode=True, default_flow_style=True).strip()
    if text.endswith("..."):
        text = text[:-3].strip()
    return text


def _get_path(data: Dict[str, Any], path: Tuple[str, ...]) -> Any:
    cur: Any = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _set_path(data: Dict[str, Any], path: Tuple[str, ...], value: Any) -> None:
    cur: Dict[str, Any] = data
    for key in path[:-1]:
        if key not in cur or not isinstance(cur[key], dict):
            cur[key] = {}
        cur = cur[key]
    cur[path[-1]] = value


def _has_question(value: Any) -> bool:
    return isinstance(value, str) and "?" in value


COMMENTS: Dict[Tuple[str, ...], str] = {
    ("activation",): "激活信息（不要外传）",
    ("activation", "app_key"): "激活 App Key",
    ("activation", "app_secret"): "激活密钥",
    ("paths",): "本地路径配置",
    ("paths", "shared_folder"): "共享文件夹（相对路径）",
    ("paths", "cache_dir"): "缓存目录",
    ("paths", "receipts_dir"): "回执/结果目录",
    ("paths", "logs_dir"): "日志目录",
    ("paths", "wechat_path"): "微信客户端路径（留空自动查找）",
    ("schedule",): "任务调度规则",
    ("schedule", "default_interval"): "默认间隔（秒）",
    ("schedule", "channels"): "各渠道调度规则",
    ("schedule", "channels", "moment"): "朋友圈渠道",
    ("schedule", "channels", "moment", "enabled"): "是否启用朋友圈",
    ("schedule", "channels", "moment", "mode"): "调度模式（interval/fixed）",
    ("schedule", "channels", "moment", "interval_value"): "间隔数值",
    ("schedule", "channels", "moment", "interval_unit"): "间隔单位（minutes/hours）",
    ("schedule", "channels", "moment", "fixed_times"): "固定时间点（mode=fixed 时生效）",
    ("schedule", "channels", "moment", "daily_start_time"): "每日开始时间",
    ("schedule", "channels", "moment", "daily_end_time"): "每日结束时间",
    ("schedule", "channels", "moment", "minute_of_hour"): "每小时第几分钟触发",
    ("schedule", "channels", "agent_group"): "代理群渠道",
    ("schedule", "channels", "agent_group", "enabled"): "是否启用代理群",
    ("schedule", "channels", "agent_group", "mode"): "调度模式（interval/fixed）",
    ("schedule", "channels", "agent_group", "interval_value"): "间隔数值",
    ("schedule", "channels", "agent_group", "interval_unit"): "间隔单位（minutes/hours）",
    ("schedule", "channels", "agent_group", "fixed_times"): "固定时间点（mode=fixed 时生效）",
    ("schedule", "channels", "agent_group", "daily_start_time"): "每日开始时间",
    ("schedule", "channels", "agent_group", "daily_end_time"): "每日结束时间",
    ("schedule", "channels", "agent_group", "global_group_names"): "默认群名列表（可选）",
    ("schedule", "channels", "agent_group", "minute_of_hour"): "每小时第几分钟触发",
    ("schedule", "channels", "customer_group"): "客户群渠道",
    ("schedule", "channels", "customer_group", "enabled"): "是否启用客户群",
    ("schedule", "channels", "customer_group", "mode"): "调度模式（interval/fixed）",
    ("schedule", "channels", "customer_group", "interval_value"): "间隔数值",
    ("schedule", "channels", "customer_group", "interval_unit"): "间隔单位（minutes/hours）",
    ("schedule", "channels", "customer_group", "fixed_times"): "固定时间点（mode=fixed 时生效）",
    ("schedule", "channels", "customer_group", "daily_start_time"): "每日开始时间",
    ("schedule", "channels", "customer_group", "daily_end_time"): "每日结束时间",
    ("schedule", "channels", "customer_group", "global_group_names"): "默认群名列表（可选）",
    ("schedule", "channels", "customer_group", "minute_of_hour"): "每小时第几分钟触发",
    ("schedule", "random_delay_min"): "随机延迟下限（秒）",
    ("schedule", "random_delay_max"): "随机延迟上限（秒）",
    ("schedule", "daily_limit"): "每日任务上限",
    ("schedule", "active_hours"): "总的可执行时间段",
    ("schedule", "active_hours", "start"): "开始时间",
    ("schedule", "active_hours", "end"): "结束时间",
    ("schedule", "work_days"): "工作日（1-7 对应周一到周日）",
    ("email",): "邮件通知配置",
    ("email", "enabled"): "是否启用邮件通知",
    ("email", "smtp"): "SMTP 服务配置",
    ("email", "smtp", "host"): "SMTP 服务器",
    ("email", "smtp", "port"): "SMTP 端口",
    ("email", "smtp", "use_ssl"): "是否使用 SSL",
    ("email", "smtp", "use_tls"): "是否使用 TLS",
    ("email", "sender"): "发件人配置",
    ("email", "sender", "address"): "发件邮箱",
    ("email", "sender", "password"): "发件邮箱密码（建议加密）",
    ("email", "sender", "name"): "发件人名称",
    ("email", "recipients"): "收件人列表",
    ("email", "notify_on"): "触发邮件的事件",
    ("email", "notify_on", "success"): "成功时通知",
    ("email", "notify_on", "failure"): "失败时通知",
    ("email", "notify_on", "daily_summary"): "每日汇总通知",
    ("email", "notify_on", "circuit_break"): "熔断通知",
    ("voice",): "语音播报配置",
    ("voice", "moment_complete_enabled"): "朋友圈完成后语音提醒",
    ("voice", "moment_complete_text"): "朋友圈播报模板",
    ("voice", "agent_group_complete_enabled"): "代理群完成后语音提醒",
    ("voice", "agent_group_complete_text"): "代理群播报模板",
    ("voice", "customer_group_complete_enabled"): "客户群完成后语音提醒",
    ("voice", "customer_group_complete_text"): "客户群播报模板",
    ("circuit_breaker",): "熔断保护配置",
    ("circuit_breaker", "enabled"): "是否启用熔断",
    ("circuit_breaker", "failure_threshold"): "连续失败阈值",
    ("circuit_breaker", "recovery_timeout"): "熔断恢复等待（秒）",
    ("circuit_breaker", "half_open_attempts"): "半开状态尝试次数",
    ("circuit_breaker", "failure_count_reset"): "失败计数重置时间（秒）",
    ("resend",): "失败重试配置",
    ("resend", "auto_resend_missed"): "自动重试失败任务",
    ("resend", "max_retry_count"): "最大重试次数",
    ("resend", "retry_interval"): "重试间隔（秒）",
    ("resend", "exponential_backoff"): "是否指数退避",
    ("resend", "max_retry_interval"): "最大重试间隔（秒）",
    ("display",): "显示与窗口尺寸配置",
    ("display", "min_resolution"): "最低分辨率要求",
    ("display", "min_resolution", "width"): "最小宽度",
    ("display", "min_resolution", "height"): "最小高度",
    ("display", "primary_monitor_only"): "仅使用主显示器",
    ("display", "check_dpi_scaling"): "检查 DPI 缩放",
    ("display", "recommended_dpi"): "推荐 DPI（100=不缩放）",
    ("display", "sns_window"): "朋友圈窗口位置与大小（像素）",
    ("display", "sns_window", "x"): "窗口左上角 X",
    ("display", "sns_window", "y"): "窗口左上角 Y",
    ("display", "sns_window", "width"): "窗口宽度",
    ("display", "sns_window", "height"): "窗口高度",
    ("display", "wechat_window"): "微信主窗口位置与大小（像素）",
    ("display", "wechat_window", "x"): "窗口左上角 X",
    ("display", "wechat_window", "y"): "窗口左上角 Y",
    ("display", "wechat_window", "width"): "窗口宽度",
    ("display", "wechat_window", "height"): "窗口高度",
    ("image_processing",): "图片处理配置",
    ("image_processing", "auto_compress"): "是否自动压缩",
    ("image_processing", "compress_quality"): "压缩质量（1-100）",
    ("image_processing", "max_size"): "最大分辨率限制",
    ("image_processing", "max_size", "width"): "最大宽度",
    ("image_processing", "max_size", "height"): "最大高度",
    ("image_processing", "max_file_size_mb"): "单图最大大小（MB）",
    ("image_processing", "supported_formats"): "支持的图片格式",
    ("image_processing", "convert_heic"): "是否转换 HEIC",
    ("logging",): "日志配置",
    ("logging", "level"): "日志级别（INFO/DEBUG）",
    ("logging", "format"): "日志格式",
    ("logging", "max_file_size_mb"): "单个日志文件大小（MB）",
    ("logging", "backup_count"): "日志文件备份数量",
    ("logging", "console_output"): "控制台输出日志",
    ("automation",): "自动化参数",
    ("automation", "wechat_version"): "微信版本标识（用于兼容逻辑）",
    ("automation", "timeout"): "自动化超时设置（秒）",
    ("automation", "timeout", "element_wait"): "元素等待时间",
    ("automation", "timeout", "window_wait"): "窗口等待时间",
    ("automation", "timeout", "upload_wait"): "上传等待时间",
    ("automation", "timeout", "publish_wait"): "发布等待时间",
    ("automation", "delay"): "操作延迟（毫秒）",
    ("automation", "delay", "click"): "点击间隔",
    ("automation", "delay", "type"): "输入间隔",
    ("automation", "delay", "scroll"): "滚动间隔",
    ("automation", "delay", "action"): "动作间隔",
    ("security",): "安全配置",
    ("security", "key_file"): "加密密钥文件",
    ("security", "allow_plain_password"): "是否允许明文密码",
    ("advanced",): "高级配置",
    ("advanced", "debug_mode"): "调试模式",
    ("advanced", "save_screenshots"): "是否保存失败截图",
    ("advanced", "screenshot_dir"): "截图保存目录",
    ("advanced", "max_concurrent_tasks"): "并发任务数",
    ("advanced", "process_priority"): "进程优先级",
    ("ui_location",): "微信操作相关定位与图像识别参数",
    ("ui_location", "dots_btn_y_offset"): "点击...按钮时的Y方向微调（像素）",
    ("ui_location", "dots_btn_right_offset"): "点击...按钮时，距离右边缘向左的偏移（像素）",
    ("ui_location", "dots_btn_top_offset"): "点击...按钮时，备用的顶部位置（像素）",
    ("ui_location", "dots_btn_scales"): "查找...按钮时，模板缩放倍率（从小到大尝试）",
    ("ui_location", "dots_btn_confidence_levels"): "查找...按钮时，匹配阈值（从高到低）",
    ("ui_location", "dots_btn_grayscale"): "查找...按钮时，是否用灰度匹配",
    ("ui_location", "dots_btn_use_all_matches"): "查找...按钮时，是否选择最靠下的匹配结果",
    ("ui_location", "dots_btn_click_offset_x"): "点击...按钮的X方向微调（像素）",
    ("ui_location", "dots_btn_click_offset_y"): "点击...按钮的Y方向微调（像素）",
    ("ui_location", "dots_image_search_width"): "查找...按钮时，右侧条带搜索区宽度",
    ("ui_location", "dots_image_search_top_pad"): "查找...按钮时，右侧条带搜索区顶部留白",
    ("ui_location", "dots_image_search_bottom_pad"): "查找...按钮时，右侧条带搜索区底部留白",
    ("ui_location", "dots_image_bottom_box_width"): "查找...按钮时，右下角搜索框宽度",
    ("ui_location", "dots_image_bottom_box_height"): "查找...按钮时，右下角搜索框高度",
    ("ui_location", "dots_image_bottom_box_right_pad"): "查找...按钮时，右下角搜索框右边距",
    ("ui_location", "dots_image_bottom_box_bottom_pad"): "查找...按钮时，右下角搜索框下边距",
    ("ui_location", "dots_debug_save"): "调试：保存...按钮搜索区截图",
    ("ui_location", "dots_debug_dir"): "调试：...按钮截图保存目录",
    ("ui_location", "dots_row_band"): "查找...按钮时，同一行允许的高度误差",
    ("ui_location", "dots_right_margin"): "查找...按钮时，匹配结果必须足够靠右",
    ("ui_location", "comment_btn_confidence_levels"): "点开...后，找评论按钮的匹配阈值",
    ("ui_location", "comment_debug_save"): "调试：保存评论按钮搜索区截图",
    ("ui_location", "comment_debug_dir"): "调试：评论按钮截图保存目录",
    ("ui_location", "dots_search_heights"): "查找...按钮时，尝试的多个Y高度",
    ("ui_location", "dots_timestamp_offset"): "用时间戳做锚点时，...按钮的X偏移",
    ("ui_location", "send_btn_x_offset"): "发送按钮备用定位：距离右边缘的X偏移",
    ("ui_location", "send_btn_y_ratio"): "发送按钮备用定位：窗口高度的Y比例",
    ("ui_location", "send_btn_dots_x_offset"): "以...为锚点，发送按钮的X偏移",
    ("ui_location", "send_btn_dots_y_offset"): "以...为锚点，发送按钮的Y偏移",
    ("ui_location", "send_btn_dots_search_width"): "以...为锚点，发送按钮搜索区宽度",
    ("ui_location", "send_btn_dots_search_height"): "以...为锚点，发送按钮搜索区高度",
    ("ui_location", "close_btn_offset"): "点击关闭朋友圈窗口按钮的偏移",
    ("ui_location", "image_confidence_levels"): "通用图像识别阈值（从高到低）",
    ("miniprogram",): "小程序窗口定位与点击动作",
    ("miniprogram", "restore_window"): "打开小程序后，恢复窗口到固定位置",
    ("miniprogram", "restore_window", "x"): "恢复窗口的X坐标",
    ("miniprogram", "restore_window", "y"): "恢复窗口的Y坐标",
    ("miniprogram", "buttons"): "小程序内按钮点击坐标（绝对坐标）",
    ("miniprogram", "buttons", "more"): "点击“更多”按钮",
    ("miniprogram", "buttons", "more", "absolute_x"): "点击位置X",
    ("miniprogram", "buttons", "more", "absolute_y"): "点击位置Y",
    ("miniprogram", "buttons", "reenter"): "点击“重新进入”按钮",
    ("miniprogram", "buttons", "reenter", "absolute_x"): "点击位置X",
    ("miniprogram", "buttons", "reenter", "absolute_y"): "点击位置Y",
    ("miniprogram", "buttons", "search"): "点击“搜索”按钮",
    ("miniprogram", "buttons", "search", "absolute_x"): "点击位置X",
    ("miniprogram", "buttons", "search", "absolute_y"): "点击位置Y",
    ("miniprogram", "buttons", "product"): "点击“商品”按钮",
    ("miniprogram", "buttons", "product", "absolute_x"): "点击位置X",
    ("miniprogram", "buttons", "product", "absolute_y"): "点击位置Y",
    ("miniprogram", "buttons", "forward"): "点击“转发”按钮",
    ("miniprogram", "buttons", "forward", "absolute_x"): "点击位置X",
    ("miniprogram", "buttons", "forward", "absolute_y"): "点击位置Y",
    ("miniprogram_customer",): "客户群小程序窗口定位与点击动作",
    ("miniprogram_customer", "restore_window"): "打开小程序后，恢复窗口到固定位置",
    ("miniprogram_customer", "restore_window", "x"): "恢复窗口的X坐标",
    ("miniprogram_customer", "restore_window", "y"): "恢复窗口的Y坐标",
    ("miniprogram_customer", "buttons"): "小程序内按钮点击坐标（绝对坐标）",
    ("miniprogram_customer", "buttons", "more"): "点击“更多”按钮",
    ("miniprogram_customer", "buttons", "more", "absolute_x"): "点击位置X",
    ("miniprogram_customer", "buttons", "more", "absolute_y"): "点击位置Y",
    ("miniprogram_customer", "buttons", "reenter"): "点击“重新进入”按钮",
    ("miniprogram_customer", "buttons", "reenter", "absolute_x"): "点击位置X",
    ("miniprogram_customer", "buttons", "reenter", "absolute_y"): "点击位置Y",
    ("miniprogram_customer", "buttons", "search"): "点击“搜索”按钮",
    ("miniprogram_customer", "buttons", "search", "absolute_x"): "点击位置X",
    ("miniprogram_customer", "buttons", "search", "absolute_y"): "点击位置Y",
    ("miniprogram_customer", "buttons", "product"): "点击“商品”按钮",
    ("miniprogram_customer", "buttons", "product", "absolute_x"): "点击位置X",
    ("miniprogram_customer", "buttons", "product", "absolute_y"): "点击位置Y",
    ("miniprogram_customer", "buttons", "forward"): "点击“转发”按钮",
    ("miniprogram_customer", "buttons", "forward", "absolute_x"): "点击位置X",
    ("miniprogram_customer", "buttons", "forward", "absolute_y"): "点击位置Y",
    ("forward_dialog",): "转发对话框里的点击动作",
    ("forward_dialog", "group_option"): "选择群聊选项的相对偏移",
    ("forward_dialog", "group_option", "x_offset"): "X偏移",
    ("forward_dialog", "group_option", "y_offset"): "Y偏移",
    ("forward_dialog", "send_button"): "点击发送按钮的相对偏移",
    ("forward_dialog", "send_button", "x_offset"): "X偏移",
    ("forward_dialog", "send_button", "y_offset"): "Y偏移",
    ("custom_channels",): "自定义渠道配置（可留空）",
}

FIXED_TEXTS: Dict[Tuple[str, ...], str] = {
    ("voice", "moment_complete_text"): "又发了一条朋友圈，还剩{remaining}条朋友圈待发，日拱一卒，财务自由。",
    ("voice", "agent_group_complete_text"): "代理群发送成功，还有{remaining}个待发送",
    ("voice", "customer_group_complete_text"): "客户群发送成功，还有{remaining}个待发送",
    ("email", "sender", "name"): "微信发布助手",
}


def _apply_fixed_texts(data: Dict[str, Any]) -> None:
    for path, value in FIXED_TEXTS.items():
        cur_value = _get_path(data, path)
        if _has_question(cur_value):
            _set_path(data, path, value)


def _emit(node: Any, path: Tuple[str, ...], indent: int, out: list[str]) -> None:
    indent_str = "  " * indent
    if isinstance(node, dict):
        for key, value in node.items():
            comment = COMMENTS.get(path + (key,))
            if comment:
                out.append(f"{indent_str}# {comment}")
            if isinstance(value, (dict, list)):
                out.append(f"{indent_str}{key}:")
                _emit(value, path + (key,), indent + 1, out)
            else:
                out.append(f"{indent_str}{key}: {_dump_scalar(value)}")
        return
    if isinstance(node, list):
        for item in node:
            if isinstance(item, (dict, list)):
                out.append(f"{indent_str}-")
                _emit(item, path, indent + 1, out)
            else:
                out.append(f"{indent_str}- {_dump_scalar(item)}")


def main() -> None:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"找不到配置文件: {CONFIG_PATH}")

    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8", errors="replace")) or {}
    if not isinstance(data, dict):
        raise SystemExit("config.yaml 不是有效的 YAML 字典结构")

    _apply_fixed_texts(data)

    lines: list[str] = []
    _emit(data, (), 0, lines)
    content = "\n".join(lines) + "\n"
    CONFIG_PATH.write_text(content, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
