"""
Analytics service for AgentOS
Collects, processes and analyzes user behavior and system metrics
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from ..models.user import User, Organization
from ..models.feedback import UserMetric, BetaTestSession, BetaMetrics
from ..database import get_db

class AnalyticsService:
    """Service for collecting and analyzing user behavior"""

    def __init__(self, db: Session):
        self.db = db

    async def track_event(
        self,
        user_id: str,
        event_type: str,
        event_category: str,
        event_data: Dict[str, Any] = None,
        session_id: str = None,
        url: str = None,
        user_agent: str = None,
        ip_address: str = None
    ) -> UserMetric:
        """
        Track a user event

        Args:
            user_id: User performing the action
            event_type: Type of event (e.g., 'agent_created', 'workflow_executed')
            event_category: Category (navigation, interaction, conversion, error)
            event_data: Additional event data
            session_id: Browser session ID
            url: URL where event occurred
            user_agent: User's browser info
            ip_address: User's IP address

        Returns:
            Created UserMetric object
        """

        user = self.db.query(User).filter(User.id == user_id).first()
        organization_id = user.organization_id if user else None

        metric = UserMetric(
            user_id=user_id,
            organization_id=organization_id,
            event_type=event_type,
            event_category=event_category,
            event_data=event_data or {},
            session_id=session_id,
            url=url,
            user_agent=user_agent,
            ip_address=ip_address
        )

        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)

        # Update user's last activity
        if user:
            user.last_activity_at = datetime.utcnow()
            self.db.commit()

        return metric

    async def calculate_time_to_first_agent(self, user_id: str) -> Optional[float]:
        """
        Calculate time from user signup to first agent creation

        Args:
            user_id: User ID

        Returns:
            Time in minutes, or None if no agent created yet
        """

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        first_agent_event = self.db.query(UserMetric).filter(
            and_(
                UserMetric.user_id == user_id,
                UserMetric.event_type == "agent_created"
            )
        ).order_by(UserMetric.timestamp.asc()).first()

        if not first_agent_event:
            return None

        time_diff = first_agent_event.timestamp - user.created_at
        return time_diff.total_seconds() / 60  # Convert to minutes

    async def calculate_user_activation(self, user_id: str) -> Dict[str, Any]:
        """
        Calculate user activation metrics

        Args:
            user_id: User ID

        Returns:
            Dict with activation metrics
        """

        # Define activation criteria
        activation_events = [
            "agent_created",
            "workflow_created",
            "workflow_executed",
            "template_installed"
        ]

        metrics = {}
        for event_type in activation_events:
            count = self.db.query(UserMetric).filter(
                and_(
                    UserMetric.user_id == user_id,
                    UserMetric.event_type == event_type
                )
            ).count()
            metrics[event_type] = count

        # Calculate activation score (0-100)
        activation_score = 0
        if metrics["agent_created"] > 0:
            activation_score += 25
        if metrics["workflow_created"] > 0:
            activation_score += 25
        if metrics["workflow_executed"] > 0:
            activation_score += 30
        if metrics["template_installed"] > 0:
            activation_score += 20

        return {
            "activation_score": activation_score,
            "is_activated": activation_score >= 50,
            "events": metrics
        }

    async def calculate_retention_rates(
        self,
        cohort_start: datetime,
        cohort_end: datetime
    ) -> Dict[str, float]:
        """
        Calculate retention rates for a user cohort

        Args:
            cohort_start: Start date of cohort
            cohort_end: End date of cohort

        Returns:
            Dict with retention rates
        """

        # Get users in cohort
        cohort_users = self.db.query(User).filter(
            and_(
                User.created_at >= cohort_start,
                User.created_at <= cohort_end
            )
        ).all()

        if not cohort_users:
            return {"day_1": 0, "day_7": 0, "day_30": 0}

        total_users = len(cohort_users)

        # Calculate retention for different periods
        retention_rates = {}
        periods = {"day_1": 1, "day_7": 7, "day_30": 30}

        for period_name, days in periods.items():
            active_users = 0

            for user in cohort_users:
                # Check if user was active N days after signup
                target_date = user.created_at + timedelta(days=days)
                activity_count = self.db.query(UserMetric).filter(
                    and_(
                        UserMetric.user_id == user.id,
                        UserMetric.timestamp >= target_date,
                        UserMetric.timestamp <= target_date + timedelta(days=1)
                    )
                ).count()

                if activity_count > 0:
                    active_users += 1

            retention_rates[period_name] = (active_users / total_users) * 100

        return retention_rates

    async def calculate_feature_adoption(
        self,
        timeframe_days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate feature adoption rates

        Args:
            timeframe_days: Number of days to analyze

        Returns:
            Dict with feature adoption metrics
        """

        start_date = datetime.utcnow() - timedelta(days=timeframe_days)

        # Get all users active in timeframe
        active_users = self.db.query(User).join(UserMetric).filter(
            UserMetric.timestamp >= start_date
        ).distinct().count()

        if active_users == 0:
            return {}

        # Feature adoption events
        features = {
            "agent_creation": "agent_created",
            "workflow_builder": "workflow_created",
            "marketplace": "template_viewed",
            "template_installation": "template_installed",
            "automation_execution": "workflow_executed",
            "collaboration": "workspace_shared"
        }

        adoption_rates = {}

        for feature_name, event_type in features.items():
            users_using_feature = self.db.query(User).join(UserMetric).filter(
                and_(
                    UserMetric.event_type == event_type,
                    UserMetric.timestamp >= start_date
                )
            ).distinct().count()

            adoption_rates[feature_name] = {
                "users": users_using_feature,
                "rate": (users_using_feature / active_users) * 100 if active_users > 0 else 0
            }

        return adoption_rates

    async def generate_daily_metrics(self, date: datetime = None) -> BetaMetrics:
        """
        Generate and store daily aggregated metrics

        Args:
            date: Date to generate metrics for (default: yesterday)

        Returns:
            Created BetaMetrics object
        """

        if date is None:
            date = datetime.utcnow() - timedelta(days=1)

        # Calculate metrics for the day
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        # Total beta users
        total_beta_users = self.db.query(User).filter(
            User.is_beta_user == True
        ).count()

        # Active beta users (users with activity on this day)
        active_beta_users = self.db.query(User).join(UserMetric).filter(
            and_(
                User.is_beta_user == True,
                UserMetric.timestamp >= start_of_day,
                UserMetric.timestamp < end_of_day
            )
        ).distinct().count()

        # New signups
        new_signups = self.db.query(User).filter(
            and_(
                User.is_beta_user == True,
                User.created_at >= start_of_day,
                User.created_at < end_of_day
            )
        ).count()

        # Calculate activation rate
        if total_beta_users > 0:
            activated_users = 0
            for user in self.db.query(User).filter(User.is_beta_user == True).all():
                activation = await self.calculate_user_activation(str(user.id))
                if activation["is_activated"]:
                    activated_users += 1
            activation_rate = (activated_users / total_beta_users) * 100
        else:
            activation_rate = 0

        # Average session duration (in minutes)
        session_durations = []
        sessions = self.db.query(BetaTestSession).filter(
            and_(
                BetaTestSession.last_activity_at >= start_of_day,
                BetaTestSession.last_activity_at < end_of_day
            )
        ).all()

        for session in sessions:
            if session.completed_at:
                duration = (session.completed_at - session.started_at).total_seconds() / 60
                session_durations.append(duration)

        avg_session_duration = sum(session_durations) / len(session_durations) if session_durations else 0

        # Time to first agent
        ttfa_times = []
        new_users = self.db.query(User).filter(
            and_(
                User.is_beta_user == True,
                User.created_at >= start_of_day - timedelta(days=7),  # Look at last week's users
                User.created_at < end_of_day
            )
        ).all()

        for user in new_users:
            ttfa = await self.calculate_time_to_first_agent(str(user.id))
            if ttfa is not None:
                ttfa_times.append(ttfa)

        avg_ttfa = sum(ttfa_times) / len(ttfa_times) if ttfa_times else 0

        # Workflow creation rate
        users_with_workflows = self.db.query(User).join(UserMetric).filter(
            and_(
                User.is_beta_user == True,
                UserMetric.event_type == "workflow_created",
                UserMetric.timestamp >= start_of_day,
                UserMetric.timestamp < end_of_day
            )
        ).distinct().count()

        workflow_creation_rate = (users_with_workflows / active_beta_users * 100) if active_beta_users > 0 else 0

        # Feature adoption rates
        feature_adoption = await self.calculate_feature_adoption(1)  # For this day

        # Quality metrics
        bug_reports = self.db.query(UserMetric).filter(
            and_(
                UserMetric.event_type == "feedback_submitted",
                UserMetric.event_data["feedback_type"].astext == "bug",
                UserMetric.timestamp >= start_of_day,
                UserMetric.timestamp < end_of_day
            )
        ).count()

        critical_issues = self.db.query(UserMetric).filter(
            and_(
                UserMetric.event_type == "feedback_submitted",
                UserMetric.event_data["severity"].astext == "critical",
                UserMetric.timestamp >= start_of_day,
                UserMetric.timestamp < end_of_day
            )
        ).count()

        feature_requests = self.db.query(UserMetric).filter(
            and_(
                UserMetric.event_type == "feedback_submitted",
                UserMetric.event_data["feedback_type"].astext == "feature_request",
                UserMetric.timestamp >= start_of_day,
                UserMetric.timestamp < end_of_day
            )
        ).count()

        # Satisfaction scores
        satisfaction_scores = self.db.query(BetaTestSession.satisfaction_score).filter(
            and_(
                BetaTestSession.satisfaction_score.isnot(None),
                BetaTestSession.last_activity_at >= start_of_day,
                BetaTestSession.last_activity_at < end_of_day
            )
        ).all()

        avg_satisfaction = sum([score[0] for score in satisfaction_scores]) / len(satisfaction_scores) if satisfaction_scores else 0

        # NPS scores
        nps_scores = self.db.query(BetaTestSession.nps_score).filter(
            and_(
                BetaTestSession.nps_score.isnot(None),
                BetaTestSession.last_activity_at >= start_of_day,
                BetaTestSession.last_activity_at < end_of_day
            )
        ).all()

        avg_nps = sum([score[0] for score in nps_scores]) / len(nps_scores) if nps_scores else 0

        # Create daily metrics record
        daily_metrics = BetaMetrics(
            metric_date=start_of_day,
            total_beta_users=total_beta_users,
            active_beta_users=active_beta_users,
            new_signups=new_signups,
            activation_rate=int(activation_rate),
            avg_session_duration=int(avg_session_duration),
            avg_time_to_first_agent=int(avg_ttfa),
            workflow_creation_rate=int(workflow_creation_rate),
            feature_adoption_rates=feature_adoption,
            bug_reports=bug_reports,
            critical_issues=critical_issues,
            feature_requests=feature_requests,
            avg_satisfaction_score=int(avg_satisfaction),
            nps_score=int(avg_nps),
            system_uptime=100,  # Would be calculated from monitoring
            avg_response_time=500,  # Would be calculated from monitoring
            error_rate=0  # Would be calculated from monitoring
        )

        self.db.add(daily_metrics)
        self.db.commit()
        self.db.refresh(daily_metrics)

        return daily_metrics

    async def get_analytics_summary(
        self,
        timeframe_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive analytics summary

        Args:
            timeframe_days: Number of days to analyze

        Returns:
            Dict with analytics summary
        """

        start_date = datetime.utcnow() - timedelta(days=timeframe_days)

        # Get latest daily metrics
        latest_metrics = self.db.query(BetaMetrics).order_by(
            BetaMetrics.metric_date.desc()
        ).first()

        # Calculate trends
        previous_period_start = start_date - timedelta(days=timeframe_days)
        previous_metrics = self.db.query(BetaMetrics).filter(
            and_(
                BetaMetrics.metric_date >= previous_period_start,
                BetaMetrics.metric_date < start_date
            )
        ).all()

        current_metrics = self.db.query(BetaMetrics).filter(
            BetaMetrics.metric_date >= start_date
        ).all()

        # Calculate averages and trends
        summary = {
            "overview": {
                "total_beta_users": latest_metrics.total_beta_users if latest_metrics else 0,
                "active_beta_users": latest_metrics.active_beta_users if latest_metrics else 0,
                "activation_rate": latest_metrics.activation_rate if latest_metrics else 0,
                "nps_score": latest_metrics.nps_score if latest_metrics else 0
            },
            "trends": {},
            "feature_adoption": latest_metrics.feature_adoption_rates if latest_metrics else {},
            "quality_metrics": {
                "bug_reports": sum([m.bug_reports for m in current_metrics]),
                "critical_issues": sum([m.critical_issues for m in current_metrics]),
                "feature_requests": sum([m.feature_requests for m in current_metrics]),
                "avg_satisfaction": latest_metrics.avg_satisfaction_score if latest_metrics else 0
            }
        }

        return summary

# Convenience functions
async def track_user_event(
    db: Session,
    user_id: str,
    event_type: str,
    event_category: str = "interaction",
    event_data: Dict[str, Any] = None,
    **kwargs
) -> UserMetric:
    """Track a user event"""
    analytics = AnalyticsService(db)
    return await analytics.track_event(
        user_id=user_id,
        event_type=event_type,
        event_category=event_category,
        event_data=event_data,
        **kwargs
    )

async def generate_daily_analytics() -> None:
    """Generate daily analytics (can be run as a scheduled task)"""
    db = next(get_db())
    analytics = AnalyticsService(db)

    try:
        await analytics.generate_daily_metrics()
        print(f"Daily metrics generated for {datetime.utcnow().date()}")
    except Exception as e:
        print(f"Error generating daily metrics: {str(e)}")
    finally:
        db.close()