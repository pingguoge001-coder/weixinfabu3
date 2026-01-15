# -*- coding: utf-8 -*-
"""
在朋友圈详情页查找评论按钮（...按钮）
"""
import uiautomation as auto

SNS_WINDOW_CLASS = "mmui::SNSWindow"

def find_comment_button():
    """查找详情页中的评论按钮"""

    # 查找朋友圈窗口
    sns_window = auto.WindowControl(searchDepth=1, ClassName=SNS_WINDOW_CLASS)

    if not sns_window.Exists(3, 1):
        print("Not found SNS window")
        return

    rect = sns_window.BoundingRectangle
    print(f"Window: ({rect.left},{rect.top}) - ({rect.right},{rect.bottom})")
    print()

    # 搜索窗口中下部分的所有控件（Y > 500）
    print("Searching for controls in lower part of window (Y > 500)...")
    print("=" * 60)

    found_controls = []

    def find_all(control, depth=0):
        if depth > 30:
            return
        try:
            ctrl_type = control.ControlTypeName
            ctrl_class = control.ClassName or ""
            ctrl_name = control.Name or ""
            ctrl_rect = control.BoundingRectangle

            if ctrl_rect:
                center_x = (ctrl_rect.left + ctrl_rect.right) // 2
                center_y = (ctrl_rect.top + ctrl_rect.bottom) // 2
                width = ctrl_rect.right - ctrl_rect.left
                height = ctrl_rect.bottom - ctrl_rect.top

                # 在窗口下半部分，排除太大的控件
                if center_y > 500 and width < 300 and height < 200:
                    found_controls.append({
                        'type': ctrl_type,
                        'class': ctrl_class,
                        'name': ctrl_name[:30] if ctrl_name else "",
                        'rect': ctrl_rect,
                        'size': (width, height),
                        'center': (center_x, center_y),
                        'depth': depth
                    })

            for child in control.GetChildren():
                find_all(child, depth + 1)
        except:
            pass

    find_all(sns_window)

    # 按 Y 坐标和 X 坐标排序
    found_controls.sort(key=lambda x: (x['center'][1], x['center'][0]))

    print(f"\nFound {len(found_controls)} controls:\n")

    for i, ctrl in enumerate(found_controls[:20]):  # 只显示前20个
        print(f"[{i+1}] {ctrl['type']} - {ctrl['class']}")
        print(f"    Name: '{ctrl['name']}'")
        r = ctrl['rect']
        print(f"    Rect: ({r.left},{r.top}) - ({r.right},{r.bottom})")
        print(f"    Center: {ctrl['center']}, Size: {ctrl['size']}")
        print()

if __name__ == "__main__":
    print("Find Comment Button in Detail Page")
    print("=" * 60)
    find_comment_button()
