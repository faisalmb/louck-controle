# Builds the Windows app (dist\LockControl + portable zip), then the installer if Inno Setup is present.
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1
# (ASCII only: Windows PowerShell 5.1 misreads UTF-8 scripts without a BOM.)
$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

& $py packaging\build.py
if ($LASTEXITCODE -ne 0) { exit 1 }

$version = (& $py packaging\build.py --version).Trim()

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    & $iscc "/DAppVersion=$version" installer\lockcontrol.iss
    if ($LASTEXITCODE -ne 0) { exit 1 }
} else {
    Write-Host "Inno Setup not installed: the app is ready in dist\LockControl (no installer)."
}
