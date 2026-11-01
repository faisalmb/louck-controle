import json

import pytest

from lockcontrol.core.backup import BackupError, export_backup, import_backup
from lockcontrol.core.security import hash_pin, pin_matches
from lockcontrol.core.storage import LockInfo, SecretStore, Settings


@pytest.fixture
def source(fake_keyring):
    secrets = SecretStore(fake_keyring)
    secrets.set("client_secret", "my-secret")
    secrets.set("pin_hash", hash_pin("2468"))
    secrets.set_json("token", {"access_token": "old"})
    secrets.set_json("auth_state", {"verified_day": "2026-11-01"})
    settings = Settings()
    settings.tuya.client_id = "cid"
    settings.locks = [LockInfo("d1", "الباب")]
    settings.default_lock_id = "d1"
    return settings, secrets


def test_round_trip_to_new_machine(tmp_path, source):
    from tests.conftest import FakeKeyring

    settings, secrets = source
    path = tmp_path / "backup.lcb"
    export_backup(path, "pass123", settings, secrets)

    raw = path.read_text(encoding="utf-8")
    assert "my-secret" not in raw and "الباب" not in raw and "cid" not in raw

    target = SecretStore(FakeKeyring())
    target.set_json("token", {"access_token": "stale"})
    imported = import_backup(path, "pass123", target)
    assert imported == settings
    assert target.get("client_secret") == "my-secret"
    assert pin_matches("2468", target.get("pin_hash"))
    assert target.get("token") is None
    assert target.get("auth_state") is None  # التحقق اليومي لا ينتقل


def test_wrong_password(tmp_path, source):
    settings, secrets = source
    path = tmp_path / "b.lcb"
    export_backup(path, "pass123", settings, secrets)
    with pytest.raises(BackupError, match="كلمة المرور"):
        import_backup(path, "wrong!!", secrets)


def test_short_password_rejected(tmp_path, source):
    with pytest.raises(BackupError):
        export_backup(tmp_path / "b.lcb", "123", *source)


def test_foreign_or_corrupt_file(tmp_path, source):
    _, secrets = source
    other = tmp_path / "x.json"
    other.write_text(json.dumps({"hello": 1}), encoding="utf-8")
    with pytest.raises(BackupError, match="ليس نسخة"):
        import_backup(other, "pass123", secrets)
    broken = tmp_path / "y.lcb"
    broken.write_text("not json", encoding="utf-8")
    with pytest.raises(BackupError):
        import_backup(broken, "pass123", secrets)
