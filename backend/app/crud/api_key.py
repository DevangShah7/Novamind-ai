import secrets
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyUpdate


def generate_api_key() -> str:
    """Generate a secure random API key.

    Prefixed with ``nm_`` so developers can immediately tell NovaMind
    keys apart from keys of other providers when they're scrolling
    through env vars.
    """
    return "nm_" + secrets.token_urlsafe(32)


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
        ip_allowlist=obj_in.ip_allowlist,
        domain_allowlist=obj_in.domain_allowlist,
        tags=obj_in.tags,
        organization=obj_in.organization,
        monthly_token_limit=obj_in.monthly_token_limit,
        monthly_request_limit=obj_in.monthly_request_limit,
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
    """Increment usage count and update last used timestamp.

    Also keeps the developer-platform monthly counters rolling, so the
    portal can render them without an extra aggregation query.
    """
    api_key = get_api_key_by_key(db, key)
    if api_key:
        api_key.usage_count = (api_key.usage_count or 0) + 1
        api_key.monthly_request_count = (api_key.monthly_request_count or 0) + 1
        api_key.last_used_at = datetime.utcnow()
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
    return api_key


def is_api_key_callable(api_key_obj: ApiKey, client_ip: Optional[str] = None) -> bool:
    """Return True if the key may be used right now.

    A key is "callable" when it's active AND not disabled AND not expired
    AND (no IP allowlist OR client_ip matches). Domain allowlist is
    enforced elsewhere (caller passes Origin / Referer) — we can't validate
    it from the server-side without trusting the headers, so this helper
    just signals "should we bother even looking up the key?".
    """
    if not api_key_obj.is_active or api_key_obj.is_disabled:
        return False
    if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
        return False
    if api_key_obj.ip_allowlist and client_ip:
        # Imported lazily so unit tests don't pull ipaddress for nothing.
        import ipaddress
        try:
            client = ipaddress.ip_address(client_ip)
        except ValueError:
            return False
        ok = False
        for rule in api_key_obj.ip_allowlist:
            try:
                if "/" in rule:
                    if client in ipaddress.ip_network(rule, strict=False):
                        ok = True
                        break
                elif str(client) == rule:
                    ok = True
                    break
            except ValueError:
                continue
        if not ok:
            return False
    return True


def rotate_api_key(db: Session, *, key_id: int) -> Optional[ApiKey]:
    """Generate a new secret value while preserving the row + history."""
    api_key = get_api_key(db, key_id=key_id)
    if not api_key:
        return None
    api_key.key = generate_api_key()
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key