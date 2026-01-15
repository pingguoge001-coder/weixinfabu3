"""
邮件通知器模块

功能:
- SMTP 发送邮件（支持 SSL/TLS）
- HTML 格式邮件
- 邮件模板：日报、告警、熔断通知、任务失败
- 附件支持
- 发送失败重试
- 异步发送
"""

import sys
import ssl
import smtplib
import logging
import threading
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.config_manager import get_config_manager, get_config


logger = logging.getLogger(__name__)


# ============================================================
# 邮件模板
# ============================================================

# 基础 HTML 模板样式
BASE_STYLE = """
<style>
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        line-height: 1.6;
        color: #333;
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
    }
    .header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 30px;
        border-radius: 10px 10px 0 0;
        text-align: center;
    }
    .header h1 {
        margin: 0;
        font-size: 24px;
    }
    .header .subtitle {
        opacity: 0.9;
        font-size: 14px;
        margin-top: 5px;
    }
    .content {
        background: #fff;
        padding: 30px;
        border: 1px solid #e0e0e0;
        border-top: none;
        border-radius: 0 0 10px 10px;
    }
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 15px;
        margin: 20px 0;
    }
    .stat-card {
        background: #f8f9fa;
        padding: 20px;
        border-radius: 8px;
        text-align: center;
    }
    .stat-card .number {
        font-size: 32px;
        font-weight: bold;
        color: #667eea;
    }
    .stat-card .label {
        color: #666;
        font-size: 14px;
        margin-top: 5px;
    }
    .stat-card.success .number { color: #28a745; }
    .stat-card.danger .number { color: #dc3545; }
    .stat-card.warning .number { color: #ffc107; }
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 15px 0;
    }
    th, td {
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid #e0e0e0;
    }
    th {
        background: #f8f9fa;
        font-weight: 600;
    }
    .alert {
        padding: 15px 20px;
        border-radius: 8px;
        margin: 15px 0;
    }
    .alert-danger {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
    .alert-warning {
        background: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
    }
    .alert-info {
        background: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
    }
    .alert-success {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
    }
    .badge-success { background: #28a745; color: white; }
    .badge-danger { background: #dc3545; color: white; }
    .badge-warning { background: #ffc107; color: #333; }
    .badge-critical { background: #6f42c1; color: white; }
    .footer {
        text-align: center;
        padding: 20px;
        color: #999;
        font-size: 12px;
    }
    .divider {
        height: 1px;
        background: #e0e0e0;
        margin: 20px 0;
    }
</style>
"""

# 日报模板
DAILY_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    {style}
</head>
<body>
    <div class="header">
        <h1>微信发布助手 - 日报</h1>
        <div class="subtitle">{date}</div>
    </div>
    <div class="content">
        <h2>今日概览</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="number">{total_tasks}</div>
                <div class="label">总任务</div>
            </div>
            <div class="stat-card success">
                <div class="number">{success_count}</div>
                <div class="label">成功</div>
            </div>
            <div class="stat-card danger">
                <div class="number">{failed_count}</div>
                <div class="label">失败</div>
            </div>
            <div class="stat-card warning">
                <div class="number">{pending_count}</div>
                <div class="label">待执行</div>
            </div>
        </div>

        <div class="alert alert-info">
            <strong>成功率:</strong> {success_rate}% |
            <strong>完成率:</strong> {completion_rate}%
        </div>

        <div class="divider"></div>

        <h3>渠道分布</h3>
        <table>
            <tr>
                <th>渠道</th>
                <th>任务数</th>
            </tr>
            <tr>
                <td>朋友圈</td>
                <td>{moment_count}</td>
            </tr>
            <tr>
                <td>群发</td>
                <td>{group_count}</td>
            </tr>
        </table>

        {failed_tasks_section}

        {tomorrow_tasks_section}
    </div>
    <div class="footer">
        微信发布助手 | 自动生成于 {generated_at}
    </div>
</body>
</html>
"""

# 失败任务列表部分
FAILED_TASKS_SECTION = """
<div class="divider"></div>
<h3>失败任务详情</h3>
<table>
    <tr>
        <th>产品</th>
        <th>内容编号</th>
        <th>渠道</th>
        <th>错误信息</th>
    </tr>
    {rows}
</table>
"""

# 明日任务部分
TOMORROW_TASKS_SECTION = """
<div class="divider"></div>
<h3>明日排期</h3>
<div class="alert alert-info">
    明日共有 <strong>{count}</strong> 个任务待执行
