"""تصدير الإعدادات واستيرادها بملف مشفّر بكلمة مرور، للنقل إلى جهاز آخر.

أسرار Credential Manager مرتبطة بحساب ويندوز ولا تنتقل بنسخ الملفات، لذلك تُضمَّن هنا:
Client Secret وبصمة الـ PIN. التوكن لا يُصدَّر (يُجلب من جديد)، ولا حالة التحقق اليومي.
"""

import base64
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .storage import SecretStore, Settings

FORMAT = "lockcontrol-backup"
VERSION = 1
EXPORTED_SECRETS = ("client_secret", "pin_hash")
_N, _R, _P = 2**15, 8, 1


class BackupError(Exception):
    pass


def _key(password: str, salt: bytes, n: int = _N, r: int = _R, p: int = _P) -> bytes:
    raw = Scrypt(salt=salt, length=32, n=n, r=r, p=p).derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


def export_backup(path: Path, password: str, settings: Settings, secrets: SecretStore) -> None:
    if len(password) < 6:
        raise BackupError("كلمة مرور الملف يجب أن تكون 6 أحرف على الأقل.")
    payload = {
        "settings": settings.to_dict(),
        "secrets": {name: secrets.get(name) for name in EXPORTED_SECRETS if secrets.get(name)},
    }
    salt = os.urandom(16)
    token = Fernet(_key(password, salt)).encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    document = {
        "format": FORMAT,
        "version": VERSION,
        "kdf": {"name": "scrypt", "n": _N, "r": _R, "p": _P, "salt": base64.b64encode(salt).decode()},
        "data": token.decode(),
    }
    Path(path).write_text(json.dumps(document, indent=2), encoding="utf-8")


def import_backup(path: Path, password: str, secrets: SecretStore) -> Settings:
    """يعيد الإعدادات المستوردة ويكتب الأسرار. حفظ الإعدادات مسؤولية المستدعي."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        if document.get("format") != FORMAT:
            raise BackupError("الملف ليس نسخة احتياطية لهذا البرنامج.")
        kdf = document["kdf"]
        key = _key(password, base64.b64decode(kdf["salt"]), int(kdf["n"]), int(kdf["r"]), int(kdf["p"]))
        payload = json.loads(Fernet(key).decrypt(document["data"].encode()))
    except InvalidToken:
        raise BackupError("كلمة المرور غير صحيحة أو الملف تالف.") from None
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise BackupError(f"تعذر قراءة الملف: {e}") from None

    for name, value in payload.get("secrets", {}).items():
        if name in EXPORTED_SECRETS and isinstance(value, str):
            secrets.set(name, value)
    secrets.delete("token")  # توكن الجهاز القديم/الحساب السابق لا يُستخدم
    return Settings.from_dict(payload.get("settings"))
