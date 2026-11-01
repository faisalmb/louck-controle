"""التحقق من هوية مستخدم ويندوز.

الأولوية لـ Windows Hello (بصمة/وجه/PIN ويندوز). إذا لم يكن مُعدّاً على الجهاز
نعرض نافذة كلمة مرور حساب ويندوز (CredUI) ونتحقق منها عبر LogonUserW.
"""

import asyncio
import ctypes
import sys
import threading
import time
from ctypes import wintypes

from .verify import VerifyOutcome


# ---------- Windows Hello ----------

# قيم UserConsentVerificationResult
_HELLO_VERIFIED = 0
_HELLO_NOT_SETUP = {1, 2}  # DeviceNotPresent, NotConfiguredForUser
_HELLO_CANCELED = 6


def _hello_module():
    import winrt.windows.security.credentials.ui as ui

    return ui


def hello_available() -> bool:
    try:
        ui = _hello_module()

        async def check():
            return await ui.UserConsentVerifier.check_availability_async()

        return int(asyncio.run(check())) == 0
    except Exception:
        return False


def _bring_hello_dialog_to_front(timeout: float = 3.0) -> None:
    """نافذة Hello في تطبيقات سطح المكتب قد تظهر خلف البرنامج؛ نرفعها للمقدمة."""
    user32 = ctypes.windll.user32
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        hwnd = user32.FindWindowW("Credential Dialog Xaml Host", None)
        if hwnd:
            user32.SetForegroundWindow(hwnd)
            return
        time.sleep(0.1)


def _hello_verify(message: str) -> int:
    ui = _hello_module()

    async def request():
        return await ui.UserConsentVerifier.request_verification_async(message)

    threading.Thread(target=_bring_hello_dialog_to_front, daemon=True).start()
    return int(asyncio.run(request()))


# ---------- كلمة مرور ويندوز (البديل) ----------

_ERROR_CANCELLED = 1223
_CREDUIWIN_ENUMERATE_CURRENT_USER = 0x200
_CRED_PACK_PROTECTED_CREDENTIALS = 0x1
_LOGON32_LOGON_NETWORK = 3
_LOGON32_PROVIDER_DEFAULT = 0


class _CREDUI_INFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hwndParent", wintypes.HWND),
        ("pszMessageText", wintypes.LPCWSTR),
        ("pszCaptionText", wintypes.LPCWSTR),
        ("hbmBanner", wintypes.HBITMAP),
    ]


def logon_user_valid(username: str, domain: str | None, password: str) -> bool:
    token = wintypes.HANDLE()
    ok = ctypes.windll.advapi32.LogonUserW(
        wintypes.LPCWSTR(username),
        wintypes.LPCWSTR(domain) if domain else None,
        wintypes.LPCWSTR(password),
        _LOGON32_LOGON_NETWORK,
        _LOGON32_PROVIDER_DEFAULT,
        ctypes.byref(token),
    )
    if ok:
        ctypes.windll.kernel32.CloseHandle(token)
    return bool(ok)


def _password_verify(message: str, caption: str, hwnd: int | None) -> VerifyOutcome:
    credui = ctypes.windll.credui
    ole32 = ctypes.windll.ole32

    info = _CREDUI_INFOW(ctypes.sizeof(_CREDUI_INFOW), hwnd or None, message, caption, None)
    auth_package = wintypes.ULONG(0)
    out_buf = ctypes.c_void_p()
    out_size = wintypes.ULONG(0)
    save = wintypes.BOOL(False)

    err = credui.CredUIPromptForWindowsCredentialsW(
        ctypes.byref(info), 0, ctypes.byref(auth_package), None, 0,
        ctypes.byref(out_buf), ctypes.byref(out_size), ctypes.byref(save),
        _CREDUIWIN_ENUMERATE_CURRENT_USER,
    )
    if err == _ERROR_CANCELLED:
        return VerifyOutcome.CANCELED
    if err != 0:
        return VerifyOutcome.FAILED

    user = ctypes.create_unicode_buffer(514)
    domain = ctypes.create_unicode_buffer(338)
    password = ctypes.create_unicode_buffer(514)
    user_len, domain_len, pass_len = wintypes.DWORD(514), wintypes.DWORD(338), wintypes.DWORD(514)
    try:
        unpacked = credui.CredUnPackAuthenticationBufferW(
            _CRED_PACK_PROTECTED_CREDENTIALS, out_buf, out_size,
            user, ctypes.byref(user_len), domain, ctypes.byref(domain_len),
            password, ctypes.byref(pass_len),
        )
        if not unpacked:
            return VerifyOutcome.FAILED
        name, dom = user.value, domain.value
        if not dom and "\\" in name:
            dom, name = name.split("\\", 1)
        return VerifyOutcome.VERIFIED if logon_user_valid(name, dom, password.value) else VerifyOutcome.FAILED
    finally:
        ctypes.memset(password, 0, ctypes.sizeof(password))
        ctypes.memset(out_buf, 0, out_size.value)
        ole32.CoTaskMemFree(out_buf)


# ---------- الواجهة العامة ----------


class WindowsVerifier:
    supported = True

    def verify(self, message: str, hwnd: int | None = None) -> VerifyOutcome:
        if sys.platform != "win32":
            return VerifyOutcome.UNAVAILABLE
        if hello_available():
            result = _hello_verify(message)
            if result == _HELLO_VERIFIED:
                return VerifyOutcome.VERIFIED
            if result == _HELLO_CANCELED:
                return VerifyOutcome.CANCELED
            if result not in _HELLO_NOT_SETUP:
                return VerifyOutcome.FAILED
        return _password_verify(message, "LockControl", hwnd)
