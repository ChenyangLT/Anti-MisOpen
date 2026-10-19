# -*- coding: utf-8 -*-
"""概览页：防护状态、今日数据、最近拦截。"""
from __future__ import annotations

import os
import time

import psutil
from PySide2.QtCore import Qt, QTimer
from PySide2.QtWidgets import (QFrame, QHBoxLayout, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from ...core import config, themes, winutil
from ..widgets import (CardRow, EmptyState, IconView, RingGauge, StatCard,
                       StatusPill, ToggleSwitch, make_badge, make_label)
from .base import PageBase, clear_layout, make_button


def human_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "%d 秒" % seconds
    minutes = seconds // 60
    if minutes < 60:
        return "%d 分钟" % minutes
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return "%d 小时 %d 分" % (hours, minutes)
    days, hours = divmod(hours, 24)
    return "%d 天 %d 小时" % (days, hours)


class DashboardPage(PageBase):
    def __init__(self, window):
        super().__init__(window)
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(1000)
        self._live_timer.timeout.connect(self._refresh_live)
        self._build()

    # ------------------------------------------------------------- 构建
    def _build(self) -> None:
        self._pill = StatusPill()
        self.page_header("概览", "阻止重复双击造成的程序多开，让电脑一直保持流畅",
                         badge=self._pill)
        self._build_hero()
        self._build_health()
        self._build_autostart_tip()
        self._build_stats()
        self._build_bottom()
        self.body.addStretch(1)
        self._recent_rows = []
        self.refresh()

    def _build_hero(self) -> None:
        hero = QFrame()
        hero.setObjectName("Hero")
        hero.setMinimumHeight(148)
        layout = QHBoxLayout(hero)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(20)

        left = QVBoxLayout()
        left.setSpacing(6)
        self._hero_title = make_label("防护已开启", "heroTitle")
        self._hero_sub = make_label("重复双击时只保留一个窗口，多余实例会被自动关闭", "heroSub", wrap=True)
        self._hero_detail = make_label("", "heroMeta")
        left.addWidget(self._hero_title)
        left.addWidget(self._hero_sub)
        left.addSpacing(2)
        left.addWidget(self._hero_detail)
        left.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self._pause_button = QPushButton("暂停防护")
        self._pause_button.setCursor(Qt.PointingHandCursor)
        self._pause_button.setStyleSheet(
            "QPushButton { color: #FFFFFF; background: rgba(255, 255, 255, 26);"
            " border: 1px solid rgba(255, 255, 255, 90); border-radius: 9px;"
            " padding: 7px 16px; font-size: 9.5pt; }"
            "QPushButton:hover { background: rgba(255, 255, 255, 46); }")
        self._pause_button.clicked.connect(self._on_pause)
        actions.addWidget(self._pause_button)
        self._log_button = QPushButton("拦截记录")
        self._log_button.setCursor(Qt.PointingHandCursor)
        self._log_button.setStyleSheet(
            "QPushButton { color: #FFFFFF; background: transparent;"
            " border: 1px solid rgba(255, 255, 255, 70); border-radius: 9px;"
            " padding: 7px 16px; font-size: 9.5pt; }"
            "QPushButton:hover { background: rgba(255, 255, 255, 30); }")
        self._log_button.clicked.connect(self._on_open_logs)
        actions.addWidget(self._log_button)
        self._clean_button = QPushButton("一键清理")
        self._clean_button.setCursor(Qt.PointingHandCursor)
        self._clean_button.setStyleSheet(
            "QPushButton { color: #1F54D8; background: rgba(255, 255, 255, 232);"
            " border: none; border-radius: 9px; padding: 7px 16px; font-size: 9.5pt;"
            " font-weight: 600; }"
            "QPushButton:hover { background: #FFFFFF; }")
        self._clean_button.clicked.connect(lambda: self.win.clean_memory_now("manual"))
        actions.addWidget(self._clean_button)
        actions.addStretch(1)
        left.addLayout(actions)
        layout.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.setAlignment(Qt.AlignCenter)
        self._switch = ToggleSwitch()
        self._switch.setToolTip("总开关")
        self._switch.installEventFilter(self.win)
        self._switch.toggled.connect(self._on_switch)
        right.addWidget(self._switch, 0, Qt.AlignHCenter)
        switch_label = make_label("总开关", "heroSub")
        switch_label.setAlignment(Qt.AlignCenter)
        right.addWidget(switch_label)
        layout.addLayout(right, 0)

        self.body.addWidget(hero)
        self._hero = hero

    def _build_health(self) -> None:
        clear_button = make_button("打开清理", "ghost")
        clear_button.clicked.connect(lambda: self.win.open_page(1))
        card, layout = self.card(
            "系统状态", "内存、CPU 与磁盘占用按比例显示，每秒刷新一次", right=clear_button)
        row = QHBoxLayout()
        row.setSpacing(8)
        specs = (
            ("cpu", "CPU 占用", "accent"),
            ("mem", "内存占用", "success"),
            ("disk", "磁盘占用", "warning"),
        )
        self._gauges = {}
        for key, label, color in specs:
            col = QVBoxLayout()
            col.setSpacing(6)
            col.setAlignment(Qt.AlignHCenter)
            gauge = RingGauge(label, color, 104)
            col.addWidget(gauge, 0, Qt.AlignHCenter)
            hint = make_label("正在读取…", "faint")
            hint.setAlignment(Qt.AlignCenter)
            col.addWidget(hint)
            row.addLayout(col, 1)
            self._gauges[key] = (gauge, hint)
        layout.addLayout(row)
        self.body.addWidget(card)
        self._prime_live()

    def _prime_live(self) -> None:
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

    def _refresh_live(self) -> None:
        if not hasattr(self, "_gauges"):
            return
        try:
            cpu = psutil.cpu_percent(interval=None)
            physical = psutil.cpu_count(logical=False) or 0
            logical = psutil.cpu_count(logical=True) or 0
            cpu_gauge, cpu_hint = self._gauges["cpu"]
            cpu_gauge.set_value(cpu)
            cpu_hint.setText("%d 核 %d 线程" % (physical, logical) if physical
                             else "%d 线程" % logical)

            memory = psutil.virtual_memory()
            mem_gauge, mem_hint = self._gauges["mem"]
            mem_gauge.set_value(memory.percent)
            mem_hint.setText("已用 %.1f / %.1f GB" % (
                (memory.total - memory.available) / float(1024 ** 3),
                memory.total / float(1024 ** 3)))

            drive = os.environ.get("SystemDrive", "C:") + "\\"
            usage = psutil.disk_usage(drive)
            disk_gauge, disk_hint = self._gauges["disk"]
            disk_gauge.set_value(usage.percent)
            disk_hint.setText("剩余 %.0f GB / %.0f GB" % (
                usage.free / float(1024 ** 3), usage.total / float(1024 ** 3)))
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._live_timer.start()
        QTimer.singleShot(120, self._refresh_live)

    def hideEvent(self, event):
        self._live_timer.stop()
        super().hideEvent(event)

    def _build_autostart_tip(self) -> None:
        self._tip = QFrame()
        self._tip.setObjectName("SoftCard")
        layout = QHBoxLayout(self._tip)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        icon = IconView("power", 18, "accent", 1.7)
        layout.addWidget(icon)
        text = make_label("建议开启开机自启动，让防护在每次开机后自动生效（默认关闭）", "muted", wrap=True)
        layout.addWidget(text, 1)
        button = make_button("去开启", "ghost")
        button.clicked.connect(lambda: self.win.open_page(5))
        layout.addWidget(button)
        self.body.addWidget(self._tip)

    def _build_stats(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(14)
        self._today_card = StatCard("ban", "今日拦截", "0", "从今天 0 点开始")
        self._total_card = StatCard("shield", "累计拦截", "0", "历史合计")
        self._time_card = StatCard("clock", "防护时长", "0 分钟", "累计运行时间")
        self._except_card = StatCard("grid", "例外程序", "0", "允许自由多开的程序")
        for card in (self._today_card, self._total_card, self._time_card, self._except_card):
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(card)
        self.body.addLayout(row)

    def _build_bottom(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(14)

        recent_card, recent_layout = self.card("最近拦截", "只展示最近 6 条记录")
        self._recent_layout = recent_layout
        self._recent_host = QWidget()
        self._recent_host_layout = QVBoxLayout(self._recent_host)
        self._recent_host_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_host_layout.setSpacing(2)
        recent_layout.addWidget(self._recent_host)
        row.addWidget(recent_card, 3)

        tips_card, tips_layout = self.card("使用提示")
        tips = [
            ("shield", "防护默认覆盖全部程序，只对例外名单里的程序放行。"),
            ("clock", "判定时间窗默认 5 秒，连续在这个时间内重复启动才会被拦截。"),
            ("key", "设置密码后，关闭防护、暂停防护或退出程序需要密码。"),
            ("info", "关闭窗口后会最小化到托盘，防护继续在后台运行。"),
        ]
        for icon_name, text in tips:
            item = QHBoxLayout()
            item.setSpacing(9)
            icon = IconView(icon_name, 15, "accent", 1.6)
            icon.setFixedSize(16, 16)
            item.addWidget(icon, 0, Qt.AlignTop)
            label = make_label(text, "muted", wrap=True)
            item.addWidget(label, 1)
            tips_layout.addLayout(item)
        tips_layout.addStretch(1)
        settings_button = make_button("打开设置", "ghost")
        settings_button.clicked.connect(lambda: self.win.open_page(5))
        tips_layout.addWidget(settings_button, 0, Qt.AlignRight)
        row.addWidget(tips_card, 2)

        self.body.addLayout(row)

    # ------------------------------------------------------------- 刷新
    def refresh(self) -> None:
        enabled = bool(self.store.get("enabled"))
        paused = self.store.is_paused()
        self._pill.set_state(enabled, paused)
        self._switch.blockSignals(True)
        self._switch.setChecked(enabled and not paused)
        self._switch.blockSignals(False)
        self._switch.setEnabled(True)

        if not enabled:
            self._hero_title.setText("防护已关闭")
            self._hero_sub.setText("当前不会拦截任何重复启动，建议重新开启")
        elif paused:
            self._hero_title.setText("防护已暂停")
            self._hero_sub.setText("暂停期间不会拦截任何程序，恢复后自动继续保护")
        else:
            self._hero_title.setText("防护已开启")
            self._hero_sub.setText("重复双击时只保留一个窗口，多余实例会被自动关闭")

        stats = self.store.touch_stats()
        total = int(stats.get("total_blocked") or 0)
        today = int(stats.get("today_blocked") or 0)
        protected = float(stats.get("protected_seconds") or 0)
        exceptions = self.store.get("exceptions") or []
        self._today_card.set_value(str(today))
        self._total_card.set_value(str(total))
        self._time_card.set_value(human_duration(protected),
                                  "自首次运行累计" if protected else "刚刚开始防护")
        self._except_card.set_value(str(len(exceptions)))
        self._hero_detail.setText("今天已拦截 %d 次 · 累计拦截 %d 次 · 已保护 %s"
                                  % (today, total, human_duration(protected)))

        pause_until = float(self.store.get("paused_until") or 0)
        if paused and pause_until > time.time() and pause_until < time.time() + 86400 * 30:
            self._pause_button.setText("恢复防护")
        else:
            self._pause_button.setText("暂停防护")

        self._tip.setVisible(not bool(self.store.get("autostart")))
        self._refresh_live()
        self._refresh_recent()

    def _refresh_recent(self) -> None:
        clear_layout(self._recent_host_layout)
        entries = self.logbook.recent(6)
        if not entries:
            empty = EmptyState("check", "暂时没有拦截记录", "防护运行中，重复双击会被自动拦截")
            self._recent_host_layout.addWidget(empty)
            return
        for entry in entries:
            row = CardRow()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(10, 8, 10, 8)
            layout.setSpacing(10)
            layout.addWidget(IconView("ban", 16, "danger", 1.7), 0, Qt.AlignTop)

            col = QVBoxLayout()
            col.setSpacing(2)
            name = str(entry.get("name") or "未知程序")
            col.addWidget(make_label(name, "body"))
            reason = str(entry.get("reason") or "")
            col.addWidget(make_label(reason, "faint", wrap=True))
            layout.addLayout(col, 1)

            killed = entry.get("killed")
            tone = "success" if killed else "muted"
            badge = make_badge("已关闭" if killed else "已提示", tone)
            layout.addWidget(badge, 0, Qt.AlignTop)

            stamp = str(entry.get("time") or "")
            time_label = make_label(stamp[11:16] if len(stamp) >= 16 else stamp, "faint")
            layout.addWidget(time_label, 0, Qt.AlignTop)
            self._recent_host_layout.addWidget(row)

    # ------------------------------------------------------------- 交互
    def _on_switch(self, checked: bool) -> None:
        if not checked and self.store.get("password"):
            if not self.win.require_password("关闭防护需要密码"):
                self.refresh()
                return
        self.persist({"enabled": checked})
        self.refresh()
        self.win.show_toast("防护已开启" if checked else "防护已关闭",
                            "success" if checked else "warning")

    def _on_pause(self) -> None:
        paused = self.store.is_paused()
        if paused:
            self.persist({"paused_until": 0})
            self.toast("防护已恢复", "success")
        else:
            from ..dialogs import PauseDialog
            dialog = PauseDialog(self.win)
            if dialog.exec_() != dialog.Accepted:
                return
            seconds = dialog.result_seconds
            import time as _time
            until = 0 if seconds == -1 else _time.time() + seconds
            if seconds == -1:
                until = _time.time() + 86400 * 365
            self.persist({"paused_until": until})
            self.toast("已暂停防护", "warning")
        self.refresh()

    def _on_open_logs(self) -> None:
        self.win.open_logs()
