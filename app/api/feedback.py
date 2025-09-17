from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import uuid

from ..database import get_db
from ..models.user import User
from ..models.organization import Organization
from ..models.feedback import (
    Feedback, BetaInvite, UserMetric, BetaTestSession,
    FeatureFlag, BetaMetrics
)
from ..auth import get_current_user, get_current_user_optional
from ..utils.email import send_email
from ..utils.notifications import notify_team

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])

# Pydantic models
class FeedbackSubmission(BaseModel):
    type: str = Field(..., description="Type of feedback: bug, feature_request, general")
    category: str = Field(..., description="Category of feedback")
    title: Optional[str] = Field(None, max_length=255)
    description: str = Field(..., min_length=10)
    severity: Optional[str] = Field("medium", description="Severity: low, medium, high, critical")
    url: Optional[str] = Field(None, max_length=500)
    screenshot_url: Optional[str] = Field(None)
    browser_info: Optional[Dict[str, Any]] = Field(default_factory=dict)

class MetricTracking(BaseModel):
    event_type: str = Field(..., description="Type of event being tracked")
    event_category: str = Field(..., description="Category: navigation, interaction, conversion, error")
    event_data: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    url: Optional[str] = None
    load_time: Optional[int] = None
    response_time: Optional[int] = None

class BetaSessionUpdate(BaseModel):
    session_type: str
    milestone_completed: Optional[str] = None
    satisfaction_score: Optional[int] = Field(None, ge=1, le=10)
    nps_score: Optional[int] = Field(None, ge=-100, le=100)
    feedback_notes: Optional[str] = None
    errors_encountered: Optional[int] = 0
    help_requests: Optional[int] = 0

class FeedbackResponse(BaseModel):
    id: str
    type: str
    category: str
    title: Optional[str]
    description: str
    severity: str
    status: str
    created_at: datetime
    user_name: str

class BetaMetricsResponse(BaseModel):
    total_beta_users: int
    active_beta_users: int
    activation_rate: float
    avg_time_to_first_agent: float
    workflow_success_rate: float
    nps_score: float
    top_issues: List[Dict[str, Any]]
    feature_requests: List[Dict[str, Any]]

