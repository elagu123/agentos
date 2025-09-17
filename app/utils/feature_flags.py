"""
Feature flags system for AgentOS
Manages beta features and rollout controls
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from ..models.feedback import FeatureFlag
from ..models.user import User

class FeatureFlagService:
    """Service for managing feature flags"""

    def __init__(self, db: Session):
        self.db = db

    def is_feature_enabled(
        self,
        feature_name: str,
        user_id: str = None,
        organization_id: str = None
    ) -> bool:
        """
        Check if a feature is enabled for a user/organization

        Args:
            feature_name: Name of the feature
            user_id: User ID to check
            organization_id: Organization ID to check

        Returns:
            True if feature is enabled, False otherwise
        """

        flag = self.db.query(FeatureFlag).filter(
            FeatureFlag.name == feature_name
        ).first()

        if not flag:
            return False

        # Global disable
        if not flag.is_enabled:
            return False

        # Check if user is specifically targeted
        if user_id and user_id in flag.target_users:
            return True

        # Check if organization is specifically targeted
        if organization_id and organization_id in flag.target_organizations:
            return True

        # Check rollout percentage
        if flag.rollout_percentage >= 100:
            return True

        if flag.rollout_percentage <= 0:
            return False

        # Use hash-based consistent rollout
        if user_id:
            user_hash = hash(f"{feature_name}:{user_id}") % 100
            return user_hash < flag.rollout_percentage

        return False

    def get_enabled_features(
        self,
        user_id: str = None,
        organization_id: str = None
    ) -> List[str]:
        """
        Get list of enabled features for a user/organization

        Args:
            user_id: User ID
            organization_id: Organization ID

        Returns:
            List of enabled feature names
        """

        enabled_features = []
        flags = self.db.query(FeatureFlag).filter(
            FeatureFlag.is_enabled == True
        ).all()

        for flag in flags:
            if self.is_feature_enabled(flag.name, user_id, organization_id):
                enabled_features.append(flag.name)

        return enabled_features

    def create_feature_flag(
        self,
        name: str,
        description: str = None,
        is_enabled: bool = False,
        rollout_percentage: int = 0,
        target_users: List[str] = None,
        target_organizations: List[str] = None,
        created_by: str = None
    ) -> FeatureFlag:
        """
        Create a new feature flag

        Args:
            name: Feature flag name
            description: Feature description
            is_enabled: Whether feature is globally enabled
            rollout_percentage: Percentage rollout (0-100)
            target_users: Specific user IDs to target
            target_organizations: Specific org IDs to target
            created_by: User ID who created the flag

        Returns:
            Created FeatureFlag object
        """

        flag = FeatureFlag(
            name=name,
            description=description,
            is_enabled=is_enabled,
            rollout_percentage=rollout_percentage,
            target_users=target_users or [],
            target_organizations=target_organizations or [],
            created_by=created_by
        )

        self.db.add(flag)
        self.db.commit()
        self.db.refresh(flag)

        return flag

    def update_feature_flag(
        self,
        feature_name: str,
        **updates
    ) -> Optional[FeatureFlag]:
        """
        Update an existing feature flag

        Args:
            feature_name: Name of the feature to update
            **updates: Fields to update

        Returns:
            Updated FeatureFlag object or None if not found
        """

        flag = self.db.query(FeatureFlag).filter(
            FeatureFlag.name == feature_name
        ).first()

        if not flag:
            return None

        for key, value in updates.items():
            if hasattr(flag, key):
                setattr(flag, key, value)

        self.db.commit()
        self.db.refresh(flag)

        return flag

    def add_user_to_feature(
        self,
        feature_name: str,
        user_id: str
    ) -> bool:
        """
        Add a user to a feature flag's target list

        Args:
            feature_name: Name of the feature
            user_id: User ID to add

        Returns:
            True if successful, False if feature not found
        """

        flag = self.db.query(FeatureFlag).filter(
            FeatureFlag.name == feature_name
        ).first()

        if not flag:
            return False

        if user_id not in flag.target_users:
            flag.target_users.append(user_id)
            self.db.commit()

        return True

    def remove_user_from_feature(
        self,
        feature_name: str,
        user_id: str
    ) -> bool:
        """
        Remove a user from a feature flag's target list

        Args:
            feature_name: Name of the feature
            user_id: User ID to remove

        Returns:
            True if successful, False if feature not found
        """

        flag = self.db.query(FeatureFlag).filter(
            FeatureFlag.name == feature_name
        ).first()

        if not flag:
            return False

        if user_id in flag.target_users:
            flag.target_users.remove(user_id)
            self.db.commit()

        return True

# Beta feature definitions
BETA_FEATURES = {
    "principal_agent": {
        "name": "principal_agent",
        "description": "Principal agent creation and management",
        "default_enabled": True,
        "rollout_percentage": 100
    },
    "5_subagents": {
        "name": "5_subagents",
        "description": "Create up to 5 specialized sub-agents",
        "default_enabled": True,
        "rollout_percentage": 100
    },
    "workflow_builder": {
        "name": "workflow_builder",
        "description": "Visual workflow builder interface",
        "default_enabled": True,
        "rollout_percentage": 100
    },
    "marketplace_readonly": {
        "name": "marketplace_readonly",
        "description": "Read-only access to template marketplace",
        "default_enabled": True,
        "rollout_percentage": 100
    },
    "marketplace_publish": {
        "name": "marketplace_publish",
        "description": "Ability to publish templates to marketplace",
        "default_enabled": False,
        "rollout_percentage": 50
    },
    "advanced_analytics": {
        "name": "advanced_analytics",
        "description": "Advanced analytics and reporting",
        "default_enabled": False,
        "rollout_percentage": 25
    },
    "api_access": {
        "name": "api_access",
        "description": "REST API access for integrations",
        "default_enabled": True,
        "rollout_percentage": 100
    },
    "webhook_triggers": {
        "name": "webhook_triggers",
        "description": "Webhook-based workflow triggers",
        "default_enabled": True,
        "rollout_percentage": 80
    },
    "collaborative_workspaces": {
        "name": "collaborative_workspaces",
        "description": "Team collaboration features",
        "default_enabled": False,
        "rollout_percentage": 10
    },
    "custom_integrations": {
        "name": "custom_integrations",
        "description": "Custom third-party integrations",
        "default_enabled": False,
        "rollout_percentage": 30
    }
}

def initialize_beta_features(db: Session) -> Dict[str, Any]:
    """
    Initialize beta feature flags in the database

    Args:
        db: Database session

    Returns:
        Dict with initialization results
    """

    results = {
        "created": 0,
        "updated": 0,
        "errors": []
    }

    service = FeatureFlagService(db)

    for feature_key, feature_config in BETA_FEATURES.items():
        try:
            existing = db.query(FeatureFlag).filter(
                FeatureFlag.name == feature_config["name"]
            ).first()

            if existing:
                # Update existing feature
                service.update_feature_flag(
                    feature_config["name"],
                    description=feature_config["description"],
                    is_enabled=feature_config["default_enabled"],
                    rollout_percentage=feature_config["rollout_percentage"]
                )
                results["updated"] += 1
            else:
                # Create new feature
                service.create_feature_flag(
                    name=feature_config["name"],
                    description=feature_config["description"],
                    is_enabled=feature_config["default_enabled"],
                    rollout_percentage=feature_config["rollout_percentage"]
                )
                results["created"] += 1

        except Exception as e:
            results["errors"].append({
                "feature": feature_key,
                "error": str(e)
            })

    return results

# Convenience functions
def check_feature(
    db: Session,
    feature_name: str,
    user_id: str = None,
    organization_id: str = None
) -> bool:
    """Check if a feature is enabled for a user/organization"""
    service = FeatureFlagService(db)
    return service.is_feature_enabled(feature_name, user_id, organization_id)

def get_user_features(
    db: Session,
    user_id: str,
    organization_id: str = None
) -> List[str]:
    """Get enabled features for a user"""
    service = FeatureFlagService(db)
    return service.get_enabled_features(user_id, organization_id)