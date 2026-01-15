"""
微信自动化测试脚本
功能：
1. 发布朋友圈（文字+图片）
2. 打开微信群并发送图片
"""
import time
import os
import random
from pathlib import Path

print("=" * 50)
print("       微信自动化测试")
print("=" * 50)
print()
print("请选择要测试的功能：")
print()
print("  [1] 发布朋友圈（测试）")
print("  [2] 打开微信群并发送图片")
print("  [3] 退出")
print()

choice = input("请输入选项 (1/2/3): ").strip()

if choice == "1":
    # ========== 测试发布朋友圈 ==========
    print()
    print("-" * 50)
    print("  发布朋友圈测试")
    print("-" * 50)
    print()

    # 获取文案
    print("请输入朋友圈文案（直接回车使用默认文案）：")
    text = input("> ").strip()
    if not text:
        text = "这是一条测试朋友圈 #自动发布测试"
        print(f"使用默认文案: {text}")

    # 获取图片
    print()
    print("请输入图片路径（直接回车不添加图片，多张图片用逗号分隔）：")
    print("例如: C:\\图片\\1.jpg,C:\\图片\\2.jpg")
    img_input = input("> ").strip()

    image_paths = []
    if img_input:
        for p in img_input.split(","):
            p = p.strip()
            if os.path.exists(p):
                image_paths.append(p)
                print(f"  ✓ 找到图片: {p}")
            else:
                print(f"  ✗ 图片不存在: {p}")

    print()
    print("=" * 50)
    print(f"  文案: {text[:30]}{'...' if len(text) > 30 else ''}")
    print(f"  图片数量: {len(image_paths)}")
    print("=" * 50)
    print()

    confirm = input("确认发布? (输入 y 确认): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        input("按回车键退出...")
        exit(0)

    print()
    print("开始发布...")
    print()

    from models.content import Content
    from models.enums import Channel
    from core.moment_sender import MomentSender

    # 创建内容
    content = Content(
        content_code="TEST001",
        text=text,
        image_paths=image_paths,
        channel=Channel.moment
    )

    # 发布
    sender = MomentSender()
    result = sender.send_moment(content)

    print()
    print("=" * 50)
    if result.is_success:
        print("  发布成功!")
    else:
        print(f"  发布失败: {result.message}")
        if result.screenshot_path:
            print(f"  错误截图: {result.screenshot_path}")
    print(f"  耗时: {result.duration:.1f} 秒")
    print("=" * 50)

elif choice == "2":
    # ========== 打开微信群并发送图片 ==========
    print()
    print("-" * 50)
    print("  打开微信群并发送图片")
    print("-" * 50)
    print()

    print("请输入群名称：")
    group_name = input("> ").strip()

    if not group_name:
        print("群名称不能为空")
        input("按回车键退出...")
        exit(1)

    # 默认图片文件夹
    default_folder = r"D:\苹果哥的商业系统A\电商\产品素材\待发布\十一月\2025-11-26"

    print()
    print(f"请输入图片文件夹路径（直接回车使用默认路径）：")
    print(f"默认: {default_folder}")
    folder_input = input("> ").strip()

    if not folder_input:
        folder_path = default_folder
    else:
        folder_path = folder_input

    # 检查文件夹是否存在
    if not os.path.exists(folder_path):
        print(f"✗ 文件夹不存在: {folder_path}")
        input("按回车键退出...")
        exit(1)

    # 扫描文件夹中的图片
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    images = []
    for f in os.listdir(folder_path):
        if Path(f).suffix.lower() in image_extensions:
            images.append(os.path.join(folder_path, f))

    if not images:
        print(f"✗ 文件夹中没有图片: {folder_path}")
        input("按回车键退出...")
        exit(1)

    # 随机选择一张图片
    selected_image = random.choice(images)
    print()
    print(f"✓ 找到 {len(images)} 张图片")
    print(f"✓ 随机选择: {os.path.basename(selected_image)}")

    print()
    print("=" * 50)
    print(f"  群名称: {group_name}")
    print(f"  发送图片: {os.path.basename(selected_image)}")
    print("=" * 50)
    print()

    confirm = input("确认发送? (输入 y 确认): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        input("按回车键退出...")
        exit(0)

    print()
    print("开始执行...")
    print()

    from core.wechat_controller import get_wechat_controller
    import uiautomation as auto
    import pyautogui
    import pyperclip

    controller = get_wechat_controller()

    # 第1步：激活微信
    if not controller.activate_window():
        print("✗ 激活微信窗口失败")
        input("按回车键退出...")
        exit(1)

    print("✓ 微信窗口已激活")
    time.sleep(0.5)

    main_window = controller.get_main_window()
    if not main_window:
        print("✗ 找不到微信主窗口")
        input("按回车键退出...")
        exit(1)

    # 第2步：搜索并打开群
    print("✓ 打开搜索框...")
    pyautogui.hotkey('ctrl', 'f')
    time.sleep(0.5)

    print(f"✓ 搜索群: {group_name}")
    pyperclip.copy(group_name)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(1.5)

    # 按回车进入群
    print("✓ 进入群聊...")
    pyautogui.press('enter')
    time.sleep(1)

    # 第3步：发送图片
    print(f"✓ 复制图片到剪贴板...")

    # 使用 PowerShell 复制文件到剪贴板
    def copy_file_to_clipboard_ps(file_path):
        """使用 PowerShell 复制文件到剪贴板"""
        import subprocess
        file_path = os.path.abspath(file_path)

        # PowerShell 命令复制文件到剪贴板
        ps_command = f'''
        Add-Type -AssemblyName System.Windows.Forms
        $files = [System.Collections.Specialized.StringCollection]::new()
        $files.Add("{file_path}")
        [System.Windows.Forms.Clipboard]::SetFileDropList($files)
        '''

        try:
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return True
            else:
                print(f"    PowerShell 错误: {result.stderr}")
                return False
        except Exception as e:
            print(f"    执行错误: {e}")
            return False

    if not copy_file_to_clipboard_ps(selected_image):
        print("✗ 复制图片失败")
        input("按回车键退出...")
        exit(1)

    print(f"✓ 图片已复制: {os.path.basename(selected_image)}")
    time.sleep(0.5)

    # 粘贴图片
    print("✓ 粘贴图片...")
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(2)  # 等待图片加载

    # 按 Alt+S 发送（对应发送按钮快捷键）
    print("✓ 发送图片...")
    pyautogui.hotkey('alt', 's')
    time.sleep(1)

    print()
    print("=" * 50)
    print("  图片发送成功!")
    print("=" * 50)

else:
    print("已退出")

print()
input("按回车键退出...")
