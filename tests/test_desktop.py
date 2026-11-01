"""المرحلة 5: الاختصار العام، قفل الجلسة، التشغيل مع ويندوز، شريط المهام، السجل."""

import ctypes
import sys
import uuid

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from lockcontrol.core import autostart
from lockcontrol.core.storage import HistoryEntry
from lockcontrol.ui import controller as controller_module
from lockcontrol.ui.controller import AppController
from lockcontrol.ui.history_dialog import HistoryDialog
from lockcontrol.ui.hotkeys import HotkeyError
from test_ui import ctx  # noqa: F401  (fixture)

if sys.platform == "win32":
    from lockcontrol.ui.win_events import (
        HOTKEY_ID,
        MOD_ALT,
        MOD_CONTROL,
        MOD_NOREPEAT,
        MOD_SHIFT,
        WM_HOTKEY,
        WM_WTSSESSION_CHANGE,
        WTS_SESSION_LOCK,
        WindowsEventFilter,
        parse_hotkey,
    )

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


def native_platform() -> bool:
    return QGuiApplication.platformName() == "windows"


@windows_only
def test_parse_hotkey():
    assert parse_hotkey("Ctrl+Alt+O") == (MOD_NOREPEAT | MOD_CONTROL | MOD_ALT, ord("O"))
    assert parse_hotkey("Ctrl+Shift+5") == (MOD_NOREPEAT | MOD_CONTROL | MOD_SHIFT, ord("5"))
    assert parse_hotkey("Alt+F12") == (MOD_NOREPEAT | MOD_ALT, 0x7B)
    for bad in ("", "O", "Ctrl+Left"):
        with pytest.raises(HotkeyError):
            parse_hotkey(bad)


@windows_only
def test_real_hotkey_and_session_lock_messages(qtbot, qapp):
    if not native_platform():
        pytest.skip("يتطلب منصة windows الأصلية لا offscreen")
    calls = {"hotkey": 0, "lock": 0}
    widget = QWidget()
    qtbot.addWidget(widget)
    f = WindowsEventFilter(
        lambda: calls.__setitem__("hotkey", calls["hotkey"] + 1),
        lambda: calls.__setitem__("lock", calls["lock"] + 1),
    )
    qapp.installNativeEventFilter(f)
    hwnd = int(widget.winId())
    f.attach(hwnd)
    try:
        f.register_hotkey("Ctrl+Alt+Shift+F11")
        # الاختصار محجوز الآن: تسجيله مرة ثانية يفشل
        assert not ctypes.windll.user32.RegisterHotKey(
            None, HOTKEY_ID + 1, *parse_hotkey("Ctrl+Alt+Shift+F11")
        )

        ctypes.windll.user32.PostMessageW(hwnd, WM_HOTKEY, HOTKEY_ID, 0)
        ctypes.windll.user32.PostMessageW(hwnd, WM_WTSSESSION_CHANGE, WTS_SESSION_LOCK, 0)
        qtbot.waitUntil(lambda: calls["hotkey"] == 1 and calls["lock"] >= 1, timeout=3000)
        qtbot.wait(300)
        assert calls["hotkey"] == 1  # ضغطة واحدة = فتح واحد
    finally:
        f.detach()
        qapp.removeNativeEventFilter(f)


@windows_only
def test_autostart_registry_round_trip():
    name = f"LockControlTest-{uuid.uuid4().hex[:8]}"
    try:
        assert not autostart.is_enabled(name)
        autostart.set_enabled(True, name, command='"C:\\x.exe" --minimized')
        assert autostart.is_enabled(name)
    finally:
        autostart.set_enabled(False, name)
    assert not autostart.is_enabled(name)


def test_launch_command_uses_minimized_flag():
    cmd = autostart.launch_command()
    assert cmd.endswith("--minimized") and "lockcontrol" in cmd


@pytest.fixture
def controller(qtbot, qapp, ctx, monkeypatch):  # noqa: F811
    registry = {"enabled": False}
    monkeypatch.setattr(controller_module.autostart, "is_enabled", lambda: registry["enabled"])
    monkeypatch.setattr(
        controller_module.autostart, "set_enabled", lambda on: registry.__setitem__("enabled", on)
    )
    ctx.settings.ui.hotkey = "Ctrl+Alt+Shift+F10"
    if sys.platform != "win32":
        # خوادم CI بلا شاشة ولا أذونات لوحة مفاتيح؛ pynput مختبر في test_platform.
        class FakeEvents:
            supports_session_lock = False

            def attach(self, window):
                pass

            def register_hotkey(self, text):
                pass

            def detach(self):
                pass

        monkeypatch.setattr(controller_module, "create_system_events", lambda app, h, s: FakeEvents())
    c = AppController(ctx, qapp)
    qtbot.addWidget(c.window)
    c.registry = registry
    yield c
    c._cleanup()