# Feedback endpoints
@router.post("/submit")
async def submit_feedback(
    feedback_data: FeedbackSubmission,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit feedback from beta users"""

    # Create feedback entry
    feedback = Feedback(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        type=feedback_data.type,
        category=feedback_data.category,
        title=feedback_data.title,
        description=feedback_data.description,
        severity=feedback_data.severity,
        url=feedback_data.url,
        metadata={
            "screenshot": feedback_data.screenshot_url,
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent")
        },
        browser_info=feedback_data.browser_info
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    # Notify team for critical issues
    if feedback_data.severity == "critical":
        background_tasks.add_task(
            notify_team,
            f"Critical feedback received from {current_user.email}",
            {
                "feedback_id": str(feedback.id),
                "type": feedback_data.type,
                "description": feedback_data.description[:200],
                "user": current_user.email
            }
        )

    # Track metric
    await track_user_metric(
        user_id=current_user.id,
        event_type="feedback_submitted",
        event_category="feedback",
        event_data={
            "feedback_type": feedback_data.type,
            "severity": feedback_data.severity
        },
        db=db
    )

    return {
        "message": "Feedback received successfully",
        "id": str(feedback.id),
        "status": feedback.status
    }

@router.post("/metrics")
async def track_metrics(
    metrics: List[MetricTracking],
    request: Request,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Track user behavior metrics"""

    tracked_metrics = []

    for metric_data in metrics:
        metric = UserMetric(
            user_id=current_user.id if current_user else None,
            organization_id=current_user.organization_id if current_user else None,
            event_type=metric_data.event_type,
            event_category=metric_data.event_category,
            event_data=metric_data.event_data,
            session_id=metric_data.session_id,
            url=metric_data.url,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host,
            load_time=metric_data.load_time,
            response_time=metric_data.response_time
        )

        db.add(metric)
        tracked_metrics.append(metric)

    db.commit()

    return {
        "tracked": len(tracked_metrics),
        "message": "Metrics tracked successfully"
    }

@router.post("/beta-session")
async def update_beta_session(
    session_data: BetaSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update or create beta testing session"""

    # Find or create active session
    session = db.query(BetaTestSession).filter(
        and_(
            BetaTestSession.user_id == current_user.id,
            BetaTestSession.session_type == session_data.session_type,
            BetaTestSession.status == "active"
        )
    ).first()

    if not session:
        session = BetaTestSession(
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            session_type=session_data.session_type,
            milestones_completed=[],
            total_milestones=10  # Default milestone count
        )
        db.add(session)

    # Update session data
    if session_data.milestone_completed:
        if session_data.milestone_completed not in session.milestones_completed:
            session.milestones_completed.append(session_data.milestone_completed)

        # Calculate completion rate
        session.completion_rate = int((len(session.milestones_completed) / session.total_milestones) * 100)

        # Mark as completed if all milestones done
        if len(session.milestones_completed) >= session.total_milestones:
            session.status = "completed"
            session.completed_at = datetime.utcnow()

    if session_data.satisfaction_score:
        session.satisfaction_score = session_data.satisfaction_score

    if session_data.nps_score:
        session.nps_score = session_data.nps_score

    if session_data.feedback_notes:
        session.feedback_notes = session_data.feedback_notes

    session.errors_encountered += session_data.errors_encountered or 0
    session.help_requests += session_data.help_requests or 0
    session.last_activity_at = datetime.utcnow()

    db.commit()
    db.refresh(session)

    return {
        "session_id": str(session.id),
        "completion_rate": session.completion_rate,
        "status": session.status
    }

@router.get("/dashboard")
async def get_feedback_dashboard(
    timeframe: str = "30d",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dashboard de métricas para el equipo"""

    # Only allow admin users
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Calculate date range
    days = int(timeframe.replace('d', ''))
    start_date = datetime.utcnow() - timedelta(days=days)

    # Get beta metrics
    metrics = await calculate_beta_metrics(db, start_date)

    return BetaMetricsResponse(**metrics)

@router.get("/feedback")
async def get_feedback_list(
    status: Optional[str] = None,
    type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get feedback submissions with filters"""

    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    query = db.query(Feedback).join(User)

    if status:
        query = query.filter(Feedback.status == status)
    if type:
        query = query.filter(Feedback.type == type)
    if severity:
        query = query.filter(Feedback.severity == severity)

    total = query.count()
    feedback_items = query.order_by(Feedback.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [
            FeedbackResponse(
                id=str(fb.id),
                type=fb.type,
                category=fb.category,
                title=fb.title,
                description=fb.description,
                severity=fb.severity,
                status=fb.status,
                created_at=fb.created_at,
                user_name=fb.user.email
            )
            for fb in feedback_items
        ]
    }

@router.patch("/feedback/{feedback_id}")
async def update_feedback_status(
    feedback_id: str,
    status: str,
    assigned_to: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update feedback status"""

    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    feedback.status = status
    feedback.updated_at = datetime.utcnow()

    if assigned_to:
        feedback.assigned_to = assigned_to

    if status in ["resolved", "closed"]:
        feedback.resolved_at = datetime.utcnow()

    db.commit()

    return {"message": "Feedback updated successfully", "status": feedback.status}

# Helper functions
async def track_user_metric(
    user_id: str,
    event_type: str,
    event_category: str,
    event_data: Dict[str, Any],
    db: Session,
    session_id: Optional[str] = None
):
    """Helper to track user metrics"""

    metric = UserMetric(
        user_id=user_id,
        event_type=event_type,
        event_category=event_category,
        event_data=event_data,
        session_id=session_id
    )

    db.add(metric)
    db.commit()

async def calculate_beta_metrics(db: Session, start_date: datetime) -> Dict[str, Any]:
    """Calculate comprehensive beta testing metrics"""

    # Total beta users
    total_beta_users = db.query(User).filter(
        User.created_at >= start_date
    ).count()

    # Active beta users (users with activity in last 7 days)
    active_date = datetime.utcnow() - timedelta(days=7)
    active_beta_users = db.query(User).filter(
        User.last_login >= active_date
    ).count()

    # Activation rate (users who created at least one agent)
    activated_users = db.query(User).join(
        UserMetric, User.id == UserMetric.user_id
    ).filter(
        and_(
            UserMetric.event_type == "agent_created",
            UserMetric.timestamp >= start_date
        )
    ).distinct().count()

    activation_rate = (activated_users / total_beta_users * 100) if total_beta_users > 0 else 0

    # Time to first agent
    ttfa_metrics = db.query(UserMetric).filter(
        and_(
            UserMetric.event_type == "agent_created",
            UserMetric.timestamp >= start_date
        )
    ).all()

    avg_ttfa = 0
    if ttfa_metrics:
        ttfa_times = []
        for metric in ttfa_metrics:
            user = db.query(User).filter(User.id == metric.user_id).first()
            if user:
                time_diff = (metric.timestamp - user.created_at).total_seconds() / 60
                ttfa_times.append(time_diff)
        avg_ttfa = sum(ttfa_times) / len(ttfa_times) if ttfa_times else 0

    # Workflow success rate
    workflow_created = db.query(UserMetric).filter(
        and_(
            UserMetric.event_type == "workflow_created",
            UserMetric.timestamp >= start_date
        )
    ).count()

    workflow_executed = db.query(UserMetric).filter(
        and_(
            UserMetric.event_type == "workflow_executed",
            UserMetric.timestamp >= start_date
        )
    ).count()

    success_rate = (workflow_executed / workflow_created * 100) if workflow_created > 0 else 0

    # NPS Score
    nps_scores = db.query(BetaTestSession.nps_score).filter(
        and_(
            BetaTestSession.nps_score.isnot(None),
            BetaTestSession.started_at >= start_date
        )
    ).all()

    avg_nps = sum([score[0] for score in nps_scores]) / len(nps_scores) if nps_scores else 0

    # Top issues
    top_issues = db.query(
        Feedback.category,
        func.count(Feedback.id).label('count')
    ).filter(
        and_(
            Feedback.type == "bug",
            Feedback.created_at >= start_date
        )
    ).group_by(Feedback.category).order_by(func.count(Feedback.id).desc()).limit(5).all()

    # Feature requests
    feature_requests = db.query(
        Feedback.category,
        func.count(Feedback.id).label('count')
    ).filter(
        and_(
            Feedback.type == "feature_request",
            Feedback.created_at >= start_date
        )
    ).group_by(Feedback.category).order_by(func.count(Feedback.id).desc()).limit(5).all()

    return {
        "total_beta_users": total_beta_users,
        "active_beta_users": active_beta_users,
        "activation_rate": round(activation_rate, 2),
        "avg_time_to_first_agent": round(avg_ttfa, 2),
        "workflow_success_rate": round(success_rate, 2),
        "nps_score": round(avg_nps, 2),
        "top_issues": [{"category": issue[0], "count": issue[1]} for issue in top_issues],
        "feature_requests": [{"category": req[0], "count": req[1]} for req in feature_requests]
    }