"""Interactive Telethon login → StringSession for Telegram market.

1) Create app at https://my.telegram.org → api_id / api_hash
2) Run:
     python scripts/telegram_login.py
   or with env already set:
     python scripts/telegram_login.py --list

Writes secrets/telegram.session.txt (StringSession) and prints .env lines.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "secrets" / "telegram.session.txt"


async def _run(api_id: int, api_hash: str, out: Path, list_dialogs: bool) -> None:
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()
    me = await client.get_me()
    session = client.session.save()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(session, encoding="utf-8")
    print(f"OK: logged in as {me.username or me.id}")
    print(f"Wrote StringSession → {out}")
    print()
    print("Добавь в .env:")
    print(f"TELEGRAM_API_ID={api_id}")
    print(f"TELEGRAM_API_HASH={api_hash}")
    print(f"TELEGRAM_SESSION_PATH={out.as_posix()}")
    print("# или скопируй содержимое файла в TELEGRAM_SESSION=...")
    print()
    if list_dialogs:
        print("Диалоги (каналы/группы), которые видит аккаунт:")
        async for d in client.iter_dialogs():
            if not (d.is_channel or d.is_group):
                continue
            uname = getattr(d.entity, "username", None)
            label = f"@{uname}" if uname else d.name
            print(f"  {label:40} id={d.id}")
    await client.disconnect()


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Telethon login for market search")
    parser.add_argument("--api-id", type=int, default=int(os.getenv("TELEGRAM_API_ID") or 0))
    parser.add_argument("--api-hash", default=os.getenv("TELEGRAM_API_HASH") or "")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--list",
        action="store_true",
        help="После логина вывести каналы/группы с id",
    )
    args = parser.parse_args()
    if not args.api_id or not args.api_hash:
        print(
            "Нужны TELEGRAM_API_ID и TELEGRAM_API_HASH "
            "(https://my.telegram.org → API development tools)",
            file=sys.stderr,
        )
        print(
            "Пример: python scripts/telegram_login.py --api-id 12345 --api-hash abcdef",
            file=sys.stderr,
        )
        return 2
    asyncio.run(_run(args.api_id, args.api_hash, args.out, args.list))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
