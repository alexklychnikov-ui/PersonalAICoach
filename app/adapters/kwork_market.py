"""Kwork read-only — api.kwork.ru POST + HTML wants[] / keyword= search."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlencode

import httpx

from app.adapters.market_urls import BROWSER_UA, kwork_project_view_url
from app.adapters.playwright_storage import load_httpx_cookies
from app.config import Settings
from app.domain.models import MarketItem, MarketSource

logger = logging.getLogger(__name__)


def _extract_json_array(html: str, key: str) -> list[dict[str, Any]]:
    m = re.search(rf'"{re.escape(key)}"\s*:\s*\[', html)
    if not m:
        return []
    start = m.end() - 1
    i = start
    depth = 0
    in_str = False
    esc = False
    end = None
    while i < len(html):
        ch = html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        i += 1
    if end is None:
        return []
    try:
        data = json.loads(html[start:end])
    except json.JSONDecodeError:
        return []
    return [x for x in data if isinstance(x, dict)]


def parse_kwork_listing(html: str) -> list[dict]:
    """HTML/regex fallback used by tests and degraded mode."""
    wants = _extract_json_array(html, "wants")
    if wants:
        return [_want_to_card(w) for w in wants if w.get("id")]

    seen: set[str] = set()
    cards: list[dict] = []
    for m in re.finditer(
        r'href=["\']([^"\']*/projects/(\d+)(?:/view)?[^"\']*)["\']',
        html,
        flags=re.I,
    ):
        href, pid = m.group(1), m.group(2)
        if pid in seen:
            continue
        seen.add(pid)
        window = html[max(0, m.start() - 200) : m.end() + 500]
        title = ""
        for pat in (
            r'class="[^"]*wants-card__header-title[^"]*"[^>]*>\s*<a[^>]*>([^<]+)',
            r'class="[^"]*project-card__title[^"]*"[^>]*>([^<]+)',
            r">([^<]{8,160})</a>",
        ):
            tm = re.search(pat, window, flags=re.I)
            if tm:
                title = re.sub(r"\s+", " ", tm.group(1)).strip()
                if title and "kwork" not in title.lower():
                    break
        url = href if href.startswith("http") else f"https://kwork.ru{href}"
        url = url.split("?")[0]
        cards.append(
            {
                "project_id": pid,
                "url": url if "/view" in url else kwork_project_view_url(pid),
                "title": title or f"Kwork project {pid}",
                "budget_text": None,
                "description": "",
            }
        )
    return cards


def _want_to_card(want: dict[str, Any]) -> dict:
    pid = str(want.get("id"))
    price = (
        want.get("price")
        or want.get("priceLimit")
        or want.get("possible_price_limit")
        or want.get("possiblePriceLimit")
    )
    budget = f"до {price} ₽" if price else None
    title = want.get("title") or want.get("name") or f"Kwork {pid}"
    return {
        "project_id": pid,
        "url": kwork_project_view_url(pid),
        "title": str(title),
        "budget_text": budget,
        "description": str(want.get("description") or "")[:4000],
    }


def parse_kwork_project(html: str, project_id: str | None = None) -> dict:
    pid = project_id or ""
    if not pid:
        m = re.search(r"/projects/(\d+)", html)
        if m:
            pid = m.group(1)
    title = (
        _first(r'class="[^"]*wants-card__header-title[^"]*"[^>]*>\s*<a[^>]*>([^<]+)', html)
        or _first(r'class="project-title"[^>]*>([^<]+)', html)
        or _first(r"<h1[^>]*>([^<]+)", html)
        or _first(r"<title[^>]*>([^<]+)</title>", html)
        or ""
    )
    title = re.sub(r"\s*[|·—-].*$", "", title).strip().replace(" — Kwork", "").strip()
    wants = _extract_json_array(html, "wants")
    for w in wants:
        if str(w.get("id")) == str(pid):
            return {
                "project_id": pid,
                "title": str(w.get("name") or title),
                "description": str(w.get("description") or "")[:8000],
            }
    desc = ""
    for token in (
        "wants-card__description-text",
        "want-card__description-text",
        "project-description",
    ):
        for m in re.finditer(
            rf'class="[^"]*{re.escape(token)}[^"]*"[^>]*>(.*?)</',
            html,
            flags=re.I | re.DOTALL,
        ):
            text = re.sub(r"<[^>]+>", " ", m.group(1))
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) > len(desc):
                desc = text
    return {"project_id": pid, "title": title, "description": desc[:8000]}


def _first(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, flags=re.I | re.DOTALL)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip()


class KworkMarketSource:
    name = "kwork"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _category_ids(self) -> list[str]:
        return [c.strip() for c in self._settings.kwork_category_ids.split(",") if c.strip()] or [
            "11"
        ]

    def _cookies(self) -> httpx.Cookies | None:
        if self._settings.kwork_storage_state:
            return load_httpx_cookies(self._settings.kwork_storage_state)
        return None

    async def _search_api(
        self, client: httpx.AsyncClient, cat: str, limit: int, *, pages: int = 2
    ) -> list[dict]:
        cards: list[dict] = []
        for page in range(1, pages + 1):
            resp = await client.post(
                "https://api.kwork.ru/projects",
                data={"c": cat, "page": page},
                headers={
                    "User-Agent": BROWSER_UA,
                    "Accept": "application/json",
                    "Origin": "https://kwork.ru",
                    "Referer": f"https://kwork.ru/projects?c={cat}",
                },
            )
            if resp.status_code >= 400:
                logger.warning("kwork api HTTP %s", resp.status_code)
                break
            payload = resp.json()
            if not payload.get("success"):
                logger.warning("kwork api error: %s", payload.get("error"))
                break
            rows = payload.get("response") or []
            if not isinstance(rows, list) or not rows:
                break
            for row in rows:
                if not isinstance(row, dict) or not row.get("id"):
                    continue
                cards.append(_want_to_card(row))
                if len(cards) >= limit:
                    return cards
        return cards

    async def _search_html(self, client: httpx.AsyncClient, cat: str) -> list[dict]:
        url = f"https://kwork.ru/projects?c={cat}"
        raw = (self._settings.kwork_listing_url or "").strip()
        if raw and "|" not in raw and "c=" in raw:
            url = raw.split("|")[0].strip()
        resp = await client.get(url, headers={"User-Agent": BROWSER_UA, "Accept": "text/html"})
        if resp.status_code >= 400:
            return []
        return parse_kwork_listing(resp.text)

    async def _search_keyword_html(
        self, client: httpx.AsyncClient, query: str, *, pages: int = 3
    ) -> list[dict]:
        """Site search + category feeds.

        Freelance Auto-Responder only polls ``c=11``. Keyword SSR often misses
        adjacent rubrics (e.g. project 3266601 lives in c=113/45, not c=11), so
        we also pull configured category listings and filter by query tokens.
        """
        cards: list[dict] = []
        seen: set[str] = set()

        def _add(batch: list[dict]) -> None:
            for card in batch:
                pid = str(card["project_id"])
                if pid in seen:
                    continue
                seen.add(pid)
                cards.append(card)

        # 1) Global keyword pages (как строка поиска на kwork.ru)
        for page in range(1, pages + 1):
            url = f"https://kwork.ru/projects?{urlencode({'keyword': query, 'page': page})}"
            resp = await client.get(
                url, headers={"User-Agent": BROWSER_UA, "Accept": "text/html"}
            )
            if resp.status_code < 400:
                _add(parse_kwork_listing(resp.text))

        # 2) Category feeds (HTML wants[] + API) — API alone often misses SSR cards.
        tokens = [t for t in query.lower().split() if len(t) >= 2]
        for cat in self._category_ids():
            got = await self._search_html(client, cat)
            got.extend(await self._search_api(client, cat, limit=40, pages=2))
            if tokens:
                got = [
                    c
                    for c in got
                    if any(
                        t in (c.get("title") or "").lower()
                        or t in (c.get("description") or "").lower()
                        for t in tokens
                    )
                ]
            _add(got)

        logger.info("kwork keyword=%r cards=%s cats=%s", query, len(cards), self._category_ids())
        return cards

    def _to_items(self, cards: list[dict]) -> list[MarketItem]:
        seen: set[str] = set()
        items: list[MarketItem] = []
        for c in cards:
            pid = str(c["project_id"])
            if pid in seen:
                continue
            seen.add(pid)
            desc = (c.get("description") or c.get("budget_text") or "").strip()
            items.append(
                MarketItem(
                    source=MarketSource.KWORK,
                    external_id=pid,
                    title=c["title"],
                    description=desc,
                    url=c.get("url") or kwork_project_view_url(pid),
                    raw={"budget_text": c.get("budget_text"), "platform": "kwork"},
                )
            )
        return items

    async def search(self, query: str, *, limit: int = 10) -> list[MarketItem]:
        if not self._settings.kwork_enabled:
            return []
        cookies = self._cookies()
        q = query.strip()
        cards: list[dict] = []
        try:
            async with httpx.AsyncClient(
                timeout=45,
                follow_redirects=True,
                cookies=cookies,
            ) as client:
                if q:
                    cards = await self._search_keyword_html(client, q, pages=3)
                    # Soft client filter only if keyword page returned mixed noise
                    tokens = [t for t in q.lower().split() if len(t) >= 2]
                    if tokens and cards:
                        filtered = [
                            c
                            for c in cards
                            if any(
                                t in (c.get("title") or "").lower()
                                or t in (c.get("description") or "").lower()
                                for t in tokens
                            )
                        ]
                        if filtered:
                            cards = filtered
                else:
                    for cat in self._category_ids()[:3]:
                        got = await self._search_api(client, cat, limit * 3, pages=3)
                        if not got:
                            got = await self._search_html(client, cat)
                        cards.extend(got)
                        if len(cards) >= limit * 3:
                            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("kwork search failed: %s", exc)
            return []

        return self._to_items(cards)[:limit]

    async def get_item(self, external_id: str) -> MarketItem | None:
        url = kwork_project_view_url(external_id)
        try:
            async with httpx.AsyncClient(
                timeout=45,
                follow_redirects=True,
                cookies=self._cookies(),
                headers={"User-Agent": BROWSER_UA},
            ) as client:
                resp = await client.get(url)
            if resp.status_code >= 400:
                return None
            parsed = parse_kwork_project(resp.text, external_id)
            return MarketItem(
                source=MarketSource.KWORK,
                external_id=str(parsed.get("project_id") or external_id),
                title=parsed.get("title") or f"Kwork {external_id}",
                description=parsed.get("description") or "",
                url=url,
                raw={"platform": "kwork", "html_len": len(resp.text)},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("kwork get_item failed: %s", exc)
            return None
