**English** | [العربية](README.ar.md)

# Tuya Lock for Windows

Unlock your **Tuya / Smart Life** smart locks from your computer with one click, through the **Tuya Cloud API**. Built for Windows, also runs on **macOS** and **Linux**.

[![build](../../actions/workflows/build.yml/badge.svg)](../../actions/workflows/build.yml)

## Download

From the [**Releases**](../../releases/latest) page:

| OS | File |
|---|---|
| Windows | `LockControl-Setup-x.y.z.exe` (installer), or `...-windows-portable.zip` (no install) |
| macOS (Apple Silicon) | `LockControl-x.y.z-macos.dmg` |
| Linux (x86_64) | `LockControl-x.y.z-linux-x86_64.tar.gz` |

> The builds are not code-signed. **Windows:** if SmartScreen warns you, click *More info → Run anyway*. **macOS:** on first launch, right-click the app and choose *Open*.

<p align="center">
  <img src="docs/screenshots/main.png" width="300" alt="Main window">
</p>

> The user interface is in **Arabic** (right-to-left).

## Features

- **Big unlock button** that opens your default lock right away.
- **Multiple locks** with a default lock ⭐, and any other lock one click away.
- **Lock status**: online/offline and battery level or state.
- **Automatic lock sync** from the Smart Life accounts linked to your Tuya project.
- **Tray icon**: double-click unlocks the default lock; the menu unlocks any lock.
- **Global hotkey** (default `Ctrl+Alt+O`) that unlocks even while the app is minimized.
- **Start with the OS**, minimized to the tray.
- **History log** of every unlock with its result.
- **Clear error messages**: lock offline, Tuya subscription expired, wrong system clock, and more.
- **Encrypted export/import** of your settings (password-protected file) to move to another computer.
- Follows the system **dark / light** theme.

## Security

| Layer | When it is asked |
|---|---|
| **OS verification**: Windows Hello (fingerprint, face, Windows PIN) or the account password; Touch ID or the device password on macOS | Once a day, on first use |
| **App PIN** (4–8 digits) | Once a day together with OS verification, or on every unlock if you enable that option |
| **PIN to open Settings** | Always, since settings hold the Client Secret |

- 3 wrong PINs → 1-minute lockout. 5 wrong PINs → today's verification is revoked and OS verification is required again.
- "Forgot PIN?" resets it after OS verification.
- Optional re-verification after locking the computer (`Win+L`, Windows only).
- The PIN is stored only as a salted scrypt hash, never the digits themselves.

## Platform differences

| Feature | Windows | macOS | Linux |
|---|---|---|---|
| Daily OS verification | Windows Hello or account password | Touch ID or device password | Not available, the app PIN alone protects the app |
| Secret storage | Credential Manager | Keychain | Secret Service (GNOME Keyring / KWallet) |
| Global hotkey | ✓ | ✓ after granting *Accessibility* permission | ✓ on X11, usually not on Wayland |
| Re-verify after screen lock | ✓ | — | — |
| Start with the OS | Run registry key | LaunchAgent | `~/.config/autostart` |
| Tray icon | ✓ | ✓ (menu bar) | ✓, on GNOME requires the AppIndicator extension |

## Where data is stored

| Data | Location |
|---|---|
| Settings, locks, default lock, history | Windows: `%APPDATA%\LockControl\` · macOS: `~/Library/Application Support/LockControl/` · Linux: `~/.config/lockcontrol/`. JSON files written atomically with a `.bak` backup |
| Client Secret, Tuya token, PIN hash, daily verification state | The OS secret store (service `LockControl`), protected by your user account |

This repository contains no keys or account data.

## Requirements

- Windows 10/11, macOS 12+ (Apple Silicon), or a recent x86_64 Linux. Linux may need the `libxcb-cursor0` package.
- An account on the [Tuya IoT Platform](https://platform.tuya.com) (the free plan is enough).
- A Tuya lock that supports **remote unlock**, linked to the Smart Life or Tuya Smart app.
- For development: Python 3.12+.

## Tuya Platform setup (one time)

1. Create a **Cloud** project on the [Tuya IoT Platform](https://platform.tuya.com/cloud), choosing the **same data center** as your app account. For the Middle East this is usually *Central Europe*.
2. Under **Cloud Services**, subscribe to **IoT Core** and **Smart Lock Open Service**.
3. Link your app account: **Devices → Link App Account**, then scan the QR code with the Smart Life app.
4. Enable **remote unlock** for the lock in its settings in the Smart Life app.
5. Copy the **Client ID** and **Client Secret** from the project **Overview** page.

> **Renewing the free plan:** the IoT Core trial has an expiry date. Find it under **Cloud → Cloud Services → My Services** and renew it with **Extend Trial Period**. If it expires, the app tells you.

## Install and use

1. Install `LockControl-Setup-x.y.z.exe` (or the macOS/Linux build), or run from source.
2. On first launch: verify with Windows Hello / Touch ID, then choose an app PIN.
3. **Settings → Tuya connection**: pick the data center, enter the Client ID and Client Secret, then click **Test connection**.
4. **Settings → Locks**: click **Sync from account**, pick the default lock ⭐, then **Save**.
5. Click **Unlock** 🔓

<p align="center">
  <img src="docs/screenshots/settings_tuya.png" width="380" alt="Tuya connection">
  <img src="docs/screenshots/settings_locks.png" width="380" alt="Locks">
</p>
<p align="center">
  <img src="docs/screenshots/settings_general.png" width="380" alt="General settings">
  <img src="docs/screenshots/pin.png" width="300" alt="PIN entry">
</p>

## Run from source

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"     # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m lockcontrol
```

