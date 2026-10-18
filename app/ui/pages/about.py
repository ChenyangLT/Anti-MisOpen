# -*- coding: utf-8 -*-
"""关于页：版本、署名、原理说明和项目链接。"""
from __future__ import annotations

import platform

from PySide2.QtCore import Qt, QUrl
from PySide2.QtGui import QDesktopServices, QPainter, QPixmap
from PySide2.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from ...core import config, themes, winutil
from ..icons import icon_pixmap
from ..widgets import IconView, make_badge, make_label
from .base import PageBase, make_button


class LogoView(QWidget):
    """圆角方块中的应用图标。"""

    def __init__(self, size: int = 64, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = themes.current()
        from PySide2.QtCore import QRectF
        from ..icons import to_color
        painter.setPen(Qt.NoPen)
        painter.setBrush(to_color(palette["accent"]))
        painter.drawRoundedRect(QRectF(0, 0, self._size, self._size), 18, 18)
        painter.drawPixmap(QRectF(self._size * 0.2, self._size * 0.2,
                                  self._size * 0.6, self._size * 0.6),
                           icon_pixmap("shield", "#FFFFFF", int(self._size * 0.6), 2.0), QRectF())


class AboutPage(PageBase):
    def __init__(self, window):
        super().__init__(window)
        self._build()

    def _build(self) -> None:
        self.page_header("关于", "版本信息、工作原理和项目地址")
        self._build_hero()
        self._build_how()
        self._build_info()
        self.body.addStretch(1)

    def _build_hero(self) -> None:
        card = QFrame()
        card.setObjectName("Card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)

        layout.addWidget(LogoView(64), 0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(4)
        name = make_label("Anti MisOpen · 防误开", "h2")
        version = make_badge("v%s" % config.APP_VERSION, "accent")
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(name)
        row.addWidget(version)
        row.addStretch(1)
        col.addLayout(row)
        col.addWidget(make_label(
            "阻止同一个程序被反复双击后开出多个实例，避免电脑卡顿。"
            "适合教室、办公室等不熟悉电脑的使用环境。", "muted", wrap=True))
        signature = make_label(config.APP_SIGNATURE, "body")
        signature.setStyleSheet("font-weight: 600; color: %s;" % themes.current()["accent"])
        col.addSpacing(2)
        col.addWidget(signature)
        layout.addLayout(col, 1)
        self.body.addWidget(card)

    def _build_how(self) -> None:
        card, layout = self.card("它是怎么工作的")
        steps = [
            ("clock", "后台每 0.4 秒检查一次新出现的程序进程"),
            ("app", "当同一个程序在判定时间窗内被再次启动、且实例数超过上限时触发拦截"),
            ("ban", "按设置结束多余的进程，或只给出提醒"),
            ("shield", "例外名单、自定义规则和密码保护让设置更灵活"),
        ]
        for icon_name, text in steps:
            row = QHBoxLayout()
            row.setSpacing(10)
            row.addWidget(IconView(icon_name, 16, "accent", 1.7), 0, Qt.AlignTop)
            row.addWidget(make_label(text, "body", wrap=True), 1)
            layout.addLayout(row)
        self.body.addWidget(card)

    def _build_info(self) -> None:
        card, layout = self.card("运行环境与项目")
        rows = [
            ("系统", "%s%s" % (winutil.windows_label(),
                               " · 兼容模式" if winutil.is_win7() else "")),
            ("配置文件", config.config_path()),
            ("日志目录", config.log_dir()),
        ]
        for name, value in rows:
            row = QHBoxLayout()
            row.setSpacing(12)
            label = make_label(name, "muted")
            label.setFixedWidth(72)
            row.addWidget(label, 0, Qt.AlignTop)
            value_label = make_label(value, "faint", wrap=True)
            row.addWidget(value_label, 1)
            layout.addLayout(row)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        github = make_button("打开 GitHub 项目主页", "primary")
        github.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(config.GITHUB_URL)))
        buttons.addWidget(github)
        releases = make_button("下载最新版本", "ghost")
        releases.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(config.GITHUB_URL + "/releases")))
        buttons.addWidget(releases)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        note = make_label("本项目以 MIT 许可证开源，可自由用于教学和办公环境。"
                          "设置保存在当前用户目录，不需要管理员权限。", "faint", wrap=True)
        layout.addWidget(note)
        self.body.addWidget(card)
