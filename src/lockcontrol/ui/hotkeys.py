"""الاختصار العام وإشعار قفل الجلسة لكل نظام تشغيل.

- ويندوز: RegisterHotKey وإشعارات WTS (انظر win_events.py).
- ماك ولينكس: مكتبة pynput. على ماك تتطلب إذن «المراقبة/تسهيلات الاستخدام»،
  وعلى لينكس تعمل في جلسات X11 لا Wayland.
"""

import sys
from typing import Callable, Protocol

from PySide6.QtCore import QKeyCombination, QObject, Qt, Signal, Slot
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QWidget

from ..i18n import t


class HotkeyError(ValueError):
    pass


def to_pynput(text: str, platform: str = sys.platform) -> str:
    """'Ctrl+Alt+O' ← '<ctrl>+<alt>+o' بصيغة pynput."""
    sequence = QKeySequence(text)
    if sequence.isEmpty():
        raise HotkeyError(t("اختصار فارغ"))
    combo: QKeyCombination = sequence[0]
    key, mods = combo.key(), combo.keyboardModifiers()

    # على ماك يسمي Qt مفتاح Command «Control» ومفتاح Control «Meta».
    ctrl_name, meta_name = ("<cmd>", "<ctrl>") if platform == "darwin" else ("<ctrl>", "<cmd>")
    parts = []
    if mods & Qt.KeyboardModifier.ControlModifier:
        parts.append(ctrl_name)
    if mods & Qt.KeyboardModifier.AltModifier:
        parts.append("<alt>")
    if mods & Qt.KeyboardModifier.ShiftModifier:
        parts.append("<shift>")
    if mods & Qt.KeyboardModifier.MetaModifier:
        parts.append(meta_name)
    if not parts:
        raise HotkeyError(t("الاختصار يحتاج مفتاح تعديل مثل Ctrl أو Alt"))

    k = key.value
    if Qt.Key.Key_A.value <= k <= Qt.Key.Key_Z.value or Qt.Key.Key_0.value <= k <= Qt.Key.Key_9.value:
        parts.append(chr(k).lower())
    elif Qt.Key.Key_F1.value <= k <= Qt.Key.Key_F24.value:
        parts.append(f"<f{k - Qt.Key.Key_F1.value + 1}>")
    elif k == Qt.Key.Key_Space.value:
        parts.append("<space>")
    else:
        raise HotkeyError(t("استخدم حرفاً أو رقماً أو مفتاح F"))
    return "+".join(parts)


class SystemEvents(Protocol):
    supports_session_lock: bool

    def attach(self, window: QWidget) -> None: ...
    def register_hotkey(self, text: str) -> None: ...
    def detach(self) -> None: ...


class WindowsSystemEvents:
    supports_session_lock = True

    def __init__(self, app: QApplication, on_hotkey: Callable[[], None], on_session_lock: Callable[[], None]):
        from .win_events import WindowsEventFilter

        self._app = app
        self._filter = WindowsEventFilter(on_hotkey, on_session_lock)

    def attach(self, window: QWidget) -> None:
        self._app.installNativeEventFilter(self._filter)
        self._filter.attach(int(window.winId()))

    def register_hotkey(self, text: str) -> None:
        self._filter.register_hotkey(text)

    def detach(self) -> None:
        self._filter.detach()
        self._app.removeNativeEventFilter(self._filter)


class PynputSystemEvents(QObject):
    """pynput يستدعي الدالة من خيطه الخاص؛ الإشارة تنقلها إلى خيط الواجهة."""

    supports_session_lock = False
    _fired = Signal()

    def __init__(self, on_hotkey: Callable[[], None]):
        super().__init__()
        self._on_hotkey = on_hotkey
        self._listener = None
        self._fired.connect(self._handle)

    @Slot()
    def _handle(self) -> None:
        self._on_hotkey()

    def attach(self, window: QWidget) -> None:
        pass

    def register_hotkey(self, text: str) -> None:
        combo = to_pynput(text)
        self.detach()
        try:
            from pynput import keyboard

            self._listener = keyboard.GlobalHotKeys({combo: self._fired.emit})
            self._listener.start()
        except Exception as e:  # لا شاشة X11، أو لا إذن على ماك
            self._listener = None
            raise HotkeyError(t("تعذر تفعيل الاختصار على هذا النظام: {e}", e=e)) from e

    def detach(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None


def create_system_events(
    app: QApplication, on_hotkey: Callable[[], None], on_session_lock: Callable[[], None]
) -> SystemEvents:
    if sys.platform == "win32":
        return WindowsSystemEvents(app, on_hotkey, on_session_lock)
    return PynputSystemEvents(on_hotkey)
