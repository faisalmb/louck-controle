"""يولّد packaging/lockcontrol.ico و lockcontrol.png من الأيقونة المرسومة في البرنامج."""

import sys
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication

from lockcontrol.ui.icons import lock_icon

app = QGuiApplication(sys.argv)
here = Path(__file__).parent
pixmap = lock_icon().pixmap(QSize(256, 256))
for name, fmt in (("lockcontrol.ico", "ICO"), ("lockcontrol.png", "PNG")):
    if not pixmap.save(str(here / name), fmt):
        sys.exit(f"Could not save {name}")
    print(here / name)
