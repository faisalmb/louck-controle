import sys
from datetime import date, timedelta

import pytest

from lockcontrol.core import windows_auth
from lockcontrol.core.security import (
    LOCKOUT_SECONDS,
    PinStatus,
    SecurityManager,
    hash_pin,
    pin_matches,
    validate_pin,
)
from lockcontrol.core.storage import SecretStore
from lockcontrol.core.windows_auth import VerifyOutcome


class FakeVerifier:
    def __init__(self, outcome=VerifyOutcome.VERIFIED):
        self.outcome = outcome
        self.calls = 0

    def verify(self, message, hwnd=None):
        self.calls += 1
        return self.outcome


class Env:
    def __init__(self, fake_keyring):
        self.t = 1000.0
        self.day = date(2026, 11, 1)
        self.verifier = FakeVerifier()
        self.secrets = SecretStore(fake_keyring)
        self.sec = SecurityManager(
            self.secrets, self.verifier, clock=lambda: self.t, today=lambda: self.day
        )

    def ready(self, pin="1234"):
        self.sec.verify_windows("msg")
        self.sec.set_pin(pin)
        return self.sec


@pytest.fixture
def env(fake_keyring):
    return Env(fake_keyring)


def test_validate_pin():
    assert validate_pin("1234") and validate_pin("12345678")
    assert not validate_pin("123") and not validate_pin("123456789")
    assert not validate_pin("12a4") and not validate_pin("١٢٣٤")  # أرقام هندية مرفوضة


def test_hash_is_salted_and_verifiable():
    a, b = hash_pin("1234"), hash_pin("1234")
    assert a != b and "1234" not in a
    assert pin_matches("1234", a) and not pin_matches("4321", a)
    assert not pin_matches("1234", "garbage")


def test_day_verification_expires_next_day(env):
    assert not env.sec.is_day_verified()
    assert env.sec.verify_windows("msg") is VerifyOutcome.VERIFIED
    assert env.sec.is_day_verified()
    env.day += timedelta(days=1)
    assert not env.sec.is_day_verified()


def test_failed_windows_verification_does_not_mark_day(env):
    env.verifier.outcome = VerifyOutcome.CANCELED
    assert env.sec.verify_windows("msg") is VerifyOutcome.CANCELED
    assert not env.sec.is_day_verified()


def test_pin_requires_day_verification(env):
    env.sec.set_pin("1234")
    assert env.sec.check_pin("1234").status is PinStatus.REVERIFY_REQUIRED
    env.sec.verify_windows("msg")
    assert env.sec.check_pin("1234").status is PinStatus.OK


def test_pin_not_set(env):
    env.sec.verify_windows("msg")
    assert env.sec.check_pin("1234").status is PinStatus.NOT_SET


def test_lockout_after_three_then_reverify_after_five(env):
    sec = env.ready()
    assert sec.check_pin("0000").status is PinStatus.WRONG
    assert sec.check_pin("0000").status is PinStatus.WRONG
    r = sec.check_pin("0000")
    assert r.status is PinStatus.LOCKED and r.locked_seconds == LOCKOUT_SECONDS
    # أثناء الإيقاف حتى الرمز الصحيح مرفوض
    assert sec.check_pin("1234").status is PinStatus.LOCKED
    env.t += LOCKOUT_SECONDS + 1
    assert sec.check_pin("0000").status is PinStatus.WRONG
    assert sec.check_pin("0000").status is PinStatus.REVERIFY_REQUIRED
    assert not sec.is_day_verified()


def test_remaining_attempts_counts_down(env):
    sec = env.ready()
    assert sec.check_pin("0000").remaining_attempts == 2
    assert sec.check_pin("0000").remaining_attempts == 1


def test_correct_pin_resets_failures(env):
    sec = env.ready()
    sec.check_pin("0000")
    sec.check_pin("0000")
    assert sec.check_pin("1234").status is PinStatus.OK
    assert sec.check_pin("0000").remaining_attempts == 2


def test_change_pin_needs_current(env):
    sec = env.ready()
    assert not sec.set_pin("5678")
    assert not sec.set_pin("5678", current_pin="9999")
    assert sec.set_pin("5678", current_pin="1234")
    assert sec.check_pin("5678").status is PinStatus.OK


def test_reset_pin_needs_windows(env):
    sec = env.ready()
    env.verifier.outcome = VerifyOutcome.CANCELED
    assert sec.reset_pin("5678", "msg") is VerifyOutcome.CANCELED
    assert sec.check_pin("1234").status is PinStatus.OK
    env.verifier.outcome = VerifyOutcome.VERIFIED
    assert sec.reset_pin("5678", "msg") is VerifyOutcome.VERIFIED
    assert sec.check_pin("5678").status is PinStatus.OK


def test_invalid_new_pin_raises(env):
    with pytest.raises(ValueError):
        env.sec.set_pin("12")


def test_invalidate_day(env):
    sec = env.ready()
    sec.invalidate_day()
    assert sec.check_pin("1234").status is PinStatus.REVERIFY_REQUIRED


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_real_logon_rejects_bad_password():
    assert windows_auth.logon_user_valid("lockcontrol_no_such_user", ".", "wrong") is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_real_hello_availability_check_runs():
    assert isinstance(windows_auth.hello_available(), bool)


def test_pin_unlocks_the_day(env):
    sec = env.ready()  # تعيين الـ PIN يُحسب تحققاً لليوم
    assert sec.is_unlocked_today()
    env.day += timedelta(days=1)
    assert not sec.is_unlocked_today()
    sec.verify_windows("msg")
    assert not sec.is_unlocked_today()  # ويندوز وحده لا يكفي
    assert sec.check_pin("1234").status is PinStatus.OK
    assert sec.is_unlocked_today()


def test_session_lock_ends_daily_unlock(env):
    sec = env.ready()
    sec.invalidate_day()
    assert not sec.is_unlocked_today()
