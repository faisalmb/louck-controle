"""يولّد packaging/lockcontrol.ico من الأيقونة المرسومة في البرنامج."""

import sys
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication

from lockcontrol.ui.icons import lock_icon

app = QGuiApplication(sys.argv)
out = Path(__file__).with_name("lockcontrol.ico")
if not lock_icon().pixmap(QSize(256, 256)).save(str(out), "ICO"):
    sys.exit("تعذر حفظ الأيقونة")
print(out)
