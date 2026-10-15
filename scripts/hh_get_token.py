"""
Получение токенов hh.ru для Personal AI Coach.

Доки:
  https://api.hh.ru/openapi/redoc#section/Avtorizaciya
  https://dev.hh.ru/

Для поиска вакансий (наш экран «Рынок») обычно хватает ТОКЕНА ПРИЛОЖЕНИЯ.

Примеры:
  python scripts/hh_get_token.py app
  python scripts/hh_get_token.py authorize-url
  python scripts/hh_get_token.py user --code CODE_FROM_REDIRECT
  python scripts/hh_get_token.py refresh --refresh-token REFRESH
  python scripts/hh_get_token.py me
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# OAuth token endpoint is on hh.ru (api.hh.ru/oauth/token → 405).
TOKEN_URL = "https://hh.ru/oauth/token"
AUTHORIZE_URL = "https://hh.ru/oauth/authorize"
ME_URL = "https://api.hh.ru/me"


def _creds() -> tuple[str, str, str, str]:
    client_id = os.getenv("HH_CLIENT_ID", "").strip()
    client_secret = os.getenv("HH_CLIENT_SECRET", "").strip()
    redirect = os.getenv("HH_REDIRECT_URI", "https://aicareercoach.alexklyvibe.ru/oauth/hh/callback").strip()
    ua = os.getenv("HH_USER_AGENT", "PersonalAICoach/0.1 (alexandr_klychnikov@mail.ru)").strip()
    if not client_id or not client_secret:
        print("Заполни HH_CLIENT_ID и HH_CLIENT_SECRET в .env (из https://dev.hh.ru)", file=sys.stderr)
        sys.exit(1)
    return client_id, client_secret, redirect, ua


def get_app_token() -> dict:
    client_id, client_secret, _, ua = _creds()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"User-Agent": ua},
        timeout=30,
    )
    print(f"status={resp.status_code}")
    data = resp.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if resp.status_code < 300 and data.get("access_token"):
        print("\n→ Впиши в .env:\nHH_ACCESS_TOKEN=" + data["access_token"])
    return data


def authorize_url() -> str:
    client_id, _, redirect, _ = _creds()
    url = (
        f"{AUTHORIZE_URL}?"
        + urlencode(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect,
            }
        )
    )
    print(url)
    print("\n1) Redirect URI в приложении на https://dev.hh.ru должен совпадать:")
    print(f"   {redirect}")
    print("2) Открой URL в браузере, залогинься, разреши доступ.")
    print("3) Из адресной строки после редиректа скопируй ?code=...")
    print("4) python scripts/hh_get_token.py user --code <CODE>")
    return url


def exchange_user_code(code: str) -> dict:
    client_id, client_secret, redirect, ua = _creds()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect,
        },
        headers={"User-Agent": ua},
        timeout=30,
    )
    print(f"status={resp.status_code}")
    data = resp.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if resp.status_code < 300 and data.get("access_token"):
        print("\n→ Впиши в .env:")
        print("HH_ACCESS_TOKEN=" + data["access_token"])
        if data.get("refresh_token"):
            print("HH_REFRESH_TOKEN=" + data["refresh_token"])
    return data


def refresh(refresh_token: str) -> dict:
    client_id, client_secret, _, ua = _creds()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"User-Agent": ua},
        timeout=30,
    )
    print(f"status={resp.status_code}")
    data = resp.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if resp.status_code < 300 and data.get("access_token"):
        print("\n→ Обнови в .env HH_ACCESS_TOKEN=" + data["access_token"])
        if data.get("refresh_token"):
            print("HH_REFRESH_TOKEN=" + data["refresh_token"])
    return data


def me() -> dict:
    token = os.getenv("HH_ACCESS_TOKEN", "").strip()
    ua = os.getenv("HH_USER_AGENT", "PersonalAICoach/0.1").strip()
    if not token:
        print("HH_ACCESS_TOKEN пуст", file=sys.stderr)
        sys.exit(1)
    resp = httpx.get(
        ME_URL,
        headers={"Authorization": f"Bearer {token}", "User-Agent": ua},
        timeout=30,
    )
    print(f"status={resp.status_code}")
    print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="hh.ru OAuth helper")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("app", help="Токен приложения (client_credentials) — для поиска вакансий")
    sub.add_parser("authorize-url", help="URL для авторизации пользователя")
    p_user = sub.add_parser("user", help="Обмен code → user token")
    p_user.add_argument("--code", required=True)
    p_ref = sub.add_parser("refresh", help="Обновить user token")
    p_ref.add_argument("--refresh-token", required=True)
    sub.add_parser("me", help="Проверить HH_ACCESS_TOKEN через /me")
    args = parser.parse_args()

    if args.cmd == "app":
        get_app_token()
    elif args.cmd == "authorize-url":
        authorize_url()
    elif args.cmd == "user":
        exchange_user_code(args.code)
    elif args.cmd == "refresh":
        refresh(args.refresh_token)
    elif args.cmd == "me":
        me()


if __name__ == "__main__":
    main()
