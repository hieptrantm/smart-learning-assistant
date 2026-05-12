"""
planner_controller.py – FastAPI router for study-planner endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth import get_current_user_id
from app.models import StudySubject, SubjectFreeSlot, StudyPlan, StudySession
from app.schemas.planner import (
    SubjectOut,
    StudyPlanOut,
    PipelineStatusOut,
    GoogleTokenRequest,
    UpdateSessionStatusRequest,
)
from app.services.planner_orchestrator import run_full_pipeline

from typing import Optional, List

router = APIRouter(prefix="/planner", tags=["Study Planner"])


# ── Helpers ───────────────────────────────────────────────────

def _subject_to_out(s: StudySubject) -> dict:
    """Convert a StudySubject ORM object to a response dict."""
    free_time: dict[str, list[str]] = {}
    for slot in s.free_slots:
        if slot.day_of_week not in free_time:
            free_time[slot.day_of_week] = []
        free_time[slot.day_of_week].append(slot.time_slot)
    for day in free_time:
        free_time[day].sort()

    return {
        "id": s.id,
        "user_id": s.user_id,
        "name": s.name,
        "emoji": s.emoji,
        "target_grade": float(s.target_grade or 7),
        "end_date": s.end_date.isoformat() if s.end_date else None,
        "status": s.status,
        "ingest_status": s.ingest_status,
        "plan_status": s.plan_status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "documents": [
            {
                "id": d.id,
                "file_name": d.file_name,
                "file_size": d.file_size,
                "mime_type": d.mime_type,
            }
            for d in s.documents
        ],
        "free_time": free_time,
    }


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/subjects", summary="List all subjects for current user")
def list_subjects(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    subjects = (
        db.query(StudySubject)
        .filter_by(user_id=user_id)
        .order_by(StudySubject.created_at.desc())
        .all()
    )
    return [_subject_to_out(s) for s in subjects]


@router.get("/subjects/{subject_id}", summary="Get one subject detail")
def get_subject(
    subject_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    s = db.query(StudySubject).filter_by(id=subject_id, user_id=user_id).first()
    if not s:
        raise HTTPException(404, "Subject not found")
    return _subject_to_out(s)



@router.delete("/subjects/{subject_id}", summary="Delete a subject and all related data")
def delete_subject(
    subject_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    subject = db.query(StudySubject).filter_by(id=subject_id, user_id=user_id).first()
    if not subject:
        raise HTTPException(404, "Subject not found")
    db.delete(subject)
    db.commit()
    return {"message": "Deleted"}


@router.get("/subjects/{subject_id}/status", summary="Check pipeline status")
def get_pipeline_status(
    subject_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    s = db.query(StudySubject).filter_by(id=subject_id, user_id=user_id).first()
    if not s:
        raise HTTPException(404, "Subject not found")
    return {
        "subject_id": s.id,
        "subject_name": s.name,
        "ingest_status": s.ingest_status,
        "plan_status": s.plan_status,
        "ingest_job_id": s.ingest_job_id,
    }


@router.get("/subjects/{subject_id}/plan", summary="Get generated study plan")
def get_plan(
    subject_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    subject = db.query(StudySubject).filter_by(id=subject_id, user_id=user_id).first()
    if not subject:
        raise HTTPException(404, "Subject not found")

    plan = (
        db.query(StudyPlan)
        .filter_by(subject_id=subject_id)
        .order_by(StudyPlan.created_at.desc())
        .first()
    )
    if not plan:
        raise HTTPException(404, "No plan generated yet")

    sessions = (
        db.query(StudySession)
        .filter_by(plan_id=plan.id)
        .order_by(StudySession.session_date, StudySession.start_time)
        .all()
    )

    return {
        "id": plan.id,
        "subject_id": plan.subject_id,
        "plan_json": plan.plan_json,
        "calendar_synced": plan.calendar_synced,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "sessions": [
            {
                "id": s.id,
                "session_date": s.session_date.isoformat() if s.session_date else None,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "title": s.title,
                "content": s.content,
                "status": s.status,
                "learning_status": s.learning_status,
                "checkpoint_node_id": s.checkpoint_node_id,
                "score": float(s.score) if s.score is not None else None,
                "calendar_event_id": s.calendar_event_id,
            }
            for s in sessions
        ],
    }


@router.post("/subjects/{subject_id}/generate-plan", summary="Trigger plan generation (called by data-ingestor after ingest)")
async def generate_plan(
    subject_id: int,
    background_tasks: BackgroundTasks,
    body: Optional[GoogleTokenRequest] = None,
    db: Session = Depends(get_db),
):
    """Internal endpoint called by data-ingestor once ingest_status = 'completed'."""
    s = db.query(StudySubject).filter_by(id=subject_id).first()
    if not s:
        raise HTTPException(404, "Subject not found")

    google_access_token = body.google_access_token if body else None
    google_refresh_token = body.google_refresh_token if body else None

    data = background_tasks.add_task(
        run_full_pipeline,
        subject_id,
        google_access_token,
        google_refresh_token,
    )
    return {"message": "Plan generation started", "subject_id": subject_id}


@router.put("/sessions/{session_id}/learning-status", summary="Update learning_status of a study session")
def update_session_learning_status(
    session_id: int,
    body: UpdateSessionStatusRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    session = (
        db.query(StudySession)
        .join(StudySubject, StudySession.subject_id == StudySubject.id)
        .filter(StudySession.id == session_id, StudySubject.user_id == user_id)
        .first()
    )
    if not session:
        raise HTTPException(404, "Session not found")

    session.learning_status = body.learning_status
    if body.score is not None:
        session.score = body.score
    db.commit()
    return {"message": "Updated", "session_id": session_id, "learning_status": body.learning_status}


@router.post("/subjects/{subject_id}/regenerate-plan", summary="Re-run plan generation for failed sessions")
async def regenerate_plan(
    subject_id: int,
    background_tasks: BackgroundTasks,
    body: Optional[GoogleTokenRequest] = None,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Re-generate plan if any session has learning_status='failed'."""
    subject = db.query(StudySubject).filter_by(id=subject_id, user_id=user_id).first()
    if not subject:
        raise HTTPException(404, "Subject not found")

    # Check if there are failed sessions
    failed_count = (
        db.query(StudySession)
        .filter_by(subject_id=subject_id, learning_status="failed")
        .count()
    )
    if failed_count == 0:
        return {"message": "No failed sessions, no regeneration needed", "subject_id": subject_id}

    google_access_token = body.google_access_token if body else None
    google_refresh_token = body.google_refresh_token if body else None

    background_tasks.add_task(
        run_full_pipeline,
        subject_id,
        google_access_token,
        google_refresh_token,
    )
    return {"message": "Plan regeneration started", "subject_id": subject_id, "failed_sessions": failed_count}


