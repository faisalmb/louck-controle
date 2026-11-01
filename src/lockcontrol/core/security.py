"""طبقتا الحماية: تحقق ويندوز مرة يومياً، ثم PIN البرنامج عند كل فتح للقفل.

الحالة (يوم آخر تحقق، المحاولات الفاشلة، الإيقاف المؤقت) تُحفظ في Credential Manager
لا في ملف الإعدادات، فلا يمكن تجاوزها بتعديل الملف.
"""

import base64
import enum
import hashlib
import hmac
import os
import threading
import time
from dataclasses import dataclass
from datetime import date
from typing import Callable

from .storage import SecretStore
from .verify import Verifier, VerifyOutcome

PIN_MIN, PIN_MAX = 4, 8
LOCKOUT_AFTER = 3
LOCKOUT_SECONDS = 60
REVERIFY_AFTER = 5

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


class PinStatus(enum.Enum):
    OK = "ok"
    WRONG = "wrong"
    LOCKED = "locked"
    REVERIFY_REQUIRED = "reverify_required"
    NOT_SET = "not_set"


@dataclass(frozen=True)
class PinResult:
    status: PinStatus
    remaining_attempts: int = 0
    locked_seconds: int = 0


def validate_pin(pin: str) -> bool:
    return pin.isdigit() and pin.isascii() and PIN_MIN <= len(pin) <= PIN_MAX


def hash_pin(pin: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    b64 = lambda b: base64.b64encode(b).decode()
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${b64(salt)}${b64(digest)}"


def pin_matches(pin: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        actual = hashlib.scrypt(
            pin.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32
        )
        return hmac.compare_digest(actual, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


class SecurityManager:
    def __init__(
        self,
        secrets: SecretStore,
        verifier: Verifier,
        *,
        clock: Callable[[], float] = time.time,
        today: Callable[[], date] = date.today,
    ):
        self._secrets = secrets
        self._verifier = verifier
        self._clock = clock
        self._today = today
        self._lock = threading.Lock()

    # ----- تحقق النظام اليومي -----

    @property
    def os_auth_supported(self) -> bool:
        """False على لينكس: لا نافذة تحقق، والـ PIN وحده يحمي البرنامج."""
        return getattr(self._verifier, "supported", True)

    def is_day_verified(self) -> bool:
        return self._state().get("verified_day") == self._today().isoformat()

    def is_unlocked_today(self) -> bool:
        """تحقق ويندوز والـ PIN كلاهما تمّا اليوم."""
        state, today = self._state(), self._today().isoformat()
        return state.get("verified_day") == today and state.get("pin_day") == today

    def verify_os(self, message: str, hwnd: int | None = None) -> VerifyOutcome:
        outcome = self._verifier.verify(message, hwnd)
        if outcome is VerifyOutcome.VERIFIED:
            with self._lock:
                self._save_state(verified_day=self._today().isoformat(), failed=0, locked_until=0)
        return outcome

    def invalidate_day(self) -> None:
        with self._lock:
            self._save_state(verified_day="")

    # ----- PIN -----

    def has_pin(self) -> bool:
        return bool(self._secrets.get("pin_hash"))

    def set_pin(self, new_pin: str, current_pin: str | None = None) -> bool:
        """تعيين أول PIN، أو تغييره بإدخال الحالي. بعد نسيانه استخدم reset_pin."""
        if not validate_pin(new_pin):
            raise ValueError(f"الـ PIN يجب أن يكون من {PIN_MIN} إلى {PIN_MAX} أرقام")
        if self.has_pin():
            if current_pin is None or self.check_pin(current_pin).status is not PinStatus.OK:
                return False
        self._secrets.set("pin_hash", hash_pin(new_pin))
        self._mark_pin_today()
        return True

    def reset_pin(self, new_pin: str, message: str, hwnd: int | None = None) -> VerifyOutcome:
        """نسيت الـ PIN: تحقق ويندوز جديد ثم PIN جديد."""
        if not validate_pin(new_pin):
            raise ValueError(f"الـ PIN يجب أن يكون من {PIN_MIN} إلى {PIN_MAX} أرقام")
        outcome = self.verify_os(message, hwnd)
        if outcome is VerifyOutcome.VERIFIED:
            self._secrets.set("pin_hash", hash_pin(new_pin))
            self._mark_pin_today()
        return outcome

    def check_pin(self, pin: str) -> PinResult:
        with self._lock:
            stored = self._secrets.get("pin_hash")
            if not stored:
                return PinResult(PinStatus.NOT_SET)
            state = self._state()
            if state.get("verified_day") != self._today().isoformat():
                return PinResult(PinStatus.REVERIFY_REQUIRED)
            locked = int(state.get("locked_until", 0) - self._clock())
            if locked > 0:
                return PinResult(PinStatus.LOCKED, locked_seconds=locked)

            if pin_matches(pin, stored):
                self._save_state(failed=0, locked_until=0, pin_day=self._today().isoformat())
                return PinResult(PinStatus.OK)

            failed = int(state.get("failed", 0)) + 1
            if failed >= REVERIFY_AFTER:
                self._save_state(verified_day="", failed=0, locked_until=0)
                return PinResult(PinStatus.REVERIFY_REQUIRED)
            if failed == LOCKOUT_AFTER:
                self._save_state(failed=failed, locked_until=self._clock() + LOCKOUT_SECONDS)
                return PinResult(PinStatus.LOCKED, REVERIFY_AFTER - failed, LOCKOUT_SECONDS)
            self._save_state(failed=failed)
            next_limit = LOCKOUT_AFTER if failed < LOCKOUT_AFTER else REVERIFY_AFTER
            return PinResult(PinStatus.WRONG, remaining_attempts=next_limit - failed)

    # ----- الحالة -----

    def _mark_pin_today(self) -> None:
        with self._lock:
            self._save_state(pin_day=self._today().isoformat())

    def _state(self) -> dict:
        state = self._secrets.get_json("auth_state")
        return state if isinstance(state, dict) else {}

    def _save_state(self, **changes) -> None:
        self._secrets.set_json("auth_state", {**self._state(), **changes})
