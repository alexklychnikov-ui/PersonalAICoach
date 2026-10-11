from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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


@router.post("/search", response_model=list[MarketItem])
async def search(
    body: SearchBody,
    svc: MarketService = Depends(market_service),
) -> list[MarketItem]:
    try:
        return await svc.search(body.source, body.query, body.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
