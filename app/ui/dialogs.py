# -*- coding: utf-8 -*-
"""通用对话框：添加例外、添加规则、选择程序、设置密码、确认、暂停。"""
from __future__ import annotations

import os

import psutil
from PySide2.QtCore import QPoint, Qt
from PySide2.QtGui import QColor, QFont, QPainter, QPen
from PySide2.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from ..core import config, themes, winutil
from ..core.rules import Matcher, normalize_name, normalize_path
from .icons import to_color
from .widgets import (IconView, SegmentedControl, Stepper, WindowButton,
                      make_label, with_alpha)


class BaseDialog(QDialog):
    """无边框圆角对话框基类。"""

    def __init__(self, parent=None, title: str = "", subtitle: str = "",
                 width: int = 460, ok_text: str = "确定", cancel_text: str = "取消",
                 tone: str = "primary"):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setWindowTitle(title)
        self.setFixedWidth(width)
        self._drag_offset = None
        self._centered = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._card = QFrame(self)
        self._card.setObjectName("DialogCard")
        outer.addWidget(self._card)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        self._title_label = make_label(title, "h2")
        self._subtitle_label = make_label(subtitle, "muted", wrap=True)
        self._subtitle_label.setVisible(bool(subtitle))
        titles.addWidget(self._title_label)
        titles.addWidget(self._subtitle_label)
        head.addLayout(titles, 1)
        close_button = WindowButton("close", danger=True)
        close_button.clicked.connect(self.reject)
        head.addWidget(close_button, 0, Qt.AlignTop)
        card_layout.addLayout(head)

        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        card_layout.addLayout(self.body)

        self._error = make_label("", "faint", wrap=True)
        self._error.setStyleSheet("color: %s; font-size: 8.5pt;" % themes.current()["danger"])
        self._error.setVisible(False)
        card_layout.addWidget(self._error)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addStretch(1)
        self._cancel_button = QPushButton(cancel_text)
        self._cancel_button.setProperty("variant", "ghost")
        self._cancel_button.clicked.connect(self.reject)
        footer.addWidget(self._cancel_button)
        self._ok_button = QPushButton(ok_text)
        self._ok_button.setProperty("variant", tone)
        self._ok_button.setDefault(True)
        self._ok_button.clicked.connect(self._on_ok)
        footer.addWidget(self._ok_button)
        card_layout.addLayout(footer)

    # ---------------------------------------------------------- 基础行为
    def set_error(self, text: str) -> None:
        self._error.setText(text)
        self._error.setVisible(bool(text))

    def validate(self) -> bool:
        return True

    def _on_ok(self) -> None:
        self.set_error("")
        if self.validate():
            self.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = themes.current()
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(Qt.NoPen)
        shadow = QColor(palette["shadow"])
        shadow.setAlpha(46)
        painter.setBrush(shadow)
        painter.drawRoundedRect(rect.adjusted(2, 4, 2, 4), 17, 17)
        painter.setPen(QPen(to_color(palette["border"]), 1.0))
        painter.setBrush(to_color(palette["card"]))
        painter.drawRoundedRect(rect, 16, 16)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._centered:
            self._centered = True
            parent = self.parentWidget()
            self.adjustSize()
            if parent is not None:
                center = parent.mapToGlobal(parent.rect().center())
                self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() < 74:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


def _field_label(text: str) -> QLabel:
    label = make_label(text, "muted")
    label.setStyleSheet("font-size: 8.5pt; font-weight: 600;")
    return label


