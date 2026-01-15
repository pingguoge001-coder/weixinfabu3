#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重构验证脚本

验证主窗口重构后的所有组件是否正常工作。
"""

import sys
import io
from pathlib import Path

# 设置控制台输出编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def test_imports():
    """测试所有导入是否正常"""
    print("=" * 60)
    print("测试 1: 导入验证")
    print("=" * 60)

    tests = [
        ("GUI服务层 - TaskExecutor", "from gui.services import TaskExecutor"),
        ("GUI服务层 - SchedulerController", "from gui.services import SchedulerController"),
        ("GUI服务层 - ImportHandler", "from gui.services import ImportHandler"),
        ("GUI服务层 - 全部", "from gui.services import TaskExecutor, SchedulerController, ImportHandler"),
        ("主窗口", "from gui.main_window import MainWindow, StatusIndicator"),
        ("核心 - 朋友圈发送器", "from core.moment_sender import MomentSender, SendResult"),
        ("核心 - 群发送器", "from core.group_sender import get_group_sender"),
    ]

    passed = 0
    failed = 0

    for name, import_stmt in tests:
        try:
            exec(import_stmt)
            print(f"✅ {name:<30} OK")
            passed += 1
        except Exception as e:
            print(f"❌ {name:<30} FAILED: {str(e)}")
            failed += 1

    print()
    print(f"通过: {passed}/{len(tests)}")
    print(f"失败: {failed}/{len(tests)}")
    print()

    return failed == 0


def test_syntax():
    """测试Python语法"""
    print("=" * 60)
    print("测试 2: 语法验证")
    print("=" * 60)

    import py_compile

    files = [
        "gui/main_window.py",
        "gui/services/__init__.py",
        "gui/services/task_executor.py",
        "gui/services/scheduler_controller.py",
        "gui/services/import_handler.py",
    ]

    passed = 0
    failed = 0

    for file_path in files:
        try:
            py_compile.compile(file_path, doraise=True)
            print(f"✅ {file_path:<50} OK")
            passed += 1
        except Exception as e:
            print(f"❌ {file_path:<50} FAILED: {str(e)}")
            failed += 1

    print()
    print(f"通过: {passed}/{len(files)}")
    print(f"失败: {failed}/{len(files)}")
    print()

    return failed == 0


def test_file_stats():
    """测试文件统计"""
    print("=" * 60)
    print("测试 3: 文件统计")
    print("=" * 60)

    files = {
        "gui/main_window.py": "主窗口",
        "gui/services/task_executor.py": "任务执行器",
        "gui/services/scheduler_controller.py": "调度器控制器",
        "gui/services/import_handler.py": "导入处理器",
    }

    total_lines = 0

    for file_path, name in files.items():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = len(f.readlines())
                total_lines += lines
                print(f"{name:<20} {file_path:<50} {lines:>5} 行")
        except Exception as e:
            print(f"❌ {name:<20} {file_path:<50} 错误: {str(e)}")

    print()
    print(f"总计: {total_lines} 行")
    print()

    return True


def test_class_structure():
    """测试类结构"""
    print("=" * 60)
    print("测试 4: 类结构验证")
    print("=" * 60)

    try:
        from gui.services import TaskExecutor, SchedulerController, ImportHandler
        from PySide6.QtCore import QObject

        # 检查TaskExecutor
        assert issubclass(TaskExecutor, QObject), "TaskExecutor应该继承QObject"
        executor = TaskExecutor()
        assert hasattr(executor, 'execute_task_async'), "TaskExecutor应该有execute_task_async方法"
        assert hasattr(executor, 'execute_moment_task'), "TaskExecutor应该有execute_moment_task方法"
        assert hasattr(executor, 'execute_group_task'), "TaskExecutor应该有execute_group_task方法"
        assert hasattr(executor, 'task_completed'), "TaskExecutor应该有task_completed信号"
        print("✅ TaskExecutor 类结构正确")

        # 检查SchedulerController
        assert issubclass(SchedulerController, QObject), "SchedulerController应该继承QObject"
        print("✅ SchedulerController 类结构正确")

        # 检查ImportHandler
        assert issubclass(ImportHandler, QObject), "ImportHandler应该继承QObject"
        print("✅ ImportHandler 类结构正确")

        print()
        return True

    except Exception as e:
        print(f"❌ 类结构验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        print()
        return False


def main():
    """主函数"""
    print()
    print("=" * 60)
    print("主窗口重构验证")
    print("=" * 60)
    print()

    results = []

    # 运行所有测试
    results.append(("导入验证", test_imports()))
    results.append(("语法验证", test_syntax()))
    results.append(("文件统计", test_file_stats()))
    results.append(("类结构验证", test_class_structure()))

    # 总结
    print("=" * 60)
    print("测试总结")
    print("=" * 60)

    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name:<20} {status}")

    print()

    all_passed = all(result[1] for result in results)
    if all_passed:
        print("🎉 所有测试通过！重构成功！")
        return 0
    else:
        print("⚠️  部分测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
