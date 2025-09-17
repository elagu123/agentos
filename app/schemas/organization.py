from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    industry: Optional[str] = None
    size_range: Optional[str] = None
    website: Optional[str] = None
    country: Optional[str] = None
    timezone: str = "UTC"


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    industry: Optional[str] = None
    size_range: Optional[str] = None
    website: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None


class OrganizationInDBBase(OrganizationBase):
    id: UUID
    slug: str
    onboarding_completed: bool
    onboarding_step: str
    plan: str
    agent_limit: str
    document_limit_mb: str
    monthly_requests_limit: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Organization(OrganizationInDBBase):
    pass


class OrganizationInDB(OrganizationInDBBase):
    pass


class OrganizationSummary(BaseModel):
    id: UUID
    name: str
    industry: Optional[str] = None
    onboarding_completed: bool
    onboarding_step: str
    plan: str
    created_at: datetime

    class Config:
        from_attributes = True


class OrganizationStats(BaseModel):
    total_agents: int
    total_documents: int
    total_requests_this_month: int
    success_rate: float
    avg_response_time: float

    class Config:
        from_attributes = True