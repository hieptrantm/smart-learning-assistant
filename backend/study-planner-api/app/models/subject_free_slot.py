from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


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
