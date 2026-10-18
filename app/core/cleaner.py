# -*- coding: utf-8 -*-
"""内存清理：参考 PCL2 / Mem Reduct 的做法，只清理工作集与系统缓存，绝不结束任何软件。

- 标准清理（无需管理员）：对当前用户有权限访问的进程调用 EmptyWorkingSet 与
  SetProcessWorkingSetSize，让不活跃的内存页交还给系统。
- 深度清理（需要管理员）：额外清空待机列表（standby list）、刷新已修改页列表，
  并重置系统文件缓存的工作集上限。
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

import psutil

# 系统信息级别：NtSetSystemInformation(SystemMemoryListInformation)
SYSTEM_MEMORY_LIST_INFORMATION = 80
MEMORY_EMPTY_WORKING_SETS = 2
MEMORY_FLUSH_MODIFIED_LIST = 3
MEMORY_PURGE_STANDBY_LIST = 4

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_SET_QUOTA = 0x0100
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002

# 这些进程绝不动（系统关键进程，清理它们没有意义，还可能引发异常）
CRITICAL_NAMES = {
    "system", "system idle process", "idle", "registry", "memory compression",
    "secure system", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "lsm.exe", "svchost.exe", "memcompression",
}

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll", use_last_error=True)

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.SetProcessWorkingSetSize.argtypes = [wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t]
kernel32.SetProcessWorkingSetSize.restype = wintypes.BOOL
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.SetSystemFileCacheSize.argtypes = [ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
kernel32.SetSystemFileCacheSize.restype = wintypes.BOOL

psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
psapi.EmptyWorkingSet.restype = wintypes.BOOL

ntdll.NtSetSystemInformation.argtypes = [wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG]
ntdll.NtSetSystemInformation.restype = wintypes.LONG

advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
advapi32.OpenProcessToken.restype = wintypes.BOOL
advapi32.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p]
advapi32.LookupPrivilegeValueW.restype = wintypes.BOOL
advapi32.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL, ctypes.c_void_p,
                                            wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
advapi32.AdjustTokenPrivileges.restype = wintypes.BOOL


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", _LUID), ("Attributes", wintypes.DWORD)]


class _TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD),
                ("Privileges", _LUID_AND_ATTRIBUTES * 1)]


def enable_privilege(name: str) -> bool:
    """尝试启用一个令牌特权；非管理员下通常返回 False。"""
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(),
                                     TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
                                     ctypes.byref(token)):
        return False
    try:
        luid = _LUID()
        if not advapi32.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
            return False
        privileges = _TOKEN_PRIVILEGES()
        privileges.PrivilegeCount = 1
        privileges.Privileges[0].Luid = luid
        privileges.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
        if not advapi32.AdjustTokenPrivileges(token, False, ctypes.byref(privileges),
                                              0, None, None):
            return False
        return ctypes.get_last_error() == 0
    finally:
        kernel32.CloseHandle(token)


def _trim_process(pid: int) -> bool:
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA,
        False, pid)
    if not handle:
        return False
    try:
        ok = bool(psapi.EmptyWorkingSet(handle))
        kernel32.SetProcessWorkingSetSize(handle, ctypes.c_size_t(-1), ctypes.c_size_t(-1))
        return ok
    finally:
        kernel32.CloseHandle(handle)


def _purge_standby_list() -> bool:
    command = wintypes.ULONG(MEMORY_PURGE_STANDBY_LIST)
    status = ntdll.NtSetSystemInformation(SYSTEM_MEMORY_LIST_INFORMATION,
                                          ctypes.byref(command),
                                          ctypes.sizeof(command))
    return status == 0


def _flush_modified_list() -> bool:
    command = wintypes.ULONG(MEMORY_FLUSH_MODIFIED_LIST)
    status = ntdll.NtSetSystemInformation(SYSTEM_MEMORY_LIST_INFORMATION,
                                          ctypes.byref(command),
                                          ctypes.sizeof(command))
    return status == 0


def _reset_file_cache() -> bool:
    return bool(kernel32.SetSystemFileCacheSize(ctypes.c_size_t(-1),
                                                ctypes.c_size_t(-1), 0))


def _used_bytes(memory) -> int:
    return int(memory.total - memory.available)


def memory_snapshot() -> dict:
    memory = psutil.virtual_memory()
    return {
        "total": int(memory.total),
        "used": _used_bytes(memory),
        "available": int(memory.available),
        "percent": float(memory.percent),
    }


def clean_memory(deep: bool = False) -> dict:
    """执行一次清理。返回清理结果，不抛异常。"""
    started = time.time()
    before = memory_snapshot()
    trimmed = 0
    denied = 0
    skipped = 0
    current_pid = psutil.Process().pid

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pid = int(proc.info["pid"])
            name = (proc.info["name"] or "").lower()
        except (psutil.Error, ValueError, TypeError):
            continue
        if pid <= 4 or pid == current_pid:
            continue
        if name in CRITICAL_NAMES:
            skipped += 1
            continue
        if _trim_process(pid):
            trimmed += 1
        else:
            denied += 1

    # 自己也清理一次，让主界面占用的内存尽快交还系统
    try:
        kernel32.SetProcessWorkingSetSize(kernel32.GetCurrentProcess(),
                                          ctypes.c_size_t(-1), ctypes.c_size_t(-1))
    except Exception:
        pass

    system_items = []
    if deep:
        enabled_profile = enable_privilege("SeProfileSingleProcessPrivilege")
        enabled_quota = enable_privilege("SeIncreaseQuotaPrivilege")
        if enabled_profile and _purge_standby_list():
            system_items.append("standby_list")
        if enabled_profile and _flush_modified_list():
            system_items.append("modified_list")
        if enabled_quota and _reset_file_cache():
            system_items.append("file_cache")

    after = memory_snapshot()
    freed = max(0, before["used"] - after["used"])
    return {
        "ok": True,
        "deep": bool(deep),
        "before": before,
        "after": after,
        "freed": int(freed),
        "trimmed": trimmed,
        "denied": denied,
        "skipped": skipped,
        "system_items": system_items,
        "elapsed": round(time.time() - started, 2),
        "timestamp": time.time(),
    }


def top_processes(limit: int = 6) -> list:
    """按内存占用排序的进程列表，用于清理页展示。"""
    items = []
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = proc.info
            memory = info.get("memory_info")
            if memory is None:
                continue
            name = info.get("name") or ""
            if not name:
                continue
            items.append((int(memory.rss), int(info["pid"]), name))
        except (psutil.Error, ValueError, TypeError):
            continue
    items.sort(reverse=True)
    result = []
    for rss, pid, name in items[:limit]:
        result.append({"pid": pid, "name": name, "rss": rss})
    return result


def format_bytes(value: float) -> str:
    value = float(max(0, value))
    units = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024.0
        index += 1
    if index == 0:
        return "%d %s" % (int(value), units[index])
    return "%.1f %s" % (value, units[index])
