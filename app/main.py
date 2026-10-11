import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.db.mongo import close_db, init_db
from app.routers import coaching, health, interview, market, plan, profile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    try:
        await init_db(settings)
        logger.info("MongoDB connected: %s", settings.mongo_db)
    except Exception as exc:  # noqa: BLE001
        logger.error("MongoDB init failed: %s", exc)
        raise
    yield
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    prefix = settings.api_prefix.rstrip("/")
    app.include_router(profile.router, prefix=prefix)
    app.include_router(plan.router, prefix=prefix)
    app.include_router(coaching.router, prefix=prefix)
    app.include_router(market.router, prefix=prefix)
    app.include_router(interview.router, prefix=prefix)
    return app


app = create_app()
