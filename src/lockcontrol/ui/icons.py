"""أيقونة القفل مرسومة برمجياً حتى لا يحتاج البرنامج ملفات صور."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from .style import ACCENT


def lock_icon(color: str = ACCENT) -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = size / 32
        # الحلقة العلوية
        pen = QPen(QColor(color), 3.2 * s)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(9 * s, 3 * s, 14 * s, 16 * s), 0, 180 * 16)
        p.drawLine(int(9 * s), int(11 * s), int(9 * s), int(15 * s))
        p.drawLine(int(23 * s), int(11 * s), int(23 * s), int(15 * s))
        # الجسم
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawRoundedRect(QRectF(5 * s, 14 * s, 22 * s, 16 * s), 3 * s, 3 * s)
        # ثقب المفتاح
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(14 * s, 18.5 * s, 4 * s, 4 * s))
        p.drawRect(QRectF(15.2 * s, 21 * s, 1.6 * s, 4.5 * s))
        p.end()
        icon.addPixmap(pixmap)
    return icon
