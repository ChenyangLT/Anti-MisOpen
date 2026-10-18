# -*- coding: utf-8 -*-
"""自绘控件库：开关、步进器、分段选择、侧边导航、主题卡片、提示条等。"""
from __future__ import annotations

from PySide2.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRectF,
                            QSize, Qt, QTimer, QVariantAnimation, Signal)
from PySide2.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen
from PySide2.QtWidgets import (QAbstractButton, QFrame, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout,
                               QWidget)

from ..core import themes
from .icons import draw_icon, to_color


def with_alpha(color, alpha: int) -> QColor:
    color = to_color(color)
    color.setAlpha(max(0, min(255, int(alpha))))
    return color


def make_label(text: str = "", role: str = None, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    if wrap:
        label.setWordWrap(True)
    return label


def make_badge(text: str, tone: str = "muted") -> QLabel:
    badge = QLabel(text)
    badge.setObjectName("Badge")
    badge.setProperty("tone", tone)
    badge.setAlignment(Qt.AlignCenter)
    badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return badge


def hline() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFrameShape(QFrame.NoFrame)
    return line


class IconView(QWidget):
    """只画一个矢量图标的小部件。"""

    def __init__(self, name: str, size: int = 20, color_key: str = None,
                 stroke: float = 1.8, parent=None):
        super().__init__(parent)
        self._name = name
        self._color_key = color_key
        self._stroke = stroke
        self.setFixedSize(size, size)

    def set_name(self, name: str) -> None:
        self._name = name
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        palette = themes.current()
        color = palette.get(self._color_key or "text", palette["text"])
        draw_icon(painter, self._name, QRectF(self.rect()), color, self._stroke)


class ToggleSwitch(QAbstractButton):
    """iOS 风格开关，带平滑动画。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(50, 28)
        self._position = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_value)
        self.toggled.connect(self._animate)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(float(self._position))
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def _on_value(self, value) -> None:
        try:
            self._position = float(value)
        except (TypeError, ValueError):
            return
        self.update()

    def setChecked(self, checked: bool) -> None:
        super().setChecked(bool(checked))
        self._anim.stop()
        self._position = 1.0 if checked else 0.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = themes.current()
        off = to_color(palette["switch_off"])
        on = to_color(palette["accent"])
        t = self._position
        track = QColor(
            int(off.red() + (on.red() - off.red()) * t),
            int(off.green() + (on.green() - off.green()) * t),
            int(off.blue() + (on.blue() - off.blue()) * t),
        )
        rect = QRectF(1, 3, self.width() - 2, self.height() - 6)
        painter.setPen(Qt.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(rect, rect.height() / 2.0, rect.height() / 2.0)

        knob_r = rect.height() / 2.0 - 2.5
        cx = rect.left() + rect.height() / 2.0 + t * (rect.width() - rect.height())
        cy = rect.center().y()
        painter.setBrush(QColor(0, 0, 0, 34))
        painter.drawEllipse(QRectF(cx - knob_r, cy - knob_r + 1.4, knob_r * 2, knob_r * 2))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(cx - knob_r, cy - knob_r, knob_r * 2, knob_r * 2))
        if self.hasFocus():
            pen = QPen(with_alpha(palette["accent"], 70))
            pen.setWidthF(1.2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(0.6, 2.6, self.width() - 1.2, self.height() - 5.2),
                                    rect.height() / 2.0, rect.height() / 2.0)


class Stepper(QWidget):
    """圆角步进器：[-] 数值 [+]"""

    valueChanged = Signal(float)

    def __init__(self, value: float, minimum: float, maximum: float,
                 step: float = 1.0, decimals: int = 0, suffix: str = "", parent=None):
        super().__init__(parent)
        self._value = float(value)
        self._min = float(minimum)
        self._max = float(maximum)
        self._step = float(step)
        self._decimals = int(decimals)
        self._suffix = suffix or ""
        self.setFixedSize(146, 34)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._pressed = 0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(120)

    def value(self) -> float:
        return self._value

    def setValue(self, value: float, emit: bool = False) -> None:
        value = max(self._min, min(self._max, float(value)))
        changed = abs(value - self._value) > 1e-9
        self._value = value
        self.update()
        if changed and emit:
            self.valueChanged.emit(self._value)

    def _nudge(self, direction: int) -> None:
        self.setValue(self._value + direction * self._step, emit=True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = themes.current()
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setPen(QPen(to_color(palette["border"]), 1.0))
        painter.setBrush(to_color(palette["input_bg"]))
        painter.drawRoundedRect(rect, 9, 9)

        for index, (name, x) in enumerate((("minus", 6.0), ("plus", self.width() - 26.0))):
            enabled = (self._value > self._min + 1e-9) if index == 0 else (self._value < self._max - 1e-9)
            color = to_color(palette["text"] if enabled else palette["faint"])
            if self._pressed == index + 1:
                painter.setPen(Qt.NoPen)
                painter.setBrush(with_alpha(palette["accent"], 26))
                painter.drawRoundedRect(QRectF(x - 4, 5, 24, 24), 6, 6)
            draw_icon(painter, name, QRectF(x, 9, 16, 16), color, 2.0)

        text = ("%." + str(self._decimals) + "f") % self._value + self._suffix
        font = QFont(self.font())
        font.setPointSizeF(10.0)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(to_color(palette["text"]))
        painter.drawText(QRectF(30, 0, self.width() - 60, self.height()), Qt.AlignCenter, text)

    def _in_zone(self, pos: QPoint) -> int:
        if pos.x() < 32:
            return 1
        if pos.x() > self.width() - 32:
            return 2
        return 0

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = self._in_zone(event.pos())
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        zone = self._in_zone(event.pos())
        if self._pressed and zone == self._pressed:
            self._nudge(-1 if zone == 1 else 1)
        self._pressed = 0
        self.update()
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        self._nudge(1 if event.angleDelta().y() > 0 else -1)
        event.accept()


class SegmentedControl(QWidget):
    """分段选择器。"""

    changed = Signal(str)

    def __init__(self, options, current: str = None, parent=None):
        super().__init__(parent)
        self._options = [(str(key), str(label)) for key, label in options]
        self._current = current if current is not None else self._options[0][0]
        self._hover = -1
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._highlight = float(self._index_of(self._current))
        self._anim.valueChanged.connect(self._on_anim)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)
        metrics = QFontMetrics(self.font())
        width = 0
        for _, label in self._options:
            width = max(width, metrics.horizontalAdvance(label))
        segment = max(84, width + 44)
        self.setFixedWidth(segment * len(self._options) + 8)

    def _index_of(self, key: str) -> int:
        for index, (option_key, _) in enumerate(self._options):
            if option_key == key:
                return index
        return 0

    def value(self) -> str:
        return self._current

    def setValue(self, key: str) -> None:
        if key == self._current:
            return
        self._current = key
        self._anim.stop()
        self._anim.setStartValue(float(self._highlight))
        self._anim.setEndValue(float(self._index_of(key)))
        self._anim.start()

    def _on_anim(self, value) -> None:
        try:
            self._highlight = float(value)
        except (TypeError, ValueError):
            return
        self.update()

    def _segment_rect(self, index: int) -> QRectF:
        count = max(1, len(self._options))
        margin = 4.0
        width = (self.width() - margin * 2) / count
        return QRectF(margin + index * width, margin, width, self.height() - margin * 2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = themes.current()
        painter.setPen(QPen(to_color(palette["border"]), 1.0))
        painter.setBrush(to_color(palette["card_soft"]))
        painter.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 10, 10)

        selected = self._highlight
        low = int(selected)
        frac = selected - low
        rect_a = self._segment_rect(low)
        if frac > 0.001 and low + 1 < len(self._options):
            rect_b = self._segment_rect(low + 1)
            rect = QRectF(rect_a.x() + (rect_b.x() - rect_a.x()) * frac, rect_a.y(),
                          rect_a.width(), rect_a.height())
        else:
            rect = rect_a
        painter.setPen(Qt.NoPen)
        painter.setBrush(to_color(palette["accent"]))
        painter.drawRoundedRect(rect, 7, 7)

        font = QFont(self.font())
        font.setPointSizeF(9.5)
        painter.setFont(font)
        for index, (_, label) in enumerate(self._options):
            is_current = index == self._index_of(self._current)
            if is_current:
                painter.setPen(QColor("#FFFFFF"))
            else:
                painter.setPen(to_color(palette["muted"]))
            painter.drawText(self._segment_rect(index), Qt.AlignCenter, label)

    def _index_at(self, pos) -> int:
        for index in range(len(self._options)):
            if self._segment_rect(index).contains(pos.x(), pos.y()):
                return index
        return -1

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            index = self._index_at(event.pos())
            if index >= 0:
                self.setValue(self._options[index][0])
                self.changed.emit(self._current)

    def mouseMoveEvent(self, event):
        index = self._index_at(event.pos())
        if index != self._hover:
            self._hover = index
            self.update()

    def leaveEvent(self, event):
        self._hover = -1
        self.update()


class NavButton(QAbstractButton):
    """侧边栏导航按钮（自绘）。"""

    def __init__(self, icon_name: str, text: str, parent=None):
        super().__init__(parent)
        self._icon = icon_name
        self._text = text
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_Hover, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = themes.current()
        rect = QRectF(8, 3, self.width() - 16, self.height() - 6)
        checked = self.isChecked()
        hover = self.underMouse()

        if checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(to_color(palette["sidebar_active_bg"]))
            painter.drawRoundedRect(rect, 10, 10)
            painter.setBrush(to_color(palette["accent"]))
            painter.drawRoundedRect(QRectF(rect.left() + 6, rect.center().y() - 8, 3, 16), 1.5, 1.5)
        elif hover:
            painter.setPen(Qt.NoPen)
            painter.setBrush(to_color(palette["sidebar_hover_bg"]))
            painter.drawRoundedRect(rect, 10, 10)

        icon_color = palette["sidebar_active"] if checked else palette["sidebar_text"]
        draw_icon(painter, self._icon, QRectF(rect.left() + 18, rect.center().y() - 9, 18, 18),
                  icon_color, 1.7)
        font = QFont(self.font())
        font.setPointSizeF(9.8)
        font.setBold(checked)
        painter.setFont(font)
        painter.setPen(to_color(palette["sidebar_active"] if checked else palette["sidebar_text"]))
        painter.drawText(QRectF(rect.left() + 48, rect.top(), rect.width() - 52, rect.height()),
                         Qt.AlignVCenter | Qt.AlignLeft, self._text)


class WindowButton(QAbstractButton):
    """无边框窗口的最小化 / 关闭按钮。"""

    def __init__(self, icon_name: str, danger: bool = False, parent=None):
        super().__init__(parent)
        self._icon = icon_name
        self._danger = danger
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(32, 32)
        self.setAttribute(Qt.WA_Hover, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = themes.current()
        rect = QRectF(2, 2, self.width() - 4, self.height() - 4)
        if self.underMouse():
            painter.setPen(Qt.NoPen)
            color = to_color(palette["danger_soft"] if self._danger else palette["border"])
            color.setAlpha(170)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 8, 8)
        color = palette["danger"] if (self._danger and self.underMouse()) else palette["muted"]
        draw_icon(painter, self._icon, QRectF(rect.center().x() - 7, rect.center().y() - 7, 14, 14),
                  color, 1.9)


class ThemeCard(QAbstractButton):
    """主题选择卡片。"""

    def __init__(self, key: str, label: str, description: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._label = label
        self._description = description
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(168, 104)
        self.setAttribute(Qt.WA_Hover, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = themes.current()
        preview = themes.PALETTES.get(self._key) or palette
        if self._key == "system":
            preview = themes.PALETTES[themes.resolve_key("system")]

        checked = self.isChecked()
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        painter.setBrush(to_color(palette["card"]))
        if checked:
            painter.setPen(QPen(to_color(palette["accent"]), 2.0))
        else:
            painter.setPen(QPen(to_color(palette["border"]), 1.0))
        painter.drawRoundedRect(rect, 12, 12)

        # 三色预览
        dots = [preview["accent"], preview["hero_b"], preview["bg"]]
        for index, color in enumerate(dots):
            painter.setPen(Qt.NoPen)
            painter.setBrush(to_color(color))
            painter.drawEllipse(QRectF(14 + index * 18, 14, 14, 14))

        font = QFont(self.font())
        font.setPointSizeF(9.8)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(to_color(palette["text"]))
        painter.drawText(QRectF(14, 38, self.width() - 28, 20), Qt.AlignLeft | Qt.AlignVCenter, self._label)

        font.setPointSizeF(8.2)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(to_color(palette["muted"]))
        painter.drawText(QRectF(14, 58, self.width() - 28, 32), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
                         self._description)

        if checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(to_color(palette["accent"]))
            painter.drawEllipse(QRectF(self.width() - 30, 12, 18, 18))
            draw_icon(painter, "check", QRectF(self.width() - 27, 15, 12, 12), "#FFFFFF", 2.2)


class CardRow(QFrame):
    """带悬停高亮的列表行。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFrameShape(QFrame.NoFrame)

    def paintEvent(self, event):
        if self.underMouse():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)
            palette = themes.current()
            painter.setPen(Qt.NoPen)
            painter.setBrush(to_color(palette["row_hover"]))
            painter.drawRoundedRect(QRectF(self.rect()), 10, 10)
        super().paintEvent(event)


