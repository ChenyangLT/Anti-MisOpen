# -*- coding: utf-8 -*-
"""例外名单页：这些程序可以正常多开。"""
from __future__ import annotations

import os

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ...core import config
from ..dialogs import AddTargetDialog, ProcessPickerDialog, ConfirmDialog
from ..widgets import (CardRow, EmptyState, IconView, make_badge, make_label)
from .base import PageBase, clear_layout, make_button

DEFAULT_EXCEPTIONS = list(config.DEFAULT_CONFIG["exceptions"])


class ExceptionsPage(PageBase):
    def __init__(self, window):
        super().__init__(window)
        self._build()
        self.refresh()

    def _build(self) -> None:
        add_button = make_button("添加例外", "primary")
        add_button.clicked.connect(self._add_exception)
        self.page_header("例外名单", "名单里的程序不会被拦截，可以放心多开",
                         actions=[add_button])

        card, layout = self.card(
            "允许自由多开的程序",
            "按照程序名匹配最省事；同名程序较多时，建议用完整路径匹配")
        self._host = QWidget()
        self._host_layout = QVBoxLayout(self._host)
        self._host_layout.setContentsMargins(0, 0, 0, 0)
        self._host_layout.setSpacing(2)
        layout.addWidget(self._host)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        pick_button = make_button("从正在运行的程序添加", "ghost")
        pick_button.clicked.connect(self._pick_exception)
        footer.addWidget(pick_button)
        restore_button = make_button("恢复默认名单", "ghost")
        restore_button.clicked.connect(self._restore_defaults)
        footer.addWidget(restore_button)
        footer.addStretch(1)
        layout.addLayout(footer)
        self.body.addWidget(card)

        self.hint("提示：列表里的程序只是“不拦截”，不会被自动启动或关闭。"
                  "默认已加入资源管理器（explorer.exe），避免文件夹窗口被误关。")
        self.body.addStretch(1)

    # ------------------------------------------------------------- 刷新
    def refresh(self) -> None:
        clear_layout(self._host_layout)
        exceptions = self.store.get("exceptions") or []
        if not exceptions:
            self._host_layout.addWidget(EmptyState(
                "check", "例外名单是空的", "所有程序都会被防护，重复双击会被拦截"))
            return
        for index, item in enumerate(exceptions):
            self._host_layout.addWidget(self._make_row(index, item))

    def _make_row(self, index: int, item: dict) -> QWidget:
        row = CardRow()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(10)
        layout.addWidget(IconView("check", 17, "success", 2.0), 0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(3)
        value = str(item.get("value") or "")
        name_label = make_label(value, "body")
        name_label.setToolTip(value)
        col.addWidget(name_label)
        badges = QHBoxLayout()
        badges.setSpacing(6)
        kind = str(item.get("kind") or "name")
        badges.addWidget(make_badge("按完整路径" if kind == "path" else "按程序名", "success"),
                         0, Qt.AlignLeft)
        note = str(item.get("note") or "")
        if note:
            badges.addWidget(make_label(note, "faint"), 0, Qt.AlignLeft)
        badges.addStretch(1)
        col.addLayout(badges)
        layout.addLayout(col, 1)

        remove = make_button("移除", "ghost")
        remove.clicked.connect(lambda _checked=False, i=index: self._remove(i))
        layout.addWidget(remove, 0, Qt.AlignVCenter)
        return row

    # ------------------------------------------------------------- 交互
    def _add_exception(self) -> None:
        dialog = AddTargetDialog(self.win, mode="exception")
        if dialog.exec_() != dialog.Accepted or not dialog.result_data:
            return
        self._append(dialog.result_data)

    def _pick_exception(self) -> None:
        dialog = ProcessPickerDialog(self.win, "添加例外", "选择要允许自由多开的程序")
        if dialog.exec_() != dialog.Accepted or not dialog.selected:
            return
        exe, name = dialog.selected
        self._append({"kind": "path", "value": exe, "note": name})

    def _append(self, data: dict) -> None:
        exceptions = list(self.store.get("exceptions") or [])
        value = str(data.get("value") or "")
        kind = str(data.get("kind") or "name")
        if not value:
            return
        for item in exceptions:
            if item.get("value") == value and item.get("kind") == kind:
                self.toast("这个程序已经在例外名单里了", "warning")
                return
        exceptions.append({"kind": kind, "value": value, "note": data.get("note", "")})
        self.persist({"exceptions": exceptions})
        self.refresh()
        self.toast("已加入例外名单", "success")

    def _remove(self, index: int) -> None:
        exceptions = list(self.store.get("exceptions") or [])
        if index < 0 or index >= len(exceptions):
            return
        item = exceptions[index]
        dialog = ConfirmDialog(self.win, "移除例外",
                               "移除“%s”后，它会被重新纳入防护，确定吗？" % (item.get("value") or ""),
                               ok_text="移除", danger=True)
        if dialog.exec_() != dialog.Accepted:
            return
        exceptions.pop(index)
        self.persist({"exceptions": exceptions})
        self.refresh()
        self.toast("已从例外名单移除", "warning")

    def _restore_defaults(self) -> None:
        dialog = ConfirmDialog(self.win, "恢复默认名单",
                               "会覆盖当前的例外名单，恢复为默认的资源管理器例外。",
                               ok_text="恢复", danger=True)
        if dialog.exec_() != dialog.Accepted:
            return
        self.persist({"exceptions": list(DEFAULT_EXCEPTIONS)})
        self.refresh()
        self.toast("已恢复默认例外名单", "success")
