from typing import List, Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.study_session import StudySession
from app.models.subject_message import SubjectMessage


def update_learning_status(session_id: int, learning_status: str, db: Optional[Session] = None) -> bool:
    """
    Update the learning_status of a study session.

    learning_status values: 'not_started' | 'in_progress' | 'completed'
    Returns True if the record was found and updated, False otherwise.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        session = db.query(StudySession).filter_by(id=session_id).first()
        if not session:
            return False
        session.learning_status = learning_status
        db.commit()
        return True
    finally:
        if close_db:
            db.close()


def add_subject_message(subject_id: int, user_id: int, role: str, content: str, db: Optional[Session] = None) -> int:
    """
    Add a chat message linked to a subject.

    role: 'user' or 'assistant'
    Returns the id of the inserted message.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        msg = SubjectMessage(
            subject_id=subject_id,
            user_id=user_id,
            role=role,
            content=content,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg.id
    finally:
        if close_db:
            db.close()


def get_subject_messages(subject_id: int, db: Optional[Session] = None) -> List[SubjectMessage]:
    """
    Retrieve all messages for a given subject, ordered by creation time.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        return (
            db.query(SubjectMessage)
            .filter_by(subject_id=subject_id)
            .order_by(SubjectMessage.created_at.asc())
            .all()
        )
    finally:
        if close_db:
            db.close()


def delete_subject_messages(subject_id: int, db: Optional[Session] = None) -> int:
    """
    Delete all messages for a given subject.
    Returns the number of deleted rows.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        deleted = db.query(SubjectMessage).filter_by(subject_id=subject_id).delete()
        db.commit()
        return deleted
    finally:
        if close_db:
            db.close()
