"""
查找微信中的"上传文件"按钮

使用方法：
1. 打开微信
2. 进入要查找按钮的界面（群聊窗口或小程序等）
3. 运行此脚本
"""

import uiautomation as auto
import sys
from datetime import datetime

# 禁用comtypes的DEBUG日志
import logging
logging.getLogger('comtypes').setLevel(logging.WARNING)


def print_element_info(elem, depth=0):
    """打印元素信息"""
    indent = "  " * depth
    name = elem.Name if elem.Name else "(空)"
    class_name = elem.ClassName if elem.ClassName else "(空)"
    control_type = elem.ControlTypeName if hasattr(elem, 'ControlTypeName') else "(未知)"
    auto_id = elem.AutomationId if elem.AutomationId else "(空)"

    try:
        rect = elem.BoundingRectangle
        pos_info = f"({rect.left}, {rect.top}) {rect.width()}x{rect.height()}"
    except:
        pos_info = "(未知)"

    return f"{indent}[{control_type}] Name='{name}' Class='{class_name}' AutoId='{auto_id}' Pos={pos_info}"


def find_buttons_with_keywords(window, keywords, output_file):
    """在窗口中查找包含关键词的按钮"""
    results = []

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"查找时间: {datetime.now()}\n")
        f.write(f"关键词: {keywords}\n")
        f.write("=" * 80 + "\n\n")

        # 枚举所有按钮
        print("\n正在枚举按钮控件...")
        f.write("=== 所有按钮 ===\n\n")

        btn_count = 0
        for i in range(100):
            try:
                btn = window.ButtonControl(searchDepth=20, foundIndex=i+1)
                if btn.Exists(0, 0):
                    btn_count += 1
                    info = print_element_info(btn)
                    f.write(f"按钮 {btn_count}: {info}\n")

                    # 检查是否包含关键词
                    name_lower = (btn.Name or "").lower()
                    class_lower = (btn.ClassName or "").lower()

                    for kw in keywords:
                        if kw.lower() in name_lower or kw.lower() in class_lower:
                            results.append((btn, info))
                            f.write(f"  >>> 匹配关键词: {kw} <<<\n")
                            print(f"  [匹配] {info}")
                            break
            except Exception as e:
                break

        print(f"共找到 {btn_count} 个按钮")
        f.write(f"\n共找到 {btn_count} 个按钮\n")

        # 枚举所有控件（不限类型）
        print("\n正在枚举所有包含关键词的控件...")
        f.write("\n" + "=" * 80 + "\n")
        f.write("=== 所有包含关键词的控件 ===\n\n")

        ctrl_count = 0
        match_count = 0
        for i in range(500):
            try:
                ctrl = window.Control(searchDepth=20, foundIndex=i+1)
                if ctrl.Exists(0, 0):
                    ctrl_count += 1
                    name = ctrl.Name or ""
                    class_name = ctrl.ClassName or ""

                    # 检查是否包含关键词
                    for kw in keywords:
                        if kw.lower() in name.lower() or kw.lower() in class_name.lower():
                            match_count += 1
                            info = print_element_info(ctrl)
                            f.write(f"控件 {match_count}: {info}\n")
                            print(f"  [匹配] {info}")
                            break
            except:
                break

        print(f"共扫描 {ctrl_count} 个控件，{match_count} 个匹配")
        f.write(f"\n共扫描 {ctrl_count} 个控件，{match_count} 个匹配\n")

    return results


def main():
    print("=" * 60)
    print("微信 '上传文件' 按钮查找工具")
    print("=" * 60)

    # 关键词列表
    keywords = ["上传", "文件", "upload", "file", "发送", "附件", "attach", "选择"]

    output_file = f"upload_button_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    print("\n正在查找微信窗口...")

    # 尝试查找微信主窗口
    main_window = auto.WindowControl(searchDepth=1, ClassName="mmui::MainWindow")

    if main_window.Exists(3, 1):
        print(f"[OK] 找到微信主窗口: {main_window.Name}")
        print(f"\n在微信主窗口中搜索...")
        results = find_buttons_with_keywords(main_window, keywords, output_file)
    else:
        print("[!] 未找到微信主窗口，将搜索所有窗口...")

        # 枚举所有顶层窗口
        print("\n枚举所有顶层窗口:")
        for i in range(30):
            try:
                window = auto.WindowControl(searchDepth=1, foundIndex=i+1)
                if window.Exists(0, 0):
                    name = window.Name or "(空)"
                    class_name = window.ClassName or "(空)"

                    # 显示所有窗口
                    print(f"  {i+1}. [{class_name}] {name}")
            except:
                break

        # 让用户选择或者搜索当前焦点窗口
        print("\n使用当前焦点窗口进行搜索...")
        focus_window = auto.GetForegroundControl()
        if focus_window:
            print(f"当前焦点窗口: {focus_window.Name}")
            results = find_buttons_with_keywords(focus_window, keywords, output_file)
        else:
            print("[X] 无法获取当前焦点窗口")
            results = []

    print("\n" + "=" * 60)
    print("搜索完成!")
    print("=" * 60)

    if results:
        print(f"\n找到 {len(results)} 个可能的'上传文件'按钮:")
        for btn, info in results:
            print(f"  - {info}")
    else:
        print("\n未找到明确包含关键词的按钮")
        print("提示:")
        print("  1. 确保微信窗口在前台")
        print("  2. 进入正确的界面（群聊、小程序等）")
        print("  3. 按钮可能使用图标而非文字")

    print(f"\n详细结果已保存到: {output_file}")


if __name__ == "__main__":
    main()
    input("\n按 Enter 键退出...")
