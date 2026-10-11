from datetime import UTC, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.models import InterviewFeedback, InterviewQuestion, InterviewSession
from app.ports.llm import LLMPort
from app.services.profile_service import ProfileService

Q_SYSTEM = """Сгенерируй вопросы mock-интервью на русском.
JSON: {"questions": [{"question": str, "kind": str, "expected_points": [str]}]}
"""

F_SYSTEM = """Оцени ответы кандидата на русском.
JSON: {"score": 0-100, "strengths": [str], "improvements": [str], "summary": str}
"""


class InterviewService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        llm: LLMPort,
        profiles: ProfileService,
    ) -> None:
        self._db = db
        self._llm = llm
        self._profiles = profiles

    async def start(self, track_id: str, role_title: str) -> InterviewSession:
        profile = await self._profiles.get_profile()
        data = await self._llm.complete_json(
            system=Q_SYSTEM,
            user=(
                f"Роль: {role_title}\n"
                f"Навыки: {profile.skills}\n"
                f"Рост: {profile.growth_areas}"
            ),
        )
        questions = [InterviewQuestion.model_validate(q) for q in data.get("questions") or []]
        session = InterviewSession(
            track_id=track_id,
            role_title=role_title,
            questions=questions,
            answers=[],
            created_at=datetime.now(UTC),
        )
        result = await self._db.interview_sessions.insert_one(session.model_dump(exclude={"id"}))
        session.id = str(result.inserted_id)
        return session

    async def submit_answers(self, session_id: str, answers: list[str]) -> InterviewSession:
        doc = await self._db.interview_sessions.find_one({"_id": ObjectId(session_id)})
        if not doc:
            raise ValueError(f"Interview session not found: {session_id}")
        doc["id"] = str(doc.pop("_id"))
        session = InterviewSession.model_validate(doc)
        qa_text = "\n".join(
            f"Q: {q.question}\nA: {a}"
            for q, a in zip(session.questions, answers, strict=False)
        )
        data = await self._llm.complete_json(
            system=F_SYSTEM,
            user=f"Роль: {session.role_title}\n{qa_text}",
        )
        feedback = InterviewFeedback.model_validate(data)
        await self._db.interview_sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"answers": answers, "feedback": feedback.model_dump()}},
        )
        session.answers = answers
        session.feedback = feedback
        return session
