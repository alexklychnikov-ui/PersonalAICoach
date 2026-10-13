from datetime import UTC, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.adapters.telegram_market import (
    TelegramMarketSource,
    normalize_channel_list,
)
from app.config import get_settings
from app.domain.models import (
    MarketItem,
    MarketSource,
    SkillGapItem,
    SkillGapReport,
)
from app.ports.llm import LLMPort
from app.ports.market import MarketSourcePort
from app.services.profile_service import ProfileService

_TG_CHANNELS_DOC = "telegram_channels"

GAP_SYSTEM = """Ты карьерный аналитик. Сравни навыки кандидата с вакансией/заказом.
Верни JSON:
{
  "match_score": 0-100,
  "strengths": [str],
  "gaps": [{"skill": str, "importance": "critical"|"important"|"nice-to-have", "note": str}],
  "roadmap_steps": [str],
  "summary": str
}
"""


class MarketService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        llm: LLMPort,
        sources: list[MarketSourcePort],
        profiles: ProfileService,
    ) -> None:
        self._db = db
        self._llm = llm
        self._sources = {s.name: s for s in sources}
        self._profiles = profiles

    async def search(self, source: str, query: str, limit: int = 10) -> list[MarketItem]:
        adapter = self._sources.get(source)
        if not adapter:
            raise ValueError(f"Unknown market source: {source}")
        if source == "telegram" and isinstance(adapter, TelegramMarketSource):
            channels = await self.get_telegram_channels()
            items = await adapter.search_channels(
                channels, (query or "").strip(), limit=limit
            )
        else:
            items = await adapter.search(query, limit=limit)
        saved: list[MarketItem] = []
        for item in items:
            saved.append(await self._upsert_item(item))
        return saved

    async def get_telegram_channels(self) -> list[str]:
        doc = await self._db.market_settings.find_one({"_id": _TG_CHANNELS_DOC})
        if doc and isinstance(doc.get("channels"), list) and doc["channels"]:
            return normalize_channel_list([str(x) for x in doc["channels"]])
        seed = normalize_channel_list(
            get_settings().telegram_channels.replace(",", "\n").splitlines()
        )
        if seed:
            await self.set_telegram_channels(seed)
        return seed

    async def set_telegram_channels(self, channels: list[str]) -> list[str]:
        normalized = normalize_channel_list(channels)
        await self._db.market_settings.update_one(
            {"_id": _TG_CHANNELS_DOC},
            {
                "$set": {
                    "channels": normalized,
                    "updated_at": datetime.now(UTC),
                }
            },
            upsert=True,
        )
        return normalized

    async def import_manual(
        self, title: str, description: str, url: str | None = None
    ) -> MarketItem:
        external_id = f"manual-{abs(hash((title, description))) % 10_000_000}"
        item = MarketItem(
            source=MarketSource.MANUAL,
            external_id=external_id,
            title=title,
            description=description,
            url=url,
            raw={"manual": True},
        )
        return await self._upsert_item(item)

    async def get_item(self, item_id: str) -> MarketItem:
        doc = await self._db.market_items.find_one({"_id": ObjectId(item_id)})
        if not doc:
            raise ValueError(f"Market item not found: {item_id}")
        doc["id"] = str(doc.pop("_id"))
        return MarketItem.model_validate(doc)

    async def skill_gap(self, market_item_id: str) -> SkillGapReport:
        item = await self.get_item(market_item_id)
        profile = await self._profiles.get_profile()
        data = await self._llm.complete_json(
            system=GAP_SYSTEM,
            user=(
                f"Профиль skills: {profile.skills}\n"
                f"Роль: {profile.desired_role}\n"
                f"Вакансия/заказ: {item.title}\n{item.description[:6000]}"
            ),
        )
        report = SkillGapReport(
            market_item_id=market_item_id,
            match_score=int(data.get("match_score") or 0),
            strengths=list(data.get("strengths") or []),
            gaps=[SkillGapItem.model_validate(g) for g in data.get("gaps") or []],
            roadmap_steps=list(data.get("roadmap_steps") or []),
            summary=str(data.get("summary") or ""),
            created_at=datetime.now(UTC),
        )
        result = await self._db.skill_gaps.insert_one(report.model_dump(exclude={"id"}))
        report.id = str(result.inserted_id)
        return report

    async def _upsert_item(self, item: MarketItem) -> MarketItem:
        item.created_at = item.created_at or datetime.now(UTC)
        data = item.model_dump(exclude={"id"})
        await self._db.market_items.update_one(
            {"source": item.source.value, "external_id": item.external_id},
            {"$set": data},
            upsert=True,
        )
        doc = await self._db.market_items.find_one(
            {"source": item.source.value, "external_id": item.external_id}
        )
        assert doc is not None
        doc["id"] = str(doc.pop("_id"))
        return MarketItem.model_validate(doc)
