"""
UI元素探测脚本 - 查找群聊窗口中的"发送文件"按钮

使用方法：
1. 打开微信并进入任意群聊窗口
2. 运行此脚本
3. 按Enter键开始枚举所有按钮
4. 查看输出，找到"发送文件"按钮的Name和ClassName
"""

import uiautomation as auto
import logging

logging.basicConfig(level=logging.DEBUG, format='%(message)s')
logger = logging.getLogger(__name__)


def main():
    print("="*60)
    print("微信群聊窗口 - '发送文件'按钮探测工具")
    print("="*60)

    # 查找微信主窗口
    print("\n正在查找微信主窗口...")
    main_window = auto.WindowControl(searchDepth=1, ClassName="mmui::MainWindow")

    if not main_window.Exists(5, 1):
        print("[X] 未找到微信主窗口 (ClassName=mmui::MainWindow)")
        print("请确保：")
        print("  1. 微信已打开")
        print("  2. 微信版本为 4.0+")
        print("  3. 微信窗口在前台可见")
        return

    print("[OK] 已找到微信主窗口")
    print(f"   窗口标题: {main_window.Name}")

    print("\n请执行以下操作：")
    print("  1. 在微信中打开任意群聊窗口")
    print("  2. 确保聊天输入框可见")
    print("  3. 找到输入框左侧的工具栏图标")

    import time
    print("\n等待3秒后自动开始...")
    time.sleep(3)

    print("\n" + "="*60)
    print("开始枚举所有 ButtonControl 控件")
    print("="*60)

    button_count = 0

    for i in range(50):  # 枚举最多50个按钮
        try:
            btn = main_window.ButtonControl(searchDepth=15, foundIndex=i+1)
            if btn.Exists(0, 0):
                button_count += 1

                # 获取按钮位置信息
                rect = btn.BoundingRectangle

                print(f"\n【按钮 {button_count}】")
                print(f"  Name          : {btn.Name if btn.Name else '(空)'}")
                print(f"  ClassName     : {btn.ClassName if btn.ClassName else '(空)'}")
                print(f"  AutomationId  : {btn.AutomationId if btn.AutomationId else '(空)'}")
                print(f"  位置          : ({rect.left}, {rect.top})")
                print(f"  大小          : {rect.width()}x{rect.height()}")
                print(f"  是否可见      : {btn.IsOffscreen == False}")

                # 特别标记可能是"发送文件"按钮的控件
                name_lower = btn.Name.lower() if btn.Name else ""
                if any(keyword in name_lower for keyword in ["文件", "file", "附件", "attach"]):
                    print(f"  >>> [可能是目标按钮！] <<<")
        except:
            break

    print("\n" + "="*60)
    print(f"枚举完成，共找到 {button_count} 个按钮")
    print("="*60)

    if button_count == 0:
        print("\n[!] 未找到任何按钮，可能的原因：")
        print("  1. 未进入群聊窗口")
        print("  2. searchDepth不足，无法深入查找")
        print("  3. 按钮控件类型不是ButtonControl")
    else:
        print("\n提示：")
        print("  1. 查找Name包含'文件'、'附件'等关键词的按钮")
        print("  2. 根据位置信息，确认是否在输入框左侧")
        print("  3. 记录目标按钮的Name和ClassName")
        print("  4. 将这些信息更新到 selectors.yaml 中")

    print("\n" + "="*60)


if __name__ == "__main__":
    main()
