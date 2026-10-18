# -*- coding: utf-8 -*-
"""自绘矢量图标（不依赖 emoji / 系统字体，Win7 上显示一致）。"""
from __future__ import annotations

import math

from PySide2.QtCore import QPointF, QRectF, Qt
from PySide2.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap


def _rounded_rect(p: QPainter, x, y, w, h, r):
    p.drawRoundedRect(QRectF(x, y, w, h), r, r)


def _icon_shield(p: QPainter):
    path = QPainterPath()
    path.moveTo(12, 2.6)
    path.lineTo(20, 5.6)
    path.lineTo(20, 11)
    path.cubicTo(20, 16.1, 16.6, 20.3, 12, 21.6)
    path.cubicTo(7.4, 20.3, 4, 16.1, 4, 11)
    path.lineTo(4, 5.6)
    path.closeSubpath()
    p.drawPath(path)
    path2 = QPainterPath()
    path2.moveTo(8.4, 11.7)
    path2.lineTo(10.9, 14.2)
    path2.lineTo(15.7, 9.3)
    p.drawPath(path2)


def _icon_grid(p: QPainter):
    for x, y in ((4.5, 4.5), (13.2, 4.5), (4.5, 13.2), (13.2, 13.2)):
        _rounded_rect(p, x, y, 6.3, 6.3, 1.8)


def _icon_sliders(p: QPainter):
    p.drawLine(QPointF(4.5, 7), QPointF(19.5, 7))
    p.drawLine(QPointF(4.5, 12), QPointF(19.5, 12))
    p.drawLine(QPointF(4.5, 17), QPointF(19.5, 17))
    brush = p.brush()
    p.setBrush(p.pen().color())
    for cx, cy in ((9.2, 7), (15.2, 12), (8.0, 17)):
        p.drawEllipse(QPointF(cx, cy), 2.0, 2.0)
    p.setBrush(brush)


def _icon_ban(p: QPainter):
    p.drawEllipse(QPointF(12, 12), 8.6, 8.6)
    p.drawLine(QPointF(6.0, 6.0), QPointF(18.0, 18.0))


def _icon_gear(p: QPainter):
    p.drawEllipse(QPointF(12, 12), 3.4, 3.4)
    for i in range(8):
        angle = math.pi * 2 * i / 8.0
        x1 = 12 + math.cos(angle) * 6.0
        y1 = 12 + math.sin(angle) * 6.0
        x2 = 12 + math.cos(angle) * 8.4
        y2 = 12 + math.sin(angle) * 8.4
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _icon_info(p: QPainter):
    p.drawEllipse(QPointF(12, 12), 8.6, 8.6)
    p.setBrush(p.pen().color())
    p.drawEllipse(QPointF(12, 7.8), 1.05, 1.05)
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(12, 11.2), QPointF(12, 16.4))


def _icon_plus(p: QPainter):
    p.drawLine(QPointF(12, 5), QPointF(12, 19))
    p.drawLine(QPointF(5, 12), QPointF(19, 12))


def _icon_minus(p: QPainter):
    p.drawLine(QPointF(5, 12), QPointF(19, 12))


def _icon_trash(p: QPainter):
    p.drawLine(QPointF(4.5, 7), QPointF(19.5, 7))
    p.drawLine(QPointF(9.5, 7), QPointF(9.5, 4.8))
    p.drawLine(QPointF(9.5, 4.8), QPointF(14.5, 4.8))
    p.drawLine(QPointF(14.5, 4.8), QPointF(14.5, 7))
    path = QPainterPath()
    path.moveTo(6.8, 7)
    path.lineTo(7.8, 20.2)
    path.lineTo(16.2, 20.2)
    path.lineTo(17.2, 7)
    p.drawPath(path)
    p.drawLine(QPointF(10.3, 10.2), QPointF(10.6, 17.2))
    p.drawLine(QPointF(13.7, 10.2), QPointF(13.4, 17.2))


def _icon_close(p: QPainter):
    p.drawLine(QPointF(7, 7), QPointF(17, 17))
    p.drawLine(QPointF(17, 7), QPointF(7, 17))


def _icon_min(p: QPainter):
    p.drawLine(QPointF(6.5, 12), QPointF(17.5, 12))


def _icon_chevron_down(p: QPainter):
    path = QPainterPath()
    path.moveTo(7, 10)
    path.lineTo(12, 15)
    path.lineTo(17, 10)
    p.drawPath(path)


