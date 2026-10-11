from datetime import UTC, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.domain.models import CareerPlan, LearningResource, PlanPhase, TaskItem, TaskStatus
from app.ports.llm import LLMPort
from app.services.profile_service import ProfileService

PLAN_SYSTEM = """Ты карьерный AI-коуч. Составь персональный карьерный план на русском.
Верни JSON:
{
  "summary": str,
  "phases": [{"name": str, "horizon": "1y"|"3y"|"5y", "goals": [str], "skills": [str]}],
  "skills_to_develop": [str],
  "resources": [{"title": str, "url": str|null, "kind": str, "estimated_hours": number|null}],
  "checklist": [str]
}
"""


class PlanService:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        llm: LLMPort,
        profiles: ProfileService,
    ) -> None:
        self._db = db
        self._llm = llm
        self._profiles = profiles

    async def generate_plan(self, track_id: str) -> CareerPlan:
        profile = await self._profiles.get_profile()
        track = None
        for t in await self._profiles.list_tracks():
            if t.id == track_id:
                track = t
                break
        if track is None:
            raise ValueError(f"Track not found: {track_id}")

        user_prompt = (
            f"Профиль: {profile.model_dump_json()}\n"
            f"Активный трек: {track.model_dump_json()}\n"
            "Сгенерируй план."
        )
        data = await self._llm.complete_json(
            system=PLAN_SYSTEM,
            user=user_prompt,
            schema_hint="CareerPlan JSON",
        )
        plan = CareerPlan(
            track_id=track_id,
            summary=str(data.get("summary") or ""),
            phases=[PlanPhase.model_validate(p) for p in data.get("phases") or []],
            skills_to_develop=list(data.get("skills_to_develop") or []),
            resources=[LearningResource.model_validate(r) for r in data.get("resources") or []],
            checklist=list(data.get("checklist") or []),
            generated_at=datetime.now(UTC),
            raw=data,
        )
        payload = plan.model_dump(exclude={"id"})
        result = await self._db.career_plans.insert_one(payload)
        plan.id = str(result.inserted_id)

        for title in plan.checklist:
            task = TaskItem(
                plan_id=plan.id,
                track_id=track_id,
                title=title,
                status=TaskStatus.TODO,
                created_at=datetime.now(UTC),
            )
            await self._db.tasks.insert_one(task.model_dump(exclude={"id"}))
        return plan

    async def list_plans(self, track_id: str | None = None) -> list[CareerPlan]:
        query = {"track_id": track_id} if track_id else {}
        cursor = self._db.career_plans.find(query).sort("generated_at", -1)
        plans: list[CareerPlan] = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            plans.append(CareerPlan.model_validate(doc))
        return plans

    async def list_tasks(self, plan_id: str | None = None) -> list[TaskItem]:
        query = {"plan_id": plan_id} if plan_id else {}
        cursor = self._db.tasks.find(query).sort("created_at", 1)
        tasks: list[TaskItem] = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            tasks.append(TaskItem.model_validate(doc))
        return tasks

    async def update_task_status(self, task_id: str, status: TaskStatus) -> TaskItem:
        result = await self._db.tasks.find_one_and_update(
            {"_id": ObjectId(task_id)},
            {"$set": {"status": status.value}},
            return_document=ReturnDocument.AFTER,
        )
        if not result:
            raise ValueError(f"Task not found: {task_id}")
        result["id"] = str(result.pop("_id"))
        return TaskItem.model_validate(result)

    async def progress_percent(self, track_id: str) -> float:
        total = await self._db.tasks.count_documents({"track_id": track_id})
        if total == 0:
            return 0.0
        done = await self._db.tasks.count_documents(
            {"track_id": track_id, "status": TaskStatus.DONE.value}
        )
        return round(100.0 * done / total, 1)
