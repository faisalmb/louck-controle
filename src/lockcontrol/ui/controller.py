"""يربط النافذة الرئيسية بأيقونة شريط المهام والاختصار العام والتشغيل مع ويندوز."""

import sys

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QSystemTrayIcon

from ..app_context import AppContext
from ..core import autostart
from .auth import authorize, daily_gate
from .history_dialog import HistoryDialog
from .icons import lock_icon
from .main_window import MainWindow
from .settings_dialog import SettingsDialog
from .win_events import HotkeyError, WindowsEventFilter


class AppController(QObject):
    def __init__(self, ctx: AppContext, app: QApplication):
        super().__init__()
        self.ctx = ctx
        self.app = app
        self._quitting = False

        self.window = MainWindow(ctx)
        self.window.setWindowIcon(lock_icon())
        self.window.close_to_tray = self._close_to_tray
        self.window.settings_button.clicked.connect(self.open_settings)
        self.window.history_button.clicked.connect(self.open_history)
        self.window.open_finished.connect(self._notify_open_result)

        self.tray = QSystemTrayIcon(lock_icon(), self)
        self.tray.setToolTip("التحكم بالأقفال")
        self.tray.activated.connect(self._tray_activated)
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)

        self.events = WindowsEventFilter(self.hotkey_pressed, self.session_locked)
        if sys.platform == "win32":
            app.installNativeEventFilter(self.events)
            self.events.attach(int(self.window.winId()))
        app.aboutToQuit.connect(self._cleanup)

        self.apply_runtime_settings()
        self.tray.show()

    # ----- الإعدادات التي تؤثر على التشغيل -----

    def apply_runtime_settings(self) -> None:
        ui = self.ctx.settings.ui
        self._rebuild_menu()
        if sys.platform != "win32":
            return
        try:
            self.events.register_hotkey(ui.hotkey)
        except HotkeyError as e:
            self.tray.showMessage("الاختصار العام", f"{ui.hotkey}: {e}", QSystemTrayIcon.MessageIcon.Warning)
        try:
            if autostart.is_enabled() != ui.start_with_windows:
                autostart.set_enabled(ui.start_with_windows)
        except OSError as e:
            self.tray.showMessage("التشغيل مع ويندوز", str(e), QSystemTrayIcon.MessageIcon.Warning)

    def _rebuild_menu(self) -> None:
        self.menu.clear()
        default = self.ctx.settings.default_lock()
        if default:
            act = self.menu.addAction(f"🔓 فتح {default.name}")
            act.triggered.connect(self.window.open_default)
        others = [l for l in self.ctx.settings.locks if not default or l.device_id != default.device_id]
        if others:
            sub = self.menu.addMenu("فتح قفل آخر")
            for lock in others:
                action = QAction(lock.name, sub)
                action.triggered.connect(lambda _=False, d=lock.device_id: self.open_lock(d))
                sub.addAction(action)
        self.menu.addSeparator()
        self.menu.addAction("إظهار النافذة").triggered.connect(self.show_window)
        self.menu.addAction("السجل").triggered.connect(self.open_history)
        self.menu.addAction("الإعدادات").triggered.connect(self.open_settings)
        self.menu.addSeparator()
        self.menu.addAction("خروج").triggered.connect(self.quit)

    # ----- الأوامر -----

    def show_window(self) -> None:
        # «مرة في اليوم عند أول فتح»: إظهار النافذة يتطلب تحقق اليوم.
        if not daily_gate(self.ctx, self.window):
            return
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def open_lock(self, device_id: str) -> None:
        combo = self.window.lock_combo
        combo.setCurrentIndex(combo.findData(device_id))
        self.window.open_selected()

    def hotkey_pressed(self) -> None:
        self.window.open_default()

    def session_locked(self) -> None:
        if self.ctx.settings.ui.reverify_on_session_lock:
            self.ctx.security.invalidate_day()

    def open_settings(self) -> None:
        if not authorize(self.ctx, self.window, force_pin=True):
            return
        self.edit_settings()

    def edit_settings(self) -> None:
        """بدون طلب PIN؛ للاستخدام بعد التحقق مباشرة (أول تشغيل)."""
        if SettingsDialog(self.ctx, self.window).exec() == QDialog.DialogCode.Accepted:
            self.window.reload_locks()
            self.apply_runtime_settings()

    def open_history(self) -> None:
        if daily_gate(self.ctx, self.window):
            HistoryDialog(self.ctx, self.window).exec()

    def quit(self) -> None:
        self._quitting = True
        self.app.quit()

    # ----- داخلي -----

    def _close_to_tray(self) -> bool:
        if self._quitting:
            return False
        if self.ctx.settings.ui.minimize_to_tray and QSystemTrayIcon.isSystemTrayAvailable():
            return True
        # البرنامج لا يُغلق تلقائياً مع آخر نافذة (لأجل شريط المهام)، فنغلقه هنا.
        QTimer.singleShot(0, self.quit)
        return False

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.window.open_default()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window()

    def _notify_open_result(self, ok: bool) -> None:
        if self.window.isVisible():
            return
        icon = QSystemTrayIcon.MessageIcon.Information if ok else QSystemTrayIcon.MessageIcon.Warning
        self.tray.showMessage("التحكم بالأقفال", self.window.message.text(), icon, 4000)

    def _cleanup(self) -> None:
        if sys.platform == "win32":
            self.events.detach()
            self.app.removeNativeEventFilter(self.events)
        self.tray.hide()
