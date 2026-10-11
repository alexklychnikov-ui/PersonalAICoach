from fastapi import APIRouter, Depends, HTTPException
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
