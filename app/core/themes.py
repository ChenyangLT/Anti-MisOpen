# -*- coding: utf-8 -*-
"""主题配色与全局样式表。"""
from __future__ import annotations

from string import Template

from . import winutil

LIGHT_BLUE = {
    "key": "light_blue",
    "label": "浅色蓝",
    "dark": False,
    "bg": "#EDF2FA",
    "bg_soft": "#F6F9FE",
    "sidebar_top": "#152A52",
    "sidebar_bottom": "#20417D",
    "sidebar_text": "#A9BDDF",
    "sidebar_active_bg": "rgba(255, 255, 255, 30)",
    "sidebar_hover_bg": "rgba(255, 255, 255, 14)",
    "sidebar_active": "#FFFFFF",
    "card": "#FFFFFF",
    "card_soft": "#F5F8FE",
    "row_hover": "#F2F6FE",
    "border": "#E2E8F4",
    "border_strong": "#CBD7EC",
    "text": "#16223A",
    "muted": "#6B7B96",
    "faint": "#98A6BE",
    "accent": "#2F6BFF",
    "accent_hover": "#4C80FF",
    "accent_press": "#2358D8",
    "accent_soft": "#E8EFFF",
    "accent_text": "#FFFFFF",
    "success": "#129E68",
    "success_soft": "#E2F6ED",
    "warning": "#D98A0B",
    "warning_soft": "#FCF0D9",
    "danger": "#DD4A4A",
    "danger_soft": "#FCE8E8",
    "hero_a": "#2A5FE8",
    "hero_b": "#6C9BFF",
    "hero_text": "#FFFFFF",
    "hero_soft": "rgba(255, 255, 255, 46)",
    "switch_off": "#C3CEE1",
    "input_bg": "#F4F7FD",
    "shadow": "#C9D6EC",
}

DARK_NEON = {
    "key": "dark_neon",
    "label": "深色霓虹",
    "dark": True,
    "bg": "#090E1B",
    "bg_soft": "#0D1424",
    "sidebar_top": "#070B14",
    "sidebar_bottom": "#101B31",
    "sidebar_text": "#8296B8",
    "sidebar_active_bg": "rgba(92, 140, 255, 42)",
    "sidebar_hover_bg": "rgba(255, 255, 255, 10)",
    "sidebar_active": "#FFFFFF",
    "card": "#111A2B",
    "card_soft": "#0E1626",
    "row_hover": "#162136",
    "border": "#1E2B44",
    "border_strong": "#2B3C5C",
    "text": "#E8EEFC",
    "muted": "#8CA0C4",
    "faint": "#61739A",
    "accent": "#5C8CFF",
    "accent_hover": "#7BA4FF",
    "accent_press": "#3F6DDB",
    "accent_soft": "#17244A",
    "accent_text": "#FFFFFF",
    "success": "#2BD08A",
    "success_soft": "#0E2C22",
    "warning": "#F0B452",
    "warning_soft": "#2C2616",
    "danger": "#FF6B6B",
    "danger_soft": "#331A1E",
    "hero_a": "#20306B",
    "hero_b": "#3D5FC4",
    "hero_text": "#FFFFFF",
    "hero_soft": "rgba(255, 255, 255, 36)",
    "switch_off": "#33415C",
    "input_bg": "#0D1524",
    "shadow": "#050810",
}

LIGHT_GREEN = {
    "key": "light_green",
    "label": "护眼绿",
    "dark": False,
    "bg": "#EFF6F1",
    "bg_soft": "#F6FBF8",
    "sidebar_top": "#0D3327",
    "sidebar_bottom": "#175340",
    "sidebar_text": "#A6CBBE",
    "sidebar_active_bg": "rgba(255, 255, 255, 30)",
    "sidebar_hover_bg": "rgba(255, 255, 255, 14)",
    "sidebar_active": "#FFFFFF",
    "card": "#FFFFFF",
    "card_soft": "#F4FAF7",
    "row_hover": "#F1F9F5",
    "border": "#DDEBE2",
    "border_strong": "#C3DCCF",
    "text": "#14291F",
    "muted": "#63796F",
    "faint": "#93A99E",
    "accent": "#10A269",
    "accent_hover": "#1CB77B",
    "accent_press": "#0B8A59",
    "accent_soft": "#E1F5EC",
    "accent_text": "#FFFFFF",
    "success": "#10A269",
    "success_soft": "#E1F5EC",
    "warning": "#CF8A10",
    "warning_soft": "#FBF0D8",
    "danger": "#D8504B",
    "danger_soft": "#FBE9E8",
    "hero_a": "#0E8F5D",
    "hero_b": "#3FC98F",
    "hero_text": "#FFFFFF",
    "hero_soft": "rgba(255, 255, 255, 46)",
    "switch_off": "#BDD3C7",
    "input_bg": "#F2F9F5",
    "shadow": "#C8DFD2",
}

