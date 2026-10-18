# -*- coding: utf-8 -*-
"""清理页：一键释放内存、阈值自动清理、查看内存占用最高的程序。"""
from __future__ import annotations

import time

import psutil
from PySide2.QtCore import Qt, QTimer
from PySide2.QtWidgets import (QFrame, QHBoxLayout, QProgressBar, QSizePolicy,
                               QVBoxLayout, QWidget)

from ...core import cleaner
from ..widgets import (SegmentedControl, StatCard, Stepper, ToggleSwitch,
                       make_label)
from .base import PageBase, clear_layout, make_button


class CleanerPage(PageBase):
    def __init__(self, window):
        super().__init__(window)
        self._tick = 0
        self._build()
        self._timer = QTimer(self)
        self._timer.setInterval(2500)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()
        self.refresh()

    # ------------------------------------------------------------- 构建
    def _build(self) -> None:
        self._clean_button = make_button("一键清理", "primary")
        self._clean_button.clicked.connect(lambda: self.win.clean_memory_now("manual"))
        self.page_header(
            "清理与性能",
            "参考 PCL2 与 Mem Reduct 的清理思路：只释放内存，不会关闭任何软件",
            actions=[self._clean_button])

        self._build_stats()
        self._build_status()
        self._build_auto()
        self._build_top()
        self.hint("清理会暂时让不活跃的进程把内存交还系统；正在使用的程序会按需重新载入，不会丢数据，"
                  "也不会被关闭。深度清理可以额外释放系统缓存，但需要以管理员身份运行。")
        self.body.addStretch(1)

    def _build_stats(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(14)
        self._mem_card = StatCard("grid", "内存占用", "0%", "已用 0 / 0")
        self._cpu_card = StatCard("clock", "CPU 占用", "0%", "全系统平均")
        self._free_card = StatCard("refresh", "累计释放", "0 MB", "自使用清理功能以来")
        for card in (self._mem_card, self._cpu_card, self._free_card):
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(card)
        self.body.addLayout(row)

    def _build_status(self) -> None:
        card, layout = self.card("内存状态", "把不活跃进程的工作集交还系统，立刻腾出可用内存")
        row = QHBoxLayout()
        row.setSpacing(22)

        left = QVBoxLayout()
        left.setSpacing(7)
        self._percent_label = make_label("0%", "value")
        self._percent_label.setStyleSheet("font-size: 26pt; font-weight: 700;")
        left.addWidget(self._percent_label)
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self._bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        left.addWidget(self._bar)
        self._status_hint = make_label("", "muted")
        left.addWidget(self._status_hint)
        row.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(6)
        right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._last_label = make_label("还没有清理过", "muted")
        self._last_label.setAlignment(Qt.AlignRight)
        right.addWidget(self._last_label)
        self._clean_hint = make_label("标准清理 · 约 1 秒", "faint")
        self._clean_hint.setAlignment(Qt.AlignRight)
        right.addWidget(self._clean_hint)
        row.addLayout(right, 0)
        layout.addLayout(row)
        self.body.addWidget(card)

    def _build_auto(self) -> None:
        card, layout = self.card("自动清理", "内存占用达到阈值时自动清理，和 Mem Reduct 的阈值触发一样")
        self._auto_switch = ToggleSwitch()
        self._auto_switch.toggled.connect(self._on_auto)
        layout.addWidget(self.setting_row(
            "启用自动清理", "关闭时只在你点击“一键清理”时释放内存", self._auto_switch))
        layout.addWidget(self.divider())

        self._threshold = Stepper(85.0, 50.0, 95.0, 5.0, 0, " %")
        self._threshold.valueChanged.connect(self._on_threshold)
        layout.addWidget(self.setting_row(
            "内存占用阈值", "达到这个百分比后触发一次自动清理", self._threshold))
        layout.addWidget(self.divider())

        self._mode = SegmentedControl(
            [("standard", "标准清理"), ("deep", "深度清理（需管理员）")], "standard")
        self._mode.changed.connect(self._on_mode)
        layout.addWidget(self.setting_row(
            "清理方式", "标准清理不需要管理员；深度清理会额外清空系统缓存", self._mode))
        layout.addWidget(self.divider())

        self._notify_switch = ToggleSwitch()
        self._notify_switch.toggled.connect(self._on_notify)
        layout.addWidget(self.setting_row(
            "自动清理后提示", "在窗口内显示一条轻提示，告诉你释放了多少内存",
            self._notify_switch))
        self.body.addWidget(card)

    def _build_top(self) -> None:
        card, layout = self.card("占用内存最多的程序", "清理后会按需重新载入，不会被关闭")
        self._top_host = QWidget()
        self._top_layout = QVBoxLayout(self._top_host)
        self._top_layout.setContentsMargins(0, 0, 0, 0)
        self._top_layout.setSpacing(2)
        layout.addWidget(self._top_host)
        self.body.addWidget(card)

    # ------------------------------------------------------------- 事件
    def _on_auto(self, checked: bool) -> None:
        self.persist({"memory_auto": bool(checked)})
        self.toast("已开启自动清理" if checked else "已关闭自动清理")

    def _on_threshold(self, value: float) -> None:
        self.persist({"memory_threshold": int(value)})

    def _on_mode(self, key: str) -> None:
        self.persist({"memory_deep": key == "deep"})
        self._sync_mode_label()

    def _on_notify(self, checked: bool) -> None:
        self.persist({"memory_auto_notify": bool(checked)})

    # ------------------------------------------------------------- 刷新
    def _sync_mode_label(self) -> None:
        deep = bool(self.store.get("memory_deep"))
        self._clean_hint.setText("深度清理 · 需要管理员权限" if deep else "标准清理 · 约 1 秒")

    def refresh(self) -> None:
        self._auto_switch.blockSignals(True)
        self._auto_switch.setChecked(bool(self.store.get("memory_auto")))
        self._auto_switch.blockSignals(False)

        self._threshold.blockSignals(True)
        self._threshold.setValue(float(self.store.get("memory_threshold") or 85))
        self._threshold.blockSignals(False)

        self._mode.blockSignals(True)
        self._mode.setValue("deep" if self.store.get("memory_deep") else "standard")
        self._mode.blockSignals(False)

        self._notify_switch.blockSignals(True)
        self._notify_switch.setChecked(bool(self.store.get("memory_auto_notify")))
        self._notify_switch.blockSignals(False)

        self._sync_mode_label()
        self._refresh_last()
        self.refresh_live(update_top=True)

    def _refresh_last(self) -> None:
        last = float(self.store.get("memory_last_cleanup") or 0)
        if last <= 0:
            self._last_label.setText("还没有清理过")
            return
        freed = int(self.store.get("memory_last_freed") or 0)
        when = time.strftime("%m-%d %H:%M", time.localtime(last))
        self._last_label.setText("上次清理：%s · 释放 %s" % (when, cleaner.format_bytes(freed)))

    def refresh_live(self, update_top: bool = False) -> None:
        memory = cleaner.memory_snapshot()
        self._percent_label.setText("%d%%" % int(round(memory["percent"])))
        self._bar.setValue(int(round(memory["percent"])))
        self._status_hint.setText("已用 %s / 共 %s" % (
            cleaner.format_bytes(memory["used"]), cleaner.format_bytes(memory["total"])))
        self._mem_card.set_value("%d%%" % int(round(memory["percent"])),
                                 "已用 %s / 共 %s" % (cleaner.format_bytes(memory["used"]),
                                                     cleaner.format_bytes(memory["total"])))
        try:
            cpu = psutil.cpu_percent(interval=None)
        except Exception:
            cpu = 0.0
        self._cpu_card.set_value("%d%%" % int(round(cpu)), "全系统平均")
        total_freed = int(self.store.get("memory_total_freed") or 0)
        self._free_card.set_value(cleaner.format_bytes(total_freed), "自使用清理功能以来")
        self._refresh_last()
        if update_top:
            self._refresh_top()

    def _refresh_top(self) -> None:
        clear_layout(self._top_layout)
        try:
            items = cleaner.top_processes(6)
        except Exception:
            items = []
        if not items:
            self._top_layout.addWidget(make_label("暂时无法读取进程信息", "muted"))
            return
        for item in items:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 5, 0, 5)
            layout.setSpacing(10)
            layout.addWidget(make_label(item["name"], "body"), 1)
            layout.addWidget(make_label("PID %d" % item["pid"], "faint"), 0)
            layout.addWidget(make_label(cleaner.format_bytes(item["rss"]), "body"), 0)
            self._top_layout.addWidget(row)

    def _on_tick(self) -> None:
        if not self.isVisible():
            return
        self._tick += 1
        self.refresh_live(update_top=(self._tick % 3 == 0))