class AddTargetDialog(BaseDialog):
    """添加例外程序 / 自定义规则。"""

    KINDS = [("name", "按程序名"), ("path", "按完整路径")]
    RULE_ACTIONS = [("inherit", "跟随全局"), ("kill_silent", "静默结束"),
                    ("kill_notify", "结束并提示"), ("notify_only", "只提示")]

    def __init__(self, parent=None, mode: str = "exception", default: dict = None,
                 global_window: float = 5.0, global_max: int = 1):
        default = default or {}
        is_rule = mode == "rule"
        title = "添加自定义规则" if is_rule else "添加例外程序"
        subtitle = ("对指定程序使用单独的判定参数" if is_rule
                    else "例外名单里的程序不会被拦截，可以正常多开")
        super().__init__(parent, title, subtitle, width=470, ok_text="添加")
        self.mode = mode
        self.result_data = None

        self.body.addWidget(_field_label("匹配方式"))
        kind = default.get("kind", "name")
        if kind not in ("name", "path"):
            kind = "name"
        self._kind = SegmentedControl(self.KINDS, kind)
        self._kind.changed.connect(lambda _v: self._sync_placeholder())
        self.body.addWidget(self._kind)

        self.body.addWidget(_field_label("程序名或路径"))
        self._value = QLineEdit()
        self._value.returnPressed.connect(self._on_ok)
        self.body.addWidget(self._value)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._browse = QPushButton("选择正在运行的程序")
        self._browse.setProperty("variant", "ghost")
        self._browse.clicked.connect(self._pick_process)
        row.addWidget(self._browse)
        row.addStretch(1)
        self.body.addLayout(row)

        self.body.addWidget(_field_label("备注（可选）"))
        self._note = QLineEdit()
        self.body.addWidget(self._note)

        self._window_stepper = None
        self._max_stepper = None
        self._action = None
        if is_rule:
            option_row = QHBoxLayout()
            option_row.setSpacing(16)
            left = QVBoxLayout()
            left.setSpacing(4)
            left.addWidget(_field_label("判定时间窗（秒）"))
            self._window_stepper = Stepper(float(default.get("window_seconds") or global_window),
                                           1.0, 60.0, 1.0, 0, " 秒")
            left.addWidget(self._window_stepper)
            option_row.addLayout(left)
            right = QVBoxLayout()
            right.setSpacing(4)
            right.addWidget(_field_label("实例上限"))
            self._max_stepper = Stepper(float(default.get("max_instances") or global_max),
                                        1.0, 20.0, 1.0, 0, " 个")
            right.addWidget(self._max_stepper)
            option_row.addLayout(right)
            option_row.addStretch(1)
            self.body.addLayout(option_row)

            self.body.addWidget(_field_label("处理方式"))
            current = default.get("action") or "inherit"
            self._action = SegmentedControl(self.RULE_ACTIONS, current)
            self.body.addWidget(self._action)

        values = default.get("matcher") or {}
        self._value.setText(str(values.get("value") or default.get("value") or ""))
        self._note.setText(str(default.get("note") or ""))
        self._sync_placeholder()
        self.adjustSize()

    def _sync_placeholder(self) -> None:
        if self._kind.value() == "path":
            self._value.setPlaceholderText(r"C:\Program Files\App\app.exe")
        else:
            self._value.setPlaceholderText("chrome.exe")

    def _pick_process(self) -> None:
        dialog = ProcessPickerDialog(self, title="选择程序",
                                     subtitle="从正在运行的程序中选择一个")
        if dialog.exec_() == QDialog.Accepted and dialog.selected:
            exe, name = dialog.selected
            self._kind.setValue("path")
            self._value.setText(exe)
            if not self._note.text().strip():
                self._note.setText(name)
            self._sync_placeholder()

    def validate(self) -> bool:
        raw = self._value.text().strip()
        if not raw:
            self.set_error("请填写程序名或完整路径")
            return False
        kind = self._kind.value()
        if kind == "name":
            if "\\" in raw or "/" in raw:
                self.set_error("按程序名匹配时只填写文件名，例如 chrome.exe")
                return False
            if not raw.lower().endswith(".exe"):
                raw += ".exe"
                self._value.setText(raw)
            value = normalize_name(raw)
        else:
            if not os.path.isabs(raw):
                self.set_error("请填写完整路径，例如 C:\\Program Files\\App\\app.exe")
                return False
            value = normalize_path(raw)
        self.result_data = {
            "kind": kind,
            "value": value,
            "note": self._note.text().strip(),
        }
        if self.mode == "rule":
            self.result_data.update({
                "window_seconds": self._window_stepper.value(),
                "max_instances": int(self._max_stepper.value()),
                "action": self._action.value(),
            })
        return True


class ProcessPickerDialog(BaseDialog):
    """列出正在运行的程序，供选择。"""

    def __init__(self, parent=None, title: str = "选择程序", subtitle: str = ""):
        super().__init__(parent, title, subtitle, width=520, ok_text="选择")
        self.selected = None

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索程序名或路径…")
        self._search.textChanged.connect(self._filter)
        self.body.addWidget(self._search)

        self._list = QListWidget()
        self._list.setFixedHeight(260)
        self._list.itemDoubleClicked.connect(lambda _item: self._on_ok())
        self.body.addWidget(self._list)

        self._hint = make_label("", "faint")
        self.body.addWidget(self._hint)
        self._entries = []
        self._reload()

    def _reload(self) -> None:
        seen = set()
        entries = []
        own = os.path.basename(os.path.abspath(__import__("sys").executable)).lower()
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                info = proc.info
                exe = (info.get("exe") or "").strip()
                name = (info.get("name") or "").strip()
                if not exe or not name:
                    continue
                lowered = exe.lower()
                if lowered in seen:
                    continue
                if "\\windows\\" in lowered or "\\windowsapps\\" in lowered:
                    continue
                if name.lower() == own:
                    continue
                if not lowered.endswith(".exe"):
                    continue
                seen.add(lowered)
                entries.append((name, exe))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        entries.sort(key=lambda item: item[0].lower())
        self._entries = entries
        self._hint.setText("共 %d 个正在运行的程序，双击可直接选择" % len(entries))
        self._filter(self._search.text())

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        self._list.clear()
        for name, exe in self._entries:
            if needle and needle not in name.lower() and needle not in exe.lower():
                continue
            item = QListWidgetItem("%s    %s" % (name, exe))
            item.setData(Qt.UserRole, (exe, name))
            item.setToolTip(exe)
            self._list.addItem(item)
        if self._list.count() and self._list.currentRow() < 0:
            self._list.setCurrentRow(0)

    def validate(self) -> bool:
        item = self._list.currentItem()
        if item is None:
            self.set_error("请先在列表中选择一个程序")
            return False
        exe, name = item.data(Qt.UserRole)
        self.selected = (exe, name)
        return True


