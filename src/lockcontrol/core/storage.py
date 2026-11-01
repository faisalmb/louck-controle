"""تخزين دائم للبرنامج.

- الإعدادات غير السرية في settings.json، والسجل في history.json داخل مجلد بيانات البرنامج
  (%APPDATA%\\LockControl، أو ~/Library/Application Support/LockControl، أو ~/.config/lockcontrol).
- الأسرار (Client Secret، التوكن، بصمة PIN...) في مخزن أسرار النظام عبر keyring:
  Windows Credential Manager، أو Keychain على ماك، أو Secret Service على لينكس.
- كل كتابة ذرّية: ملف مؤقت ثم os.replace، مع نسخة .bak تُستعاد إذا تلف الملف الأصلي.
"""

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from .token_manager import Token

APP_NAME = "LockControl"
SCHEMA_VERSION = 1
HISTORY_LIMIT = 200


def default_data_dir(platform: str = sys.platform) -> Path:
    if platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    if platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_NAME.lower()


# ---------- ملفات JSON ----------


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    if path.exists():
        os.replace(path, path.with_suffix(path.suffix + ".bak"))
    os.replace(tmp, path)


def read_json_with_backup(path: Path) -> Any | None:
    """يقرأ الملف، وإن كان مفقوداً أو تالفاً يقرأ النسخة الاحتياطية. None إذا فشل الاثنان."""
    for candidate in (path, path.with_suffix(path.suffix + ".bak")):
        try:
            with open(candidate, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            continue
    return None


# ---------- نماذج الإعدادات ----------


def _from_dict(cls, data: Any):
    """ينشئ dataclass من قاموس متسامحاً مع المفاتيح الناقصة أو الزائدة."""
    if not isinstance(data, dict):
        return cls()
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class TuyaSettings:
    region: str = "eu"
    client_id: str = ""
    uid: str = ""  # UID حساب تطبيق Smart Life المرتبط بالمشروع


@dataclass
class LockInfo:
    device_id: str
    name: str = ""
    category: str = ""
    # مسار الفتح الذي نجح آخر مرة لهذا القفل، لتجربته أولاً في المرة القادمة.
    open_method: str = ""


@dataclass
class UiSettings:
    start_with_windows: bool = False
    minimize_to_tray: bool = True
    hotkey: str = "Ctrl+Alt+O"
    language: str = "ar"
    reverify_on_session_lock: bool = False
    # False: الـ PIN مرة يومياً مع تحقق ويندوز عند أول فتح. True: عند كل فتح للقفل.
    pin_every_open: bool = False


@dataclass
class Settings:
    tuya: TuyaSettings = field(default_factory=TuyaSettings)
    locks: list[LockInfo] = field(default_factory=list)
    default_lock_id: str = ""
    ui: UiSettings = field(default_factory=UiSettings)

    def default_lock(self) -> LockInfo | None:
        for lock in self.locks:
            if lock.device_id == self.default_lock_id:
                return lock
        return self.locks[0] if self.locks else None

    def find_lock(self, device_id: str) -> LockInfo | None:
        return next((l for l in self.locks if l.device_id == device_id), None)

    def to_dict(self) -> dict:
        return {"version": SCHEMA_VERSION, **asdict(self)}

    @classmethod
    def from_dict(cls, data: Any) -> "Settings":
        if not isinstance(data, dict):
            return cls()
        locks = [
            _from_dict(LockInfo, l)
            for l in data.get("locks", [])
            if isinstance(l, dict) and l.get("device_id")
        ]
        return cls(
            tuya=_from_dict(TuyaSettings, data.get("tuya")),
            locks=locks,
            default_lock_id=str(data.get("default_lock_id", "")),
            ui=_from_dict(UiSettings, data.get("ui")),
        )


@dataclass
class HistoryEntry:
    time: str
    device_id: str
    lock_name: str
    ok: bool
    message: str = ""

    @classmethod
    def now(cls, device_id: str, lock_name: str, ok: bool, message: str = "") -> "HistoryEntry":
        return cls(datetime.now().isoformat(timespec="seconds"), device_id, lock_name, ok, message)


class SettingsStore:
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or default_data_dir()
        self.settings_path = self.data_dir / "settings.json"
        self.history_path = self.data_dir / "history.json"

    def load(self) -> Settings:
        return Settings.from_dict(read_json_with_backup(self.settings_path))

    def save(self, settings: Settings) -> None:
        atomic_write_json(self.settings_path, settings.to_dict())

    def load_history(self) -> list[HistoryEntry]:
        data = read_json_with_backup(self.history_path)
        if not isinstance(data, list):
            return []
        return [_from_dict(HistoryEntry, e) for e in data if isinstance(e, dict) and "time" in e]

    def append_history(self, entry: HistoryEntry) -> None:
        history = self.load_history()
        history.append(entry)
        atomic_write_json(self.history_path, [asdict(e) for e in history[-HISTORY_LIMIT:]])


# ---------- الأسرار ----------


class KeyringBackend(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...
    def set_password(self, service: str, username: str, password: str) -> None: ...
    def delete_password(self, service: str, username: str) -> None: ...


class SecretStore:
    """أسماء الأسرار: client_secret, token, pin_hash, auth_state."""

    def __init__(self, backend: KeyringBackend | None = None, service: str = APP_NAME):
        if backend is None:
            import keyring

            backend = keyring
        self._backend = backend
        self._service = service

    def get(self, name: str) -> str | None:
        return self._backend.get_password(self._service, name)

    def set(self, name: str, value: str) -> None:
        self._backend.set_password(self._service, name, value)

    def delete(self, name: str) -> None:
        try:
            self._backend.delete_password(self._service, name)
        except Exception:
            # غير موجود أصلاً
            pass

    def get_json(self, name: str) -> Any | None:
        raw = self.get(name)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    def set_json(self, name: str, value: Any) -> None:
        self.set(name, json.dumps(value, separators=(",", ":")))


class KeyringTokenStore:
    """TokenStore يحفظ توكن تويا في Credential Manager."""

    def __init__(self, secrets: SecretStore):
        self._secrets = secrets

    def load(self) -> Token | None:
        data = self._secrets.get_json("token")
        if not isinstance(data, dict):
            return None
        try:
            return Token(
                data["access_token"], data["refresh_token"], float(data["expires_at"]), data.get("uid", "")
            )
        except (KeyError, TypeError, ValueError):
            return None

    def save(self, token: Token) -> None:
        self._secrets.set_json("token", asdict(token))

    def clear(self) -> None:
        self._secrets.delete("token")
