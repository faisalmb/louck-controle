"""عمليات الأقفال فوق TuyaClient: السرد، الحالة، والفتح عن بُعد بدون كلمة مرور."""

from dataclasses import dataclass
from typing import Any, Callable

from ..i18n import t
from .errors import TuyaError
from .storage import LockInfo
from .tuya_client import TuyaClient

# فئات تويا للأقفال وأجهزة التحكم بالأبواب.
LOCK_CATEGORIES = frozenset({"ms", "jtmspro", "jtmsbh", "mk", "gyms", "bxx", "hotelms", "videolock"})

PAGE_SIZE = 50
MAX_PAGES = 20

# رمز «مسار غير موجود»: هذا القفل لا يدعم هذا الأسلوب، فلا يُعرض كسبب الفشل.
_PATH_INVALID = 1108


@dataclass(frozen=True)
class RemoteLock:
    device_id: str
    name: str
    category: str
    online: bool
    product_name: str = ""


@dataclass(frozen=True)
class LockStatus:
    online: bool
    battery: int | None = None  # نسبة مئوية إن توفرت
    battery_state: str = ""  # high / medium / low / poweroff


class LockOpenError(Exception):
    def __init__(self, errors: dict[str, Exception]):
        self.errors = errors
        primary = next(
            (e for e in errors.values() if not (isinstance(e, TuyaError) and e.code == _PATH_INVALID)),
            next(iter(errors.values())),
        )
        self.primary = primary
        super().__init__(str(primary))


class LockService:
    def __init__(self, client: TuyaClient):
        self._client = client
        self._methods: dict[str, Callable[[str], Any]] = {
            "door_operate": self._open_door_operate,
            "open_door": self._open_open_door,
        }

    @property
    def methods(self) -> list[str]:
        return list(self._methods)

    def list_locks(self, uid: str = "", include_all: bool = False) -> list[RemoteLock]:
        """أجهزة كل حسابات التطبيق المرتبطة بالمشروع. واجهة users/{uid}/devices
        مرفوضة (1106) في كثير من المشاريع الحديثة، فهي بديل فقط عند إدخال UID."""
        try:
            devices = self._associated_devices()
        except TuyaError:
            if not uid:
                raise
            devices = self._client.get(f"/v1.0/users/{uid}/devices") or []
        locks = []
        for d in devices:
            category = d.get("category", "")
            if include_all or category in LOCK_CATEGORIES:
                locks.append(
                    RemoteLock(
                        device_id=d["id"],
                        name=(d.get("name") or d.get("product_name") or d["id"]).strip(),
                        category=category,
                        online=bool(d.get("online")),
                        product_name=d.get("product_name", ""),
                    )
                )
        return locks

    def _associated_devices(self) -> list[dict]:
        devices: list[dict] = []
        last_row_key = ""
        for _ in range(MAX_PAGES):
            params = {"size": PAGE_SIZE}
            if last_row_key:
                params["last_row_key"] = last_row_key
            page = self._client.get("/v1.0/iot-01/associated-users/devices", params) or {}
            devices.extend(page.get("devices") or [])
            last_row_key = page.get("last_row_key") or ""
            if not page.get("has_more") or not last_row_key:
                break
        return devices

    def status(self, device_id: str) -> LockStatus:
        info = self._client.get(f"/v1.0/devices/{device_id}") or {}
        values = {s.get("code"): s.get("value") for s in info.get("status", []) if isinstance(s, dict)}
        battery = values.get("residual_electricity", values.get("battery_percentage"))
        return LockStatus(
            online=bool(info.get("online")),
            battery=int(battery) if isinstance(battery, (int, float)) else None,
            battery_state=str(values.get("battery_state", "")),
        )

    def open(self, device_id: str, preferred_method: str = "") -> str:
        """يفتح القفل ويعيد اسم الأسلوب الذي نجح، ليُحفظ ويُجرَّب أولاً في المرة القادمة."""
        order = sorted(self._methods, key=lambda m: m != preferred_method)
        errors: dict[str, Exception] = {}
        for method in order:
            try:
                result = self._methods[method](device_id)
            except TuyaError as e:
                errors[method] = e
                continue
            if result is False:
                errors[method] = TuyaError(-1, t("رفض القفل أمر الفتح"))
                continue
            return method
        raise LockOpenError(errors)

    def _ticket(self, device_id: str) -> str:
        result = self._client.post(f"/v1.0/devices/{device_id}/door-lock/password-ticket")
        return result["ticket_id"]

    def _open_door_operate(self, device_id: str) -> Any:
        ticket = self._ticket(device_id)
        return self._client.post(
            f"/v1.0/smart-lock/devices/{device_id}/password-free/door-operate",
            {"ticket_id": ticket, "open": True},
        )

    def _open_open_door(self, device_id: str) -> Any:
        ticket = self._ticket(device_id)
        return self._client.post(
            f"/v1.0/devices/{device_id}/door-lock/password-free/open-door",
            {"ticket_id": ticket},
        )


def merge_locks(existing: list[LockInfo], remote: list[RemoteLock]) -> list[LockInfo]:
    """مزامنة القائمة المحلية مع الحساب: تبقى الأسماء المعدّلة محلياً وأسلوب الفتح المحفوظ،
    تُضاف الأقفال الجديدة، وتُحذف التي لم تعد في الحساب."""
    local = {l.device_id: l for l in existing}
    merged = []
    for r in remote:
        old = local.get(r.device_id)
        if old:
            merged.append(LockInfo(r.device_id, old.name or r.name, r.category, old.open_method))
        else:
            merged.append(LockInfo(r.device_id, r.name, r.category))
    return merged
