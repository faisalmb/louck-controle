"""أداة سطر أوامر لاختبار الاتصال بتويا قبل وجود الواجهة.

المتغيرات المطلوبة: TUYA_CLIENT_ID و TUYA_CLIENT_SECRET، واختيارياً TUYA_REGION (الافتراضي eu).
"""

import argparse
import os
import sys
import time

from .core.errors import TuyaError, TuyaNetworkError
from .core.lock_service import LockOpenError, LockService
from .core.token_manager import MemoryTokenStore
from .core.tuya_client import REGIONS, TuyaClient, TuyaCredentials


def _client_from_env() -> TuyaClient:
    client_id = os.environ.get("TUYA_CLIENT_ID")
    secret = os.environ.get("TUYA_CLIENT_SECRET")
    if not client_id or not secret:
        sys.exit("عيّن TUYA_CLIENT_ID و TUYA_CLIENT_SECRET أولاً.")
    region = os.environ.get("TUYA_REGION", "eu")
    return TuyaClient(TuyaCredentials(client_id, secret, region), MemoryTokenStore())


def cmd_token(client: TuyaClient) -> None:
    client.tokens.access_token()
    token = client.tokens.current()
    minutes = int((token.expires_at - time.time()) / 60)
    # لا نطبع التوكن نفسه.
    print(f"تم الاتصال بنجاح. التوكن صالح لمدة {minutes} دقيقة. uid={token.uid}")


def cmd_locks(client: TuyaClient, include_all: bool) -> None:
    uid = os.environ.get("TUYA_UID", "")
    for lock in LockService(client).list_locks(uid, include_all):
        state = "متصل" if lock.online else "غير متصل"
        print(f"{lock.device_id}  {lock.category:9} {state:9} {lock.name}")


def cmd_open(client: TuyaClient, device_id: str) -> None:
    method = LockService(client).open(device_id)
    print(f"تم فتح القفل ({method}).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lockcontrol-cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("token", help="اختبار الاتصال وجلب التوكن")
    sub.add_parser("regions", help="عرض مراكز البيانات")
    locks = sub.add_parser("locks", help="سرد أقفال الحسابات المرتبطة بالمشروع")
    locks.add_argument("--all", action="store_true", help="عرض كل الأجهزة لا الأقفال فقط")
    open_cmd = sub.add_parser("open", help="فتح قفل")
    open_cmd.add_argument("device_id")
    args = parser.parse_args(argv)

    if args.command == "regions":
        for key, url in REGIONS.items():
            print(f"{key:6} {url}")
        return 0

    client = _client_from_env()
    try:
        if args.command == "token":
            cmd_token(client)
        elif args.command == "locks":
            cmd_locks(client, args.all)
        elif args.command == "open":
            cmd_open(client, args.device_id)
    except LockOpenError as e:
        print(f"تعذر فتح القفل: {e.primary}", file=sys.stderr)
        return 1
    except TuyaError as e:
        print(f"رفض خادم تويا الطلب: {e.code} {e.msg}", file=sys.stderr)
        return 1
    except TuyaNetworkError as e:
        print(f"تعذر الاتصال بخادم تويا: {e}", file=sys.stderr)
        return 1
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
