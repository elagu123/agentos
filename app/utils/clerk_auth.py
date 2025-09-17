from typing import Optional, Dict, Any
import httpx
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models import User

security = HTTPBearer()


class ClerkAuth:
    def __init__(self):
        self.secret_key = settings.clerk_secret_key
        self.base_url = "https://api.clerk.dev/v1"
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token with Clerk
        Returns user data if valid, None if invalid
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/me",
                    headers={**self.headers, "Authorization": f"Bearer {token}"}
                )

                if response.status_code == 200:
                    return response.json()
                return None
        except Exception:
            return None

    async def get_user_info(self, clerk_user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user information from Clerk
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users/{clerk_user_id}",
                    headers=self.headers
                )

                if response.status_code == 200:
                    return response.json()
                return None
        except Exception:
            return None

    async def create_or_update_user(
        self,
        db: AsyncSession,
        clerk_user_data: Dict[str, Any]
    ) -> User:
        """
        Create or update user from Clerk data
        """
        clerk_id = clerk_user_data["id"]
        email = None

        # Extract email from email_addresses
        if "email_addresses" in clerk_user_data and clerk_user_data["email_addresses"]:
            primary_email = next(
                (ea for ea in clerk_user_data["email_addresses"] if ea.get("id") == clerk_user_data.get("primary_email_address_id")),
                clerk_user_data["email_addresses"][0]
            )
            email = primary_email.get("email_address")

        # Check if user exists
        result = await db.execute(select(User).where(User.clerk_id == clerk_id))
        user = result.scalar_one_or_none()

        if user:
            # Update existing user
            user.email = email or user.email
            user.first_name = clerk_user_data.get("first_name") or user.first_name
            user.last_name = clerk_user_data.get("last_name") or user.last_name
        else:
            # Create new user
            user = User(
                clerk_id=clerk_id,
                email=email,
                first_name=clerk_user_data.get("first_name"),
                last_name=clerk_user_data.get("last_name")
            )
            db.add(user)

        await db.commit()
        await db.refresh(user)
        return user


clerk_auth = ClerkAuth()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current authenticated user
    """
    token = credentials.credentials

    # Verify token with Clerk
    clerk_user_data = await clerk_auth.verify_token(token)
    if not clerk_user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Create or update user in our database
    try:
        user = await clerk_auth.create_or_update_user(db, clerk_user_data)
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing user data: {str(e)}"
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise return None
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def require_organization_member(user: User = Depends(get_current_user)) -> User:
    """
    Require user to be a member of an organization
    """
    if not user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required"
        )
    return user


def require_organization_admin(user: User = Depends(get_current_user)) -> User:
    """
    Require user to be an admin of their organization
    """
    if not user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required"
        )

    if not user.is_organization_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin privileges required"
        )

    return user


def require_organization_owner(user: User = Depends(get_current_user)) -> User:
    """
    Require user to be the owner of their organization
    """
    if not user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required"
        )

    if not user.is_organization_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization owner privileges required"
        )

    return user