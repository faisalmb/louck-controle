"""تشغيل البرنامج مع ويندوز عبر مفتاح Run في سجل المستخدم الحالي (لا يحتاج صلاحيات مسؤول)."""

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "LockControl"


def launch_command() -> str:
    """الأمر الذي يشغّل البرنامج مصغّراً في شريط المهام."""
    if getattr(sys, "frozen", False):  # نسخة PyInstaller
        return f'"{sys.executable}" --minimized'
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    return f'"{pythonw if pythonw.exists() else exe}" -m lockcontrol --minimized'


def is_enabled(value_name: str = VALUE_NAME) -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, value_name)
            return True
    except FileNotFoundError:
        return False


def set_enabled(enabled: bool, value_name: str = VALUE_NAME, command: str | None = None) -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, command or launch_command())
        else:
            try:
                winreg.DeleteValue(key, value_name)
            except FileNotFoundError:
                pass
