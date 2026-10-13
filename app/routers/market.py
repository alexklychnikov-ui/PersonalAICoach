from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import market_service
from app.domain.models import MarketItem, SkillGapReport
from app.services.market_service import MarketService

router = APIRouter(prefix="/market", tags=["market"])


class SearchBody(BaseModel):
    source: str
    query: str
    limit: int = 10


class ManualImportBody(BaseModel):
    title: str
    description: str
    url: str | None = None


class TelegramChannelsBody(BaseModel):
    channels: list[str] = Field(default_factory=list)


class TelegramChannelsOut(BaseModel):
    channels: list[str]


@router.post("/search", response_model=list[MarketItem])
async def search(
    body: SearchBody,
    svc: MarketService = Depends(market_service),
) -> list[MarketItem]:
    try:
        return await svc.search(body.source, body.query, body.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/telegram/channels", response_model=TelegramChannelsOut)
async def get_telegram_channels(
    svc: MarketService = Depends(market_service),
) -> TelegramChannelsOut:
    return TelegramChannelsOut(channels=await svc.get_telegram_channels())


@router.put("/telegram/channels", response_model=TelegramChannelsOut)
async def put_telegram_channels(
    body: TelegramChannelsBody,
    svc: MarketService = Depends(market_service),
) -> TelegramChannelsOut:
    channels = await svc.set_telegram_channels(body.channels)
    return TelegramChannelsOut(channels=channels)


@router.post("/import", response_model=MarketItem)
async def import_manual(
    body: ManualImportBody,
    svc: MarketService = Depends(market_service),
) -> MarketItem:
    return await svc.import_manual(body.title, body.description, body.url)


@router.post("/skill-gap/{item_id}", response_model=SkillGapReport)
async def skill_gap(
    item_id: str,
    svc: MarketService = Depends(market_service),
) -> SkillGapReport:
    try:
        return await svc.skill_gap(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
