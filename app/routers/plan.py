from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import plan_service
from app.domain.models import CareerPlan, TaskItem, TaskStatus
from app.services.plan_service import PlanService

router = APIRouter(prefix="/plans", tags=["plans"])


class GenerateBody(BaseModel):
    track_id: str


class TaskStatusBody(BaseModel):
    status: TaskStatus


@router.post("/generate", response_model=CareerPlan)
async def generate_plan(
    body: GenerateBody,
    svc: PlanService = Depends(plan_service),
) -> CareerPlan:
    try:
        return await svc.generate_plan(body.track_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[CareerPlan])
async def list_plans(
    track_id: str | None = None,
    svc: PlanService = Depends(plan_service),
) -> list[CareerPlan]:
    return await svc.list_plans(track_id)


@router.get("/tasks", response_model=list[TaskItem])
async def list_tasks(
    plan_id: str | None = None,
    svc: PlanService = Depends(plan_service),
) -> list[TaskItem]:
    return await svc.list_tasks(plan_id)


@router.patch("/tasks/{task_id}", response_model=TaskItem)
async def patch_task(
    task_id: str,
    body: TaskStatusBody,
    svc: PlanService = Depends(plan_service),
) -> TaskItem:
    try:
        return await svc.update_task_status(task_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/progress/{track_id}")
async def progress(track_id: str, svc: PlanService = Depends(plan_service)) -> dict:
    return {"track_id": track_id, "percent": await svc.progress_percent(track_id)}
