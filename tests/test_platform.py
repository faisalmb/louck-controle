"""السلوك الخاص بكل نظام تشغيل (يُختبر على أي نظام بمحاكاة sys.platform)."""

import plistlib
import sys
from pathlib import Path

import pytest

from lockcontrol.core import autostart, verify
from lockcontrol.core.macos_auth import MacVerifier
from lockcontrol.core.security import SecurityManager
from lockcontrol.core.storage import SecretStore, default_data_dir
from lockcontrol.core.verify import NoOsVerifier, VerifyOutcome


def test_data_dir_per_platform(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert default_data_dir("win32") == tmp_path / "Roaming" / "LockControl"
    assert default_data_dir("darwin") == Path.home() / "Library" / "Application Support" / "LockControl"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert default_data_dir("linux") == tmp_path / "cfg" / "lockcontrol"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert default_data_dir("linux") == Path.home() / ".config" / "lockcontrol"


def test_mac_launch_agent(tmp_path):
    path = autostart.mac_agent_path(tmp_path)
    assert path == tmp_path / "Library" / "LaunchAgents" / "com.lockcontrol.app.plist"
    autostart.write_mac_agent(path, ["/Applications/LockControl.app/Contents/MacOS/LockControl", "--minimized"])
    with open(path, "rb") as f:
        data = plistlib.load(f)
    assert data["RunAtLoad"] is True
    assert data["ProgramArguments"][-1] == "--minimized"


def test_linux_desktop_entry_quotes_paths(tmp_path):
    path = autostart.linux_desktop_path(tmp_path)
    assert path == tmp_path / ".config" / "autostart" / "lockcontrol.desktop"
    autostart.write_linux_desktop(path, ["/opt/Lock Control/LockControl", "--minimized"])
    text = path.read_text(encoding="utf-8")
    assert "Exec='/opt/Lock Control/LockControl' --minimized" in text
    assert text.startswith("[Desktop Entry]")


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_set_enabled_creates_and_removes_file(monkeypatch, tmp_path, platform):
    target = tmp_path / "autostart-file"
    monkeypatch.setattr(autostart.sys, "platform", platform)
    monkeypatch.setattr(autostart, "_file_path", lambda: target)
    assert not autostart.is_enabled()
    autostart.set_enabled(True)
    assert autostart.is_enabled() and target.exists()
    autostart.set_enabled(False)
    autostart.set_enabled(False)  # الحذف مرتين لا يرمي خطأ
    assert not autostart.is_enabled()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_windows_launch_command_is_quoted():
    cmd = autostart.launch_command()
    assert cmd.startswith('"') and cmd.endswith("-m lockcontrol --minimized")


def test_verifier_per_platform(monkeypatch):
    monkeypatch.setattr(verify.sys, "platform", "linux")
    assert isinstance(verify.default_verifier(), NoOsVerifier)
    assert verify.os_auth_name() == ""
    monkeypatch.setattr(verify.sys, "platform", "darwin")
    assert isinstance(verify.default_verifier(), MacVerifier)
    assert verify.os_name() == "ماك"


@pytest.mark.skipif(sys.platform == "darwin", reason="pyobjc موجود على ماك")
def test_mac_verifier_without_pyobjc_is_unavailable():
    assert MacVerifier().verify("x") is VerifyOutcome.UNAVAILABLE


def test_no_os_verifier_means_pin_only(fake_keyring):
    sec = SecurityManager(SecretStore(fake_keyring), NoOsVerifier())
    assert not sec.os_auth_supported
    assert sec.verify_os("x") is VerifyOutcome.VERIFIED
    assert sec.is_day_verified()


# ----- الاختصار العام على ماك ولينكس -----

from lockcontrol.ui import hotkeys  # noqa: E402


def test_to_pynput_conversion():
    assert hotkeys.to_pynput("Ctrl+Alt+O", "linux") == "<ctrl>+<alt>+o"
    assert hotkeys.to_pynput("Ctrl+Shift+5", "linux") == "<ctrl>+<shift>+5"
    assert hotkeys.to_pynput("Alt+F12", "linux") == "<alt>+<f12>"
    # على ماك: Control في Qt هو Command
    assert hotkeys.to_pynput("Ctrl+Alt+O", "darwin") == "<cmd>+<alt>+o"
    for bad in ("", "O", "Ctrl+Left"):
        with pytest.raises(hotkeys.HotkeyError):
            hotkeys.to_pynput(bad, "linux")


def test_pynput_events_deliver_on_qt_thread(qtbot):
    calls = []
    events = hotkeys.PynputSystemEvents(lambda: calls.append(1))
    events._fired.emit()  # كما يفعل خيط pynput
    qtbot.waitUntil(lambda: calls == [1], timeout=2000)
    assert not events.supports_session_lock


def _fake_pynput(monkeypatch, global_hotkeys):
    """وحدة pynput مزيفة: الاختبار لا يحتاج شاشة ولا أذونات لوحة مفاتيح."""
    import types

    keyboard = types.ModuleType("pynput.keyboard")
    keyboard.GlobalHotKeys = global_hotkeys
    package = types.ModuleType("pynput")
    package.keyboard = keyboard
    monkeypatch.setitem(sys.modules, "pynput", package)
    monkeypatch.setitem(sys.modules, "pynput.keyboard", keyboard)


def test_pynput_registration_failure_is_hotkey_error(monkeypatch):
    class Broken:
        def __init__(self, *a, **k):
            raise OSError("no display")

    _fake_pynput(monkeypatch, Broken)
    events = hotkeys.PynputSystemEvents(lambda: None)
    with pytest.raises(hotkeys.HotkeyError):
        events.register_hotkey("Ctrl+Alt+O")
    events.detach()


def test_pynput_registers_and_stops(monkeypatch):
    started = {}

    class FakeListener:
        def __init__(self, mapping):
            started["combo"] = list(mapping)

        def start(self):
            started["running"] = True

        def stop(self):
            started["running"] = False

    _fake_pynput(monkeypatch, FakeListener)
    events = hotkeys.PynputSystemEvents(lambda: None)
    events.register_hotkey("Ctrl+Alt+O")
    assert started == {"combo": [hotkeys.to_pynput("Ctrl+Alt+O")], "running": True}
    events.detach()
    assert started["running"] is False


def test_linux_gate_skips_os_dialog(qtbot, tmp_path, fake_keyring, monkeypatch):
    from lockcontrol.app_context import AppContext
    from lockcontrol.core.storage import SettingsStore
    from lockcontrol.ui import auth

    class NoDialog:
        def __init__(self, *a, **k):
            pytest.fail("لا يجب عرض نافذة تحقق النظام على لينكس")

    monkeypatch.setattr(auth, "AuthGateDialog", NoDialog)
    ctx = AppContext(SettingsStore(tmp_path), SecretStore(fake_keyring), NoOsVerifier())
    ctx.security.set_pin("1234")
    assert auth.ensure_verified(ctx)
    assert ctx.security.is_day_verified()
