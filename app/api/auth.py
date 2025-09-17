from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import UserProfile
from app.utils import get_current_user, get_optional_user

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user profile"""
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        full_name=current_user.full_name,
        role=current_user.role,
        is_organization_owner=current_user.is_organization_owner,
        is_organization_admin=current_user.is_organization_admin,
        organization_id=current_user.organization_id
    )


@router.get("/status")
async def get_auth_status(
    current_user: User = Depends(get_optional_user)
):
    """Get authentication status"""
    if current_user:
        return {
            "authenticated": True,
            "user_id": str(current_user.id),
            "has_organization": current_user.organization_id is not None,
            "is_onboarded": current_user.is_onboarded
        }
    else:
        return {
            "authenticated": False,
            "user_id": None,
            "has_organization": False,
            "is_onboarded": False
        }