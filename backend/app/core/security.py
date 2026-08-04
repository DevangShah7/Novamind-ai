from datetime import datetime, timedelta
from typing import Optional, Any, Mapping
# Use PyJWT directly. python-jose's jwt module is a PyJWT fork that doesn't
# expose PyJWTError at the top level, so callers that want `jwt.PyJWTError`
# (this file's decode_access_token) get the canonical PyJWT exception
# hierarchy. We keep python-jose installed because it's a transitive dep
# of passlib[bcrypt] on some platforms, but we don't depend on its API.
import jwt  # PyJWT
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(_truncate(plain_password), hashed_password)

def get_password_hash(password):
    return pwd_context.hash(_truncate(password))

def _truncate(password: str) -> str:
    # bcrypt has a hard 72-byte limit. passlib 1.7.4 + bcrypt >= 4 raise
    # rather than silently truncate. Truncate ourselves so any caller
    # can pass long passwords without crashing the auth flow.
    if password is None:
        return ""
    encoded = password.encode("utf-8")
    return encoded[:72].decode("utf-8", errors="ignore")

def create_access_token(
    data: Optional[Mapping[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
    subject: Optional[str] = None,
    extra_claims: Optional[Mapping[str, Any]] = None,
):
    """Mint a signed HS256 access token.

    `extra_claims` lets callers add non-standard claims (e.g. `tv` for
    token-version) without having to know the internal `data` shape.
    Reserved claim keys (`sub`, `exp`) set via `extra_claims` will be
    ignored — `subject` and `expires_delta` are the supported paths.
    """
    to_encode: dict = dict(data or {})
    if subject is not None and "sub" not in to_encode:
        to_encode["sub"] = subject
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    if extra_claims:
        for k, v in extra_claims.items():
            if k in ("sub", "exp"):
                continue  # never let callers override these
            to_encode[k] = v
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        return None