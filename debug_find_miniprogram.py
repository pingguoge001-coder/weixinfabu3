"""
查找微信小程序窗口 - 花城农夫

使用方法：
1. 打开微信小程序"花城农夫"
2. 运行此脚本
3. 查看输出，找到小程序窗口的属性
"""

import uiautomation as auto
import logging
from datetime import datetime

# 设置日志输出到文件和控制台
log_file = f"miniprogram_detect_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def find_miniprogram_window():
    """查找微信小程序窗口"""
    print("="*60)
    print("微信小程序窗口探测工具 - 花城农夫")
    print("="*60)

    print("\n请确保:")
    print("  1. 微信已打开")
    print("  2. 小程序'花城农夫'已打开")
    print("  3. 小程序窗口在前台可见")

    import time
    print("\n等待3秒后开始探测...")
    time.sleep(3)

    print("\n" + "="*60)
    print("方法1: 枚举所有顶层窗口")
    print("="*60)

    found_windows = []

    # 枚举所有顶层窗口
    for i in range(50):
        try:
            window = auto.WindowControl(searchDepth=1, foundIndex=i+1)
            if window.Exists(0, 0):
                name = window.Name if window.Name else "(空)"
                class_name = window.ClassName if window.ClassName else "(空)"

                # 查找包含"花城"、"农夫"、"小程序"、"miniprogram"等关键词的窗口
                keywords = ["花城", "农夫", "小程序", "miniprogram", "Mini", "苹果哥"]
                is_target = any(keyword in name.lower() or keyword in class_name.lower()
                               for keyword in [k.lower() for k in keywords])

                if is_target or "mmui" in class_name.lower() or "wechat" in name.lower() or "微信" in name:
                    found_windows.append((i+1, window))
                    print(f"\n[窗口 {i+1}]")
                    print(f"  Name          : {name}")
                    print(f"  ClassName     : {class_name}")

                    # 获取窗口位置
                    try:
                        rect = window.BoundingRectangle
                        print(f"  位置          : ({rect.left}, {rect.top})")
                        print(f"  大小          : {rect.width()}x{rect.height()}")
                    except:
                        pass

                    # 判断是否可能是目标窗口
                    if is_target:
                        print(f"  >>> [可能是小程序窗口！] <<<")
        except:
            break

    print("\n" + "="*60)
    print("方法2: 从微信主窗口查找子窗口")
    print("="*60)

    # 查找微信主窗口
    main_window = auto.WindowControl(searchDepth=1, ClassName="mmui::MainWindow")
    if main_window.Exists(5, 1):
        print("[OK] 找到微信主窗口")
        print(f"  Name: {main_window.Name}")

        # 查找所有子窗口
        print("\n枚举微信主窗口的子窗口...")
        for depth in [3, 5, 8]:
            print(f"\n--- searchDepth={depth} ---")
            for i in range(20):
                try:
                    child = main_window.WindowControl(searchDepth=depth, foundIndex=i+1)
                    if child.Exists(0, 0):
                        name = child.Name if child.Name else "(空)"
                        class_name = child.ClassName if child.ClassName else "(空)"

                        # 查找包含关键词的子窗口
                        keywords = ["花城", "农夫", "小程序", "miniprogram", "Mini", "苹果哥"]
                        is_target = any(keyword in name or keyword in class_name for keyword in keywords)

                        if is_target:
                            print(f"\n[子窗口 {i+1}]")
                            print(f"  Name          : {name}")
                            print(f"  ClassName     : {class_name}")
                            print(f"  >>> [可能是小程序窗口！] <<<")
                except:
                    break
    else:
        print("[X] 未找到微信主窗口")

    print("\n" + "="*60)
    print("方法3: 通过ClassName直接查找")
    print("="*60)

    # 尝试常见的小程序窗口类名
    possible_classnames = [
        "mmui::MiniProgramWindow",
        "mmui::WebViewWindow",
        "Chrome_WidgetWin_1",
        "mmui::ChildWindow",
    ]

    for class_name in possible_classnames:
        print(f"\n尝试ClassName: {class_name}")
        window = auto.WindowControl(searchDepth=1, ClassName=class_name)
        if window.Exists(2, 1):
            print(f"  [OK] 找到窗口")
            print(f"  Name: {window.Name if window.Name else '(空)'}")
            rect = window.BoundingRectangle
            print(f"  位置: ({rect.left}, {rect.top})")
            print(f"  大小: {rect.width()}x{rect.height()}")
        else:
            print(f"  [X] 未找到")

    print("\n" + "="*60)
    print("探测完成")
    print("="*60)

    if found_windows:
        print(f"\n共找到 {len(found_windows)} 个可能的窗口")
        print("请根据Name、ClassName和位置信息判断哪个是小程序窗口")
    else:
        print("\n未找到匹配的窗口")
        print("提示:")
        print("  1. 确保小程序窗口已打开且在前台")
        print("  2. 尝试点击小程序窗口使其获得焦点")
        print("  3. 小程序可能以嵌入式控件形式存在于微信主窗口内")

    print(f"\n完整输出已保存到文件: {log_file}")


if __name__ == "__main__":
    print(f"日志文件: {log_file}")
    find_miniprogram_window()
    print(f"\n请查看日志文件获取完整信息: {log_file}")
    input("\n按 Enter 键退出...")
