#!/usr/bin/env python3
"""
Beta Onboarding Script
Automated onboarding process for beta testers
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, Organization
from app.models.feedback import BetaInvite, FeatureFlag, BetaTestSession
from app.utils.email import send_email
from app.utils.password import generate_temp_password
import uuid

class BetaOnboardingManager:
    """Manage beta user onboarding process"""

    def __init__(self, db: Session):
        self.db = db

    async def onboard_beta_user(
        self,
        email: str,
        company_name: str,
        beta_type: str = "general",
        features: List[str] = None
    ) -> Dict[str, Any]:
        """
        Complete onboarding process for beta tester
        """

        if features is None:
            features = [
                "principal_agent",
                "5_subagents",
                "workflow_builder",
                "marketplace_readonly"
            ]

        try:
            # 1. Check if user already exists
            existing_user = self.db.query(User).filter(User.email == email).first()
            if existing_user:
                return {"error": f"User {email} already exists"}

            # 2. Create beta invite
            invite_token = str(uuid.uuid4())
            invite = BetaInvite(
                email=email,
                company_name=company_name,
                token=invite_token,
                beta_type=beta_type,
                features_enabled=features,
                limits={
                    "agents": 10,
                    "workflows": 20,
                    "executions_per_day": 1000,
                    "api_calls_per_day": 5000
                },
                expires_at=datetime.utcnow() + timedelta(days=30)
            )

            self.db.add(invite)
            self.db.commit()
            self.db.refresh(invite)

            # 3. Create organization with beta limits
            org = Organization(
                name=company_name,
                plan="beta",
                settings={
                    "beta_features": features,
                    "limits": invite.limits,
                    "beta_start_date": datetime.utcnow().isoformat()
                }
            )

            self.db.add(org)
            self.db.commit()
            self.db.refresh(org)

            # 4. Generate temporary password
            temp_password = generate_temp_password()

            # 5. Create user account
            user = User(
                email=email,
                organization_id=org.id,
                is_beta_user=True,
                role="admin",
                metadata={
                    "beta_invite_id": str(invite.id),
                    "onboarding_status": "invited",
                    "temp_password": temp_password
                }
            )

            # Set password
            user.set_password(temp_password)

            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

            # 6. Update invite with user ID
            invite.status = "accepted"
            invite.accepted_at = datetime.utcnow()
            self.db.commit()

            # 7. Activate beta features
            await self.activate_features(user.id, features)

            # 8. Create initial beta test session
            session = BetaTestSession(
                user_id=user.id,
                organization_id=org.id,
                session_type="onboarding",
                total_milestones=8,  # Standard onboarding milestones
                milestones_completed=[]
            )

            self.db.add(session)
            self.db.commit()

            # 9. Send welcome email
            email_result = await self.send_welcome_email(
                email=email,
                company_name=company_name,
                temp_password=temp_password,
                invite_token=invite_token
            )

            # 10. Schedule follow-up emails
            await self.schedule_follow_ups(user.id, email)

            return {
                "success": True,
                "user_id": str(user.id),
                "organization_id": str(org.id),
                "invite_id": str(invite.id),
                "temp_password": temp_password,
                "email_sent": email_result
            }

        except Exception as e:
            self.db.rollback()
            return {"error": f"Failed to onboard user: {str(e)}"}

    async def activate_features(self, user_id: str, features: List[str]):
        """Activate specific features for beta user"""

        for feature_name in features:
            # Check if feature flag exists
            flag = self.db.query(FeatureFlag).filter(
                FeatureFlag.name == feature_name
            ).first()

            if not flag:
                # Create feature flag if it doesn't exist
                flag = FeatureFlag(
                    name=feature_name,
                    description=f"Beta feature: {feature_name}",
                    is_enabled=True,
                    rollout_percentage=100,
                    target_users=[user_id]
                )
                self.db.add(flag)
            else:
                # Add user to target users
                if user_id not in flag.target_users:
                    flag.target_users.append(user_id)

        self.db.commit()

    async def send_welcome_email(
        self,
        email: str,
        company_name: str,
        temp_password: str,
        invite_token: str
    ) -> Dict[str, Any]:
        """Send welcome email to beta user"""

        try:
            email_data = {
                "company_name": company_name,
                "login_url": f"https://app.agentos.ai/login",
                "temp_password": temp_password,
                "onboarding_link": f"https://app.agentos.ai/beta/onboard?token={invite_token}",
                "calendar_link": "https://cal.com/agentos/onboarding",
                "documentation_link": "https://docs.agentos.ai/beta",
                "support_email": "beta@agentos.ai"
            }

            await send_email(
                to=email,
                subject="🚀 Bienvenido al Beta de AgentOS",
                template="beta_welcome",
                data=email_data
            )

            return {"success": True, "email_sent": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def schedule_follow_ups(self, user_id: str, email: str):
        """Schedule follow-up emails and check-ins"""

        # Day 1: Getting started tips
        # Day 3: First workflow check
        # Day 7: Weekly check-in
        # Day 14: Feature discovery
        # Day 30: Beta feedback survey

        follow_ups = [
            {"day": 1, "template": "beta_day1_tips"},
            {"day": 3, "template": "beta_workflow_check"},
            {"day": 7, "template": "beta_weekly_checkin"},
            {"day": 14, "template": "beta_feature_discovery"},
            {"day": 30, "template": "beta_feedback_survey"}
        ]

        # In a real implementation, you would use a task queue like Celery
        # For now, we'll log the scheduled follow-ups
        print(f"Scheduled {len(follow_ups)} follow-up emails for user {user_id}")

    async def collect_beta_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive beta testing metrics"""

        metrics = {
            "activation_rate": 0,
            "time_to_value": [],
            "feature_adoption": {},
            "satisfaction_scores": [],
            "completion_rates": [],
            "error_rates": []
        }

        # Get all beta users
        beta_users = self.db.query(User).filter(User.is_beta_user == True).all()

        if not beta_users:
            return metrics

        activated_users = 0
        total_users = len(beta_users)

        for user in beta_users:
            # Check activation (created at least one agent)
            # This would query the actual agent creation events
            # For now, we'll use a placeholder

            # Get user's beta session
            session = self.db.query(BetaTestSession).filter(
                BetaTestSession.user_id == user.id
            ).first()

            if session:
                # Time to value (time to complete first milestone)
                if session.milestones_completed:
                    ttv = (session.last_activity_at - session.started_at).total_seconds() / 60
                    metrics["time_to_value"].append(ttv)
                    activated_users += 1

                # Completion rate
                if session.total_milestones > 0:
                    completion_rate = len(session.milestones_completed) / session.total_milestones
                    metrics["completion_rates"].append(completion_rate)

                # Satisfaction scores
                if session.satisfaction_score:
                    metrics["satisfaction_scores"].append(session.satisfaction_score)

        # Calculate averages
        metrics["activation_rate"] = (activated_users / total_users) * 100 if total_users > 0 else 0
        metrics["avg_time_to_value"] = sum(metrics["time_to_value"]) / len(metrics["time_to_value"]) if metrics["time_to_value"] else 0
        metrics["avg_completion_rate"] = sum(metrics["completion_rates"]) / len(metrics["completion_rates"]) if metrics["completion_rates"] else 0
        metrics["avg_satisfaction"] = sum(metrics["satisfaction_scores"]) / len(metrics["satisfaction_scores"]) if metrics["satisfaction_scores"] else 0

        return metrics

    async def generate_beta_report(self) -> Dict[str, Any]:
        """Generate comprehensive beta testing report"""

        metrics = await self.collect_beta_metrics()

        # Get feedback summary
        total_feedback = self.db.query(User).join(
            User.feedback
        ).filter(User.is_beta_user == True).count()

        bug_reports = self.db.query(User).join(
            User.feedback
        ).filter(
            User.is_beta_user == True,
            User.feedback.any(type="bug")
        ).count()

        feature_requests = self.db.query(User).join(
            User.feedback
        ).filter(
            User.is_beta_user == True,
            User.feedback.any(type="feature_request")
        ).count()

        return {
            "summary": {
                "total_beta_users": self.db.query(User).filter(User.is_beta_user == True).count(),
                "activation_rate": f"{metrics['activation_rate']:.1f}%",
                "avg_time_to_value": f"{metrics['avg_time_to_value']:.1f} minutes",
                "avg_satisfaction": f"{metrics['avg_satisfaction']:.1f}/10"
            },
            "feedback": {
                "total_submissions": total_feedback,
                "bug_reports": bug_reports,
                "feature_requests": feature_requests
            },
            "recommendations": [
                "Focus on reducing time to first agent creation",
                "Improve onboarding flow based on completion rates",
                "Address top bug reports from feedback",
                "Enhance documentation for common issues"
            ]
        }

