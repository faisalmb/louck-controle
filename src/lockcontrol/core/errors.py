"""أخطاء طبقة الاتصال بتويا."""


class TuyaError(Exception):
    """خطأ أعاده خادم تويا (success = false)."""

    def __init__(self, code: int, msg: str):
        super().__init__(f"Tuya error {code}: {msg}")
        self.code = code
        self.msg = msg


class TuyaNetworkError(Exception):
    """تعذر الوصول إلى خادم تويا (لا إنترنت، مهلة، استجابة غير صالحة)."""


# رموز تعني أن التوكن غير صالح أو منتهٍ: نجدده ونعيد المحاولة مرة واحدة.
TOKEN_ERROR_CODES = frozenset({1010, 1011, 1012})
