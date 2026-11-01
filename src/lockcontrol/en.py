"""الترجمة الإنجليزية. المفتاح هو النص العربي كما في الكود حرفياً (يتحقق منه tests/test_i18n.py)."""

EN: dict[str, str] = {
    # ----- عام -----
    "التحكم بالأقفال": "Lock Control",
    "البرنامج يعمل بالفعل في شريط المهام.": "The app is already running in the system tray.",
    "إلغاء": "Cancel",
    "موافق": "OK",
    "حفظ": "Save",
    "إغلاق": "Close",
    "خروج": "Quit",
    "ويندوز": "Windows",
    "ماك": "macOS",
    "لينكس": "Linux",
    # ----- النافذة الرئيسية -----
    "⚙ الإعدادات": "⚙ Settings",
    "السجل": "History",
    "فتح": "Unlock",
    "أكمل إعدادات الربط بتويا من ⚙ الإعدادات.": "Finish the Tuya connection setup in ⚙ Settings.",
    "لا توجد أقفال. زامنها من ⚙ الإعدادات ← الأقفال.": "No locks yet. Sync them from ⚙ Settings → Locks.",
    "جارٍ قراءة الحالة...": "Reading status...",
    "● متصل": "● Online",
    "○ غير متصل": "○ Offline",
    "البطارية {battery}%": "Battery {battery}%",
    "البطارية: {state}": "Battery: {state}",
    "عالية": "high",
    "متوسطة": "medium",
    "منخفضة ⚠": "low ⚠",
    "فارغة ⚠": "empty ⚠",
    "جارٍ فتح {name}...": "Unlocking {name}...",
    "✓ تم فتح {name}": "✓ Unlocked {name}",
    # ----- شريط المهام -----
    "🔓 فتح {name}": "🔓 Unlock {name}",
    "فتح قفل آخر": "Unlock another lock",
    "إظهار النافذة": "Show window",
    "الاختصار العام": "Global hotkey",
    "التشغيل مع {os}": "Start with {os}",
    # ----- السجل -----
    "سجل العمليات": "Unlock history",
    "الوقت": "Time",
    "القفل": "Lock",
    "النتيجة": "Result",
    "التفاصيل": "Details",
    "✓ نجح": "✓ Success",
    "✗ فشل": "✗ Failed",
    # ----- التحقق والـ PIN -----
    "تأكيد هويتك لفتح برنامج التحكم بالأقفال": "Confirm your identity to open Lock Control",
    "التحقق من الهوية": "Identity verification",
    "للمتابعة تحقق من هويتك عبر {auth}.\nيُطلب هذا مرة واحدة يومياً.": (
        "To continue, verify your identity with {auth}.\nThis is asked once a day."
    ),
    "تحقق الآن": "Verify now",
    "بانتظار {auth}...": "Waiting for {auth}...",
    "أُلغي التحقق.": "Verification was canceled.",
    "فشل التحقق.": "Verification failed.",
    "التحقق عبر {auth} غير متاح على هذا الجهاز.": "{auth} verification is not available on this device.",
    "تعذر التحقق: {e}": "Could not verify: {e}",
    "أدخل الـ PIN": "Enter PIN",
    "تعيين PIN للبرنامج": "Set an app PIN",
    "تغيير الـ PIN": "Change PIN",
    "إعادة تعيين الـ PIN": "Reset PIN",
    "الـ PIN:": "PIN:",
    "الـ PIN الحالي:": "Current PIN:",
    "الـ PIN الجديد:": "New PIN:",
    "تأكيد الـ PIN:": "Confirm PIN:",
    "من {PIN_MIN} إلى {PIN_MAX} أرقام.": "{PIN_MIN} to {PIN_MAX} digits.",
    "نسيت الـ PIN؟": "Forgot your PIN?",
    "الـ PIN يجب أن يكون من {PIN_MIN} إلى {PIN_MAX} أرقام.": "The PIN must be {PIN_MIN} to {PIN_MAX} digits.",
    "الـ PIN يجب أن يكون من {PIN_MIN} إلى {PIN_MAX} أرقام": "The PIN must be {PIN_MIN} to {PIN_MAX} digits",
    "الرمزان غير متطابقين.": "The PINs don't match.",
    "الـ PIN الحالي غير صحيح.": "The current PIN is incorrect.",
    "رمز خاطئ. المحاولات المتبقية قبل الإيقاف: {remaining_attempts}": (
        "Wrong PIN. Attempts left before lockout: {remaining_attempts}"
    ),
    "لم يُعيَّن PIN بعد.": "No PIN has been set yet.",
    "محاولات خاطئة كثيرة. انتظر {_locked_seconds} ثانية.": "Too many wrong attempts. Wait {_locked_seconds} seconds.",
    "سيُطلب منك التحقق عبر {auth} بعد إدخال الرمز الجديد.": "You'll be asked to verify with {auth} after entering the new PIN.",
    "تحقق وحفظ": "Verify and save",
    "أدخل رمزين متطابقين من {PIN_MIN} إلى {PIN_MAX} أرقام.": "Enter two matching PINs of {PIN_MIN} to {PIN_MAX} digits.",
    "لم يكتمل التحقق، لم يتغير الـ PIN.": "Verification wasn't completed; the PIN was not changed.",
    # ----- الإعدادات -----
    "الإعدادات": "Settings",
    "الربط بتويا": "Tuya connection",
    "الأقفال": "Locks",
    "عام": "General",
    "مركز البيانات:": "Data center:",
    "اختياري": "optional",
    "معرّف الحساب (UID):": "Account ID (UID):",
    "محفوظ — اتركه فارغاً للإبقاء عليه": "Saved — leave empty to keep it",
    "اختبار الاتصال": "Test connection",
    "اللغة / Language:": "Language:",
    "يُطبَّق تغيير اللغة بعد إعادة تشغيل البرنامج. إعادة التشغيل الآن؟": (
        "The new language applies after restarting the app. Restart now?"
    ),
    "البيانات من موقع <a href=\"https://platform.tuya.com/cloud\">Tuya IoT Platform</a>:<br>"
    "• Client ID و Client Secret: صفحة المشروع ← Overview<br>"
    "• معرّف الحساب (اختياري): Devices ← Link App Account": (
        "Get these from the <a href=\"https://platform.tuya.com/cloud\">Tuya IoT Platform</a>:<br>"
        "• Client ID and Client Secret: your project → Overview<br>"
        "• Account ID (optional): Devices → Link App Account"
    ),
    "أدخل Client ID و Client Secret.": "Enter the Client ID and Client Secret.",
    "جارٍ الاتصال...": "Connecting...",
    "✓ تم الاتصال. عدد الأقفال في الحساب: {count}": "✓ Connected. Locks in the account: {count}",
    "⭐ تعيين كافتراضي": "⭐ Set as default",
    "مزامنة من الحساب": "Sync from account",
    "إظهار كل الأجهزة (ليس الأقفال فقط)": "Show all devices (not only locks)",
    "انقر نقراً مزدوجاً على القفل لإعادة تسميته.": "Double-click a lock to rename it.",
    "القفل الافتراضي": "Default lock",
    "أكمل بيانات تبويب «الربط بتويا» أولاً.": "Fill in the \"Tuya connection\" tab first.",
    "جارٍ المزامنة...": "Syncing...",
    "✓ تمت المزامنة: {count} قفل. اضغط «حفظ» للاعتماد.": "✓ Synced {count} lock(s). Click \"Save\" to apply.",
    "تشغيل البرنامج مع {os}": "Start the app with {os}",
    "التصغير إلى شريط المهام عند الإغلاق": "Minimize to the tray when closed",
    "طلب تحقق ويندوز من جديد بعد قفل الجهاز (Win+L)": "Ask for Windows verification again after locking the PC (Win+L)",
    "طلب الـ PIN عند كل فتح للقفل (افتراضياً: مرة يومياً)": "Ask for the PIN on every unlock (default: once a day)",
    "اختصار فتح القفل الافتراضي:": "Hotkey to unlock the default lock:",
    "تصدير الإعدادات...": "Export settings...",
    "استيراد الإعدادات...": "Import settings...",
    "لنقل الإعدادات إلى جهاز آخر بملف مشفّر بكلمة مرور.": "Move your settings to another computer with a password-protected file.",
    "كلمة مرور الملف": "File password",
    "كلمة المرور (6 أحرف على الأقل):": "Password (at least 6 characters):",
    "أعد كتابة كلمة المرور:": "Re-enter the password:",
    "كلمتا المرور غير متطابقتين.": "The passwords don't match.",
    "تصدير الإعدادات": "Export settings",
    "تصدير": "Export",
    "تم حفظ النسخة الاحتياطية.": "Backup saved.",
    "استيراد الإعدادات": "Import settings",
    "استيراد": "Import",
    "تم استيراد الإعدادات.": "Settings imported.",
    # ----- مراكز البيانات -----
    "الصين": "China",
    "غرب أمريكا": "Western America",
    "شرق أمريكا": "Eastern America",
    "وسط أوروبا (الشرق الأوسط غالباً)": "Central Europe (usually the Middle East)",
    "غرب أوروبا": "Western Europe",
    "الهند": "India",
    "منطقة غير معروفة: {region}": "Unknown region: {region}",
    # ----- الاختصار العام -----
    "اختصار فارغ": "Empty hotkey",
    "الاختصار يحتاج Ctrl أو Alt أو Shift أو Win": "The hotkey needs Ctrl, Alt, Shift or Win",
    "الاختصار يحتاج مفتاح تعديل مثل Ctrl أو Alt": "The hotkey needs a modifier such as Ctrl or Alt",
    "استخدم حرفاً أو رقماً أو مفتاح F": "Use a letter, a digit or an F key",
    "الاختصار مستخدم من برنامج آخر": "The hotkey is already used by another app",
    "تعذر تفعيل الاختصار على هذا النظام: {e}": "Could not enable the hotkey on this system: {e}",
    # ----- النسخ الاحتياطي -----
    "كلمة مرور الملف يجب أن تكون 6 أحرف على الأقل.": "The file password must be at least 6 characters.",
    "الملف ليس نسخة احتياطية لهذا البرنامج.": "This file is not a Lock Control backup.",
    "كلمة المرور غير صحيحة أو الملف تالف.": "Wrong password, or the file is damaged.",
    "تعذر قراءة الملف: {e}": "Could not read the file: {e}",
    # ----- رسائل الأخطاء -----
    "رفض القفل أمر الفتح": "The lock rejected the unlock command",
    "Client Secret غير صحيح.": "The Client Secret is incorrect.",
    "توقيع الطلب غير صحيح: تحقق من Client Secret.": "Invalid request signature: check the Client Secret.",
    "Client ID غير صحيح.": "The Client ID is incorrect.",
    "انتهت صلاحية الجلسة مع تويا. أعد المحاولة.": "The Tuya session expired. Please try again.",
    "ساعة الكمبيوتر غير مضبوطة. فعّل «ضبط الوقت تلقائياً» في إعدادات النظام.": (
        "Your computer's clock is wrong. Turn on automatic time in your system settings."
    ),
    "لا توجد صلاحية: تأكد من ربط حساب التطبيق بالمشروع (Link App Account) ومن أن مركز البيانات صحيح.": (
        "No permission: make sure the app account is linked to the project (Link App Account) "
        "and the data center is correct."
    ),
    "هذا القفل لا يدعم الفتح عن بُعد عبر Cloud API.": "This lock doesn't support remote unlock through the Cloud API.",
    "بيانات الطلب غير صالحة: تحقق من معرّف الحساب (UID).": "Invalid request data: check the account ID (UID).",
    "القفل غير متصل بالإنترنت.": "The lock is offline.",
    "انتهى اشتراك خدمة IoT Core في منصة تويا. جدّده من Tuya IoT Platform ← Cloud ← Cloud Services.": (
        "Your IoT Core subscription on the Tuya platform has expired. "
        "Renew it in Tuya IoT Platform → Cloud → Cloud Services."
    ),
    "المشروع غير مخوّل لهذه الخدمة: فعّل «Smart Lock Open Service» و «IoT Core» من Cloud Services.": (
        "The project isn't authorized for this service: subscribe to \"Smart Lock Open Service\" "
        "and \"IoT Core\" under Cloud Services."
    ),
    "طلبات كثيرة خلال وقت قصير. انتظر قليلاً ثم أعد المحاولة.": "Too many requests. Wait a moment and try again.",
    "تأكد من تفعيل «الفتح عن بُعد» للقفل في تطبيق Smart Life.": "Make sure remote unlock is enabled for the lock in the Smart Life app.",
    "أكمل إعدادات الربط بتويا أولاً.": "Finish the Tuya connection setup first.",
    "تعذر الاتصال بخادم تويا. تحقق من الإنترنت.": "Couldn't reach the Tuya server. Check your internet connection.",
    "رفض خادم تويا الطلب ({code}): {msg}": "The Tuya server rejected the request ({code}): {msg}",
    "خطأ غير متوقع: {error}": "Unexpected error: {error}",
}
