import logging
import re

import httpx

from app.config import Settings
from app.domain.models import MarketItem, MarketSource

logger = logging.getLogger(__name__)


class HHMarketSource:
    name = "hh"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base = "https://api.hh.ru"

    def _headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": self._settings.hh_user_agent,
            "Accept": "application/json",
        }
        if self._settings.hh_access_token:
            headers["Authorization"] = f"Bearer {self._settings.hh_access_token}"
        return headers

    async def search(self, query: str, *, limit: int = 10) -> list[MarketItem]:
        if not self._settings.hh_enabled:
            return []
        params = {"text": query, "per_page": min(limit, 50), "page": 0}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self._base}/vacancies",
                    params=params,
                    headers=self._headers(),
                )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            result: list[MarketItem] = []
            for item in items[:limit]:
                result.append(
                    MarketItem(
                        source=MarketSource.HH,
                        external_id=str(item["id"]),
                        title=item.get("name") or "Vacancy",
                        description=(item.get("snippet") or {}).get("requirement")
                        or item.get("name")
                        or "",
                        url=item.get("alternate_url"),
                        raw=item,
                    )
                )
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("hh search failed: %s", exc)
            return []

    async def get_item(self, external_id: str) -> MarketItem | None:
        if not self._settings.hh_enabled:
            return None
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self._base}/vacancies/{external_id}",
                    headers=self._headers(),
                )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            desc = data.get("description") or ""
            desc = re.sub(r"<[^>]+>", " ", desc)
            return MarketItem(
                source=MarketSource.HH,
                external_id=str(data["id"]),
                title=data.get("name") or "Vacancy",
                description=desc.strip(),
                url=data.get("alternate_url"),
                raw=data,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("hh get_item failed: %s", exc)
            return None
