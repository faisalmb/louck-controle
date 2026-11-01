"""نقطة تشغيل البرنامج: python -m lockcontrol [--minimized]"""

import sys

from PySide6.QtCore import QLockFile, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from .app_context import AppContext
from .core.storage import SecretStore, SettingsStore
from .core.verify import default_verifier
from .ui.auth import daily_gate
from .ui.controller import AppController
from .ui.style import APP_STYLE


def self_check(path: str) -> int:
    """تشخيص النسخة المحزّمة: يتأكد من وجود المكتبات الحرجة ويكتب النتيجة في ملف."""
    import json

    import keyring

    verifier = default_verifier()
    report = {
        "platform": sys.platform,
        "keyring_backend": type(keyring.get_keyring()).__name__,
        "verifier": type(verifier).__name__,
        "os_auth_supported": verifier.supported,
        "settings_dir": str(SettingsStore().data_dir),
    }
    if sys.platform == "win32":
        from .core.windows_auth import hello_available

        report["hello_available"] = hello_available()
    elif sys.platform == "darwin":
        try:
            import LocalAuthentication  # noqa: F401

            report["local_authentication"] = True
        except ImportError:
            report["local_authentication"] = False
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False)
    return 0


def main() -> int:
    if "--self-check" in sys.argv:
        return self_check(sys.argv[sys.argv.index("--self-check") + 1])
    minimized = "--minimized" in sys.argv
    app = QApplication(sys.argv)
    app.setApplicationName("LockControl")
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    app.setStyleSheet(APP_STYLE)
    app.setQuitOnLastWindowClosed(False)  # يبقى في شريط المهام

    store = SettingsStore()
    store.data_dir.mkdir(parents=True, exist_ok=True)
    instance_lock = QLockFile(str(store.data_dir / "app.lock"))
    if not instance_lock.tryLock(100):
        QMessageBox.information(None, "LockControl", "البرنامج يعمل بالفعل في شريط المهام.")
        return 0

    ctx = AppContext(store, SecretStore(), default_verifier())

    # مع ويندوز يبدأ مصغّراً، والتحقق يُطلب عند أول استخدام.
    if not minimized and not daily_gate(ctx):
        return 0

    controller = AppController(ctx, app)
    if not minimized:
        controller.window.show()
        if not ctx.is_configured():
            # أول تشغيل: التحقق وتعيين الـ PIN تمّا للتو، فلا نطلب الـ PIN مرة أخرى.
            controller.edit_settings()
    elif not ctx.settings.ui.minimize_to_tray:
        controller.window.showMinimized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
