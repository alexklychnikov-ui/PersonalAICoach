"""FL.ru read-only market source — parsers/URLs from Freelance Auto-Responder."""

from __future__ import annotations

import logging
import re

import httpx

from app.adapters.market_urls import (
    BROWSER_UA,
    FLRU_ORIGIN,
    ensure_flru_for_all,
    flru_project_url,
)
from app.adapters.playwright_storage import load_httpx_cookies
from app.adapters.query_expand import dedupe_items, filter_items_by_query
from app.config import Settings
from app.domain.models import MarketItem, MarketSource

logger = logging.getLogger(__name__)

_CLOSED_RE = re.compile(
    r"(?:исполнитель\s+определ|выбрал\s+исполнител|исполнитель\s+выбран)",
    re.I,
)


def _is_closed(text: str) -> bool:
    return bool(_CLOSED_RE.search(text or ""))


def parse_flru_listing(html: str, *, skip_closed: bool = True) -> list[dict]:
    seen: set[str] = set()
    cards: list[dict] = []
    for m in re.finditer(
        r'href=["\']([^"\']*/projects/(\d{5,9})[^"\']*)["\']',
        html,
        flags=re.I,
    ):
        href, pid = m.group(1), m.group(2)
        if pid in seen:
            continue
        start_a = html.rfind("<a", 0, m.start())
        end_a = html.find("</a>", m.end())
        if start_a < 0 or end_a < 0:
            continue
        link_html = html[start_a : end_a + 4]
        title = ""
        tm = re.search(r">([^<]{5,200})</a>", link_html, flags=re.I)
        if tm:
            title = re.sub(r"\s+", " ", tm.group(1)).strip()
        vac = "\u0432\u0430\u043a\u0430\u043d\u0441\u0438\u044f"
        if vac in title.lower() or vac in href.lower():
            continue
        # Closed / budget from a short trail after this link only
        trail = html[end_a : end_a + 280]
        if skip_closed and _is_closed(link_html + trail):
            continue
        seen.add(pid)
        budget = None
        bm = re.search(
            r"(\u043f\u043e \u0434\u043e\u0433\u043e\u0432\u043e\u0440\u0435\u043d\u043d\u043e\u0441\u0442\u0438|\d[\d\s]*\s*\u0440\u0443\u0431)",
            trail,
            flags=re.I,
        )
        if bm:
            budget = re.sub(r"\s+", " ", bm.group(1)).strip()
        url = href if href.startswith("http") else f"{FLRU_ORIGIN}{href}"
        url = url.split("?")[0]
        cards.append(
            {
                "project_id": pid,
                "url": url,
                "title": title or f"Project {pid}",
                "budget_text": budget,
            }
        )
    return cards


def parse_flru_project(html: str, project_id: str | None = None) -> dict:
    pid = (project_id or "").strip() or None
    if not pid:
        m = re.search(r"/projects/(\d{5,9})", html, flags=re.I)
        if m:
            pid = m.group(1)
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
    desc = ""
    for pat in (
        r'class="[^"]*description[^"]*"[^>]*>(.*?)</(?:div|section)>',
        r"<article[^>]*>(.*?)</article>",
    ):
        m = re.search(pat, html, flags=re.I | re.DOTALL)
        if m:
            raw = re.sub(r"<script[^>]*>.*?</script>", " ", m.group(1), flags=re.I | re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", raw)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) > len(desc):
                desc = text
    return {"project_id": pid, "title": title, "description": desc[:12000]}


class FlruMarketSource:
    name = "flru"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def search(self, query: str, *, limit: int = 10) -> list[MarketItem]:
        if not self._settings.flru_enabled:
            return []
        cookies = load_httpx_cookies(self._settings.flru_storage_state)
        if cookies is None:
            logger.warning("FL.ru: set FLRU_STORAGE_STATE to Playwright storage JSON")
            return []
        url = ensure_flru_for_all(self._settings.flru_listing_url)
        try:
            async with httpx.AsyncClient(
                timeout=45,
                follow_redirects=True,
                cookies=cookies,
                headers={"User-Agent": BROWSER_UA, "Accept-Language": "ru-RU,ru;q=0.9"},
            ) as client:
                resp = await client.get(url)
            if resp.status_code >= 400:
                logger.warning("FL.ru listing HTTP %s", resp.status_code)
                return []
            if "account/login" in str(resp.url).lower() or "войти" in resp.text[:2000].lower():
                logger.warning("FL.ru session expired — refresh FLRU_STORAGE_STATE")
                return []
            cards = parse_flru_listing(resp.text, skip_closed=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("FL.ru search failed: %s", exc)
            return []

        items = [
            MarketItem(
                source=MarketSource.FLRU,
                external_id=c["project_id"],
                title=c["title"],
                description=c.get("budget_text") or "",
                url=c["url"],
                raw={"budget_text": c.get("budget_text"), "platform": "flru"},
            )
            for c in cards
        ]
        items = filter_items_by_query(items, query)
        return dedupe_items(items)[:limit]

    async def get_item(self, external_id: str) -> MarketItem | None:
        cookies = load_httpx_cookies(self._settings.flru_storage_state)
        url = flru_project_url(external_id)
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
            parsed = parse_flru_project(resp.text, external_id)
            return MarketItem(
                source=MarketSource.FLRU,
                external_id=str(parsed.get("project_id") or external_id),
                title=parsed.get("title") or f"FL.ru {external_id}",
                description=parsed.get("description") or "",
                url=url,
                raw={"platform": "flru"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("FL.ru get_item failed: %s", exc)
            return None
