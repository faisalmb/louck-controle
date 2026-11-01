# LockControl

برنامج ويندوز لفتح أقفال تويا الذكية عبر Tuya Cloud.

## التشغيل للتطوير

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m lockcontrol
```

## قبل أول استخدام (منصة تويا)

1. أنشئ مشروع Cloud على [Tuya IoT Platform](https://platform.tuya.com/cloud) بمركز البيانات نفسه الذي يستخدمه حساب التطبيق.
2. فعّل خدمتي **IoT Core** و **Smart Lock Open Service**.
3. اربط حساب Smart Life من: Devices ← Link App Account، وانسخ الـ UID.
4. فعّل «الفتح عن بُعد» للقفل من تطبيق Smart Life.

## الاختبارات

```bash
.venv/Scripts/python -m pytest -q
```

## أداة سطر الأوامر (لاختبار الاتصال)

```bash
TUYA_CLIENT_ID=... TUYA_CLIENT_SECRET=... TUYA_REGION=eu .venv/Scripts/lockcontrol-cli token
TUYA_UID=... .venv/Scripts/lockcontrol-cli locks
```

## البناء

```bash
powershell -ExecutionPolicy Bypass -File build.ps1
```

النتيجة: `dist/LockControl/LockControl.exe`، والمثبّت `dist/LockControl-Setup-<version>.exe` إذا كان Inno Setup مثبّتاً.

## أين تُحفظ البيانات

| البيانات | المكان |
|---|---|
| الإعدادات والأقفال والسجل | `%APPDATA%\LockControl\` (JSON مع نسخة `.bak`) |
| Client Secret، التوكن، بصمة الـ PIN، حالة التحقق | Windows Credential Manager (الخدمة `LockControl`) |
