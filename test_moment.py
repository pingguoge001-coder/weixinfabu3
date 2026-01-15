"""测试朋友圈入口"""
import time
from core.wechat_controller import get_wechat_controller
from core.moment_sender import MomentSender

print("=" * 40)
print("   测试点击朋友圈入口")
print("=" * 40)
print()

# 第1步：检查微信
print("[1] 检查微信状态...")
controller = get_wechat_controller()
status = controller.check_login_status()
print(f"    微信状态: {status.value}")

if status.value != "logged_in":
    print("    错误: 请先登录微信!")
    input("按回车键退出...")
    exit(1)

# 第2步：激活微信窗口
print()
print("[2] 激活微信窗口...")
if controller.activate_window():
    print("    成功!")
else:
    print("    失败!")
    input("按回车键退出...")
    exit(1)

time.sleep(1)

# 第3步：测试导航到朋友圈
print()
print("[3] 尝试打开朋友圈...")
print("    (请观察微信窗口)")
print()

sender = MomentSender()

# 激活微信
if sender._activate_wechat():
    print("    ✓ 微信窗口已激活")
else:
    print("    ✗ 激活微信失败")
    input("按回车键退出...")
    exit(1)

time.sleep(0.5)

# 导航到朋友圈
if sender._navigate_to_moment():
    print("    ✓ 成功打开朋友圈!")
    print()
    print("=" * 40)
    print("   测试成功!")
    print("=" * 40)
else:
    print("    ✗ 打开朋友圈失败")
    print()
    print("可能的原因:")
    print("1. 微信界面元素找不到")
    print("2. 需要调整元素定位")

print()
input("按回车键退出...")
