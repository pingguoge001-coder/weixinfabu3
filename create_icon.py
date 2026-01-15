#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成程序图标脚本

运行此脚本生成 icon.ico 文件
"""

from PIL import Image, ImageDraw, ImageFont
import io


def create_icon():
    """创建微信绿色主题图标"""
    # 微信绿色
    WECHAT_GREEN = "#07C160"
    WHITE = "#FFFFFF"

    sizes = [256, 128, 64, 48, 32, 16]
    images = []

    for size in sizes:
        # 创建图像
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 绘制圆形背景
        padding = size // 16
        draw.ellipse(
            [padding, padding, size - padding, size - padding],
            fill=WECHAT_GREEN
        )

        # 绘制发布图标（简化的上箭头/发送符号）
        center_x = size // 2
        center_y = size // 2
        arrow_size = size // 3

        # 箭头三角形
        points = [
            (center_x, center_y - arrow_size // 2),  # 顶点
            (center_x - arrow_size // 2, center_y + arrow_size // 4),  # 左下
            (center_x + arrow_size // 2, center_y + arrow_size // 4),  # 右下
        ]
        draw.polygon(points, fill=WHITE)

        # 箭头底部矩形
        rect_width = arrow_size // 3
        rect_height = arrow_size // 2
        draw.rectangle(
            [
                center_x - rect_width // 2,
                center_y,
                center_x + rect_width // 2,
                center_y + rect_height
            ],
            fill=WHITE
        )

        images.append(img)

    # 保存为 ICO 文件
    images[0].save(
        "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:]
    )

    print(f"图标已生成: icon.ico")
    print(f"包含尺寸: {sizes}")


if __name__ == "__main__":
    create_icon()
