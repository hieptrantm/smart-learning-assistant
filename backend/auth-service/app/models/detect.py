from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    TIMESTAMP,
    func,
)
from sqlalchemy.dialects.postgresql import BYTEA, ARRAY
from .user import Base

class Detect(Base):
    __tablename__ = "detects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    image_mime_type = Column(String(50))
    detected_ingredients = Column(ARRAY(Text))  # TEXT[] in PostgreSQL
    recommendation = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
