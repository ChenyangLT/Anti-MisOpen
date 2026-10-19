# -*- coding: utf-8 -*-
"""自检：第三方启动器（非 explorer 父进程）连续启动同一程序时，smart 模式能否拦截。"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

sandbox = tempfile.mkdtemp(prefix="antimisopen-selftest-")
os.environ["APPDATA"] = sandbox
os.environ.pop("ANTIMISOPEN_ANY_PARENT", None)

from app.core import config  # noqa: E402
from app.core.logbook import LogBook  # noqa: E402
from app.core.monitor import MonitorEngine  # noqa: E402

fake = sys.argv[1] if len(sys.argv) > 1 else ""
launcher = sys.argv[2] if len(sys.argv) > 2 else ""
if not (os.path.isfile(fake) and os.path.isfile(launcher)):
    print("usage: selftest_trigger.py <FakeApp.exe> <Launcher.exe>")
    sys.exit(2)


def kill_previous():
    for name in (os.path.basename(fake), os.path.basename(launcher)):
        subprocess.call(["taskkill", "/IM", name, "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.6)


kill_previous()

store = config.ConfigStore()
store.update({
    "first_run": False,
    "enabled": True,
    "action": "notify_only",
    "exceptions": [],
    "rules": [],
    "window_seconds": 5.0,
    "max_instances": 1,
    "trigger_mode": "smart",
    "notify": False,
    "always_enforce_max": False,
    "focus_existing": False,
})
store.save()

logbook = LogBook()
logbook.clear()
before = len(logbook.recent(100))

engine = MonitorEngine(store, logbook)
engine.apply_config(dict(store.data))
engine.start()

try:
    proc = subprocess.Popen([launcher, fake])
    deadline = time.time() + 8.0
    while time.time() < deadline:
        entries = logbook.recent(50)
        if len(entries) > before:
            break
        time.sleep(0.2)
    time.sleep(0.6)
finally:
    engine.stop()
    kill_previous()

entries = logbook.recent(50)
new_entries = entries[: max(0, len(entries) - before)]
print("launcher parent is not explorer.exe -> smart mode")
print("new blocked entries:", len(new_entries))
for entry in reversed(new_entries):
    print("  -", entry.get("name"), "|", entry.get("reason"), "| killed:", entry.get("killed"))
print("RESULT:", "PASS" if new_entries else "FAIL")
