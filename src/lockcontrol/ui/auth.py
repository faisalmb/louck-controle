"""نوافذ الحماية: تحقق ويندوز اليومي، وإدخال/تعيين/تغيير الـ PIN."""

import enum

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..app_context import AppContext
from ..core.security import PIN_MAX, PIN_MIN, PinStatus, validate_pin
from ..core.windows_auth import VerifyOutcome
from .style import set_role
from .worker import run_in_background

VERIFY_MESSAGE = "تأكيد هويتك لفتح برنامج التحكم بالأقفال"


class _ForegroundDialog(QDialog):
    """قد تُفتح من الاختصار العام والنافذة مخفية، فنرفعها للمقدمة."""

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()
        self.activateWindow()


def _pin_field() -> QLineEdit:
    field = QLineEdit()
    field.setEchoMode(QLineEdit.EchoMode.Password)
    field.setMaxLength(PIN_MAX)
    field.setValidator(QRegularExpressionValidator(r"[0-9]*"))
    field.setAlignment(Qt.AlignmentFlag.AlignCenter)
    field.setInputMethodHints(Qt.InputMethodHint.ImhDigitsOnly)
    return field


class AuthGateDialog(_ForegroundDialog):
    """تحقق ويندوز (Hello أو كلمة المرور). يبدأ تلقائياً عند الظهور."""

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("التحقق من الهوية")
        self.setMinimumWidth(360)

        self.info = QLabel("للمتابعة تحقق من هويتك عبر ويندوز.\nيُطلب هذا مرة واحدة يومياً.")
        self.info.setWordWrap(True)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.retry = QPushButton("تحقق الآن")
        self.retry.clicked.connect(self.start)
        cancel = QPushButton("إلغاء")
        cancel.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.info)
        layout.addWidget(self.status)
        layout.addWidget(self.retry)
        layout.addWidget(cancel)
        QTimer.singleShot(250, self.start)

    def start(self):
        self.retry.setEnabled(False)
        set_role(self.status, "muted")
        self.status.setText("بانتظار Windows Hello...")
        hwnd = int(self.winId())
        run_in_background(
            lambda: self.ctx.security.verify_windows(VERIFY_MESSAGE, hwnd), self._done, self._error
        )

    def _done(self, outcome: VerifyOutcome):
        if outcome is VerifyOutcome.VERIFIED:
            self.accept()
            return
        texts = {
            VerifyOutcome.CANCELED: "أُلغي التحقق.",
            VerifyOutcome.FAILED: "فشل التحقق.",
            VerifyOutcome.UNAVAILABLE: "التحقق عبر ويندوز غير متاح على هذا الجهاز.",
        }
        self._show_error(texts[outcome])

    def _error(self, e: Exception):
        self._show_error(f"تعذر التحقق: {e}")

    def _show_error(self, text: str):
        set_role(self.status, "error")
        self.status.setText(text)
        self.retry.setEnabled(True)


class PinMode(enum.Enum):
    ENTER = "enter"
    SETUP = "setup"
    CHANGE = "change"