def _icon_chevron_right(p: QPainter):
    path = QPainterPath()
    path.moveTo(10, 7)
    path.lineTo(15, 12)
    path.lineTo(10, 17)
    p.drawPath(path)


def _icon_folder(p: QPainter):
    path = QPainterPath()
    path.moveTo(3.6, 7.4)
    path.lineTo(3.6, 18.4)
    path.cubicTo(3.6, 19.3, 4.3, 20, 5.2, 20)
    path.lineTo(18.8, 20)
    path.cubicTo(19.7, 20, 20.4, 19.3, 20.4, 18.4)
    path.lineTo(20.4, 9.4)
    path.cubicTo(20.4, 8.5, 19.7, 7.8, 18.8, 7.8)
    path.lineTo(12.2, 7.8)
    path.lineTo(10.2, 5.2)
    path.lineTo(5.2, 5.2)
    path.cubicTo(4.3, 5.2, 3.6, 5.9, 3.6, 6.8)
    path.closeSubpath()
    p.drawPath(path)


def _icon_app(p: QPainter):
    _rounded_rect(p, 4.2, 4.2, 15.6, 15.6, 3.0)
    p.drawLine(QPointF(4.6, 9.0), QPointF(19.4, 9.0))
    p.setBrush(p.pen().color())
    p.drawEllipse(QPointF(7.4, 6.7), 0.9, 0.9)
    p.drawEllipse(QPointF(10.2, 6.7), 0.9, 0.9)
    p.setBrush(Qt.NoBrush)


def _icon_clock(p: QPainter):
    p.drawEllipse(QPointF(12, 12), 8.6, 8.6)
    p.drawLine(QPointF(12, 7.2), QPointF(12, 12.2))
    p.drawLine(QPointF(12, 12.2), QPointF(15.6, 14.2))


def _icon_refresh(p: QPainter):
    path = QPainterPath()
    path.arcMoveTo(QRectF(4.2, 4.2, 15.6, 15.6), 60)
    path.arcTo(QRectF(4.2, 4.2, 15.6, 15.6), 60, 270)
    p.drawPath(path)
    head = QPainterPath()
    head.moveTo(17.4, 4.2)
    head.lineTo(19.6, 8.4)
    head.lineTo(15.2, 8.6)
    p.setBrush(p.pen().color())
    p.drawPath(head)
    p.setBrush(Qt.NoBrush)


def _icon_key(p: QPainter):
    p.drawEllipse(QPointF(8.2, 8.6), 3.6, 3.6)
    p.drawLine(QPointF(10.8, 11.2), QPointF(19.4, 19.8))
    p.drawLine(QPointF(16.4, 16.8), QPointF(18.6, 14.6))
    p.drawLine(QPointF(18.4, 18.8), QPointF(20.4, 16.8))


def _icon_play(p: QPainter):
    path = QPainterPath()
    path.moveTo(7.4, 5.2)
    path.lineTo(18.4, 12)
    path.lineTo(7.4, 18.8)
    path.closeSubpath()
    p.setBrush(p.pen().color())
    p.drawPath(path)
    p.setBrush(Qt.NoBrush)


def _icon_pause(p: QPainter):
    p.setBrush(p.pen().color())
    p.drawRoundedRect(QRectF(6.6, 5, 4.0, 14), 1.4, 1.4)
    p.drawRoundedRect(QRectF(13.4, 5, 4.0, 14), 1.4, 1.4)
    p.setBrush(Qt.NoBrush)


def _icon_check(p: QPainter):
    path = QPainterPath()
    path.moveTo(5, 12.6)
    path.lineTo(9.8, 17.4)
    path.lineTo(19, 7.8)
    p.drawPath(path)


def _icon_copy(p: QPainter):
    _rounded_rect(p, 8.4, 8.4, 11.2, 11.2, 2.6)
    path = QPainterPath()
    path.moveTo(15.6, 8)
    path.lineTo(15.6, 7.2)
    path.cubicTo(15.6, 6.2, 14.8, 5.4, 13.8, 5.4)
    path.lineTo(7.4, 5.4)
    path.cubicTo(6.4, 5.4, 5.6, 6.2, 5.6, 7.2)
    path.lineTo(5.6, 13.6)
    path.cubicTo(5.6, 14.6, 6.4, 15.4, 7.4, 15.4)
    path.lineTo(8.2, 15.4)
    p.drawPath(path)


def _icon_log(p: QPainter):
    _rounded_rect(p, 5.6, 3.4, 12.8, 17.2, 2.6)
    for y in (8.2, 12.0, 15.8):
        p.drawLine(QPointF(8.8, y), QPointF(15.4, y))