class Toast(QFrame):
    """窗口内浮动的轻提示。"""

    TONES = {"success": ("check", "success"), "danger": ("ban", "danger"),
             "warning": ("info", "warning"), "info": ("info", "accent")}

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setObjectName("Toast")
        self.hide()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 18, 10)
        layout.setSpacing(10)
        self._icon = IconView("check", 18, "success")
        self._label = make_label("", "body")
        self._label.setStyleSheet("font-size: 9.5pt;")
        layout.addWidget(self._icon)
        layout.addWidget(self._label)
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setDuration(200)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_hide)
        self._tone = "success"

    def show_message(self, text: str, tone: str = "success", duration: int = 2600) -> None:
        icon_name, color_key = self.TONES.get(tone, self.TONES["info"])
        self._tone = tone
        self._icon.set_name(icon_name)
        self._icon._color_key = color_key
        self._icon.update()
        self._label.setText(text)
        self.adjustSize()
        self.setFixedWidth(min(max(self.sizeHint().width(), 220), 360))
        self.adjustSize()
        self.reposition()
        self._fade.stop()
        self._fade.setStartValue(float(self._opacity.opacity()))
        self._fade.setEndValue(1.0)
        self._fade.start()
        self.show()
        self.raise_()
        self._timer.start(duration)

    def _start_hide(self) -> None:
        self._fade.stop()
        self._fade.setStartValue(float(self._opacity.opacity()))
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self._after_hide)
        self._fade.start()

    def _after_hide(self) -> None:
        try:
            self._fade.finished.disconnect(self._after_hide)
        except (RuntimeError, TypeError):
            pass
        if self._opacity.opacity() <= 0.01:
            self.hide()

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.move(parent.width() - self.width() - 24, parent.height() - self.height() - 22)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = themes.current()
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setPen(QPen(to_color(palette["border"]), 1.0))
        painter.setBrush(to_color(palette["card"]))
        painter.drawRoundedRect(rect, 12, 12)
        color = palette.get(self.TONES.get(self._tone, self.TONES["info"])[1], palette["accent"])
        painter.setPen(Qt.NoPen)
        painter.setBrush(to_color(color))
        painter.drawRoundedRect(QRectF(0, 14, 3.5, self.height() - 28), 1.75, 1.75)


