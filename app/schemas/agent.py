from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    type: str
    response_style: str = "helpful"
    max_response_length: str = "medium"
    allowed_topics: List[str] = Field(default_factory=list)
    forbidden_topics: List[str] = Field(default_factory=list)
    escalation_rules: List[str] = Field(default_factory=list)


class AgentCreate(AgentBase):
    llm_config: Dict[str, Any] = Field(default_factory=dict)
    tools_config: List[Dict[str, Any]] = Field(default_factory=list)
    memory_config: Dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    response_style: Optional[str] = None
    max_response_length: Optional[str] = None
    allowed_topics: Optional[List[str]] = None
    forbidden_topics: Optional[List[str]] = None
    escalation_rules: Optional[List[str]] = None
    llm_config: Optional[Dict[str, Any]] = None
    tools_config: Optional[List[Dict[str, Any]]] = None
    memory_config: Optional[Dict[str, Any]] = None


class AgentInDBBase(AgentBase):
    id: UUID
    organization_id: UUID
    status: str
    system_prompt: Optional[str] = None
    llm_config: Dict[str, Any]
    tools_config: List[Dict[str, Any]]
    memory_config: Dict[str, Any]
    vector_store_collection: Optional[str] = None
    retrieval_config: Dict[str, Any]
    context_window_size: int
    total_executions: int
    successful_executions: int
    failed_executions: int
    avg_response_time: float
    avg_satisfaction_score: float
    last_execution_at: Optional[datetime] = None
    training_completed: bool
    training_started_at: Optional[datetime] = None
    training_completed_at: Optional[datetime] = None
    validation_score: Optional[float] = None
    validation_details: Dict[str, Any]
    version: str
    parent_agent_id: Optional[UUID] = None
    is_active_version: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Agent(AgentInDBBase):
    success_rate: Optional[float] = None
    is_ready: Optional[bool] = None
    is_principal_agent: Optional[bool] = None

    @classmethod
    def from_orm_with_computed(cls, orm_obj):
        agent = cls.from_orm(orm_obj)
        agent.success_rate = orm_obj.success_rate
        agent.is_ready = orm_obj.is_ready
        agent.is_principal_agent = orm_obj.is_principal_agent
        return agent


class AgentInDB(AgentInDBBase):
    pass


class AgentSummary(BaseModel):
    id: UUID
    name: str
    type: str
    status: str
    success_rate: float
    total_executions: int
    avg_response_time: float
    training_completed: bool
    is_ready: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AgentExecution(BaseModel):
    agent_id: UUID
    input_text: str
    output_text: str
    execution_time: float
    success: bool
    error_message: Optional[str] = None
    satisfaction_score: Optional[float] = None
    context_used: List[str] = Field(default_factory=list)
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class AgentPerformance(BaseModel):
    agent_id: UUID
    total_executions: int
    success_rate: float
    avg_response_time: float
    avg_satisfaction_score: float
    executions_last_24h: int
    executions_last_week: int
    executions_last_month: int
    error_rate: float
    most_common_topics: List[str]
    performance_trend: str  # improving, declining, stable

    class Config:
        from_attributes = True