PALETTES = {
    "light_blue": LIGHT_BLUE,
    "dark_neon": DARK_NEON,
    "light_green": LIGHT_GREEN,
}

THEME_CHOICES = [
    ("light_blue", "浅色蓝", "明亮干净，适合教室大屏"),
    ("dark_neon", "深色霓虹", "低亮度，夜间不刺眼"),
    ("light_green", "护眼绿", "柔和的绿色调，久看不累"),
    ("system", "跟随系统", "随 Windows 深浅色设置切换"),
]

_current = LIGHT_BLUE


def resolve_key(key: str) -> str:
    if key == "system":
        return "dark_neon" if winutil.system_prefers_dark() else "light_blue"
    if key in PALETTES:
        return key
    return "light_blue"


def set_theme(key: str) -> dict:
    global _current
    _current = PALETTES[resolve_key(key)]
    return _current


def current() -> dict:
    return _current


def is_dark() -> bool:
    return bool(_current.get("dark"))


_TOUCH = {"enabled": False}


def set_touch(enabled: bool) -> None:
    """触屏模式：滚动条更宽、按钮更高，方便手指点按。"""
    _TOUCH["enabled"] = bool(enabled)


def touch_enabled() -> bool:
    return bool(_TOUCH["enabled"])


_QSS = Template("""
* { outline: none; }

QWidget {
    color: $text;
    font-size: 10pt;
}

QWidget#Root {
    background: $bg;
    border: 1px solid $border;
    border-radius: 18px;
}

QFrame#Sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
        stop:0 $sidebar_top, stop:1 $sidebar_bottom);
    border-top-left-radius: 17px;
    border-bottom-left-radius: 17px;
}

QWidget#Content, QWidget#PageBody, QStackedWidget, QScrollArea,
QScrollArea > QWidget#qt_scrollarea_viewport,
QScrollArea > QWidget > QWidget {
    background: transparent;
    border: none;
}

QLabel[role="title"]      { font-size: 20pt; font-weight: 700; color: $text; }
QLabel[role="subtitle"]   { font-size: 9.5pt; color: $muted; }
QLabel[role="h2"]         { font-size: 12pt; font-weight: 600; color: $text; }
QLabel[role="h3"]         { font-size: 10.5pt; font-weight: 600; color: $text; }
QLabel[role="body"]       { font-size: 9.5pt; color: $text; }
QLabel[role="muted"]      { font-size: 9pt; color: $muted; }
QLabel[role="faint"]      { font-size: 8.5pt; color: $faint; }
QLabel[role="value"]      { font-size: 23pt; font-weight: 700; color: $text; }
QLabel[role="sideTitle"]  { color: #FFFFFF; font-size: 12.5pt; font-weight: 600; }
QLabel[role="sideSub"]    { color: $sidebar_text; font-size: 8pt; }
QLabel[role="sideName"]   { color: #FFFFFF; font-size: 9.5pt; font-weight: 600; }
QLabel[role="sideModel"]  { color: $sidebar_text; font-size: 7.5pt; }
QLabel[role="heroTitle"]  { color: $hero_text; font-size: 17pt; font-weight: 700; }
QLabel[role="heroSub"]    { color: rgba(255, 255, 255, 215); font-size: 9.5pt; }
QLabel[role="heroMeta"]   { color: rgba(255, 255, 255, 165); font-size: 8.5pt; }
QLabel[role="wordmark"]   { color: $sidebar_text; font-size: 8pt; }

QFrame#Card {
    background: $card;
    border: 1px solid $border;
    border-radius: 14px;
}
QFrame#SoftCard {
    background: $card_soft;
    border: 1px solid $border;
    border-radius: 12px;
}
QFrame#DialogCard {
    background: $card;
    border: 1px solid $border;
    border-radius: 16px;
}
QFrame#Hero {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 $hero_a, stop:1 $hero_b);
    border-radius: 16px;
}
QFrame#Divider {
    background: $border;
    border: none;
    max-height: 1px;
    min-height: 1px;
}

QPushButton {
    background: $card;
    border: 1px solid $border;
    border-radius: 9px;
    padding: 8px 16px;
    min-height: $button_min;
    font-size: 9.5pt;
    font-weight: 500;
    color: $text;
}
QPushButton:hover  { border-color: $accent; color: $accent; }
QPushButton:pressed { background: $accent_soft; }
QPushButton:disabled { color: $faint; border-color: $border; }

QPushButton[variant="primary"] {
    background: $accent;
    border: 1px solid $accent;
    color: $accent_text;
}
QPushButton[variant="primary"]:hover   { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:pressed { background: $accent_press; border-color: $accent_press; }

QPushButton[variant="ghost"] {
    background: transparent;
    border: 1px solid transparent;
    color: $muted;
}
QPushButton[variant="ghost"]:hover { background: $accent_soft; color: $accent; }

QPushButton[variant="danger"] {
    background: transparent;
    border: 1px solid $border;
    color: $danger;
}
QPushButton[variant="danger"]:hover { background: $danger_soft; border-color: $danger; }

QPushButton[variant="link"] {
    background: transparent;
    border: none;
    color: $accent;
    padding: 2px 4px;
}
QPushButton[variant="link"]:hover { color: $accent_hover; }

QLineEdit {
    background: $input_bg;
    border: 1px solid $border;
    border-radius: 9px;
    padding: 8px 12px;
    color: $text;
    selection-background-color: $accent;
    selection-color: #FFFFFF;
}
QLineEdit:focus { border-color: $accent; background: $card; }

QListWidget {
    background: $card_soft;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 4px;
}
QListWidget::item {
    padding: 8px 10px;
    border-radius: 8px;
    color: $text;
}
QListWidget::item:hover { background: $row_hover; }
QListWidget::item:selected { background: $accent_soft; color: $accent; }

QComboBox {
    background: $input_bg;
    border: 1px solid $border;
    border-radius: 9px;
    padding: 7px 12px;
    color: $text;
}
QComboBox:hover { border-color: $border_strong; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: $card;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: $accent_soft;
    selection-color: $accent;
    outline: none;
}

QTextEdit {
    background: $input_bg;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 8px;
    color: $text;
}

QLabel#Badge {
    border-radius: 9px;
    padding: 2px 10px;
    font-size: 8.5pt;
    font-weight: 600;
}
QLabel#Badge[tone="success"] { background: $success_soft; color: $success; }
QLabel#Badge[tone="danger"]  { background: $danger_soft;  color: $danger; }
QLabel#Badge[tone="accent"]  { background: $accent_soft;  color: $accent; }
QLabel#Badge[tone="warning"] { background: $warning_soft; color: $warning; }
QLabel#Badge[tone="muted"]   { background: $card_soft;    color: $muted; }

QScrollArea { border: none; }
QScrollBar:vertical {
    background: transparent;
    width: $scroll_width;
    margin: 2px 2px 2px 0;
}
QScrollBar::handle:vertical {
    background: $border_strong;
    border-radius: $scroll_radius;
    min-height: $scroll_min;
}
QScrollBar::handle:vertical:hover { background: $faint; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: $scroll_width; }
QScrollBar::handle:horizontal { background: $border_strong; border-radius: $scroll_radius; min-width: $scroll_min; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

QMenu {
    background: $card;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 26px 7px 14px;
    border-radius: 6px;
    color: $text;
    font-size: 9.5pt;
}
QMenu::item:selected { background: $accent_soft; color: $accent; }
QMenu::separator { height: 1px; background: $border; margin: 5px 8px; }

QToolTip {
    background: #1B2436;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 9pt;
}

QDialog { background: $bg; }

QProgressBar {
    background: $card_soft;
    border: none;
    border-radius: 4px;
    max-height: 8px;
    min-height: 8px;
}
QProgressBar::chunk { background: $accent; border-radius: 4px; }

QSizeGrip { background: transparent; width: 14px; height: 14px; }
""")


def build_stylesheet(palette: dict = None) -> str:
    p = dict(palette or _current)
    if _TOUCH["enabled"]:
        p.update({"scroll_width": "16px", "scroll_radius": "7px",
                  "scroll_min": "44px", "button_min": "34px"})
    else:
        p.update({"scroll_width": "10px", "scroll_radius": "4px",
                  "scroll_min": "30px", "button_min": "0px"})
    return _QSS.substitute(p)


def qss() -> str:
    return build_stylesheet(_current)


def repolish(widget) -> None:
    """动态属性变化后刷新样式。"""
    try:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()
    except Exception:
        pass
