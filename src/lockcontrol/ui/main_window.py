"""النافذة الرئيسية: زر فتح كبير للقفل المحدد (الافتراضي أولاً) مع حالته."""

from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..app_context import AppContext
from ..core.lock_service import LockStatus
from ..core.storage import LockInfo
from .auth import authorize
from .messages import describe_error
from .style import set_role
from .worker import run_in_background

Authorize = Callable[[AppContext, QWidget], bool]

BATTERY_STATES = {"high": "عالية", "medium": "متوسطة", "low": "منخفضة ⚠", "poweroff": "فارغة ⚠"}


class MainWindow(QMainWindow):
    open_finished = Signal(bool)  # للاختبارات ولأيقونة شريط المهام

    def __init__(self, ctx: AppContext, authorize_fn: Authorize = authorize):
        super().__init__()
        self.ctx = ctx
        self._authorize = authorize_fn
        self._busy = False
        self.setWindowTitle("التحكم بالأقفال")
        self.setMinimumSize(380, 520)

        title = QLabel("التحكم بالأقفال")
        title.setObjectName("title")
        self.settings_button = QPushButton("⚙ الإعدادات")
        self.history_button = QPushButton("السجل")
        header = QHBoxLayout()
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.history_button)
        header.addWidget(self.settings_button)
        # يحدده المتحكم: True يعني إخفاء النافذة إلى شريط المهام بدل إغلاقها.
        self.close_to_tray: Callable[[], bool] = lambda: False

        self.lock_combo = QComboBox()
        self.lock_combo.currentIndexChanged.connect(self.refresh_status)
        self.status_label = QLabel("")
        set_role(self.status_label, "muted")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.open_button = QPushButton("فتح")
        self.open_button.setObjectName("openButton")
        self.open_button.setFixedSize(180, 180)
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_button.clicked.connect(self.open_selected)

        self.message = QLabel("")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addLayout(header)
        layout.addSpacing(12)
        layout.addWidget(self.lock_combo)
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(self.open_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(12)
        layout.addWidget(self.message)
        layout.addStretch()
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(lambda: self.message.setText(""))

        self.reload_locks()

    def closeEvent(self, event) -> None:
        if self.close_to_tray():
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)

    # ----- قائمة الأقفال -----

    def reload_locks(self) -> None:
        settings = self.ctx.settings
        default = settings.default_lock()
        self.lock_combo.blockSignals(True)
        self.lock_combo.clear()
        for lock in settings.locks:
            star = " ⭐" if default and lock.device_id == default.device_id else ""
            self.lock_combo.addItem(lock.name + star, lock.device_id)
        if default:
            self.lock_combo.setCurrentIndex(self.lock_combo.findData(default.device_id))
        self.lock_combo.blockSignals(False)

        has_locks = bool(settings.locks)
        self.lock_combo.setVisible(has_locks)
        self.open_button.setEnabled(has_locks and not self._busy)
        if not self.ctx.is_configured():
            self.status_label.setText("أكمل إعدادات الربط بتويا من ⚙ الإعدادات.")
        elif not has_locks:
            self.status_label.setText("لا توجد أقفال. زامنها من ⚙ الإعدادات ← الأقفال.")
        else:
            self.refresh_status()

    def selected_lock(self) -> LockInfo | None:
        device_id = self.lock_combo.currentData()
        return self.ctx.settings.find_lock(device_id) if device_id else None

    def refresh_status(self) -> None:
        lock = self.selected_lock()
        if not lock or not self.ctx.is_configured():
            return
        self.status_label.setText("جارٍ قراءة الحالة...")
        device_id = lock.device_id

        def done(status: LockStatus):
            if self.lock_combo.currentData() != device_id:
                return  # تغيّر الاختيار أثناء الطلب
            parts = ["● متصل" if status.online else "○ غير متصل"]
            if status.battery is not None:
                parts.append(f"البطارية {status.battery}%")
            elif status.battery_state:
                state = BATTERY_STATES.get(status.battery_state, status.battery_state)
                parts.append(f"البطارية: {state}")
            self.status_label.setText(" · ".join(parts))

        def failed(e: Exception):
            if self.lock_combo.currentData() == device_id:
                self.status_label.setText(describe_error(e))

        run_in_background(lambda: self.ctx.lock_service().status(device_id), done, failed)

    # ----- الفتح -----

    def open_default(self) -> None:
        default = self.ctx.settings.default_lock()
        if default:
            self.lock_combo.setCurrentIndex(self.lock_combo.findData(default.device_id))
        self.open_selected()

    def open_selected(self) -> None:
        lock = self.selected_lock()
        if self._busy or lock is None:
            return
        if not self.ctx.is_configured():
            self._show("أكمل إعدادات الربط بتويا أولاً.", ok=False)
            return
        if not self._authorize(self.ctx, self):
            return

        self._set_busy(True)
        self._show(f"جارٍ فتح {lock.name}...", ok=None)

        def done(method: str):
            self.ctx.remember_open_method(lock.device_id, method)
            self.ctx.record(lock, True, method)
            self._set_busy(False)
            self._show(f"✓ تم فتح {lock.name}", ok=True)
            self.open_finished.emit(True)

        def failed(e: Exception):
            text = describe_error(e)
            self.ctx.record(lock, False, text)
            self._set_busy(False)
            self._show(text, ok=False)
            self.open_finished.emit(False)

        run_in_background(
            lambda: self.ctx.lock_service().open(lock.device_id, lock.open_method), done, failed
        )

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.open_button.setEnabled(not busy and bool(self.ctx.settings.locks))
        self.open_button.setText("..." if busy else "فتح")

    def _show(self, text: str, ok: bool | None) -> None:
        set_role(self.message, {True: "success", False: "error", None: "muted"}[ok])
        self.message.setText(text)
        self._clear_timer.stop()
        if ok is not None:
            self._clear_timer.start(6000)
