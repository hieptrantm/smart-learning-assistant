from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class SubjectMessage(Base):
    __tablename__ = "subject_messages"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("study_subjects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    subject = relationship("StudySubject", back_populates="messages")
