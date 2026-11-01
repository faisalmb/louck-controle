import json
import sys
import uuid

import pytest

from lockcontrol.core.storage import (
    HISTORY_LIMIT,
    HistoryEntry,
    KeyringTokenStore,
    LockInfo,
    SecretStore,
    Settings,
    SettingsStore,
)
from lockcontrol.core.token_manager import Token


def sample_settings() -> Settings:
    s = Settings()
    s.tuya.client_id = "cid"
    s.tuya.uid = "uid1"
    s.locks = [LockInfo("d1", "الباب الرئيسي", "jtmspro"), LockInfo("d2", "المكتب")]
    s.default_lock_id = "d2"
    s.ui.hotkey = "Ctrl+Alt+L"
    return s


def test_missing_file_gives_defaults(tmp_path):
    s = SettingsStore(tmp_path).load()
    assert s == Settings()
    assert s.default_lock() is None


def test_round_trip_keeps_arabic_and_all_fields(tmp_path):
    store = SettingsStore(tmp_path)
    store.save(sample_settings())
    assert store.load() == sample_settings()
    assert "الباب الرئيسي" in store.settings_path.read_text(encoding="utf-8")


def test_save_leaves_no_tmp_and_keeps_backup(tmp_path):
    store = SettingsStore(tmp_path)
    first = sample_settings()
    store.save(first)
    second = sample_settings()
    second.default_lock_id = "d1"
    store.save(second)
    assert not list(tmp_path.glob("*.tmp"))
    backup = json.loads((tmp_path / "settings.json.bak").read_text(encoding="utf-8"))
    assert backup["default_lock_id"] == "d2"


def test_corrupt_file_recovers_from_backup(tmp_path):
    store = SettingsStore(tmp_path)
    store.save(sample_settings())
    store.save(sample_settings())  # ينشئ .bak
    store.settings_path.write_text("{ broken", encoding="utf-8")
    assert store.load() == sample_settings()


def test_unknown_and_missing_keys_are_tolerated(tmp_path):
    store = SettingsStore(tmp_path)
    store.settings_path.parent.mkdir(parents=True, exist_ok=True)
    store.settings_path.write_text(
        json.dumps({"tuya": {"client_id": "x", "future": 1}, "locks": [{"name": "no id"}], "ui": None}),
        encoding="utf-8",
    )
    s = store.load()
    assert s.tuya.client_id == "x" and s.tuya.region == "eu"
    assert s.locks == []


def test_default_lock_falls_back_to_first():
    s = sample_settings()
    assert s.default_lock().device_id == "d2"
    s.default_lock_id = "gone"
    assert s.default_lock().device_id == "d1"


def test_history_is_capped(tmp_path):
    store = SettingsStore(tmp_path)
    for i in range(HISTORY_LIMIT + 5):
        store.append_history(HistoryEntry.now("d1", "باب", i % 2 == 0, str(i)))
    history = store.load_history()
    assert len(history) == HISTORY_LIMIT
    assert history[-1].message == str(HISTORY_LIMIT + 4)


def test_secret_store_json_and_delete(fake_keyring):
    secrets = SecretStore(fake_keyring)
    secrets.set_json("x", {"a": 1})
    assert secrets.get_json("x") == {"a": 1}
    secrets.delete("x")
    secrets.delete("x")  # حذف غير الموجود لا يرمي خطأ
    assert secrets.get("x") is None


def test_token_store_round_trip(fake_keyring):
    store = KeyringTokenStore(SecretStore(fake_keyring))
    assert store.load() is None
    token = Token("at", "rt", 123.5, "u")
    store.save(token)
    assert store.load() == token
    store.clear()
    assert store.load() is None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Credential Manager")
def test_real_windows_credential_manager():
    service = f"LockControlTest-{uuid.uuid4().hex[:8]}"
    secrets = SecretStore(service=service)
    try:
        secrets.set("client_secret", "سر-تجريبي")
        assert SecretStore(service=service).get("client_secret") == "سر-تجريبي"
    finally:
        secrets.delete("client_secret")
    assert secrets.get("client_secret") is None
