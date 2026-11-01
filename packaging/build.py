"""يبني نسخة قابلة للتوزيع للنظام الحالي (لا يمكن بناء نظام آخر من هذا الجهاز).

    python packaging/build.py

الناتج في dist/:
- ويندوز: LockControl/ و LockControl-<ver>-windows-portable.zip (المثبّت يبنيه build.ps1 أو CI)
- ماك:    LockControl.app و LockControl-<ver>-macos.dmg
- لينكس:  LockControl/ و LockControl-<ver>-linux-x86_64.tar.gz
"""

import platform
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging"
DIST = ROOT / "dist"
NAME = "LockControl"


def version() -> str:
    text = (ROOT / "src" / "lockcontrol" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)


def run(*args: str) -> None:
    print(">", " ".join(args), flush=True)
    subprocess.run(args, check=True, cwd=ROOT)


def pyinstaller_args() -> list[str]:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed", "--onedir",
        "--name", NAME,
        "--paths", str(ROOT / "src"),
        "--collect-submodules", "keyring.backends",
        "--exclude-module", "pytest",
    ]
    if sys.platform == "win32":
        args += ["--icon", str(PACKAGING / "lockcontrol.ico"), "--collect-submodules", "winrt"]
    elif sys.platform == "darwin":
        args += [
            "--icon", str(PACKAGING / "lockcontrol.png"),  # يحوّله PyInstaller إلى icns عبر Pillow
            "--osx-bundle-identifier", "com.lockcontrol.app",
            "--hidden-import", "LocalAuthentication",
            "--collect-submodules", "pynput",
        ]
    else:
        args += ["--icon", str(PACKAGING / "lockcontrol.png"), "--collect-submodules", "pynput"]
    return args + [str(PACKAGING / "run_lockcontrol.py")]


def package(ver: str) -> Path:
    if sys.platform == "win32":
        archive = shutil.make_archive(str(DIST / f"{NAME}-{ver}-windows-portable"), "zip", DIST, NAME)
        return Path(archive)
    if sys.platform == "darwin":
        dmg = DIST / f"{NAME}-{ver}-macos.dmg"
        dmg.unlink(missing_ok=True)
        run("hdiutil", "create", "-volname", NAME, "-srcfolder", str(DIST / f"{NAME}.app"),
            "-ov", "-format", "UDZO", str(dmg))
        return dmg
    # لينكس: نضيف ملف .desktop والأيقونة داخل المجلد
    app_dir = DIST / NAME
    shutil.copy(PACKAGING / "lockcontrol.png", app_dir / "lockcontrol.png")
    shutil.copy(PACKAGING / "lockcontrol.desktop", app_dir / "lockcontrol.desktop")
    archive = DIST / f"{NAME}-{ver}-linux-{platform.machine()}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(app_dir, arcname=NAME)
    return archive


def main() -> int:
    ver = version()
    if "--version" in sys.argv:
        print(ver)
        return 0
    run(sys.executable, str(PACKAGING / "make_icon.py"))
    run(*pyinstaller_args())
    out = package(ver)
    # إنجليزي: طرفيات ويندوز في CI لا تطبع العربية دائماً
    print(f"\nBuilt: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
