"""
User self-service endpoints.

These complement the admin `/users/...` endpoints. They're mounted at
`/api/v1/users` and exist so the frontend doesn't have to base64-decode
the JWT to figure out "who am I" — see `web/lib/auth.ts`.

Two endpoints:
  - `GET  /users/me`        — return the current user
  - `POST /users/me/change-password` — rotate the password, return 200
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.core.security import verify_password, get_password_hash
from app.crud.user import get_user
from app.models.user import User
from app.schemas.user import User as UserSchema

router = APIRouter()


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordResponse(BaseModel):
    message: str = "Password changed successfully. Please sign in again."


@router.get("/me", response_model=UserSchema)
def get_me(current_user: User = Depends(deps.get_current_active_user)):
    """Return the authenticated user. Used by the frontend on app boot
    to populate the session without trusting client-side JWT decoding."""
    return current_user


@router.post("/me/change-password", response_model=ChangePasswordResponse)
def change_my_password(
    body: ChangePasswordRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Rotate the authenticated user's password.

    Refuses if `current_password` doesn't match. On success, bumps
    `token_version` so all other JWTs for this user become invalid
    (forced re-login on other devices).
    """
    user = get_user(db, current_user.id)
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account doesn't have a password set (use Google login).",
        )
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password",
        )
    user.hashed_password = get_password_hash(body.new_password)
    # Bump token_version if the column exists; this invalidates other
    # sessions for the same user. We swallow the AttributeError so the
    # endpoint still works on an old DB that hasn't been migrated yet.
    if hasattr(user, "token_version"):
        user.token_version = (user.token_version or 0) + 1
    db.commit()
    return ChangePasswordResponse()