</div>
"""

# 告警模板
ALERT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    {style}
</head>
<body>
    <div class="header" style="background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);">
        <h1>微信发布助手 - 告警通知</h1>
        <div class="subtitle">{event_type}</div>
    </div>
    <div class="content">
        <div class="alert alert-{alert_class}">
            <strong>告警级别:</strong> <span class="badge badge-{badge_class}">{risk_level}</span>
        </div>

        <h3>告警信息</h3>
        <table>
            <tr>
                <td><strong>告警时间</strong></td>
                <td>{alert_time}</td>
            </tr>
            <tr>
                <td><strong>事件类型</strong></td>
                <td>{event_type}</td>
            </tr>
            <tr>
                <td><strong>风险等级</strong></td>
                <td>{risk_level}</td>
            </tr>
        </table>

        <h3>详细信息</h3>
        <div class="alert alert-warning">
            {details}
        </div>

        <h3>建议操作</h3>
        <ul>
            {suggestions}
        </ul>
    </div>
    <div class="footer">
        微信发布助手 | 告警生成于 {generated_at}
    </div>
</body>
</html>
"""

# 熔断通知模板
CIRCUIT_BREAK_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    {style}
</head>
<body>
    <div class="header" style="background: linear-gradient(135deg, #6f42c1 0%, #5a32a3 100%);">
        <h1>微信发布助手 - 熔断触发</h1>
        <div class="subtitle">系统已进入保护状态</div>
    </div>
    <div class="content">
        <div class="alert alert-danger">
            <strong>紧急通知:</strong> 系统检测到连续失败，已触发熔断保护机制
        </div>

        <h3>熔断详情</h3>
        <table>
            <tr>
                <td><strong>熔断时间</strong></td>
                <td>{break_time}</td>
            </tr>
            <tr>
                <td><strong>连续失败次数</strong></td>
                <td><span class="badge badge-danger">{failure_count} 次</span></td>
            </tr>
            <tr>
                <td><strong>熔断状态</strong></td>
                <td><span class="badge badge-critical">{circuit_state}</span></td>
            </tr>
        </table>

        <h3>最后错误信息</h3>
        <div class="alert alert-warning">
            {last_error}
        </div>

        <h3>恢复建议</h3>
        <ol>
            <li>检查微信客户端是否正常运行</li>
            <li>检查网络连接是否稳定</li>
            <li>查看微信是否有风控提示</li>
            <li>确认问题解决后，系统将在 {recovery_timeout} 秒后自动尝试恢复</li>
            <li>如需立即恢复，请删除停机标记文件并重启程序</li>
        </ol>
    </div>
    <div class="footer">
        微信发布助手 | 熔断通知生成于 {generated_at}
    </div>
</body>
</html>
"""

# 任务失败通知模板
TASK_FAILURE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    {style}
</head>
<body>
    <div class="header" style="background: linear-gradient(135deg, #fd7e14 0%, #dc3545 100%);">
        <h1>微信发布助手 - 任务失败</h1>
        <div class="subtitle">{product_name}</div>
    </div>
    <div class="content">
        <h3>任务信息</h3>
        <table>
            <tr>
                <td><strong>产品名称</strong></td>
                <td>{product_name}</td>
            </tr>
            <tr>
                <td><strong>内容编号</strong></td>
                <td>{content_code}</td>
            </tr>
            <tr>
                <td><strong>发布渠道</strong></td>
                <td>{channel}</td>
            </tr>
            <tr>
                <td><strong>计划时间</strong></td>
                <td>{scheduled_time}</td>
            </tr>
            <tr>
                <td><strong>执行时间</strong></td>
                <td>{executed_time}</td>
            </tr>
            <tr>
                <td><strong>重试次数</strong></td>
                <td>{retry_count} / {max_retry}</td>
            </tr>
        </table>

        <h3>错误信息</h3>
        <div class="alert alert-danger">
            {error_message}
        </div>

        {screenshot_section}
    </div>
    <div class="footer">
        微信发布助手 | 通知生成于 {generated_at}
    </div>
</body>
</html>
"""


# ============================================================
# 邮件发送结果
# ============================================================

@dataclass
class EmailResult:
    """邮件发送结果"""
    success: bool
    message: str = ""
    recipients: List[str] = None
    subject: str = ""
    sent_at: datetime = None

    def __post_init__(self):
        if self.recipients is None:
            self.recipients = []
        if self.sent_at is None:
            self.sent_at = datetime.now()


# ============================================================
# 邮件通知器
# ============================================================

