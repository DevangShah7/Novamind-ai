from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import re

# Password rules — keep this in sync with the dev mailer copy and the
# frontend password strength meter. Pydantic 1.10's `min_length` only
# checks length; the validator enforces the composition rule.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
_PASSWORD_COMPOSITION = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).+$")


def _validate_password(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
        )
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password must be at most {PASSWORD_MAX_LENGTH} characters"
        )
    if not _PASSWORD_COMPOSITION.match(value):
        raise ValueError(
            "Password must contain at least one letter and one digit"
        )
    return value


class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    is_admin: bool = False

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    is_admin: bool = False

    @validator("password", always=True)
    def _password_rules(cls, v: str) -> str:
        return _validate_password(v)

    @validator("password", always=True)
    def _password_not_email_local_part(cls, v: str, values: Dict[str, Any]) -> str:
        # Reject "password == user@gmail.com" style trivially guessable
        # passwords. Only checked when email is present.
        email = values.get("email")
        if email and isinstance(email, str) and v.lower() == email.lower():
            raise ValueError("Password must not match your email")
        return v


class UserAdminCreate(BaseModel):
    """Body for `POST /admin/` — admin-provisioned user creation.

    Re-uses the same password rules as the public `UserCreate` flow
    (8+ chars, letter + digit, not equal to email) so admins can't
    create weak accounts. The `is_admin` flag is exposed so admins
    can promote a colleague without a second round-trip. Email
    verification is intentionally NOT enforced here — the admin
    router in `endpoints/admin.py` flips `is_verified=True` on the
    resulting user so they can log in immediately.
    """
    email: EmailStr
    password: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    is_admin: bool = False

    @validator("password", always=True)
    def _password_rules(cls, v: str) -> str:
        return _validate_password(v)

    @validator("password", always=True)
    def _password_not_email_local_part(cls, v: str, values: Dict[str, Any]) -> str:
        email = values.get("email")
        if email and isinstance(email, str) and v.lower() == email.lower():
            raise ValueError("Password must not match your email")
        return v


class ResendVerificationRequest(BaseModel):
    """Body for /auth/resend-verification. The endpoint is intentionally
    unauthenticated: a user who just signed up doesn't have a JWT yet,
    and they need to be able to ask for the email to be re-sent before
    they click the link. Rate limiting is enforced at the IP level by
    the global RATELIMIT_AUTH_PER_MIN middleware (see main.py), and the
    handler returns the same response whether the email is registered
    or not so attackers can't enumerate accounts.
    """
    email: EmailStr


class EmailVerifyRequest(BaseModel):
    token: str = Field(..., min_length=8, max_length=512)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=8, max_length=512)
    new_password: str

    @validator("new_password", always=True)
    def _new_password_rules(cls, v: str) -> str:
        return _validate_password(v)


class MessageResponse(BaseModel):
    """Generic success envelope used by /verify-email, /forgot-password,
    /reset-password, /logout, etc."""
    message: str


class GoogleAuthRequest(BaseModel):
    token: str  # Google ID token

class GoogleAuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    avatar_url: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    is_admin: Optional[bool] = None

class UserInDBBase(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    is_admin: bool

    class Config:
        orm_mode = True

class UserInDB(UserInDBBase):
    hashed_password: Optional[str] = None
    google_id: Optional[str] = None

class User(UserInDBBase):
    pass

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None
    scopes: List[str] = []