class EmptyState(QWidget):
    """空列表占位。"""

    def __init__(self, icon_name: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 18, 0, 18)
        layout.setSpacing(8)
        icon = IconView(icon_name, 34, "faint", 1.5)
        icon.setFixedSize(34, 34)
        layout.addWidget(icon, 0, Qt.AlignHCenter)
        title_label = make_label(title, "h3")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        sub = make_label(subtitle, "muted")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        layout.addWidget(sub)


class StatusPill(QFrame):
    """顶部状态胶囊。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = True
        self._paused = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 5, 14, 5)
        layout.setSpacing(0)
        self._label = make_label("防护中", "body")
        self._label.setStyleSheet("font-size: 9pt; font-weight: 600;")
        layout.addWidget(self._label)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = themes.current()
        if not self._enabled:
            color = palette["muted"]
        elif self._paused:
            color = palette["warning"]
        else:
            color = palette["success"]
        painter.setPen(Qt.NoPen)
        painter.setBrush(to_color(color))
        painter.drawEllipse(QRectF(14, self.height() / 2.0 - 4, 8, 8))

    def set_state(self, enabled: bool, paused: bool) -> None:
        self._enabled = enabled
        self._paused = paused
        if not enabled:
            text, tone = "防护已关闭", "muted"
        elif paused:
            text, tone = "已暂停", "warning"
        else:
            text, tone = "防护中", "success"
        self._label.setText(text)
        palette = themes.current()
        background = palette["success_soft"] if tone == "success" else (
            palette["warning_soft"] if tone == "warning" else palette["card_soft"])
        text_color = palette["success"] if tone == "success" else (
            palette["warning"] if tone == "warning" else palette["muted"])
        self.setStyleSheet(
            "QFrame { background: %s; border-radius: 12px; } QLabel { color: %s; background: transparent; }"
            % (background, text_color))
        self.update()


class StatCard(QFrame):
    """数据卡片：大数字 + 说明。"""

    def __init__(self, icon_name: str, title: str, value: str = "0", hint: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(IconView(icon_name, 16, "accent", 1.7))
        top.addWidget(make_label(title, "muted"))
        top.addStretch(1)
        layout.addLayout(top)
        self._value = make_label(value, "value")
        self._value.setStyleSheet("font-size: 21pt; font-weight: 700;")
        layout.addWidget(self._value)
        self._hint = make_label(hint, "faint")
        layout.addWidget(self._hint)
        self.setMinimumHeight(112)

    def set_value(self, value: str, hint: str = None) -> None:
        self._value.setText(str(value))
        if hint is not None:
            self._hint.setText(hint)
