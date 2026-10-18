# -*- coding: utf-8 -*-
"""规则与例外名单的匹配逻辑。"""
from __future__ import annotations

import os

DEFAULT_ACTION = "kill_notify"


def normalize_name(name: str) -> str:
    return (name or "").strip().lower()


def normalize_path(path: str) -> str:
    return os.path.normpath(path).lower() if path else ""


class AppInfo:
    """一个进程的身份信息。"""

    __slots__ = ("pid", "name", "exe", "ppid", "create_time")

    def __init__(self, pid, name, exe="", ppid=0, create_time=0.0):
        self.pid = int(pid)
        self.name = normalize_name(name)
        self.exe = normalize_path(exe)
        self.ppid = int(ppid or 0)
        self.create_time = float(create_time or 0.0)

    @property
    def identity(self) -> str:
        return self.exe or ("name:" + self.name)

    @property
    def display_name(self) -> str:
        if self.exe:
            base = os.path.basename(self.exe)
            return base or self.name
        return self.name

    def __repr__(self):
        return "AppInfo(%s, %s)" % (self.pid, self.identity)


class Matcher:
    """一条“例外 / 针对性规则”里的匹配条件。"""

    def __init__(self, kind: str = "name", value: str = "", note: str = ""):
        self.kind = kind if kind in ("name", "path") else "name"
        self.value = value or ""
        self.note = note or ""

    def to_dict(self) -> dict:
        return {"kind": self.kind, "value": self.value, "note": self.note}

    @classmethod
    def from_dict(cls, data: dict) -> "Matcher":
        return cls(data.get("kind", "name"), data.get("value", ""), data.get("note", ""))

    def matches(self, info: AppInfo) -> bool:
        if not self.value:
            return False
        if self.kind == "path":
            return bool(info.exe) and info.exe == normalize_path(self.value)
        target = normalize_name(self.value)
        return info.name == target or (info.exe and os.path.basename(info.exe) == target)


class AppRule:
    """针对性规则：对某个程序使用不同的时间窗 / 实例数 / 处理方式。"""

    def __init__(self, matcher: Matcher, window_seconds=None, max_instances=None,
                 action=None, enabled=True, note=""):
        self.matcher = matcher
        self.window_seconds = window_seconds
        self.max_instances = max_instances
        self.action = action
        self.enabled = enabled
        self.note = note

    def to_dict(self) -> dict:
        return {
            "matcher": self.matcher.to_dict(),
            "window_seconds": self.window_seconds,
            "max_instances": self.max_instances,
            "action": self.action,
            "enabled": bool(self.enabled),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppRule":
        return cls(
            Matcher.from_dict(data.get("matcher") or {}),
            data.get("window_seconds"),
            data.get("max_instances"),
            data.get("action"),
            bool(data.get("enabled", True)),
            data.get("note", ""),
        )

    def matches(self, info: AppInfo) -> bool:
        return self.enabled and self.matcher.matches(info)


def find_matching_rule(rules, info: AppInfo):
    """先按完整路径匹配，再按进程名匹配。"""
    candidates = [r for r in rules if r.enabled and r.matcher.kind == "path" and r.matcher.matches(info)]
    candidates += [r for r in rules if r.enabled and r.matcher.kind != "path" and r.matcher.matches(info)]
    return candidates[0] if candidates else None


def find_exception(exceptions, info: AppInfo):
    for matcher in exceptions:
        if matcher.matches(info):
            return matcher
    return None


def is_exception(exceptions, info: AppInfo) -> bool:
    return find_exception(exceptions, info) is not None


def resolve_action(rule, config) -> str:
    if rule is not None and rule.action:
        return rule.action
    return config.get("action") or DEFAULT_ACTION


def resolve_window(rule, config) -> float:
    if rule is not None and rule.window_seconds is not None:
        return max(0.5, float(rule.window_seconds))
    return max(0.5, float(config.get("window_seconds") or 5.0))


def resolve_max_instances(rule, config) -> int:
    if rule is not None and rule.max_instances is not None:
        return max(1, int(rule.max_instances))
    return max(1, int(config.get("max_instances") or 1))
