# -*- coding: utf-8 -*-
"""页面基类与通用布局辅助。"""
from __future__ import annotations

from PySide2.QtCore import Qt
from PySide2.QtWidgets import (QFrame, QHBoxLayout, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from ...core import themes
from ..widgets import IconView, make_label


def clear_layout(layout) -> None:
    """移除布局里的全部条目；立刻解除父子关系，避免 deleteLater 之前留下残影。"""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
            continue
        child = item.layout()
        if child is not None:
            clear_layout(child)


def make_button(text: str, variant: str = "", icon: str = "") -> QPushButton:
    button = QPushButton(text)
    if variant:
        button.setProperty("variant", variant)
    button.setCursor(Qt.PointingHandCursor)
    return button


class PageBase(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.win = window
        self.store = window.store
        self.logbook = window.logbook

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        holder = QWidget()
        holder.setObjectName("PageBody")
        self.body = QVBoxLayout(holder)
        self.body.setContentsMargins(30, 18, 30, 28)
        self.body.setSpacing(16)
        scroll.setWidget(holder)
        scroll.viewport().setAutoFillBackground(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)
        self._scroll = scroll

    # ---------------------------------------------------------- 通用构件
    def page_header(self, title: str, subtitle: str, actions=None, badge=None):
        row = QHBoxLayout()
        row.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(make_label(title, "title"))
        titles.addWidget(make_label(subtitle, "subtitle"))
        row.addLayout(titles, 1)
        if badge is not None:
            row.addWidget(badge, 0, Qt.AlignVCenter)
        for widget in (actions or []):
            row.addWidget(widget, 0, Qt.AlignVCenter)
        self.body.addLayout(row)
        return row

    def card(self, title: str = None, subtitle: str = None, right=None):
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        if title:
            head = QHBoxLayout()
            head.setSpacing(10)
            titles = QVBoxLayout()
            titles.setSpacing(2)
            titles.addWidget(make_label(title, "h3"))
            if subtitle:
                titles.addWidget(make_label(subtitle, "muted", wrap=True))
            head.addLayout(titles, 1)
            if right is not None:
                head.addWidget(right, 0, Qt.AlignVCenter)
            layout.addLayout(head)
        return card, layout

    def setting_row(self, title: str, subtitle: str, control: QWidget):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(16)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        titles.addWidget(make_label(title, "body"))
        if subtitle:
            titles.addWidget(make_label(subtitle, "muted", wrap=True))
        layout.addLayout(titles, 1)
        layout.addWidget(control, 0, Qt.AlignVCenter)
        return widget

    def divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("Divider")
        line.setFrameShape(QFrame.NoFrame)
        line.setFixedHeight(1)
        return line

    def hint(self, text: str):
        label = make_label(text, "faint", wrap=True)
        self.body.addWidget(label)
        return label

    # ---------------------------------------------------------- 数据操作
    def persist(self, mapping: dict = None) -> None:
        if mapping:
            self.store.update(mapping)
        self.store.save()
        self.win.apply_config()

    def toast(self, text: str, tone: str = "success") -> None:
        self.win.show_toast(text, tone)
