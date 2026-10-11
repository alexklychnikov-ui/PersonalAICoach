import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _owner_only(user_id: int | None) -> bool:
    settings = get_settings()
    if settings.telegram_owner_id is None:
        return True
    return user_id == settings.telegram_owner_id


async def run_polling() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty")

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    api = settings.api_base_url.rstrip("/")

    @dp.message(Command("start"))
    async def start_cmd(message: Message) -> None:
        if not _owner_only(message.from_user.id if message.from_user else None):
            return
        await message.answer(
            "Personal AI Coach.\n"
            "Команды: /status /checkin\n"
            "Или просто напиши апдейт за неделю."
        )

    @dp.message(Command("status"))
    async def status_cmd(message: Message) -> None:
        if not _owner_only(message.from_user.id if message.from_user else None):
            return
        async with httpx.AsyncClient(timeout=30) as client:
            health = await client.get(f"{api}/health")
            tracks = await client.get(f"{api}{settings.api_prefix}/profile/tracks/active")
        active = tracks.json() if tracks.status_code == 200 else None
        title = active.get("title") if isinstance(active, dict) else "нет активного трека"
        await message.answer(f"API: {health.json().get('status')}\nТрек: {title}")

    @dp.message(Command("checkin"))
    async def checkin_cmd(message: Message) -> None:
        if not _owner_only(message.from_user.id if message.from_user else None):
            return
        await message.answer(
            "Формат check-in:\n"
            "настроение 1-5 | wins | blockers\n"
            "Пример: 4 | сделал 3 отклика | нет времени вечером"
        )

    @dp.message(F.text)
    async def text_handler(message: Message) -> None:
        if not _owner_only(message.from_user.id if message.from_user else None):
            return
        text = (message.text or "").strip()
        if text.startswith("/"):
            return

        async with httpx.AsyncClient(timeout=60) as client:
            active = await client.get(f"{api}{settings.api_prefix}/profile/tracks/active")
            track = active.json() if active.status_code == 200 else None
            track_id = track.get("id") if isinstance(track, dict) else None
            if not track_id:
                await message.answer("Нет активного трека. Заполни онбординг в Streamlit.")
                return

            if "|" in text and text[0].isdigit():
                parts = [p.strip() for p in text.split("|")]
                mood = int(parts[0]) if parts[0].isdigit() else 3
                wins = parts[1] if len(parts) > 1 else ""
                blockers = parts[2] if len(parts) > 2 else ""
                resp = await client.post(
                    f"{api}{settings.api_prefix}/coaching/checkins",
                    json={
                        "track_id": track_id,
                        "mood": mood,
                        "wins": wins,
                        "blockers": blockers,
                    },
                )
                if resp.status_code < 300:
                    await message.answer("Check-in сохранён.")
                    return

            resp = await client.post(
                f"{api}{settings.api_prefix}/coaching/turn",
                json={"track_id": track_id, "message": text, "history": []},
            )
            if resp.status_code >= 300:
                await message.answer(f"Ошибка коучинга: {resp.status_code}")
                return
            data = resp.json()
            actions = data.get("suggested_actions") or []
            suffix = ("\n\nДальше:\n- " + "\n- ".join(actions)) if actions else ""
            kb = " (KB)" if data.get("knowledge_context_used") else ""
            await message.answer(f"{data.get('reply')}{kb}{suffix}")

    logger.info("Telegram bot polling started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_polling())
