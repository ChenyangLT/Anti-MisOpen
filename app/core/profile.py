# -*- coding: utf-8 -*-
"""作者头像与 GitHub 信息。

默认从 GitHub 镜像服务器读取头像（学校网络经常连不上 github.com），成功一次
就缓存到本地；之后即使断网也能直接显示。全部失败时由界面画一个占位头像，
不影响软件其它功能。
"""
from __future__ import annotations

import json
import os
import time
from urllib.request import Request, urlopen

from . import config

LOGIN = config.GITHUB_LOGIN
MODEL = config.MODEL_SIGNATURE
CACHE_TTL = 7 * 86400
TIMEOUT = 6
MAX_BYTES = 3 * 1024 * 1024

# 国内可直连的 GitHub 镜像，按可用性排序；最后再试官方地址
MIRRORS = (
    ("ghproxy 镜像", "https://ghproxy.net/https://github.com/{login}.png?size=200"),
    ("ghfast 镜像", "https://ghfast.top/https://github.com/{login}.png?size=200"),
    ("gh-proxy 镜像", "https://gh-proxy.com/https://github.com/{login}.png?size=200"),
    ("GitHub 官方", "https://github.com/{login}.png?size=200"),
)

_MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")


def cache_paths():
    base = config.app_data_dir()
    return os.path.join(base, "avatar.png"), os.path.join(base, "avatar.json")


def _read_meta() -> dict:
    _png, meta_path = cache_paths()
    try:
        with open(meta_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def _write_cache(data: bytes, source: str) -> None:
    png_path, meta_path = cache_paths()
    try:
        os.makedirs(os.path.dirname(png_path), exist_ok=True)
        temp = png_path + ".tmp"
        with open(temp, "wb") as handle:
            handle.write(data)
        os.replace(temp, png_path)
        meta = {"login": LOGIN, "source": source, "fetched_at": int(time.time())}
        temp_meta = meta_path + ".tmp"
        with open(temp_meta, "w", encoding="utf-8") as handle:
            json.dump(meta, handle, ensure_ascii=False)
        os.replace(temp_meta, meta_path)
    except OSError:
        pass


def load_cached() -> dict:
    """读取本地缓存，返回 {"ok","data","source","cached","fetched_at"}。"""
    png_path, _meta_path = cache_paths()
    meta = _read_meta()
    try:
        with open(png_path, "rb") as handle:
            data = handle.read()
    except OSError:
        return {"ok": False, "data": None, "source": "内置占位",
                "cached": False, "fetched_at": 0}
    if not data:
        return {"ok": False, "data": None, "source": "内置占位",
                "cached": False, "fetched_at": 0}
    return {"ok": True, "data": data,
            "source": meta.get("source") or "本地缓存",
            "cached": True, "fetched_at": int(meta.get("fetched_at") or 0)}


def _offline() -> bool:
    return os.environ.get("ANTIMISOPEN_OFFLINE", "") == "1"


def _valid_image(data: bytes) -> bool:
    return bool(data) and any(data.startswith(magic) for magic in _MAGIC)


def fetch_avatar(force: bool = False) -> dict:
    """获取头像。force=False 时优先使用 7 天内的缓存，避免每次启动都联网。"""
    cached = load_cached()
    age = time.time() - (cached.get("fetched_at") or 0)
    if cached["ok"] and not force and age < CACHE_TTL:
        cached["fresh"] = True
        return cached
    if _offline():
        cached["error"] = "离线模式"
        return cached

    errors = []
    for label, template in MIRRORS:
        url = template.format(login=LOGIN)
        try:
            request = Request(url, headers={
                "User-Agent": "AntiMisOpen/%s" % config.APP_VERSION,
                "Accept": "image/png,image/*;q=0.8",
            })
            with urlopen(request, timeout=TIMEOUT) as response:
                data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                errors.append("%s：图片过大" % label)
                continue
            if not _valid_image(data):
                errors.append("%s：返回的不是图片" % label)
                continue
            _write_cache(data, label)
            return {"ok": True, "data": data, "source": label, "cached": False,
                    "fetched_at": int(time.time()), "fresh": True, "error": ""}
        except Exception as exc:  # 网络错误种类很多，统一记录后换下一个镜像
            errors.append("%s：%s" % (label, exc))

    if cached["ok"]:
        cached["error"] = "；".join(errors[:2])
        cached["fresh"] = False
        return cached
    return {"ok": False, "data": None, "source": "内置占位", "cached": False,
            "fetched_at": 0, "fresh": False,
            "error": "；".join(errors[:2]) or "网络不可用"}


def display_name() -> str:
    return LOGIN


def subtitle() -> str:
    return MODEL


def source_text(result: dict) -> str:
    if not result:
        return "内置占位头像"
    if not result.get("ok"):
        return "暂时没取到头像：%s" % (result.get("error") or "网络不可用")
    source = result.get("source") or "本地缓存"
    if result.get("cached"):
        return "头像来自本地缓存（%s）" % source
    return "头像来自 %s" % source
