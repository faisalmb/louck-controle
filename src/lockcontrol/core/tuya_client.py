"""عميل Tuya OpenAPI: يوقّع الطلبات ويدير التوكن ويحوّل الأخطاء إلى استثناءات."""

import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import httpx

from . import signing
from .errors import TOKEN_ERROR_CODES, TuyaError, TuyaNetworkError
from .token_manager import Token, TokenManager, TokenStore

REGIONS: dict[str, str] = {
    "cn": "https://openapi.tuyacn.com",
    "us": "https://openapi.tuyaus.com",
    "us-e": "https://openapi-ueaz.tuyaus.com",
    "eu": "https://openapi.tuyaeu.com",
    "eu-w": "https://openapi-weaz.tuyaeu.com",
    "in": "https://openapi.tuyain.com",
}

REGION_NAMES: dict[str, str] = {
    "cn": "الصين",
    "us": "غرب أمريكا",
    "us-e": "شرق أمريكا",
    "eu": "وسط أوروبا (الشرق الأوسط غالباً)",
    "eu-w": "غرب أوروبا",
    "in": "الهند",
}

DEFAULT_TIMEOUT = 10.0


@dataclass(frozen=True)
class TuyaCredentials:
    client_id: str
    client_secret: str
    region: str = "eu"

    @property
    def base_url(self) -> str:
        try:
            return REGIONS[self.region]
        except KeyError:
            raise ValueError(f"منطقة غير معروفة: {self.region}") from None


class TuyaClient:
    def __init__(
        self,
        credentials: TuyaCredentials,
        token_store: TokenStore,
        *,
        http: httpx.Client | None = None,
        clock: Callable[[], float] = time.time,
        nonce_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
    ):
        self._creds = credentials
        self._http = http or httpx.Client(timeout=DEFAULT_TIMEOUT)
        self._clock = clock
        self._nonce = nonce_factory
        self.tokens = TokenManager(self._fetch_token, token_store, clock)

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, body: Any | None = None) -> Any:
        return self.request("POST", path, body=body)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Any | None = None,
    ) -> Any:
        """يعيد قيمة `result` من الاستجابة."""
        token = self.tokens.access_token()
        try:
            return self._send(method, path, params, body, token)
        except TuyaError as e:
            if e.code not in TOKEN_ERROR_CODES:
                raise
            token = self.tokens.force_refresh(token)
            return self._send(method, path, params, body, token)

    def close(self) -> None:
        self._http.close()

    def _fetch_token(self, refresh_token: str | None) -> Token:
        if refresh_token:
            result = self._send("GET", f"/v1.0/token/{refresh_token}", None, None, "")
        else:
            result = self._send("GET", "/v1.0/token", {"grant_type": 1}, None, "")
        return Token(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            expires_at=self._clock() + int(result["expire_time"]),
            uid=result.get("uid", ""),
        )

    def _send(
        self,
        method: str,
        path: str,
        params: Mapping[str, Any] | None,
        body: Any | None,
        access_token: str,
    ) -> Any:
        url = signing.canonical_url(path, params)
        content = signing.encode_body(body)
        t = str(int(self._clock() * 1000))
        nonce = self._nonce()
        sign = signing.sign(
            self._creds.client_id,
            self._creds.client_secret,
            t,
            nonce,
            signing.string_to_sign(method, url, content),
            access_token,
        )
        headers = {
            "client_id": self._creds.client_id,
            "sign": sign,
            "sign_method": "HMAC-SHA256",
            "t": t,
            "nonce": nonce,
        }
        if access_token:
            headers["access_token"] = access_token
        if content:
            headers["Content-Type"] = "application/json"

        try:
            response = self._http.request(
                method, self._creds.base_url + url, content=content or None, headers=headers
            )
            data = response.json()
        except (httpx.HTTPError, ValueError) as e:
            raise TuyaNetworkError(str(e)) from e

        if not data.get("success"):
            raise TuyaError(int(data.get("code", -1)), str(data.get("msg", "")))
        return data.get("result")
