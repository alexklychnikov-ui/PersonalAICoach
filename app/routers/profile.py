from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.defaults.profile_seed import DEFAULT_PROFILE, DEFAULT_TRACK, TRACK_TYPE_LABELS
from app.deps import profile_service
from app.domain.models import CareerTrack, CareerTrackType, UserProfile
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["profile"])


class TrackCreate(BaseModel):
    type: CareerTrackType
    title: str
    weekly_hours_budget: float = 10.0
    kpis: list[str] = Field(default_factory=list)
    activate: bool = True


@router.get("", response_model=UserProfile)
async def get_profile(svc: ProfileService = Depends(profile_service)) -> UserProfile:
    return await svc.get_profile()


@router.put("", response_model=UserProfile)
async def put_profile(
    profile: UserProfile,
    svc: ProfileService = Depends(profile_service),
) -> UserProfile:
    return await svc.save_profile(profile)


@router.get("/defaults")
async def get_defaults() -> dict:
    return {
        "profile": DEFAULT_PROFILE,
        "track": DEFAULT_TRACK,
        "track_type_labels": TRACK_TYPE_LABELS,
    }


@router.post("/seed")
async def seed_profile(
    force_profile: bool = Query(False),
    svc: ProfileService = Depends(profile_service),
) -> dict:
    result = await svc.seed_defaults(force_profile=force_profile)
    return {
        "profile": result["profile"].model_dump(mode="json"),
        "track": result["track"].model_dump(mode="json"),
    }


@router.get("/tracks", response_model=list[CareerTrack])
async def list_tracks(svc: ProfileService = Depends(profile_service)) -> list[CareerTrack]:
    return await svc.list_tracks()


@router.post("/tracks", response_model=CareerTrack)
async def create_track(
    body: TrackCreate,
    svc: ProfileService = Depends(profile_service),
) -> CareerTrack:
    track = CareerTrack(
        type=body.type,
        title=body.title,
        weekly_hours_budget=body.weekly_hours_budget,
        kpis=body.kpis,
    )
    return await svc.create_track(track)


@router.post("/tracks/upsert", response_model=CareerTrack)
async def upsert_track(
    body: TrackCreate,
    svc: ProfileService = Depends(profile_service),
) -> CareerTrack:
    track = CareerTrack(
        type=body.type,
        title=body.title,
        weekly_hours_budget=body.weekly_hours_budget,
        kpis=body.kpis,
    )
    return await svc.upsert_track(track, activate=body.activate)


@router.get("/tracks/active", response_model=CareerTrack | None)
async def active_track(svc: ProfileService = Depends(profile_service)) -> CareerTrack | None:
    return await svc.get_active_track()


@router.post("/tracks/{track_id}/activate", response_model=CareerTrack)
async def activate_track(
    track_id: str,
    svc: ProfileService = Depends(profile_service),
) -> CareerTrack:
    try:
        return await svc.activate_track(track_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
