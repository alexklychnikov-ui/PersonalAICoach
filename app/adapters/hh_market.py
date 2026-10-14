import logging
import re

import httpx

from app.adapters.query_expand import (
    dedupe_items,
    remote_keywords_for_term,
    split_query_terms,
)
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

    def _map_items(self, items: list[dict], *, limit: int) -> list[MarketItem]:
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

    async def _search_text(
        self, client: httpx.AsyncClient, text: str, *, limit: int
    ) -> list[MarketItem]:
        params = {"text": text, "per_page": min(max(limit, 10), 50), "page": 0}
        resp = await client.get(
            f"{self._base}/vacancies",
            params=params,
            headers=self._headers(),
        )
        if resp.status_code == 403:
            raise RuntimeError(
                "hh.ru вернул 403 Forbidden — токен/приложение не приняты "
                "или истекли. Проверь статус на https://dev.hh.ru/admin"
            )
        resp.raise_for_status()
        return self._map_items(resp.json().get("items", []), limit=limit)

    async def search(self, query: str, *, limit: int = 10) -> list[MarketItem]:
        if not self._settings.hh_enabled:
            return []
        if not self._settings.hh_access_token:
            raise RuntimeError(
                "hh.ru: нет HH_ACCESS_TOKEN. Заявка на dev.hh.ru ещё "
                "«рассматривается» (до 15 рабочих дней). После одобрения: "
                "scripts/hh_get_token.py app → токен в .env → redeploy."
            )
        terms = split_query_terms(query)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if not terms:
                    return await self._search_text(client, "python", limit=limit)
                merged: list[MarketItem] = []
                for term in terms:
                    for kw in remote_keywords_for_term(term):
                        merged.extend(
                            await self._search_text(client, kw, limit=limit)
                        )
                return dedupe_items(merged)[:limit]
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("hh search failed: %s", exc)
            raise RuntimeError(f"hh.ru поиск упал: {exc}") from exc

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
