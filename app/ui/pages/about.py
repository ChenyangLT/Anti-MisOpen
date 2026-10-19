# -*- coding: utf-8 -*-
"""关于页：版本、署名、原理说明和项目链接。"""
from __future__ import annotations

import os
import platform
import time

from PySide2.QtCore import Qt, QUrl
from PySide2.QtGui import QDesktopServices, QPainter, QPixmap
from PySide2.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from ...core import config, hardware, profile, themes, winutil
from ..hardware_worker import HardwareThread
from ..icons import icon_pixmap
from ..widgets import AvatarView, IconView, make_badge, make_label
from .base import PageBase, clear_layout, make_button


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
        self._hw_thread = None
        self._hw_started = False
        self._build()

    def _build(self) -> None:
        self.page_header("关于", "版本信息、硬件信息、工作原理和项目地址")
        self._build_hero()
        self._build_how()
        self._build_hardware()
        self._build_info()
        self.body.addStretch(1)

    # ------------------------------------------------------------ 硬件信息
    def _build_hardware(self) -> None:
        self._hw_refresh = make_button("重新读取", "ghost")
        self._hw_refresh.clicked.connect(lambda: self.refresh_hardware(force=True))
        card, layout = self.card(
            "硬件信息",
            "自动读取处理器、主板、内存、显卡、硬盘与网络等设备信息（只读，不会修改系统设置）",
            right=self._hw_refresh)
        self._hw_status = make_label("正在读取硬件信息…", "muted", wrap=True)
        layout.addWidget(self._hw_status)
        self._hw_host = QWidget()
        self._hw_layout = QVBoxLayout(self._hw_host)
        self._hw_layout.setContentsMargins(0, 0, 0, 0)
        self._hw_layout.setSpacing(8)
        layout.addWidget(self._hw_host)
        self.body.addWidget(card)

    def showEvent(self, event):
        super().showEvent(event)
        if self._hw_started:
            return
        self._hw_started = True
        cached = hardware.load_cache()
        if cached and cached.get("groups"):
            self._render_hardware(cached, cached=True)
        self.refresh_hardware()

    def refresh_hardware(self, force: bool = False) -> None:
        try:
            if self._hw_thread is not None and self._hw_thread.isRunning():
                return
        except RuntimeError:
            self._hw_thread = None
        if force or not self._hw_host.layout().count():
            self._hw_status.setText("正在重新读取硬件信息，首次可能需要几秒钟…")
        self._hw_refresh.setEnabled(False)
        self._hw_thread = HardwareThread(self)
        self._hw_thread.finished_data.connect(self._render_hardware)
        self._hw_thread.finished.connect(lambda: self._hw_refresh.setEnabled(True))
        self._hw_thread.start()

    def _render_hardware(self, data: dict, cached: bool = False) -> None:
        groups = data.get("groups") or []
        if not groups:
            self._hw_status.setText(
                "暂时没有读到硬件信息，可能是系统 WMI 服务不可用。"
                "可以点击右上角「重新读取」再试一次。")
            return
        clear_layout(self._hw_layout)
        for index, group in enumerate(groups):
            title = make_label(str(group.get("title") or "硬件"), "h3")
            self._hw_layout.addWidget(title)
            for name, value in group.get("rows") or []:
                row = QHBoxLayout()
                row.setSpacing(12)
                label = make_label(str(name), "muted")
                label.setFixedWidth(104)
                row.addWidget(label, 0, Qt.AlignTop)
                row.addWidget(make_label(str(value), "faint", wrap=True), 1)
                self._hw_layout.addLayout(row)
            if index != len(groups) - 1:
                self._hw_layout.addWidget(self.divider())
        stamp = data.get("generated_at") or 0
        text = "已读取 %d 项设备信息" % len(groups)
        if stamp:
            text += " · 更新于 " + time.strftime("%H:%M:%S", time.localtime(stamp))
        if cached:
            text += " · 缓存"
        self._hw_status.setText(text)

    def wait_hardware(self, timeout: int = 4000) -> None:
        try:
            if self._hw_thread is not None and self._hw_thread.isRunning():
                self._hw_thread.wait(timeout)
        except Exception:
            pass

    def _build_hero(self) -> None:
        card = QFrame()
        card.setObjectName("Card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(18)

        self._avatar_view = AvatarView(64, "CY")
        layout.addWidget(self._avatar_view, 0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(10)
        self._hero_name = make_label(profile.LOGIN, "h2")
        row.addWidget(self._hero_name)
        row.addWidget(make_badge("v%s" % config.APP_VERSION, "accent"))
        row.addStretch(1)
        self._avatar_refresh = make_button("刷新头像", "ghost")
        self._avatar_refresh.clicked.connect(lambda: self.win.refresh_avatar(True))
        row.addWidget(self._avatar_refresh, 0, Qt.AlignTop)
        col.addLayout(row)

        model = make_label(profile.MODEL + " 制作", "body")
        model.setStyleSheet("font-weight: 600; color: %s;" % themes.current()["accent"])
        col.addWidget(model)
        col.addWidget(make_label(
            "阻止同一个程序被反复双击后开出多个实例，避免电脑卡顿。"
            "适合教室、办公室等不熟悉电脑的使用环境。", "muted", wrap=True))

        self._avatar_status = make_label("正在获取 GitHub 头像…", "faint", wrap=True)
        col.addSpacing(2)
        col.addWidget(self._avatar_status)
        layout.addLayout(col, 1)
        self.body.addWidget(card)

    def set_avatar(self, result: dict) -> None:
        """由主窗口在后台取到头像后调用。"""
        result = result or {}
        data = result.get("data")
        if data:
            self._avatar_view.set_image_data(data)
        self._avatar_status.setText(profile.source_text(result))
        self._avatar_refresh.setEnabled(True)
        if result.get("ok") and not result.get("cached"):
            self.win.show_toast("已更新 GitHub 头像与作者信息", "success")

    def _build_how(self) -> None:
        card, layout = self.card("它是怎么工作的")
        steps = [
            ("clock", "后台每 0.2 秒检查一次新出现的程序进程"),
            ("app", "智能识别启动方式：快捷方式、桌面整理软件启动的程序同样会被判定"),
            ("ban", "当同一个程序在判定时间窗内被再次启动、且实例数超过上限时触发拦截"),
            ("trash", "垃圾清理：回收站、临时文件、下载、图片、视频定期清一清"),
            ("shield", "例外名单、自定义规则、通知修复和密码保护让设置更灵活"),
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
