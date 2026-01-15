# -*- coding: utf-8 -*-
"""
测试拖拽功能
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import Qt

from gui.queue_tab import ChannelQueueWidget
from models.task import Task, TaskStatus, Channel


def test_drag():
    app = QApplication(sys.argv)

    # 创建测试窗口
    window = QMainWindow()
    window.setWindowTitle("拖拽测试")
    window.resize(1000, 600)

    # 创建渠道组件
    widget = ChannelQueueWidget(Channel.moment)
    window.setCentralWidget(widget)

    # 添加测试任务
    tasks = [
        Task(id=1, content_code="T001", product_name="产品A", text="测试1",
             channel=Channel.moment, status=TaskStatus.pending, priority=3),
        Task(id=2, content_code="T002", product_name="产品B", text="测试2",
             channel=Channel.moment, status=TaskStatus.pending, priority=2),
        Task(id=3, content_code="T003", product_name="产品C", text="测试3",
             channel=Channel.moment, status=TaskStatus.pending, priority=1),
    ]

    widget.load_tasks(tasks)

    # 连接信号测试
    def on_reordered(tasks):
        print("=" * 50)
        print("顺序变更!")
        for i, t in enumerate(tasks):
            print(f"  {i+1}. {t.content_code} - priority={t.priority}")
        print("=" * 50)

    widget.tasks_reordered.connect(on_reordered)

    window.show()

    print("\n拖拽测试:")
    print("1. 点击行号列拖拽")
    print("2. 或者选中一行后拖拽")
    print("3. 观察控制台输出\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    test_drag()
