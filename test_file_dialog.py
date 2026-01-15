"""
测试文件对话框上传图片功能

测试步骤：
1. 点击"发送文件"按钮
2. 等待文件对话框打开
3. 导航到指定文件夹
4. 批量输入文件名
5. 点击打开按钮
"""

import time
import logging
import uiautomation as auto
import pyautogui
import pyperclip
from pathlib import Path

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_file_dialog_upload():
    """测试文件对话框上传流程"""

    print("="*60)
    print("文件对话框上传图片测试")
    print("="*60)

    # 配置：修改这里的测试参数
    TEST_FOLDER = r"D:\外接大脑 (D)\苹果哥的商业系统A\电商\产品素材\待发布\十一月\2025-11-25"  # 修改为你的测试文件夹
    TEST_IMAGES = [
        "F00619 (1)",  # 只需要文件名，不含扩展名
        "F00619 (2)",
        "F00619 (3)"
    ]

    print(f"\n测试配置:")
    print(f"  文件夹: {TEST_FOLDER}")
    print(f"  图片数量: {len(TEST_IMAGES)}")
    print(f"  图片列表: {TEST_IMAGES}")

    print("\n请执行以下操作:")
    print("  1. 打开微信")
    print("  2. 进入任意群聊窗口")
    print("  3. 确保聊天输入框可见")
    print("  4. 不要操作鼠标和键盘")

    input("\n按 Enter 键开始测试...")

    try:
        # Step 1: 查找微信主窗口
        print("\n[Step 1] 查找微信主窗口...")
        main_window = auto.WindowControl(searchDepth=1, ClassName="mmui::MainWindow")

        if not main_window.Exists(5, 1):
            print("❌ 未找到微信主窗口")
            return False

        print("✓ 已找到微信主窗口")

        # Step 2: 先尝试点击输入框激活
        print("\n[Step 2] 尝试激活聊天输入框...")
        try:
            # 查找输入框（可能需要先激活）
            edit = main_window.EditControl(searchDepth=15, Name="")
            if edit.Exists(2, 1):
                print("  找到输入框，点击激活...")
                edit.Click()
                time.sleep(0.5)
                print("✓ 已激活输入框")
            else:
                print("  ⚠ 未找到输入框，继续查找按钮...")
        except Exception as e:
            print(f"  ⚠ 激活输入框时出错: {e}")

        # Step 3: 查找"发送文件"按钮
        print("\n[Step 3] 查找'发送文件'按钮...")
        print("  提示：请确保已进入群聊窗口且输入框可见")
        time.sleep(1)  # 等待界面稳定

        send_file_btn = None

        # 尝试不同的searchDepth，从深到浅
        for depth in [25, 20, 15]:
            if send_file_btn:
                break
            for name in ["发送文件", "文件", "附件"]:
                print(f"  尝试查找: Name={name}, searchDepth={depth}")
                btn = main_window.ButtonControl(searchDepth=depth, Name=name)
                if btn.Exists(2, 1):
                    send_file_btn = btn
                    print(f"✓ 找到'发送文件'按钮: Name={name}, searchDepth={depth}")
                    rect = btn.BoundingRectangle
                    print(f"  位置: ({rect.left}, {rect.top}), 大小: {rect.width()}x{rect.height()}")
                    break

        if not send_file_btn:
            print("❌ 未找到'发送文件'按钮")
            print("\n正在枚举所有ButtonControl以帮助调试...")

            # 枚举前10个按钮看看有什么
            for i in range(10):
                try:
                    btn = main_window.ButtonControl(searchDepth=25, foundIndex=i+1)
                    if btn.Exists(0, 0):
                        print(f"  按钮 {i+1}: Name='{btn.Name}', ClassName='{btn.ClassName}'")
                except:
                    break

            print("\n提示：")
            print("  1. 请确保已进入群聊窗口（不是联系人列表）")
            print("  2. 请确保输入框在屏幕上可见")
            print("  3. 查看上方枚举的按钮中是否有文件相关的按钮")
            print("  4. 如果有，请记录其Name，我们可以更新选择器配置")
            return False

        # Step 4: 点击"发送文件"按钮
        print("\n[Step 4] 点击'发送文件'按钮...")
        send_file_btn.Click()
        print("✓ 已点击按钮")
        time.sleep(0.5)

        # Step 5: 等待文件对话框出现
        print("\n[Step 5] 等待文件对话框出现...")
        file_dialog = auto.WindowControl(searchDepth=2, Name="打开")

        if not file_dialog.Exists(5, 1):
            print("  尝试通过ClassName查找...")
            file_dialog = auto.WindowControl(searchDepth=2, ClassName="#32770")

        if not file_dialog.Exists(5, 1):
            print("❌ 文件对话框未出现")
            # 尝试按ESC取消
            auto.SendKeys("{Escape}")
            return False

        print("✓ 文件对话框已打开")
        file_dialog.SetFocus()
        time.sleep(0.3)

        # Step 6: 导航到测试文件夹
        if TEST_FOLDER and Path(TEST_FOLDER).exists():
            print(f"\n[Step 6] 导航到文件夹: {TEST_FOLDER}")

            # 使用Ctrl+L聚焦地址栏
            print("  按Ctrl+L聚焦地址栏...")
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.3)

            # 粘贴文件夹路径
            print("  粘贴路径...")
            pyperclip.copy(TEST_FOLDER)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.3)

            # 按Enter导航
            print("  按Enter导航...")
            pyautogui.press('enter')
            time.sleep(0.8)

            print("✓ 已导航到目标文件夹")
        else:
            print(f"⚠ 跳过导航（文件夹不存在或未指定）: {TEST_FOLDER}")

        # Step 7: 批量输入文件名
        print(f"\n[Step 7] 批量输入 {len(TEST_IMAGES)} 个文件名...")
        files_str = " ".join(f'"{name}"' for name in TEST_IMAGES)
        print(f"  文件名格式: {files_str}")

        # 查找文件名输入框
        print("  查找文件名输入框...")
        edit = file_dialog.ComboBoxControl(searchDepth=10, Name="文件名(N):")
        if not edit.Exists(3, 1):
            print("  尝试查找EditControl...")
            edit = file_dialog.EditControl(searchDepth=10)

        if not edit.Exists(3, 1):
            print("❌ 未找到文件名输入框")
            file_dialog.SendKeys("{Escape}")
            return False

        print("✓ 找到文件名输入框")

        # 点击输入框
        print("  点击输入框...")
        edit.Click()
        time.sleep(0.3)

        # 粘贴所有文件名
        print("  粘贴文件名...")
        pyperclip.copy(files_str)
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)

        print("✓ 已输入文件名")

        # Step 8: 点击打开按钮
        print("\n[Step 8] 点击'打开'按钮...")
        open_btn = file_dialog.ButtonControl(searchDepth=10, Name="打开(O)")

        if open_btn.Exists(3, 1):
            print("  找到'打开(O)'按钮，点击...")
            open_btn.Click()
            print("✓ 已点击'打开'按钮")
        else:
            print("  未找到'打开(O)'按钮，尝试按Enter...")
            file_dialog.SendKeys("{Enter}")
            print("✓ 已按Enter确认")

        time.sleep(1.5)

        # Step 9: 验证图片是否加载到输入框
        print("\n[Step 9] 验证图片加载...")
        time.sleep(0.5)
        print("⚠ 请人工检查微信输入框中是否出现了图片预览")

        # Step 10: 询问是否发送
        print("\n" + "="*60)
        print("测试完成！")
        print("="*60)

        send_choice = input("\n是否发送这些图片到群聊？(y/n): ").strip().lower()

        if send_choice == 'y':
            print("\n按Enter发送...")
            auto.SendKeys("{Enter}")
            time.sleep(1)
            print("✓ 已发送")
        else:
            print("\n取消发送，按ESC清空...")
            auto.SendKeys("{Escape}")
            time.sleep(0.5)
            print("✓ 已取消")

        return True

    except Exception as e:
        logger.exception(f"测试过程中出错: {e}")
        return False


if __name__ == "__main__":
    success = test_file_dialog_upload()

    print("\n" + "="*60)
    if success:
        print("测试结果: ✓ 成功")
    else:
        print("测试结果: ✗ 失败")
    print("="*60)

    input("\n按 Enter 键退出...")
