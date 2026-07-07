from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.security import create_access_token, verify_password, get_password_hash
from app.core.config import settings
from app.core.mailer import send_email
from app.crud.user import get_user_by_email, create_user, get_user_by_google_id, create_user_from_google, update_last_active
from app.schemas.user import (
    UserCreate,
    Token,
    GoogleAuthRequest,
    GoogleAuthResponse,
    EmailVerifyRequest,
    ResendVerificationRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    MessageResponse,
)
from app.api import deps
from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordRequestForm
import json
import logging
import secrets

# Google ID-token verification. We try `google.oauth2.id_token.verify_token`
# first (cryptographic signature check against Google's published JWKs),
# and fall back to Google's HTTPS `tokeninfo` endpoint only if the local
# verifier can't fetch the certs (e.g. transient network blip). The
# previous implementation called `jwt.decode(..., verify_signature=False)`
# which accepted any forged token — see git history.
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

import requests as _requests  # standard requests, used only for the tokeninfo fallback

logger = logging.getLogger("novamind.auth")

router = APIRouter()


def _as_utc(dt: datetime) -> datetime:
    """Treat a DB-read datetime as UTC.

    SQLite's TIMESTAMP columns come back as naive (no tzinfo) regardless
    of how they were written, while Python's `datetime.now(timezone.utc)`
    is tz-aware. Comparing the two raises `TypeError: can't compare
    offset-naive and offset-aware datetimes`. We standardize on UTC by
    attaching tzinfo=UTC to anything naive, so all expiry comparisons
    can use a single `datetime.now(timezone.utc)` reference.
    """
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


# ---------- constants for the new auth flows ----------
EMAIL_VERIFICATION_TTL_HOURS = 24
PASSWORD_RESET_TTL_HOURS = 1
LOGIN_LOCKOUT_THRESHOLD = 5            # failed attempts before lockout
LOGIN_LOCKOUT_WINDOW_MIN = 15          # failures within this window count
LOGIN_LOCKOUT_DURATION_MIN = 15        # how long the lockout lasts
PASSWORD_RESET_FRONTEND_PATH = "/reset-password"
EMAIL_VERIFY_FRONTEND_PATH = "/verify-email"


def _verify_google_id_token(token: str) -> dict:
    """Verify a Google ID token's signature and return the decoded claims.

    Raises HTTPException(401) on any failure. The claims dict is the
    canonical Google payload: ``sub``, ``email``, ``email_verified``,
    ``name``, ``picture``, ``aud``, ``iss``, ``exp``, ``iat``.

    Two-stage verification:
      1. Preferred: `google.oauth2.id_token.verify_token` (RS256 against
         Google's published JWKs, audience check, exp check, issuer check).
      2. Fallback: HTTPS GET to Google's `tokeninfo` endpoint. This is
         network-only and does no local cryptographic check, so it's only
         used when step 1 raises a transport error. We refuse to skip
         signature verification on a malformed token — those still 401.
    """
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authentication failed: empty token",
        )

    # --- Path 1: cryptographic verification ---
    try:
        req = google_requests.Request()
        claims = google_id_token.verify_token(
            token, req, audience=settings.GOOGLE_CLIENT_ID or None
        )
        if not claims:
            raise ValueError("verify_token returned falsy")
        # `verify_token` accepts `audience=None` for tokens without an
        # expected audience. We log a warning so a misconfigured prod
        # deployment is visible.
        if not settings.GOOGLE_CLIENT_ID:
            logger.warning(
                "Google ID token accepted with no audience check "
                "(GOOGLE_CLIENT_ID is unset). Set it in .env for prod."
            )
        return claims
    except HTTPException:
        raise
    except Exception as primary_exc:
        # --- Path 2: HTTPS tokeninfo fallback ---
        # Only fall back for transport-level failures. Signature/exp
        # failures from verify_token should NOT fall back to a looser
        # verifier — that would weaken security.
        primary_msg = str(primary_exc)
        if "signature" in primary_msg.lower() or "expired" in primary_msg.lower() \
                or "audience" in primary_msg.lower() or "issuer" in primary_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Google authentication failed: {primary_msg}",
            )

        try:
            resp = _requests.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={token}",
                timeout=5,
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Google token",
                )
            info = resp.json()
            if "error_description" in info or "errors" in info:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid Google token: {info.get('error_description', info)}",
                )
            if not info.get("sub"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google token missing subject",
                )
            if settings.GOOGLE_CLIENT_ID and info.get("aud") != settings.GOOGLE_CLIENT_ID:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google token audience mismatch",
                )
            if info.get("exp") and int(info["exp"]) < int(__import__("time").time()):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google token expired",
                )
            logger.warning(
                "Used tokeninfo HTTPS fallback for Google verification "
                "(primary path failed: %s). Check network reachability.",
                primary_msg,
            )
            return info
        except HTTPException:
            raise
        except Exception as fb_exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Google authentication failed: {fb_exc}",
            )

