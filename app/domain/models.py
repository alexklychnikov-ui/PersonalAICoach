from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CareerTrackType(StrEnum):
    EMPLOYMENT = "employment"
    SIDE_INCOME = "side_income"
    FIRST_FREELANCE_ORDER = "first_freelance_order"
    CUSTOM = "custom"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    SKIPPED = "skipped"


class MarketSource(StrEnum):
    HH = "hh"
    KWORK = "kwork"
    FLRU = "flru"
    YANDEX_USLUGI = "yandex_uslugi"
    TELEGRAM = "telegram"
    MANUAL = "manual"


class UserProfile(BaseModel):
    id: str = "singleton"
    current_position: str = ""
    desired_role: str = ""
    skills: list[str] = Field(default_factory=list)
    growth_areas: list[str] = Field(default_factory=list)
    resume_summary: str = ""
    locale: str = "ru"
    weekly_hours_available: float = 10.0
    updated_at: datetime | None = None


class CareerTrack(BaseModel):
    id: str | None = None
    type: CareerTrackType
    title: str
    deadline: datetime | None = None
    weekly_hours_budget: float = 10.0
    kpis: list[str] = Field(default_factory=list)
    is_active: bool = False
    status: str = "active"
    activated_at: datetime | None = None
    created_at: datetime | None = None


class LearningResource(BaseModel):
    title: str
    url: str | None = None
    kind: str = "course"
    estimated_hours: float | None = None


class PlanPhase(BaseModel):
    name: str
    horizon: str
    goals: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class CareerPlan(BaseModel):
    id: str | None = None
    track_id: str
    summary: str = ""
    phases: list[PlanPhase] = Field(default_factory=list)
    skills_to_develop: list[str] = Field(default_factory=list)
    resources: list[LearningResource] = Field(default_factory=list)
    checklist: list[str] = Field(default_factory=list)
    generated_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class TaskItem(BaseModel):
    id: str | None = None
    plan_id: str
    track_id: str
    title: str
    status: TaskStatus = TaskStatus.TODO
    due: datetime | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class CheckIn(BaseModel):
    id: str | None = None
    track_id: str
    mood: int = Field(ge=1, le=5, default=3)
    wins: str = ""
    blockers: str = ""
    next_actions: str = ""
    created_at: datetime | None = None


class MarketItem(BaseModel):
    id: str | None = None
    source: MarketSource
    external_id: str
    title: str
    description: str = ""
    url: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class SkillGapItem(BaseModel):
    skill: str
    importance: str = "important"
    note: str = ""


class SkillGapReport(BaseModel):
    id: str | None = None
    market_item_id: str
    match_score: int = Field(ge=0, le=100, default=0)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[SkillGapItem] = Field(default_factory=list)
    roadmap_steps: list[str] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime | None = None


class CoachingMessage(BaseModel):
    role: str
    content: str


class CoachingTurnResponse(BaseModel):
    reply: str
    knowledge_context_used: bool = False
    suggested_actions: list[str] = Field(default_factory=list)


class InterviewQuestion(BaseModel):
    question: str
    kind: str = "behavioral"
    expected_points: list[str] = Field(default_factory=list)


class InterviewFeedback(BaseModel):
    score: int = Field(ge=0, le=100, default=0)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    summary: str = ""


class InterviewSession(BaseModel):
    id: str | None = None
    track_id: str
    role_title: str
    questions: list[InterviewQuestion] = Field(default_factory=list)
    answers: list[str] = Field(default_factory=list)
    feedback: InterviewFeedback | None = None
    created_at: datetime | None = None