class PinDialog(_ForegroundDialog):
    # نتيجة إضافية لـ exec(): يجب إعادة تحقق ويندوز
    REVERIFY = 2

    def __init__(self, ctx: AppContext, mode: PinMode, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.mode = mode
        self.setMinimumWidth(320)
        titles = {
            PinMode.ENTER: "أدخل الـ PIN",
            PinMode.SETUP: "تعيين PIN للبرنامج",
            PinMode.CHANGE: "تغيير الـ PIN",
        }
        self.setWindowTitle(titles[mode])

        self.current = _pin_field()
        self.new = _pin_field()
        self.confirm = _pin_field()
        self.message = QLabel("")
        self.message.setWordWrap(True)

        form = QFormLayout()
        if mode is PinMode.ENTER:
            form.addRow("الـ PIN:", self.current)
        else:
            if mode is PinMode.CHANGE:
                form.addRow("الـ PIN الحالي:", self.current)
            form.addRow("الـ PIN الجديد:", self.new)
            form.addRow("تأكيد الـ PIN:", self.confirm)
            hint = QLabel(f"من {PIN_MIN} إلى {PIN_MAX} أرقام.")
            hint.setObjectName("muted")
            form.addRow(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("موافق")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("إلغاء")
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.message)
        if mode is PinMode.ENTER:
            forgot = QPushButton("نسيت الـ PIN؟")
            forgot.setFlat(True)
            forgot.clicked.connect(self.forgot)
            layout.addWidget(forgot)
        layout.addWidget(buttons)

        self._unlock_timer = QTimer(self)
        self._unlock_timer.setInterval(1000)
        self._unlock_timer.timeout.connect(self._tick)
        self._locked_seconds = 0

    def _error(self, text: str):
        set_role(self.message, "error")
        self.message.setText(text)

    def submit(self):
        if self.mode is PinMode.ENTER:
            self._submit_enter()
            return
        new, confirm = self.new.text(), self.confirm.text()
        if not validate_pin(new):
            self._error(f"الـ PIN يجب أن يكون من {PIN_MIN} إلى {PIN_MAX} أرقام.")
            return
        if new != confirm:
            self._error("الرمزان غير متطابقين.")
            return
        current = self.current.text() if self.mode is PinMode.CHANGE else None
        if self.ctx.security.set_pin(new, current):
            self.accept()
        else:
            self._error("الـ PIN الحالي غير صحيح.")

    def _submit_enter(self):
        result = self.ctx.security.check_pin(self.current.text())
        self.current.clear()
        if result.status is PinStatus.OK:
            self.accept()
        elif result.status is PinStatus.WRONG:
            self._error(f"رمز خاطئ. المحاولات المتبقية قبل الإيقاف: {result.remaining_attempts}")
        elif result.status is PinStatus.LOCKED:
            self._locked_seconds = result.locked_seconds
            self.ok_button.setEnabled(False)
            self.current.setEnabled(False)
            self._tick()
            self._unlock_timer.start()
        elif result.status is PinStatus.REVERIFY_REQUIRED:
            self.done(self.REVERIFY)
        elif result.status is PinStatus.NOT_SET:
            self._error("لم يُعيَّن PIN بعد.")

    def _tick(self):
        if self._locked_seconds <= 0:
            self._unlock_timer.stop()
            self.ok_button.setEnabled(True)
            self.current.setEnabled(True)
            self.message.setText("")
            return
        self._error(f"محاولات خاطئة كثيرة. انتظر {self._locked_seconds} ثانية.")
        self._locked_seconds -= 1

    def forgot(self):
        """إعادة تعيين الـ PIN تتطلب تحقق ويندوز جديداً."""
        dialog = PinResetDialog(self.ctx, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.accept()


class PinResetDialog(_ForegroundDialog):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("إعادة تعيين الـ PIN")
        self.new = _pin_field()
        self.confirm = _pin_field()
        self.message = QLabel("سيُطلب منك التحقق عبر ويندوز بعد إدخال الرمز الجديد.")
        self.message.setWordWrap(True)
        form = QFormLayout()
        form.addRow("الـ PIN الجديد:", self.new)
        form.addRow("تأكيد الـ PIN:", self.confirm)
        self.ok = QPushButton("تحقق وحفظ")
        self.ok.clicked.connect(self.submit)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.message)
        layout.addWidget(self.ok)

    def submit(self):
        new = self.new.text()
        if not validate_pin(new) or new != self.confirm.text():
            self.message.setText(f"أدخل رمزين متطابقين من {PIN_MIN} إلى {PIN_MAX} أرقام.")
            return
        self.ok.setEnabled(False)
        hwnd = int(self.winId())
        run_in_background(
            lambda: self.ctx.security.reset_pin(new, VERIFY_MESSAGE, hwnd), self._done, self._failed
        )

    def _done(self, outcome: VerifyOutcome):
        if outcome is VerifyOutcome.VERIFIED:
            self.accept()
        else:
            self.message.setText("لم يكتمل التحقق، لم يتغير الـ PIN.")
            self.ok.setEnabled(True)

    def _failed(self, e: Exception):
        self.message.setText(f"تعذر التحقق: {e}")
        self.ok.setEnabled(True)


def ensure_verified(ctx: AppContext, parent: QWidget | None = None) -> bool:
    """تحقق ويندوز إن لم يتم اليوم، ثم تعيين PIN إن لم يوجد."""
    if not ctx.security.is_day_verified():
        if AuthGateDialog(ctx, parent).exec() != QDialog.DialogCode.Accepted:
            return False
    if not ctx.security.has_pin():
        return PinDialog(ctx, PinMode.SETUP, parent).exec() == QDialog.DialogCode.Accepted
    return True


def authorize(ctx: AppContext, parent: QWidget | None = None, *, force_pin: bool = False) -> bool:
    """البوابة قبل أي عملية حساسة. افتراضياً: تحقق ويندوز + PIN عند أول فتح في اليوم فقط.
    force_pin أو خيار «PIN عند كل فتح» يطلبان الـ PIN في كل مرة."""
    every_time = force_pin or ctx.settings.ui.pin_every_open
    if not every_time and ctx.security.is_unlocked_today():
        return True
    for _ in range(2):
        had_pin = ctx.security.has_pin()
        if not ensure_verified(ctx, parent):
            return False
        if not had_pin:
            return True  # عيّن الـ PIN للتو، فلا داعي لطلبه مرة أخرى
        result = PinDialog(ctx, PinMode.ENTER, parent).exec()
        if result == QDialog.DialogCode.Accepted:
            return True
        if result != PinDialog.REVERIFY:
            return False
    return False


def daily_gate(ctx: AppContext, parent: QWidget | None = None) -> bool:
    """عند أول فتح للبرنامج/النافذة: تحقق ويندوز، والـ PIN أيضاً إن كان مرة يومياً."""
    if ctx.settings.ui.pin_every_open:
        return ensure_verified(ctx, parent)
    return authorize(ctx, parent)
