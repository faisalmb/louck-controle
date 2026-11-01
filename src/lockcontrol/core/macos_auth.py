"""Touch ID على ماك، مع كلمة مرور الجهاز بديلاً (LAPolicyDeviceOwnerAuthentication)."""

import threading

from .verify import VerifyOutcome

# رموز LAError
_USER_CANCEL, _SYSTEM_CANCEL, _APP_CANCEL, _USER_FALLBACK = -2, -4, -9, -3
VERIFY_TIMEOUT_SECONDS = 120


class MacVerifier:
    supported = True

    def verify(self, message: str, hwnd: int | None = None) -> VerifyOutcome:
        try:
            from LocalAuthentication import LAContext, LAPolicyDeviceOwnerAuthentication
        except ImportError:
            return VerifyOutcome.UNAVAILABLE

        context = LAContext.new()
        can, _error = context.canEvaluatePolicy_error_(LAPolicyDeviceOwnerAuthentication, None)
        if not can:
            return VerifyOutcome.UNAVAILABLE

        done = threading.Event()
        result: dict = {}

        def reply(success, error):
            result["ok"] = bool(success)
            result["code"] = int(error.code()) if error is not None else 0
            done.set()

        context.evaluatePolicy_localizedReason_reply_(LAPolicyDeviceOwnerAuthentication, message, reply)
        if not done.wait(VERIFY_TIMEOUT_SECONDS):
            return VerifyOutcome.CANCELED
        if result.get("ok"):
            return VerifyOutcome.VERIFIED
        if result.get("code") in (_USER_CANCEL, _SYSTEM_CANCEL, _APP_CANCEL, _USER_FALLBACK):
            return VerifyOutcome.CANCELED
        return VerifyOutcome.FAILED
