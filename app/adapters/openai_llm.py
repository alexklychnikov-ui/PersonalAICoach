import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Settings

logger = logging.getLogger(__name__)


class OpenAILLM:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key or "missing",
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_sec,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def complete_text(self, *, system: str, user: str) -> str:
        if not self._settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        response = await self._client.chat.completions.create(
            model=self._settings.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
        )
        return response.choices[0].message.content or ""

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str | None = None,
    ) -> dict[str, Any]:
        hint = schema_hint or "Return a single JSON object."
        text = await self.complete_text(
            system=f"{system}\n\nRespond ONLY with valid JSON. {hint}",
            user=user,
        )
        return _parse_json(text)


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"LLM did not return JSON: {text[:200]}")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("LLM JSON root must be an object")
    return data


class StubLLM:
    """Deterministic fallback for tests / missing key."""

    async def complete_text(self, *, system: str, user: str) -> str:
        return "Stub coach reply: сфокусируйся на одной задаче на этой неделе."

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str | None = None,
    ) -> dict[str, Any]:
        if "career plan" in system.lower() or "карьерн" in system.lower() or "план" in user.lower():
            return {
                "summary": "Stub career plan for MVP development.",
                "phases": [
                    {
                        "name": "30 дней",
                        "horizon": "1y",
                        "goals": ["Собрать портфолио", "10 откликов"],
                        "skills": ["Python", "FastAPI"],
                    }
                ],
                "skills_to_develop": ["prompt engineering", "RAG"],
                "resources": [
                    {
                        "title": "FastAPI docs",
                        "url": "https://fastapi.tiangolo.com",
                        "kind": "docs",
                        "estimated_hours": 8,
                    }
                ],
                "checklist": [
                    "Обновить резюме",
                    "Сделать 5 персональных откликов",
                    "Подготовить mock interview",
                ],
            }
        if "skill" in system.lower() or "gap" in user.lower():
            return {
                "match_score": 62,
                "strengths": ["Python", "Telegram bots"],
                "gaps": [
                    {"skill": "System design", "importance": "important", "note": "для middle+"},
                    {"skill": "Tests", "importance": "critical", "note": "pytest в портфолио"},
                ],
                "roadmap_steps": ["Добавить тесты в 2 репо", "Один кейс с метриками"],
                "summary": "Stub skill-gap: усилить доказательства в GitHub.",
            }
        if "interview" in system.lower() or "интервью" in user.lower():
            return {
                "questions": [
                    {
                        "question": "Расскажите о проекте с measurable impact.",
                        "kind": "behavioral",
                        "expected_points": ["контекст", "действия", "метрика"],
                    },
                    {
                        "question": "Как проектировали API для бота?",
                        "kind": "technical",
                        "expected_points": ["слои", "ошибки", "идемпотентность"],
                    },
                ]
            }
        if "feedback" in system.lower() or "оцен" in user.lower():
            return {
                "score": 70,
                "strengths": ["Структура ответа"],
                "improvements": ["Добавить цифры результата"],
                "summary": "Stub feedback: хороший каркас, мало метрик.",
            }
        return {"reply": "Stub coach reply", "suggested_actions": ["Сделать один отклик сегодня"]}
