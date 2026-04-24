from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date, datetime


# ── Request schemas ───────────────────────────────────────────

class UpdateSessionStatusRequest(BaseModel):
    learning_status: Literal["not_started", "passed", "failed"]
    score: Optional[float] = None


class SubjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    emoji: str = Field(default="📚", max_length=10)
    target_grade: float = Field(default=7.0, ge=1.0, le=10.0)
    end_date: Optional[date] = None
    free_time: dict[str, list[str]] = Field(
        default_factory=dict,
        description='{"mon": ["08:00","09:00"], "wed": ["14:00"]}',
    )


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    emoji: Optional[str] = None
    target_grade: Optional[float] = None
    end_date: Optional[date] = None
    free_time: Optional[dict[str, list[str]]] = None


class GoogleTokenRequest(BaseModel):
    google_access_token: Optional[str] = None
    google_refresh_token: Optional[str] = None


# ── Response schemas ──────────────────────────────────────────

class DocumentOut(BaseModel):
    id: int
    file_name: str
    file_size: Optional[str] = None
    mime_type: Optional[str] = None

    class Config:
        from_attributes = True


class FreeSlotOut(BaseModel):
    day_of_week: str
    time_slot: str

    class Config:
        from_attributes = True


class SubjectOut(BaseModel):
    id: int
    user_id: int
    name: str
    emoji: str
    target_grade: float
    end_date: Optional[date] = None
    status: str
    ingest_status: str
    plan_status: str
    created_at: datetime
    documents: list[DocumentOut] = []
    free_time: dict[str, list[str]] = {}

    class Config:
        from_attributes = True


class StudySessionOut(BaseModel):
    id: int
    session_date: date
    start_time: str
    end_time: str
    title: Optional[str] = None
    content: Optional[str] = None
    status: str
    learning_status: str
    score: Optional[float] = None
    calendar_event_id: Optional[str] = None

    class Config:
        from_attributes = True


class StudyPlanOut(BaseModel):
    id: int
    subject_id: int
    plan_json: dict
    calendar_synced: bool
    created_at: datetime
    sessions: list[StudySessionOut] = []

    class Config:
        from_attributes = True


class PipelineStatusOut(BaseModel):
    subject_id: int
    subject_name: str
    ingest_status: str
    plan_status: str
    ingest_job_id: Optional[str] = None
