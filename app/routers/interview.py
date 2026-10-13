from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.deps import interview_service
from app.domain.models import InterviewSession
from app.services.interview_service import InterviewService

router = APIRouter(prefix="/interview", tags=["interview"])


class StartBody(BaseModel):
    track_id: str
    role_title: str


class AnswersBody(BaseModel):
    answers: list[str] = Field(default_factory=list)


@router.post("/start", response_model=InterviewSession)
async def start(
    body: StartBody,
    svc: InterviewService = Depends(interview_service),
) -> InterviewSession:
    return await svc.start(body.track_id, body.role_title)


@router.get("/latest", response_model=InterviewSession | None)
async def latest(
    track_id: str | None = Query(default=None),
    svc: InterviewService = Depends(interview_service),
) -> InterviewSession | None:
    return await svc.latest(track_id)


@router.get("/{session_id}", response_model=InterviewSession)
async def get_session(
    session_id: str,
    svc: InterviewService = Depends(interview_service),
) -> InterviewSession:
    try:
        return await svc.get(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{session_id}/draft", response_model=InterviewSession)
async def save_draft(
    session_id: str,
    body: AnswersBody,
    svc: InterviewService = Depends(interview_service),
) -> InterviewSession:
    try:
        return await svc.save_draft(session_id, body.answers)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{session_id}/answers", response_model=InterviewSession)
async def submit_answers(
    session_id: str,
    body: AnswersBody,
    svc: InterviewService = Depends(interview_service),
) -> InterviewSession:
    try:
        return await svc.submit_answers(session_id, body.answers)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
