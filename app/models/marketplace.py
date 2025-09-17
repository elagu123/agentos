"""
Marketplace models for template sharing and community features.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.database import Base


class TemplateStatus(str, Enum):
    """Template publication status"""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class TemplateVisibility(str, Enum):
    """Template visibility settings"""
    PUBLIC = "public"
    ORGANIZATION = "organization"
    PRIVATE = "private"


class MarketplaceTemplate(Base):
    """
    Marketplace template model for community sharing.
    Extends the base workflow template with marketplace-specific features.
    """
    __tablename__ = "marketplace_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Basic template info
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)
    tags = Column(JSON, default=list)  # List of strings

    # Template content
    workflow_definition = Column(JSON, nullable=False)
    version = Column(String(50), nullable=False, default="1.0.0")
    changelog = Column(Text)

    # Marketplace metadata
    status = Column(String(50), nullable=False, default=TemplateStatus.DRAFT, index=True)
    visibility = Column(String(50), nullable=False, default=TemplateVisibility.PUBLIC, index=True)
    is_featured = Column(Boolean, default=False, index=True)
    is_certified = Column(Boolean, default=False, index=True)

    # Author information
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    author_name = Column(String(255), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True)

    # Statistics
    download_count = Column(Integer, default=0, index=True)
    install_count = Column(Integer, default=0, index=True)
    view_count = Column(Integer, default=0, index=True)

    # Ratings
    rating_average = Column(Float, default=0.0, index=True)
    rating_count = Column(Integer, default=0)

    # Media
    preview_image_url = Column(String(500))
    screenshots = Column(JSON, default=list)  # List of image URLs
    video_url = Column(String(500))

    # Pricing (for future premium features)
    is_premium = Column(Boolean, default=False, index=True)
    price = Column(Float, default=0.0)
    currency = Column(String(3), default="USD")

    # SEO and discovery
    slug = Column(String(255), unique=True, index=True)
    search_keywords = Column(JSON, default=list)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    published_at = Column(DateTime, nullable=True, index=True)

    # Relationships
    author = relationship("User", back_populates="marketplace_templates")
    organization = relationship("Organization", back_populates="marketplace_templates")
    ratings = relationship("TemplateRating", back_populates="template", cascade="all, delete-orphan")
    installations = relationship("TemplateInstallation", back_populates="template", cascade="all, delete-orphan")
    reports = relationship("TemplateReport", back_populates="template", cascade="all, delete-orphan")
    collections = relationship("TemplateCollection", secondary="template_collection_items", back_populates="templates")

    # Indexes for performance
    __table_args__ = (
        Index('idx_marketplace_templates_category_status', 'category', 'status'),
        Index('idx_marketplace_templates_rating_downloads', 'rating_average', 'download_count'),
        Index('idx_marketplace_templates_created_featured', 'created_at', 'is_featured'),
    )

    def __repr__(self):
        return f"<MarketplaceTemplate(id={self.id}, name='{self.name}', author='{self.author_name}')>"


class TemplateRating(Base):
    """
    Template rating and review model.
    """
    __tablename__ = "template_ratings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Rating details
    template_id = Column(UUID(as_uuid=True), ForeignKey("marketplace_templates.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True)

    # Rating content
    rating = Column(Integer, nullable=False)  # 1-5 stars
    review_title = Column(String(255))
    review_text = Column(Text)

    # Usage context
    use_case = Column(String(255))  # How they used the template
    industry = Column(String(100))
    team_size = Column(String(50))

    # Helpfulness tracking
    helpful_count = Column(Integer, default=0)
    not_helpful_count = Column(Integer, default=0)

    # Verification
    is_verified_purchase = Column(Boolean, default=False)
    is_verified_usage = Column(Boolean, default=False)

    # Moderation
    is_approved = Column(Boolean, default=True)
    is_flagged = Column(Boolean, default=False)
    moderation_notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    template = relationship("MarketplaceTemplate", back_populates="ratings")
    user = relationship("User", back_populates="template_ratings")
    organization = relationship("Organization", back_populates="template_ratings")

    # Unique constraint: one rating per user per template
    __table_args__ = (
        Index('idx_template_ratings_user_template', 'user_id', 'template_id', unique=True),
        Index('idx_template_ratings_template_rating', 'template_id', 'rating'),
    )

    def __repr__(self):
        return f"<TemplateRating(id={self.id}, template_id={self.template_id}, rating={self.rating})>"


class TemplateInstallation(Base):
    """
    Template installation tracking model.
    """
    __tablename__ = "template_installations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Installation details
    template_id = Column(UUID(as_uuid=True), ForeignKey("marketplace_templates.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)

    # Installation metadata
    installation_type = Column(String(50), default="standard")  # standard, custom, fork
    customization_data = Column(JSON, default=dict)
    installed_workflow_id = Column(UUID(as_uuid=True), nullable=True)  # Reference to created workflow

    # Usage tracking
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)

    # Success metrics
    installation_successful = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    template = relationship("MarketplaceTemplate", back_populates="installations")
    user = relationship("User", back_populates="template_installations")
    organization = relationship("Organization", back_populates="template_installations")

    # Indexes
    __table_args__ = (
        Index('idx_template_installations_user_org', 'user_id', 'organization_id'),
        Index('idx_template_installations_template_date', 'template_id', 'created_at'),
    )

    def __repr__(self):
        return f"<TemplateInstallation(id={self.id}, template_id={self.template_id}, user_id={self.user_id})>"


class TemplateReport(Base):
    """
    Template report model for community moderation.
    """
    __tablename__ = "template_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Report details
    template_id = Column(UUID(as_uuid=True), ForeignKey("marketplace_templates.id"), nullable=False, index=True)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Report content
    reason = Column(String(100), nullable=False)  # spam, inappropriate, broken, copyright, etc.
    description = Column(Text, nullable=False)
    evidence_urls = Column(JSON, default=list)  # Screenshots, links, etc.

    # Report status
    status = Column(String(50), default="pending")  # pending, reviewing, resolved, dismissed
    resolution = Column(Text, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    template = relationship("MarketplaceTemplate", back_populates="reports")
    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="template_reports")
    resolver = relationship("User", foreign_keys=[resolved_by])

    # Indexes
    __table_args__ = (
        Index('idx_template_reports_status_date', 'status', 'created_at'),
        Index('idx_template_reports_template_reason', 'template_id', 'reason'),
    )

    def __repr__(self):
        return f"<TemplateReport(id={self.id}, template_id={self.template_id}, reason='{self.reason}')>"


class TemplateCollection(Base):
    """
    Curated collections of templates.
    """
    __tablename__ = "template_collections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Collection info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    slug = Column(String(255), unique=True, index=True)

    # Collection metadata
    curator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_official = Column(Boolean, default=False, index=True)
    is_featured = Column(Boolean, default=False, index=True)

    # Display
    cover_image_url = Column(String(500))
    tags = Column(JSON, default=list)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    curator = relationship("User", back_populates="template_collections")
    templates = relationship("MarketplaceTemplate", secondary="template_collection_items", back_populates="collections")

    def __repr__(self):
        return f"<TemplateCollection(id={self.id}, name='{self.name}')>"


class TemplateCollectionItem(Base):
    """
    Association table for templates in collections.
    """
    __tablename__ = "template_collection_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("template_collections.id"), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("marketplace_templates.id"), nullable=False)

    # Ordering and metadata
    order_index = Column(Integer, default=0)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    added_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Unique constraint
    __table_args__ = (
        Index('idx_collection_items_unique', 'collection_id', 'template_id', unique=True),
        Index('idx_collection_items_order', 'collection_id', 'order_index'),
    )


class TemplateAnalytics(Base):
    """
    Template analytics and metrics tracking.
    """
    __tablename__ = "template_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Analytics target
    template_id = Column(UUID(as_uuid=True), ForeignKey("marketplace_templates.id"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)

    # Metrics
    views = Column(Integer, default=0)
    unique_views = Column(Integer, default=0)
    downloads = Column(Integer, default=0)
    installations = Column(Integer, default=0)
    searches = Column(Integer, default=0)

    # Geographic data
    country_stats = Column(JSON, default=dict)

    # Referrer data
    referrer_stats = Column(JSON, default=dict)

    # Search terms that led to this template
    search_terms = Column(JSON, default=list)

    # Unique constraint on template + date
    __table_args__ = (
        Index('idx_template_analytics_unique', 'template_id', 'date', unique=True),
    )

    def __repr__(self):
        return f"<TemplateAnalytics(template_id={self.template_id}, date={self.date})>"