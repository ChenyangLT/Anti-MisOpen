# -*- coding: utf-8 -*-
"""通知诊断与一键修复。

学校的电脑经常被策略、电脑管家或“专注助手”关掉通知，导致拦截提示弹不出来。
这里把关键开关集中检查并修复（只改当前用户 HKCU，不改系统文件，不需要管理员）。
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import winreg
from ctypes import wintypes

from . import config, winutil

AUMID = config.APP_ID
HKCU = winreg.HKEY_CURRENT_USER
HKLM = winreg.HKEY_LOCAL_MACHINE

PUSH_KEY = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications"
NOTIFY_ROOT = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
APP_KEY = NOTIFY_ROOT + "\\" + AUMID
EXPLORER_ADV = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
POLICY_KEY = r"Software\Policies\Microsoft\Windows\Explorer"
AUMID_KEY = r"Software\Classes\AppUserModelId\%s" % AUMID

WM_SETTINGCHANGE = 0x001A
HWND_BROADCAST = 0xFFFF
SMTO_ABORTIFHUNG = 0x0002
CREATE_NO_WINDOW = 0x08000000


# ------------------------------------------------------------------ 注册表
def _read_dword(root, path: str, name: str):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as key:
            value, _kind = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _write_dword(root, path: str, name: str, value: int):
    try:
        with winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(value))
        return True, ""
    except OSError as exc:
        return False, str(exc)


def _read_string(root, path: str, name: str) -> str:
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as key:
            value, _kind = winreg.QueryValueEx(key, name)
            return str(value)
    except OSError:
        return ""


def _write_string(root, path: str, name: str, value: str):
    try:
        with winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))
        return True, ""
    except OSError as exc:
        return False, str(exc)


def _broadcast_change() -> None:
    try:
        result = wintypes.DWORD()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, ctypes.c_wchar_p("Notifications"),
            SMTO_ABORTIFHUNG, 1200, ctypes.byref(result))
    except Exception:
        pass


# ------------------------------------------------------------------ 图标
def app_icon_path() -> str:
    cached = os.path.join(config.app_data_dir(), "app_icon.ico")
    if os.path.exists(cached):
        return cached
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    for candidate in (os.path.join(base, "assets", "anti_misopen.ico"),
                      os.path.join(base, "assets", "anti_misopen.png")):
        if os.path.exists(candidate):
            return candidate
    return ""


def _ensure_aumid():
    ok, detail = _write_string(HKCU, AUMID_KEY, "DisplayName", "Anti Mis Open")
    if not ok:
        return False, detail
    _write_dword(HKCU, AUMID_KEY, "ShowInSettings", 1)
    icon = app_icon_path()
    if icon:
        _write_string(HKCU, AUMID_KEY, "IconUri", icon)
    return True, ""


# ------------------------------------------------------------------ 服务
def wpn_service():
    """返回 (服务名, 是否运行中)；找不到（如 Win7）返回 (None, True)。"""
    try:
        import psutil
        for service in psutil.win_service_iter():
            try:
                name = (service.name() or "").lower()
            except Exception:
                continue
            if name.startswith("wpnuserservice") or name == "wpnservice":
                try:
                    status = service.status()
                except Exception:
                    status = "unknown"
                return service.name(), status == "running"
    except Exception:
        return None, True
    return None, True


def _start_wpn_service():
    name, running = wpn_service()
    if not name:
        return True, "此系统没有 Windows 推送服务（Win7 用气泡提示）"
    if running:
        return True, "通知服务已在运行"
    try:
        completed = subprocess.run(["sc", "start", name], capture_output=True,
                                   creationflags=CREATE_NO_WINDOW, timeout=12)
        if completed.returncode == 0:
            return True, "已启动 " + name
        text = (completed.stdout or b"").decode("mbcs", "ignore").strip()
        return False, (text or "启动服务失败，可能需要管理员权限")
    except Exception as exc:
        return False, str(exc)


# ------------------------------------------------------------------ 诊断
def diagnose() -> dict:
    checks = []

    def add(key, title, ok, detail, fixable=True, required=True):
        checks.append({"key": key, "title": title, "ok": bool(ok), "detail": detail,
                       "fixable": bool(fixable), "required": bool(required)})

    value = _read_dword(HKCU, PUSH_KEY, "ToastEnabled")
    add("toast", "系统通知总开关",
        value is None or value != 0,
        "已开启" if value is None or value != 0 else "被关闭（ToastEnabled = 0）")

    value = _read_dword(HKCU, NOTIFY_ROOT, "NOC_GLOBAL_SETTING_TOASTS_ENABLED")
    add("global", "允许应用弹出通知",
        value is None or value != 0,
        "已允许" if value is None or value != 0 else "被关闭（应用通知总开关 = 0）")

    value = _read_dword(HKCU, APP_KEY, "Enabled")
    add("app", "本软件的通知权限",
        value is None or value != 0,
        "允许弹出" if value is None or value != 0 else "被单独关闭")

    value = _read_dword(HKCU, EXPLORER_ADV, "EnableBalloonTips")
    add("balloon", "托盘气泡提示（Win7 必需）",
        value is None or value != 0,
        "已开启" if value is None or value != 0 else "被关闭", required=winutil.is_win7())

    policy = _read_dword(HKCU, POLICY_KEY, "DisableNotificationCenter")
    policy_machine = _read_dword(HKLM, POLICY_KEY, "DisableNotificationCenter")
    disabled = policy == 1 or policy_machine == 1
    add("policy", "通知中心未被策略禁用", not disabled,
        "正常" if not disabled else (
            "已被系统策略禁用" + ("（需管理员解除）" if policy_machine == 1 else "（可一键修复）")))

    display = _read_string(HKCU, AUMID_KEY, "DisplayName")
    add("aumid", "应用身份注册（通知里显示名字）",
        bool(display), "已注册为 " + display if display else "未注册，通知可能没有应用名")

    name, running = wpn_service()
    if name:
        add("service", "Windows 通知服务",
            running, "运行中" if running else "已停止，可能导致所有通知不弹出")
    else:
        add("service", "Windows 通知服务",
            True, "当前系统不需要此服务（或无法读取）", required=False)

    if winutil.is_win7():
        note = "Windows 7 使用托盘气泡提示，不需要通知中心。"
    elif winutil.is_windows():
        note = "如果仍然不弹提示，请检查“专注助手 / 请勿打扰”是否开启。"
    else:
        note = "当前系统不是 Windows，通知修复不可用。"
    required_ok = all(item["ok"] for item in checks if item["required"])
    return {"ok": required_ok, "checks": checks, "note": note,
            "admin": winutil.is_admin(), "win7": winutil.is_win7()}


# ------------------------------------------------------------------ 修复
def repair() -> dict:
    steps = []

    def step(title, action):
        try:
            ok, detail = action()
        except Exception as exc:  # 修复流程绝不中断
            ok, detail = False, str(exc)
        steps.append({"title": title, "ok": bool(ok), "detail": detail or ""})

    step("打开系统通知总开关", lambda: _write_dword(HKCU, PUSH_KEY, "ToastEnabled", 1))
    step("允许应用弹出通知",
         lambda: _write_dword(HKCU, NOTIFY_ROOT, "NOC_GLOBAL_SETTING_TOASTS_ENABLED", 1))
    step("允许通知声音",
         lambda: _write_dword(HKCU, NOTIFY_ROOT, "NOC_GLOBAL_SETTING_ALLOW_NOTIFICATION_SOUND", 1))
    step("恢复本软件的通知权限", lambda: _repair_app_permissions())
    step("开启托盘气泡提示",
         lambda: _write_dword(HKCU, EXPLORER_ADV, "EnableBalloonTips", 1))
    step("解除当前用户的策略限制", lambda: _repair_policy())
    step("注册应用身份", _ensure_aumid)
    step("启动 Windows 通知服务", _start_wpn_service)
    _broadcast_change()
    return {"steps": steps, "ok": all(item["ok"] for item in steps),
            "diagnosis": diagnose()}


def _repair_app_permissions():
    ok, detail = _write_dword(HKCU, APP_KEY, "Enabled", 1)
    _write_dword(HKCU, APP_KEY, "ShowBanner", 1)
    _write_dword(HKCU, APP_KEY, "ShowInActionCenter", 1)
    return ok, detail


def _repair_policy():
    if _read_dword(HKCU, POLICY_KEY, "DisableNotificationCenter") != 1:
        return True, "未被禁用"
    return _write_dword(HKCU, POLICY_KEY, "DisableNotificationCenter", 0)


def summary(diagnosis: dict) -> str:
    """把诊断结果变成一行用户可读的结论。"""
    if diagnosis.get("ok"):
        return "通知设置正常"
    broken = [item["title"] for item in diagnosis.get("checks", [])
              if item["required"] and not item["ok"]]
    return "发现 %d 项问题：%s" % (len(broken), "、".join(broken))
