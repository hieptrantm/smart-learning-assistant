from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class SubjectDocument(Base):
    __tablename__ = "subject_documents"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("study_subjects.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_size = Column(String(50), nullable=True)
    mime_type = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    subject = relationship("StudySubject", back_populates="documents")
