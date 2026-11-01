"""إدارة توكن تويا: جلبه أول مرة، وتجديده قبل انتهائه، وحفظه في مخزن دائم."""

import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from .errors import TuyaError

REFRESH_MARGIN_SECONDS = 300


@dataclass(frozen=True)
class Token:
    access_token: str
    refresh_token: str
    expires_at: float
    uid: str = ""

    def expires_within(self, seconds: float, now: float) -> bool:
        return self.expires_at - now <= seconds


class TokenStore(Protocol):
    def load(self) -> Token | None: ...
    def save(self, token: Token) -> None: ...
    def clear(self) -> None: ...


class MemoryTokenStore:
    def __init__(self, token: Token | None = None):
        self._token = token

    def load(self) -> Token | None:
        return self._token

    def save(self, token: Token) -> None:
        self._token = token

    def clear(self) -> None:
        self._token = None


# تستقبل refresh_token (أو None لطلب توكن جديد) وتعيد Token.
FetchToken = Callable[[str | None], Token]


class TokenManager:
    def __init__(self, fetch: FetchToken, store: TokenStore, clock: Callable[[], float] = time.time):
        self._fetch = fetch
        self._store = store
        self._clock = clock
        self._lock = threading.Lock()
        self._current: Token | None = None

    def access_token(self) -> str:
        with self._lock:
            token = self._current or self._store.load()
            if token is None:
                token = self._obtain(None)
            elif token.expires_within(REFRESH_MARGIN_SECONDS, self._clock()):
                token = self._renew(token)
            self._current = token
            return token.access_token

    def force_refresh(self, rejected_access_token: str) -> str:
        """يُستدعى عندما يرفض الخادم توكناً. إذا جدّده خيط آخر في الأثناء نستخدم الجديد."""
        with self._lock:
            token = self._current or self._store.load()
            if token is not None and token.access_token != rejected_access_token:
                return token.access_token
            token = self._renew(token) if token else self._obtain(None)
            self._current = token
            return token.access_token

    def current(self) -> Token | None:
        with self._lock:
            return self._current or self._store.load()

    def clear(self) -> None:
        with self._lock:
            self._current = None
            self._store.clear()

    def _renew(self, token: Token) -> Token:
        try:
            return self._obtain(token.refresh_token)
        except TuyaError:
            # refresh_token نفسه منتهٍ أو مرفوض: نطلب توكناً جديداً من الصفر.
            return self._obtain(None)

    def _obtain(self, refresh_token: str | None) -> Token:
        token = self._fetch(refresh_token)
        self._store.save(token)
        return token
