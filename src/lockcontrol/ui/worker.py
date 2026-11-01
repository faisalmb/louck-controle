"""تنفيذ طلبات الشبكة في خيط خلفي حتى لا تتجمد الواجهة."""

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

_pending: set["_Relay"] = set()


class _Relay(QObject):
    """يعيش في الخيط الرئيسي، فتُنفَّذ الدوال المستدعاة في الخيط الرئيسي."""

    done = Signal(object)
    failed = Signal(object)

    def __init__(self, on_done, on_error):
        super().__init__()
        self._on_done, self._on_error = on_done, on_error
        self.done.connect(self._handle_done)
        self.failed.connect(self._handle_failed)

    @Slot(object)
    def _handle_done(self, result):
        _pending.discard(self)
        self._on_done(result)

    @Slot(object)
    def _handle_failed(self, error):
        _pending.discard(self)
        self._on_error(error)


class _Task(QRunnable):
    def __init__(self, fn, relay: _Relay):
        super().__init__()
        self._fn, self._relay = fn, relay

    def run(self):
        try:
            result = self._fn()
        except Exception as e:  # تُعرض للمستخدم عبر on_error
            self._relay.failed.emit(e)
        else:
            self._relay.done.emit(result)


def run_in_background(
    fn: Callable[[], Any],
    on_done: Callable[[Any], None],
    on_error: Callable[[Exception], None],
) -> None:
    relay = _Relay(on_done, on_error)
    _pending.add(relay)
    QThreadPool.globalInstance().start(_Task(fn, relay))
