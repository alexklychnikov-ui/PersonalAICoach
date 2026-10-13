import asyncio
import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _poll_source(source: str) -> None:
    settings = get_settings()
    api = settings.api_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{api}{settings.api_prefix}/market/search",
                json={"source": source, "query": "", "limit": 10},
            )
        logger.info(
            "%s poll status=%s count=%s",
            source,
            resp.status_code,
            len(resp.json() or []),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s poll failed: %s", source, exc)


async def poll_kwork() -> None:
    if get_settings().kwork_enabled:
        await _poll_source("kwork")


async def poll_flru() -> None:
    if get_settings().flru_enabled:
        await _poll_source("flru")


async def poll_yandex() -> None:
    if get_settings().yandex_uslugi_enabled:
        await _poll_source("yandex_uslugi")


async def weekly_checkin_ping() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_owner_id:
        logger.info("Skip weekly ping: telegram not configured")
        return
    from aiogram import Bot

    bot = Bot(token=settings.telegram_bot_token)
    try:
        await bot.send_message(
            settings.telegram_owner_id,
            "Weekly check-in: ответь `/checkin` или текстом "
            "`4 | wins | blockers`.",
        )
    finally:
        await bot.session.close()


async def main() -> None:
    settings = get_settings()
    if not settings.worker_enabled:
        logger.info("Worker disabled")
        return

    scheduler = AsyncIOScheduler(timezone=settings.tz)
    scheduler.add_job(
        poll_kwork,
        "interval",
        seconds=max(60, settings.kwork_poll_interval_sec),
        id="kwork_poll",
    )
    scheduler.add_job(
        poll_flru,
        "interval",
        seconds=max(60, settings.flru_poll_interval_sec),
        id="flru_poll",
    )
    scheduler.add_job(
        poll_yandex,
        "interval",
        seconds=max(60, settings.yandex_poll_interval_sec),
        id="yandex_poll",
    )
    parts = settings.checkin_cron.split()
    if len(parts) == 5:
        minute, hour, _, _, day_of_week = parts
        scheduler.add_job(
            weekly_checkin_ping,
            "cron",
            minute=minute,
            hour=hour,
            day_of_week=day_of_week,
            id="weekly_checkin",
        )
    else:
        scheduler.add_job(weekly_checkin_ping, "interval", days=7, id="weekly_checkin")

    scheduler.start()
    logger.info("Worker started")
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
