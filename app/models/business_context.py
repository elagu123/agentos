from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class BusinessContext(Base):
    __tablename__ = "business_contexts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    # Business Profile
    business_name = Column(String, nullable=False)
    industry = Column(String)
    business_description = Column(Text)

    # Products and Services
    products = Column(JSON, default=list)  # List of products/services
    services = Column(JSON, default=list)  # List of services
    value_proposition = Column(Text)  # What makes the business unique

    # Target Audience
    target_audience = Column(Text)
    customer_personas = Column(JSON, default=list)  # List of customer personas
    pain_points = Column(JSON, default=list)  # Customer pain points the business solves

    # Brand Identity
    brand_tone = Column(String, default="professional")  # formal, casual, friendly, professional, authoritative
    brand_voice = Column(Text)  # How the brand communicates
    brand_guidelines = Column(Text)  # Brand guidelines and rules
    brand_values = Column(JSON, default=list)  # Core brand values

    # Communication Preferences
    preferred_language = Column(String, default="en")
    communication_style = Column(String, default="helpful")  # helpful, direct, consultative, sales-oriented
    response_length = Column(String, default="medium")  # short, medium, detailed

    # Knowledge Base
    faq_data = Column(JSON, default=list)  # Frequently asked questions
    policies = Column(JSON, default=dict)  # Business policies (refund, privacy, etc)
    contact_info = Column(JSON, default=dict)  # Contact information
    business_hours = Column(JSON, default=dict)  # Operating hours

    # Document Processing
    documents_metadata = Column(JSON, default=list)  # References to processed documents
    total_documents = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)

    # Vector Store Configuration
    vector_store_id = Column(String)  # Collection ID in Qdrant
    embedding_model = Column(String, default="text-embedding-ada-002")
    last_indexed_at = Column(DateTime)

    # Training Data
    sample_conversations = Column(JSON, default=list)  # Example conversations for training
    do_not_answer = Column(JSON, default=list)  # Topics the agent should not discuss
    escalation_triggers = Column(JSON, default=list)  # When to escalate to human

    # Integration Configuration
    integrations_config = Column(JSON, default=dict)  # Third-party integrations settings

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="business_context")

    def __repr__(self):
        return f"<BusinessContext(id={self.id}, business_name={self.business_name}, industry={self.industry})>"

    @property
    def is_complete(self):
        """Check if business context has minimum required information"""
        required_fields = [
            self.business_name,
            self.industry,
            self.target_audience,
            self.brand_tone
        ]
        return all(field is not None and field.strip() != "" for field in required_fields)

    @property
    def has_documents(self):
        """Check if any documents have been processed"""
        return self.total_documents > 0

    @property
    def is_indexed(self):
        """Check if documents are indexed in vector store"""
        return self.vector_store_id is not None and self.last_indexed_at is not None

    def get_brand_personality(self):
        """Get a description of the brand personality for prompt generation"""
        personality_traits = []

        if self.brand_tone:
            personality_traits.append(f"tone: {self.brand_tone}")

        if self.communication_style:
            personality_traits.append(f"style: {self.communication_style}")

        if self.brand_values:
            values_str = ", ".join(self.brand_values)
            personality_traits.append(f"values: {values_str}")

        return "; ".join(personality_traits) if personality_traits else "professional and helpful"