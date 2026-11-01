"""يجمع خدمات البرنامج في مكان واحد تتشاركه نوافذ الواجهة."""

from typing import Callable

from .core.lock_service import LockService
from .core.security import SecurityManager, Verifier
from .core.storage import HistoryEntry, KeyringTokenStore, LockInfo, SecretStore, Settings, SettingsStore
from .core.token_manager import TokenStore
from .core.tuya_client import TuyaClient, TuyaCredentials

ServiceFactory = Callable[[TuyaCredentials, TokenStore], LockService]


def default_service_factory(creds: TuyaCredentials, tokens: TokenStore) -> LockService:
    return LockService(TuyaClient(creds, tokens))


class NotConfigured(Exception):
    pass


class AppContext:
    def __init__(
        self,
        store: SettingsStore,
        secrets: SecretStore,
        verifier: Verifier,
        service_factory: ServiceFactory = default_service_factory,
    ):
        self.store = store
        self.secrets = secrets
        self.settings: Settings = store.load()
        self.security = SecurityManager(secrets, verifier)
        self.token_store = KeyringTokenStore(secrets)
        self._factory = service_factory
        self._service: LockService | None = None

    # ----- الإعدادات -----

    def client_secret(self) -> str:
        return self.secrets.get("client_secret") or ""

    def credentials(self) -> TuyaCredentials:
        t = self.settings.tuya
        return TuyaCredentials(t.client_id, self.client_secret(), t.region)

    def is_configured(self) -> bool:
        t = self.settings.tuya
        return bool(t.client_id and self.client_secret())

    def save(self) -> None:
        self.store.save(self.settings)

    def update_tuya(self, region: str, client_id: str, uid: str, secret: str | None) -> None:
        """secret = None يعني الإبقاء على المحفوظ."""
        t = self.settings.tuya
        creds_changed = (region, client_id) != (t.region, t.client_id) or (
            secret is not None and secret != self.client_secret()
        )
        t.region, t.client_id, t.uid = region, client_id, uid
        if secret is not None:
            self.secrets.set("client_secret", secret)
        if creds_changed:
            # توكن الحساب القديم لا يصلح للجديد.
            self.token_store.clear()
            self._service = None
        self.save()

    def replace_settings(self, settings: Settings) -> None:
        """بعد الاستيراد: الأسرار كُتبت مسبقاً، والتوكن حُذف."""
        self.settings = settings
        self._service = None
        self.save()

    def set_locks(self, locks: list[LockInfo], default_lock_id: str) -> None:
        self.settings.locks = locks
        self.settings.default_lock_id = default_lock_id
        self.save()

    def remember_open_method(self, device_id: str, method: str) -> None:
        lock = self.settings.find_lock(device_id)
        if lock and lock.open_method != method:
            lock.open_method = method
            self.save()

    # ----- الخدمات -----

    def lock_service(self) -> LockService:
        if not self.is_configured():
            raise NotConfigured()
        if self._service is None:
            self._service = self._factory(self.credentials(), self.token_store)
        return self._service

    def record(self, lock: LockInfo, ok: bool, message: str = "") -> None:
        self.store.append_history(HistoryEntry.now(lock.device_id, lock.name, ok, message))
