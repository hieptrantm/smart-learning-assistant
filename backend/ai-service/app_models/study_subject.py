from sqlalchemy import Column, Integer, String, Numeric, Date, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


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
    plans = relationship("StudyPlan", back_populates="subject", cascade="all, delete-orphan")
    messages = relationship("SubjectMessage", back_populates="subject", cascade="all, delete-orphan")
