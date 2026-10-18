# -*- coding: utf-8 -*-
"""程序入口：单实例守卫、主题初始化与主窗口启动。"""
from __future__ import annotations

import os
import sys
import traceback

from PySide2.QtCore import Qt
from PySide2.QtGui import QFont, QFontDatabase
from PySide2.QtNetwork import QLocalServer, QLocalSocket
from PySide2.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from app.core import config, themes, winutil
from app.core.logbook import LogBook
from app.ui.main_window import MainWindow, app_icon

SERVER_NAME = "AntiMisOpen.SingleInstance.v1"


def _set_app_user_model_id() -> None:
    """让任务栏使用本程序图标，而不是 python.exe 的图标。"""
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            u"ChenyangLT.AntiMisOpen.1")
    except Exception:
        pass


def _pick_font() -> QFont:
    families = set(QFontDatabase().families())
    for name in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial"):
        if name in families:
            return QFont(name, 9)
    return QFont()


def _write_crash_log(exc_type, exc_value, tb) -> None:
    try:
        path = os.path.join(config.log_dir(), "crash.log")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("\n===== %s =====\n" % __import__("time").strftime("%Y-%m-%d %H:%M:%S"))
            traceback.print_exception(exc_type, exc_value, tb, file=handle)
    except Exception:
        pass
    try:
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("%s 出现错误" % config.APP_NAME)
        box.setText("程序遇到了一个错误，但防护仍在运行。\n\n%s: %s"
                    % (getattr(exc_type, "__name__", "Error"), exc_value))
        box.setInformativeText("详细信息已写入：%s" % os.path.join(config.log_dir(), "crash.log"))
        box.exec_()
    except Exception:
        pass


class SingleInstance(object):
    """通过本地命名管道保证只运行一个实例。"""

    def __init__(self, application, on_activate):
        self._application = application
        self._on_activate = on_activate
        self._server = None

        socket = QLocalSocket()
        socket.connectToServer(SERVER_NAME)
        if socket.waitForConnected(320):
            socket.write(b"show")
            socket.flush()
            socket.waitForBytesWritten(300)
            socket.disconnectFromServer()
            self.already_running = True
            return
        self.already_running = False

        QLocalServer.removeServer(SERVER_NAME)
        self._server = QLocalServer(application)
        self._server.setSocketOptions(QLocalServer.UserAccessOption)
        self._server.newConnection.connect(self._accept)
        self._server.listen(SERVER_NAME)

    def _accept(self) -> None:
        while self._server.hasPendingConnections():
            connection = self._server.nextPendingConnection()
            if connection is None:
                continue
            try:
                connection.readAll()
                self._on_activate()
            except Exception:
                pass
            finally:
                connection.disconnectFromServer()
                connection.deleteLater()


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    autostart_mode = "--autostart" in argv
    argv = [item for item in argv if item != "--autostart"]

    winutil.enable_dpi_awareness()
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    application = QApplication(argv)
    application.setApplicationName(config.APP_NAME)
    application.setApplicationDisplayName("%s · %s" % (config.APP_NAME, config.APP_NAME_CN))
    application.setApplicationVersion(config.APP_VERSION)
    application.setOrganizationName("ChenyangLT")
    application.setQuitOnLastWindowClosed(False)
    application.setStyle("Fusion")
    application.setFont(_pick_font())
    application.setWindowIcon(app_icon())
    _set_app_user_model_id()
    sys.excepthook = _write_crash_log

    store = config.ConfigStore()
    themes.set_theme(str(store.get("theme") or "light_blue"))
    application.setStyleSheet(themes.qss())

    holder = {}

    def activate() -> None:
        window = holder.get("window")
        if window is not None:
            window.show_from_tray()

    guard = SingleInstance(application, activate)
    if guard.already_running:
        return 0

    logbook = LogBook()
    window = MainWindow(store, logbook)
    holder["window"] = window

    if autostart_mode:
        window.hide()
        if window._tray.isVisible():
            window._tray.showMessage(
                "%s 已在后台启动" % config.APP_NAME,
                "开机自启动成功，重复双击会被自动拦截。",
                QSystemTrayIcon.Information, 3000)
    else:
        window.show()

    return application.exec_()


if __name__ == "__main__":
    sys.exit(main())