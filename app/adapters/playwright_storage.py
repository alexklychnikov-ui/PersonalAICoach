"""Load cookies from Playwright storage_state JSON (same format as Freelance Auto-Responder)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


def load_httpx_cookies(storage_state_path: str) -> httpx.Cookies | None:
    path = Path(storage_state_path).expanduser()
    if not path.is_file():
        logger.warning("storage_state not found: %s", path)
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("storage_state read failed %s: %s", path, exc)
        return None
    cookies = httpx.Cookies()
    for item in data.get("cookies") or []:
        name = item.get("name")
        value = item.get("value")
        if not name or value is None:
            continue
        cookies.set(
            name,
            value,
            domain=item.get("domain") or None,
            path=item.get("path") or "/",
        )
    return cookies
