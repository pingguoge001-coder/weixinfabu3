"""
任务执行器模块

负责任务执行逻辑，包括朋友圈和群发任务的执行。
"""

import logging
import threading
import concurrent.futures
from pathlib import Path
from typing import Optional, Callable

from PySide6.QtCore import QObject, Signal

from models.task import Task
from models.content import Content
from models.enums import Channel, SendStatus
from core.moment_sender import MomentSender, SendResult
from core.group_sender import get_group_sender
from core.group_sender import Content as GroupContent
from core.wechat_controller import get_wechat_controller

logger = logging.getLogger(__name__)


class TaskExecutor(QObject):
    """
    任务执行器

    功能：
    - 执行朋友圈发布任务
    - 执行群发任务
    - 通过信号与主窗口通信
    """

    # 信号定义
    task_started = Signal(object)  # task
    task_completed = Signal(object, object)  # task, result
    task_failed = Signal(object, str)  # task, error_message
    task_waiting = Signal(object, str)  # task, reason
    task_progress = Signal(object, str, int)  # task, text, percent

    def __init__(self, parent=None):
        super().__init__(parent)
        self._import_folder_path: Optional[str] = None
        self._group_names_provider: Optional[Callable[[Channel], list]] = None
        self._extra_message_provider: Optional[Callable[[Channel], str]] = None
        # 全局执行锁，避免多任务并发操作微信窗口
        self._execution_lock = threading.Lock()
        # 单线程执行器，避免任务堆积出大量线程
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._pending_tasks = 0
        self._pending_lock = threading.Lock()

    def _format_channel(self, channel) -> str:
        """统一渠道显示，兼容自定义渠道字符串"""
        return channel.value if isinstance(channel, Channel) else str(channel)

    def set_folder_path(self, folder_path: str):
        """设置导入文件夹路径（用于文件对话框导航）"""
        self._import_folder_path = folder_path
        logger.info(f"set import folder path: {folder_path}")

    def _resolve_folder_path(self, task: Task) -> Optional[str]:
        """获取任务对应的图片文件夹路径"""
        logger.info(
            f"resolve folder path start: code={task.content_code}, "
            f"source_folder={task.source_folder}, import_folder={self._import_folder_path}"
        )
        candidates = []
        if task.source_folder:
            candidates.append(task.source_folder)
        if self._import_folder_path and self._import_folder_path not in candidates:
            candidates.append(self._import_folder_path)

        for candidate in candidates:
            try:
                if Path(candidate).exists():
                    logger.debug(f"resolve folder path: {candidate}")
                    return candidate
            except Exception:
                continue

        for image_path in task.image_paths or []:
            if not image_path:
                continue
            try:
                path_obj = Path(image_path)
            except Exception:
                continue
            if path_obj.is_absolute() and path_obj.parent.exists():
                logger.debug(f"resolve folder path from image: {path_obj.parent}")
                return str(path_obj.parent)

        logger.debug("resolve folder path: None (use dialog default)")
        return None

    def _emit_task_progress(self, task: Task, text: str, percent: int):
        """发送进度信号"""
        self.task_progress.emit(task, text, percent)

    def _build_moment_steps(self, content: Content) -> list[str]:
        """构建朋友圈任务步骤列表"""
        steps = ["activate_wechat", "navigate_to_moment", "open_compose"]
        if content.has_images:
            steps.append("add_images")
        if content.full_text:
            steps.append("input_text")
        steps.extend(["click_publish", "wait_publish", "view_moment", "return_main"])
        return steps

    def set_group_names_provider(self, provider: Callable[[Channel], list]):
        """
        设置全局群名提供器

        Args:
            provider: 函数，接收Channel参数，返回群名列表
        """
        self._group_names_provider = provider

    def set_extra_message_provider(self, provider: Callable[[Channel], str]):
        """
        设置额外消息提供器

        Args:
            provider: 函数，接收Channel参数，返回额外消息字符串
        """
        self._extra_message_provider = provider

    def execute_task_async(self, task: Task, content: Content):
        """
        异步执行任务（在后台线程中执行）

        Args:
            task: 要执行的任务
            content: 任务内容
        """
        logger.info(f"异步执行任务: {task.content_code}, 渠道: {self._format_channel(task.channel)}")

        # 发送任务开始信号
        self.task_started.emit(task)

        with self._pending_lock:
            if self._pending_tasks > 0:
                self.task_waiting.emit(task, "排队中")
            self._pending_tasks += 1

        # 在后台线程中执行
        def execute_in_thread():
            try:
                if task.channel == Channel.moment:
                    result = self.execute_moment_task(task, content)
                else:
                    result = self.execute_group_task(task, content)

                # 回到主线程更新 UI
                self.task_completed.emit(task, result)

            except Exception as e:
                logger.exception(f"执行任务出错: {e}")
                error_result = SendResult(
                    status=SendStatus.FAILED,
                    content_code=task.content_code,
                    message=str(e)
                )
                self.task_completed.emit(task, error_result)
            finally:
                with self._pending_lock:
                    self._pending_tasks = max(0, self._pending_tasks - 1)

        self._executor.submit(execute_in_thread)

    def execute_moment_task(self, task: Task, content: Content) -> SendResult:
        """
        执行朋友圈发布任务

        Args:
            task: 任务对象
            content: 内容对象

        Returns:
            SendResult: 发送结果
        """
        logger.info(f"执行朋友圈任务: {task.content_code}, 图片数: {len(content.image_paths)}")

        if self._execution_lock.locked():
            self.task_waiting.emit(task, "等待锁")
            logger.info("等待全局执行锁，避免任务并发冲突")
        with self._execution_lock:
            try:
                # 创建发布器
                steps = self._build_moment_steps(content)
                step_index = {name: idx + 1 for idx, name in enumerate(steps)}
                total_steps = max(1, len(steps))

                self._emit_task_progress(task, f"{task.content_code} | 准备执行", 0)

                def step_callback(step_name: str, success: bool):
                    idx = step_index.get(step_name)
                    if not idx:
                        return
                    label_map = {
                        "activate_wechat": "激活微信",
                        "navigate_to_moment": "进入朋友圈",
                        "open_compose": "打开编辑框",
                        "add_images": "添加图片",
                        "input_text": "输入文案",
                        "click_publish": "点击发表",
                        "wait_publish": "等待发布完成",
                        "view_moment": "查看发布",
                        "return_main": "返回主界面",
                    }
                    label = label_map.get(step_name, step_name)
                    percent = int(idx / total_steps * 100)
                    self._emit_task_progress(
                        task,
                        f"{task.content_code} | {label} {idx}/{total_steps}",
                        percent
                    )

                sender = MomentSender(step_callback=step_callback)

                # 执行发布，传递文件夹路径用于文件对话框导航
                folder_path = self._resolve_folder_path(task)
                result = sender.send_moment(content, folder_path=folder_path)

                return result

            except Exception as e:
                logger.exception(f"朋友圈发布失败: {e}")
                return SendResult(
                    status=SendStatus.FAILED,
                    content_code=task.content_code,
                    message=f"发布失败: {str(e)}"
                )

    def execute_group_task(self, task: Task, content: Content) -> SendResult:
        """
        执行群发任务 - 循环发送到所有全局群名

        Args:
            task: 任务对象
            content: 内容对象

        Returns:
            SendResult: 发送结果
        """
        logger.info(f"执行群发任务: {task.content_code}, 渠道: {self._format_channel(task.channel)}")

        # 获取全局群名列表
        if self._group_names_provider:
            group_names = self._group_names_provider(task.channel)
        else:
            group_names = []

        if not group_names:
            logger.warning(f"任务 {task.content_code} 未配置全局群名列表")
            return SendResult(
                status=SendStatus.FAILED,
                content_code=task.content_code,
                message="未配置全局群名列表，请在渠道页面输入群名"
            )

        logger.info(f"任务 {task.content_code} 将发送到 {len(group_names)} 个群")

        if self._execution_lock.locked():
            self.task_waiting.emit(task, "等待锁")
            logger.info("等待全局执行锁，避免任务并发冲突")
        with self._execution_lock:
            try:
                sender = get_group_sender()

                group_content = GroupContent(
                    content_code=task.content_code,
                    text=content.text or task.text or "",
                    image_paths=content.image_paths or [],
                    channel=task.channel,
                    product_link=content.product_link or task.product_link,
                    product_name=content.product_name or task.product_name,
                    category=content.category or task.category,
                )

                total_groups = len(group_names)
                if total_groups:
                    self._emit_task_progress(task, f"{task.content_code} | 群发 0/{total_groups}", 0)

                extra_message = (
                    self._extra_message_provider(task.channel)
                    if self._extra_message_provider
                    else ""
                )
                has_product_link = bool(task.product_link) or bool(content.product_link)

                stage_sequence = ["open_group"]
                if group_content.image_paths:
                    stage_sequence.append("input_images")
                if group_content.text.strip():
                    stage_sequence.append("input_text")
                stage_sequence.extend(["click_send", "wait_complete"])
                if has_product_link:
                    stage_sequence.append("forward_miniprogram")
                if extra_message:
                    stage_sequence.append("send_extra_message")

                stage_index = {name: idx + 1 for idx, name in enumerate(stage_sequence)}
                stage_total = max(1, len(stage_sequence))
                group_index = {name: idx + 1 for idx, name in enumerate(group_names)}

                stage_labels = {
                    "open_group": "打开群",
                    "input_text": "输入文案",
                    "input_images": "输入图片",
                    "click_send": "点击发送",
                    "wait_complete": "等待完成",
                    "forward_miniprogram": "转发小程序",
                    "send_extra_message": "发送附加消息",
                }

                def emit_stage(group_name: str, stage_name: str) -> None:
                    cur = group_index.get(group_name)
                    idx = stage_index.get(stage_name)
                    if not cur or not idx or not total_groups:
                        return
                    percent = int(((cur - 1) + idx / stage_total) / total_groups * 100)
                    label = stage_labels.get(stage_name, stage_name)
                    self._emit_task_progress(
                        task,
                        f"{task.content_code} | 群发 {cur}/{total_groups} | {label} {idx}/{stage_total}",
                        percent,
                    )

                status_text = {
                    SendStatus.SUCCESS: "成功",
                    SendStatus.FAILED: "失败",
                    SendStatus.PARTIAL: "部分成功",
                    SendStatus.TIMEOUT: "超时",
                    SendStatus.CANCELLED: "取消",
                }

                controller = get_wechat_controller() if has_product_link else None

                def progress_callback(cur: int, total: int, res):
                    group_name = group_names[cur - 1] if cur - 1 < len(group_names) else ""

                    if has_product_link and group_name:
                        emit_stage(group_name, "forward_miniprogram")
                        try:
                            ok = controller.open_product_forward(
                                task.content_code,
                                group_name,
                                task.channel,
                            )
                            if not ok:
                                logger.warning(
                                    f"任务 {task.content_code} 小程序转发失败: {group_name}"
                                )
                        except Exception as exc:
                            logger.exception(
                                f"任务 {task.content_code} 小程序转发异常: {group_name}, {exc}"
                            )

                    if extra_message and group_name:
                        emit_stage(group_name, "send_extra_message")
                        try:
                            sender.send_text_in_current_chat(extra_message)
                        except Exception as exc:
                            logger.exception(
                                f"任务 {task.content_code} 附加消息发送异常: {group_name}, {exc}"
                            )

                    self._emit_task_progress(
                        task,
                        f"{task.content_code} | 群发 {cur}/{total} {status_text.get(res.status, res.status.value)}",
                        int(cur / total * 100) if total else 0,
                    )

                batch_result = sender.send_to_groups(
                    group_names=group_names,
                    content=group_content,
                    folder_path=self._resolve_folder_path(task),
                    interval=(3, 8),
                    stop_on_error=False,
                    progress_callback=progress_callback,
                    stage_callback=lambda name, stage: emit_stage(name, stage),
                )

                # 根据结果返回
                success_rate = batch_result.success_rate
                if success_rate >= 80:
                    return SendResult(
                        status=SendStatus.SUCCESS,
                        content_code=task.content_code,
                        message=f"成功发送到 {batch_result.success_count}/{batch_result.total} 个群 ({success_rate:.0f}%)"
                    )
                elif success_rate >= 50:
                    return SendResult(
                        status=SendStatus.PARTIAL,
                        content_code=task.content_code,
                        message=f"部分成功: {batch_result.success_count}/{batch_result.total} 个群 ({success_rate:.0f}%)"
                    )
                else:
                    return SendResult(
                        status=SendStatus.FAILED,
                        content_code=task.content_code,
                        message=f"发送失败: {batch_result.failed_count}/{batch_result.total} 个群失败"
                    )

            except Exception as e:
                logger.exception(f"群发任务执行异常: {e}")
                return SendResult(
                    status=SendStatus.FAILED,
                    content_code=task.content_code,
                    message=f"群发执行异常: {str(e)}"
                )

    def get_extra_message(self, channel: Channel) -> str:
        """
        获取额外消息

        Args:
            channel: 渠道

        Returns:
            str: 额外消息
        """
        if self._extra_message_provider:
            return self._extra_message_provider(channel)
        return ""
