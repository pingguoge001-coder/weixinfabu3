"""
微信窗口控制器模块（向后兼容层）

此文件保持向后兼容，所有功能已拆分到 core/wechat/ 子模块中。

功能:
- 查找微信主窗口
- 激活窗口到前台
- 窗口位置/大小调整
- 检测微信登录状态
- 使用 uiautomation 库实现 Windows UI 自动化

新代码应使用:
    from core.wechat import get_wechat_controller, WeChatController

为保持向后兼容，原有导入仍然有效:
    from core.wechat_controller import get_wechat_controller, WeChatController
"""

# 从新模块导入所有内容
from .wechat.controller import WeChatController
from .wechat.window_manager import Rect, MonitorInfo
from .wechat.login_checker import WeChatStatus
from .wechat import get_wechat_controller


# 导出所有公共接口，保持向后兼容
__all__ = [
    'WeChatController',
    'get_wechat_controller',
    'Rect',
    'MonitorInfo',
    'WeChatStatus',
]


# ============================================================
# 测试入口（保持原有测试代码）
# ============================================================

if __name__ == "__main__":
    import time
    import logging

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    controller = WeChatController()

    print("=== 微信窗口控制器测试 ===\n")

    # 检查微信状态
    print("1. 检查微信状态...")
    status = controller.check_login_status()
    print(f"   状态: {status.value}")

    if status == WeChatStatus.NOT_RUNNING:
        print("\n2. 微信未运行，尝试启动...")
        if controller.start_wechat():
            print("   启动成功，等待 5 秒...")
            time.sleep(5)

    # 查找窗口
    print("\n3. 查找微信主窗口...")
    window = controller.find_wechat_window()
    if window:
        print(f"   找到窗口: {window.Name}")

        # 获取窗口位置
        rect = controller.get_window_rect()
        if rect:
            print(f"   位置: ({rect.left}, {rect.top})")
            print(f"   大小: {rect.width} x {rect.height}")

        # 激活窗口
        print("\n4. 激活窗口...")
        if controller.activate_window():
            print("   窗口已激活")

        # 获取显示器信息
        print("\n5. 显示器信息:")
        monitors = controller.get_monitors()
        for i, m in enumerate(monitors):
            print(f"   显示器 {i+1}: {'主' if m.is_primary else '副'} "
                  f"- 分辨率: {m.rect.width}x{m.rect.height}")

        # 截图测试
        print("\n6. 截图测试...")
        # 临时启用截图
        from services.config_manager import get_config_manager
        config = get_config_manager()
        config.set("advanced.save_screenshots", True)
        screenshot = controller.take_screenshot("test_screenshot")
        if screenshot:
            print(f"   截图已保存: {screenshot}")
        else:
            print("   截图失败或未启用")

    else:
        print("   未找到微信窗口")

    print("\n测试完成")
