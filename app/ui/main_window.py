# -*- coding: utf-8 -*-
"""主窗口：侧边导航、页面栈、托盘与守护引擎的接线。"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import os
import sys
import time

from PySide2.QtCore import QByteArray, QRectF, Qt, QTimer
from PySide2.QtGui import (QColor, QCursor, QIcon, QPainter, QPainterPath,
                           QPen, QPixmap)
from PySide2.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMenu, QStackedWidget,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

import psutil

from ..core import autostart, cleaner, config, themes, winutil
from ..core.logbook import LogBook
from ..core.monitor import MonitorEngine
from . import icons
from .clean_worker import CleanerThread
from .dialogs import BaseDialog, PasswordDialog
from .pages.about import AboutPage
from .pages.cleaner import CleanerPage
from .pages.dashboard import DashboardPage, human_duration
from .pages.exceptions import ExceptionsPage
from .pages.junk import JunkPage
from .pages.rules import RulesPage
from .pages.settings import SettingsPage
from .widgets import IconView, NavButton, Toast, WindowButton, make_badge, make_label

PAGES = ("概览", "清理", "垃圾清理", "规则", "例外", "设置", "关于")


class LogoMark(QWidget):
    """侧边栏顶部的应用标志。"""

    def __init__(self, size: int = 38, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 42))
        painter.drawRoundedRect(QRectF(0, 0, self._size, self._size),
                                self._size * 0.3, self._size * 0.3)
        icons.draw_icon(painter, "shield",
                        QRectF(self._size * 0.2, self._size * 0.16,
                               self._size * 0.6, self._size * 0.68),
                        "#FFFFFF", 2.0)
        painter.end()


def app_icon() -> QIcon:
    """优先使用打包资源里的 .ico，缺失时现场绘制。"""
    path = os.path.join(config.asset_dir(), "anti_misopen.ico")
    if os.path.isfile(path):
        icon = QIcon(path)
        if not icon.isNull():
            return icon
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2F6BFF"))
        painter.drawRoundedRect(0, 0, size, size, size * 0.28, size * 0.28)
        icons.draw_icon(painter, "shield",
                        QRectF(size * 0.2, size * 0.13, size * 0.6, size * 0.72),
                        "#FFFFFF", max(1.2, size * 0.055))
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class LogDialog(BaseDialog):
    """完整拦截记录。"""

    def __init__(self, parent, logbook: LogBook):
        super().__init__(parent, "拦截记录", "这里保存了最近的所有拦截动作", width=560,
                         ok_text="关闭", cancel_text="")
        self._logbook = logbook
        self._cancel_button.hide()
        self._list = QListWidget()
        self._list.setMinimumHeight(320)
        self._list.setSpacing(1)
        self.body.addWidget(self._list)
        self._reload()

    def _reload(self) -> None:
        self._list.clear()
        entries = self._logbook.recent(200)
        if not entries:
            item = QListWidgetItem("暂时没有拦截记录")
            item.setFlags(Qt.NoItemFlags)
            self._list.addItem(item)
            return
        for entry in entries:
            stamp = str(entry.get("time") or "")
            name = str(entry.get("name") or "未知程序")
            reason = str(entry.get("reason") or "")
            killed = bool(entry.get("killed"))
            text = "%s    %s\n%s" % (stamp[5:16] if len(stamp) >= 16 else stamp, name, reason)
            item = QListWidgetItem(text + ("    · 已关闭" if killed else "    · 已提示"))
            item.setData(Qt.UserRole, entry)
            self._list.addItem(item)

    def validate(self) -> bool:
        return True


class MainWindow(QWidget):
    def __init__(self, store, logbook: LogBook):
        super().__init__()
        self.store = store
        self.logbook = logbook
        self._quitting = False
        self._pages = []
        self._nav_buttons = []
        self._tray_tip_shown = False
        self._last_save = time.time()
        self._clean_thread = None

        self.setObjectName("Root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        # 只有系统启用了 DWM 合成（Vista/Win7 Aero 及以上）才使用圆角 + 半透明，
        # 否则退回不透明矩形窗口，避免 Windows 7 基本主题下四角出现黑块。
        self._rounded = winutil.composition_enabled()
        if self._rounded:
            self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setWindowTitle("%s · %s" % (config.APP_NAME, config.APP_NAME_CN))
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1000, 660)
        self.resize(1140, 740)

        self._build_ui()
        self._build_tray()
        self._build_engine()
        self._build_timers()
        self._restore_geometry()
        self.open_page(0)
        self.apply_config()
        self.apply_theme(str(self.store.get("theme") or "light_blue"), refresh=False)
        # 在窗口第一次显示前就把图标写入窗口与窗口类，避免任务栏按钮先按“无图标”
        # 创建，之后即使 WM_SETICON 成功也不再刷新。
        self.winId()
        self._apply_taskbar_icon()

    # ------------------------------------------------------------- 界面
    def paintEvent(self, event):
        # 顶层窗口是半透明无边框窗口，QSS 的 background 不会自动绘制，这里手工画圆角底板。
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        palette = themes.current()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if not self._rounded:
            painter.fillRect(self.rect(), QColor(palette["bg"]))
            painter.end()
            return
        path = QPainterPath()
        path.addRoundedRect(rect, 17, 17)
        painter.fillPath(path, QColor(palette["bg"]))
        painter.setPen(QPen(QColor(palette["border"]), 1))
        painter.drawPath(path)
        painter.end()

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._sidebar = QFrame()
        self._sidebar.setObjectName("Sidebar")
        self._sidebar.setFixedWidth(232)
        side = QVBoxLayout(self._sidebar)
        side.setContentsMargins(16, 22, 16, 18)
        side.setSpacing(6)

        brand = QHBoxLayout()
        brand.setSpacing(11)
        brand.setContentsMargins(6, 0, 0, 0)
        brand.addWidget(LogoMark(38), 0, Qt.AlignVCenter)
        names = QVBoxLayout()
        names.setSpacing(1)
        names.addWidget(make_label(config.APP_NAME, "sideTitle"))
        names.addWidget(make_label(config.APP_NAME_CN + " · 重复启动拦截", "sideSub"))
        brand.addLayout(names, 1)
        side.addLayout(brand)
        side.addSpacing(20)

        section = make_label("防 护", "sideSub")
        section.setContentsMargins(10, 0, 0, 4)
        side.addWidget(section)

        nav_items = (("grid", "概览"), ("refresh", "清理"), ("trash", "垃圾清理"),
                     ("sliders", "规则"), ("check", "例外"), ("gear", "设置"),
                     ("info", "关于"))
        for index, (icon_name, text) in enumerate(nav_items):
            button = NavButton(icon_name, text)
            button.clicked.connect(lambda _checked=False, i=index: self.open_page(i))
            side.addWidget(button)
            self._nav_buttons.append(button)

        side.addStretch(1)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(10, 0, 8, 6)
        status_row.setSpacing(7)
        self._side_dot = QLabel()
        self._side_dot.setFixedSize(8, 8)
        status_row.addWidget(self._side_dot, 0, Qt.AlignVCenter)
        self._side_status = make_label("正在启动…", "sideSub")
        status_row.addWidget(self._side_status, 1)
        side.addLayout(status_row)

        wordmark = make_label("v%s  ·  %s" % (config.APP_VERSION, config.APP_SIGNATURE), "wordmark")
        wordmark.setContentsMargins(10, 4, 4, 0)
        wordmark.setWordWrap(True)
        side.addWidget(wordmark)

        outer.addWidget(self._sidebar)

        content = QWidget()
        content.setObjectName("Content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        titlebar = QWidget()
        titlebar.setObjectName("TitleBar")
        titlebar.setFixedHeight(46)
        bar = QHBoxLayout(titlebar)
        bar.setContentsMargins(26, 8, 10, 0)
        bar.setSpacing(6)
        self._bar_title = make_label("", "faint")
        bar.addWidget(self._bar_title, 0, Qt.AlignVCenter)
        bar.addStretch(1)
        minimize = WindowButton("min")
        minimize.clicked.connect(self.showMinimized)
        bar.addWidget(minimize, 0, Qt.AlignTop)
        close_button = WindowButton("close", danger=True)
        close_button.clicked.connect(self.close)
        bar.addWidget(close_button, 0, Qt.AlignTop)
        content_layout.addWidget(titlebar)

        self._stack = QStackedWidget()
        self._stack.setObjectName("PageStack")
        self._pages = [DashboardPage(self), CleanerPage(self), JunkPage(self),
                       RulesPage(self), ExceptionsPage(self), SettingsPage(self),
                       AboutPage(self)]
        for page in self._pages:
            self._stack.addWidget(page)
        content_layout.addWidget(self._stack, 1)

        outer.addWidget(content, 1)

        self._toast = Toast(self)

    # ------------------------------------------------------------- 托盘
    def _build_tray(self) -> None:
        self._tray = QSystemTrayIcon(app_icon(), self)
        self._tray.setToolTip("%s · %s" % (config.APP_NAME, config.APP_NAME_CN))
        menu = QMenu(self)
        self._tray_open = menu.addAction("打开主界面")
        self._tray_open.triggered.connect(self.show_from_tray)
        menu.addSeparator()
        self._tray_status = menu.addAction("防护已开启")
        self._tray_status.setEnabled(False)
        self._tray_pause = menu.addAction("暂停防护 15 分钟")
        self._tray_pause.triggered.connect(lambda: self._tray_set_pause(900))
        self._tray_resume = menu.addAction("恢复防护")
        self._tray_resume.triggered.connect(lambda: self._tray_set_pause(0))
        menu.addSeparator()
        self._tray_clean = menu.addAction("一键清理内存")
        self._tray_clean.triggered.connect(lambda: self.clean_memory_now("manual"))
        menu.addSeparator()
        self._tray_autostart = menu.addAction("开机自启动")
        self._tray_autostart.setCheckable(True)
        self._tray_autostart.triggered.connect(self._tray_toggle_autostart)
        menu.addSeparator()
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self.quit_app)
        self._tray_menu = menu
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_from_tray()

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.refresh_pages()
        self._sync_tray()

    def _tray_set_pause(self, seconds: int) -> None:
        if seconds and self.store.get("password"):
            if not self.require_password("暂停防护需要密码"):
                return
        until = 0 if not seconds else time.time() + seconds
        self.store.update({"paused_until": until})
        self.store.save()
        self.apply_config()
        self.refresh_pages()
        self._sync_tray()
        self.show_toast("已暂停防护" if seconds else "防护已恢复", "warning" if seconds else "success")

    def _tray_toggle_autostart(self) -> None:
        enabled = bool(self._tray_autostart.isChecked())
        if not autostart.set_enabled(enabled):
            self.show_toast("写入开机启动项失败，请检查系统权限", "danger")
            self._sync_tray()
            return
        self.store.update({"autostart": enabled})
        self.store.save()
        self.refresh_pages()
        self._sync_tray()
        self.show_toast("已开启开机自启动" if enabled else "已关闭开机自启动",
                        "success" if enabled else "warning")

    def _sync_tray(self) -> None:
        enabled = bool(self.store.get("enabled"))
        paused = self.store.is_paused()
        if not enabled:
            state = "防护已关闭"
        elif paused:
            state = "防护已暂停"
        else:
            state = "防护运行中"
        self._tray_status.setText(state)
        self._tray_pause.setEnabled(enabled and not paused)
        self._tray_resume.setEnabled(enabled and paused)
        self._tray_autostart.blockSignals(True)
        self._tray_autostart.setChecked(bool(self.store.get("autostart")))
        self._tray_autostart.blockSignals(False)
        self._tray.setToolTip("%s · %s" % (config.APP_NAME, state))
        color = "#129E68" if enabled and not paused else ("#D98A0B" if paused else "#98A6BE")
        self._side_status.setText(state)
        self._side_dot.setStyleSheet("background: %s; border-radius: 4px;" % color)

    # ------------------------------------------------------------- 引擎
    def _build_engine(self) -> None:
        self.engine = MonitorEngine(self.store, self.logbook, self)
        self.engine.blocked.connect(self._on_blocked)
        self.engine.log.connect(lambda _text: None)
        self.engine.stateChanged.connect(lambda _e, _p: self._sync_tray())
        self.engine.start()
        try:
            self.logbook.prune(int(self.store.get("log_keep_days") or 30))
        except Exception:
            pass

    def _on_blocked(self, entry: dict) -> None:
        stats = self.store.touch_stats()
        stats["total_blocked"] = int(stats.get("total_blocked") or 0) + 1
        stats["today_blocked"] = int(stats.get("today_blocked") or 0) + 1
        if not stats.get("since"):
            stats["since"] = int(time.time())
        self.store.save()

        name = str(entry.get("name") or "某个程序")
        killed = bool(entry.get("killed"))
        if bool(self.store.get("notify")):
            message = ("已关闭 %s 的多余窗口" % name) if killed else ("检测到 %s 重复启动" % name)
            if self.isVisible() and not self.isMinimized():
                self.show_toast(message, "warning" if killed else "info")
            if self._tray.isVisible():
                self._tray.showMessage(config.APP_NAME,
                                       message + "\n重复双击已拦截，电脑保持流畅。",
                                       QSystemTrayIcon.Warning, 3500)
        self._sync_tray()
        try:
            self._pages[0].refresh()
        except Exception:
            pass

    # ------------------------------------------------------------- 计时
    def _build_timers(self) -> None:
        self._minute_timer = QTimer(self)
        self._minute_timer.setInterval(60000)
        self._minute_timer.timeout.connect(self._on_minute)
        self._minute_timer.start()

        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(20000)
        self._watch_timer.timeout.connect(self._on_watch)
        self._watch_timer.start()

        # 自动清理：每 15 秒检查一次内存占用是否达到阈值
        self._clean_timer = QTimer(self)
        self._clean_timer.setInterval(5000)
        self._clean_timer.timeout.connect(self._auto_clean_tick)
        self._clean_timer.start()

    def _on_minute(self) -> None:
        if bool(self.store.get("enabled")) and not self.store.is_paused():
            stats = self.store.touch_stats()
            stats["protected_seconds"] = float(stats.get("protected_seconds") or 0) + 60.0
            if not stats.get("since"):
                stats["since"] = int(time.time())
            if time.time() - self._last_save > 240:
                self.store.save()
                self._last_save = time.time()
            if self.isVisible() and self._stack.currentIndex() == 0:
                try:
                    self._pages[0].refresh()
                except Exception:
                    pass

    def _on_watch(self) -> None:
        if self.store.is_paused() and float(self.store.get("paused_until") or 0) <= time.time():
            self.store.update({"paused_until": 0})
            self.store.save()
            self.apply_config()
            self.refresh_pages()
        self._sync_tray()

    # ------------------------------------------------------------- 内存清理
    def clean_memory_now(self, source: str = "manual") -> None:
        if self._clean_thread is not None and self._clean_thread.isRunning():
            if source == "manual":
                self.show_toast("正在清理中，请稍候…", "info")
            return
        deep = bool(self.store.get("memory_deep"))
        if source == "manual":
            self.show_toast("正在清理内存…", "info")
        thread = CleanerThread(deep, self)
        thread.finished_result.connect(lambda result: self._on_clean_done(result, source))
        thread.finished.connect(thread.deleteLater)
        self._clean_thread = thread
        thread.start()

    def _on_clean_done(self, result: dict, source: str) -> None:
        self._clean_thread = None
        if not result.get("ok"):
            self.show_toast("清理失败：%s" % (result.get("error") or "未知错误"), "danger")
            return
        freed = int(result.get("freed") or 0)
        total = int(self.store.get("memory_total_freed") or 0) + freed
        self.store.update({
            "memory_last_cleanup": time.time(),
            "memory_last_freed": freed,
            "memory_total_freed": total,
        })
        self.store.save()
        if freed > 0:
            summary = "已释放 %s 内存" % cleaner.format_bytes(freed)
        else:
            summary = "内存已经比较清爽"
        if source == "auto":
            if bool(self.store.get("memory_auto_notify")):
                self.show_toast("自动清理完成：%s" % summary, "success")
        else:
            self.show_toast("%s · 清理了 %d 个进程" % (summary, int(result.get("trimmed") or 0)),
                            "success")
        self.refresh_pages()

    def _auto_clean_tick(self) -> None:
        if not bool(self.store.get("memory_auto")):
            return
        if self._clean_thread is not None and self._clean_thread.isRunning():
            return
        last = float(self.store.get("memory_last_cleanup") or 0)
        if time.time() - last < 300:  # 两次自动清理至少间隔 5 分钟
            return
        try:
            percent = psutil.virtual_memory().percent
        except Exception:
            return
        if percent >= float(self.store.get("memory_threshold") or 85):
            self.clean_memory_now("auto")

    # ------------------------------------------------------------- 对外接口
    def show_toast(self, text: str, tone: str = "success") -> None:
        self._toast.show_message(text, tone)
        self._toast.raise_()

    def test_notification(self) -> None:
        """从设置页触发的一条通知测试，同时走托盘气泡和窗口内 Toast。"""
        if self._tray.isVisible():
            self._tray.showMessage(
                "Anti MisOpen 通知测试",
                "能看到这条系统通知，说明通知已经正常工作。",
                QSystemTrayIcon.Information, 5000)
        self.show_toast("通知测试已发送：如果只看到这条提示而没看到系统通知，点“一键修复通知设置”",
                        "info")

    def open_page(self, index: int) -> None:
        index = max(0, min(len(self._pages) - 1, int(index)))
        self._stack.setCurrentIndex(index)
        for position, button in enumerate(self._nav_buttons):
            button.setChecked(position == index)
        self._bar_title.setText("Anti MisOpen  /  " + PAGES[index])
        try:
            page = self._pages[index]
            if hasattr(page, "refresh"):
                page.refresh()
        except Exception:
            pass

    def open_logs(self) -> None:
        dialog = LogDialog(self, self.logbook)
        dialog.exec_()

    def require_password(self, reason: str = "") -> bool:
        record = self.store.get("password")
        if not record:
            return True
        dialog = PasswordDialog(self, has_password=True, mode="verify", record=record)
        if reason:
            dialog._subtitle_label.setText(reason)
        return dialog.exec_() == dialog.Accepted and bool(dialog.verified)

    def apply_config(self) -> None:
        snapshot = dict(self.store.data)
        try:
            self.engine.apply_config(snapshot)
        except Exception:
            pass
        self._sync_tray()

    def apply_theme(self, key: str, refresh: bool = True) -> None:
        themes.set_theme(key)
        application = QApplication.instance()
        if application is not None:
            application.setStyleSheet(themes.qss())
        themes.repolish(self)
        self.update()
        if refresh:
            self.refresh_pages()

    def refresh_pages(self) -> None:
        for page in self._pages:
            if hasattr(page, "refresh"):
                try:
                    page.refresh()
                except Exception:
                    pass
        self._sync_tray()
        self.update()

    def after_reset(self) -> None:
        self.store.reset()
        self.store.save()
        self.apply_config()
        self.apply_theme(str(self.store.get("theme") or "light_blue"), refresh=False)
        self.refresh_pages()
        self.open_page(0)

    # ------------------------------------------------------------- 几何
    def _restore_geometry(self) -> None:
        raw = self.store.get("window_geometry") or ""
        if not raw:
            return
        try:
            geometry = QByteArray.fromBase64(raw.encode("ascii"))
            if not geometry.isEmpty():
                self.restoreGeometry(geometry)
        except Exception:
            pass
        self._keep_on_screen()

    def _keep_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        if frame.width() > available.width() or frame.height() > available.height():
            self.resize(min(self.width(), available.width() - 40),
                        min(self.height(), available.height() - 40))
        if not available.intersects(frame):
            self.move(available.center() - self.rect().center())

    def _save_geometry(self) -> None:
        try:
            self.store.update({"window_geometry": bytes(self.saveGeometry().toBase64()).decode("ascii")})
            self.store.save()
        except Exception:
            pass

    # ------------------------------------------------------------- 事件
    def _apply_taskbar_icon(self) -> None:
        """无边框窗口是 WS_POPUP，任务栏图标可能空白；这里显式设置任务栏样式与图标。"""
        if os.name != "nt":
            return
        try:
            user32 = ctypes.windll.user32
            hwnd = wintypes.HWND(int(self.winId()))
            ws_ex_appwindow = 0x00040000
            ws_ex_toolwindow = 0x00000080
            gwlp_hicon = -14
            gwlp_hiconsm = -34
            long_ptr = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long

            get_long = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
            set_long = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
            get_long.restype = long_ptr
            get_long.argtypes = [wintypes.HWND, ctypes.c_int]
            set_long.restype = long_ptr
            set_long.argtypes = [wintypes.HWND, ctypes.c_int, long_ptr]

            ex_style = get_long(hwnd, -20)
            new_style = (ex_style | ws_ex_appwindow) & ~ws_ex_toolwindow
            if new_style != ex_style:
                set_long(hwnd, -20, new_style)

            image_icon = 1
            lr_loadfromfile = 0x00000010
            icon_path = os.path.join(config.asset_dir(), "anti_misopen.ico")
            big = small = 0
            if os.path.isfile(icon_path):
                user32.LoadImageW.restype = wintypes.HANDLE
                user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR,
                                              wintypes.UINT, ctypes.c_int,
                                              ctypes.c_int, wintypes.UINT]
                big = user32.LoadImageW(None, icon_path, image_icon, 32, 32,
                                        lr_loadfromfile)
                small = user32.LoadImageW(None, icon_path, image_icon, 16, 16,
                                          lr_loadfromfile)
            if not big:
                shell32 = ctypes.windll.shell32
                shell32.ExtractIconW.restype = wintypes.HICON
                big = shell32.ExtractIconW(None, sys.executable, 0)
            if big or small:
                user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                                wintypes.WPARAM, wintypes.LPARAM]
                user32.SendMessageW.restype = ctypes.c_longlong
                if big:
                    user32.SendMessageW(hwnd, 0x0080, 1, big)
                    if hasattr(user32, "SetClassLongPtrW"):
                        user32.SetClassLongPtrW.restype = long_ptr
                        user32.SetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, long_ptr]
                        user32.SetClassLongPtrW(hwnd, gwlp_hicon, big)
                if small:
                    user32.SendMessageW(hwnd, 0x0080, 0, small)
                    if hasattr(user32, "SetClassLongPtrW"):
                        user32.SetClassLongPtrW(hwnd, gwlp_hiconsm, small)
            # 让任务栏立即重绘图标
            user32.SetWindowPos.restype = wintypes.BOOL
            user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0013)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._toast.reposition()
        QTimer.singleShot(0, self._apply_taskbar_icon)
        if bool(self.store.get("first_run")):
            self.store.set("first_run", False)
            self.store.save()
            QTimer.singleShot(450, lambda: self.show_toast(
                "防护已开启：重复双击会被自动拦截", "success"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._toast.reposition()

    def closeEvent(self, event):
        if self._quitting:
            event.accept()
            return
        if bool(self.store.get("close_to_tray")) and self._tray.isVisible():
            event.ignore()
            self.hide()
            if not self._tray_tip_shown:
                self._tray_tip_shown = True
                self._tray.showMessage(
                    config.APP_NAME,
                    "仍在后台保护：关闭窗口不会停止防护，可从托盘图标重新打开或退出。",
                    QSystemTrayIcon.Information, 4000)
            return
        self.quit_app()
        event.ignore()

    def quit_app(self) -> None:
        if self.store.get("password"):
            if not self.require_password("退出程序需要密码"):
                return
        self._quitting = True
        self._save_geometry()
        try:
            if self._clean_thread is not None and self._clean_thread.isRunning():
                self._clean_thread.wait(3000)
        except Exception:
            pass
        try:
            for page in self._pages:
                if hasattr(page, "wait_hardware"):
                    page.wait_hardware(3000)
        except Exception:
            pass
        try:
            self.engine.stop()
        except Exception:
            pass
        self._tray.hide()
        application = QApplication.instance()
        if application is not None:
            application.quit()

    # ------------------------------------------------------------- 无边框
    def nativeEvent(self, event_type, message):
        if sys.platform == "win32" and self.isVisible():
            try:
                from ctypes import wintypes

                address = int(message)
                if address < 0:
                    address += 1 << 64
                msg = wintypes.MSG.from_address(address)
                if msg.message == 0x0084:  # WM_NCHITTEST
                    position = self.mapFromGlobal(QCursor.pos())
                    width, height = self.width(), self.height()
                    x, y = position.x(), position.y()
                    border, caption = 8, 46
                    left, right = x < border, x > width - border
                    top, bottom = y < border, y > height - border
                    if top and left:
                        return True, 13  # HTTOPLEFT
                    if top and right:
                        return True, 14  # HTTOPRIGHT
                    if bottom and left:
                        return True, 16  # HTBOTTOMLEFT
                    if bottom and right:
                        return True, 17  # HTBOTTOMRIGHT
                    if left:
                        return True, 10  # HTLEFT
                    if right:
                        return True, 11  # HTRIGHT
                    if top:
                        return True, 12  # HTTOP
                    if bottom:
                        return True, 15  # HTBOTTOM
                    if 0 <= y <= caption and x < width - 92:
                        return True, 2  # HTCAPTION
            except Exception:
                pass
        return super().nativeEvent(event_type, message)