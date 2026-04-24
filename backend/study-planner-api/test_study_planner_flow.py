"""CLI script to test the study planner flow while bypassing ingest.

This script assumes study content has already been indexed into Qdrant.
It creates or reuses a subject, skips PDF ingest, runs the planner pipeline,
and prints a concise summary of the generated plan.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, timedelta

from app import models  # noqa: F401
from app.agents.study_planner_agent import StudyPlannerAgent
from app.database import Base, SessionLocal, engine
from app.models.study_plan import StudyPlan
from app.models.study_session import StudySession
from app.models.study_subject import StudySubject
from app.models.subject_free_slot import SubjectFreeSlot
from app.services.llm_client import create_llm_client
from app.services.planner_orchestrator import run_full_pipeline, set_planner_agent


DEFAULT_FREE_TIME = {
    "mon": ["07:00", "08:00"],
    "wed": ["07:00", "08:00"],
    "fri": ["08:00", "09:00", "10:00"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test the study planner flow while skipping the ingest step.",
    )
    parser.add_argument("--subject-id", type=int, help="Reuse an existing subject instead of creating a new one.")
    parser.add_argument("--user-id", type=int, default=1, help="User ID used when creating a subject.")
    parser.add_argument("--subject-name", default="Kinh te vi mo", help="Subject name for Qdrant retrieval.")
    parser.add_argument("--target-grade", type=float, default=7.0, help="Target grade for plan generation.")
    parser.add_argument(
        "--end-date",
        default=(date.today() + timedelta(days=28)).isoformat(),
        help="Plan end date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--free-time-json",
        default=json.dumps(DEFAULT_FREE_TIME, ensure_ascii=False),
        help="Free time JSON, for example: {\"mon\": [\"07:00\", \"08:00\"]}",
    )
    parser.add_argument(
        "--google-access-token",
        default=None,
        help="Optional Google access token to test calendar sync.",
    )
    parser.add_argument(
        "--google-refresh-token",
        default=None,
        help="Optional Google refresh token to test calendar sync.",
    )
    return parser.parse_args()


def ensure_subject(args: argparse.Namespace) -> int:
    free_time = json.loads(args.free_time_json)

    with SessionLocal() as db:
        if args.subject_id:
            subject = db.query(StudySubject).filter_by(id=args.subject_id).first()
            if not subject:
                raise ValueError(f"Subject {args.subject_id} not found")
            return subject.id

        subject = StudySubject(
            user_id=args.user_id,
            name=args.subject_name,
            target_grade=args.target_grade,
            end_date=date.fromisoformat(args.end_date),
            status="active",
            ingest_status="pending",
            plan_status="pending",
        )
        db.add(subject)
        db.flush()

        for day, slots in free_time.items():
            for slot in slots:
                db.add(
                    SubjectFreeSlot(
                        subject_id=subject.id,
                        day_of_week=day,
                        time_slot=slot,
                    )
                )

        db.commit()
        return subject.id


def load_summary(subject_id: int) -> dict:
    with SessionLocal() as db:
        subject = db.query(StudySubject).filter_by(id=subject_id).first()
        if not subject:
            raise ValueError(f"Subject {subject_id} not found after pipeline run")

        plan = (
            db.query(StudyPlan)
            .filter_by(subject_id=subject_id)
            .order_by(StudyPlan.created_at.desc())
            .first()
        )
        sessions = []
        if plan:
            sessions = (
                db.query(StudySession)
                .filter_by(plan_id=plan.id)
                .order_by(StudySession.session_date, StudySession.start_time)
                .all()
            )

        return {
            "subject_id": subject.id,
            "subject_name": subject.name,
            "ingest_status": subject.ingest_status,
            "plan_status": subject.plan_status,
            "plan_id": plan.id if plan else None,
            "session_count": len(sessions),
            "sessions_preview": [
                {
                    "session_date": s.session_date.isoformat() if s.session_date else None,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "title": s.title,
                }
                for s in sessions[:5]
            ],
        }


async def main() -> None:
    args = parse_args()

    Base.metadata.create_all(bind=engine)
    set_planner_agent(StudyPlannerAgent(create_llm_client()))

    subject_id = ensure_subject(args)
    print(f"Running study planner pipeline for subject_id={subject_id} with ingest bypassed...")

    await run_full_pipeline(
        subject_id=subject_id,
        file_bytes=None,
        file_name=None,
        google_access_token=args.google_access_token,
        google_refresh_token=args.google_refresh_token,
    )

    summary = load_summary(subject_id)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if summary["plan_status"] != "completed" or summary["session_count"] == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())