# Get all occupied slots for a user (for conflict detection in planner agent)
@router.get("/occupied-slots/{user_id_param}", summary="Get all occupied time slots for a user")
def get_occupied_slots(
    user_id_param: int,
    exclude_subject_id: int = None,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Return all occupied slots across user's subjects for conflict detection."""
    if user_id_param != user_id:
        raise HTTPException(403, "Forbidden")

    query = db.query(SubjectFreeSlot).join(StudySubject).filter(StudySubject.user_id == user_id)
    if exclude_subject_id:
        query = query.filter(SubjectFreeSlot.subject_id != exclude_subject_id)

    slots = query.all()
    occupied: dict[str, list[str]] = {}
    for s in slots:
        if s.day_of_week not in occupied:
            occupied[s.day_of_week] = []
        occupied[s.day_of_week].append(s.time_slot)

    return occupied


# Kịch bản test cho pipeline import môn học -> lưu db -> ingest pdf -> tạo plan -> sync calendar
if __name__ == "__main__":
    import asyncio
    from app.database import SessionLocal
    from app.services.planner_orchestrator import run_full_pipeline

    # Giả lập dữ liệu đầu vào
    subject_id = 1  # ID môn học đã tồn tại trong DB
    file_bytes = b"%PDF-1.4 fake pdf content"  # Nội dung PDF giả
    file_name = "study_material.pdf"
    google_access_token = "ya29.fake_token"
    google_refresh_token = None

    # Chạy pipeline
    asyncio.run(
        run_full_pipeline(
            subject_id,
            file_bytes,
            file_name,
            google_access_token,
            google_refresh_token,
        )
    )