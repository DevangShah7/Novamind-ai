from typing import Any, List
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps

router = APIRouter()


@router.post("/", response_model=schemas.ApiKeyCreateResponse)
def create_api_key(
    *,
    db: Session = Depends(deps.get_db),
    api_key_in: schemas.ApiKeyCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create new API key for current user.
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
    """
    Retrieve API keys for current user.
    """
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
    """
    Get API key by ID.
    """
    api_key = crud.api_key.get_api_key(db, key_id=key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.user_id != current_user.id:
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
    """
    Update an API key.
    """
    api_key = crud.api_key.get_api_key(db, key_id=key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    api_key = crud.api_key.update_api_key(db, db_obj=api_key, obj_in=api_key_in)
    return api_key


@router.delete("/{key_id}", response_model=schemas.ApiKeyInDBBase)
def delete_api_key(
    *,
    db: Session = Depends(deps.get_db),
    key_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete an API key.
    """
    api_key = crud.api_key.get_api_key(db, key_id=key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    api_key = crud.api_key.delete_api_key(db, key_id=key_id)
    return api_key


@router.post("/{key_id}/validate", response_model=dict)
def validate_api_key(
    *,
    db: Session = Depends(deps.get_db),
    key_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Validate an API key by checking if it exists and is active.
    """
    api_key = crud.api_key.get_api_key(db, key_id=key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    is_valid = api_key.is_active and (not api_key.expires_at or api_key.expires_at >= datetime.utcnow())
    return {
        "valid": is_valid,
        "key_id": api_key.id,
        "name": api_key.name,
        "expires_at": api_key.expires_at,
        "usage_count": api_key.usage_count,
        "last_used_at": api_key.last_used_at
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
    """
    Get usage statistics for a specific API key.
    """
    api_key = crud.api_key.get_api_key(db, key_id=key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    if api_key.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    usage = crud.api_usage.get_api_usage_by_api_key(
        db, api_key_id=key_id, skip=skip, limit=limit
    )
    return usage


@router.get("/usage", response_model=List[schemas.ApiUsage])
def read_user_api_usage(
    *,
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get usage statistics for all API keys of the current user.
    """
    usage = crud.api_usage.get_api_usage_by_user(
        db, user_id=current_user.id, skip=skip, limit=limit
    )
    return usage


@router.get("/usage/summary")
def read_user_usage_summary(
    *,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get usage summary statistics for the current user.
    """
    from sqlalchemy import func
    from datetime import datetime, timedelta

    # Get today's date at midnight
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Total usage
    total_usage = db.query(func.count(models.ApiUsage.id)).filter(
        models.ApiUsage.user_id == current_user.id
    ).scalar()

    # Today's usage
    today_usage = db.query(func.count(models.ApiUsage.id)).filter(
        models.ApiUsage.user_id == current_user.id,
        models.ApiUsage.created_at >= today
    ).scalar()

    # Total tokens used (for AI endpoints)
    total_tokens = db.query(func.sum(models.ApiUsage.tokens_used)).filter(
        models.ApiUsage.user_id == current_user.id,
        models.ApiUsage.tokens_used.isnot(None)
    ).scalar() or 0

    # Today's tokens used
    today_tokens = db.query(func.sum(models.ApiUsage.tokens_used)).filter(
        models.ApiUsage.user_id == current_user.id,
        models.ApiUsage.created_at >= today,
        models.ApiUsage.tokens_used.isnot(None)
    ).scalar() or 0

    # Usage by endpoint
    endpoint_stats = db.query(
        models.ApiUsage.endpoint,
        func.count(models.ApiUsage.id).label('count')
    ).filter(
        models.ApiUsage.user_id == current_user.id
    ).group_by(
        models.ApiUsage.endpoint
    ).order_by(
        func.count(models.ApiUsage.id).desc()
    ).limit(10).all()

    # Average response time
    avg_response_time = db.query(func.avg(models.ApiUsage.response_time_ms)).filter(
        models.ApiUsage.user_id == current_user.id,
        models.ApiUsage.response_time_ms.isnot(None)
    ).scalar() or 0

    return {
        "total_requests": total_usage,
        "today_requests": today_usage,
        "total_tokens_used": int(total_tokens),
        "today_tokens_used": int(today_tokens),
        "average_response_time_ms": round(avg_response_time, 2),
        "top_endpoints": [
            {"endpoint": endpoint, "count": count}
            for endpoint, count in endpoint_stats
        ]
    }