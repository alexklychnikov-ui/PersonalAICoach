from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import Settings, get_settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def init_db(settings: Settings | None = None) -> AsyncIOMotorDatabase:
    global _client, _db
    settings = settings or get_settings()
    if _db is not None:
        return _db
    _client = AsyncIOMotorClient(settings.build_mongo_uri(), serverSelectionTimeoutMS=5000)
    _db = _client[settings.mongo_db]
    await _ensure_indexes(_db)
    return _db


async def _ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.market_items.create_index(
        [("source", 1), ("external_id", 1)],
        unique=True,
        name="uniq_source_external",
    )
    await db.tasks.create_index([("plan_id", 1), ("status", 1)], name="tasks_plan_status")
    await db.career_tracks.create_index([("is_active", 1)], name="tracks_active")


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database is not initialized. Call init_db() first.")
    return _db


async def ping_db() -> bool:
    db = get_db()
    result = await db.command("ping")
    return result.get("ok") == 1.0


async def close_db() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None
