# -*- coding: utf-8 -*-
"""进程守护引擎：发现“同一个人反复双击导致的多开”，并按规则处理。"""
from __future__ import annotations

import os
import threading
import time

import psutil
from PySide2.QtCore import QObject, Signal

from . import winutil
from .rules import (AppInfo, AppRule, Matcher, find_matching_rule, is_exception,
                    resolve_action, resolve_max_instances, resolve_window)

# 用户主动启动程序时，新进程的父进程通常是这些外壳程序
LAUNCH_PARENTS = {
    "explorer.exe",
    "startmenuexperiencehost.exe",
    "shellexperiencehost.exe",
    "searchapp.exe",
    "searchhost.exe",
}

# 永远不处理的系统进程
SYSTEM_NAMES = {
    "system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "svchost.exe", "fontdrvhost.exe", "dwm.exe",
    "ctfmon.exe", "sihost.exe", "taskhostw.exe", "explorer.exe", "runtimebroker.exe",
    "searchindexer.exe", "audiodg.exe", "spoolsv.exe", "conhost.exe", "dllhost.exe",
    "wudfhost.exe", "searchprotocolhost.exe", "searchfilterhost.exe", "msmpeng.exe",
    "securityhealthservice.exe", "lsass.exe", "winlogon.exe", "textinputhost.exe",
    "applicationframehost.exe", "shellhost.exe", "useroobebroker.exe",
    "startmenuexperiencehost.exe", "shellexperiencehost.exe", "searchapp.exe",
    "searchhost.exe", "lockapp.exe", "logonui.exe", "taskmgr.exe",
    # 系统自带的宿主/脚本进程：它们经常成对短暂出现，误杀会影响系统功能。
    "rundll32.exe", "regsvr32.exe", "mshta.exe", "wscript.exe", "cscript.exe",
    "wmiprvse.exe", "sppsvc.exe", "smartscreen.exe", "backgroundtaskhost.exe",
    "gamebar.exe", "gamebarftserver.exe", "shellexperiencehost.exe",
}

INSTALLER_HINTS = ("setup", "install", "unins", "update", "msiexec", "patch")

POLL_INTERVAL = 0.4
SELF_NAME = os.path.basename(os.path.abspath(__import__("sys").executable)).lower()


