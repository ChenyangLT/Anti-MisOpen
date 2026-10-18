# -*- coding: utf-8 -*-
"""硬件信息读取：WMI（通过系统 PowerShell）为主，注册表与 psutil 兜底。

说明：为了兼容 Windows 7 自带的 PowerShell 2.0，脚本不使用 ConvertTo-Json，
而是输出 key=value 文本，再由 Python 解析；所有查询只读，不会修改系统设置。
"""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time

import psutil

from . import config, winutil

_PROBE_SCRIPT = r'''
$ErrorActionPreference = 'SilentlyContinue'
$out = $args[0]
$sb = New-Object System.Text.StringBuilder
function Add-Line([string]$key, $val) {
  if ($null -ne $val -and ("$val").Trim().Length -gt 0) {
    $clean = ("$val" -replace "`r", " " -replace "`n", " ").Trim()
    [void]$sb.AppendLine($key + "=" + $clean)
  }
}
function Get-Items([string]$cls) {
  if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
    return @(Get-CimInstance -ClassName $cls -ErrorAction SilentlyContinue)
  }
  return @(Get-WmiObject -Class $cls -ErrorAction SilentlyContinue)
}
function Fmt-Size($bytes) {
  if ($null -eq $bytes -or [double]$bytes -le 0) { return "" }
  $g = [double]$bytes / 1GB
  if ($g -ge 1) { return ("{0:N1} GB" -f $g) }
  return ("{0:N0} MB" -f ([double]$bytes / 1MB))
}
function Fmt-Date($value) {
  if ($null -eq $value) { return "" }
  try {
    if ($value -is [datetime]) { return $value.ToString("yyyy-MM-dd") }
    $text = "$value"
    if ($text -match '^\d{4}-\d{2}-\d{2}') { return $text.Substring(0, 10) }
    if ($text.Length -ge 8 -and $text -match '^\d{8}') {
      return [Management.ManagementDateTimeConverter]::ToDateTime($text).ToString("yyyy-MM-dd")
    }
  } catch { }
  return ""
}
function Fmt-Resolution($w, $h) {
  if ($null -eq $w -or $null -eq $h) { return "" }
  if ([int]$w -le 0 -or [int]$h -le 0) { return "" }
  return ("{0}x{1}" -f [int]$w, [int]$h)
}
$i = 0
foreach ($c in @(Get-Items "Win32_Processor")) {
  Add-Line ("cpu." + $i + ".name") $c.Name
  Add-Line ("cpu." + $i + ".cores") $c.NumberOfCores
  Add-Line ("cpu." + $i + ".threads") $c.NumberOfLogicalProcessors
  Add-Line ("cpu." + $i + ".clock") $c.MaxClockSpeed
  Add-Line ("cpu." + $i + ".socket") $c.SocketDesignation
  $i++
}
$i = 0
foreach ($b in @(Get-Items "Win32_BaseBoard")) {
  Add-Line ("board." + $i + ".manufacturer") $b.Manufacturer
  Add-Line ("board." + $i + ".product") $b.Product
  Add-Line ("board." + $i + ".version") $b.Version
  $i++
}
$i = 0
foreach ($b in @(Get-Items "Win32_BIOS")) {
  Add-Line ("bios." + $i + ".vendor") $b.Manufacturer
  Add-Line ("bios." + $i + ".version") (("$($b.SMBIOSBIOSVersion) $($b.Version)").Trim())
  Add-Line ("bios." + $i + ".date") (Fmt-Date $b.ReleaseDate)
  $i++
}
$i = 0
foreach ($r in @(Get-Items "Win32_PhysicalMemory")) {
  Add-Line ("ram." + $i + ".capacity") (Fmt-Size $r.Capacity)
  Add-Line ("ram." + $i + ".speed") $r.Speed
  Add-Line ("ram." + $i + ".manufacturer") $r.Manufacturer
  Add-Line ("ram." + $i + ".part") $r.PartNumber
  $slot = "$($r.DeviceLocator)"
  if ($slot.Trim().Length -eq 0) { $slot = "$($r.BankLabel)" }
  Add-Line ("ram." + $i + ".slot") $slot
  $i++
}
$i = 0
foreach ($g in @(Get-Items "Win32_VideoController")) {
  Add-Line ("gpu." + $i + ".name") $g.Name
  Add-Line ("gpu." + $i + ".vram") (Fmt-Size $g.AdapterRAM)
  Add-Line ("gpu." + $i + ".driver") $g.DriverVersion
  Add-Line ("gpu." + $i + ".resolution") (Fmt-Resolution $g.CurrentHorizontalResolution $g.CurrentVerticalResolution)
  $i++
}
$i = 0
foreach ($d in @(Get-Items "Win32_DiskDrive")) {
  Add-Line ("disk." + $i + ".model") $d.Model
  Add-Line ("disk." + $i + ".size") (Fmt-Size $d.Size)
  Add-Line ("disk." + $i + ".interface") $d.InterfaceType
  Add-Line ("disk." + $i + ".media") $d.MediaType
  $i++
}
$i = 0
foreach ($m in @(Get-Items "Win32_DesktopMonitor")) {
  Add-Line ("monitor." + $i + ".name") $m.Name
  Add-Line ("monitor." + $i + ".size") (Fmt-Resolution $m.ScreenWidth $m.ScreenHeight)
  $i++
}
$i = 0
foreach ($n in @(Get-Items "Win32_NetworkAdapter" | Where-Object { $_.PhysicalAdapter -eq $true })) {
  Add-Line ("net." + $i + ".name") $n.Name
  Add-Line ("net." + $i + ".mac") $n.MACAddress
  Add-Line ("net." + $i + ".speed") $n.Speed
  $i++
}
foreach ($o in @(Get-Items "Win32_OperatingSystem")) {
  Add-Line ("os.caption") $o.Caption
  Add-Line ("os.version") $o.Version
  Add-Line ("os.build") $o.BuildNumber
  Add-Line ("os.arch") $o.OSArchitecture
}
[IO.File]::WriteAllText($out, $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))
exit 0
'''


