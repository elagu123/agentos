from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class BusinessContextCreate(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=100)
    industry: str
    business_description: Optional[str] = None
    target_audience: str
    brand_tone: str = Field(default="professional")
    brand_voice: Optional[str] = None
    brand_guidelines: Optional[str] = None
    brand_values: List[str] = Field(default_factory=list)
    products: List[Dict[str, Any]] = Field(default_factory=list)
    services: List[Dict[str, Any]] = Field(default_factory=list)
    value_proposition: Optional[str] = None
    customer_personas: List[Dict[str, Any]] = Field(default_factory=list)
    pain_points: List[str] = Field(default_factory=list)
    preferred_language: str = "en"
    communication_style: str = "helpful"
    response_length: str = "medium"
    faq_data: List[Dict[str, str]] = Field(default_factory=list)
    policies: Dict[str, Any] = Field(default_factory=dict)
    contact_info: Dict[str, Any] = Field(default_factory=dict)
    business_hours: Dict[str, Any] = Field(default_factory=dict)
    sample_conversations: List[Dict[str, Any]] = Field(default_factory=list)
    do_not_answer: List[str] = Field(default_factory=list)
    escalation_triggers: List[str] = Field(default_factory=list)


class BusinessContextUpdate(BaseModel):
    business_name: Optional[str] = None
    industry: Optional[str] = None
    business_description: Optional[str] = None
    target_audience: Optional[str] = None
    brand_tone: Optional[str] = None
    brand_voice: Optional[str] = None
    brand_guidelines: Optional[str] = None
    brand_values: Optional[List[str]] = None
    products: Optional[List[Dict[str, Any]]] = None
    services: Optional[List[Dict[str, Any]]] = None
    value_proposition: Optional[str] = None
    customer_personas: Optional[List[Dict[str, Any]]] = None
    pain_points: Optional[List[str]] = None
    preferred_language: Optional[str] = None
    communication_style: Optional[str] = None
    response_length: Optional[str] = None
    faq_data: Optional[List[Dict[str, str]]] = None
    policies: Optional[Dict[str, Any]] = None
    contact_info: Optional[Dict[str, Any]] = None
    business_hours: Optional[Dict[str, Any]] = None
    sample_conversations: Optional[List[Dict[str, Any]]] = None
    do_not_answer: Optional[List[str]] = None
    escalation_triggers: Optional[List[str]] = None


class IntegrationsConfig(BaseModel):
    email_integration: Optional[Dict[str, Any]] = None
    whatsapp_integration: Optional[Dict[str, Any]] = None
    slack_integration: Optional[Dict[str, Any]] = None
    website_widget: Optional[Dict[str, Any]] = None
    api_webhooks: Optional[List[Dict[str, Any]]] = None


class DocumentUploadResponse(BaseModel):
    filename: str
    size: int
    content_type: str
    chunks_created: int
    status: str
    processing_time: float


class OnboardingStepResponse(BaseModel):
    step: str
    completed: bool
    message: str
    next_step: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class TrainingStatus(BaseModel):
    agent_id: UUID
    status: str
    progress: float
    estimated_completion: Optional[datetime] = None
    validation_score: Optional[float] = None
    error_message: Optional[str] = None


class OnboardingStatus(BaseModel):
    organization_id: UUID
    current_step: str
    completed_steps: List[str]
    progress_percentage: float
    can_proceed: bool
    next_action: Optional[str] = None
    business_context_complete: bool
    documents_uploaded: int
    integrations_configured: int
    agent_trained: bool