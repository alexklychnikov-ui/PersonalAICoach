"""URL helpers ported from Freelance Auto-Responder (kwork / fl.ru / yandex uslugi)."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_KWORK_HOST = re.compile(r"(?:https?://)?(?:www\.)?kwork\.ru", re.I)
_KWORK_PROJECT_PATH = re.compile(
    r"kwork\.ru/projects/(\d+)(?:/view)?(?:[/?#]|$)",
    re.I,
)
_KWORK_NEW_OFFER = re.compile(
    r"kwork\.ru/new_offer\?(?:[^#]*&)?project=(\d+)",
    re.I,
)
_KWORK_PROJECT_QUERY = re.compile(r"[?&]project=(\d+)", re.I)

_FL_PROJECT_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?fl\.ru/projects/(\d+)(?:/[^/\s\"']*)?",
    re.I,
)

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)
_YANDEX_ORDER_URL_RE = re.compile(
    r"(?:https?://)?(?:[a-z0-9-]+\.)?uslugi\.yandex\.ru/order/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.I,
)

FLRU_ORIGIN = "https://www.fl.ru"
YANDEX_USLUGI_ORIGIN = "https://uslugi.yandex.ru"
KWORK_ORIGIN = "https://kwork.ru"

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def extract_kwork_project_id(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    for pattern in (_KWORK_PROJECT_PATH, _KWORK_NEW_OFFER):
        match = pattern.search(raw)
        if match:
            return match.group(1)
    if _KWORK_HOST.search(raw):
        match = _KWORK_PROJECT_QUERY.search(raw)
        if match:
            return match.group(1)
    return None


def kwork_project_view_url(project_id: str) -> str:
    return f"{KWORK_ORIGIN}/projects/{project_id}/view"


def extract_flru_project_id(text: str) -> str | None:
    if not text:
        return None
    m = _FL_PROJECT_URL_RE.search(text.strip())
    return m.group(1) if m else None


def flru_project_url(project_id: str) -> str:
    return f"{FLRU_ORIGIN}/projects/{str(project_id).strip()}/"


def ensure_flru_for_all(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return f"{FLRU_ORIGIN}/projects/?kind=1&for_all=1"
    parsed = urlparse(raw)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["for_all"] = "1"
    return urlunparse(parsed._replace(query=urlencode(query)))


def extract_yandex_order_id(text: str) -> str | None:
    if not text:
        return None
    m = _YANDEX_ORDER_URL_RE.search(text)
    if m:
        return m.group(1).lower()
    m = _UUID_RE.search(text.strip())
    if m and "uslugi.yandex" in text.lower():
        return m.group(0).lower()
    stripped = text.strip()
    if _UUID_RE.fullmatch(stripped):
        return stripped.lower()
    return None


def yandex_order_url(order_id: str) -> str:
    return f"{YANDEX_USLUGI_ORIGIN}/order/{order_id}"
