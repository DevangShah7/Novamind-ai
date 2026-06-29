from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.crud import api_key as api_key_crud

router = APIRouter()


@router.post("/", response_model=schemas.ApiKeyCreateResponse)
def create_api_key(
    *,
    db: Session = Depends(deps.get_db),
    api_key_in: schemas.ApiKeyCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """Create a new API key for the current user.

    The full secret value is returned **once** in the response. Store it
    somewhere safe — subsequent reads of the key will return it masked.
    """
    api_key = crud.api_key.create_api_key(db, obj_in=api_key_in, user_id=current_user.id)
    return api_key


@router.get("/", response_model=List[schemas.ApiKeyInDBBase])
def read_api_keys(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """List API keys for the current user."""
    api_keys = crud.api_key.get_api_keys_by_user(
        db, user_id=current_user.id, skip=skip, limit=limit
    )
    return api_keys


@router.get("/{key_id}", response_model=schemas.ApiKeyInDBBase)
def read_api_key(
    *,
    db: Session = Depends(deps.get_db),
    key_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    api_key = crud.api_key.get_api_key(db, key_id=key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return api_key


@router.put("/{key_id}", response_model=schemas.ApiKeyInDBBase)
def update_api_key(
    *,
    db: Session = Depends(deps.get_db),
    key_id: int,
    api_key_in: schemas.ApiKeyUpdate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    api_key = crud.api_key.get_api_key(db, key_id=key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return crud.api_key.update_api_key(db, db_obj=api_key, obj_in=api_key_in)


@router.delete("/{key_id}", response_model=schemas.ApiKeyInDBBase)
def delete_api_key(
    *,
    db: Session = Depends(deps.get_db),
    key_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    api_key = crud.api_key.get_api_key(db, key_id=key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return crud.api_key.delete_api_key(db, key_id=key_id)


@router.post("/{key_id}/rotate", response_model=schemas.ApiKeyCreateResponse)
def rotate_api_key(
    *,
    db: Session = Depends(deps.get_db),
    key_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """Issue a new secret value for an existing key. Old secret stops working."""
    api_key = crud.api_key.get_api_key(db, key_id=key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    rotated = api_key_crud.rotate_api_key(db, key_id=key_id)
    return rotated


@router.post("/{key_id}/validate", response_model=dict)
def validate_api_key(
    *,
    db: Session = Depends(deps.get_db),
    key_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    api_key = crud.api_key.get_api_key(db, key_id=key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    is_valid = (
        api_key.is_active
        and not api_key.is_disabled
        and (not api_key.expires_at or api_key.expires_at >= datetime.utcnow())
    )
    return {
        "valid": is_valid,
        "key_id": api_key.id,
        "name": api_key.name,
        "expires_at": api_key.expires_at,
        "is_disabled": api_key.is_disabled,
        "usage_count": api_key.usage_count,
        "last_used_at": api_key.last_used_at,
        "monthly_request_count": api_key.monthly_request_count,
        "monthly_token_count": api_key.monthly_token_count,
    }


@router.get("/{key_id}/usage", response_model=List[schemas.ApiUsage])
def read_api_key_usage(
    *,
    db: Session = Depends(deps.get_db),
    key_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    api_key = crud.api_key.get_api_key(db, key_id=key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return crud.api_usage.get_api_usage_by_api_key(
        db, api_key_id=key_id, skip=skip, limit=limit
    )


@router.get("/usage", response_model=List[schemas.ApiUsage])
def read_user_api_usage(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    return crud.api_usage.get_api_usage_by_user(
        db, user_id=current_user.id, skip=skip, limit=limit
    )


@router.get("/usage/summary")
def read_user_usage_summary(
    *,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    from sqlalchemy import func

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today.replace(day=1)

    total_usage = db.query(func.count(models.ApiUsage.id)).filter(
        models.ApiUsage.user_id == current_user.id
    ).scalar() or 0

    today_usage = db.query(func.count(models.ApiUsage.id)).filter(
        models.ApiUsage.user_id == current_user.id,
        models.ApiUsage.created_at >= today,
    ).scalar() or 0

    month_usage = db.query(func.count(models.ApiUsage.id)).filter(
        models.ApiUsage.user_id == current_user.id,
        models.ApiUsage.created_at >= month_start,
    ).scalar() or 0

    total_tokens = db.query(func.sum(models.ApiUsage.tokens_used)).filter(
        models.ApiUsage.user_id == current_user.id,
        models.ApiUsage.tokens_used.isnot(None),
    ).scalar() or 0

    today_tokens = db.query(func.sum(models.ApiUsage.tokens_used)).filter(
        models.ApiUsage.user_id == current_user.id,
        models.ApiUsage.created_at >= today,
        models.ApiUsage.tokens_used.isnot(None),
    ).scalar() or 0

    month_tokens = db.query(func.sum(models.ApiUsage.tokens_used)).filter(
        models.ApiUsage.user_id == current_user.id,
        models.ApiUsage.created_at >= month_start,
        models.ApiUsage.tokens_used.isnot(None),
    ).scalar() or 0

    endpoint_stats = db.query(
        models.ApiUsage.endpoint,
        func.count(models.ApiUsage.id).label('count'),
    ).filter(
        models.ApiUsage.user_id == current_user.id
    ).group_by(
        models.ApiUsage.endpoint
    ).order_by(
        func.count(models.ApiUsage.id).desc()
    ).limit(10).all()

    avg_response_time = db.query(func.avg(models.ApiUsage.response_time_ms)).filter(
        models.ApiUsage.user_id == current_user.id,
        models.ApiUsage.response_time_ms.isnot(None),
    ).scalar() or 0

    return {
        "total_requests": int(total_usage),
        "today_requests": int(today_usage),
        "month_requests": int(month_usage),
        "total_tokens_used": int(total_tokens),
        "today_tokens_used": int(today_tokens),
        "month_tokens_used": int(month_tokens),
        "average_response_time_ms": round(float(avg_response_time), 2),
        "top_endpoints": [
            {"endpoint": endpoint, "count": count}
            for endpoint, count in endpoint_stats
        ],
    }