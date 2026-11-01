"""سجل عمليات الفتح."""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..app_context import AppContext
from ..i18n import t


class HistoryDialog(QDialog):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(t("سجل العمليات"))
        self.resize(620, 420)

        history = list(reversed(ctx.store.load_history()))  # الأحدث أولاً
        self.table = QTableWidget(len(history), 4)
        self.table.setHorizontalHeaderLabels([t("الوقت"), t("القفل"), t("النتيجة"), t("التفاصيل")])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for row, e in enumerate(history):
            values = [e.time.replace("T", "  "), e.lock_name, t("✓ نجح") if e.ok else t("✗ فشل"), e.message]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()

        close = QPushButton(t("إغلاق"))
        close.clicked.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(close)
