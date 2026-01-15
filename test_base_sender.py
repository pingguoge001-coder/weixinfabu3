"""
测试 BaseSender 重构
验证 MomentSender 和 GroupSender 继承自 BaseSender 后的功能
"""

import sys
import io
import logging
from core.base_sender import BaseSender
from core.moment_sender import MomentSender
from core.group_sender import GroupSender

# 设置控制台输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def test_inheritance():
    """测试继承关系"""
    print("=" * 60)
    print("测试 1: 继承关系检查")
    print("=" * 60)

    assert issubclass(MomentSender, BaseSender), "MomentSender 应该继承自 BaseSender"
    assert issubclass(GroupSender, BaseSender), "GroupSender 应该继承自 BaseSender"

    print("✓ MomentSender 继承自 BaseSender")
    print("✓ GroupSender 继承自 BaseSender")
    print()


def test_abstract_methods():
    """测试抽象方法实现"""
    print("=" * 60)
    print("测试 2: 抽象方法实现检查")
    print("=" * 60)

    # MomentSender
    assert hasattr(MomentSender, 'send'), "MomentSender 应该实现 send 方法"
    assert hasattr(MomentSender, '_do_send'), "MomentSender 应该实现 _do_send 方法"
    print("✓ MomentSender 实现了 send 和 _do_send 方法")

    # GroupSender
    assert hasattr(GroupSender, 'send'), "GroupSender 应该实现 send 方法"
    assert hasattr(GroupSender, '_do_send'), "GroupSender 应该实现 _do_send 方法"
    print("✓ GroupSender 实现了 send 和 _do_send 方法")
    print()


def test_base_methods():
    """测试基类方法可用性"""
    print("=" * 60)
    print("测试 3: 基类方法可用性检查")
    print("=" * 60)

    # 创建实例
    ms = MomentSender(save_screenshots=False)
    gs = GroupSender(save_screenshots=False)

    # 检查基类方法
    base_methods = [
        '_ensure_wechat_ready',
        '_take_screenshot',
        '_take_error_screenshot',
        '_step',
        '_step_with_result',
        '_wait_for_send_complete',
        '_return_to_main',
        'get_wechat_version',
        'is_v4',
        'get_current_step',
    ]

    print("MomentSender 基类方法:")
    for method in base_methods:
        assert hasattr(ms, method), f"MomentSender 应该有 {method} 方法"
        print(f"  ✓ {method}")

    print("\nGroupSender 基类方法:")
    for method in base_methods:
        assert hasattr(gs, method), f"GroupSender 应该有 {method} 方法"
        print(f"  ✓ {method}")
    print()


def test_instance_creation():
    """测试实例创建"""
    print("=" * 60)
    print("测试 4: 实例创建检查")
    print("=" * 60)

    # MomentSender
    ms1 = MomentSender()
    ms2 = MomentSender(save_screenshots=False)
    print("✓ MomentSender 实例创建成功")
    print(f"  - ms1.get_wechat_version(): {ms1.get_wechat_version()}")
    print(f"  - ms2.get_wechat_version(): {ms2.get_wechat_version()}")

    # GroupSender
    gs1 = GroupSender()
    gs2 = GroupSender(save_screenshots=False)
    print("✓ GroupSender 实例创建成功")
    print(f"  - gs1.get_wechat_version(): {gs1.get_wechat_version()}")
    print(f"  - gs2.get_wechat_version(): {gs2.get_wechat_version()}")
    print()


def test_specific_methods():
    """测试特定方法保留"""
    print("=" * 60)
    print("测试 5: 子类特定方法检查")
    print("=" * 60)

    ms = MomentSender(save_screenshots=False)
    gs = GroupSender(save_screenshots=False)

    # MomentSender 特定方法
    moment_methods = [
        'send_moment',
        '_navigate_to_moment',
        '_open_compose_dialog',
        '_add_images',
        '_input_text',
        '_click_publish',
        '_wait_for_publish_complete',
    ]

    print("MomentSender 特定方法:")
    for method in moment_methods:
        assert hasattr(ms, method), f"MomentSender 应该有 {method} 方法"
        print(f"  ✓ {method}")

    # GroupSender 特定方法
    group_methods = [
        'send_to_group',
        'send_to_groups',
        '_search_group',
        '_enter_chat',
        '_send_images',
        '_send_text',
    ]

    print("\nGroupSender 特定方法:")
    for method in group_methods:
        assert hasattr(gs, method), f"GroupSender 应该有 {method} 方法"
        print(f"  ✓ {method}")
    print()


def test_common_attributes():
    """测试共同属性"""
    print("=" * 60)
    print("测试 6: 共同属性检查")
    print("=" * 60)

    ms = MomentSender(save_screenshots=False)
    gs = GroupSender(save_screenshots=False)

    # 共同属性
    common_attrs = [
        '_controller',
        '_clipboard',
        '_screenshot_dir',
        '_save_screenshots',
        '_step_callback',
        '_current_step',
        '_wechat_version',
    ]

    print("共同属性检查:")
    for attr in common_attrs:
        assert hasattr(ms, attr), f"MomentSender 应该有 {attr} 属性"
        assert hasattr(gs, attr), f"GroupSender 应该有 {attr} 属性"
        print(f"  ✓ {attr}")
    print()


def run_all_tests():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "BaseSender 重构测试" + " " * 23 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    try:
        test_inheritance()
        test_abstract_methods()
        test_base_methods()
        test_instance_creation()
        test_specific_methods()
        test_common_attributes()

        print("=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        print()
        print("重构总结:")
        print("  - 创建了 BaseSender 抽象基类")
        print("  - MomentSender 继承自 BaseSender")
        print("  - GroupSender 继承自 BaseSender")
        print("  - 提取了以下共同逻辑到基类:")
        print("    * 初始化逻辑（controller, clipboard, screenshot_dir）")
        print("    * _ensure_wechat_ready() - 确保微信就绪")
        print("    * _take_screenshot() - 截图方法")
        print("    * _step() - 步骤执行和回调")
        print("    * _wait_for_send_complete() - 等待发送完成")
        print("    * _return_to_main() - 返回主界面")
        print("  - 定义了抽象方法:")
        print("    * send() - 发送入口")
        print("    * _do_send() - 实际发送逻辑")
        print("  - 保持了原有的公共接口不变")
        print("  - 代码重复减少，统一了发送流程")
        print()

        return True

    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        return False
    except Exception as e:
        print(f"\n✗ 测试错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
