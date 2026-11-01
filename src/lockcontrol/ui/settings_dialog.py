"""نافذة الإعدادات: الربط بتويا، الأقفال والقفل الافتراضي، والخيارات العامة."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..app_context import AppContext
from ..core.backup import BackupError, export_backup, import_backup
from ..core.lock_service import LockService, RemoteLock, merge_locks
from ..core.storage import LockInfo
from ..core.token_manager import MemoryTokenStore
from ..core.tuya_client import REGION_NAMES, TuyaClient, TuyaCredentials
from .auth import PinDialog, PinMode
from .messages import describe_error
from .style import set_role
from .worker import run_in_background

DEVICE_ROLE = Qt.ItemDataRole.UserRole


class SettingsDialog(QDialog):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("الإعدادات")
        self.setMinimumSize(480, 440)
        # نسخة عمل من الأقفال؛ لا تُحفظ إلا عند الضغط على «حفظ».
        self._locks = [LockInfo(**vars(l)) for l in ctx.settings.locks]
        self._default_id = ctx.settings.default_lock_id

        tabs = QTabWidget()
        tabs.addTab(self._build_tuya_tab(), "الربط بتويا")
        tabs.addTab(self._build_locks_tab(), "الأقفال")
        tabs.addTab(self._build_general_tab(), "عام")
        self.tabs = tabs

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("حفظ")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("إلغاء")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # ----- تبويب الربط -----

    def _build_tuya_tab(self) -> QWidget:
        t = self.ctx.settings.tuya
        self.region = QComboBox()
        for key, name in REGION_NAMES.items():
            self.region.addItem(f"{name} ({key})", key)
        self.region.setCurrentIndex(max(0, self.region.findData(t.region)))

        self.client_id = QLineEdit(t.client_id)
        self.client_id.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.secret = QLineEdit()
        self.secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        if self.ctx.client_secret():
            self.secret.setPlaceholderText("محفوظ — اتركه فارغاً للإبقاء عليه")
        self.uid = QLineEdit(t.uid)
        self.uid.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        self.test_button = QPushButton("اختبار الاتصال")
        self.test_button.clicked.connect(self.test_connection)
        self.test_result = QLabel("")
        self.test_result.setWordWrap(True)

        help_text = QLabel(
            'البيانات من موقع <a href="https://platform.tuya.com/cloud">Tuya IoT Platform</a>:<br>'
            "• Client ID و Client Secret: صفحة المشروع ← Overview<br>"
            "• معرّف الحساب (اختياري): Devices ← Link App Account"
        )
        help_text.setOpenExternalLinks(True)
        help_text.setWordWrap(True)
        set_role(help_text, "muted")

        form = QFormLayout()
        form.addRow("مركز البيانات:", self.region)
        form.addRow("Client ID:", self.client_id)
        form.addRow("Client Secret:", self.secret)
        self.uid.setPlaceholderText("اختياري")
        form.addRow("معرّف الحساب (UID):", self.uid)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self.test_button)
        layout.addWidget(self.test_result)
        layout.addStretch()
        layout.addWidget(help_text)
        page = QWidget()
        page.setLayout(layout)
        return page

    def _form_credentials(self) -> TuyaCredentials:
        secret = self.secret.text().strip() or self.ctx.client_secret()
        return TuyaCredentials(self.client_id.text().strip(), secret, self.region.currentData())

    def _temp_service(self) -> tuple[LockService, TuyaClient]:
        client = TuyaClient(self._form_credentials(), MemoryTokenStore())
        return LockService(client), client

    def _fetch_remote_locks(self, include_all: bool) -> list[RemoteLock]:
        service, client = self._temp_service()
        try:
            return service.list_locks(self.uid.text().strip(), include_all)
        finally:
            client.close()

    def _form_complete(self) -> bool:
        c = self._form_credentials()
        return bool(c.client_id and c.client_secret)

    def test_connection(self) -> None:
        if not self._form_complete():
            set_role(self.test_result, "error")
            self.test_result.setText("أدخل Client ID و Client Secret.")
            return
        self.test_button.setEnabled(False)
        set_role(self.test_result, "muted")
        self.test_result.setText("جارٍ الاتصال...")

        def done(locks: list[RemoteLock]):
            self.test_button.setEnabled(True)
            set_role(self.test_result, "success")
            self.test_result.setText(f"✓ تم الاتصال. عدد الأقفال في الحساب: {len(locks)}")

        def failed(e: Exception):
            self.test_button.setEnabled(True)
            set_role(self.test_result, "error")
            self.test_result.setText(describe_error(e))

        run_in_background(lambda: self._fetch_remote_locks(False), done, failed)

    # ----- تبويب الأقفال -----

    def _build_locks_tab(self) -> QWidget:
        self.lock_list = QListWidget()
        self.lock_list.itemChanged.connect(self._lock_renamed)
        self.default_button = QPushButton("⭐ تعيين كافتراضي")
        self.default_button.clicked.connect(self._make_default)
        self.sync_button = QPushButton("مزامنة من الحساب")
        self.sync_button.clicked.connect(self.sync_locks)
        self.include_all = QCheckBox("إظهار كل الأجهزة (ليس الأقفال فقط)")
        self.sync_result = QLabel("")
        self.sync_result.setWordWrap(True)
        hint = QLabel("انقر نقراً مزدوجاً على القفل لإعادة تسميته.")
        set_role(hint, "muted")

        row = QHBoxLayout()
        row.addWidget(self.sync_button)
        row.addWidget(self.default_button)
        layout = QVBoxLayout()
        layout.addWidget(self.lock_list)
        layout.addWidget(hint)
        layout.addLayout(row)
        layout.addWidget(self.include_all)
        layout.addWidget(self.sync_result)
        page = QWidget()
        page.setLayout(layout)
        self._fill_lock_list()
        return page

    def _fill_lock_list(self) -> None:
        self.lock_list.blockSignals(True)
        self.lock_list.clear()
        default_id = self._default_id
        if self._locks and not any(l.device_id == default_id for l in self._locks):
            default_id = self._default_id = self._locks[0].device_id
        for lock in self._locks:
            item = QListWidgetItem(lock.name)
            item.setData(DEVICE_ROLE, lock.device_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            if lock.device_id == default_id:
                item.setToolTip("القفل الافتراضي")
                item.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogYesButton))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.lock_list.addItem(item)
        self.lock_list.blockSignals(False)

    def _lock_by_id(self, device_id: str) -> LockInfo | None:
        return next((l for l in self._locks if l.device_id == device_id), None)

    def _lock_renamed(self, item: QListWidgetItem) -> None:
        lock = self._lock_by_id(item.data(DEVICE_ROLE))
        name = item.text().strip()
        if lock and name:
            lock.name = name

    def _make_default(self) -> None:
        item = self.lock_list.currentItem()
        if item:
            self._default_id = item.data(DEVICE_ROLE)
            self._fill_lock_list()

    def sync_locks(self) -> None:
        if not self._form_complete():
            set_role(self.sync_result, "error")
            self.sync_result.setText("أكمل بيانات تبويب «الربط بتويا» أولاً.")
            return
        self.sync_button.setEnabled(False)
        set_role(self.sync_result, "muted")
        self.sync_result.setText("جارٍ المزامنة...")
        include_all = self.include_all.isChecked()

        def done(remote: list[RemoteLock]):
            self.sync_button.setEnabled(True)
            self._locks = merge_locks(self._locks, remote)
            self._fill_lock_list()
            set_role(self.sync_result, "success")
            self.sync_result.setText(f"✓ تمت المزامنة: {len(remote)} قفل. اضغط «حفظ» للاعتماد.")

        def failed(e: Exception):
            self.sync_button.setEnabled(True)
            set_role(self.sync_result, "error")
            self.sync_result.setText(describe_error(e))

        run_in_background(lambda: self._fetch_remote_locks(include_all), done, failed)

    # ----- تبويب عام -----

    def _build_general_tab(self) -> QWidget:
        ui = self.ctx.settings.ui
        self.start_with_windows = QCheckBox("تشغيل البرنامج مع ويندوز")
        self.start_with_windows.setChecked(ui.start_with_windows)
        self.minimize_to_tray = QCheckBox("التصغير إلى شريط المهام عند الإغلاق")
        self.minimize_to_tray.setChecked(ui.minimize_to_tray)
        self.reverify = QCheckBox("طلب تحقق ويندوز من جديد بعد قفل الجهاز (Win+L)")
        self.reverify.setChecked(ui.reverify_on_session_lock)
        self.pin_every_open = QCheckBox("طلب الـ PIN عند كل فتح للقفل (افتراضياً: مرة يومياً)")
        self.pin_every_open.setChecked(ui.pin_every_open)
        self.hotkey =QKeySequenceEdit(QKeySequence(ui.hotkey))
        self.hotkey.setMaximumSequenceLength(1)
        self.hotkey.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        change_pin = QPushButton("تغيير الـ PIN")
        change_pin.clicked.connect(lambda: PinDialog(self.ctx, PinMode.CHANGE, self).exec())

        form = QFormLayout()
        form.addRow(self.start_with_windows)
        form.addRow(self.minimize_to_tray)
        form.addRow(self.reverify)
        form.addRow(self.pin_every_open)
        form.addRow("اختصار فتح القفل الافتراضي:", self.hotkey)
        form.addRow(change_pin)

        export_button = QPushButton("تصدير الإعدادات...")
        export_button.clicked.connect(self.export_settings)
        import_button = QPushButton("استيراد الإعدادات...")
        import_button.clicked.connect(self.import_settings)
        backup_row = QHBoxLayout()
        backup_row.addWidget(export_button)
        backup_row.addWidget(import_button)
        backup_hint = QLabel("لنقل الإعدادات إلى جهاز آخر بملف مشفّر بكلمة مرور.")
        set_role(backup_hint, "muted")
        form.addRow(backup_row)
        form.addRow(backup_hint)
        page = QWidget()
        page.setLayout(form)
        return page

    # ----- التصدير والاستيراد -----

    def _ask_password(self, confirm: bool) -> str | None:
        password, ok = QInputDialog.getText(
            self, "كلمة مرور الملف", "كلمة المرور (6 أحرف على الأقل):", QLineEdit.EchoMode.Password
        )
        if not ok or not password:
            return None
        if confirm:
            again, ok = QInputDialog.getText(self, "كلمة مرور الملف", "أعد كتابة كلمة المرور:", QLineEdit.EchoMode.Password)
            if not ok:
                return None
            if again != password:
                QMessageBox.warning(self, "تصدير", "كلمتا المرور غير متطابقتين.")
                return None
        return password

    def export_settings(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "تصدير الإعدادات", "LockControl-backup.lcb", "LockControl Backup (*.lcb)"
        )
        if not path:
            return
        password = self._ask_password(confirm=True)
        if password is None:
            return
        try:
            export_backup(Path(path), password, self.ctx.settings, self.ctx.secrets)
        except (BackupError, OSError) as e:
            QMessageBox.warning(self, "تصدير", str(e))
            return
        QMessageBox.information(self, "تصدير", "تم حفظ النسخة الاحتياطية.")

    def import_settings(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "استيراد الإعدادات", "", "LockControl Backup (*.lcb)")
        if not path:
            return
        password = self._ask_password(confirm=False)
        if password is None:
            return
        try:
            self.ctx.replace_settings(import_backup(Path(path), password, self.ctx.secrets))
        except BackupError as e:
            QMessageBox.warning(self, "استيراد", str(e))
            return
        QMessageBox.information(self, "استيراد", "تم استيراد الإعدادات.")
        # الإعدادات المستوردة محفوظة؛ نغلق دون حفظ النموذج القديم فوقها.
        self.accept()

    # ----- الحفظ -----

    def save(self) -> None:
        secret = self.secret.text().strip() or None
        self.ctx.update_tuya(
            self.region.currentData(), self.client_id.text().strip(), self.uid.text().strip(), secret
        )
        ui = self.ctx.settings.ui
        ui.start_with_windows = self.start_with_windows.isChecked()
        ui.minimize_to_tray = self.minimize_to_tray.isChecked()
        ui.reverify_on_session_lock = self.reverify.isChecked()
        ui.pin_every_open = self.pin_every_open.isChecked()
        sequence = self.hotkey.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        ui.hotkey = sequence or ui.hotkey
        self.ctx.set_locks(self._locks, self._default_id)
        self.accept()
