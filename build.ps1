# Builds a distributable app in dist\LockControl, then the installer if Inno Setup is present.
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1
# (ASCII only: Windows PowerShell 5.1 misreads UTF-8 scripts without a BOM.)
$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"

& $py packaging\make_icon.py
if ($LASTEXITCODE -ne 0) { exit 1 }

& $py -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name LockControl `
    --icon packaging\lockcontrol.ico `
    --paths src `
    --collect-submodules winrt `
    --hidden-import keyring.backends.Windows `
    --exclude-module pytest `
    packaging\run_lockcontrol.py
if ($LASTEXITCODE -ne 0) { exit 1 }

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    & $iscc installer\lockcontrol.iss
} else {
    Write-Host "Inno Setup not installed: the app is ready in dist\LockControl (no installer)."
}
