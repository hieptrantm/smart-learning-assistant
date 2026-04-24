from sqlalchemy import Column, Integer, String, Date, DateTime, Text, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("study_subjects.id", ondelete="CASCADE"), nullable=False)
    checkpoint_node_id = Column(String(200), nullable=True)
    session_date = Column(Date, nullable=False)
    start_time = Column(String(10), nullable=False)
    end_time = Column(String(10), nullable=False)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    calendar_event_id = Column(String(200), nullable=True)
    status = Column(String(30), default="scheduled")
    learning_status = Column(String(30), default="not_started")
    score = Column(Numeric(3, 1), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    plan = relationship("StudyPlan", back_populates="sessions")
