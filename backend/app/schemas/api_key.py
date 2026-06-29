from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ApiKeyBase(BaseModel):
    name: str = Field(..., example="Production API Key")
    description: Optional[str] = Field(None, example="Key for production services")
    expires_at: Optional[datetime] = Field(None, example="2024-12-31T00:00:00Z")


class ApiKeyCreate(ApiKeyBase):
    """Create a new API key. All restriction fields are optional."""
    ip_allowlist: Optional[List[str]] = Field(
        None, example=["203.0.113.0/24"], description="CIDR/IP allowlist; empty = unrestricted"
    )
    domain_allowlist: Optional[List[str]] = Field(
        None, example=["api.example.com"], description="Domain allowlist for browser callers; empty = unrestricted"
    )
    tags: Optional[List[str]] = Field(None, example=["prod", "billing"])
    organization: Optional[str] = Field(None, example="Acme Corp")
    monthly_token_limit: Optional[int] = Field(None, ge=0, description="0/unset = unlimited")
    monthly_request_limit: Optional[int] = Field(None, ge=0, description="0/unset = unlimited")


class ApiKeyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_disabled: Optional[bool] = None
    disable_reason: Optional[str] = None
    expires_at: Optional[datetime] = None
    ip_allowlist: Optional[List[str]] = None
    domain_allowlist: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    organization: Optional[str] = None
    monthly_token_limit: Optional[int] = None
    monthly_request_limit: Optional[int] = None


class ApiKeyInDBBase(ApiKeyBase):
    id: int
    key: str
    is_active: bool
    is_disabled: bool = False
    disable_reason: Optional[str] = None
    last_used_at: Optional[datetime] = None
    usage_count: int
    ip_allowlist: Optional[List[str]] = None
    domain_allowlist: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    organization: Optional[str] = None
    monthly_token_limit: Optional[int] = None
    monthly_request_limit: Optional[int] = None
    monthly_token_count: Optional[int] = 0
    monthly_request_count: Optional[int] = 0
    monthly_cost_usd: Optional[int] = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class ApiKeyInDB(ApiKeyInDBBase):
    user_id: int


class ApiKey(ApiKeyInDBBase):
    pass


class ApiKeyCreateResponse(BaseModel):
    """Returned once at creation — the only time the full secret is shown."""
    id: int
    key: str
    name: str
    description: Optional[str] = None
    is_active: bool
    is_disabled: bool = False
    expires_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    organization: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# ---------- Usage ----------

class ApiUsageBase(BaseModel):
    endpoint: str
    method: str
    status_code: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    response_time_ms: Optional[float] = None
    tokens_used: Optional[int] = None
    model_used: Optional[str] = None


class ApiUsageCreate(ApiUsageBase):
    user_id: Optional[int] = None
    api_key_id: Optional[int] = None


class ApiUsage(ApiUsageBase):
    id: int
    user_id: Optional[int] = None
    api_key_id: Optional[int] = None
    created_at: datetime

    class Config:
        orm_mode = True


class ApiUsageSummary(BaseModel):
    total_requests: int
    today_requests: int
    total_tokens_used: int
    today_tokens_used: int
    average_response_time_ms: float
    top_endpoints: List[dict]

    class Config:
        orm_mode = True


# ---------- /v1/models listing ----------

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "novamind"
    created: Optional[int] = None
    source: str = "local"  # "local" | "ollama" — tells the caller whether it's a real model


class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]