def test_tray_menu_lists_default_and_others(controller):
    texts = [a.text() for a in controller.menu.actions()]
    assert texts[0] == "🔓 فتح المكتب"
    sub = controller.menu.actions()[1].menu()
    assert [a.text() for a in sub.actions()] == ["الباب الرئيسي"]
    assert "خروج" in texts


def test_close_hides_to_tray(controller, qtbot):
    controller.window.show()
    controller.window.close()
    assert not controller.window.isVisible()
    assert not controller._quitting


def test_autostart_follows_settings(controller):
    controller.ctx.settings.ui.start_with_windows = True
    controller.apply_runtime_settings()
    assert controller.registry["enabled"]
    controller.ctx.settings.ui.start_with_windows = False
    controller.apply_runtime_settings()
    assert not controller.registry["enabled"]


def test_session_lock_invalidates_day_only_if_enabled(controller):
    sec = controller.ctx.security
    sec.verify_os("m")
    controller.session_locked()
    assert sec.is_day_verified()
    controller.ctx.settings.ui.reverify_on_session_lock = True
    controller.session_locked()
    assert not sec.is_day_verified()


def test_hotkey_opens_default(controller, qtbot):
    controller.window._authorize = lambda c, p: True
    with qtbot.waitSignal(controller.window.open_finished, timeout=3000):
        controller.hotkey_pressed()
    assert controller.ctx.fake_service.opened[-1][0] == "d2"


def test_history_dialog_shows_newest_first(qtbot, ctx):  # noqa: F811
    ctx.store.append_history(HistoryEntry("2026-11-01T10:00:00", "d1", "الباب", True, "open_door"))
    ctx.store.append_history(HistoryEntry("2026-11-01T11:00:00", "d2", "المكتب", False, "غير متصل"))
    d = HistoryDialog(ctx)
    qtbot.addWidget(d)
    assert d.table.rowCount() == 2
    assert d.table.item(0, 1).text() == "المكتب"
    assert d.table.item(0, 2).text() == "✗ فشل"


# ----- اللغة -----


@pytest.fixture
def english():
    from lockcontrol import i18n

    i18n.set_language("en")
    yield
    i18n.set_language("ar")


def test_main_window_in_english(qtbot, ctx, english):  # noqa: F811
    from lockcontrol.ui.main_window import MainWindow

    w = MainWindow(ctx, authorize_fn=lambda c, p: True)
    qtbot.addWidget(w)
    assert w.open_button.text() == "Unlock"
    assert w.settings_button.text() == "⚙ Settings"
    with qtbot.waitSignal(w.open_finished, timeout=3000):
        w.open_selected()
    assert w.message.text() == "✓ Unlocked المكتب"


def test_language_choice_is_saved(qtbot, ctx):  # noqa: F811
    from lockcontrol.core.storage import SettingsStore
    from lockcontrol.ui.settings_dialog import SettingsDialog

    d = SettingsDialog(ctx)
    qtbot.addWidget(d)
    d.language.setCurrentIndex(d.language.findData("en"))
    d.save()
    assert SettingsStore(ctx.store.data_dir).load().ui.language == "en"


def test_changing_language_offers_restart(controller, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from lockcontrol import i18n

    asked, restarted = [], []
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: asked.append(a[2]) or QMessageBox.StandardButton.Yes
    )
    monkeypatch.setattr(controller, "restart", lambda: restarted.append(True))
    try:
        controller.ctx.settings.ui.language = "en"
        controller._offer_restart_for_language()
        assert asked == ["The new language applies after restarting the app. Restart now?"]
        assert restarted == [True]
    finally:
        i18n.set_language("ar")


def test_restart_launches_new_instance_then_quits(controller, monkeypatch):
    started = []
    monkeypatch.setattr(
        controller_module.QProcess, "startDetached", lambda program, args: started.append([program, *args]) or True
    )
    quit_called = []
    monkeypatch.setattr(controller, "quit", lambda: quit_called.append(True))
    controller.restart()
    assert started[0][-1] == "--restarted" and "--minimized" not in started[0]
    assert quit_called == [True]


@windows_only
def test_autostart_creates_missing_run_key(monkeypatch):
    """ملف مستخدم جديد بلا مفتاح Run (هكذا فشل CI)."""
    import winreg

    test_key = rf"Software\LockControlTest-{uuid.uuid4().hex[:8]}\Run"
    monkeypatch.setattr(autostart, "RUN_KEY", test_key)
    try:
        autostart.set_enabled(False, "X")  # المفتاح غير موجود: لا خطأ
        assert not autostart.is_enabled("X")
        autostart.set_enabled(True, "X", command=r'"C:\x.exe" --minimized')
        assert autostart.is_enabled("X")
        autostart.set_enabled(False, "X")
        assert not autostart.is_enabled("X")
    finally:
        parent = test_key.rsplit("\\", 1)[0]
        for key in (test_key, parent):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
            except FileNotFoundError:
                pass
