from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    # Basic Information
    name = Column(String, nullable=False)
    description = Column(Text)
    type = Column(String, nullable=False)  # principal, copywriter, researcher, customer_service, sales
    status = Column(String, default="created")  # created, training, ready, error, disabled

    # Agent Configuration
    system_prompt = Column(Text)
    llm_config = Column(JSON, default=dict)  # model, temperature, max_tokens, etc
    tools_config = Column(JSON, default=list)  # enabled tools and their configurations
    memory_config = Column(JSON, default=dict)  # memory configuration and settings

    # RAG Configuration
    vector_store_collection = Column(String)  # Qdrant collection name
    retrieval_config = Column(JSON, default=dict)  # RAG retrieval settings
    context_window_size = Column(Integer, default=4000)

    # Behavioral Settings
    response_style = Column(String, default="helpful")  # helpful, direct, consultative, creative
    max_response_length = Column(String, default="medium")  # short, medium, long
    allowed_topics = Column(JSON, default=list)  # topics the agent can discuss
    forbidden_topics = Column(JSON, default=list)  # topics the agent should avoid
    escalation_rules = Column(JSON, default=list)  # when to escalate to human

    # Performance Metrics
    total_executions = Column(Integer, default=0)
    successful_executions = Column(Integer, default=0)
    failed_executions = Column(Integer, default=0)
    avg_response_time = Column(Float, default=0.0)
    avg_satisfaction_score = Column(Float, default=0.0)
    last_execution_at = Column(DateTime)

    # Training and Validation
    training_completed = Column(Boolean, default=False)
    training_started_at = Column(DateTime)
    training_completed_at = Column(DateTime)
    validation_score = Column(Float)
    validation_details = Column(JSON, default=dict)

    # Version Control
    version = Column(String, default="1.0.0")
    parent_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    is_active_version = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="agents")
    parent_agent = relationship("Agent", remote_side=[id], backref="child_versions")

    def __repr__(self):
        return f"<Agent(id={self.id}, name={self.name}, type={self.type}, status={self.status})>"

    @property
    def success_rate(self):
        """Calculate success rate percentage"""
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100

    @property
    def is_ready(self):
        """Check if agent is ready for use"""
        return (
            self.status == "ready" and
            self.training_completed and
            self.system_prompt is not None
        )

    @property
    def is_principal_agent(self):
        """Check if this is the principal agent"""
        return self.type == "principal"

    def get_llm_model(self):
        """Get the configured LLM model"""
        return self.llm_config.get("model", "gpt-4-turbo-preview")

    def get_temperature(self):
        """Get the configured temperature"""
        return self.llm_config.get("temperature", 0.7)

    def get_max_tokens(self):
        """Get the configured max tokens"""
        return self.llm_config.get("max_tokens", 2000)

    def increment_execution_count(self, success: bool = True, response_time: float = 0.0):
        """Increment execution metrics"""
        self.total_executions += 1
        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1

        # Update average response time
        if response_time > 0:
            if self.avg_response_time == 0:
                self.avg_response_time = response_time
            else:
                self.avg_response_time = (
                    (self.avg_response_time * (self.total_executions - 1) + response_time) /
                    self.total_executions
                )

        self.last_execution_at = datetime.utcnow()

    def update_satisfaction_score(self, score: float):
        """Update average satisfaction score"""
        if self.avg_satisfaction_score == 0:
            self.avg_satisfaction_score = score
        else:
            # Weighted average with recent scores having more weight
            self.avg_satisfaction_score = (self.avg_satisfaction_score * 0.8) + (score * 0.2)

    def can_handle_topic(self, topic: str) -> bool:
        """Check if agent can handle a specific topic"""
        if self.forbidden_topics and any(forbidden in topic.lower() for forbidden in self.forbidden_topics):
            return False

        if self.allowed_topics:
            return any(allowed in topic.lower() for allowed in self.allowed_topics)

        return True