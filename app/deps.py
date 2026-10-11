from functools import lru_cache

from fastapi import Request

from app.adapters.factory import build_knowledge_base, build_llm, build_market_sources
from app.config import Settings, get_settings
from app.db.mongo import get_db
from app.services.coaching_service import CoachingService
from app.services.interview_service import InterviewService
from app.services.market_service import MarketService
from app.services.plan_service import PlanService
from app.services.profile_service import ProfileService


@lru_cache
def settings_dep() -> Settings:
    return get_settings()


def profile_service(request: Request) -> ProfileService:
    settings: Settings = request.app.state.settings
    return ProfileService(get_db(), profile_id=settings.profile_doc_id)


def plan_service(request: Request) -> PlanService:
    settings: Settings = request.app.state.settings
    return PlanService(get_db(), build_llm(settings), profile_service(request))


def coaching_service(request: Request) -> CoachingService:
    settings: Settings = request.app.state.settings
    return CoachingService(
        get_db(),
        build_llm(settings),
        build_knowledge_base(settings),
        profile_service(request),
    )


def market_service(request: Request) -> MarketService:
    settings: Settings = request.app.state.settings
    return MarketService(
        get_db(),
        build_llm(settings),
        build_market_sources(settings),
        profile_service(request),
    )


def interview_service(request: Request) -> InterviewService:
    settings: Settings = request.app.state.settings
    return InterviewService(get_db(), build_llm(settings), profile_service(request))