# CLI interface
async def main():
    """Main CLI interface for beta onboarding"""

    if len(sys.argv) < 2:
        print("Usage: python beta_onboarding.py <command> [args]")
        print("Commands:")
        print("  onboard <email> <company_name> - Onboard new beta user")
        print("  metrics - Show beta metrics")
        print("  report - Generate beta testing report")
        print("  bulk-onboard <file> - Onboard users from CSV file")
        return

    # Get database session
    db = next(get_db())
    manager = BetaOnboardingManager(db)

    command = sys.argv[1]

    try:
        if command == "onboard":
            if len(sys.argv) < 4:
                print("Usage: python beta_onboarding.py onboard <email> <company_name>")
                return

            email = sys.argv[2]
            company_name = sys.argv[3]

            print(f"Onboarding beta user: {email} from {company_name}")
            result = await manager.onboard_beta_user(email, company_name)

            if result.get("success"):
                print("✅ Beta user onboarded successfully!")
                print(f"User ID: {result['user_id']}")
                print(f"Temp Password: {result['temp_password']}")
            else:
                print(f"❌ Onboarding failed: {result.get('error')}")

        elif command == "metrics":
            print("Collecting beta metrics...")
            metrics = await manager.collect_beta_metrics()

            print("\n📊 Beta Testing Metrics:")
            print(f"Activation Rate: {metrics['activation_rate']:.1f}%")
            print(f"Avg Time to Value: {metrics['avg_time_to_value']:.1f} minutes")
            print(f"Avg Completion Rate: {metrics['avg_completion_rate']:.1f}%")
            print(f"Avg Satisfaction: {metrics['avg_satisfaction']:.1f}/10")

        elif command == "report":
            print("Generating beta testing report...")
            report = await manager.generate_beta_report()

            print("\n📋 Beta Testing Report:")
            print("Summary:")
            for key, value in report["summary"].items():
                print(f"  {key}: {value}")

            print("\nFeedback:")
            for key, value in report["feedback"].items():
                print(f"  {key}: {value}")

            print("\nRecommendations:")
            for rec in report["recommendations"]:
                print(f"  - {rec}")

        elif command == "bulk-onboard":
            if len(sys.argv) < 3:
                print("Usage: python beta_onboarding.py bulk-onboard <csv_file>")
                return

            # Implement bulk onboarding from CSV
            print("Bulk onboarding not implemented yet")

        else:
            print(f"Unknown command: {command}")

    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    # Predefined beta testers for quick onboarding
    BETA_TESTERS = [
        {"email": "owner@techstyle.com", "company": "TechStyle Store"},
        {"email": "founder@cloudmetrics.com", "company": "CloudMetrics"},
        {"email": "ceo@automate.pro", "company": "AutomatePro"},
        {"email": "admin@digitalsolutions.com", "company": "Digital Solutions"},
        {"email": "manager@innovatetech.com", "company": "InnovateTech"}
    ]

    # If no arguments provided, show help and offer to onboard predefined testers
    if len(sys.argv) == 1:
        print("🚀 AgentOS Beta Onboarding Manager")
        print("\nPredefined beta testers available:")
        for i, tester in enumerate(BETA_TESTERS, 1):
            print(f"  {i}. {tester['email']} - {tester['company']}")

        choice = input("\nOnboard all predefined testers? (y/n): ")
        if choice.lower() == 'y':
            async def onboard_all():
                db = next(get_db())
                manager = BetaOnboardingManager(db)

                for tester in BETA_TESTERS:
                    print(f"\nOnboarding {tester['email']}...")
                    result = await manager.onboard_beta_user(
                        tester["email"],
                        tester["company"]
                    )

                    if result.get("success"):
                        print(f"✅ {tester['email']} onboarded successfully")
                    else:
                        print(f"❌ Failed to onboard {tester['email']}: {result.get('error')}")

                db.close()

            asyncio.run(onboard_all())
        else:
            asyncio.run(main())
    else:
        asyncio.run(main())