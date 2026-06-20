import secrets
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyUpdate


def generate_api_key() -> str:
    """Generate a secure random API key"""
    return secrets.token_urlsafe(32)


def get_api_key(db: Session, key_id: int) -> Optional[ApiKey]:
    return db.query(ApiKey).filter(ApiKey.id == key_id).first()


def get_api_key_by_key(db: Session, key: str) -> Optional[ApiKey]:
    return db.query(ApiKey).filter(ApiKey.key == key).first()


def get_api_keys_by_user(
    db: Session, user_id: int, skip: int = 0, limit: int = 100
) -> List[ApiKey]:
    return (
        db.query(ApiKey)
        .filter(ApiKey.user_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_api_keys(
    db: Session, skip: int = 0, limit: int = 100
) -> List[ApiKey]:
    return db.query(ApiKey).offset(skip).limit(limit).all()


def create_api_key(
    db: Session, *, obj_in: ApiKeyCreate, user_id: int
) -> ApiKey:
    key = generate_api_key()
    db_obj = ApiKey(
        key=key,
        name=obj_in.name,
        description=obj_in.description,
        expires_at=obj_in.expires_at,
        user_id=user_id,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_api_key(
    db: Session, *, db_obj: ApiKey, obj_in: ApiKeyUpdate
) -> ApiKey:
    update_data = obj_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_api_key(db: Session, *, key_id: int) -> Optional[ApiKey]:
    obj = db.query(ApiKey).get(key_id)
    if obj:
        db.delete(obj)
        db.commit()
    return obj


def increment_api_key_usage(db: Session, key: str) -> Optional[ApiKey]:
    """Increment usage count and update last used timestamp"""
    from datetime import datetime

    api_key = get_api_key_by_key(db, key)
    if api_key:
        api_key.usage_count += 1
        api_key.last_used_at = datetime.utcnow()
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
    return api_key