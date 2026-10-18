# -*- coding: utf-8 -*-
"""Windows 平台相关的小工具（全部做兼容处理，可在 Win7 SP1 / Win10 / Win11 工作）。"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import platform
import sys
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_RESTORE = 9
SW_SHOW = 5
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


def windows_version():
    try:
        return sys.getwindowsversion()
    except Exception:
        return platform.win32_ver()[1]


def is_windows() -> bool:
    return os.name == "nt"


def is_win7() -> bool:
    try:
        v = sys.getwindowsversion()
        return v.major == 6 and v.minor == 1
    except Exception:
        return False


def windows_label() -> str:
    """返回人类可读的系统名称，Win11 不会被显示成 Win10。"""
    try:
        v = sys.getwindowsversion()
    except Exception:
        return platform.system()
    if (v.major, v.minor) == (6, 1):
        return "Windows 7"
    if (v.major, v.minor) == (6, 2):
        return "Windows 8"
    if (v.major, v.minor) == (6, 3):
        return "Windows 8.1"
    if (v.major, v.minor) == (10, 0):
        return "Windows 11" if v.build >= 22000 else "Windows 10"
    return "Windows %d.%d" % (v.major, v.minor)


def is_win8_or_later() -> bool:
    try:
        v = sys.getwindowsversion()
        return (v.major, v.minor) >= (6, 2)
    except Exception:
        return True


def enable_dpi_awareness() -> None:
    """尽量开启 DPI 感知；Win7 上退回到旧 API。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:
        pass
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def composition_enabled() -> bool:
    """DWM 合成是否可用（决定能否使用无边框圆角窗口）。"""
    try:
        enabled = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmIsCompositionEnabled(ctypes.byref(enabled))
        return bool(enabled.value)
    except Exception:
        return False


def system_prefers_dark() -> bool:
    """读取系统“应用使用浅色/深色主题”设置，读不到时按浅色处理。"""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
    except Exception:
        return False


# ---------------------------------------------------------------- 窗口枚举
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)


def _enum_windows():
    handles = []

    @WNDENUMPROC
    def callback(hwnd, lparam):
        handles.append(hwnd)
        return True

    user32.EnumWindows(callback, 0)
    return handles


def window_pid(hwnd: int) -> int:
    pid = wt.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 2)
    user32.GetWindowTextW(hwnd, buffer, length + 2)
    return buffer.value


def _window_exstyle(hwnd: int) -> int:
    try:
        return int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE)) & 0xFFFFFFFF
    except Exception:
        return 0


def is_real_window(hwnd: int) -> bool:
    if not user32.IsWindowVisible(hwnd):
        return False
    if user32.GetWindow(hwnd, 4) != 0:  # GW_OWNER：跳过弹窗/工具窗口
        return False
    exstyle = _window_exstyle(hwnd)
    if exstyle & WS_EX_TOOLWINDOW:
        return False
    return True


def find_main_window(pid: int) -> int:
    """返回该进程的第一个“主窗口”句柄，找不到返回 0。"""
    for hwnd in _enum_windows():
        if window_pid(hwnd) != pid:
            continue
        if not is_real_window(hwnd):
            continue
        if not window_title(hwnd).strip():
            continue
        return hwnd
    return 0


def has_visible_window(pid: int) -> bool:
    return find_main_window(pid) != 0


def activate_window(hwnd: int) -> bool:
    """尽力把窗口带到前台。"""
    if not hwnd:
        return False
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        else:
            user32.ShowWindow(hwnd, SW_SHOW)

        foreground = user32.GetForegroundWindow()
        if foreground == hwnd:
            return True
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        current_thread = kernel32.GetCurrentThreadId()
        attached = False
        if target_thread and target_thread != current_thread:
            attached = bool(user32.AttachThreadInput(current_thread, target_thread, True))
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
        if attached:
            user32.AttachThreadInput(current_thread, target_thread, False)
        return True
    except Exception:
        return False


def shell_window_owner_pid() -> int:
    """explorer.exe 的 pid（双击启动程序的父进程）。"""
    try:
        hwnd = user32.GetShellWindow()
        if hwnd:
            return window_pid(hwnd)
    except Exception:
        pass
    return 0


def long_path(path: str) -> str:
    if not path:
        return path
    if path.startswith("\\\\?\\"):
        return path
    if len(path) > 250:
        if path.startswith("\\\\"):
            return "\\\\?\\UNC\\" + path[2:]
        return "\\\\?\\" + path
    return path
