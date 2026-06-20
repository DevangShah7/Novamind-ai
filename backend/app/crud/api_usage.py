from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.api_usage import ApiUsage


def create_api_usage(
    db: Session,
    *,
    endpoint: str,
    method: str,
    status_code: int,
    user_id: Optional[int] = None,
    api_key_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    response_time_ms: Optional[float] = None,
    tokens_used: Optional[int] = None,
    model_used: Optional[str] = None
) -> ApiUsage:
    """Create a new API usage record"""
    db_obj = ApiUsage(
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        user_id=user_id,
        api_key_id=api_key_id,
        ip_address=ip_address,
        user_agent=user_agent,
        response_time_ms=response_time_ms,
        tokens_used=tokens_used,
        model_used=model_used
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_api_usage_by_user(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 100
) -> List[ApiUsage]:
    """Get API usage records for a specific user"""
    return (
        db.query(ApiUsage)
        .filter(ApiUsage.user_id == user_id)
        .order_by(desc(ApiUsage.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_api_usage_by_api_key(
    db: Session,
    api_key_id: int,
    skip: int = 0,
    limit: int = 100
) -> List[ApiUsage]:
    """Get API usage records for a specific API key"""
    return (
        db.query(ApiUsage)
        .filter(ApiUsage.api_key_id == api_key_id)
        .order_by(desc(ApiUsage.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_recent_api_usage(
    db: Session,
    skip: int = 0,
    limit: int = 100
) -> List[ApiUsage]:
    """Get recent API usage records across all users"""
    return (
        db.query(ApiUsage)
        .order_by(desc(ApiUsage.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )