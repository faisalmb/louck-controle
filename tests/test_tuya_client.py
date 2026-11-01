import json

import httpx
import pytest
import respx

from lockcontrol.core import signing
from lockcontrol.core.errors import TuyaError, TuyaNetworkError
from lockcontrol.core.token_manager import MemoryTokenStore
from lockcontrol.core.tuya_client import TuyaClient, TuyaCredentials

BASE = "https://openapi.tuyaeu.com"
CREDS = TuyaCredentials("cid", "secret", "eu")
NOW = 1_700_000_000.0


def ok(result):
    return httpx.Response(200, json={"success": True, "result": result, "t": 1})


def fail(code, msg="err"):
    return httpx.Response(200, json={"success": False, "code": code, "msg": msg, "t": 1})


def token_result(n=1):
    return {"access_token": f"at{n}", "refresh_token": f"rt{n}", "expire_time": 7200, "uid": "u"}


@pytest.fixture
def client():
    c = TuyaClient(CREDS, MemoryTokenStore(), clock=lambda: NOW, nonce_factory=lambda: "nonce")
    yield c
    c.close()


@respx.mock
def test_token_request_is_signed_without_access_token(client):
    route = respx.get(f"{BASE}/v1.0/token", params={"grant_type": "1"}).mock(return_value=ok(token_result()))
    client.tokens.access_token()

    req = route.calls.last.request
    t = str(int(NOW * 1000))
    expected = signing.sign(
        "cid", "secret", t, "nonce", signing.string_to_sign("GET", "/v1.0/token?grant_type=1")
    )
    assert req.headers["sign"] == expected
    assert req.headers["t"] == t
    assert req.headers["client_id"] == "cid"
    assert "access_token" not in req.headers
    assert client.tokens.current().expires_at == NOW + 7200


@respx.mock
def test_business_request_signs_body_and_token(client):
    respx.get(f"{BASE}/v1.0/token").mock(return_value=ok(token_result()))
    route = respx.post(f"{BASE}/v1.0/devices/d1/commands").mock(return_value=ok(True))

    assert client.post("/v1.0/devices/d1/commands", {"commands": [{"code": "x", "value": 1}]}) is True

    req = route.calls.last.request
    body = signing.encode_body({"commands": [{"code": "x", "value": 1}]})
    assert req.content == body
    assert req.headers["access_token"] == "at1"
    expected = signing.sign(
        "cid", "secret", req.headers["t"], "nonce",
        signing.string_to_sign("POST", "/v1.0/devices/d1/commands", body), "at1",
    )
    assert req.headers["sign"] == expected


@respx.mock
def test_retries_once_on_token_error(client):
    respx.get(f"{BASE}/v1.0/token").mock(return_value=ok(token_result(1)))
    respx.get(f"{BASE}/v1.0/token/rt1").mock(return_value=ok(token_result(2)))
    route = respx.get(f"{BASE}/v1.0/users/u/devices").mock(side_effect=[fail(1010), ok([])])

    assert client.get("/v1.0/users/u/devices") == []
    assert [c.request.headers["access_token"] for c in route.calls] == ["at1", "at2"]


@respx.mock
def test_other_errors_raise(client):
    respx.get(f"{BASE}/v1.0/token").mock(return_value=ok(token_result()))
    respx.get(f"{BASE}/v1.0/devices/d1").mock(return_value=fail(1106, "permission deny"))

    with pytest.raises(TuyaError) as e:
        client.get("/v1.0/devices/d1")
    assert e.value.code == 1106


@respx.mock
def test_network_errors_are_wrapped(client):
    respx.get(f"{BASE}/v1.0/token").mock(side_effect=httpx.ConnectError("offline"))
    with pytest.raises(TuyaNetworkError):
        client.tokens.access_token()


@respx.mock
def test_non_json_response_is_network_error(client):
    respx.get(f"{BASE}/v1.0/token").mock(return_value=httpx.Response(502, text="Bad Gateway"))
    with pytest.raises(TuyaNetworkError):
        client.tokens.access_token()


def test_unknown_region():
    with pytest.raises(ValueError):
        TuyaCredentials("a", "b", "xx").base_url
