"""تحويل الأخطاء إلى رسائل عربية مفهومة."""

from ..app_context import NotConfigured
from ..core.errors import TuyaError, TuyaNetworkError
from ..core.lock_service import LockOpenError

TUYA_MESSAGES: dict[int, str] = {
    1001: "Client Secret غير صحيح.",
    1004: "توقيع الطلب غير صحيح: تحقق من Client Secret.",
    1005: "Client ID غير صحيح.",
    1010: "انتهت صلاحية الجلسة مع تويا. أعد المحاولة.",
    1011: "انتهت صلاحية الجلسة مع تويا. أعد المحاولة.",
    1013: "ساعة الكمبيوتر غير مضبوطة. فعّل «ضبط الوقت تلقائياً» في إعدادات ويندوز.",
    1106: "لا توجد صلاحية: تأكد من ربط حساب التطبيق بالمشروع (Link App Account) "
    "ومن أن مركز البيانات صحيح.",
    1108: "هذا القفل لا يدعم الفتح عن بُعد عبر Cloud API.",
    1109: "بيانات الطلب غير صالحة: تحقق من معرّف الحساب (UID).",
    2001: "القفل غير متصل بالإنترنت.",
    2009: "Client ID غير صحيح.",
}

# مقاطع من نص رسالة تويا؛ أدق من الرموز التي تختلف بين الخدمات.
TEXT_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (
        ("subscription", "expired", "trial"),
        "انتهى اشتراك خدمة IoT Core في منصة تويا. جدّده من Tuya IoT Platform ← Cloud ← Cloud Services.",
    ),
    (
        ("not authorized to call this api", "api is not authorized", "no permissions"),
        "المشروع غير مخوّل لهذه الخدمة: فعّل «Smart Lock Open Service» و «IoT Core» من Cloud Services.",
    ),
    (("frequency", "too many", "rate limit"), "طلبات كثيرة خلال وقت قصير. انتظر قليلاً ثم أعد المحاولة."),
    (("offline",), "القفل غير متصل بالإنترنت."),
    (("clientid", "client_id"), "Client ID غير صحيح."),
]

OPEN_HINT = "تأكد من تفعيل «الفتح عن بُعد» للقفل في تطبيق Smart Life."


def describe_tuya_error(error: TuyaError) -> str | None:
    text = error.msg.lower()
    for needles, message in TEXT_PATTERNS:
        if any(n in text for n in needles):
            return message
    return TUYA_MESSAGES.get(error.code)


def describe_error(error: Exception) -> str:
    from_open = isinstance(error, LockOpenError)
    if from_open:
        error = error.primary
    if isinstance(error, NotConfigured):
        return "أكمل إعدادات الربط بتويا أولاً."
    if isinstance(error, TuyaNetworkError):
        return "تعذر الاتصال بخادم تويا. تحقق من الإنترنت."
    if isinstance(error, TuyaError):
        known = describe_tuya_error(error)
        if known:
            return known
        generic = f"رفض خادم تويا الطلب ({error.code}): {error.msg}"
        return f"{generic}\n{OPEN_HINT}" if from_open else generic
    return f"خطأ غير متوقع: {error}"
