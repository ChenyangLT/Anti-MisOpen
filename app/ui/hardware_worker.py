# -*- coding: utf-8 -*-
"""后台线程：读取硬件信息，避免界面卡顿。"""
from __future__ import annotations

from PySide2.QtCore import QThread, Signal

from ..core import hardware


class HardwareThread(QThread):
    finished_data = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            data = hardware.collect_and_cache()
        except Exception as exc:  # 兜底：至少展示系统信息
            try:
                data = {"generated_at": 0, "groups": hardware.collect_groups(False)["groups"],
                        "source": "fallback", "error": str(exc)}
            except Exception:
                data = {"generated_at": 0, "groups": [], "source": "fallback",
                        "error": str(exc)}
        self.finished_data.emit(data)