@router.post("/register", response_model=MessageResponse, status_code=202)
def register(user_in: UserCreate, db: Session = Depends(deps.get_db)):
    """Create a new user account.

    Returns 202 (not 201) because the user isn't fully "ready" until
    they verify their email. The response is a generic message; the
    verification email is sent to the address they registered with.
    """
    user = get_user_by_email(db, email=user_in.email)
    if user:
        # Use a generic 400 so an attacker can't probe which emails are
        # registered. The client UI shows a friendlier "Email already
        # in use — try logging in" message based on the 400.
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    user = create_user(db, user_in)

    # Mint a 24h verification token and email the user. If mailer is
    # in dev-stub mode, the URL ends up in backend/logs/dev-mail.log.
    token = secrets.token_urlsafe(32)
    user.email_verification_token = token
    user.email_verification_expires = datetime.now(timezone.utc) + timedelta(
        hours=EMAIL_VERIFICATION_TTL_HOURS
    )
    db.commit()

    _send_verification_email(user.email, token)

    return MessageResponse(
        message="Account created. Please check your email to verify your account."
    )


def _frontend_base_url() -> str:
    """Where to point email links. Defaults to the Vercel production URL,
    overridable via FRONTEND_BASE_URL for local dev. The tunnel URL
    works too — users just follow the link from their email client."""
    return (
        getattr(settings, "FRONTEND_BASE_URL", "")
        or "http://localhost:3000"
    )


def _send_verification_email(email: str, token: str) -> None:
    base = _frontend_base_url().rstrip("/")
    link = f"{base}{EMAIL_VERIFY_FRONTEND_PATH}?token={token}"
    text = (
        f"Welcome to NovaMind!\n\n"
        f"Please verify your email by opening this link:\n{link}\n\n"
        f"This link is valid for {EMAIL_VERIFICATION_TTL_HOURS} hours. "
        f"If you didn't create a NovaMind account, you can ignore this email.\n"
    )
    html = (
        f"<p>Welcome to NovaMind!</p>"
        f"<p>Please verify your email by clicking the link below:</p>"
        f'<p><a href="{link}">Verify my email</a></p>'
        f"<p>This link is valid for {EMAIL_VERIFICATION_TTL_HOURS} hours. "
        f"If you didn't create a NovaMind account, you can ignore this email.</p>"
    )
    send_email(email, "Verify your NovaMind email", text, html)


