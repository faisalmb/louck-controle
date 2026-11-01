; مثبّت LockControl — يُبنى بـ build.ps1 بعد PyInstaller
#define AppName "LockControl"
#define AppVersion "0.1.0"

[Setup]
AppId={{6E1B7C52-4F0B-4F0E-9B8B-3C1D2E7A9F10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=LockControl
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=LockControl-Setup-{#AppVersion}
SetupIconFile=..\packaging\lockcontrol.ico
UninstallDisplayIcon={app}\LockControl.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\LockControl\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\LockControl.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\LockControl.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LockControl.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; إزالة التشغيل مع ويندوز إن كان مفعّلاً
Filename: "reg.exe"; Parameters: "delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v LockControl /f"; Flags: runhidden; RunOnceId: "RemoveAutostart"
