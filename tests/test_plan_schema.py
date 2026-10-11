import pytest

from app.adapters.openai_llm import StubLLM
from app.domain.models import CareerPlan, PlanPhase


@pytest.mark.asyncio
async def test_stub_llm_career_plan_json():
    llm = StubLLM()
    data = await llm.complete_json(
        system="Create a career plan JSON",
        user="Сгенерируй план для Python разработчика",
    )
    plan = CareerPlan(
        track_id="t1",
        summary=data["summary"],
        phases=[PlanPhase.model_validate(p) for p in data["phases"]],
        skills_to_develop=data["skills_to_develop"],
        resources=data["resources"],
        checklist=data["checklist"],
    )
    assert plan.summary
    assert plan.phases
    assert plan.checklist
