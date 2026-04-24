"""
models.py -- ORM models shared with study-planner-api (same PostgreSQL DB).
"""
from sqlalchemy import (
    Column, Integer, String, Numeric, Date, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.db_utils import Base


class StudySubject(Base):
    __tablename__ = "study_subjects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    emoji = Column(String(10), default="📚")
    target_grade = Column(Numeric(3, 1), default=7.0)
    end_date = Column(Date, nullable=True)
    status = Column(String(30), default="active")
    ingest_job_id = Column(String(200), nullable=True)
    ingest_status = Column(String(30), default="pending")
    plan_status = Column(String(30), default="pending")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    documents = relationship("SubjectDocument", back_populates="subject", cascade="all, delete-orphan")
    free_slots = relationship("SubjectFreeSlot", back_populates="subject", cascade="all, delete-orphan")


class SubjectDocument(Base):
    __tablename__ = "subject_documents"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("study_subjects.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_size = Column(String(50), nullable=True)
    mime_type = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    subject = relationship("StudySubject", back_populates="documents")


class SubjectFreeSlot(Base):
    __tablename__ = "subject_free_slots"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("study_subjects.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(String(10), nullable=False)
    time_slot = Column(String(10), nullable=False)

    __table_args__ = (
        UniqueConstraint("subject_id", "day_of_week", "time_slot"),
    )

    subject = relationship("StudySubject", back_populates="free_slots")
