from datetime import date

import pytest
from PySide6.QtWidgets import QDialog

from lockcontrol.app_context import AppContext
from lockcontrol.core.errors import TuyaError
from lockcontrol.core.lock_service import LockOpenError, LockStatus, RemoteLock
from lockcontrol.core.security import PinStatus
from lockcontrol.core.storage import LockInfo, SecretStore, SettingsStore
from lockcontrol.core.verify import VerifyOutcome
from lockcontrol.ui.auth import PinDialog, PinMode
from lockcontrol.ui.main_window import MainWindow
from lockcontrol.ui.settings_dialog import SettingsDialog


class FakeVerifier:
    def verify(self, message, hwnd=None):
        return VerifyOutcome.VERIFIED


class FakeService:
    def __init__(self):
        self.opened: list[tuple[str, str]] = []
        self.fail_with: Exception | None = None

    def status(self, device_id):
        return LockStatus(online=True, battery=80)

    def open(self, device_id, preferred_method=""):
        if self.fail_with:
            raise self.fail_with
        self.opened.append((device_id, preferred_method))
        return "open_door"


@pytest.fixture
def ctx(tmp_path, fake_keyring):
    service = FakeService()
    c = AppContext(SettingsStore(tmp_path), SecretStore(fake_keyring), FakeVerifier(), lambda creds, tokens: service)
    c.fake_service = service
    c.update_tuya("eu", "cid", "uid", "secret")
    c.set_locks([LockInfo("d1", "الباب الرئيسي"), LockInfo("d2", "المكتب")], "d2")
    return c


def make_window(qtbot, ctx, allow=True):
    w = MainWindow(ctx, authorize_fn=lambda c, p: allow)
    qtbot.addWidget(w)
    return w


def test_main_window_selects_default_and_shows_status(qtbot, ctx):
    w = make_window(qtbot, ctx)
    assert w.selected_lock().device_id == "d2"
    assert "⭐" in w.lock_combo.currentText()
    qtbot.waitUntil(lambda: "البطارية 80%" in w.status_label.text(), timeout=3000)


def test_open_success_records_history_and_method(qtbot, ctx):
    w = make_window(qtbot, ctx)
    with qtbot.waitSignal(w.open_finished, timeout=3000) as sig:
        w.open_selected()
    assert sig.args == [True]
    assert ctx.fake_service.opened == [("d2", "")]
    assert ctx.settings.find_lock("d2").open_method == "open_door"
    assert SettingsStore(ctx.store.data_dir).load().find_lock("d2").open_method == "open_door"
    history = ctx.store.load_history()
    assert history[-1].ok and history[-1].lock_name == "المكتب"
    assert "تم فتح المكتب" in w.message.text()


def test_open_failure_shows_arabic_error(qtbot, ctx):
    ctx.fake_service.fail_with = LockOpenError({"door_operate": TuyaError(2001, "device is offline")})
    w = make_window(qtbot, ctx)
    with qtbot.waitSignal(w.open_finished, timeout=3000) as sig:
        w.open_selected()
    assert sig.args == [False]
    assert w.message.text() == "القفل غير متصل بالإنترنت."
    assert not ctx.store.load_history()[-1].ok
    assert w.open_button.isEnabled()


def test_open_blocked_without_authorization(qtbot, ctx):
    w = make_window(qtbot, ctx, allow=False)
    w.open_selected()
    assert ctx.fake_service.opened == []


def test_open_default_switches_selection(qtbot, ctx):
    w = make_window(qtbot, ctx)
    w.lock_combo.setCurrentIndex(w.lock_combo.findData("d1"))
    with qtbot.waitSignal(w.open_finished, timeout=3000):
        w.open_default()
    assert ctx.fake_service.opened[-1][0] == "d2"


def test_unconfigured_window_guides_user(qtbot, tmp_path, fake_keyring):
    c = AppContext(SettingsStore(tmp_path), SecretStore(fake_keyring), FakeVerifier())
    w = make_window(qtbot, c)
    assert "الإعدادات" in w.status_label.text()
    assert not w.open_button.isEnabled()


def test_settings_dialog_saves_everything(qtbot, ctx):
    d = SettingsDialog(ctx)
    qtbot.addWidget(d)
    d.client_id.setText("cid2")
    d.uid.setText("uid2")
    d.region.setCurrentIndex(d.region.findData("us"))
    d.secret.setText("")  # الإبقاء على السر المحفوظ
    d.lock_list.item(0).setText("البوابة")
    d.lock_list.setCurrentRow(0)
    d._make_default()
    d.start_with_windows.setChecked(True)
    d.save()

    loaded = SettingsStore(ctx.store.data_dir).load()
    assert (loaded.tuya.client_id, loaded.tuya.uid, loaded.tuya.region) == ("cid2", "uid2", "us")
    assert loaded.default_lock_id == "d1"
    assert loaded.find_lock("d1").name == "البوابة"
    assert loaded.ui.start_with_windows
    assert ctx.client_secret() == "secret"


