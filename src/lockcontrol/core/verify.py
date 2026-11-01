"""التحقق من هوية مستخدم النظام، مستقلاً عن نظام التشغيل.

- ويندوز: Windows Hello، وبديله كلمة مرور الحساب.
- ماك: Touch ID، وبديله كلمة مرور الجهاز.
- لينكس: لا يوجد معيار موحّد، فيُكتفى بـ PIN البرنامج.
"""

import enum
import sys
from typing import Protocol

from ..i18n import t


class VerifyOutcome(enum.Enum):
    VERIFIED = "verified"
    CANCELED = "canceled"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class Verifier(Protocol):
    # False: لا يوجد تحقق من النظام، والـ PIN وحده يحمي البرنامج.
    supported: bool

    def verify(self, message: str, hwnd: int | None = None) -> VerifyOutcome: ...


class NoOsVerifier:
    supported = False

    def verify(self, message: str, hwnd: int | None = None) -> VerifyOutcome:
        return VerifyOutcome.VERIFIED


def default_verifier() -> Verifier:
    if sys.platform == "win32":
        from .windows_auth import WindowsVerifier

        return WindowsVerifier()
    if sys.platform == "darwin":
        from .macos_auth import MacVerifier

        return MacVerifier()
    return NoOsVerifier()


def os_name() -> str:
    return {"win32": t("ويندوز"), "darwin": t("ماك")}.get(sys.platform, t("لينكس"))


def os_auth_name() -> str:
    return {"win32": "Windows Hello", "darwin": "Touch ID"}.get(sys.platform, "")
