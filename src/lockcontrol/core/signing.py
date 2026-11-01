"""توقيع طلبات Tuya OpenAPI (HMAC-SHA256، الإصدار الجديد للتوقيع).

stringToSign = METHOD \\n SHA256(body) \\n headers \\n url
sign = HMAC-SHA256(client_id + access_token + t + nonce + stringToSign, secret).upper()
"""

import hashlib
import hmac
import json
from typing import Any, Mapping

EMPTY_BODY_SHA256 = hashlib.sha256(b"").hexdigest()


def encode_body(body: Any | None) -> bytes:
    """الجسم كما يُرسل بالضبط، لأن الهاش يُحسب على البايتات نفسها."""
    if body is None:
        return b""
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_url(path: str, params: Mapping[str, Any] | None = None) -> str:
    """المسار مع المعاملات مرتبة أبجدياً حسب المفتاح."""
    if not params:
        return path
    query = "&".join(f"{key}={params[key]}" for key in sorted(params))
    return f"{path}?{query}"


def string_to_sign(method: str, url: str, body: bytes = b"") -> str:
    content_hash = hashlib.sha256(body).hexdigest()
    # لا نستخدم Signature-Headers، فسطر الترويسات فارغ.
    return f"{method.upper()}\n{content_hash}\n\n{url}"


def sign(
    client_id: str,
    secret: str,
    t: str,
    nonce: str,
    to_sign: str,
    access_token: str = "",
) -> str:
    message = f"{client_id}{access_token}{t}{nonce}{to_sign}"
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest().upper()
