"""أحداث ويندوز على مستوى النظام: الاختصار العام (RegisterHotKey) وقفل الجلسة (Win+L)."""

import ctypes
import time
from ctypes import wintypes
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QKeyCombination, Qt
from PySide6.QtGui import QKeySequence

from ..i18n import t
from .hotkeys import HotkeyError

WM_HOTKEY = 0x0312
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
NOTIFY_FOR_THIS_SESSION = 0

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000

HOTKEY_ID = 0x4C43  # "LC"
HOTKEY_DEBOUNCE_SECONDS = 0.5


def parse_hotkey(text: str) -> tuple[int, int]:
    """'Ctrl+Alt+O' ← (modifiers, virtual key) لـ RegisterHotKey."""
    sequence = QKeySequence(text)
    if sequence.isEmpty():
        raise HotkeyError(t("اختصار فارغ"))
    combo: QKeyCombination = sequence[0]
    key, mods = combo.key(), combo.keyboardModifiers()

    win_mods = MOD_NOREPEAT
    if mods & Qt.KeyboardModifier.ControlModifier:
        win_mods |= MOD_CONTROL
    if mods & Qt.KeyboardModifier.AltModifier:
        win_mods |= MOD_ALT
    if mods & Qt.KeyboardModifier.ShiftModifier:
        win_mods |= MOD_SHIFT
    if mods & Qt.KeyboardModifier.MetaModifier:
        win_mods |= MOD_WIN
    if win_mods == MOD_NOREPEAT:
        raise HotkeyError(t("الاختصار يحتاج Ctrl أو Alt أو Shift أو Win"))

    k = key.value if hasattr(key, "value") else int(key)
    if Qt.Key.Key_A.value <= k <= Qt.Key.Key_Z.value or Qt.Key.Key_0.value <= k <= Qt.Key.Key_9.value:
        vk = k  # رموز Qt للحروف والأرقام تساوي رموز ويندوز
    elif Qt.Key.Key_F1.value <= k <= Qt.Key.Key_F24.value:
        vk = 0x70 + (k - Qt.Key.Key_F1.value)
    elif k == Qt.Key.Key_Space.value:
        vk = 0x20
    else:
        raise HotkeyError(t("استخدم حرفاً أو رقماً أو مفتاح F"))
    return win_mods, vk


class WindowsEventFilter(QAbstractNativeEventFilter):
    """يستقبل WM_HOTKEY وإشعارات الجلسة للنافذة المسجّلة."""

    def __init__(self, on_hotkey: Callable[[], None], on_session_lock: Callable[[], None]):
        super().__init__()
        self._on_hotkey = on_hotkey
        self._on_session_lock = on_session_lock
        self._hwnd: int | None = None
        self._hotkey_registered = False
        self._last_hotkey = 0.0

    def attach(self, hwnd: int) -> None:
        self._hwnd = hwnd
        ctypes.windll.wtsapi32.WTSRegisterSessionNotification(wintypes.HWND(hwnd), NOTIFY_FOR_THIS_SESSION)

    def detach(self) -> None:
        self.unregister_hotkey()
        if self._hwnd:
            ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(wintypes.HWND(self._hwnd))
            self._hwnd = None

    def register_hotkey(self, text: str) -> None:
        """يرمي HotkeyError إذا كان الاختصار غير صالح أو محجوزاً لبرنامج آخر."""
        mods, vk = parse_hotkey(text)
        self.unregister_hotkey()
        if not ctypes.windll.user32.RegisterHotKey(wintypes.HWND(self._hwnd), HOTKEY_ID, mods, vk):
            raise HotkeyError(t("الاختصار مستخدم من برنامج آخر"))
        self._hotkey_registered = True

    def unregister_hotkey(self) -> None:
        if self._hotkey_registered:
            ctypes.windll.user32.UnregisterHotKey(wintypes.HWND(self._hwnd), HOTKEY_ID)
            self._hotkey_registered = False

    def nativeEventFilter(self, event_type, message):
        # PySide6 يمرر النوع كـ QByteArray
        kind = event_type.data() if hasattr(event_type, "data") else bytes(event_type)
        if kind != b"windows_generic_MSG":
            return False, 0
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
            # قد تصل الرسالة نفسها للمرشح مرتين (من حلقة الأحداث ومن نافذة Qt)
            now = time.monotonic()
            if now - self._last_hotkey > HOTKEY_DEBOUNCE_SECONDS:
                self._last_hotkey = now
                self._on_hotkey()
            return True, 0
        if msg.message == WM_WTSSESSION_CHANGE and msg.wParam == WTS_SESSION_LOCK:
            self._on_session_lock()
        return False, 0
