from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clerk_id = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    first_name = Column(String)
    last_name = Column(String)

    # Organization relationship
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)

    # User role and permissions
    role = Column(String, default="member")  # owner, admin, member
    is_active = Column(Boolean, default=True)
    is_onboarded = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)

    # Relationships
    organization = relationship("Organization", back_populates="users")

    # Marketplace relationships
    marketplace_templates = relationship("MarketplaceTemplate", back_populates="author")
    template_ratings = relationship("TemplateRating", back_populates="user")
    template_installations = relationship("TemplateInstallation", back_populates="user")
    template_reports = relationship("TemplateReport", foreign_keys="TemplateReport.reporter_id", back_populates="reporter")
    template_collections = relationship("TemplateCollection", back_populates="curator")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"

    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or self.email

    @property
    def is_organization_owner(self):
        return self.role == "owner"

    @property
    def is_organization_admin(self):
        return self.role in ["owner", "admin"]