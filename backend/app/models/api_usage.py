from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class ApiUsage(Base):
    __tablename__ = "api_usage"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign key to user (nullable for anonymous/IP-based tracking)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user = relationship("User", back_populates="api_usage")

    # API key used (if any)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=True, index=True)
    api_key = relationship("ApiKey", back_populates="usage_logs")

    # Request details
    endpoint = Column(String, nullable=False, index=True)
    method = Column(String, nullable=False)  # GET, POST, PUT, DELETE, etc.
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)

    # Response details
    status_code = Column(Integer, nullable=False, index=True)
    response_time_ms = Column(Float, nullable=True)  # Response time in milliseconds

    # AI-specific metrics (for AI endpoints)
    tokens_used = Column(Integer, nullable=True)
    model_used = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)