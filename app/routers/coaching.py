from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.deps import coaching_service
from app.domain.models import CheckIn, CoachingMessage, CoachingTurnResponse
from app.services.coaching_service import CoachingService

router = APIRouter(prefix="/coaching", tags=["coaching"])


class CoachBody(BaseModel):
    track_id: str
    message: str
    history: list[CoachingMessage] = Field(default_factory=list)


@router.post("/turn", response_model=CoachingTurnResponse)
async def coach_turn(
    body: CoachBody,
    svc: CoachingService = Depends(coaching_service),
) -> CoachingTurnResponse:
    return await svc.coach_turn(
        track_id=body.track_id,
        message=body.message,
        history=body.history,
    )


@router.post("/checkins", response_model=CheckIn)
async def create_checkin(
    body: CheckIn,
    svc: CoachingService = Depends(coaching_service),
) -> CheckIn:
    return await svc.create_checkin(body)


@router.get("/checkins", response_model=list[CheckIn])
async def list_checkins(
    track_id: str | None = None,
    svc: CoachingService = Depends(coaching_service),
) -> list[CheckIn]:
    return await svc.list_checkins(track_id)
