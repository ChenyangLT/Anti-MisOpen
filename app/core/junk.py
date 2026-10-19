# -*- coding: utf-8 -*-
"""垃圾清理：回收站、临时文件、下载 / 图片 / 视频文件夹、自定义目录。

只删除这些目录“里面的内容”，不会删除目录本身；下载、图片、视频和自定义
目录默认先移到回收站（可恢复），点“清空回收站”才真正释放磁盘空间。
清理时可以额外选择“只删 7 天以前的文件”，最近还在用的文件会被跳过。
"""
from __future__ import annotations

import ctypes
import os
import shutil
import tempfile
import time
from ctypes import wintypes

FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FO_DELETE = 3
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040
FOF_NOERRORUI = 0x0400
SHERB_NOCONFIRMATION = 0x00000001
SHERB_NOPROGRESSUI = 0x00000002
SHERB_NOSOUND = 0x00000004

# “保留 7 天内的文件”用的时间门槛
KEEP_DAYS = 7


class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD),
                ("i64Size", ctypes.c_longlong),
                ("i64NumItems", ctypes.c_longlong)]


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND),
                ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR),
                ("fFlags", wintypes.WORD),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", wintypes.LPCWSTR)]


_shell32 = None
try:
    _shell32 = ctypes.windll.shell32
    _shell32.SHQueryRecycleBinW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(_SHQUERYRBINFO)]
    _shell32.SHQueryRecycleBinW.restype = ctypes.c_long
    _shell32.SHEmptyRecycleBinW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.DWORD]
    _shell32.SHEmptyRecycleBinW.restype = ctypes.c_long
    _shell32.SHFileOperationW.argtypes = [ctypes.POINTER(_SHFILEOPSTRUCTW)]
    _shell32.SHFileOperationW.restype = ctypes.c_int
except Exception:
    _shell32 = None


CATEGORIES = [
    {"id": "recycle", "title": "回收站", "hint": "清空后无法恢复，能立刻腾出磁盘空间",
     "personal": False, "default": True},
    {"id": "temp", "title": "临时文件", "hint": "系统和软件产生的临时文件，直接删除",
     "personal": False, "default": True},
    {"id": "downloads", "title": "下载文件夹", "hint": "下载目录里的全部文件和文件夹",
     "personal": True, "default": False},
    {"id": "pictures", "title": "图片文件夹", "hint": "图片目录里的全部文件和文件夹",
     "personal": True, "default": False},
    {"id": "videos", "title": "视频文件夹", "hint": "视频目录里的全部文件和文件夹",
     "personal": True, "default": False},
    {"id": "custom", "title": "自定义目录", "hint": "你自己添加的文件夹，比如桌面或班级资料盘",
     "personal": True, "default": False},
]

CATEGORY_BY_ID = {item["id"]: item for item in CATEGORIES}


def _user_dir(name: str) -> str:
    return os.path.join(os.path.expanduser("~"), name)


def _temp_dirs():
    paths = []
    for candidate in (tempfile.gettempdir(),
                      os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Temp")):
        if candidate and os.path.isdir(candidate) and candidate not in paths:
            paths.append(candidate)
    return paths


# ------------------------------------------------------------------ 自定义目录
def normalize_dirs(dirs) -> list:
    """去掉空项、重复项，并跳过已经被父目录覆盖的子目录。"""
    cleaned = []
    for raw in dirs or []:
        try:
            path = os.path.normpath(str(raw))
        except Exception:
            continue
        if not path or path in cleaned:
            continue
        cleaned.append(path)
    # 父目录已经在列表里时，子目录重复统计 / 重复删除没有意义
    result = []
    for path in sorted(cleaned, key=len):
        if any(path == kept or path.startswith(kept.rstrip("\\/") + os.sep)
               for kept in result):
            continue
        result.append(path)
    return result


def custom_dir_details(custom_dirs) -> list:
    details = []
    for path in normalize_dirs(custom_dirs):
        exists = os.path.isdir(path)
        size, count = _dir_stats(path) if exists else (0, 0)
        details.append({"path": path, "bytes": size, "items": count, "exists": exists})
    return details


# ------------------------------------------------------------------ 统计
def recycle_stats():
    if _shell32 is None:
        return 0, 0
    info = _SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(_SHQUERYRBINFO)
    try:
        if _shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) == 0:
            return int(info.i64Size), int(info.i64NumItems)
    except Exception:
        pass
    return 0, 0


def _dir_stats(path: str):
    total = 0
    items = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            try:
                stat = entry.stat(follow_symlinks=False)
                if stat.st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                else:
                    total += int(stat.st_size)
                    items += 1
            except OSError:
                continue
    return total, items


def category_stats(category_id: str, custom_dirs=None):
    if category_id == "recycle":
        return recycle_stats()
    if category_id == "temp":
        total = 0
        items = 0
        for path in _temp_dirs():
            part = _dir_stats(path)
            total += part[0]
            items += part[1]
        return total, items
    if category_id == "custom":
        total = 0
        items = 0
        for item in custom_dir_details(custom_dirs):
            total += item["bytes"]
            items += item["items"]
        return total, items
    if category_id in ("downloads", "pictures", "videos"):
        path = _user_dir({"downloads": "Downloads", "pictures": "Pictures",
                          "videos": "Videos"}[category_id])
        if os.path.isdir(path):
            return _dir_stats(path)
    return 0, 0