class PasswordDialog(BaseDialog):
    """设置 / 修改 / 关闭 / 验证密码。"""

    def __init__(self, parent=None, has_password: bool = False, mode: str = "set", record=None):
        if mode == "verify":
            title, subtitle = "需要密码", "该页面包含防护设置，请输入密码后继续"
        elif mode == "set":
            title, subtitle = "开启密码保护", "设置后，修改防护设置需要输入密码"
        elif mode == "change":
            title, subtitle = "修改密码", "请输入当前密码，并设置新密码"
        else:
            title, subtitle = "关闭密码保护", "验证当前密码后即可关闭保护"
        ok_text = "保存" if mode == "change" else "确认"
        super().__init__(parent, title, subtitle, width=430, ok_text=ok_text)
        self.mode = mode
        self._record = record
        self.result_password = None
        self.verified = False

        self._old = None
        self._first = None
        self._second = None

        if mode == "verify":
            self.body.addWidget(_field_label("密码"))
            self._old = QLineEdit()
            self._old.setEchoMode(QLineEdit.Password)
            self._old.returnPressed.connect(self._on_ok)
            self.body.addWidget(self._old)
        else:
            if has_password and mode in ("change", "disable"):
                self.body.addWidget(_field_label("当前密码"))
                self._old = QLineEdit()
                self._old.setEchoMode(QLineEdit.Password)
                self._old.returnPressed.connect(self._on_ok)
                self.body.addWidget(self._old)

            if mode in ("set", "change"):
                self.body.addWidget(_field_label("新密码（至少 4 位）"))
                self._first = QLineEdit()
                self._first.setEchoMode(QLineEdit.Password)
                self.body.addWidget(self._first)
                self.body.addWidget(_field_label("再次输入新密码"))
                self._second = QLineEdit()
                self._second.setEchoMode(QLineEdit.Password)
                self._second.returnPressed.connect(self._on_ok)
                self.body.addWidget(self._second)

    def validate(self) -> bool:
        record = self._record
        if self.mode == "verify":
            if config.verify_password(self._old.text(), record):
                self.verified = True
                return True
            self.set_error("密码不正确，请重试")
            return False
        if self._old is not None:
            if not config.verify_password(self._old.text(), record):
                self.set_error("当前密码不正确")
                return False
        if self.mode == "disable":
            self.result_password = ""
            return True
        first = self._first.text()
        if len(first) < 4:
            self.set_error("密码至少 4 位")
            return False
        if first != self._second.text():
            self.set_error("两次输入的密码不一致")
            return False
        self.result_password = first
        return True


class ConfirmDialog(BaseDialog):
    def __init__(self, parent=None, title: str = "确认", message: str = "",
                 ok_text: str = "确定", danger: bool = False):
        super().__init__(parent, title, "", width=420, ok_text=ok_text,
                         tone="danger" if danger else "primary")
        label = make_label(message, "body", wrap=True)
        self.body.addWidget(label)


class PauseDialog(BaseDialog):
    """选择暂停时长。"""

    OPTIONS = [("300", "5 分钟"), ("900", "15 分钟"), ("1800", "30 分钟"),
               ("3600", "1 小时"), ("-1", "直到手动恢复")]

    def __init__(self, parent=None):
        super().__init__(parent, "暂停防护", "暂停期间不会拦截任何程序，适合临时安装或更新软件",
                         width=430, ok_text="暂停")
        self.result_seconds = None
        self._segmented = SegmentedControl(self.OPTIONS, "900")
        self.body.addWidget(self._segmented)
        note = make_label("暂停结束后会自动恢复防护。", "faint")
        self.body.addWidget(note)

    def validate(self) -> bool:
        seconds = int(self._segmented.value())
        self.result_seconds = seconds
        return True


class InfoDialog(BaseDialog):
    """展示多行结果（通知修复报告等）。"""

    def __init__(self, parent=None, title: str = "提示", subtitle: str = "",
                 lines=None, width: int = 480):
        super().__init__(parent, title, subtitle, width=width,
                         ok_text="知道了", cancel_text="关闭")
        self._cancel_button.setVisible(False)
        for text in (lines or []):
            self.body.addWidget(make_label(str(text), "body", wrap=True))


def confirm(parent, title: str, message: str, ok_text: str = "确定",
            danger: bool = False) -> bool:
    dialog = ConfirmDialog(parent, title, message, ok_text, danger)
    return dialog.exec_() == QDialog.Accepted
