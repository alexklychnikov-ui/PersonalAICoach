from fastapi import APIRouter

from app.adapters.factory import build_knowledge_base
from app.config import get_settings
from app.db.mongo import ping_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    mongo_ok = False
    mongo_error = None
    try:
        mongo_ok = await ping_db()
    except Exception as exc:  # noqa: BLE001
        mongo_error = str(exc)

    kb = build_knowledge_base(settings)
    kb_health = await kb.health()

    status = "ok" if mongo_ok else "degraded"
    return {
        "status": status,
        "app": settings.app_name,
        "env": settings.app_env,
        "mongo": {"ok": mongo_ok, "error": mongo_error},
        "knowledge_base": kb_health.model_dump(),
        "llm_configured": bool(settings.openai_api_key),
    }
