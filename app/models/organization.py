from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text)

    # Business details
    industry = Column(String)  # e-commerce, saas, agency, consulting, etc
    size_range = Column(String)  # 1-10, 11-50, 51-200, 200+
    website = Column(String)
    country = Column(String)
    timezone = Column(String, default="UTC")

    # Onboarding status
    onboarding_completed = Column(Boolean, default=False)
    onboarding_step = Column(String, default="created")  # created, documents, integrations, training, completed

    # Subscription and limits
    plan = Column(String, default="free")  # free, pro, enterprise
    agent_limit = Column(String, default="1")
    document_limit_mb = Column(String, default="100")
    monthly_requests_limit = Column(String, default="1000")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="organization")
    agents = relationship("Agent", back_populates="organization")
    business_context = relationship("BusinessContext", back_populates="organization", uselist=False)

    # Marketplace relationships
    marketplace_templates = relationship("MarketplaceTemplate", back_populates="organization")
    template_ratings = relationship("TemplateRating", back_populates="organization")
    template_installations = relationship("TemplateInstallation", back_populates="organization")

    def __repr__(self):
        return f"<Organization(id={self.id}, name={self.name}, industry={self.industry})>"

    @property
    def is_onboarded(self):
        return self.onboarding_completed

    @property
    def can_create_agent(self):
        current_agents = len(self.agents) if self.agents else 0
        return current_agents < int(self.agent_limit)

    def get_owner(self):
        """Get the organization owner"""
        for user in self.users:
            if user.role == "owner":
                return user
        return None

    def get_admins(self):
        """Get all organization admins (including owner)"""
        return [user for user in self.users if user.role in ["owner", "admin"]]