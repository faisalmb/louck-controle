import pytest

from lockcontrol.app_context import NotConfigured
from lockcontrol.core.errors import TuyaError, TuyaNetworkError
from lockcontrol.core.lock_service import LockOpenError
from lockcontrol.ui.messages import OPEN_HINT, describe_error


@pytest.mark.parametrize(
    "error, expected",
    [
        (TuyaError(1013, "request time is invalid"), "ساعة الكمبيوتر"),
        (TuyaError(1004, "sign invalid"), "Client Secret"),
        (TuyaError(2009, "clientId is invalid"), "Client ID غير صحيح"),
        (TuyaError(1106, "permission deny"), "Link App Account"),
        (TuyaError(28841002, "No permissions. Your subscription to cloud development plan has expired."), "انتهى اشتراك"),
        (TuyaError(28841105, "No permissions. This project is not authorized to call this API."), "Smart Lock Open Service"),
        (TuyaError(40000309, "request frequency exceeds limit"), "طلبات كثيرة"),
        (TuyaError(9999, "device is offline"), "غير متصل"),
        (TuyaNetworkError("timeout"), "الإنترنت"),
        (NotConfigured(), "أكمل إعدادات"),
    ],
)
def test_known_errors(error, expected):
    assert expected in describe_error(error)


def test_open_error_prefers_real_cause_over_unsupported_path():
    e = LockOpenError({"door_operate": TuyaError(1108, "uri path invalid"), "open_door": TuyaError(2001, "x")})
    assert describe_error(e) == "القفل غير متصل بالإنترنت."


def test_open_error_all_unsupported():
    e = LockOpenError({"door_operate": TuyaError(1108, "uri path invalid"), "open_door": TuyaError(1108, "uri path invalid")})
    assert "لا يدعم الفتح عن بُعد" in describe_error(e)


def test_unknown_open_error_adds_hint():
    text = describe_error(LockOpenError({"door_operate": TuyaError(12345, "strange")}))
    assert "12345" in text and OPEN_HINT in text


def test_unknown_non_open_error_has_no_hint():
    text = describe_error(TuyaError(12345, "strange"))
    assert "12345" in text and OPEN_HINT not in text