class MonitorEngine(QObject):
    blocked = Signal(dict)
    log = Signal(str)
    stateChanged = Signal(bool, bool)  # (enabled, paused)

    def __init__(self, store, logbook, parent=None):
        super().__init__(parent)
        self._store = store
        self._logbook = logbook
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None

        self._enabled = True
        self._paused = False
        self._window_seconds = 5.0
        self._max_instances = 1
        self._action = "kill_notify"
        self._always_enforce = False
        self._focus_existing = True
        self._notify = True
        self._rules = []
        self._exceptions = []

        self._known = {}
        self._exe_cache = {}
        self._launch_history = {}
        self._accept_all_parents = os.environ.get("ANTIMISOPEN_ANY_PARENT") == "1"
        self._current_user = ""
        try:
            self._current_user = psutil.Process().username()
        except Exception:
            self._current_user = os.environ.get("USERNAME", "")

    # ------------------------------------------------------------ 生命周期
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="AntiMisOpenEngine", daemon=True)
        self._thread.start()
        self.log.emit("守护引擎已启动")

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=1.5)
        self.log.emit("守护引擎已停止")

    def apply_config(self, snapshot: dict) -> None:
        """由界面线程调用，刷新引擎使用的配置快照。"""
        with self._lock:
            self._enabled = bool(snapshot.get("enabled", True))
            self._paused = float(snapshot.get("paused_until") or 0) > time.time()
            self._window_seconds = float(snapshot.get("window_seconds") or 5.0)
            self._max_instances = int(snapshot.get("max_instances") or 1)
            self._action = snapshot.get("action") or "kill_notify"
            self._always_enforce = bool(snapshot.get("always_enforce_max"))
            self._focus_existing = bool(snapshot.get("focus_existing", True))
            self._notify = bool(snapshot.get("notify", True))
            self._rules = [AppRule.from_dict(item) for item in (snapshot.get("rules") or [])
                           if isinstance(item, dict)]
            self._exceptions = [Matcher.from_dict(item) for item in (snapshot.get("exceptions") or [])
                                if isinstance(item, dict)]
        self.stateChanged.emit(self._enabled, self._paused)

    # ------------------------------------------------------------ 主循环
    def _loop(self) -> None:
        while not self._stop.is_set():
            started = time.time()
            try:
                self._scan()
            except Exception as exc:  # 引擎绝不因单次异常退出
                self.log.emit("扫描异常：%r" % (exc,))
            elapsed = time.time() - started
            self._stop.wait(max(0.12, POLL_INTERVAL - elapsed))

    def _scan(self) -> None:
        current = {}
        try:
            iterator = psutil.process_iter(["pid", "ppid", "name", "create_time"])
        except Exception:
            return
        for proc in iterator:
            try:
                info = proc.info
                pid = int(info.get("pid") or 0)
                if not pid:
                    continue
                current[pid] = (
                    (info.get("name") or "").lower(),
                    int(info.get("ppid") or 0),
                    float(info.get("create_time") or 0.0),
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        new_pids = [pid for pid in current if pid not in self._known]
        for pid in new_pids:
            try:
                self._consider(pid, current)
            except Exception as exc:
                self.log.emit("处理新进程异常：%r" % (exc,))

        self._known = current
        if len(self._exe_cache) > 400:
            self._exe_cache = {pid: path for pid, path in self._exe_cache.items() if pid in current}

    # ------------------------------------------------------------ 判定
    def _consider(self, pid: int, current: dict) -> None:
        if pid == os.getpid():
            return
        name, ppid, _create = current.get(pid, ("", 0, 0.0))
        if not name or name == SELF_NAME:
            return
        if name in SYSTEM_NAMES:
            return
        if any(hint in name for hint in INSTALLER_HINTS):
            return

        parent_name = current.get(ppid, ("", 0, 0.0))[0]
        if not self._accept_all_parents and parent_name not in LAUNCH_PARENTS:
            return
        if parent_name == name:
            return

        exe = self._exe_of(pid)
        lowered = exe.replace("/", "\\")
        if lowered:
            if "\\windows\\" in lowered or "\\windowsapps\\" in lowered:
                return
            if os.path.basename(lowered) == SELF_NAME:
                return

        info = AppInfo(pid, name, exe, ppid, _create)
        with self._lock:
            enabled = self._enabled
            paused = self._paused
            action = self._action
            rules = list(self._rules)
            exceptions = list(self._exceptions)
            window = self._window_seconds
            max_instances = self._max_instances
            always = self._always_enforce
            focus_existing = self._focus_existing
        if not enabled or paused:
            return
        if is_exception(exceptions, info):
            return

        rule = find_matching_rule(rules, info)
        window = resolve_window(rule, {"window_seconds": window})
        max_instances = resolve_max_instances(rule, {"max_instances": max_instances})
        action = resolve_action(rule, {"action": action})

        instances = self._count_instances(info, current)
        now = time.time()
        history = self._launch_history.setdefault(info.identity, [])
        rapid = bool(history) and (now - history[-1]) <= window
        history.append(now)
        if len(history) > 20:
            del history[:-20]

        exceeded = instances > max_instances
        if not exceeded:
            return
        if not (rapid or always):
            return

        reason = "检测到 %d 个实例（上限 %d 个），且间隔小于 %.0f 秒" % (instances, max_instances, window)
        entry = self._apply_action(info, action, reason, focus_existing)
        if entry:
            self.blocked.emit(entry)

    def _count_instances(self, info: AppInfo, current: dict) -> int:
        count = 0
        for pid, (name, ppid, _create) in current.items():
            if name != info.name:
                continue
            parent_name = current.get(ppid, ("", 0, 0.0))[0]
            if parent_name == name:
                continue  # 程序自己派生的同名子进程，不算多开
            if info.exe:
                exe = self._exe_of(pid)
                if exe and exe != info.exe:
                    continue
            count += 1
        return count

    def _exe_of(self, pid: int) -> str:
        cached = self._exe_cache.get(pid)
        if cached is not None:
            return cached
        path = ""
        try:
            path = (psutil.Process(pid).exe() or "").lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            path = ""
        self._exe_cache[pid] = path
        return path

    # ------------------------------------------------------------ 处理
    def _apply_action(self, info: AppInfo, action: str, reason: str, focus_existing: bool):
        killed = False
        failed_note = ""
        if action in ("kill_silent", "kill_notify"):
            killed, failed_note = self._kill_process(info)
        entry = {
            "ts": time.time(),
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "name": info.display_name,
            "exe": info.exe,
            "pid": info.pid,
            "reason": reason + (("；" + failed_note) if failed_note else ""),
            "action": action,
            "killed": killed,
        }
        if killed and focus_existing:
            self._focus_running_instance(info)
        try:
            self._logbook.add(entry)
        except Exception:
            pass
        return entry

    def _kill_process(self, info: AppInfo):
        try:
            proc = psutil.Process(info.pid)
        except psutil.NoSuchProcess:
            return False, "进程已退出"
        try:
            if self._current_user and proc.username() != self._current_user and not winutil.is_admin():
                return False, "权限不足，未结束进程"
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            return False, "权限不足，未结束进程"
        try:
            for child in proc.children(recursive=True):
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            proc.terminate()
            try:
                proc.wait(0.8)
            except psutil.TimeoutExpired:
                proc.kill()
            return True, ""
        except psutil.NoSuchProcess:
            return True, ""
        except psutil.AccessDenied:
            return False, "权限不足，未结束进程"
        except Exception:
            return False, "结束进程失败"

    def _focus_running_instance(self, info: AppInfo) -> None:
        for pid in list(self._known.keys()):
            if pid == info.pid:
                continue
            if self._known.get(pid, ("", 0, 0.0))[0] != info.name:
                continue
            try:
                handle = winutil.find_main_window(pid)
            except Exception:
                handle = 0
            if handle:
                winutil.activate_window(handle)
                return