Command-line tool to test the connection without the UI:

```bash
set TUYA_CLIENT_ID=...
set TUYA_CLIENT_SECRET=...
set TUYA_REGION=eu
.venv\Scripts\lockcontrol-cli token     # test the connection
.venv\Scripts\lockcontrol-cli locks     # list locks
.venv\Scripts\lockcontrol-cli regions   # list data centers
```

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

The tests cover request signing, token refresh, atomic storage, the security and PIN logic, the lock service (against mocked Tuya responses), the UI (pytest-qt), the global hotkey and screen-lock events, and export/import.

## Building

Each OS is built on itself; a macOS build cannot be made on Windows.

```bash
python -m pip install -e ".[build]"
python packaging/build.py                                  # macOS or Linux
powershell -ExecutionPolicy Bypass -File build.ps1         # Windows, with installer
```

- **Windows**: `dist\LockControl\`, a portable zip, and the installer if [Inno Setup 6](https://jrsoftware.org/isinfo.php) is installed.
- **macOS**: `dist/LockControl.app` and a `.dmg`.
- **Linux**: `dist/LockControl/` and a `.tar.gz`.
- Diagnostics: `LockControl --self-check result.json` checks the secret store and OS verification.

### Automatic releases (GitHub Actions)

[`.github/workflows/build.yml`](.github/workflows/build.yml) runs the tests on all three systems on every push. Pushing a **tag** that starts with `v` also builds all three and publishes them as a Release:

1. Bump the version in `src/lockcontrol/__init__.py` and `pyproject.toml`, then commit.
2. Create the tag, e.g. `v0.2.0`:
   - In GitHub Desktop: *History* → right-click the commit → *Create Tag*.
   - Or from a terminal: `git tag v0.2.0`.
3. Push. The Release with all three builds appears within minutes.

## Project structure

```
src/lockcontrol/
├─ core/                    # logic, no UI
│  ├─ signing.py            # HMAC-SHA256 signing for Tuya OpenAPI requests
│  ├─ token_manager.py      # fetches the token and refreshes it before expiry
│  ├─ tuya_client.py        # client: regions, requests, retry on expired token
│  ├─ lock_service.py       # lock listing, status, remote unlock (two methods with fallback)
│  ├─ storage.py            # atomic JSON + backup + OS secret store
│  ├─ security.py           # daily verification, PIN, attempt limits
│  ├─ verify.py             # picks the OS verifier for the current platform
│  ├─ windows_auth.py       # Windows Hello (WinRT) with Windows password fallback
│  ├─ macos_auth.py         # Touch ID / device password (LocalAuthentication)
│  ├─ autostart.py          # start with the OS (Run key / LaunchAgent / autostart)
│  └─ backup.py             # encrypted export/import (scrypt + Fernet)
├─ ui/                      # PySide6 UI
│  ├─ main_window.py        # unlock button and status
│  ├─ settings_dialog.py    # Tuya connection, locks, general settings
│  ├─ auth.py               # verification and PIN dialogs
│  ├─ controller.py         # tray, hotkey, applying settings
│  ├─ hotkeys.py            # global hotkey per OS (pynput on macOS/Linux)
│  ├─ win_events.py         # RegisterHotKey and screen-lock events (Windows)
│  └─ messages.py           # user-facing error messages (Arabic)
├─ app_context.py           # shared services
├─ cli.py                   # command-line tool
└─ __main__.py              # entry point (--minimized, --self-check)
```

## Tuya APIs used

| Purpose | Endpoint |
|---|---|
| Token | `GET /v1.0/token`, `GET /v1.0/token/{refresh_token}` |
| List devices | `GET /v1.0/iot-01/associated-users/devices` (fallback: `GET /v1.0/users/{uid}/devices` when a UID is set) |
| Status | `GET /v1.0/devices/{device_id}` |
| Unlock | `POST /v1.0/devices/{id}/door-lock/password-ticket`, then `POST /v1.0/smart-lock/devices/{id}/password-free/door-operate` (fallback: `.../door-lock/password-free/open-door`) |

Each unlock uses 2–3 API calls; reading the status uses one.

## Troubleshooting

| Message (shown in Arabic in the app) | Fix |
|---|---|
| No permission (1106) | Make sure the app account is linked (Link App Account) and the data center is correct |
| Project not authorized for this service | Subscribe to IoT Core and Smart Lock Open Service under Cloud Services |
| IoT Core subscription expired | Renew under Cloud Services → My Services → Extend Trial Period |
| Computer clock is wrong | Turn on automatic time in your OS settings |
| Lock is offline | Check the lock's or gateway's connection |
| Lock doesn't support remote unlock | Enable remote unlock in the Smart Life app, or the lock doesn't support it through the cloud |

## License

[MIT](LICENSE). This is an independent project, not affiliated with Tuya.
