"""نقطة دخول PyInstaller (يحتاج ملفاً لا وحدة -m)."""

import sys

from lockcontrol.__main__ import main

sys.exit(main())
