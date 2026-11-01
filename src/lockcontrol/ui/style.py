"""ألوان البرنامج وأنماطه."""

from PySide6.QtWidgets import QWidget


def set_role(widget: QWidget, role: str) -> None:
    """تغيير نمط العنصر (muted / success / error) وإعادة تطبيقه فوراً."""
    widget.setObjectName(role)
    widget.style().unpolish(widget)
    widget.style().polish(widget)

ACCENT = "#1f8f5f"
ACCENT_HOVER = "#23a56d"
ACCENT_PRESSED = "#187549"
DANGER = "#c0392b"
MUTED = "#6b7280"

APP_STYLE = f"""
QWidget {{ font-family: "Segoe UI"; font-size: 10.5pt; }}
QPushButton {{
    padding: 6px 14px; border-radius: 6px;
    background: palette(button); border: 1px solid palette(mid);
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:flat {{ background: transparent; border: none; color: palette(link); }}
QPushButton#openButton {{
    background: {ACCENT}; color: white; border: none;
    border-radius: 90px; font-size: 20pt; font-weight: 600;
}}
QPushButton#openButton:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#openButton:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#openButton:disabled {{ background: #9ca3af; }}
QLabel#title {{ font-size: 15pt; font-weight: 600; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#success {{ color: {ACCENT}; font-weight: 600; }}
QLabel#error {{ color: {DANGER}; font-weight: 600; }}
"""
