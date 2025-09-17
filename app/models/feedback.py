from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from .base import Base

class Feedback(Base):
    """Feedback submissions from beta users"""
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)

    type = Column(String(50), nullable=False)  # bug, feature_request, general
    category = Column(String(100), nullable=False)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    severity = Column(String(20), default="medium")  # low, medium, high, critical

    # Additional context
    metadata = Column(JSON, default=dict)  # user_agent, screenshot, etc.
    url = Column(String(500), nullable=True)
    browser_info = Column(JSON, default=dict)

    # Status tracking
    status = Column(String(20), default="open")  # open, in_progress, resolved, closed
    priority = Column(String(20), default="medium")  # low, medium, high, critical
    assigned_to = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="feedback")
    organization = relationship("Organization", back_populates="feedback")

class BetaInvite(Base):
    """Beta testing invitations"""
    __tablename__ = "beta_invites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True)
    company_name = Column(String(255), nullable=False)
    token = Column(String(255), nullable=False, unique=True)

    # Invite details
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status = Column(String(20), default="pending")  # pending, accepted, expired

    # Beta testing info
    beta_type = Column(String(50), default="general")  # general, specific_feature, stress_test
    features_enabled = Column(JSON, default=list)
    limits = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    inviter = relationship("User", foreign_keys=[invited_by])

class UserMetric(Base):
    """User behavior metrics for analytics"""
    __tablename__ = "user_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)

    # Metric details
    event_type = Column(String(100), nullable=False)  # page_view, feature_used, workflow_created, etc.
    event_category = Column(String(50), nullable=False)  # navigation, interaction, conversion, error
    event_data = Column(JSON, default=dict)

    # Context
    session_id = Column(String(255), nullable=True)
    url = Column(String(500), nullable=True)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Performance metrics
    load_time = Column(Integer, nullable=True)  # milliseconds
    response_time = Column(Integer, nullable=True)  # milliseconds

    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="metrics")
    organization = relationship("Organization", back_populates="metrics")

class BetaTestSession(Base):
    """Beta testing sessions and milestones"""
    __tablename__ = "beta_test_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)

    # Session details
    session_type = Column(String(50), nullable=False)  # onboarding, feature_test, feedback_session
    status = Column(String(20), default="active")  # active, completed, abandoned

    # Milestones tracking
    milestones_completed = Column(JSON, default=list)
    current_milestone = Column(String(100), nullable=True)
    total_milestones = Column(Integer, default=0)

    # Performance tracking
    time_to_first_action = Column(Integer, nullable=True)  # seconds
    completion_rate = Column(Integer, default=0)  # percentage
    errors_encountered = Column(Integer, default=0)
    help_requests = Column(Integer, default=0)

    # Feedback
    satisfaction_score = Column(Integer, nullable=True)  # 1-10
    nps_score = Column(Integer, nullable=True)  # -100 to 100
    feedback_notes = Column(Text, nullable=True)

    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    last_activity_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="beta_sessions")
    organization = relationship("Organization", back_populates="beta_sessions")

class FeatureFlag(Base):
    """Feature flags for beta testing"""
    __tablename__ = "feature_flags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Flag configuration
    is_enabled = Column(Boolean, default=False)
    rollout_percentage = Column(Integer, default=0)  # 0-100
    target_users = Column(JSON, default=list)  # specific user IDs
    target_organizations = Column(JSON, default=list)  # specific org IDs

    # Conditions
    conditions = Column(JSON, default=dict)  # complex targeting rules

    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    tags = Column(JSON, default=list)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])

class BetaMetrics(Base):
    """Aggregated beta testing metrics"""
    __tablename__ = "beta_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_date = Column(DateTime, nullable=False)

    # User metrics
    total_beta_users = Column(Integer, default=0)
    active_beta_users = Column(Integer, default=0)
    new_signups = Column(Integer, default=0)
    activation_rate = Column(Integer, default=0)  # percentage

    # Engagement metrics
    avg_session_duration = Column(Integer, default=0)  # minutes
    avg_time_to_first_agent = Column(Integer, default=0)  # minutes
    workflow_creation_rate = Column(Integer, default=0)  # percentage
    feature_adoption_rates = Column(JSON, default=dict)

    # Quality metrics
    bug_reports = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    feature_requests = Column(Integer, default=0)
    avg_satisfaction_score = Column(Integer, default=0)
    nps_score = Column(Integer, default=0)

    # Performance metrics
    system_uptime = Column(Integer, default=100)  # percentage
    avg_response_time = Column(Integer, default=0)  # milliseconds
    error_rate = Column(Integer, default=0)  # percentage

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)