# -*- coding: utf-8 -*-
"""规则与强度页：判定参数、处理方式、自定义规则。"""
from __future__ import annotations

from PySide2.QtCore import Qt
from PySide2.QtWidgets import (QFrame, QHBoxLayout, QPushButton, QVBoxLayout,
                               QWidget)

from ...core import config, themes
from ..dialogs import AddTargetDialog, ConfirmDialog
from ..widgets import (CardRow, EmptyState, IconView, SegmentedControl,
                       Stepper, ToggleSwitch, make_badge, make_label)
from .base import PageBase, clear_layout, make_button

ACTION_LABELS = dict(config.ACTIONS)
ACTION_LABELS["inherit"] = "跟随全局"


class RulesPage(PageBase):
    def __init__(self, window):
        super().__init__(window)
        self._build()
        self.refresh()

    def _build(self) -> None:
        self.page_header("规则与强度", "决定什么情况算“重复启动”，以及多余实例怎么处理")
        self._build_basic()
        self._build_extra()
        self._build_rules()
        self.body.addStretch(1)

    def _build_basic(self) -> None:
        card, layout = self.card("基础判定", "对全部程序生效，自定义规则可以单独覆盖")

        self._enabled_switch = ToggleSwitch()
        self._enabled_switch.toggled.connect(self._on_enabled)
        layout.addWidget(self.setting_row(
            "启用防护", "关闭后不再拦截任何重复启动", self._enabled_switch))
        layout.addWidget(self.divider())

        self._window_stepper = Stepper(5.0, 1.0, 60.0, 1.0, 0, " 秒")
        self._window_stepper.valueChanged.connect(self._on_window)
        layout.addWidget(self.setting_row(
            "判定时间窗", "同一个程序在这段时间内被再次启动，算作“重复双击”",
            self._window_stepper))
        layout.addWidget(self.divider())

        self._max_stepper = Stepper(1.0, 1.0, 20.0, 1.0, 0, " 个")
        self._max_stepper.valueChanged.connect(self._on_max)
        layout.addWidget(self.setting_row(
            "允许的实例数量", "超过这个数量的新实例会被处理，默认只允许 1 个",
            self._max_stepper))
        layout.addWidget(self.divider())

        self._action = SegmentedControl(
            [("kill_silent", "静默结束"), ("kill_notify", "结束并提示"),
             ("notify_only", "只提示")], "kill_notify")
        self._action.changed.connect(self._on_action)
        layout.addWidget(self.setting_row(
            "处理方式", "静默结束最不打扰；只提示则不会关闭任何程序", self._action))
        self.body.addWidget(card)

    def _build_extra(self) -> None:
        card, layout = self.card("附加行为")

        self._always_switch = ToggleSwitch()
        self._always_switch.toggled.connect(self._on_always)
        layout.addWidget(self.setting_row(
            "总是执行实例上限", "开启后只要实例数超过上限就拦截；关闭时只在短时间内连续启动才拦截",
            self._always_switch))
        layout.addWidget(self.divider())

        self._focus_switch = ToggleSwitch()
        self._focus_switch.toggled.connect(self._on_focus)
        layout.addWidget(self.setting_row(
            "结束后切换到已有窗口", "让用户感觉程序已经打开，减少反复点击", self._focus_switch))
        layout.addWidget(self.divider())

        self._notify_switch = ToggleSwitch()
        self._notify_switch.toggled.connect(self._on_notify)
        layout.addWidget(self.setting_row(
            "在桌面弹出提示", "拦截时在托盘弹出气泡提醒，便于知道发生了什么",
            self._notify_switch))
        self.body.addWidget(card)

    def _build_rules(self) -> None:
        add_button = make_button("添加规则", "primary")
        add_button.clicked.connect(self._add_rule)
        card, layout = self.card(
            "自定义规则", "为某个程序单独设置时间窗、实例上限或处理方式", right=add_button)
        self._rules_host = QWidget()
        self._rules_layout = QVBoxLayout(self._rules_host)
        self._rules_layout.setContentsMargins(0, 0, 0, 0)
        self._rules_layout.setSpacing(2)
        layout.addWidget(self._rules_host)
        self.body.addWidget(card)

    # ------------------------------------------------------------- 刷新
    def refresh(self) -> None:
        store = self.store
        self._enabled_switch.blockSignals(True)
        self._enabled_switch.setChecked(bool(store.get("enabled")))
        self._enabled_switch.blockSignals(False)

        self._window_stepper.setValue(float(store.get("window_seconds") or 5.0))
        self._max_stepper.setValue(float(store.get("max_instances") or 1))

        action = str(store.get("action") or "kill_notify")
        if action not in ("kill_silent", "kill_notify", "notify_only"):
            action = "kill_notify"
        self._action.setValue(action)

        for switch, key in ((self._always_switch, "always_enforce_max"),
                            (self._focus_switch, "focus_existing"),
                            (self._notify_switch, "notify")):
            switch.blockSignals(True)
            switch.setChecked(bool(store.get(key)))
            switch.blockSignals(False)

        self._refresh_rules()

    def _refresh_rules(self) -> None:
        clear_layout(self._rules_layout)
        rules = self.store.get("rules") or []
        if not rules:
            self._rules_layout.addWidget(EmptyState(
                "sliders", "还没有自定义规则",
                "直接点右上角“添加规则”，为某个程序单独设置参数"))
            return
        for index, rule in enumerate(rules):
            self._rules_layout.addWidget(self._make_rule_row(index, rule))

    def _make_rule_row(self, index: int, rule: dict) -> QWidget:
        matcher = rule.get("matcher") or {}
        row = CardRow()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(10)
        layout.addWidget(IconView("sliders", 17, "accent", 1.7), 0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(3)
        value = str(matcher.get("value") or "")
        kind = str(matcher.get("kind") or "name")
        title = make_label(value, "body")
        title.setToolTip(value)
        col.addWidget(title)

        badges = QHBoxLayout()
        badges.setSpacing(6)
        badges.addWidget(make_badge("按路径" if kind == "path" else "按名称", "accent"), 0, Qt.AlignLeft)
        window = rule.get("window_seconds")
        if window is not None:
            badges.addWidget(make_badge("%.0f 秒内" % float(window), "muted"), 0, Qt.AlignLeft)
        maximum = rule.get("max_instances")
        if maximum is not None:
            badges.addWidget(make_badge("上限 %d 个" % int(maximum), "muted"), 0, Qt.AlignLeft)
        action = rule.get("action")
        if action:
            badges.addWidget(make_badge(ACTION_LABELS.get(action, str(action)), "success"), 0, Qt.AlignLeft)
        badges.addStretch(1)
        col.addLayout(badges)
        note = str(rule.get("note") or "")
        if note:
            col.addWidget(make_label(note, "faint"))
        layout.addLayout(col, 1)

        remove = make_button("删除", "ghost")
        remove.clicked.connect(lambda _checked=False, i=index: self._remove_rule(i))
        layout.addWidget(remove, 0, Qt.AlignVCenter)
        return row

    # ------------------------------------------------------------- 交互
    def _on_enabled(self, checked: bool) -> None:
        if not checked and self.store.get("password"):
            if not self.win.require_password("关闭防护需要密码"):
                self.refresh()
                return
        self.persist({"enabled": checked})
        self.refresh()

    def _on_window(self, value: float) -> None:
        self.persist({"window_seconds": float(value)})

    def _on_max(self, value: float) -> None:
        self.persist({"max_instances": int(value)})

    def _on_action(self, value: str) -> None:
        self.persist({"action": str(value)})

    def _on_always(self, checked: bool) -> None:
        self.persist({"always_enforce_max": bool(checked)})

    def _on_focus(self, checked: bool) -> None:
        self.persist({"focus_existing": bool(checked)})

    def _on_notify(self, checked: bool) -> None:
        self.persist({"notify": bool(checked)})

    def _add_rule(self) -> None:
        dialog = AddTargetDialog(self.win, mode="rule",
                                 global_window=float(self.store.get("window_seconds") or 5.0),
                                 global_max=int(self.store.get("max_instances") or 1))
        if dialog.exec_() != dialog.Accepted or not dialog.result_data:
            return
        data = dialog.result_data
        action = data.get("action") or "inherit"
        entry = {
            "matcher": {"kind": data["kind"], "value": data["value"], "note": data.get("note", "")},
            "window_seconds": float(data.get("window_seconds") or 5.0),
            "max_instances": int(data.get("max_instances") or 1),
            "action": None if action == "inherit" else action,
            "enabled": True,
            "note": data.get("note", ""),
        }
        rules = list(self.store.get("rules") or [])
        rules.append(entry)
        self.persist({"rules": rules})
        self.refresh()
        self.toast("自定义规则已添加", "success")

    def _remove_rule(self, index: int) -> None:
        rules = list(self.store.get("rules") or [])
        if index < 0 or index >= len(rules):
            return
        rule = rules[index]
        value = str((rule.get("matcher") or {}).get("value") or "")
        dialog = ConfirmDialog(self.win, "删除规则", "确定删除“%s”的规则吗？" % value,
                               ok_text="删除", danger=True)
        if dialog.exec_() != dialog.Accepted:
            return
        rules.pop(index)
        self.persist({"rules": rules})
        self.refresh()
        self.toast("规则已删除", "warning")