def cache_path() -> str:
    return os.path.join(config.app_data_dir(), "hardware.json")


def _powershell_exe() -> str:
    root = os.environ.get("SystemRoot") or r"C:\Windows"
    candidate = os.path.join(root, "System32", "WindowsPowerShell", "v1.0",
                             "powershell.exe")
    if os.path.isfile(candidate):
        return candidate
    return "powershell.exe"


def _run_probe(timeout: float = 25.0):
    temp_dir = tempfile.mkdtemp(prefix="antimisopen-hw-")
    script_path = os.path.join(temp_dir, "probe.ps1")
    output_path = os.path.join(temp_dir, "probe.txt")
    try:
        with open(script_path, "w", encoding="ascii", errors="replace") as handle:
            handle.write(_PROBE_SCRIPT)
        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        subprocess.run(
            [_powershell_exe(), "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", script_path, output_path],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=timeout, creationflags=flags,
            check=False)
        if not os.path.isfile(output_path):
            return {}
        raw = open(output_path, "rb").read()
        for encoding in ("utf-8-sig", "gbk", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw.decode("latin-1", "replace")
        result = {}
        for line in text.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                result[key] = value
        return result
    except Exception:
        return {}
    finally:
        for name in ("probe.ps1", "probe.txt"):
            try:
                os.remove(os.path.join(temp_dir, name))
            except OSError:
                pass
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass


def _grouped(raw: dict):
    """把 key=value 展平成 groups：{"cpu": {0: {...}}, "gpu": {1: {...}}}。"""
    groups = {}
    for key, value in raw.items():
        parts = key.split(".")
        if len(parts) != 3:
            continue
        group, index, field = parts
        try:
            index = int(index)
        except ValueError:
            continue
        groups.setdefault(group, {}).setdefault(index, {})[field] = value
    return groups


def _fmt_clock(mhz: str) -> str:
    try:
        value = float(mhz)
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return ""
    if value >= 1000:
        return "%.2f GHz" % (value / 1000.0)
    return "%.0f MHz" % value


def _fmt_date(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) >= 8:
        return "%s-%s-%s" % (digits[0:4], digits[4:6], digits[6:8])
    return ""


def _fmt_speed(bps: str) -> str:
    try:
        value = float(bps)
    except (TypeError, ValueError):
        return ""
    if value <= 0:
        return ""
    if value >= 1e9:
        return "%.1f Gbps" % (value / 1e9)
    if value >= 1e6:
        return "%.0f Mbps" % (value / 1e6)
    return "%.0f Kbps" % (value / 1e3)


def _fmt_gb(value: float, digits: int = 1) -> str:
    return ("%." + str(digits) + "f GB") % (value / float(1024 ** 3))


def _windows_build() -> str:
    """返回 Windows 内部版本号与显示版本（Win7 起均可用）。"""
    if os.name != "nt":
        return ""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        try:
            build = str(winreg.QueryValueEx(key, "CurrentBuildNumber")[0] or "")
            try:
                display = str(winreg.QueryValueEx(key, "DisplayVersion")[0] or "")
            except OSError:
                display = ""
        finally:
            winreg.CloseKey(key)
        pieces = [p for p in (display, build) if p]
        return " · ".join(pieces)
    except Exception:
        return ""


def _cpu_from_registry() -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        try:
            name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
        finally:
            winreg.CloseKey(key)
        return str(name or "").strip()
    except Exception:
        return ""


def collect_groups(force_wmi: bool = True) -> dict:
    """读取硬件信息，返回 {"generated_at": ..., "groups": [{"title", "rows"}]}。"""
    raw = _run_probe() if force_wmi else {}
    groups = _grouped(raw)
    result = []

    def add(title, rows):
        rows = [(str(label), str(value)) for label, value in rows if value]
        if rows:
            result.append({"title": title, "rows": rows})

    # ---- 处理器
    cpu_rows = []
    cpus = groups.get("cpu") or {}
    if cpus:
        first = cpus[min(cpus)]
        model = first.get("name") or _cpu_from_registry() or platform.processor() or "未知"
        cpu_rows.append(("型号", model))
        cores = first.get("cores") or ""
        threads = first.get("threads") or str(psutil.cpu_count(logical=True) or "")
        if cores and threads:
            cpu_rows.append(("核心 / 线程", "%s 核 %s 线程" % (cores, threads)))
        elif threads:
            cpu_rows.append(("线程", threads))
        clock = _fmt_clock(first.get("clock") or "")
        if clock:
            cpu_rows.append(("最高频率", clock))
        if first.get("socket"):
            cpu_rows.append(("插槽", first["socket"]))
    else:
        model = _cpu_from_registry() or platform.processor() or "未知"
        cpu_rows.append(("型号", model))
        physical = psutil.cpu_count(logical=False) or 0
        logical = psutil.cpu_count(logical=True) or 0
        if physical or logical:
            cpu_rows.append(("核心 / 线程", "%d 核 %d 线程" % (physical, logical)))
    add("处理器", cpu_rows)

    # ---- 主板 / BIOS
    boards = groups.get("board") or {}
    if boards:
        board = boards[min(boards)]
        name = " ".join(part for part in (
            board.get("manufacturer", ""), board.get("product", "")) if part).strip()
        rows = []
        if name:
            rows.append(("型号", name))
        if board.get("version"):
            rows.append(("版本", board["version"]))
        add("主板", rows)
    bioses = groups.get("bios") or {}
    if bioses:
        bios = bioses[min(bioses)]
        add("BIOS", [
            ("厂商", bios.get("vendor", "")),
            ("版本", bios.get("version", "")),
            ("日期", _fmt_date(bios.get("date", ""))),
        ])

    # ---- 内存
    memory = psutil.virtual_memory()
    mem_rows = [("总容量", _fmt_gb(memory.total, 1))]
    modules = groups.get("ram") or {}
    for index in sorted(modules):
        module = modules[index]
        capacity = module.get("capacity", "")
        speed = module.get("speed", "")
        maker = module.get("manufacturer", "")
        part = module.get("part", "")
        pieces = [capacity]
        if speed:
            pieces.append("%s MHz" % speed)
        if maker:
            pieces.append(maker)
        if part and part not in ("", "None"):
            pieces.append(part)
        label = module.get("slot") or "内存条 %d" % (index + 1)
        mem_rows.append((label, " · ".join(p for p in pieces if p)))
    add("内存", mem_rows)

    # ---- 显卡
    gpus = groups.get("gpu") or {}
    gpu_rows = []
    for index in sorted(gpus):
        gpu = gpus[index]
        prefix = "显卡" if len(gpus) == 1 else "显卡 %d" % (index + 1)
        gpu_rows.append((prefix, gpu.get("name", "")))
        extra = []
        if gpu.get("vram"):
            extra.append("显存 " + gpu["vram"])
        resolution = (gpu.get("resolution") or "").strip()
        if resolution and resolution not in ("x", "0x0"):
            extra.append(resolution)
        if extra:
            gpu_rows.append((prefix + " 详情", " · ".join(extra)))
        if gpu.get("driver"):
            gpu_rows.append((prefix + " 驱动", gpu["driver"]))
    add("显卡", gpu_rows)

    # ---- 硬盘
    disk_rows = []
    disks = groups.get("disk") or {}
    for index in sorted(disks):
        disk = disks[index]
        pieces = [disk.get("model", ""), disk.get("size", "")]
        if disk.get("interface"):
            pieces.append(disk["interface"])
        disk_rows.append(("磁盘 %d" % (index + 1), " · ".join(p for p in pieces if p)))
    try:
        for part in psutil.disk_partitions(all=False):
            if "cdrom" in (part.opts or ""):
                continue
            if not part.fstype:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except Exception:
                continue
            disk_rows.append((part.device.rstrip("\\"),
                              "已用 %s / %s · 剩余 %s" % (
                                  _fmt_gb(usage.used), _fmt_gb(usage.total),
                                  _fmt_gb(usage.free))))
    except Exception:
        pass
    add("硬盘与分区", disk_rows)

    # ---- 显示器
    monitors = groups.get("monitor") or {}
    monitor_rows = []
    for index in sorted(monitors):
        monitor = monitors[index]
        name = (monitor.get("name") or "").strip()
        size = (monitor.get("size") or "").strip()
        if size in ("x", "0x0"):
            size = ""
        pieces = [name, size]
        if not name and not size:
            continue
        monitor_rows.append(("显示器 %d" % (index + 1),
                             " · ".join(p for p in pieces if p)))
    add("显示器", monitor_rows)

    # ---- 网络
    nets = groups.get("net") or {}
    net_rows = []
    for index in sorted(nets):
        net = nets[index]
        pieces = []
        if net.get("mac"):
            pieces.append(net["mac"])
        speed = _fmt_speed(net.get("speed", ""))
        if speed:
            pieces.append(speed)
        if net.get("name"):
            net_rows.append((net["name"], " · ".join(pieces)))
    add("网络适配器", net_rows)

    # ---- 系统
    boot = psutil.boot_time()
    uptime = max(0, time.time() - boot)
    hours, remainder = divmod(int(uptime), 3600)
    minutes = remainder // 60
    os_caption = ""
    os_group = groups.get("os")
    os_rows = []
    if os_group:
        first_os = os_group[min(os_group)]
        os_caption = first_os.get("caption", "")
        if first_os.get("version"):
            os_rows.append(("版本", first_os["version"]))
        if first_os.get("build"):
            os_rows.append(("内部版本", first_os["build"]))
        if first_os.get("arch"):
            os_rows.append(("架构", first_os["arch"]))
    build = _windows_build()
    if build and not any(label == "内部版本" for label, _ in os_rows):
        os_rows.append(("内部版本", build))
    if not any(label == "架构" for label, _ in os_rows):
        machine = platform.machine() or ""
        if machine:
            arch = "64 位" if "64" in machine else "32 位"
            os_rows.append(("架构", arch))
    add("操作系统", [
        ("系统", os_caption or winutil.windows_label()),
        ("计算机名", platform.node()),
    ] + os_rows + [
        ("运行时长", ("%d 天 " % (hours // 24) if hours >= 24 else "") +
         "%d 小时 %d 分钟" % (hours % 24, minutes)),
    ])

    return {"generated_at": time.time(), "groups": result, "source": "wmi" if raw else "fallback"}


def save_cache(data: dict) -> None:
    try:
        path = cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temp = path + ".tmp"
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=1)
        os.replace(temp, path)
    except Exception:
        pass


def load_cache():
    try:
        with open(cache_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and isinstance(data.get("groups"), list):
            return data
    except Exception:
        pass
    return None


def collect_and_cache() -> dict:
    data = collect_groups()
    if data.get("groups"):
        save_cache(data)
    return data
