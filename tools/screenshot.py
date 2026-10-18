# -*- coding: utf-8 -*-
"""离屏渲染各页面截图，用于界面自检与 README。

用法： .venv38\Scripts\python.exe tools/screenshot.py
输出： screenshots/*.png
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SHOT_DIR = os.path.join(ROOT, "screenshots")
os.makedirs(SHOT_DIR, exist_ok=True)

sandbox = tempfile.mkdtemp(prefix="antimisopen-shot-")
os.environ["APPDATA"] = sandbox
os.environ["QT_QPA_PLATFORM"] = "windows"  # offscreen 平台不渲染文字，必须用真实平台

from PySide2.QtCore import Qt  # noqa: E402
from PySide2.QtGui import QFont  # noqa: E402
from PySide2.QtWidgets import QApplication  # noqa: E402

from app.core import config, themes  # noqa: E402
from app.core.logbook import LogBook  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def seed(store: config.ConfigStore) -> None:
    now = time.time()
    store.update({
        "action": "notify_only",
        "autostart": True,
        "exceptions": [
            {"kind": "name", "value": "explorer.exe", "note": "资源管理器 / 文件夹窗口"},
            {"kind": "name", "value": "code.exe", "note": "VS Code 需要多窗口"},
            {"kind": "name", "value": "vmware.exe", "note": "虚拟机"},
        ],
        "rules": [
            {"matcher": {"kind": "name", "value": "chrome.exe", "note": "浏览器"},
             "window_seconds": 8.0, "max_instances": 3, "action": "kill_silent",
             "enabled": True, "note": "允许最多 3 个窗口"},
            {"matcher": {"kind": "name", "value": "notepad.exe", "note": "记事本"},
             "window_seconds": 3.0, "max_instances": 1, "action": None,
             "enabled": True, "note": ""},
        ],
        "stats": {
            "total_blocked": 128,
            "today": config.today_key(),
            "today_blocked": 7,
            "protected_seconds": 3600 * 26 + 1800,
            "since": int(now - 86400 * 12),
        },
    })
    store.save()


def seed_logs(logbook: LogBook) -> None:
    samples = [
        ("Microsoft Word", "检测到 2 个实例（上限 1 个），且间隔小于 5 秒", True, 5200),
        ("微信", "检测到 2 个实例（上限 1 个），且间隔小于 5 秒", True, 2700),
        ("QQ", "检测到 2 个实例（上限 1 个），且间隔小于 5 秒", False, 1500),
        ("Chrome", "检测到 4 个实例（上限 3 个），且间隔小于 8 秒", True, 640),
        ("WPS Office", "检测到 2 个实例（上限 1 个），且间隔小于 5 秒", True, 120),
    ]
    for name, reason, killed, age in samples:
        logbook.add({
            "ts": time.time() - age,
            "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - age)),
            "name": name,
            "exe": "",
            "pid": 0,
            "reason": reason,
            "action": "kill_notify" if killed else "notify_only",
            "killed": killed,
        })


def main() -> int:
    application = QApplication(sys.argv)
    application.setStyle("Fusion")
    font = QFont("Microsoft YaHei UI", 9)
    application.setFont(font)

    store = config.ConfigStore()
    seed(store)
    logbook = LogBook()
    seed_logs(logbook)

    # 截图里展示一个干净的用户目录，而不是临时沙箱路径。
    demo_dir = r"C:\Users\Teacher\AppData\Roaming\AntiMisOpen"
    config.app_data_dir = lambda: demo_dir
    config.config_path = lambda: os.path.join(demo_dir, "config.json")
    config.log_dir = lambda: os.path.join(demo_dir, "logs")

    themes.set_theme(str(store.get("theme") or "light_blue"))
    application.setStyleSheet(themes.qss())

    window = MainWindow(store, logbook)
    window.resize(1180, 760)
    window.show()
    for _ in range(8):
        application.processEvents()

    names = ["dashboard", "rules", "exceptions", "settings", "about"]
    for index, name in enumerate(names):
        window.open_page(index)
        for _ in range(6):
            application.processEvents()
        time.sleep(0.15)
        for _ in range(4):
            application.processEvents()
        path = os.path.join(SHOT_DIR, "%s.png" % name)
        window.grab().save(path)
        print("saved", path)

    # 深色主题预览
    window.apply_theme("dark_neon")
    window.open_page(0)
    for _ in range(8):
        application.processEvents()
    theme2 = os.path.join(SHOT_DIR, "dashboard-dark.png")
    window.grab().save(theme2)
    print("saved", theme2)
    window.apply_theme("light_blue")

    window._quitting = True
    window.hide()
    return 0


if __name__ == "__main__":
    sys.exit(main())
