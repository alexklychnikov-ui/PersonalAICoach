"""Prefill profile/track from personal LightRAG context (Александр Клычников)."""

from app.domain.models import CareerTrackType

DEFAULT_PROFILE = {
    "id": "singleton",
    "current_position": "Python / AI-разработчик (ERP→AI, Telegram, автоматизация)",
    "desired_role": (
        "Python/AI подрядчик и product-разработчик: Telegram-боты, RAG/LightRAG, "
        "MVP и интеграции для МСБ/стартапов (удалёнка)"
    ),
    "skills": [
        "Python",
        "FastAPI",
        "OpenAI API",
        "RAG / LightRAG",
        "LangChain (базово)",
        "prompt-инжиниринг",
        "aiogram",
        "Telegram Bot API",
        "PostgreSQL",
        "MongoDB",
        "Docker",
        "Linux VPS",
        "REST API",
        "asyncio",
        "Make / n8n",
        "X++ / Dynamics AX (бэкграунд)",
        "интеграции ERP/API",
    ],
    "growth_areas": [
        "разговорный английский (live)",
        "упаковка кейсов с метриками",
        "стабильный поток персональных откликов",
        "system design для middle+ вакансий",
        "тесты/CI как доказательство качества",
    ],
    "resume_summary": (
        "Python/AI-разработчик из Иркутска. Многолетний бэкграунд в корпоративных ERP "
        "(Microsoft Dynamics AX, X++): доработки, интеграции, автоматизация бизнес-процессов. "
        "Сейчас фокус на Python, AI и Telegram-ботах: собираю рабочие MVP с LLM/RAG и API — "
        "от бота с памятью до LightRAG на VPS (Docker, hybrid-поиск, MCP в Cursor, Q&A). "
        "Формула: понял задачу → собрал решение → довёл до деплоя и измеримого эффекта. "
        "Позиционирование: не «новичок-вайбкодер», а опытный разработчик, "
        "осваивающий AI-инструменты для быстрых Python/Telegram/автоматизационных заказов."
    ),
    "locale": "ru",
    "weekly_hours_available": 15.0,
}

DEFAULT_TRACK = {
    "type": CareerTrackType.FIRST_FREELANCE_ORDER.value,
    "title": "Первые платные заказы: Telegram + AI/RAG + автоматизация",
    "weekly_hours_budget": 15.0,
    "kpis": [
        "10–15 персональных откликов/нед (Kwork / FL / Telegram)",
        "конверсия ответ≥15% от отправленных",
        "1–3 оплаченных проекта за 30 дней",
        "1–3 отзыва + 2 кейса (проблема→решение→результат→GitHub)",
        "фокус-ниши: боты, AI/RAG, API-интеграции для МСБ",
    ],
}

TRACK_TYPE_LABELS = {
    "employment": "Устройство на работу",
    "side_income": "Доп. заработок",
    "first_freelance_order": "Первые заказы на фрилансе",
    "custom": "Своя цель",
}
