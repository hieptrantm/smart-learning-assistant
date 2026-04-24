from sqlalchemy import Column, String, Integer, TIMESTAMP, Boolean, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    email_verified = Column(Boolean, default=False)
    last_login = Column(TIMESTAMP, nullable=True)

    providers = relationship("AuthProvider", back_populates="user", cascade="all, delete")
    detects = relationship("Detect", backref="user", cascade="all, delete-orphan")
