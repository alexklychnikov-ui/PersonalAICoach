"""Telegram bot: button funnel (menu → status / check-in / coach / progress)."""

from __future__ import annotations

import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from app.config import get_settings
from bot.keyboards import (
    BTN_CANCEL,
    BTN_CHECKIN,
    BTN_COACH,
    BTN_MENU,
    BTN_PROGRESS,
    BTN_SKIP,
    BTN_STATUS,
    main_menu,
    mood_keyboard,
    parse_mood_button,
    step_keyboard,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CheckinFSM(StatesGroup):
    mood = State()
    wins = State()
    blockers = State()


class CoachFSM(StatesGroup):
    waiting = State()


def _owner_only(user_id: int | None) -> bool:
    settings = get_settings()
    if settings.telegram_owner_id is None:
        return True
    return user_id == settings.telegram_owner_id


def _api() -> tuple[str, str]:
    settings = get_settings()
    return settings.api_base_url.rstrip("/"), settings.api_prefix.rstrip("/")


async def _get_active_track(client: httpx.AsyncClient) -> dict | None:
    base, prefix = _api()
    resp = await client.get(f"{base}{prefix}/profile/tracks/active")
    if resp.status_code != 200:
        return None
    data = resp.json()
    return data if isinstance(data, dict) and data.get("id") else None


async def _require_track(message: Message, client: httpx.AsyncClient) -> dict | None:
    track = await _get_active_track(client)
    if track:
        return track
    await message.answer(
        "Нет активного трека.\n"
        "Сначала зайди в Streamlit → Онбординг и активируй цель.",
        reply_markup=main_menu(),
    )
    return None


def _fmt_health(data: dict) -> str:
    status = data.get("status") or "—"
    status_ru = {
        "ok": "всё в порядке",
        "degraded": "частично недоступно",
        "error": "ошибка",
    }.get(str(status), str(status))
    mongo = data.get("mongo") or {}
    mongo_ru = "ок" if mongo.get("ok") else f"проблема ({mongo.get('error') or '—'})"
    kb = data.get("knowledge_base") or {}
    if kb.get("enabled"):
        kb_ru = "включена" if kb.get("ok") else f"сбой ({kb.get('detail') or '—'})"
    else:
        kb_ru = "выключена"
    llm_ru = "настроен" if data.get("llm_configured") else "нет ключа (StubLLM)"
    return (
        f"Состояние: {status_ru}\n"
        f"MongoDB: {mongo_ru}\n"
        f"База знаний: {kb_ru}\n"
        f"LLM: {llm_ru}"
    )


async def run_polling() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty")

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    base, prefix = _api()

    async def _gate(message: Message) -> bool:
        return _owner_only(message.from_user.id if message.from_user else None)

    @dp.message(Command("start", "menu", "help"))
    async def start_cmd(message: Message, state: FSMContext) -> None:
        if not await _gate(message):
            return
        await state.clear()
        await message.answer(
            "Персональный ИИ-коуч.\n\n"
            "Выбери действие кнопкой ниже — так понятнее, куда что писать.\n\n"
            f"• {BTN_STATUS} — здоровье API и активный трек\n"
            f"• {BTN_PROGRESS} — % плана и задачи\n"
            f"• {BTN_CHECKIN} — настроение → что получилось → что мешает\n"
            f"• {BTN_COACH} — один вопрос коучу текстом\n\n"
            "Или снова /start, если меню пропало.",
            reply_markup=main_menu(),
        )

    @dp.message(F.text == BTN_MENU)
    @dp.message(F.text == BTN_CANCEL)
    async def back_to_menu(message: Message, state: FSMContext) -> None:
        if not await _gate(message):
            return
        await state.clear()
        await message.answer("Главное меню:", reply_markup=main_menu())

    @dp.message(F.text == BTN_STATUS)
    async def status_btn(message: Message, state: FSMContext) -> None:
        if not await _gate(message):
            return
        await state.clear()
        async with httpx.AsyncClient(timeout=30) as client:
            health = await client.get(f"{base}/health")
            track = await _get_active_track(client)
        health_txt = (
            _fmt_health(health.json())
            if health.status_code == 200
            else f"API недоступен ({health.status_code})"
        )
        track_txt = (
            f"Активный трек: {track.get('title')}"
            if track
            else "Активный трек: нет — зайди в Онбординг в UI"
        )
        await message.answer(
            f"{health_txt}\n\n{track_txt}",
            reply_markup=main_menu(),
        )

    @dp.message(F.text == BTN_PROGRESS)
    async def progress_btn(message: Message, state: FSMContext) -> None:
        if not await _gate(message):
            return
        await state.clear()
        async with httpx.AsyncClient(timeout=30) as client:
            track = await _require_track(message, client)
            if not track:
                return
            track_id = track["id"]
            prog = await client.get(f"{base}{prefix}/plans/progress/{track_id}")
            plans = await client.get(
                f"{base}{prefix}/plans", params={"track_id": track_id}
            )
        percent = (
            (prog.json() or {}).get("percent", 0)
            if prog.status_code == 200
            else "—"
        )
        plan_list = (
            plans.json()
            if plans.status_code == 200 and isinstance(plans.json(), list)
            else []
        )
        summary = ""
        if plan_list:
            summary = (plan_list[0].get("summary") or "").strip()
            if len(summary) > 400:
                summary = summary[:400] + "…"
        lines = [
            f"Трек: {track.get('title')}",
            f"Прогресс плана: {percent}%",
        ]
        if summary:
            lines.extend(["", "Кратко по плану:", summary])
        else:
            lines.append("\nПлана ещё нет — сгенерируй в Streamlit → План.")
        await message.answer("\n".join(lines), reply_markup=main_menu())

    @dp.message(F.text == BTN_CHECKIN)
    async def checkin_start(message: Message, state: FSMContext) -> None:
        if not await _gate(message):
            return
        async with httpx.AsyncClient(timeout=30) as client:
            if not await _require_track(message, client):
                return
        await state.set_state(CheckinFSM.mood)
        await message.answer(
            "Check-in · шаг 1/3 — Настроение\n\n"
            "Как прошла неделя / день по шкале 1–5?\n"
            "Жми кнопку — руками писать не нужно.",
            reply_markup=mood_keyboard(),
        )

    @dp.message(StateFilter(CheckinFSM.mood))
    async def checkin_mood(message: Message, state: FSMContext) -> None:
        if not await _gate(message):
            return
        mood = parse_mood_button(message.text or "")
        if mood is None:
            await message.answer(
                "Выбери настроение кнопкой 1–5.",
                reply_markup=mood_keyboard(),
            )
            return
        await state.update_data(mood=mood)
        await state.set_state(CheckinFSM.wins)
        await message.answer(
            f"Check-in · шаг 2/3 — Что получилось?\n\n"
            f"Настроение: {mood}/5.\n"
            "Напиши коротко wins (или «Пропустить»).",
            reply_markup=step_keyboard(allow_skip=True),
        )

    @dp.message(StateFilter(CheckinFSM.wins))
    async def checkin_wins(message: Message, state: FSMContext) -> None:
        if not await _gate(message):
            return
        text = (message.text or "").strip()
        if text == BTN_CANCEL:
            await state.clear()
            await message.answer("Отменено.", reply_markup=main_menu())
            return
        wins = "" if text == BTN_SKIP else text
        await state.update_data(wins=wins)
        await state.set_state(CheckinFSM.blockers)
        await message.answer(
            "Check-in · шаг 3/3 — Что мешает?\n\n"
            "Напиши blockers (или «Пропустить»).",
            reply_markup=step_keyboard(allow_skip=True),
        )

    @dp.message(StateFilter(CheckinFSM.blockers))
    async def checkin_blockers(message: Message, state: FSMContext) -> None:
        if not await _gate(message):
            return
        text = (message.text or "").strip()
        if text == BTN_CANCEL:
            await state.clear()
            await message.answer("Отменено.", reply_markup=main_menu())
            return
        blockers = "" if text == BTN_SKIP else text
        data = await state.get_data()
        await state.clear()
        async with httpx.AsyncClient(timeout=30) as client:
            track = await _require_track(message, client)
            if not track:
                return
            resp = await client.post(
                f"{base}{prefix}/coaching/checkins",
                json={
                    "track_id": track["id"],
                    "mood": int(data.get("mood") or 3),
                    "wins": data.get("wins") or "",
                    "blockers": blockers,
                },
            )
        if resp.status_code >= 300:
            await message.answer(
                f"Не удалось сохранить check-in ({resp.status_code}).",
                reply_markup=main_menu(),
            )
            return
        await message.answer(
            "Check-in сохранён.\n\n"
            f"Настроение: {data.get('mood')}/5\n"
            f"Получилось: {(data.get('wins') or '—') or '—'}\n"
            f"Мешает: {blockers or '—'}",
            reply_markup=main_menu(),
        )

    @dp.message(F.text == BTN_COACH)
    async def coach_start(message: Message, state: FSMContext) -> None:
        if not await _gate(message):
            return
        async with httpx.AsyncClient(timeout=30) as client:
            if not await _require_track(message, client):
                return
        await state.set_state(CoachFSM.waiting)
        await message.answer(
            "Спросить коуча\n\n"
            "Напиши одним сообщением вопрос или апдейт.\n"
            "Пример: «что сделать на этой неделе под мой KPI?»",
            reply_markup=step_keyboard(allow_skip=False),
        )

    @dp.message(StateFilter(CoachFSM.waiting))
    async def coach_message(message: Message, state: FSMContext) -> None:
        if not await _gate(message):
            return
        text = (message.text or "").strip()
        if text == BTN_CANCEL or text == BTN_MENU:
            await state.clear()
            await message.answer("Главное меню:", reply_markup=main_menu())
            return
        if not text or text.startswith("/"):
            await message.answer(
                "Напиши текст вопроса (не команду).",
                reply_markup=step_keyboard(allow_skip=False),
            )
            return
        await state.clear()
        async with httpx.AsyncClient(timeout=90) as client:
            track = await _require_track(message, client)
            if not track:
                return
            resp = await client.post(
                f"{base}{prefix}/coaching/turn",
                json={"track_id": track["id"], "message": text, "history": []},
            )
        if resp.status_code >= 300:
            await message.answer(
                f"Ошибка коучинга: {resp.status_code}",
                reply_markup=main_menu(),
            )
            return
        data = resp.json()
        actions = data.get("suggested_actions") or []
        suffix = ("\n\nДальше:\n• " + "\n• ".join(actions)) if actions else ""
        kb = "\n\n(с учётом базы знаний)" if data.get("knowledge_context_used") else ""
        await message.answer(
            f"{data.get('reply')}{kb}{suffix}",
            reply_markup=main_menu(),
        )

    @dp.message(F.text)
    async def fallback_text(message: Message, state: FSMContext) -> None:
        if not await _gate(message):
            return
        if await state.get_state() is not None:
            return
        text = (message.text or "").strip()
        if text.startswith("/"):
            return
        await message.answer(
            "Свободный текст больше не угадывается.\n"
            f"Нажми {BTN_COACH}, если хочешь спросить коуча, "
            f"или {BTN_CHECKIN} для недельного отчёта.",
            reply_markup=main_menu(),
        )

    logger.info("Telegram bot polling started (button funnel)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_polling())
