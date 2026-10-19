# -*- coding: utf-8 -*-
"""设置页：启动方式、外观、安全、数据维护。"""
from __future__ import annotations

import subprocess
import time

from PySide2.QtCore import Qt, QUrl
from PySide2.QtGui import QDesktopServices
from PySide2.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

from ...core import autostart, config, notifyfix, themes, winutil
from ..dialogs import ConfirmDialog, InfoDialog, PasswordDialog
from ..widgets import (EmptyState, Stepper, ThemeCard, ToggleSwitch,
                       make_badge, make_label)
from .base import PageBase, make_button
from ...core.logbook import LogBook
from ...core import winutil


class SettingsPage(PageBase):
    def __init__(self, window):
        super().__init__(window)
        self._theme_cards = {}
        self._build()
        self.refresh()

    def _build(self) -> None:
        self.page_header("设置", "启动方式、界面外观、密码保护和数据维护")
        self._build_startup()
        self._build_notifications()
        self._build_theme()
        self._build_security()
        self._build_data()
        self.body.addStretch(1)

    def _build_startup(self) -> None:
        card, layout = self.card("启动与运行", "默认关闭自启动，可随时在这里开启")
        self._autostart_switch = ToggleSwitch()
        self._autostart_switch.toggled.connect(self._on_autostart)
        layout.addWidget(self.setting_row(
            "开机自启动", "开机后自动在后台运行，老师打开电脑就已经受到保护",
            self._autostart_switch))
        layout.addWidget(self.divider())

        self._tray_switch = ToggleSwitch()
        self._tray_switch.toggled.connect(self._on_tray)
        layout.addWidget(self.setting_row(
            "关闭窗口时最小化到托盘", "关闭主界面后继续在后台防护，可从托盘重新打开",
            self._tray_switch))
        layout.addWidget(self.divider())

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(make_badge("常驻后台", "success"))
        row.addWidget(make_label("守护引擎以约 0.2 秒的间隔检查新启动的程序，占用很低。", "muted"))
        row.addStretch(1)
        layout.addLayout(row)
        self.body.addWidget(card)

    def _build_notifications(self) -> None:
        card, layout = self.card("通知与提示", "拦截提示弹不出来时，可以用这里的“一键修复”恢复系统通知设置")
        self._notify_badge = make_badge("检测中…", "muted")
        self._notify_status = make_label("", "muted", wrap=True)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(self._notify_badge, 0, Qt.AlignVCenter)
        head.addWidget(self._notify_status, 1)
        layout.addLayout(head)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        repair = make_button("一键修复通知设置", "primary")
        repair.clicked.connect(self._on_repair_notify)
        buttons.addWidget(repair)
        recheck = make_button("重新检测", "ghost")
        recheck.clicked.connect(lambda: self._refresh_notify_status(force=True, toast=True))
        buttons.addWidget(recheck)
        test = make_button("测试通知", "ghost")
        test.clicked.connect(self.win.test_notification)
        buttons.addWidget(test)
        open_settings = make_button("打开系统通知设置", "ghost")
        open_settings.clicked.connect(self._open_notification_settings)
        buttons.addWidget(open_settings)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._notify_note = make_label("", "faint", wrap=True)
        layout.addWidget(self._notify_note)
        self.body.addWidget(card)

    def _build_theme(self) -> None:
        card, layout = self.card("外观主题", "四种主题随时切换，选择后立即生效")
        row = QHBoxLayout()
        row.setSpacing(12)
        for key, label, description in themes.THEME_CHOICES:
            item = ThemeCard(key, label, description)
            item.clicked.connect(lambda _checked=False, k=key: self._on_theme(k))
            self._theme_cards[key] = item
            row.addWidget(item)
        row.addStretch(1)
        layout.addLayout(row)
        self.body.addWidget(card)

    def _build_security(self) -> None:
        card, layout = self.card("密码保护", "开启后，关闭防护、暂停防护或退出程序需要输入密码")
        self._password_row = QWidget()
        row_layout = QHBoxLayout(self._password_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        titles.addWidget(make_label("设置密码", "body"))
        titles.addWidget(make_label("老师不知道密码，就无法关闭或暂停防护", "muted", wrap=True))
        row_layout.addLayout(titles, 1)
        self._password_badge = make_badge("未开启", "muted")
        row_layout.addWidget(self._password_badge, 0, Qt.AlignVCenter)
        self._password_button = make_button("设置密码", "primary")
        self._password_button.clicked.connect(self._on_password)
        row_layout.addWidget(self._password_button, 0, Qt.AlignVCenter)
        self._password_clear = make_button("关闭保护", "ghost")
        self._password_clear.clicked.connect(self._on_password_disable)
        row_layout.addWidget(self._password_clear, 0, Qt.AlignVCenter)
        layout.addWidget(self._password_row)

        warning = make_label("忘记密码后需要手动删除配置文件 %s 才能重置。"
                             % config.config_path(), "faint", wrap=True)
        layout.addWidget(warning)
        self.body.addWidget(card)

    def _build_data(self) -> None:
        card, layout = self.card("数据与维护", "配置和记录都保存在本机用户目录")

        self._days_stepper = Stepper(30.0, 1.0, 365.0, 1.0, 0, " 天")
        self._days_stepper.valueChanged.connect(self._on_days)
        layout.addWidget(self.setting_row(
            "拦截记录保留天数", "超期的记录会在启动时自动清理", self._days_stepper))
        layout.addWidget(self.divider())

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        open_config = make_button("打开配置目录", "ghost")
        open_config.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(config.app_data_dir())))
        buttons.addWidget(open_config)
        open_logs = make_button("打开日志目录", "ghost")
        open_logs.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(config.log_dir())))
        buttons.addWidget(open_logs)
        clear_logs = make_button("清空拦截记录", "ghost")
        clear_logs.clicked.connect(self._on_clear_logs)
        buttons.addWidget(clear_logs)
        buttons.addStretch(1)
        reset = make_button("恢复默认设置", "danger")
        reset.clicked.connect(self._on_reset)
        buttons.addWidget(reset)
        layout.addLayout(buttons)
        self.body.addWidget(card)

    # ------------------------------------------------------------- 刷新
    def refresh(self) -> None:
        for switch, key in ((self._autostart_switch, "autostart"),
                            (self._tray_switch, "close_to_tray")):
            switch.blockSignals(True)
            switch.setChecked(bool(self.store.get(key)))
            switch.blockSignals(False)

        theme_key = str(self.store.get("theme") or "light_blue")
        for key, card in self._theme_cards.items():
            card.setChecked(key == theme_key)

        self._days_stepper.setValue(float(self.store.get("log_keep_days") or 30))

        has_password = bool(self.store.get("password"))
        self._password_badge.setText("已开启" if has_password else "未开启")
        self._password_badge.setProperty("tone", "success" if has_password else "muted")
        themes.repolish(self._password_badge)
        self._password_clear.setVisible(has_password)
        self._password_button.setText("修改密码" if has_password else "设置密码")

        self._refresh_notify_status()

    # ------------------------------------------------------------- 通知
    def _refresh_notify_status(self, force: bool = False, toast: bool = False) -> None:
        now = time.time()
        if not force and now - getattr(self, "_notify_checked", 0) < 30:
            return
        self._notify_checked = now
        try:
            diagnosis = notifyfix.diagnose()
        except Exception as exc:  # noqa: BLE001
            self._notify_badge.setText("无法检测")
            self._notify_badge.setProperty("tone", "muted")
            themes.repolish(self._notify_badge)
            self._notify_status.setText("读取通知设置失败：%s" % exc)
            return
        ok = bool(diagnosis.get("ok"))
        self._notify_badge.setText("正常" if ok else "需要修复")
        self._notify_badge.setProperty("tone", "success" if ok else "warning")
        themes.repolish(self._notify_badge)
        self._notify_status.setText(notifyfix.summary(diagnosis))
        self._notify_note.setText(diagnosis.get("note") or "")
        if not ok:
            broken = [item["title"] for item in diagnosis.get("checks", [])
                      if item["required"] and not item["ok"]]
            self._notify_note.setText("需要处理：%s%s" % (
                "、".join(broken),
                "（部分项目需要管理员权限）" if not diagnosis.get("admin") else ""))
        if toast:
            self.toast("通知设置正常" if ok else "通知设置需要修复", "success" if ok else "warning")

    def _on_repair_notify(self) -> None:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = notifyfix.repair()
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            self.toast("修复失败：%s" % exc, "danger")
            return
        QApplication.restoreOverrideCursor()
        lines = []
        lines.append("修复完成，通知设置已恢复正常。" if result.get("ok")
                     else "已尽量修复，但下面这些项目没能改成功：")
        for step in result.get("steps", []):
            prefix = "✓ " if step.get("ok") else "✗ "
            detail = ("（%s）" % step["detail"]) if step.get("detail") else ""
            lines.append(prefix + step.get("title", "") + detail)
        lines.append("")
        lines.append("可以点“测试通知”确认效果；如果系统开了“专注助手 / 请勿打扰”，需要先关掉。")
        InfoDialog(self.win, "通知设置修复结果", "下面的修改已写入当前用户的通知设置",
                   lines, width=520).exec_()
        self._refresh_notify_status(force=True)
        self.win.test_notification()

    def _open_notification_settings(self) -> None:
        if winutil.is_win7():
            try:
                subprocess.Popen(["control.exe", "/name", "Microsoft.NotificationAreaIcons"],
                                 creationflags=0x08000000)
                return
            except Exception:
                pass
        QDesktopServices.openUrl(QUrl("ms-settings:notifications"))

    # ------------------------------------------------------------- 交互
    def _on_autostart(self, checked: bool) -> None:
        ok = autostart.set_enabled(checked)
        if not ok:
            self.toast("写入开机启动项失败，请检查系统权限", "danger")
            self.refresh()
            return
        self.persist({"autostart": checked})
        self.toast("已开启开机自启动" if checked else "已关闭开机自启动",
                   "success" if checked else "warning")
        self.win.refresh_pages()
        self.refresh()

    def _on_tray(self, checked: bool) -> None:
        self.persist({"close_to_tray": checked})
        self.toast("已更新关闭窗口行为", "success")

    def _on_theme(self, key: str) -> None:
        self.persist({"theme": key})
        self.win.apply_theme(key)
        self.refresh()
        self.toast("已切换主题：%s" % (dict((k, label) for k, label, _d in themes.THEME_CHOICES).get(key, key)),
                   "success")

    def _on_days(self, value: float) -> None:
        self.persist({"log_keep_days": int(value)})

    def _on_password(self) -> None:
        record = self.store.get("password")
        mode = "change" if record else "set"
        dialog = PasswordDialog(self.win, has_password=bool(record), mode=mode, record=record)
        if dialog.exec_() != dialog.Accepted:
            return
        self.persist({"password": config.make_password(dialog.result_password)})
        self.refresh()
        self.toast("密码已保存", "success")

    def _on_password_disable(self) -> None:
        record = self.store.get("password")
        if not record:
            return
        dialog = PasswordDialog(self.win, has_password=True, mode="disable", record=record)
        if dialog.exec_() != dialog.Accepted:
            return
        self.persist({"password": None})
        self.refresh()
        self.toast("已关闭密码保护", "warning")

    def _on_clear_logs(self) -> None:
        dialog = ConfirmDialog(self.win, "清空拦截记录",
                               "会删除所有拦截记录和统计数字，此操作不可撤销。",
                               ok_text="清空", danger=True)
        if dialog.exec_() != dialog.Accepted:
            return
        self.win.logbook.clear()
        stats = {"total_blocked": 0, "today": config.today_key(),
                 "today_blocked": 0, "protected_seconds": 0.0, "since": 0}
        self.persist({"stats": stats})
        self.win.refresh_pages()
        self.toast("已清空拦截记录", "warning")

    def _on_reset(self) -> None:
        dialog = ConfirmDialog(self.win, "恢复默认设置",
                               "会恢复所有设置（包括密码、主题和例外名单），但不会删除拦截记录。",
                               ok_text="恢复默认", danger=True)
        if dialog.exec_() != dialog.Accepted:
            return
        autostart.disable()
        self.store.reset()
        self.store.save()
        self.win.after_reset()
        self.refresh()
        self.toast("已恢复默认设置", "success")
