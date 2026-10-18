# -*- coding: utf-8 -*-
"""开机自启动：写入当前用户的 Run 注册表项（无需管理员权限，Win7 起可用）。"""
from __future__ import annotations

import os
import sys

try:
    import winreg
except ImportError:  # pragma: no cover - 非 Windows 平台
    winreg = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "AntiMisOpen"


def _project_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(here))


def launch_command() -> str:
    """返回写入注册表的启动命令行。"""
    if getattr(sys, "frozen", False):
        return '"%s" --autostart' % os.path.abspath(sys.executable)
    python_dir = os.path.dirname(os.path.abspath(sys.executable))
    pythonw = os.path.join(python_dir, "pythonw.exe")
    if not os.path.isfile(pythonw):
        pythonw = os.path.abspath(sys.executable)
    # 从源码运行时要走项目根目录的 run.py，直接执行 app/main.py 会缺少包路径。
    entry = os.path.join(_project_root(), "run.py")
    return '"%s" "%s" --autostart' % (pythonw, entry)


def is_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except OSError:
        return False


def enable() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
        return True
    except OSError:
        return False


def disable() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    return enable() if enabled else disable()
