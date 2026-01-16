"""
导入处理器模块

负责文件导入逻辑，包括解析Excel文件和保存任务到数据库。
"""

import logging
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from models.task import Task
from models.content import Content
from data.excel_parser import parse_folder, ParseResult
from data.database import Database

logger = logging.getLogger(__name__)


class ImportHandler(QObject):
    """
    导入处理器

    功能：
    - 解析文件夹中的Excel文件
    - 保存任务到数据库
    - 管理内容数据
    """

    # 信号定义
    import_started = Signal(str)  # folder_path
    import_completed = Signal(object)  # ParseResult
    import_failed = Signal(str)  # error_message
    parse_progress = Signal(int, int)  # current, total

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self._db = db
        self._contents: Dict[str, Content] = {}  # content_code -> Content
        self._current_folder_path: Optional[str] = None

    def get_folder_path(self) -> Optional[str]:
        """获取当前导入的文件夹路径"""
        return self._current_folder_path

    def get_content(self, content_code: str) -> Optional[Content]:
        """
        获取内容对象

        Args:
            content_code: 内容编码

        Returns:
            Content对象，如果不存在返回None
        """
        return self._contents.get(content_code)

    def get_all_contents(self) -> Dict[str, Content]:
        """获取所有内容对象"""
        return self._contents.copy()

    def import_folder(self, folder_path: str) -> Tuple[bool, ParseResult]:
        """
        导入文件夹

        Args:
            folder_path: 文件夹路径

        Returns:
            Tuple[bool, ParseResult]: (是否成功, 解析结果)
        """
        logger.info(f"导入文件夹: {folder_path}")
        self.import_started.emit(folder_path)

        # 保存文件夹路径
        self._current_folder_path = folder_path

        # 解析文件夹（自动查找汇总Excel）
        result: ParseResult = parse_folder(folder_path)

        if not result.success:
            # 导入失败
            error_messages = [f"行 {e.row}: {e.message}" for e in result.errors[:10]]
            if len(result.errors) > 10:
                error_messages.append(f"... 还有 {len(result.errors) - 10} 个错误")

            error_msg = "解析文件失败:\n\n" + "\n".join(error_messages)
            logger.error(error_msg)
            self.import_failed.emit(error_msg)
            return False, result

        # 检查是否有任务
        if not result.tasks:
            error_msg = "文件中没有有效的任务数据"
            logger.warning(error_msg)
            self.import_failed.emit(error_msg)
            return False, result

        # 保存内容数据（用于执行时获取图片等信息）
        self._contents.update(result.contents)
        logger.info(f"已保存 {len(result.contents)} 个内容对象")

        # 发送导入完成信号
        self.import_completed.emit(result)

        return True, result

    def save_tasks_to_db(self, tasks: List[Task]) -> Tuple[int, int]:
        """
        保存任务到数据库

        Args:
            tasks: 任务列表

        Returns:
            Tuple[int, int]: (保存成功数, 总数)
        """
        saved_count = 0
        total = len(tasks)

        for i, task in enumerate(tasks):
            try:
                # 从 _contents 获取对应的图片路径和文案
                content = self._contents.get(task.content_code)
                if content:
                    if content.image_paths:
                        task.image_paths = content.image_paths
                        logger.info(f"任务 {task.content_code} 关联了 {len(content.image_paths)} 张图片")
                    # 将文案写入 task（用于群发渠道）
                    if content.text:
                        task.text = content.text
                        logger.info(f"任务 {task.content_code} 关联了文案: {content.text[:50]}...")
                else:
                    logger.warning(f"任务 {task.content_code} 未找到内容 (content={content is not None})")

                task_id = self._db.create_task(task)
                if task_id:
                    task.id = task_id
                    saved_count += 1

                # 发送进度信号
                self.parse_progress.emit(i + 1, total)

            except Exception as e:
                logger.warning(f"保存任务到数据库失败: {task.content_code}, 错误: {e}")

        logger.info(f"保存 {saved_count}/{total} 个任务到数据库")
        return saved_count, total

    def clear_contents(self):
        """清空内容数据"""
        self._contents.clear()
        self._current_folder_path = None
        logger.info("已清空内容数据")
