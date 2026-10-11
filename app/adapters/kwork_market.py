import logging
import re

import httpx

from app.config import Settings
from app.domain.models import MarketItem, MarketSource

logger = logging.getLogger(__name__)


class KworkMarketSource:
    """
    Read-only Kwork projects listing.

    Uses public projects HTML/JSON endpoints when available; degrades to empty
    list on auth/HTML changes. Manual import remains the hard fallback.
    """

    name = "kwork"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def search(self, query: str, *, limit: int = 10) -> list[MarketItem]:
        if not self._settings.kwork_enabled:
            return []
        # Prefer category poll; keyword filter applied client-side when present.
        category_ids = [
            c.strip() for c in self._settings.kwork_category_ids.split(",") if c.strip()
        ]
        items: list[MarketItem] = []
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                for cat in category_ids[:3]:
                    url = f"https://kwork.ru/projects?fc={cat}&page=1"
                    resp = await client.get(
                        url,
                        headers={
                            "User-Agent": "PersonalAICoach/0.1",
                            "Accept": "text/html",
                        },
                    )
                    if resp.status_code >= 400:
                        continue
                    # Lightweight parse: extract project links /titles heuristically
                    html = resp.text
                    items.extend(_parse_kwork_projects(html, limit=limit))
                    if len(items) >= limit:
                        break
        except Exception as exc:  # noqa: BLE001
            logger.warning("kwork search failed: %s", exc)
            return []

        if query:
            q = query.lower()
            items = [i for i in items if q in i.title.lower() or q in i.description.lower()]
        return items[:limit]

    async def get_item(self, external_id: str) -> MarketItem | None:
        url = f"https://kwork.ru/projects/{external_id}"
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "PersonalAICoach/0.1"})
            if resp.status_code >= 400:
                return None
            title = _first_match(resp.text, r"<title>(.*?)</title>") or f"Kwork {external_id}"
            return MarketItem(
                source=MarketSource.KWORK,
                external_id=external_id,
                title=title.replace(" — Kwork", "").strip(),
                description=resp.text[:4000],
                url=url,
                raw={"html_len": len(resp.text)},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("kwork get_item failed: %s", exc)
            return None


def _first_match(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def _parse_kwork_projects(html: str, *, limit: int) -> list[MarketItem]:
    ids = re.findall(r"/projects/(\d+)", html)
    seen: set[str] = set()
    items: list[MarketItem] = []
    for pid in ids:
        if pid in seen:
            continue
        seen.add(pid)
        items.append(
            MarketItem(
                source=MarketSource.KWORK,
                external_id=pid,
                title=f"Kwork project {pid}",
                description="",
                url=f"https://kwork.ru/projects/{pid}",
                raw={},
            )
        )
        if len(items) >= limit:
            break
    return items
