#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
微信自动发布工具 - 启动脚本
"""

import sys
import os
import logging

# 确保项目根目录在 Python 路径中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from gui.main_window import MainWindow
from services.config_manager import ConfigManager
from data.database import get_database, clear_contents_on_startup, clear_tasks_on_startup


def check_activation(config: dict, logger) -> bool:
    """
    检查软件激活状态

    Args:
        config: 配置字典
        logger: 日志记录器

    Returns:
        是否已激活（True=可以继续使用）
    """
    from services.activation_service import init_activation_service
    from gui.activation_dialog import ActivationDialog

    # 获取激活配置
    activation_config = config.get("activation", {})
    app_key = activation_config.get("app_key", "")
    app_secret = activation_config.get("app_secret", "")

    # 检查是否配置了 app_key 和 app_secret
    if not app_key or not app_secret:
        QMessageBox.critical(
            None,
            "配置错误",
            "未配置激活服务凭证 (app_key/app_secret)\n\n"
            "请在 config.yaml 中配置:\n"
            "activation:\n"
            "  app_key: 你的app_key\n"
            "  app_secret: 你的app_secret\n\n"
            "凭证可在管理后台获取:\n"
            "https://pingguoge.zeabur.app/admin"
        )
        return False

    # 初始化激活服务
    try:
        activation_service = init_activation_service(
            app_key=app_key,
            app_secret=app_secret,
            cache_dir=project_root
        )
    except Exception as e:
        logger.error(f"初始化激活服务失败: {e}")
        QMessageBox.critical(None, "错误", f"初始化激活服务失败: {str(e)}")
        return False

    # 检查激活状态并显示对话框
    return ActivationDialog.check_and_show(activation_service)


def main():
    """主函数"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    # 初始化数据库并清空历史数据（每次启动重新导入）
    try:
        get_database()  # 确保数据库初始化
        # 清空任务表
        tasks_cleared = clear_tasks_on_startup()
        if tasks_cleared > 0:
            logger.info(f"已清空 {tasks_cleared} 条历史任务数据")
        # 清空文案表
        contents_cleared = clear_contents_on_startup()
        if contents_cleared > 0:
            logger.info(f"已清空 {contents_cleared} 条历史文案数据")
    except Exception as e:
        logger.warning(f"清空历史数据失败: {e}")

    # 加载配置
    try:
        config_manager = ConfigManager()
        config = config_manager.get_all_config()
        logger.info("配置加载成功")
    except Exception as e:
        logger.warning(f"配置加载失败，使用默认配置: {e}")
        config = {}

    # 创建 Qt 应用
    app = QApplication(sys.argv)
    app.setApplicationName("微信自动发布工具")
    app.setOrganizationName("WeChatPublisher")

    # 高 DPI 支持 (PySide6 默认已启用，无需手动设置)

    # 检查激活状态
    if not check_activation(config, logger):
        logger.warning("软件未激活，退出程序")
        sys.exit(1)

    logger.info("软件激活验证通过")

    # 创建主窗口
    window = MainWindow(config=config)
    window.show()

    logger.info("应用启动成功")

    # 运行事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
