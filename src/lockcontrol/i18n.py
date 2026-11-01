"""ترجمة الواجهة. النص العربي في الكود هو المفتاح، والإنجليزية في en.py.

    t("تم فتح {name}", name=lock.name)
"""

LANGUAGES = {"ar": "العربية", "en": "English"}  # كل لغة باسمها الأصلي

_language = "ar"


def set_language(language: str) -> None:
    global _language
    _language = language if language in LANGUAGES else "ar"


def language() -> str:
    return _language


def is_rtl() -> bool:
    return _language == "ar"


def t(text: str, **values) -> str:
    if _language == "en":
        from .en import EN

        text = EN.get(text, text)
    return text.format(**values) if values else text
