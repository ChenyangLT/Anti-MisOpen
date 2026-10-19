# -*- coding: utf-8 -*-
"""垃圾清理页：回收站、临时文件、下载 / 图片 / 视频。"""
from __future__ import annotations

import os
import subprocess
import time

from PySide2.QtCore import Qt, QThread, QTimer, Signal
from PySide2.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from ...core import junk
from ...core.cleaner import format_bytes
from ..dialogs import ConfirmDialog
from ..widgets import StatCard, ToggleSwitch, make_label
from .base import PageBase, make_button


class _JunkWorker(QThread):
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, mode, selected, use_recycle, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.selected = list(selected)
        self.use_recycle = bool(use_recycle)

    def run(self):
        try:
            if self.mode == "scan":
                result = junk.scan()
            else:
                result = junk.clean(self.selected, self.use_recycle)
            self.done.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class JunkPage(PageBase):
    def __init__(self, window):
        super().__init__(window)
        self._scan = {}
        self._scanning = False
        self._cleaning = False
        self._thread = None
        self._last_scan = 0.0
        self._switches = {}
        self._size_labels = {}
        self._build()
        self.refresh()

    # ------------------------------------------------------------- 构建
    def _build(self) -> None:
        self._scan_button = make_button("重新扫描", "ghost")
        self._scan_button.clicked.connect(lambda: self._start_scan(force=True))
        self._clean_button = make_button("立即清理", "primary")
        self._clean_button.clicked.connect(self._on_clean)
        self.page_header(
            "垃圾清理",
            "定期清掉电教电脑里越积越多的图片、下载、临时文件和回收站",
            actions=[self._clean_button, self._scan_button])

        self._build_stats()
        self._build_categories()
        self._build_options()
        self.hint("清理只针对上面勾选的内容，不会动系统文件和已安装的软件。"
                  "下载、图片、视频默认先移到回收站，误删可以恢复；回收站需要另外勾选才会清空。")
        self.body.addStretch(1)

    def _build_stats(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(14)
        self._total_card = StatCard("trash", "可清理空间", "—", "扫描中…")
        self._selected_card = StatCard("check", "已选择", "—", "勾选要清理的项目")
        self._freed_card = StatCard("refresh", "累计释放", "0 B", "自使用垃圾清理以来")
        for card in (self._total_card, self._selected_card, self._freed_card):
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(card)
        self.body.addLayout(row)

    def _build_categories(self) -> None:
        card, layout = self.card(
            "可清理的内容", "默认勾选回收站和临时文件；下载、图片、视频里是个人文件，请确认后再勾选")
        for index, category in enumerate(junk.CATEGORIES):
            switch = ToggleSwitch()
            switch.toggled.connect(
                lambda checked, cid=category["id"]: self._on_toggle(cid, checked))
            self._switches[category["id"]] = switch

            size = make_label("—", "body")
            size.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            size.setMinimumWidth(120)
            self._size_labels[category["id"]] = size

            box = QWidget()
            box_layout = QHBoxLayout(box)
            box_layout.setContentsMargins(0, 0, 0, 0)
            box_layout.setSpacing(16)
            box_layout.addWidget(size)
            box_layout.addWidget(switch)
            layout.addWidget(self.setting_row(category["title"], category["hint"], box))
            if index != len(junk.CATEGORIES) - 1:
                layout.addWidget(self.divider())
        self.body.addWidget(card)

    def _build_options(self) -> None:
        card, layout = self.card("清理方式", "决定个人文件夹里的内容删掉后还能不能找回来")
        self._recycle_switch = ToggleSwitch()
        self._recycle_switch.toggled.connect(self._on_use_recycle)
        layout.addWidget(self.setting_row(
            "删除到回收站", "开启时下载 / 图片 / 视频先放进回收站，可以恢复；关闭则直接删除",
            self._recycle_switch))
        layout.addWidget(self.divider())
        row = QHBoxLayout()
        row.setSpacing(10)
        open_button = make_button("打开回收站", "ghost")
        open_button.clicked.connect(self._open_recycle)
        row.addWidget(open_button)
        row.addWidget(make_label("清空回收站会真正释放磁盘空间，清空后无法恢复。", "muted"), 1)
        layout.addLayout(row)
        self.body.addWidget(card)

    # ------------------------------------------------------------- 扫描 / 清理
    def showEvent(self, event):
        super().showEvent(event)
        if time.time() - self._last_scan > 60 and not self._scanning:
            QTimer.singleShot(60, lambda: self._start_scan())

    def _selected_ids(self):
        return [cid for cid, switch in self._switches.items() if switch.isChecked()]

    def _start_scan(self, force: bool = False) -> None:
        if self._scanning or self._cleaning:
            return
        if not force and self._scan and time.time() - self._last_scan < 60:
            return
        self._scanning = True
        self._scan_button.setEnabled(False)
        self._scan_button.setText("扫描中…")
        self._total_card.set_value("—", "正在统计占用空间…")
        self._thread = _JunkWorker("scan", self._selected_ids(), True, self)
        self._thread.done.connect(self._on_scan_done)
        self._thread.failed.connect(self._on_thread_failed)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _on_scan_done(self, result: dict) -> None:
        self._scan = result
        self._last_scan = time.time()
        self._apply_scan()

    def _apply_scan(self) -> None:
        categories = self._scan.get("categories") or {}
        for category in junk.CATEGORIES:
            cid = category["id"]
            info = categories.get(cid) or {"bytes": 0, "items": 0}
            label = self._size_labels.get(cid)
            if label is not None:
                if info["items"]:
                    label.setText("%s · %s 项" % (
                        format_bytes(info["bytes"]), format("{:,}".format(info["items"]))))
                else:
                    label.setText("空")
        total = int(self._scan.get("total_bytes") or 0)
        total_items = int(self._scan.get("total_items") or 0)
        self._total_card.set_value(
            format_bytes(total),
            "%s 项 · 上次扫描 %s" % (format("{:,}".format(total_items)),
                                    time.strftime("%H:%M", time.localtime(self._last_scan))))
        self._update_selected()
        self._freed_card.set_value(
            format_bytes(int(self.store.get("junk_total_freed") or 0)),
            "自使用垃圾清理以来")

    def _update_selected(self) -> None:
        categories = self._scan.get("categories") or {}
        total = 0
        items = 0
        for cid in self._selected_ids():
            info = categories.get(cid) or {}
            total += int(info.get("bytes") or 0)
            items += int(info.get("items") or 0)
        self._selected_card.set_value(
            format_bytes(total), "%s 项待清理" % format("{:,}".format(items)))
        self._clean_button.setEnabled(bool(self._selected_ids()) and not self._scanning)

    def _on_thread_finished(self) -> None:
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        self._scanning = False
        self._cleaning = False
        self._scan_button.setEnabled(True)
        self._scan_button.setText("重新扫描")
        self._clean_button.setEnabled(bool(self._selected_ids()))

    def _on_thread_failed(self, message: str) -> None:
        self.toast("操作失败：%s" % message, "warning")

    def _on_toggle(self, category_id: str, checked: bool) -> None:
        selected = self._selected_ids()
        self.store.update({"junk_selected": selected})
        self.store.save()
        self._update_selected()

    def _on_use_recycle(self, checked: bool) -> None:
        self.store.update({"junk_use_recycle": bool(checked)})
        self.store.save()

    def _on_clean(self) -> None:
        selected = self._selected_ids()
        if not selected:
            self.toast("先勾选要清理的内容", "warning")
            return
        categories = self._scan.get("categories") or {}
        lines = []
        for category in junk.CATEGORIES:
            if category["id"] not in selected:
                continue
            info = categories.get(category["id"]) or {}
            detail = "%s · %s 项" % (format_bytes(int(info.get("bytes") or 0)),
                                     format("{:,}".format(int(info.get("items") or 0))))
            lines.append("· %s（%s）" % (category["title"], detail))
        use_recycle = bool(self._recycle_switch.isChecked())
        body = "将清理：\n%s\n\n%s" % (
            "\n".join(lines),
            "下载、图片、视频会移到回收站，误删可以恢复。" if use_recycle
            else "所有内容会直接删除，无法恢复。")
        if not ConfirmDialog.confirm(self.win, "确认清理", body, "开始清理", danger=True):
            return

        self._cleaning = True
        self._scanning = False
        self._clean_button.setEnabled(False)
        self._clean_button.setText("清理中…")
        self._thread = _JunkWorker("clean", selected, use_recycle, self)
        self._thread.done.connect(self._on_clean_done)
        self._thread.failed.connect(self._on_thread_failed)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _on_clean_done(self, result: dict) -> None:
        freed = int(result.get("freed") or 0)
        removed = int(result.get("removed") or 0)
        moved = int(result.get("moved") or 0)
        failed = int(result.get("failed") or 0)

        if freed or removed:
            total = int(self.store.get("junk_total_freed") or 0) + freed
            self.store.update({
                "junk_total_freed": total,
                "junk_last_cleanup": time.time(),
                "junk_last_freed": freed,
            })
            self.store.save()

        if moved:
            self.toast("已把 %s 项移到回收站，如需腾出空间请在回收站中清空" % format("{:,}".format(moved)),
                       "success")
        elif freed or removed:
            self.toast("清理完成，释放了 %s" % format_bytes(freed), "success")
        else:
            self.toast("没有可清理的内容", "warning")
        if failed:
            self.toast("%s 项被占用，已跳过" % format("{:,}".format(failed)), "warning")

        self._freed_card.set_value(
            format_bytes(int(self.store.get("junk_total_freed") or 0)),
            "自使用垃圾清理以来")
        QTimer.singleShot(600, lambda: self._start_scan(force=True))

    # ------------------------------------------------------------- 其他
    def _open_recycle(self) -> None:
        try:
            if os.path.isdir(os.path.join("C:\\$Recycle.Bin")):
                subprocess.Popen(["explorer.exe", "shell:RecycleBinFolder"])
        except Exception:
            pass

    def refresh(self) -> None:
        self._recycle_switch.blockSignals(True)
        self._recycle_switch.setChecked(bool(self.store.get("junk_use_recycle")))
        self._recycle_switch.blockSignals(False)

        saved = set(self.store.get("junk_selected") or [])
        for cid, switch in self._switches.items():
            switch.blockSignals(True)
            switch.setChecked(cid in saved)
            switch.blockSignals(False)

        self._freed_card.set_value(
            format_bytes(int(self.store.get("junk_total_freed") or 0)),
            "自使用垃圾清理以来")
        self._update_selected()
