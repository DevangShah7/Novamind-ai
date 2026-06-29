from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core import security
from app.core.config import settings
from app.core.rate_limiting import create_auth_rate_limiter as auth_rate_limiter, create_default_rate_limiter as default_rate_limiter
from app.core.database import SessionLocal
from app.models import user, api_key
from app.schemas.user import TokenData
from app.crud import user as user_crud, api_key as api_key_crud
from app.crud.user import get_user_by_email

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

def get_api_key_header(
    x_api_key: Optional[str] = Header(None),
) -> Optional[str]:
    """Extract API key from X-API-Key header"""
    return x_api_key


def get_current_user_from_api_key(
    db: Session = Depends(get_db),
    api_key: Optional[str] = Depends(get_api_key_header),
) -> Optional[user.User]:
    """
    Get current user from API key.
    """
    if not api_key:
        return None

    api_key_obj = api_key_crud.get_api_key_by_key(db, api_key=api_key)
    if not api_key_obj or not api_key_obj.is_active:
        return None

    # Update usage statistics
    api_key_crud.increment_api_key_usage(db, api_key=api_key)

    return api_key_obj.user


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
    api_key_user: Optional[user.User] = Depends(get_current_user_from_api_key),
) -> user.User:
    # If API key authentication succeeded, return that user
    if api_key_user:
        return api_key_user

    # Otherwise, fall back to JWT authentication
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except (jwt.JWTError, ValidationError):
        raise credentials_exception
    user = get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(
    current_user: user.User = Depends(get_current_user),
) -> user.User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_current_active_admin(
    current_user: user.User = Depends(get_current_active_user),
) -> user.User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user


async def rate_limit_dependency(
    request: Request,
    _: bool = Depends(auth_rate_limiter if False else default_rate_limiter)  # Placeholder - actual implementation would be in middleware
):
    """
    Rate limiting dependency.
    This is a placeholder - actual rate limiting would be implemented as middleware.
    """
    pass


def get_current_user_from_api_key(
    db: Session = Depends(get_db),
    api_key: Optional[str] = Depends(get_api_key_header),
) -> Optional[user.User]:
    """
    Get current user from API key.
    """
    if not api_key:
        return None

    api_key_obj = api_key_crud.get_api_key_by_key(db, api_key=api_key)
    if not api_key_obj or not api_key_obj.is_active:
        return None

    # Update usage statistics
    api_key_crud.increment_api_key_usage(db, api_key=api_key)

    return api_key_obj.user