def _icon_external(p: QPainter):
    p.drawLine(QPointF(13.4, 4.6), QPointF(19.4, 4.6))
    p.drawLine(QPointF(19.4, 4.6), QPointF(19.4, 10.6))
    p.drawLine(QPointF(12.0, 12.0), QPointF(19.0, 5.0))
    path = QPainterPath()
    path.moveTo(18.0, 14.4)
    path.lineTo(18.0, 18.6)
    path.cubicTo(18.0, 19.5, 17.3, 20.2, 16.4, 20.2)
    path.lineTo(5.4, 20.2)
    path.cubicTo(4.5, 20.2, 3.8, 19.5, 3.8, 18.6)
    path.lineTo(3.8, 7.6)
    path.cubicTo(3.8, 6.7, 4.5, 6.0, 5.4, 6.0)
    path.lineTo(9.6, 6.0)
    p.drawPath(path)


def _icon_power(p: QPainter):
    path = QPainterPath()
    path.arcMoveTo(QRectF(4.6, 5.4, 14.8, 14.8), 130)
    path.arcTo(QRectF(4.6, 5.4, 14.8, 14.8), 130, 280)
    p.drawPath(path)
    p.drawLine(QPointF(12, 3.2), QPointF(12, 10.6))


def _icon_book(p: QPainter):
    path = QPainterPath()
    path.moveTo(4.4, 5.2)
    path.cubicTo(7.6, 4.0, 9.8, 5.0, 12, 6.4)
    path.cubicTo(14.2, 5.0, 16.4, 4.0, 19.6, 5.2)
    path.lineTo(19.6, 18.6)
    path.cubicTo(16.4, 17.4, 14.2, 18.4, 12, 19.8)
    path.cubicTo(9.8, 18.4, 7.6, 17.4, 4.4, 18.6)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(12, 6.6), QPointF(12, 19.4))


_ICONS = {
    "shield": _icon_shield,
    "grid": _icon_grid,
    "sliders": _icon_sliders,
    "ban": _icon_ban,
    "gear": _icon_gear,
    "info": _icon_info,
    "plus": _icon_plus,
    "minus": _icon_minus,
    "trash": _icon_trash,
    "close": _icon_close,
    "min": _icon_min,
    "chevron_down": _icon_chevron_down,
    "chevron_right": _icon_chevron_right,
    "folder": _icon_folder,
    "app": _icon_app,
    "clock": _icon_clock,
    "refresh": _icon_refresh,
    "key": _icon_key,
    "play": _icon_play,
    "pause": _icon_pause,
    "check": _icon_check,
    "copy": _icon_copy,
    "log": _icon_log,
    "external": _icon_external,
    "power": _icon_power,
    "book": _icon_book,
}

NAMES = tuple(_ICONS.keys())


def to_color(value, alpha=None) -> QColor:
    """把配色字符串（含 rgba(...)）转换成 QColor。"""
    if isinstance(value, QColor):
        color = QColor(value)
    else:
        text = str(value).strip()
        if text.startswith("rgba"):
            inner = text[text.find("(") + 1: text.find(")")]
            parts = [part.strip() for part in inner.split(",")]
            try:
                color = QColor(int(parts[0]), int(parts[1]), int(parts[2]),
                               int(round(float(parts[3]))) if len(parts) > 3 else 255)
            except (ValueError, IndexError):
                color = QColor("#000000")
        else:
            color = QColor(text)
    if not color.isValid():
        color = QColor("#000000")
    if alpha is not None:
        color.setAlpha(max(0, min(255, int(alpha))))
    return color


def draw_icon(painter: QPainter, name: str, rect, color, stroke: float = 1.8, alpha: int = None) -> None:
    func = _ICONS.get(name)
    if func is None:
        return
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    size = min(rect.width(), rect.height())
    scale = size / 24.0
    painter.translate(rect.x() + (rect.width() - 24 * scale) / 2.0,
                      rect.y() + (rect.height() - 24 * scale) / 2.0)
    painter.scale(scale, scale)
    pen = QPen(to_color(color, alpha))
    pen.setWidthF(stroke)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    func(painter)
    painter.restore()


def icon_pixmap(name: str, color, size: int = 20, stroke: float = 1.8, dpr: float = 1.0) -> QPixmap:
    pixmap = QPixmap(int(size * dpr), int(size * dpr))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    draw_icon(painter, name, QRectF(0, 0, size, size), color, stroke)
    painter.end()
    return pixmap
