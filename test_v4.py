"""测试微信 4.0 识别"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, '.')

from core.wechat_controller import WeChatController
from core.element_locator import ElementLocator

print("=" * 50)
print("微信 4.0 识别测试")
print("=" * 50)

# 测试窗口控制器
print("\n1. 测试 WeChatController...")
controller = WeChatController()
window = controller.find_wechat_window(timeout=5)

if window:
    print(f"   [OK] 找到窗口: {window.Name}")
    print(f"   [OK] 类名: {window.ClassName}")
    print(f"   [OK] 检测版本: {controller.get_detected_version()}")
else:
    print("   [X] 未找到微信窗口")

# 测试元素定位器
print("\n2. 测试 ElementLocator...")
locator = ElementLocator()
version = locator.detect_wechat_version()
print(f"   [OK] 检测版本: {version}")

locator.set_version(version)

# 查找主窗口
print("\n3. 查找主窗口...")
main_window = locator.find_element("main_window", timeout=3)
if main_window:
    print(f"   [OK] 主窗口: {main_window.Name} ({main_window.ClassName})")
else:
    print("   [X] 未找到主窗口")

# 查找朋友圈按钮
print("\n4. 查找朋友圈按钮...")
moments_btn = locator.find_element("navigation.moments_button", parent=main_window, timeout=3)
if moments_btn:
    print(f"   [OK] 朋友圈按钮: {moments_btn.Name} ({moments_btn.ClassName})")
else:
    print("   [X] 未找到朋友圈按钮")

# 查找搜索框
print("\n5. 查找搜索框...")
search_box = locator.find_element("group_chat.search_box", parent=main_window, timeout=3)
if search_box:
    print(f"   [OK] 搜索框: {search_box.Name} ({search_box.ClassName})")
else:
    print("   [X] 未找到搜索框")

print("\n" + "=" * 50)
print("测试完成!")
print("=" * 50)
