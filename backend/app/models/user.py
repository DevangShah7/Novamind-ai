from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)  # nullable for OAuth-only users
    username = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)  # nullable for OAuth-only users
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)

    # OAuth fields
    google_id = Column(String, unique=True, index=True, nullable=True)
    avatar_url = Column(String, nullable=True)

    # Profile & Preferences
    full_name = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    preferences = Column(JSON, nullable=True)  # Store user preferences, AI settings, etc.

    # Usage & Analytics
    total_chats = Column(Integer, default=0)
    total_messages = Column(Integer, default=0)
    last_active = Column(DateTime(timezone=True), onupdate=func.now())

    # API Keys
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")

    # API Usage
    api_usage = relationship("ApiUsage", back_populates="user", cascade="all, delete-orphan")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())