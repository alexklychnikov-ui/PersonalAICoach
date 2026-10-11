from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.models import CheckIn, CoachingMessage, CoachingTurnResponse
from app.ports.knowledge_base import KnowledgeBasePort
from app.ports.llm import LLMPort
from app.services.profile_service import ProfileService

COACH_SYSTEM = """Ты еженедельный карьерный коуч. Отвечай кратко на русском.
Верни JSON: {"reply": str, "suggested_actions": [str]}
"""


class CoachingService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        llm: LLMPort,
        kb: KnowledgeBasePort,
        profiles: ProfileService,
    ) -> None:
        self._db = db
        self._llm = llm
        self._kb = kb
        self._profiles = profiles

    async def coach_turn(
        self,
        *,
        track_id: str,
        message: str,
        history: list[CoachingMessage] | None = None,
    ) -> CoachingTurnResponse:
        profile = await self._profiles.get_profile()
        kb_result = await self._kb.search(
            f"карьера {profile.desired_role or profile.current_position}: {message}"
        )
        history = history or []
        hist_text = "\n".join(f"{m.role}: {m.content}" for m in history[-8:])
        user = (
            f"Профиль: {profile.model_dump_json()}\n"
            f"Трек: {track_id}\n"
            f"История:\n{hist_text}\n"
            f"Контекст KB (может быть пустым):\n{kb_result.text[:4000]}\n"
            f"Сообщение пользователя: {message}"
        )
        data = await self._llm.complete_json(system=COACH_SYSTEM, user=user)
        reply = str(data.get("reply") or data.get("response") or "")
        actions = list(data.get("suggested_actions") or [])
        turn = CoachingTurnResponse(
            reply=reply,
            knowledge_context_used=kb_result.used,
            suggested_actions=actions,
        )
        await self._db.coaching_sessions.insert_one(
            {
                "track_id": track_id,
                "messages": [
                    *(m.model_dump() for m in history),
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": reply},
                ],
                "knowledge_context_used": turn.knowledge_context_used,
                "suggested_actions": actions,
                "created_at": datetime.now(UTC),
            }
        )
        return turn

    async def create_checkin(self, checkin: CheckIn) -> CheckIn:
        checkin.created_at = datetime.now(UTC)
        result = await self._db.checkins.insert_one(checkin.model_dump(exclude={"id"}))
        checkin.id = str(result.inserted_id)
        return checkin

    async def list_checkins(self, track_id: str | None = None, limit: int = 20) -> list[CheckIn]:
        query = {"track_id": track_id} if track_id else {}
        cursor = self._db.checkins.find(query).sort("created_at", -1).limit(limit)
        items: list[CheckIn] = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            items.append(CheckIn.model_validate(doc))
        return items
