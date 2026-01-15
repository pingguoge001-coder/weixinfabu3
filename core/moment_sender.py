"""
朋友圈发布器模块（向后兼容层）

此文件保持向后兼容性，从新的模块化结构中导入所有功能。

原有的约1700行代码已重构为以下模块：
- core/moment/window_handler.py - 朋友圈窗口处理（打开、关闭、检测）
- core/moment/image_handler.py - 图片处理（添加图片、文件对话框操作）
- core/moment/text_handler.py - 文案处理（输入文字、剪贴板操作）
- core/moment/publish_handler.py - 发布操作（点击发表、等待完成）
- core/moment/locator.py - 元素定位（混合定位策略、图像识别）
- core/moment/sender.py - 主发送器（整合上述模块）

功能:
- 自动发布朋友圈（图文/纯文字）
- 支持微信 3.x 和 4.0 版本
- 通过剪贴板粘贴图片和文案
- 每步操作验证和失败截图
- 详细日志记录

微信 4.0 朋友圈发布流程:
1. 双击导航栏"朋友圈"按钮 -> 打开独立窗口 (mmui::SNSWindow)
2. 点击顶部"发表"按钮 -> 进入发布界面
3. 点击"添加图片"按钮 (mmui::PublishImageAddGridCell) -> 弹出文件对话框
4. 在文件对话框中选择图片
5. 输入文案到输入框 (mmui::ReplyInputField)
6. 点击"发表"按钮完成发布

使用方法:
    from core.moment_sender import MomentSender, SendResult
    from models.content import Content

    sender = MomentSender()
    result = sender.send_moment(content)
    if result.is_success:
        print("发布成功")
"""

# 从新的模块化结构导入所有公共接口
from .moment import (
    MomentSender,
    SendResult,
    get_moment_sender,
    send_moment,

    # 导出处理器（用于高级用法或测试）
    WindowHandler,
    ImageHandler,
    TextHandler,
    PublishHandler,
    ElementLocator,

    # 导出工厂函数
    create_window_handler,
    create_image_handler,
    create_text_handler,
    create_publish_handler,
    create_locator,
)

# 导出所有公共接口，保持向后兼容
__all__ = [
    # 主要接口
    "MomentSender",
    "SendResult",
    "get_moment_sender",
    "send_moment",

    # 处理器类（高级用法）
    "WindowHandler",
    "ImageHandler",
    "TextHandler",
    "PublishHandler",
    "ElementLocator",

    # 工厂函数
    "create_window_handler",
    "create_image_handler",
    "create_text_handler",
    "create_publish_handler",
    "create_locator",
]


# ============================================================
# 兼容性说明
# ============================================================

"""
本文件已从单一的 1700+ 行文件重构为模块化结构。

旧的使用方式仍然完全兼容：
    from core.moment_sender import MomentSender, SendResult
    sender = MomentSender()
    result = sender.send_moment(content)

新的使用方式（推荐）：
    from core.moment import MomentSender, SendResult
    sender = MomentSender()
    result = sender.send_moment(content)

模块化优势：
1. 代码结构清晰，每个模块职责单一
2. 更容易测试和维护
3. 更容易扩展新功能
4. 更容易定位和修复问题

模块说明：
- window_handler.py (约300行): 处理朋友圈窗口的打开、关闭、调整
- image_handler.py (约300行): 处理图片添加、文件对话框操作
- text_handler.py (约150行): 处理文案输入、剪贴板操作
- publish_handler.py (约600行): 处理发布流程、查看评论
- locator.py (约250行): 元素定位、图像识别、混合定位策略
- sender.py (约400行): 主发送器，整合所有功能模块

总计：约2000行（含文档和注释），原1700行功能完整保留
"""


# ============================================================
# 测试入口（保持兼容）
# ============================================================

if __name__ == "__main__":
    import logging
    from models.content import Content
    from models.enums import Channel

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=== 朋友圈发布器测试 ===\n")
    print("注意：代码已重构为模块化结构")
    print("原有功能保持不变，向后兼容\n")

    # 创建测试内容
    test_content = Content(
        content_code="TEST001",
        text="这是一条测试朋友圈消息 #自动发布测试",
        image_paths=[],  # 添加测试图片路径
        channel=Channel.moment,
    )

    print(f"测试内容: {test_content.content_code}")
    print(f"文案: {test_content.text}")
    print(f"图片数: {test_content.image_count}")

    # 确认执行
    confirm = input("\n确认发送测试消息? (y/N): ")
    if confirm.lower() != 'y':
        print("已取消")
        exit(0)

    # 发送
    sender = MomentSender()
    result = sender.send_moment(test_content)

    print(f"\n发送结果: {result.status.value}")
    print(f"消息: {result.message}")
    print(f"耗时: {result.duration:.2f} 秒")

    if result.screenshot_path:
        print(f"截图: {result.screenshot_path}")
