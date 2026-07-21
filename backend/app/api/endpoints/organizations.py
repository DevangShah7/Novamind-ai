"""
/v1/organizations — multi-tenant org + team management.

Three roles: owner > admin > member. Only owner/admin can add or remove
members; only owner can delete the org. The membership check is in
``_require_role``; endpoints declare the minimum role they accept.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.api.endpoints.v1_compat import get_user_from_api_key
from app.models import Organization, OrganizationMember, Team, TeamMember, User

router = APIRouter()

ROLE_RANK = {"member": 0, "admin": 1, "owner": 2}


# ---------- Pydantic ----------

class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    slug: Optional[str] = Field(None, min_length=2, max_length=40, pattern=r"^[a-z0-9-]+$")


class OrganizationOut(BaseModel):
    id: int
    name: str
    slug: str
    owner_id: int
    created_at: datetime
    role: str  # the requesting user's role in this org

    class Config:
        orm_mode = True


class MemberAdd(BaseModel):
    user_id: int
    role: str = Field("member", pattern=r"^(member|admin|owner)$")


class MemberOut(BaseModel):
    id: int
    user_id: int
    role: str
    created_at: datetime
    user_email: Optional[str] = None

    class Config:
        orm_mode = True


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    description: Optional[str] = None


class TeamOut(BaseModel):
    id: int
    organization_id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    member_count: int = 0

    class Config:
        orm_mode = True


# ---------- helpers ----------

def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "org"


def _get_membership(db: Session, org_id: int, user_id: int) -> Optional[OrganizationMember]:
    return (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == user_id)
        .first()
    )


def _require_role(db: Session, org_id: int, user_id: int, min_role: str) -> OrganizationMember:
    m = _get_membership(db, org_id, user_id)
    if not m:
        raise HTTPException(status_code=404, detail="organization not found")
    if ROLE_RANK.get(m.role, -1) < ROLE_RANK[min_role]:
        raise HTTPException(status_code=403, detail=f"requires {min_role} role")
    return m


def _to_org_out(org: Organization, role: str) -> Dict[str, Any]:
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "owner_id": org.owner_id,
        "created_at": org.created_at,
        "role": role,
    }


# ---------- orgs ----------

@router.get("/organizations", response_model=List[OrganizationOut])
def list_my_organizations(
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    rows = (
        db.query(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .filter(OrganizationMember.user_id == user.id)
        .order_by(Organization.created_at.desc())
        .all()
    )
    return [_to_org_out(org, role) for org, role in rows]


@router.post("/organizations", response_model=OrganizationOut)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    slug = payload.slug or _slugify(payload.name)
    # Defensive unique check (the DB has a unique constraint too, but
    # surfacing it as 400 instead of 500 is friendlier).
    if db.query(Organization).filter(Organization.slug == slug).first():
        raise HTTPException(status_code=400, detail=f"slug {slug!r} is taken")

    org = Organization(owner_id=user.id, name=payload.name, slug=slug)
    db.add(org)
    db.flush()  # so org.id is populated

    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(org)
    return _to_org_out(org, "owner")


@router.get("/organizations/{org_id}", response_model=OrganizationOut)
def get_organization(
    org_id: int,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="organization not found")
    m = _get_membership(db, org_id, user.id)
    if not m:
        raise HTTPException(status_code=403, detail="not a member")
    return _to_org_out(org, m.role)


@router.delete("/organizations/{org_id}")
def delete_organization(
    org_id: int,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    _require_role(db, org_id, user.id, "owner")
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="organization not found")
    db.delete(org)
    db.commit()
    return {"object": "organization.deleted", "id": org_id}


# ---------- members ----------

@router.get("/organizations/{org_id}/members", response_model=List[MemberOut])
def list_members(
    org_id: int,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    _require_role(db, org_id, user.id, "member")
    rows = (
        db.query(OrganizationMember, User.email)
        .join(User, User.id == OrganizationMember.user_id)
        .filter(OrganizationMember.organization_id == org_id)
        .order_by(OrganizationMember.created_at.asc())
        .all()
    )
    return [
        {
            "id": m.id,
            "user_id": m.user_id,
            "role": m.role,
            "created_at": m.created_at,
            "user_email": email,
        }
        for m, email in rows
    ]


@router.post("/organizations/{org_id}/members", response_model=MemberOut)
def add_member(
    org_id: int,
    payload: MemberAdd,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    _require_role(db, org_id, user.id, "admin")
    if not db.query(User).filter(User.id == payload.user_id).first():
        raise HTTPException(status_code=400, detail="user_id does not exist")
    if _get_membership(db, org_id, payload.user_id):
        raise HTTPException(status_code=400, detail="user is already a member")
    m = OrganizationMember(
        organization_id=org_id, user_id=payload.user_id, role=payload.role
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    target_user = db.query(User).filter(User.id == payload.user_id).first()
    return {
        "id": m.id,
        "user_id": m.user_id,
        "role": m.role,
        "created_at": m.created_at,
        "user_email": target_user.email if target_user else None,
    }


@router.delete("/organizations/{org_id}/members/{user_id}")
def remove_member(
    org_id: int,
    user_id: int,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    _require_role(db, org_id, user.id, "admin")
    m = _get_membership(db, org_id, user_id)
    if not m:
        raise HTTPException(status_code=404, detail="member not found")
    if m.role == "owner":
        raise HTTPException(status_code=400, detail="cannot remove the owner; transfer ownership first")
    db.delete(m)
    db.commit()
    return {"object": "member.removed", "user_id": user_id}


# ---------- teams ----------

@router.get("/organizations/{org_id}/teams", response_model=List[TeamOut])
def list_teams(
    org_id: int,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    _require_role(db, org_id, user.id, "member")
    teams = (
        db.query(Team)
        .filter(Team.organization_id == org_id)
        .order_by(Team.created_at.desc())
        .all()
    )
    out = []
    for t in teams:
        count = db.query(TeamMember).filter(TeamMember.team_id == t.id).count()
        out.append({
            "id": t.id,
            "organization_id": t.organization_id,
            "name": t.name,
            "description": t.description,
            "created_at": t.created_at,
            "member_count": count,
        })
    return out


@router.post("/organizations/{org_id}/teams", response_model=TeamOut)
def create_team(
    org_id: int,
    payload: TeamCreate,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    _require_role(db, org_id, user.id, "admin")
    t = Team(organization_id=org_id, name=payload.name, description=payload.description)
    db.add(t)
    db.commit()
    db.refresh(t)
    return {
        "id": t.id,
        "organization_id": t.organization_id,
        "name": t.name,
        "description": t.description,
        "created_at": t.created_at,
        "member_count": 0,
    }


@router.post("/organizations/{org_id}/teams/{team_id}/members")
def add_team_member(
    org_id: int,
    team_id: int,
    user_id: int,
    db: Session = Depends(deps.get_db),
    auth: tuple = Depends(get_user_from_api_key),
):
    user, _ = auth
    _require_role(db, org_id, user.id, "admin")
    team = db.query(Team).filter(Team.id == team_id, Team.organization_id == org_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="team not found")
    if not _get_membership(db, org_id, user_id):
        raise HTTPException(status_code=400, detail="user is not a member of the org")
    if db.query(TeamMember).filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id).first():
        raise HTTPException(status_code=400, detail="user is already on the team")
    db.add(TeamMember(team_id=team_id, user_id=user_id))
    db.commit()
    return {"object": "team.member.added", "team_id": team_id, "user_id": user_id}
