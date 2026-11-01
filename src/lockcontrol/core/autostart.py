"""تشغيل البرنامج مع النظام، للمستخدم الحالي فقط وبدون صلاحيات مسؤول.

- ويندوز: قيمة في مفتاح Run بسجل المستخدم.
- ماك: ملف LaunchAgent في ~/Library/LaunchAgents.
- لينكس: ملف .desktop في ~/.config/autostart.
"""

import os
import plistlib
import shlex
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "LockControl"
MAC_LABEL = "com.lockcontrol.app"
LINUX_FILE = "lockcontrol.desktop"


def launch_args() -> list[str]:
    """الأمر الذي يشغّل البرنامج مصغّراً في شريط المهام."""
    if getattr(sys, "frozen", False):  # نسخة PyInstaller
        return [sys.executable, "--minimized"]
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    python = pythonw if pythonw.exists() else exe
    return [str(python), "-m", "lockcontrol", "--minimized"]


def launch_command() -> str:
    args = launch_args()
    if sys.platform == "win32":
        return " ".join(f'"{a}"' if " " in a or a == args[0] else a for a in args)
    return shlex.join(args)


# ----- ويندوز -----


def _win_is_enabled(value_name: str) -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, value_name)
            return True
    except FileNotFoundError:
        return False


def _win_set_enabled(enabled: bool, value_name: str, command: str | None) -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, command or launch_command())
        else:
            try:
                winreg.DeleteValue(key, value_name)
            except FileNotFoundError:
                pass


# ----- ماك ولينكس: ملفات -----


def mac_agent_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"


def linux_desktop_path(home: Path | None = None) -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") if home is None else None
    return Path(base or (home or Path.home()) / ".config") / "autostart" / LINUX_FILE


def write_mac_agent(path: Path, args: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        plistlib.dump({"Label": MAC_LABEL, "ProgramArguments": args, "RunAtLoad": True}, f)


def write_linux_desktop(path: Path, args: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=LockControl\n"
        f"Exec={shlex.join(args)}\n"
        "X-GNOME-Autostart-enabled=true\n",
        encoding="utf-8",
    )


def _file_path() -> Path:
    return mac_agent_path() if sys.platform == "darwin" else linux_desktop_path()


# ----- الواجهة العامة -----


def is_enabled(value_name: str = VALUE_NAME) -> bool:
    if sys.platform == "win32":
        return _win_is_enabled(value_name)
    return _file_path().exists()


def set_enabled(enabled: bool, value_name: str = VALUE_NAME, command: str | None = None) -> None:
    if sys.platform == "win32":
        _win_set_enabled(enabled, value_name, command)
        return
    path = _file_path()
    if not enabled:
        path.unlink(missing_ok=True)
    elif sys.platform == "darwin":
        write_mac_agent(path, launch_args())
    else:
        write_linux_desktop(path, launch_args())