def test_settings_cancel_does_not_save(qtbot, ctx):
    d = SettingsDialog(ctx)
    qtbot.addWidget(d)
    d.lock_list.setCurrentRow(0)
    d._make_default()
    d.reject()
    assert SettingsStore(ctx.store.data_dir).load().default_lock_id == "d2"


def test_settings_sync_merges_remote_locks(qtbot, ctx, monkeypatch):
    d = SettingsDialog(ctx)
    qtbot.addWidget(d)
    remote = [RemoteLock("d1", "Remote", "ms", True), RemoteLock("d9", "قفل جديد", "ms", True)]
    monkeypatch.setattr(d, "_fetch_remote_locks", lambda include_all: remote)
    d.sync_locks()
    qtbot.waitUntil(lambda: d.lock_list.count() == 2 and "تمت المزامنة" in d.sync_result.text(), timeout=3000)
    names = [d.lock_list.item(i).text() for i in range(2)]
    assert names == ["الباب الرئيسي", "قفل جديد"]
    # القفل الافتراضي d2 حُذف من الحساب فيصبح الأول افتراضياً
    assert d._default_id == "d1"


def test_pin_dialog_wrong_then_right(qtbot, ctx):
    ctx.security.verify_os("m")
    ctx.security.set_pin("2468")
    d = PinDialog(ctx, PinMode.ENTER)
    qtbot.addWidget(d)
    d.current.setText("1111")
    d.submit()
    assert "المحاولات المتبقية" in d.message.text()
    d.current.setText("2468")
    d.submit()
    assert d.result() == QDialog.DialogCode.Accepted


def test_pin_dialog_setup_validates(qtbot, ctx):
    ctx.security.verify_os("m")
    d = PinDialog(ctx, PinMode.SETUP)
    qtbot.addWidget(d)
    d.new.setText("12")
    d.confirm.setText("12")
    d.submit()
    assert not ctx.security.has_pin()
    d.new.setText("1357")
    d.confirm.setText("1350")
    d.submit()
    assert "غير متطابقين" in d.message.text()
    d.confirm.setText("1357")
    d.submit()
    assert ctx.security.check_pin("1357").status is PinStatus.OK


def test_settings_export_then_import(qtbot, ctx, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

    path = str(tmp_path / "b.lcb")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (path, ""))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (path, ""))
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("pass123", True))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: pytest.fail(str(a)))

    d = SettingsDialog(ctx)
    qtbot.addWidget(d)
    d.export_settings()

    ctx.set_locks([], "")
    d2 = SettingsDialog(ctx)
    qtbot.addWidget(d2)
    d2.import_settings()
    assert d2.result() == QDialog.DialogCode.Accepted
    assert [l.device_id for l in ctx.settings.locks] == ["d1", "d2"]
    assert SettingsStore(ctx.store.data_dir).load().default_lock_id == "d2"


class _ShouldNotOpen:
    def __init__(self, *a, **k):
        pytest.fail("لم يكن يجب طلب أي نافذة تحقق")


def _count_pin_prompts(monkeypatch):
    from lockcontrol.ui import auth

    prompts = []

    class FakePin:
        REVERIFY = 2

        def __init__(self, ctx, mode, parent=None):
            prompts.append(mode)

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(auth, "PinDialog", FakePin)
    monkeypatch.setattr(auth, "AuthGateDialog", _ShouldNotOpen)
    return prompts


def test_authorize_asks_pin_once_per_day(ctx, monkeypatch):
    from lockcontrol.core.security import hash_pin
    from lockcontrol.ui.auth import authorize

    ctx.security.verify_os("m")
    ctx.secrets.set("pin_hash", hash_pin("1234"))
    prompts = _count_pin_prompts(monkeypatch)
    assert authorize(ctx)  # أول فتح اليوم: يُطلب
    assert prompts == [PinMode.ENTER]
    ctx.security._mark_pin_today()  # ما يفعله check_pin عند النجاح
    assert authorize(ctx) and authorize(ctx)
    assert prompts == [PinMode.ENTER]


def test_authorize_every_time_when_enabled(ctx, monkeypatch):
    from lockcontrol.core.security import hash_pin
    from lockcontrol.ui.auth import authorize

    ctx.security.verify_os("m")
    ctx.secrets.set("pin_hash", hash_pin("1234"))
    ctx.security._mark_pin_today()
    prompts = _count_pin_prompts(monkeypatch)
    assert authorize(ctx)
    assert prompts == []
    ctx.settings.ui.pin_every_open = True
    assert authorize(ctx)
    assert authorize(ctx, force_pin=True)
    assert prompts == [PinMode.ENTER, PinMode.ENTER]
