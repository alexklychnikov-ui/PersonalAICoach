"""Reply keyboards for Telegram bot funnel."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

BTN_STATUS = "📊 Статус"
BTN_CHECKIN = "✅ Check-in"
BTN_COACH = "💬 Спросить коуча"
BTN_PROGRESS = "📈 Прогресс"
BTN_MENU = "🏠 Меню"
BTN_SKIP = "Пропустить"
BTN_CANCEL = "« Назад в меню"

MOOD_LABELS = {
    "1": "1 — тяжело",
    "2": "2 — так себе",
    "3": "3 — нормально",
    "4": "4 — хорошо",
    "5": "5 — отлично",
}


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_STATUS), KeyboardButton(text=BTN_PROGRESS)],
            [KeyboardButton(text=BTN_CHECKIN), KeyboardButton(text=BTN_COACH)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие кнопкой…",
    )


def mood_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MOOD_LABELS["1"]), KeyboardButton(text=MOOD_LABELS["2"])],
            [KeyboardButton(text=MOOD_LABELS["3"]), KeyboardButton(text=MOOD_LABELS["4"])],
            [KeyboardButton(text=MOOD_LABELS["5"])],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Выбери настроение 1–5",
    )


def step_keyboard(*, allow_skip: bool = False) -> ReplyKeyboardMarkup:
    row = [KeyboardButton(text=BTN_CANCEL)]
    if allow_skip:
        row.insert(0, KeyboardButton(text=BTN_SKIP))
    return ReplyKeyboardMarkup(
        keyboard=[row],
        resize_keyboard=True,
        input_field_placeholder="Напиши текст или нажми кнопку…",
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def parse_mood_button(text: str) -> int | None:
    raw = (text or "").strip()
    if raw[:1].isdigit() and raw[0] in "12345":
        return int(raw[0])
    return None
