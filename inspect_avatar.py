# -*- coding: utf-8 -*-
"""
搜索弹窗区域的所有控件
"""
import uiautomation as auto

def inspect_popup_area():
    """搜索弹窗可能存在的区域"""

    print("Searching all controls in popup area...")
    print("=" * 60)

    # 弹窗大约在屏幕中间偏右，根据截图估计
    # 搜索 x: 600-1100, y: 200-650 区域

    all_controls = []

    def find_in_area(control, depth=0):
        if depth > 30:
            return
        try:
            ctrl_rect = control.BoundingRectangle
            if ctrl_rect:
                center_x = (ctrl_rect.left + ctrl_rect.right) // 2
                center_y = (ctrl_rect.top + ctrl_rect.bottom) // 2

                # 检查是否在弹窗区域
                if 600 < center_x < 1200 and 200 < center_y < 700:
                    width = ctrl_rect.right - ctrl_rect.left
                    height = ctrl_rect.bottom - ctrl_rect.top

                    # 过滤掉太大的控件（可能是整个窗口）
                    if width < 600 and height < 500:
                        all_controls.append({
                            'name': control.Name or "",
                            'class': control.ClassName or "",
                            'type': control.ControlTypeName,
                            'rect': ctrl_rect,
                            'center': (center_x, center_y),
                            'size': (width, height),
                            'depth': depth
                        })

            for child in control.GetChildren():
                find_in_area(child, depth + 1)
        except:
            pass

    desktop = auto.GetRootControl()
    find_in_area(desktop)

    # 按 Y 坐标排序
    all_controls.sort(key=lambda x: x['center'][1])

    print(f"Found {len(all_controls)} controls in popup area:\n")

    for ctrl in all_controls:
        print(f"[{ctrl['type']}] {ctrl['class']}")
        print(f"    Name: '{ctrl['name']}'")
        rect = ctrl['rect']
        print(f"    Rect: ({rect.left},{rect.top}) - ({rect.right},{rect.bottom})")
        print(f"    Center: {ctrl['center']}, Size: {ctrl['size']}")
        print()

if __name__ == "__main__":
    print("Popup Area Inspector")
    print("=" * 60)
    inspect_popup_area()
