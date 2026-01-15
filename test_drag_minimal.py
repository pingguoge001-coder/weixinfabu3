# -*- coding: utf-8 -*-
"""
拖拽测试 - 完全手动实现，不依赖 Qt 内置拖拽
"""
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QStyle
)
from PySide6.QtCore import Qt, QPoint, QMimeData
from PySide6.QtGui import QDrag, QPixmap, QPainter, QCursor


class DragDropTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._drag_row = -1
        self._drag_start_pos = None

        # 设置表格
        self.setRowCount(5)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["编号", "名称", "状态"])

        # 添加测试数据
        for i in range(5):
            self.setItem(i, 0, QTableWidgetItem(f"T00{i+1}"))
            self.setItem(i, 1, QTableWidgetItem(f"产品{i+1}"))
            self.setItem(i, 2, QTableWidgetItem("待执行"))

        # 选择整行
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

        # 禁用 Qt 内置拖拽！使用手动实现
        self.setDragEnabled(False)
        self.setAcceptDrops(False)
        self.setDragDropMode(QAbstractItemView.NoDragDrop)

        # 表头设置
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            row = self.rowAt(event.position().toPoint().y())
            if row >= 0:
                self._drag_row = row
                self._drag_start_pos = event.position().toPoint()
                self.selectRow(row)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_row >= 0 and self._drag_start_pos:
            # 检查是否移动了足够距离来触发拖拽
            diff = event.position().toPoint() - self._drag_start_pos
            if diff.manhattanLength() > QApplication.startDragDistance():
                self._start_drag()
        super().mouseMoveEvent(event)

    def _start_drag(self):
        """开始拖拽"""
        if self._drag_row < 0:
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(self._drag_row))
        drag.setMimeData(mime_data)

        # 创建拖拽时显示的图像
        row_height = self.rowHeight(self._drag_row)
        width = self.viewport().width()
        pixmap = QPixmap(width, row_height)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setOpacity(0.7)
        for col in range(self.columnCount()):
            item = self.item(self._drag_row, col)
            if item:
                rect = self.visualItemRect(item)
                rect.moveTop(0)
                painter.fillRect(rect, Qt.lightGray)
                painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft, "  " + item.text())
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))

        # 执行拖拽
        self.setAcceptDrops(True)  # 临时启用接收
        result = drag.exec(Qt.MoveAction)
        self.setAcceptDrops(False)  # 恢复禁用

        self._drag_row = -1
        self._drag_start_pos = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """处理放置 - 纯插入，无覆盖"""
        if not event.mimeData().hasText():
            event.ignore()
            return

        try:
            source_row = int(event.mimeData().text())
        except:
            event.ignore()
            return

        # 获取目标位置
        pos = event.position().toPoint()
        target_row = self.rowAt(pos.y())

        if target_row < 0:
            target_row = self.rowCount()
        else:
            # 检查鼠标在目标行的上半部还是下半部
            item = self.item(target_row, 0)
            if item:
                rect = self.visualItemRect(item)
                if pos.y() > rect.center().y():
                    target_row += 1

        print(f"拖拽: 行 {source_row} -> 位置 {target_row}")

        # 相同位置不移动
        if source_row == target_row or source_row + 1 == target_row:
            print("  位置相同，跳过")
            event.ignore()
            return

        # 保存源行数据
        row_data = []
        for col in range(self.columnCount()):
            item = self.item(source_row, col)
            row_data.append(item.text() if item else "")

        # 执行移动
        self.move_row(source_row, target_row, row_data)

        event.acceptProposedAction()

    def move_row(self, from_row, to_row, row_data):
        """移动行到新位置"""
        print(f"  执行移动: {from_row} -> {to_row}")

        # 计算实际插入位置
        if from_row < to_row:
            insert_row = to_row - 1
        else:
            insert_row = to_row

        # 删除原行
        self.removeRow(from_row)

        # 插入到新位置
        self.insertRow(insert_row)
        for col, text in enumerate(row_data):
            self.setItem(insert_row, col, QTableWidgetItem(text))

        # 选中移动后的行
        self.selectRow(insert_row)

        # 打印结果
        print(f"完成: 共 {self.rowCount()} 行")
        for i in range(self.rowCount()):
            item = self.item(i, 0)
            print(f"  行 {i}: {item.text() if item else '空'}")

    def mouseReleaseEvent(self, event):
        self._drag_row = -1
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)


def main():
    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("拖拽测试 - 手动实现")
    window.resize(600, 400)

    table = DragDropTable()
    window.setCentralWidget(table)

    window.show()

    print("\n操作方法:")
    print("1. 点击选中一行")
    print("2. 按住鼠标左键拖动")
    print("3. 拖到目标位置释放\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
