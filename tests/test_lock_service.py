import json

import httpx
import pytest
import respx

from lockcontrol.core.errors import TuyaError
from lockcontrol.core.lock_service import LockOpenError, LockService, RemoteLock, merge_locks
from lockcontrol.core.storage import LockInfo
from lockcontrol.core.token_manager import MemoryTokenStore, Token
from lockcontrol.core.tuya_client import TuyaClient, TuyaCredentials

BASE = "https://openapi.tuyaeu.com"
NOW = 1_700_000_000.0


def ok(result):
    return httpx.Response(200, json={"success": True, "result": result})


def fail(code, msg="err"):
    return httpx.Response(200, json={"success": False, "code": code, "msg": msg})


@pytest.fixture
def service():
    store = MemoryTokenStore(Token("at", "rt", NOW + 7200, "u"))
    client = TuyaClient(TuyaCredentials("cid", "secret"), store, clock=lambda: NOW)
    yield LockService(client)
    client.close()


DEVICES = [
    {"id": "d1", "name": "الباب", "category": "jtmspro", "online": True, "product_name": "Lock X"},
    {"id": "d2", "name": "", "category": "ms", "online": False, "product_name": "Lock Y"},
    {"id": "d3", "name": "لمبة", "category": "dj", "online": True},
]


ASSOCIATED = f"{BASE}/v1.0/iot-01/associated-users/devices"


@respx.mock
def test_list_locks_filters_categories(service):
    respx.get(ASSOCIATED).mock(
        return_value=ok({"devices": DEVICES, "has_more": False, "last_row_key": "", "total": 3})
    )
    locks = service.list_locks()
    assert [l.device_id for l in locks] == ["d1", "d2"]
    assert locks[1].name == "Lock Y" and locks[1].online is False
    assert len(service.list_locks(include_all=True)) == 3


@respx.mock
def test_list_locks_follows_pages(service):
    route = respx.get(ASSOCIATED).mock(
        side_effect=[
            ok({"devices": DEVICES[:1], "has_more": True, "last_row_key": "K1"}),
            ok({"devices": DEVICES[1:2], "has_more": False, "last_row_key": ""}),
        ]
    )
    assert [l.device_id for l in service.list_locks()] == ["d1", "d2"]
    assert route.calls[1].request.url.params["last_row_key"] == "K1"


@respx.mock
def test_list_locks_falls_back_to_uid_endpoint(service):
    respx.get(ASSOCIATED).mock(return_value=fail(1106, "permission deny"))
    respx.get(f"{BASE}/v1.0/users/app-uid/devices").mock(return_value=ok(DEVICES))
    assert len(service.list_locks("app-uid")) == 2
    with pytest.raises(TuyaError):
        service.list_locks()  # بدون UID لا يوجد بديل


@respx.mock
def test_lock_names_are_trimmed(service):
    respx.get(ASSOCIATED).mock(
        return_value=ok({"devices": [{"id": "v1", "name": "الإدارة المالية ", "category": "videolock"}]})
    )
    assert service.list_locks()[0].name == "الإدارة المالية"


@respx.mock
def test_status_reads_battery(service):
    respx.get(f"{BASE}/v1.0/devices/d1").mock(
        return_value=ok({"online": True, "status": [{"code": "residual_electricity", "value": 76}]})
    )
    s = service.status("d1")
    assert s.online and s.battery == 76


@respx.mock
def test_open_with_door_operate(service):
    respx.post(f"{BASE}/v1.0/devices/d1/door-lock/password-ticket").mock(
        return_value=ok({"ticket_id": "T1", "expire_time": 300})
    )
    operate = respx.post(f"{BASE}/v1.0/smart-lock/devices/d1/password-free/door-operate").mock(
        return_value=ok(True)
    )
    assert service.open("d1") == "door_operate"
    assert json.loads(operate.calls.last.request.content) == {"ticket_id": "T1", "open": True}


@respx.mock
def test_open_falls_back_to_second_method(service):
    respx.post(f"{BASE}/v1.0/devices/d1/door-lock/password-ticket").mock(return_value=ok({"ticket_id": "T"}))
    respx.post(f"{BASE}/v1.0/smart-lock/devices/d1/password-free/door-operate").mock(
        return_value=fail(1108, "uri path invalid")
    )
    open_door = respx.post(f"{BASE}/v1.0/devices/d1/door-lock/password-free/open-door").mock(
        return_value=ok(True)
    )
    assert service.open("d1") == "open_door"
    assert json.loads(open_door.calls.last.request.content) == {"ticket_id": "T"}


@respx.mock
def test_preferred_method_tried_first(service):
    respx.post(f"{BASE}/v1.0/devices/d1/door-lock/password-ticket").mock(return_value=ok({"ticket_id": "T"}))
    operate = respx.post(f"{BASE}/v1.0/smart-lock/devices/d1/password-free/door-operate").mock(
        return_value=ok(True)
    )
    respx.post(f"{BASE}/v1.0/devices/d1/door-lock/password-free/open-door").mock(return_value=ok(True))
    assert service.open("d1", preferred_method="open_door") == "open_door"
    assert not operate.called


@respx.mock
def test_all_methods_fail_reports_meaningful_error(service):
    respx.post(f"{BASE}/v1.0/devices/d1/door-lock/password-ticket").mock(
        return_value=fail(2001, "device is offline")
    )
    with pytest.raises(LockOpenError) as e:
        service.open("d1")
    assert isinstance(e.value.primary, TuyaError) and e.value.primary.code == 2001
    assert set(e.value.errors) == {"door_operate", "open_door"}


@respx.mock
def test_false_result_is_failure(service):
    respx.post(f"{BASE}/v1.0/devices/d1/door-lock/password-ticket").mock(return_value=ok({"ticket_id": "T"}))
    respx.post(f"{BASE}/v1.0/smart-lock/devices/d1/password-free/door-operate").mock(return_value=ok(False))
    respx.post(f"{BASE}/v1.0/devices/d1/door-lock/password-free/open-door").mock(
        return_value=fail(1108, "uri path invalid")
    )
    with pytest.raises(LockOpenError) as e:
        service.open("d1")
    assert e.value.primary.code == -1


def test_merge_keeps_local_names_and_methods():
    existing = [LockInfo("d1", "اسمي", "ms", "open_door"), LockInfo("gone", "قديم")]
    remote = [RemoteLock("d1", "Remote", "jtmspro", True), RemoteLock("d2", "جديد", "ms", True)]
    merged = merge_locks(existing, remote)
    assert merged == [LockInfo("d1", "اسمي", "jtmspro", "open_door"), LockInfo("d2", "جديد", "ms")]
