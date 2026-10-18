# -*- coding: utf-8 -*-
"""生成应用图标：蓝色圆角方块 + 白色盾牌 + “1”（只保留一个实例）。

用法： python tools/make_icon.py
输出： assets/anti_misopen.ico、assets/anti_misopen.png、assets/anti_misopen_256.png
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
SIZE = 1024


def _font(size: int):
    for name in ("segoeuib.ttf", "arialbd.ttf", "msyhbd.ttc", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _vertical_gradient(size: int, top=(58, 130, 255), bottom=(26, 74, 214)) -> Image.Image:
    image = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        ratio = y / float(size - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        draw.line([(0, y), (size - 1, y)], fill=color)
    return image


def _shield_points(size: int):
    """居中的盾牌轮廓点。"""
    width = size * 0.56
    height = size * 0.66
    left = (size - width) / 2.0
    top = size * 0.16
    right = left + width
    bottom = top + height
    shoulder = top + height * 0.30
    points = [
        (left, top + height * 0.04),
        (left + width * 0.32, top),
        (size / 2.0, top + height * 0.035),
        (right - width * 0.32, top),
        (right, top + height * 0.04),
        (right, top + height * 0.42),
    ]
    # 右半边向下收拢到尖端，再镜像回左侧
    tail = [
        (right - width * 0.05, top + height * 0.62),
        (right - width * 0.20, top + height * 0.80),
        (right - width * 0.35, top + height * 0.92),
        (size / 2.0, bottom),
        (left + width * 0.35, top + height * 0.92),
        (left + width * 0.20, top + height * 0.80),
        (left + width * 0.05, top + height * 0.62),
        (left, top + height * 0.42),
    ]
    return points + tail, (left, top, right, bottom, shoulder)


def build() -> None:
    os.makedirs(ASSETS, exist_ok=True)
    base = _vertical_gradient(SIZE).convert("RGBA")

    shape = Image.new("L", (SIZE, SIZE), 0)
    shape_draw = ImageDraw.Draw(shape)
    shape_draw.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=int(SIZE * 0.235), fill=255)

    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.paste(base, (0, 0), shape)

    # 轻微高光
    gloss = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gloss_draw = ImageDraw.Draw(gloss)
    gloss_draw.ellipse([-SIZE * 0.28, -SIZE * 0.62, SIZE * 1.28, SIZE * 0.52],
                       fill=(255, 255, 255, 34))
    icon = Image.alpha_composite(icon, gloss)

    # 盾牌（白色，半透明阴影）
    points, _ = _shield_points(SIZE)
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    offset = int(SIZE * 0.018)
    shadow_draw.polygon([(x, y + offset) for x, y in points], fill=(10, 30, 80, 80))
    icon = Image.alpha_composite(icon, shadow)

    shield = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shield_draw = ImageDraw.Draw(shield)
    shield_draw.polygon(points, fill=(255, 255, 255, 255))
    icon = Image.alpha_composite(icon, shield)

    # 盾内蓝色圆 + 数字 1
    circle_d = SIZE * 0.34
    circle = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    circle_draw = ImageDraw.Draw(circle)
    circle_draw.ellipse([(SIZE - circle_d) / 2.0, SIZE * 0.335,
                         (SIZE + circle_d) / 2.0, SIZE * 0.335 + circle_d],
                        fill=(47, 107, 255, 255))
    icon = Image.alpha_composite(icon, circle)

    number = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    number_draw = ImageDraw.Draw(number)
    font = _font(int(SIZE * 0.24))
    text = "1"
    try:
        box = number_draw.textbbox((0, 0), text, font=font)
    except AttributeError:
        box = number_draw.textsize(text, font=font)
        box = (0, 0, box[0], box[1])
    text_w = box[2] - box[0]
    text_h = box[3] - box[1]
    position = ((SIZE - text_w) / 2.0 - box[0], SIZE * 0.335 + circle_d / 2.0 - text_h / 2.0 - box[1])
    number_draw.text(position, text, font=font, fill=(255, 255, 255, 255))
    icon = Image.alpha_composite(icon, number)

    full = icon.resize((256, 256), Image.LANCZOS)
    full.save(os.path.join(ASSETS, "anti_misopen_256.png"))
    icon.resize((512, 512), Image.LANCZOS).save(os.path.join(ASSETS, "anti_misopen.png"))

    sizes = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
    # 以 1024 的原图为基准，由 PIL 逐尺寸缩放写入 ICO，避免只写出 16x16。
    icon.save(os.path.join(ASSETS, "anti_misopen.ico"), format="ICO",
              sizes=[(size, size) for size in sizes])
    print("icon written:", os.path.join(ASSETS, "anti_misopen.ico"))


if __name__ == "__main__":
    build()
