# -*- coding: utf-8 -*-
"""后台清理线程：内存清理需要遍历进程，放到线程里避免界面卡顿。"""
from __future__ import annotations

from PySide2.QtCore import QThread, Signal

from ..core import cleaner


class CleanerThread(QThread):
    finished_result = Signal(dict)

    def __init__(self, deep: bool = False, parent=None):
        super().__init__(parent)
        self._deep = bool(deep)

    def run(self) -> None:
        try:
            result = cleaner.clean_memory(self._deep)
        except Exception as exc:  # 清理失败不应该影响主程序
            result = {
                "ok": False,
                "error": str(exc),
                "freed": 0,
                "trimmed": 0,
                "deep": self._deep,
                "timestamp": 0,
                "elapsed": 0,
                "system_items": [],
                "before": cleaner.memory_snapshot(),
                "after": cleaner.memory_snapshot(),
            }
        self.finished_result.emit(result)
