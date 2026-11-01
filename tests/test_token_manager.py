import pytest

from lockcontrol.core.errors import TuyaError
from lockcontrol.core.token_manager import MemoryTokenStore, Token, TokenManager


class FakeFetch:
    def __init__(self, now):
        self.calls: list[str | None] = []
        self.now = now
        self.fail_refresh = False

    def __call__(self, refresh_token):
        self.calls.append(refresh_token)
        if refresh_token and self.fail_refresh:
            raise TuyaError(1011, "refresh token invalid")
        n = len(self.calls)
        return Token(f"access{n}", f"refresh{n}", self.now() + 7200, "uid")


@pytest.fixture
def clock():
    state = {"t": 1000.0}

    def now():
        return state["t"]

    now.state = state
    return now


def test_first_call_fetches_and_saves(clock):
    fetch, store = FakeFetch(clock), MemoryTokenStore()
    tm = TokenManager(fetch, store, clock)
    assert tm.access_token() == "access1"
    assert fetch.calls == [None]
    assert store.load().access_token == "access1"


def test_valid_token_is_reused(clock):
    fetch = FakeFetch(clock)
    tm = TokenManager(fetch, MemoryTokenStore(), clock)
    tm.access_token()
    clock.state["t"] += 3600
    assert tm.access_token() == "access1"
    assert len(fetch.calls) == 1


def test_stored_token_survives_restart(clock):
    store = MemoryTokenStore(Token("saved", "r", clock() + 7200))
    fetch = FakeFetch(clock)
    assert TokenManager(fetch, store, clock).access_token() == "saved"
    assert fetch.calls == []


def test_refreshes_before_expiry(clock):
    fetch = FakeFetch(clock)
    tm = TokenManager(fetch, MemoryTokenStore(), clock)
    tm.access_token()
    clock.state["t"] += 7200 - 200  # داخل هامش الخمس دقائق
    assert tm.access_token() == "access2"
    assert fetch.calls == [None, "refresh1"]


def test_failed_refresh_falls_back_to_new_token(clock):
    fetch = FakeFetch(clock)
    tm = TokenManager(fetch, MemoryTokenStore(), clock)
    tm.access_token()
    fetch.fail_refresh = True
    clock.state["t"] += 7200
    assert tm.access_token() == "access3"
    assert fetch.calls == [None, "refresh1", None]


def test_force_refresh_skips_if_already_renewed(clock):
    fetch = FakeFetch(clock)
    tm = TokenManager(fetch, MemoryTokenStore(), clock)
    tm.access_token()
    assert tm.force_refresh("access1") == "access2"
    # خيط آخر رُفض بالتوكن القديم نفسه: لا داعي لتجديد ثانٍ
    assert tm.force_refresh("access1") == "access2"
    assert len(fetch.calls) == 2


def test_clear_removes_stored_token(clock):
    store = MemoryTokenStore()
    tm = TokenManager(FakeFetch(clock), store, clock)
    tm.access_token()
    tm.clear()
    assert store.load() is None and tm.current() is None