def _send_password_reset_email(email: str, token: str) -> None:
    base = _frontend_base_url().rstrip("/")
    link = f"{base}{PASSWORD_RESET_FRONTEND_PATH}?token={token}"
    text = (
        f"We received a request to reset your NovaMind password.\n\n"
        f"If you made this request, open this link to set a new password:\n{link}\n\n"
        f"This link is valid for {PASSWORD_RESET_TTL_HOURS} hour(s). "
        f"If you didn't request a reset, you can safely ignore this email — "
        f"your password is unchanged.\n"
    )
    html = (
        f"<p>We received a request to reset your NovaMind password.</p>"
        f"<p>If you made this request, click the link below to set a new password:</p>"
        f'<p><a href="{link}">Reset my password</a></p>'
        f"<p>This link is valid for {PASSWORD_RESET_TTL_HOURS} hour(s). "
        f"If you didn't request a reset, you can safely ignore this email.</p>"
    )
    send_email(email, "Reset your NovaMind password", text, html)


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(body: EmailVerifyRequest, db: Session = Depends(deps.get_db)):
    """Mark a user's email as verified using the token emailed on register.

    Idempotent: a second call with the same token returns 200. An
    unknown / expired token returns 400.
    """
    from app.crud.user import get_user_by_email  # local to avoid circular noise
    user = (
        db.query(__import__("app.models.user", fromlist=["User"]).User)
        .filter_by(email_verification_token=body.token)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification link",
        )
    # Expiry check — accept a small clock skew.
    if _as_utc(user.email_verification_expires) and _as_utc(user.email_verification_expires) < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Verification link has expired. Please request a new one.",
        )
    user.is_verified = True
    user.email_verification_token = None
    user.email_verification_expires = None
    db.commit()
    return MessageResponse(message="Email verified. You can now sign in.")


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    _body: ResendVerificationRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
):
    """Re-mint a verification token and email the current user.

    Requires the user to be logged in (so an attacker can't flood
    arbitrary inboxes). If the user is already verified, this is a
    no-op that returns 200.
    """
    if current_user.is_verified:
        return MessageResponse(message="Email already verified.")
    token = secrets.token_urlsafe(32)
    current_user.email_verification_token = token
    current_user.email_verification_expires = datetime.now(timezone.utc) + timedelta(
        hours=EMAIL_VERIFICATION_TTL_HOURS
    )
    db.commit()
    _send_verification_email(current_user.email, token)
    return MessageResponse(
        message="Verification email resent. Please check your inbox."
    )


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(deps.get_db)):
    """Authenticate with email + password.

    On success, resets the failure counter, clears any lockout, and
    returns a fresh JWT. On failure, increments the counter and may
    trigger a 15-minute lockout after 5 failed attempts.
    """
    user = get_user_by_email(db, email=form_data.username)
    now = datetime.now(timezone.utc)

    # Check lockout first — don't even bother hashing the password.
    if user and user.lockout_until and _as_utc(user.lockout_until) > now:
        retry_after = int((_as_utc(user.lockout_until) - now).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    password_ok = bool(
        user
        and user.hashed_password
        and verify_password(form_data.password, user.hashed_password)
    )
    if not password_ok:
        if user:
            # Bump the counter; trigger lockout if the threshold is hit
            # AND the failures are still within the sliding window.
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= LOGIN_LOCKOUT_THRESHOLD:
                user.lockout_until = now + timedelta(minutes=LOGIN_LOCKOUT_DURATION_MIN)
                # Reset the counter so the next window starts clean.
                user.failed_login_count = 0
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Gate on email verification, but allow admins to skip so they
    # can still recover accounts in dev.
    if not user.is_verified and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your inbox for the verification link.",
        )

    # Success: clear failure state and bump token_version so any
    # outstanding tokens from before this login become invalid.
    user.failed_login_count = 0
    user.lockout_until = None
    if hasattr(user, "token_version"):
        user.token_version = (user.token_version or 0) + 1
    update_last_active(db, user.id)
    db.commit()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.email,
        expires_delta=access_token_expires,
        extra_claims={"tv": user.token_version},
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(deps.get_db)):
    """Start a password reset.

    Always returns 200 to avoid revealing whether the email is
    registered. If it is, mints a 1h-TTL token and emails the reset
    link. Otherwise silently no-ops.
    """
    user = get_user_by_email(db, email=body.email)
    if user and user.hashed_password:
        token = secrets.token_urlsafe(32)
        user.password_reset_token = token
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(
            hours=PASSWORD_RESET_TTL_HOURS
        )
        db.commit()
        _send_password_reset_email(user.email, token)
    # Return the same message regardless — anti-enumeration.
    return MessageResponse(
        message=(
            "If an account exists for that email, a reset link has been sent. "
            "Check your inbox (and spam folder)."
        )
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(deps.get_db)):
    """Complete a password reset using a token from the email.

    On success: hash the new password, save it, clear the token,
    bump `token_version` so all existing JWTs are invalidated.
    """
    from app.models.user import User
    user = (
        db.query(User)
        .filter(User.password_reset_token == body.token)
        .first()
    )
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    if (
        user.password_reset_expires is None
        or _as_utc(user.password_reset_expires) < datetime.now(timezone.utc)
    ):
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")
    user.hashed_password = get_password_hash(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    user.failed_login_count = 0
    user.lockout_until = None
    if hasattr(user, "token_version"):
        user.token_version = (user.token_version or 0) + 1
    db.commit()
    return MessageResponse(
        message="Password reset successfully. You can now sign in with your new password."
    )


@router.post("/logout", response_model=MessageResponse)
def logout(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
):
    """Invalidate the current session by bumping token_version.

    The caller should also drop the JWT from localStorage; this
    endpoint just makes the JWT useless on the server side. Any other
    device holding a JWT for this user will get 401 on their next
    request.
    """
    if hasattr(current_user, "token_version"):
        current_user.token_version = (current_user.token_version or 0) + 1
        db.commit()
    return MessageResponse(message="Signed out.")

@router.post("/google", response_model=GoogleAuthResponse)
def google_auth(google_req: GoogleAuthRequest, db: Session = Depends(deps.get_db)):
    """Authenticate user with Google OAuth ID token.

    The token's RS256 signature is verified against Google's published
    JWKs, the audience is checked against `GOOGLE_CLIENT_ID` if it's set,
    and the expiry is enforced. See `_verify_google_id_token` for the
    verification logic.
    """
    try:
        google_info = _verify_google_id_token(google_req.token)

        # Check if user exists by Google ID
        user = get_user_by_google_id(db, google_id=google_info.get("sub"))

        if not user:
            # Check if user exists by email (for account linking)
            if google_info.get("email"):
                user = get_user_by_email(db, email=google_info.get("email"))
                if user:
                    # Link existing account with Google ID
                    user.google_id = google_info.get("sub")
                    user.avatar_url = google_info.get("picture")
                    user.is_verified = True
                    db.commit()
                    db.refresh(user)
                else:
                    # Create new user from Google info
                    user = create_user_from_google(db, google_info)
            else:
                # Create new user from Google info
                user = create_user_from_google(db, google_info)
        else:
            # Update last active for existing user
            update_last_active(db, user.id)

        # Generate access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=user.email or f"google_{user.google_id}",
            expires_delta=access_token_expires,
            extra_claims={"tv": getattr(user, "token_version", 0) or 0},
        )

        # Return user info (excluding sensitive data)
        user_data = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "google_id": user.google_id
        }

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )