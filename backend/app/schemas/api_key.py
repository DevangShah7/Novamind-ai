from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ApiKeyBase(BaseModel):
    name: str = Field(..., example="Production API Key")
    description: Optional[str] = Field(None, example="Key for production services")
    expires_at: Optional[datetime] = Field(None, example="2024-12-31T00:00:00Z")


class ApiKeyCreate(ApiKeyBase):
    pass


class ApiKeyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None


class ApiKeyInDBBase(ApiKeyBase):
    id: int
    key: str
    is_active: bool
    last_used_at: Optional[datetime] = None
    usage_count: int

    class Config:
        orm_mode = True


class ApiKeyInDB(ApiKeyInDBBase):
    user_id: int


class ApiKey(ApiKeyInDBBase):
    pass


class ApiKeyCreateResponse(BaseModel):
    id: int
    key: str  # Only returned on creation
    name: str
    description: Optional[str] = None
    is_active: bool
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


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