def scan(custom_dirs=None) -> dict:
    result = {}
    total = 0
    items = 0
    for category in CATEGORIES:
        size, count = category_stats(category["id"], custom_dirs)
        result[category["id"]] = {"bytes": size, "items": count}
        total += size
        items += count
    return {"categories": result, "total_bytes": total, "total_items": items,
            "custom_dirs": custom_dir_details(custom_dirs)}


# ------------------------------------------------------------------ 删除
def _remove_path(path: str):
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return True
    except OSError:
        return False


def _recycle_path(path: str) -> bool:
    if _shell32 is None:
        return False
    operation = _SHFILEOPSTRUCTW()
    operation.hwnd = None
    operation.wFunc = FO_DELETE
    operation.pFrom = path + "\0\0"
    operation.pTo = None
    operation.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    try:
        result = _shell32.SHFileOperationW(ctypes.byref(operation))
        return result == 0 and not operation.fAnyOperationsAborted
    except Exception:
        return False


def _clean_tree(path: str, cutoff: float, result: dict):
    """保留模式：递归删除修改时间早于 cutoff 的文件，最近用过的文件原样留下。"""
    for folder, dirs, files in os.walk(path, topdown=False):
        for name in files:
            full = os.path.join(folder, name)
            try:
                mtime = os.path.getmtime(full)
            except OSError:
                continue
            if mtime >= cutoff:
                result["kept"] += 1
                continue
            if _remove_path(full):
                result["removed"] += 1
            else:
                result["failed"] += 1
                result["errors"].append(full)
        for name in dirs:
            full = os.path.join(folder, name)
            try:
                if not os.listdir(full):
                    os.rmdir(full)
            except OSError:
                pass


def _clean_dir(path: str, use_recycle: bool, result: dict, keep_days: int = 0):
    try:
        entries = list(os.scandir(path))
    except OSError as exc:
        result["errors"].append("%s：%s" % (path, exc))
        return
    cutoff = time.time() - keep_days * 86400 if keep_days else 0
    if cutoff:
        _clean_tree(path, cutoff, result)
        return
    for entry in entries:
        try:
            stat = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        if cutoff and stat.st_mtime >= cutoff:
            # 最近还在使用的文件，保留
            result["kept"] += 1
            continue
        if use_recycle:
            if _recycle_path(entry.path):
                result["moved"] += 1
            else:
                result["failed"] += 1
                result["errors"].append(entry.path)
        else:
            if _remove_path(entry.path):
                result["removed"] += 1
            else:
                result["failed"] += 1
                result["errors"].append(entry.path)


def empty_recycle_bin() -> bool:
    if _shell32 is None:
        return False
    flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    try:
        return _shell32.SHEmptyRecycleBinW(None, None, flags) == 0
    except Exception:
        return False


def _category_paths(category_id: str, custom_dirs=None) -> list:
    if category_id == "temp":
        return _temp_dirs()
    if category_id == "custom":
        return [item["path"] for item in custom_dir_details(custom_dirs)
                if item["exists"]]
    if category_id in ("downloads", "pictures", "videos"):
        path = _user_dir({"downloads": "Downloads", "pictures": "Pictures",
                          "videos": "Videos"}[category_id])
        return [path] if os.path.isdir(path) else []
    return []


def clean(selected_ids, use_recycle: bool = True, custom_dirs=None,
          keep_days: int = 0) -> dict:
    selected = [cid for cid in selected_ids if cid in CATEGORY_BY_ID]
    before = {cid: category_stats(cid, custom_dirs)[0] for cid in selected}
    result = {"freed": 0, "removed": 0, "moved": 0, "failed": 0, "kept": 0,
              "skipped_recycle": False, "errors": [], "categories": {},
              "custom_dirs": []}

    for category_id in selected:
        category = CATEGORY_BY_ID[category_id]
        if category_id == "recycle":
            if keep_days:
                # 回收站接口无法按时间过滤，保留模式下先跳过，避免误删最近删掉的文件
                result["skipped_recycle"] = True
                result["categories"][category_id] = {"freed": 0, "skipped": True}
                continue
            ok = empty_recycle_bin()
            after_size, _after_items = recycle_stats()
            freed = max(0, before.get(category_id, 0) - after_size)
            result["freed"] += freed
            result["categories"][category_id] = {"freed": freed, "ok": ok}
            if not ok:
                result["failed"] += 1
                result["errors"].append("清空回收站失败（可能被占用）")
            continue

        paths = _category_paths(category_id, custom_dirs)
        # 保留模式下直接删除，保证真的能腾出空间；普通模式按个人文件走回收站
        recycled = bool(category["personal"] and use_recycle and not keep_days)
        for path in paths:
            _clean_dir(path, recycled, result, keep_days)

        after_size = category_stats(category_id, custom_dirs)[0]
        freed = max(0, before.get(category_id, 0) - after_size)
        if not recycled:
            result["freed"] += freed
        result["categories"][category_id] = {"freed": 0 if recycled else freed,
                                             "recycled": recycled}

    result["custom_dirs"] = custom_dir_details(custom_dirs)
    if not selected:
        result["errors"].append("没有选择要清理的内容")
    return result
