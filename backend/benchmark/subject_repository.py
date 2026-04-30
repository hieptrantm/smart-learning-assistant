from __future__ import annotations

from contextlib import contextmanager

from benchmark.bootstrap import configure_paths
from benchmark.models import SubjectDescriptor

configure_paths()

from app.database import SessionLocal  # type: ignore  # noqa: E402
from app.models.study_subject import StudySubject  # type: ignore  # noqa: E402


class SubjectRepository:
    @contextmanager
    def session(self):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def get_subject(self, subject_id: int) -> SubjectDescriptor:
        with self.session() as db:
            subject = db.query(StudySubject).filter_by(id=subject_id).first()
            if not subject:
                raise ValueError(f"Subject {subject_id} not found")

            free_slots: dict[str, list[str]] = {}
            for slot in subject.free_slots:
                free_slots.setdefault(slot.day_of_week, []).append(slot.time_slot)

            return SubjectDescriptor(
                subject_id=subject.id,
                subject_name=subject.name,
                target_grade=float(subject.target_grade) if subject.target_grade is not None else None,
                end_date=subject.end_date.isoformat() if subject.end_date else None,
                free_slots={key: sorted(value) for key, value in free_slots.items()},
            )