class EmailNotifier:
    """
    邮件通知器

    支持 SMTP 发送邮件，包含日报、告警、熔断通知等模板
    """

    def __init__(self):
        """初始化邮件通知器"""
        self._config = get_config_manager()

        # SMTP 配置
        self._smtp_host = get_config("email.smtp.host", "smtp.qq.com")
        self._smtp_port = get_config("email.smtp.port", 465)
        self._use_ssl = get_config("email.smtp.use_ssl", True)
        self._use_tls = get_config("email.smtp.use_tls", False)

        # 发件人配置
        self._sender_address = get_config("email.sender.address", "")
        self._sender_name = get_config("email.sender.name", "微信发布助手")
        self._sender_password = self._config.get_decrypted("email.sender.password", "")

        # 收件人
        self._recipients = get_config("email.recipients", [])

        # 通知开关
        self._notify_on = get_config("email.notify_on", {})

        # 是否启用
        self._enabled = get_config("email.enabled", False)

        # 线程池
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email_")

        # 重试配置
        self._max_retries = 3
        self._retry_delay = 5  # 秒

        # 发送历史
        self._send_history: List[EmailResult] = []
        self._max_history = 100

        logger.debug(f"邮件通知器初始化完成, 启用: {self._enabled}")

    # ========================================================
    # 主要接口
    # ========================================================

    def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        html: bool = True,
        attachments: Optional[List[str]] = None,
        async_send: bool = True
    ) -> EmailResult:
        """
        发送邮件

        Args:
            to: 收件人列表
            subject: 邮件主题
            body: 邮件内容
            html: 是否为 HTML 格式
            attachments: 附件路径列表
            async_send: 是否异步发送

        Returns:
            发送结果
        """
        if not self._enabled:
            logger.debug("邮件通知未启用")
            return EmailResult(success=False, message="邮件通知未启用")

        if not to:
            to = self._recipients

        if not to:
            logger.warning("没有指定收件人")
            return EmailResult(success=False, message="没有指定收件人")

        if async_send:
            # 异步发送
            future = self._executor.submit(
                self._send_with_retry, to, subject, body, html, attachments
            )
            # 添加回调记录异步发送结果
            future.add_done_callback(
                lambda f: self._log_async_result(f, subject, to)
            )
            return EmailResult(
                success=True,
                message="邮件已提交异步发送",
                recipients=to,
                subject=subject
            )
        else:
            # 同步发送
            return self._send_with_retry(to, subject, body, html, attachments)

    def send_daily_report(
        self,
        stats: "DailyStats",
        failed_tasks: Optional[List["Task"]] = None,
        tomorrow_count: int = 0
    ) -> EmailResult:
        """
        发送日报

        Args:
            stats: 日统计数据
            failed_tasks: 失败任务列表
            tomorrow_count: 明日任务数

        Returns:
            发送结果
        """
        if not self._should_notify("daily_summary"):
            return EmailResult(success=False, message="日报通知已禁用")

        # 构建失败任务部分
        failed_section = ""
        if failed_tasks:
            rows = ""
            for task in failed_tasks:
                rows += f"""
                <tr>
                    <td>{task.product_name}</td>
                    <td>{task.content_code}</td>
                    <td>{task.channel.value if hasattr(task.channel, 'value') else task.channel}</td>
                    <td>{task.error_message or '未知错误'}</td>
                </tr>
                """
            failed_section = FAILED_TASKS_SECTION.format(rows=rows)

        # 构建明日任务部分
        tomorrow_section = ""
        if tomorrow_count > 0:
            tomorrow_section = TOMORROW_TASKS_SECTION.format(count=tomorrow_count)

        # 渲染模板
        body = DAILY_REPORT_TEMPLATE.format(
            style=BASE_STYLE,
            date=stats.stat_date.strftime("%Y年%m月%d日"),
            total_tasks=stats.total_tasks,
            success_count=stats.success_count,
            failed_count=stats.failed_count,
            pending_count=stats.pending_count,
            success_rate=f"{stats.success_rate:.1f}",
            completion_rate=f"{stats.completion_rate:.1f}",
            moment_count=stats.moment_count,
            group_count=stats.group_count,
            failed_tasks_section=failed_section,
            tomorrow_tasks_section=tomorrow_section,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        subject = f"微信发布助手 - {stats.stat_date.strftime('%Y-%m-%d')} 日报"

        return self.send_email(self._recipients, subject, body)

    def send_alert(
        self,
        level: "RiskLevel",
        event_type: str,
        details: str,
        suggestions: Optional[List[str]] = None
    ) -> EmailResult:
        """
        发送告警通知

        Args:
            level: 风险等级
            event_type: 事件类型
            details: 详细信息
            suggestions: 建议操作列表

        Returns:
            发送结果
        """
        if not self._should_notify("failure"):
            return EmailResult(success=False, message="告警通知已禁用")

        # 根据等级设置样式
        level_value = level.value if hasattr(level, 'value') else str(level)
        style_map = {
            "critical": ("danger", "critical"),
            "high": ("danger", "danger"),
            "medium": ("warning", "warning"),
            "low": ("info", "success"),
        }
        alert_class, badge_class = style_map.get(level_value, ("warning", "warning"))

        # 默认建议
        if not suggestions:
            suggestions = [
                "检查微信客户端状态",
                "查看详细日志分析原因",
                "必要时手动介入处理",
            ]

        suggestions_html = "\n".join(f"<li>{s}</li>" for s in suggestions)

        body = ALERT_TEMPLATE.format(
            style=BASE_STYLE,
            event_type=event_type,
            alert_class=alert_class,
            badge_class=badge_class,
            risk_level=level_value.upper(),
            alert_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            details=details,
            suggestions=suggestions_html,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        subject = f"[告警] 微信发布助手 - {event_type}"

        return self.send_email(self._recipients, subject, body)

    def send_circuit_break_notice(
        self,
        failure_count: int,
        last_error: str,
        circuit_state: str = "open",
        recovery_timeout: int = 300
    ) -> EmailResult:
        """
        发送熔断通知

        Args:
            failure_count: 连续失败次数
            last_error: 最后一次错误信息
            circuit_state: 熔断状态
            recovery_timeout: 恢复超时时间

        Returns:
            发送结果
        """
        if not self._should_notify("circuit_break"):
            return EmailResult(success=False, message="熔断通知已禁用")

        body = CIRCUIT_BREAK_TEMPLATE.format(
            style=BASE_STYLE,
            break_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            failure_count=failure_count,
            circuit_state=circuit_state.upper(),
            last_error=last_error or "未知错误",
            recovery_timeout=recovery_timeout,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        subject = "[紧急] 微信发布助手 - 熔断触发"

        return self.send_email(self._recipients, subject, body)

    def send_task_failure_notice(
        self,
        task: "Task",
        error: str,
        screenshot_path: Optional[str] = None
    ) -> EmailResult:
        """
        发送任务失败通知

        Args:
            task: 失败的任务
            error: 错误信息
            screenshot_path: 截图路径

        Returns:
            发送结果
        """
        if not self._should_notify("failure"):
            return EmailResult(success=False, message="失败通知已禁用")

        # 截图部分
        screenshot_section = ""
        attachments = []
        if screenshot_path and Path(screenshot_path).exists():
            screenshot_section = """
            <h3>错误截图</h3>
            <p>请查看附件中的截图</p>
            """
            attachments.append(screenshot_path)

        # 渠道显示
        channel = task.channel.value if hasattr(task.channel, 'value') else str(task.channel)

        body = TASK_FAILURE_TEMPLATE.format(
            style=BASE_STYLE,
            product_name=task.product_name or "未知产品",
            content_code=task.content_code or "未知",
            channel=channel,
            scheduled_time=task.scheduled_time.strftime("%Y-%m-%d %H:%M:%S") if task.scheduled_time else "未设置",
            executed_time=task.executed_time.strftime("%Y-%m-%d %H:%M:%S") if task.executed_time else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            retry_count=task.retry_count,
            max_retry=task.max_retry,
            error_message=error or task.error_message or "未知错误",
            screenshot_section=screenshot_section,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        subject = f"[任务失败] {task.product_name or '未知产品'} - {task.content_code or ''}"

        return self.send_email(
            self._recipients, subject, body,
            attachments=attachments if attachments else None
        )

    # ========================================================
    # 内部方法
    # ========================================================

    def _should_notify(self, event_type: str) -> bool:
        """检查是否应该发送通知"""
        if not self._enabled:
            return False
        return self._notify_on.get(event_type, False)

    def _send_with_retry(
        self,
        to: List[str],
        subject: str,
        body: str,
        html: bool,
        attachments: Optional[List[str]]
    ) -> EmailResult:
        """带重试的发送"""
        last_error = ""

        for attempt in range(self._max_retries):
            try:
                result = self._do_send(to, subject, body, html, attachments)

                if result.success:
                    self._add_to_history(result)
                    return result

                last_error = result.message

            except Exception as e:
                last_error = str(e)
                logger.warning(f"邮件发送失败 (尝试 {attempt + 1}/{self._max_retries}): {e}")

            if attempt < self._max_retries - 1:
                import time
                time.sleep(self._retry_delay)

        result = EmailResult(
            success=False,
            message=f"发送失败，已重试 {self._max_retries} 次: {last_error}",
            recipients=to,
            subject=subject
        )
        self._add_to_history(result)
        return result

    def _do_send(
        self,
        to: List[str],
        subject: str,
        body: str,
        html: bool,
        attachments: Optional[List[str]]
    ) -> EmailResult:
        """执行发送"""
        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg["From"] = formataddr((self._sender_name, self._sender_address))
            msg["To"] = ", ".join(to)
            msg["Subject"] = subject

            # 添加正文
            content_type = "html" if html else "plain"
            msg.attach(MIMEText(body, content_type, "utf-8"))

            # 添加附件
            if attachments:
                for file_path in attachments:
                    path = Path(file_path)
                    if path.exists():
                        with open(path, "rb") as f:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                "Content-Disposition",
                                f"attachment; filename={path.name}"
                            )
                            msg.attach(part)

            # 创建连接并发送
            smtp = None
            try:
                smtp = self._create_smtp_connection()
                smtp.sendmail(self._sender_address, to, msg.as_string())
                logger.info(f"邮件发送成功: {subject} -> {to}")

                return EmailResult(
                    success=True,
                    message="发送成功",
                    recipients=to,
                    subject=subject
                )

            finally:
                if smtp is not None:
                    try:
                        smtp.quit()
                    except Exception:
                        pass  # 忽略关闭连接时的错误

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP 认证失败: {e}")
            return EmailResult(success=False, message=f"SMTP 认证失败: {e}")

        except smtplib.SMTPException as e:
            logger.error(f"SMTP 错误: {e}")
            return EmailResult(success=False, message=f"SMTP 错误: {e}")

        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return EmailResult(success=False, message=str(e))

    def _create_smtp_connection(self) -> smtplib.SMTP:
        """创建 SMTP 连接"""
        if self._use_ssl:
            context = ssl.create_default_context()
            smtp = smtplib.SMTP_SSL(
                self._smtp_host,
                self._smtp_port,
                context=context
            )
        else:
            smtp = smtplib.SMTP(self._smtp_host, self._smtp_port)
            if self._use_tls:
                smtp.starttls()

        # 登录
        smtp.login(self._sender_address, self._sender_password)

        return smtp

    def _add_to_history(self, result: EmailResult) -> None:
        """添加到发送历史"""
        self._send_history.append(result)
        if len(self._send_history) > self._max_history:
            self._send_history = self._send_history[-self._max_history:]

    def _log_async_result(self, future, subject: str, recipients: List[str]) -> None:
        """记录异步发送结果"""
        try:
            result = future.result()
            if result.success:
                logger.debug(f"异步邮件发送成功: {subject} -> {recipients}")
            else:
                logger.warning(f"异步邮件发送失败: {subject} -> {recipients}, 原因: {result.message}")
        except Exception as e:
            logger.error(f"异步邮件发送异常: {subject} -> {recipients}, 错误: {e}")

    def get_send_history(self, limit: int = 20) -> List[EmailResult]:
        """获取发送历史"""
        return self._send_history[-limit:]

    def test_connection(self) -> Tuple[bool, str]:
        """
        测试 SMTP 连接

        Returns:
            (是否成功, 消息)
        """
        smtp = None
        try:
            smtp = self._create_smtp_connection()
            return True, "SMTP 连接测试成功"
        except Exception as e:
            return False, f"SMTP 连接失败: {e}"
        finally:
            if smtp is not None:
                try:
                    smtp.quit()
                except Exception:
                    pass

    def shutdown(self) -> None:
        """关闭邮件通知器"""
        self._executor.shutdown(wait=False)
        logger.debug("邮件通知器已关闭")


# ============================================================
# 便捷函数
# ============================================================

_notifier: Optional[EmailNotifier] = None


def get_email_notifier() -> EmailNotifier:
    """获取邮件通知器单例"""
    global _notifier
    if _notifier is None:
        _notifier = EmailNotifier()
    return _notifier


def send_email(
    to: List[str],
    subject: str,
    body: str,
    html: bool = True
) -> EmailResult:
    """快捷发送邮件"""
    return get_email_notifier().send_email(to, subject, body, html)


def send_alert(level: "RiskLevel", event_type: str, details: str) -> EmailResult:
    """快捷发送告警"""
    return get_email_notifier().send_alert(level, event_type, details)
