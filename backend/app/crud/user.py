from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, GoogleAuthRequest, GoogleAuthResponse
from app.core.security import get_password_hash
from app.core.config import settings
import json
from datetime import datetime

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def get_user_by_google_id(db: Session, google_id: str):
    return db.query(User).filter(User.google_id == google_id).first()

def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=hashed_password,
        preferences=json.dumps({"theme": "light", "notifications": True})  # Default preferences
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_user_from_google(db: Session, google_info: dict):
    """Create a new user from Google OAuth info"""
    db_user = User(
        email=google_info.get("email"),
        username=google_info.get("email").split("@")[0] if google_info.get("email") else None,
        full_name=google_info.get("name"),
        google_id=google_info.get("sub"),
        avatar_url=google_info.get("picture"),
        is_verified=True if google_info.get("email_verified") else False,
        preferences=json.dumps({"theme": "light", "notifications": True})
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user: UserUpdate):
    db_user = get_user(db, user_id)
    if db_user:
        update_data = user.dict(exclude_unset=True)
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
        # Handle preferences JSON
        if "preferences" in update_data and isinstance(update_data["preferences"], dict):
            update_data["preferences"] = json.dumps(update_data["preferences"])
        for key, value in update_data.items():
            setattr(db_user, key, value)
        db.commit()
        db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int):
    db_user = get_user(db, user_id)
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user

def update_last_active(db: Session, user_id: int):
    """Update user's last active timestamp"""
    db_user = get_user(db, user_id)
    if db_user:
        db_user.last_active = datetime.utcnow()
        db.commit()
        db.refresh(db_user)
    return db_user


def count_admins(db: Session) -> int:
    """Count admin users"""
    return db.query(User).filter(User.is_admin == True).count()


def count_active(db: Session) -> int:
    """Count active users"""
    return db.query(User).filter(User.is_active == True).count()