import hashlib
import hmac

from lockcontrol.core import signing


def test_canonical_url_sorts_params():
    assert signing.canonical_url("/v1.0/x", {"b": 2, "a": "1"}) == "/v1.0/x?a=1&b=2"
    assert signing.canonical_url("/v1.0/x") == "/v1.0/x"


def test_string_to_sign_for_get_without_body():
    s = signing.string_to_sign("get", "/v1.0/token?grant_type=1")
    assert s == f"GET\n{signing.EMPTY_BODY_SHA256}\n\n/v1.0/token?grant_type=1"


def test_string_to_sign_hashes_exact_body_bytes():
    body = signing.encode_body({"ticket_id": "abc", "open": True})
    assert body == b'{"ticket_id":"abc","open":true}'
    s = signing.string_to_sign("POST", "/v1.0/x", body)
    assert s.split("\n")[1] == hashlib.sha256(body).hexdigest()


def test_sign_matches_hmac_and_is_uppercase():
    to_sign = "GET\nhash\n\n/v1.0/token?grant_type=1"
    expected = hmac.new(
        b"secret", f"cid{'tok'}1700000000000nonce{to_sign}".encode(), hashlib.sha256
    ).hexdigest().upper()
    assert signing.sign("cid", "secret", "1700000000000", "nonce", to_sign, "tok") == expected


def test_sign_without_access_token_differs():
    a = signing.sign("cid", "secret", "1", "n", "x")
    b = signing.sign("cid", "secret", "1", "n", "x", "tok")
    assert a != b and a == a.upper()
