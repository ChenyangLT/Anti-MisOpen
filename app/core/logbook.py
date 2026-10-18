# -*- coding: utf-8 -*-
"""拦截记录（JSON Lines）。"""
from __future__ import annotations

import json
import os
import threading
import time

from . import config as cfg


class LogBook:
    def __init__(self, path: str = None):
        self.path = path or os.path.join(cfg.log_dir(), "blocked.jsonl")
        self._lock = threading.Lock()
        self._memory = []

    def add(self, entry: dict) -> dict:
        if "ts" not in entry:
            entry["ts"] = time.time()
        entry.setdefault("time", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry["ts"])))
        with self._lock:
            self._memory.append(entry)
            if len(self._memory) > 400:
                self._memory = self._memory[-400:]
            try:
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError:
                pass
        return entry

    def recent(self, limit: int = 30) -> list:
        with self._lock:
            items = list(self._memory[-limit:])
            if items:
                return items[::-1]
        return self._read_file(limit)

    def _read_file(self, limit: int) -> list:
        if not os.path.isfile(self.path):
            return []
        rows = []
        try:
            with open(self.path, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            return []
        return rows[-limit:][::-1]

    def clear(self) -> None:
        with self._lock:
            self._memory = []
            try:
                open(self.path, "w", encoding="utf-8").close()
            except OSError:
                pass

    def count(self) -> int:
        with self._lock:
            if self._memory:
                return len(self._memory)
        return len(self._read_file(1000000))

    def prune(self, days: int = 30) -> None:
        """删除过旧的记录，避免日志无限增长。"""
        if not os.path.isfile(self.path) or days <= 0:
            return
        cutoff = time.time() - days * 86400
        kept = []
        try:
            with open(self.path, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except ValueError:
                        continue
                    if float(item.get("ts", 0)) >= cutoff:
                        kept.append(line)
            with open(self.path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(kept) + ("\n" if kept else ""))
        except OSError:
            pass
