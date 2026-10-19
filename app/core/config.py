# -*- coding: utf-8 -*-
"""配置与常量的持久化。

配置保存在 %APPDATA%\AntiMisOpen\config.json（UTF-8，原子写入）。
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import threading
import time

APP_ID = "AntiMisOpen"
APP_NAME = "Anti MisOpen"
APP_NAME_CN = "防误开"
APP_VERSION = "1.2.0"
BUILD_DATE = "2026-10-19"
APP_SIGNATURE = "Chen_yang_ & Deepseek V4.1 Flash 1017 Ver."
GITHUB_URL = "https://github.com/ChenyangLT/Anti-MisOpen"

ACTIONS = {
    "kill_silent": "静默结束多余实例",
    "kill_notify": "结束时弹出提示",
    "notify_only": "只提示，不结束进程",
}

THEME_KEYS = ["light_blue", "dark_neon", "light_green", "system"]

DEFAULT_CONFIG = {
    "version": 1,
    "enabled": True,
    "autostart": False,
    "window_seconds": 5.0,
    "max_instances": 1,
    "action": "kill_notify",
    # 判断“用户主动启动”的方式：smart=智能识别（默认），shell=只看桌面/开始菜单，
    # any=所有新进程都算（仅用于排查问题，容易误伤）
    "trigger_mode": "smart",
    "always_enforce_max": False,
    "focus_existing": True,
    "exceptions": [
        {"kind": "name", "value": "explorer.exe", "note": "资源管理器 / 文件夹窗口"},
    ],
    "rules": [],
    "password": None,
    "theme": "light_blue",
    "close_to_tray": True,
    "notify": True,
    "log_keep_days": 30,
    "paused_until": 0,
    "stats": {
        "total_blocked": 0,
        "today": "",
        "today_blocked": 0,
        "protected_seconds": 0.0,
        "since": 0,
    },
    "first_run": True,
    "window_geometry": "",
    # 内存清理（参考 PCL2 / Mem Reduct：只清理工作集与系统缓存，不结束任何软件）
    "memory_auto": False,
    "memory_threshold": 85,
    "memory_deep": False,
    "memory_auto_notify": True,
    "memory_last_cleanup": 0,
    "memory_last_freed": 0,
    "memory_total_freed": 0,
    # 垃圾清理
    "junk_selected": ["recycle", "temp"],
    "junk_use_recycle": True,
    "junk_last_cleanup": 0,
    "junk_last_freed": 0,
    "junk_total_freed": 0,
}


def app_data_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_ID)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def config_path() -> str:
    return os.path.join(app_data_dir(), "config.json")


def log_dir() -> str:
    path = os.path.join(app_data_dir(), "logs")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def asset_dir() -> str:
    """资源目录：打包后位于 _MEIPASS/assets，开发时位于项目根目录 assets。"""
    import sys

    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    for candidate in (os.path.join(base, "assets"), os.path.join(base, "app", "assets")):
        if os.path.isdir(candidate):
            return candidate
    return os.path.join(base, "assets")


def _deep_merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def make_password(password: str) -> dict:
    salt = os.urandom(16)
    iterations = 120000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return {
        "algo": "pbkdf2_sha256",
        "iterations": iterations,
        "salt": salt.hex(),
        "hash": digest.hex(),
    }


def verify_password(password: str, record) -> bool:
    if not record:
        return True
    try:
        salt = bytes.fromhex(record.get("salt", ""))
        iterations = int(record.get("iterations", 120000))
        expected = record.get("hash", "")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return digest.hex() == expected
    except Exception:
        return False


def today_key() -> str:
    return time.strftime("%Y-%m-%d")


class ConfigStore:
    """线程安全的配置容器。"""

    def __init__(self, path: str = None):
        self.path = path or config_path()
        self._lock = threading.RLock()
        self.data = self._load()

    def _load(self) -> dict:
        raw = {}
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                raw = loaded
        except FileNotFoundError:
            pass
        except Exception:
            try:
                shutil.copy2(self.path, self.path + ".broken")
            except OSError:
                pass
        data = _deep_merge(copy.deepcopy(DEFAULT_CONFIG), raw)
        return data

    def get(self, key: str, default=None):
        with self._lock:
            return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        with self._lock:
            self.data[key] = value

    def update(self, mapping: dict) -> None:
        with self._lock:
            self.data.update(mapping)

    def save(self) -> None:
        with self._lock:
            payload = json.dumps(self.data, ensure_ascii=False, indent=2)
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, self.path)
        except OSError:
            try:
                with open(self.path, "w", encoding="utf-8") as fh:
                    fh.write(payload)
            except OSError:
                pass

    def reset(self) -> None:
        with self._lock:
            self.data = copy.deepcopy(DEFAULT_CONFIG)
        self.save()

    def is_paused(self) -> bool:
        with self._lock:
            return float(self.data.get("paused_until") or 0) > time.time()

    def touch_stats(self) -> dict:
        with self._lock:
            stats = self.data.setdefault("stats", {})
            key = today_key()
            if stats.get("today") != key:
                stats["today"] = key
                stats["today_blocked"] = 0
            return stats
