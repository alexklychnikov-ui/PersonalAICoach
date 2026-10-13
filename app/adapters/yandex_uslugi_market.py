"""Яндекс.Услуги — Playwright DOM scrape (как Freelance Auto-Responder)."""

from __future__ import annotations

import asyncio
import logging
import re

import httpx

from app.adapters.browser_scrape import YANDEX_LISTING_JS, scrape_with_playwright
from app.adapters.market_urls import (
    BROWSER_UA,
    YANDEX_USLUGI_ORIGIN,
    yandex_order_url,
)
from app.adapters.playwright_storage import load_httpx_cookies
from app.config import Settings
from app.domain.models import MarketItem, MarketSource

logger = logging.getLogger(__name__)

_UUID = (
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


def parse_yandex_listing(html: str) -> list[dict]:
    seen: set[str] = set()
    cards: list[dict] = []
    for m in re.finditer(
        rf'href=["\']([^"\']*/order/({_UUID})[^"\']*)["\']',
        html,
        flags=re.I,
    ):
        href, oid = m.group(1), m.group(2).lower()
        if oid in seen:
            continue
        seen.add(oid)
        window = html[max(0, m.start() - 200) : m.end() + 400]
        title = ""
        tm = re.search(r">([^<]{5,200})</a>", window, flags=re.I)
        if tm:
            title = re.sub(r"\s+", " ", tm.group(1)).strip()
        url = href if href.startswith("http") else f"{YANDEX_USLUGI_ORIGIN}{href}"
        url = url.split("?")[0]
        cards.append(
            {
                "project_id": oid,
                "url": url,
                "title": title or f"Заказ {oid[:8]}",
                "budget_text": None,
                "description": "",
            }
        )
    return cards


def parse_yandex_order(html: str, order_id: str | None = None) -> dict:
    pid = (order_id or "").lower() or None
    if not pid:
        m = re.search(_UUID, html, flags=re.I)
        if m:
            pid = m.group(0).lower()
    title = ""
    for pat in (
        r"<h1[^>]*>(.*?)</h1>",
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
        r"<title[^>]*>([^<]+)</title>",
    ):
        m = re.search(pat, html, flags=re.I | re.DOTALL)
        if m:
            title = re.sub(r"<[^>]+>", " ", m.group(1))
            title = re.sub(r"\s+", " ", title).strip()
            title = re.sub(r"\s*[|·—-].*$", "", title).strip()
            if title:
                break
    desc = re.sub(r"<[^>]+>", " ", html)
    desc = re.sub(r"\s+", " ", desc).strip()[:8000]
    return {"project_id": pid, "title": title, "description": desc}


def _filter_query(items: list[MarketItem], query: str) -> list[MarketItem]:
    if not query.strip():
        return items
    tokens = [t for t in query.lower().split() if len(t) >= 2]
    if not tokens:
        return items
    return [
        i
        for i in items
        if any(t in i.title.lower() or t in i.description.lower() for t in tokens)
    ]


class YandexUslugiMarketSource:
    name = "yandex_uslugi"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _cards_to_items(self, cards: list[dict]) -> list[MarketItem]:
        items: list[MarketItem] = []
        for c in cards:
            pid = str(c.get("project_id") or "").lower()
            if not re.fullmatch(_UUID, pid, flags=re.I):
                continue
            desc = (c.get("description") or c.get("budget_text") or "").strip()
            items.append(
                MarketItem(
                    source=MarketSource.YANDEX_USLUGI,
                    external_id=pid,
                    title=str(c.get("title") or f"Заказ {pid[:8]}"),
                    description=desc,
                    url=str(c.get("url") or yandex_order_url(pid)),
                    raw={"budget_text": c.get("budget_text"), "platform": "yandex_uslugi"},
                )
            )
        return items

    async def search(self, query: str, *, limit: int = 10) -> list[MarketItem]:
        if not self._settings.yandex_uslugi_enabled:
            return []
        state = self._settings.yandex_storage_state
        if not state:
            logger.warning("Yandex.Uslugi: set YANDEX_STORAGE_STATE")
            return []

        url = self._settings.yandex_listing_url
        cards: list[dict] = []
        try:
            cards = await asyncio.to_thread(
                scrape_with_playwright,
                url=url,
                storage_state_path=state,
                evaluate_js=YANDEX_LISTING_JS,
                wait_ms=5000,
            )
            logger.info("yandex playwright cards=%s", len(cards))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Yandex playwright failed: %s — fallback httpx", exc)
            cookies = load_httpx_cookies(state)
            if cookies is None:
                return []
            try:
                async with httpx.AsyncClient(
                    timeout=45,
                    follow_redirects=True,
                    cookies=cookies,
                    headers={"User-Agent": BROWSER_UA, "Accept-Language": "ru-RU,ru;q=0.9"},
                ) as client:
                    resp = await client.get(url)
                cards = parse_yandex_listing(resp.text)
            except Exception as exc2:  # noqa: BLE001
                logger.warning("Yandex httpx fallback failed: %s", exc2)
                return []

        items = _filter_query(self._cards_to_items(cards), query)
        return items[:limit]

    async def get_item(self, external_id: str) -> MarketItem | None:
        url = yandex_order_url(external_id)
        state = self._settings.yandex_storage_state
        try:
            if state:
                cards = await asyncio.to_thread(
                    scrape_with_playwright,
                    url=url,
                    storage_state_path=state,
                    evaluate_js="""
                    () => {
                      const title = (document.querySelector('h1')?.textContent || document.title || '')
                        .replace(/\\s+/g, ' ').trim();
                      const root = document.querySelector('main, article') || document.body;
                      const description = (root?.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 8000);
                      return [{ project_id: location.pathname.match(
                        /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i)?.[0]?.toLowerCase()
                        || null, url: location.href.split('?')[0], title, description, budget_text: null }];
                    }
                    """,
                    wait_ms=3000,
                )
                if cards:
                    items = self._cards_to_items(cards)
                    if items:
                        return items[0]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Yandex get_item playwright failed: %s", exc)

        cookies = load_httpx_cookies(state) if state else None
        try:
            async with httpx.AsyncClient(
                timeout=45,
                follow_redirects=True,
                cookies=cookies,
                headers={"User-Agent": BROWSER_UA},
            ) as client:
                resp = await client.get(url)
            if resp.status_code >= 400:
                return None
            parsed = parse_yandex_order(resp.text, external_id)
            return MarketItem(
                source=MarketSource.YANDEX_USLUGI,
                external_id=str(parsed.get("project_id") or external_id),
                title=parsed.get("title") or f"Яндекс {external_id[:8]}",
                description=parsed.get("description") or "",
                url=url,
                raw={"platform": "yandex_uslugi"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Yandex get_item failed: %s", exc)
            return None
