"""
Authentication and Authorization Manager for AgentOS
Robust authentication with 2FA, JWT tokens, API keys, and RBAC
"""

from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets
import pyotp
import qrcode
import io
import base64
import hashlib
import hmac
import time
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from dataclasses import dataclass, field
from enum import Enum
import re

logger = logging.getLogger(__name__)

class UserRole(Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    API_USER = "api_user"

class SessionStatus(Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"

@dataclass
class AuthConfig:
    # JWT settings
    secret_key: str = secrets.token_urlsafe(32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Password settings
    min_password_length: int = 8
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_numbers: bool = True
    require_special_chars: bool = True
    password_history_count: int = 5

    # 2FA settings
    totp_issuer: str = "AgentOS"
    totp_window: int = 1  # Allow ±30 seconds
    backup_codes_count: int = 10

    # Session settings
    max_sessions_per_user: int = 5
    session_timeout_hours: int = 24
    remember_me_days: int = 30

    # Security settings
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    require_2fa_for_admin: bool = True
    force_password_change_days: int = 90

@dataclass
class LoginAttempt:
    identifier: str
    ip_address: str
    user_agent: str
    success: bool
    timestamp: datetime
    failure_reason: Optional[str] = None

@dataclass
class UserSession:
    session_id: str
    user_id: str
    ip_address: str
    user_agent: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    status: SessionStatus
    remember_me: bool = False
    device_fingerprint: Optional[str] = None

class AuthManager:
    def __init__(self, config: AuthConfig = None):
        self.config = config or AuthConfig()
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12
        )

        # Security components
        self.security = HTTPBearer()
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

        # In-memory stores (in production, use Redis)
        self.active_sessions: Dict[str, UserSession] = {}
        self.login_attempts: List[LoginAttempt] = []
        self.password_reset_tokens: Dict[str, Dict] = {}
        self.email_verification_tokens: Dict[str, Dict] = {}

        # Rate limiting for auth endpoints
        self.login_attempts_by_ip: Dict[str, List[datetime]] = {}
        self.failed_attempts_by_user: Dict[str, List[datetime]] = {}

    # === Password Management ===

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self.pwd_context.verify(plain_password, hashed_password)

    def validate_password_strength(self, password: str, user_email: str = "") -> Tuple[bool, List[str]]:
        """Validate password strength and return issues"""

        issues = []

        # Length check
        if len(password) < self.config.min_password_length:
            issues.append(f"Password must be at least {self.config.min_password_length} characters long")

        # Character requirements
        if self.config.require_uppercase and not re.search(r'[A-Z]', password):
            issues.append("Password must contain at least one uppercase letter")

        if self.config.require_lowercase and not re.search(r'[a-z]', password):
            issues.append("Password must contain at least one lowercase letter")

        if self.config.require_numbers and not re.search(r'\d', password):
            issues.append("Password must contain at least one number")

        if self.config.require_special_chars and not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
            issues.append("Password must contain at least one special character")

        # Common password checks
        common_passwords = [
            "password", "123456", "123456789", "qwerty", "abc123",
            "password123", "admin", "letmein", "welcome", "monkey"
        ]

        if password.lower() in common_passwords:
            issues.append("Password is too common, please choose a more unique password")

        # Personal information check
        if user_email:
            email_parts = user_email.lower().split('@')[0].split('.')
            for part in email_parts:
                if len(part) > 3 and part in password.lower():
                    issues.append("Password should not contain parts of your email address")

        # Pattern checks
        if re.search(r'(.)\1{3,}', password):  # 4+ repeated characters
            issues.append("Password should not contain 4 or more repeated characters")

        if re.search(r'(012|123|234|345|456|567|678|789|890|abc|bcd|cde|def)', password.lower()):
            issues.append("Password should not contain common sequences")

        return len(issues) == 0, issues

    def generate_secure_password(self, length: int = 12) -> str:
        """Generate a secure password"""
        import string

        # Ensure we have at least one of each required character type
        chars = []

        if self.config.require_uppercase:
            chars.append(secrets.choice(string.ascii_uppercase))
        if self.config.require_lowercase:
            chars.append(secrets.choice(string.ascii_lowercase))
        if self.config.require_numbers:
            chars.append(secrets.choice(string.digits))
        if self.config.require_special_chars:
            chars.append(secrets.choice("!@#$%^&*()_+-=[]{}|;:,.<>?"))

        # Fill the rest randomly
        all_chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
        while len(chars) < length:
            chars.append(secrets.choice(all_chars))

        # Shuffle to avoid predictable patterns
        secrets.SystemRandom().shuffle(chars)

        return ''.join(chars)

    # === JWT Token Management ===

    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token"""

        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.config.access_token_expire_minutes)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
            "jti": secrets.token_urlsafe(16)  # JWT ID for revocation
        })

        encoded_jwt = jwt.encode(
            to_encode,
            self.config.secret_key,
            algorithm=self.config.algorithm
        )

        return encoded_jwt

    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """Create JWT refresh token"""

        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.config.refresh_token_expire_days)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
            "jti": secrets.token_urlsafe(16)
        })

        encoded_jwt = jwt.encode(
            to_encode,
            self.config.secret_key,
            algorithm=self.config.algorithm
        )

        return encoded_jwt

    async def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """Verify and decode JWT token"""

        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm]
            )

            if payload.get("type") != token_type:
                raise credentials_exception

            # Check if token is revoked (in production, check against Redis)
            jti = payload.get("jti")
            if jti and await self._is_token_revoked(jti):
                raise credentials_exception

            return payload

        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            raise credentials_exception

    async def _is_token_revoked(self, jti: str) -> bool:
        """Check if token is revoked (implement with Redis in production)"""
        # Placeholder - implement with Redis blacklist
        return False

    async def revoke_token(self, jti: str, expiry: Optional[datetime] = None):
        """Revoke token by adding to blacklist"""
        # Implement with Redis in production
        pass

    # === Two-Factor Authentication ===

    def generate_2fa_secret(self) -> str:
        """Generate 2FA secret key"""
        return pyotp.random_base32()

    def generate_2fa_qr_code(self, user_email: str, secret: str) -> str:
        """Generate QR code for 2FA setup"""

        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user_email,
            issuer_name=self.config.totp_issuer
        )

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4
        )
        qr.add_data(totp_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_base64}"

    def verify_2fa_token(self, secret: str, token: str) -> bool:
        """Verify 2FA TOTP token"""

        totp = pyotp.TOTP(secret)

        # Allow for clock skew
        return totp.verify(token, valid_window=self.config.totp_window)

    def generate_backup_codes(self) -> List[str]:
        """Generate backup codes for 2FA"""

        codes = []
        for _ in range(self.config.backup_codes_count):
            # Format: XXXX-XXXX
            code = f"{secrets.randbelow(10000):04d}-{secrets.randbelow(10000):04d}"
            codes.append(code)

        return codes

    def verify_backup_code(self, stored_codes: List[str], provided_code: str) -> Tuple[bool, List[str]]:
        """Verify backup code and remove it from list"""

        if provided_code in stored_codes:
            remaining_codes = [code for code in stored_codes if code != provided_code]
            return True, remaining_codes

        return False, stored_codes

    # === Session Management ===

    async def create_session(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        remember_me: bool = False,
        device_fingerprint: Optional[str] = None
    ) -> str:
        """Create user session"""

        session_id = secrets.token_urlsafe(32)

        # Calculate expiry
        if remember_me:
            expires_at = datetime.utcnow() + timedelta(days=self.config.remember_me_days)
        else:
            expires_at = datetime.utcnow() + timedelta(hours=self.config.session_timeout_hours)

        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            expires_at=expires_at,
            status=SessionStatus.ACTIVE,
            remember_me=remember_me,
            device_fingerprint=device_fingerprint
        )

        # Limit sessions per user
        await self._cleanup_user_sessions(user_id)

        self.active_sessions[session_id] = session

        logger.info(f"Created session {session_id} for user {user_id}")

        return session_id

    async def verify_session(self, session_id: str) -> Optional[UserSession]:
        """Verify and update session"""

        session = self.active_sessions.get(session_id)

        if not session:
            return None

        # Check expiry
        if datetime.utcnow() > session.expires_at:
            session.status = SessionStatus.EXPIRED
            del self.active_sessions[session_id]
            return None

        # Check status
        if session.status != SessionStatus.ACTIVE:
            return None

        # Update last activity
        session.last_activity = datetime.utcnow()

        return session

    async def revoke_session(self, session_id: str, reason: str = "user_logout"):
        """Revoke session"""

        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.status = SessionStatus.REVOKED
            del self.active_sessions[session_id]

            logger.info(f"Revoked session {session_id}: {reason}")

    async def revoke_all_user_sessions(self, user_id: str, except_session: Optional[str] = None):
        """Revoke all sessions for a user"""

        sessions_to_revoke = []

        for session_id, session in self.active_sessions.items():
            if session.user_id == user_id and session_id != except_session:
                sessions_to_revoke.append(session_id)

        for session_id in sessions_to_revoke:
            await self.revoke_session(session_id, "admin_revoke_all")

        logger.info(f"Revoked {len(sessions_to_revoke)} sessions for user {user_id}")

    async def _cleanup_user_sessions(self, user_id: str):
        """Clean up old sessions for user to stay within limit"""

        user_sessions = [
            (session_id, session)
            for session_id, session in self.active_sessions.items()
            if session.user_id == user_id and session.status == SessionStatus.ACTIVE
        ]

        if len(user_sessions) >= self.config.max_sessions_per_user:
            # Sort by last activity and remove oldest
            user_sessions.sort(key=lambda x: x[1].last_activity)

            sessions_to_remove = len(user_sessions) - self.config.max_sessions_per_user + 1

            for i in range(sessions_to_remove):
                session_id, _ = user_sessions[i]
                await self.revoke_session(session_id, "session_limit_exceeded")

    # === API Key Management ===

    def generate_api_key(self, prefix: str = "aos") -> Tuple[str, str]:
        """Generate API key and return (key, hash)"""

        # Format: prefix_environment_random
        # Example: aos_prod_k7h3j5k2l9m4n6p8q1r2s3t4

        environment = "prod"  # Could be "dev", "test", etc.
        random_part = secrets.token_urlsafe(20)

        api_key = f"{prefix}_{environment}_{random_part}"

        # Hash for storage
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        return api_key, key_hash

    async def verify_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Verify API key and return key info"""

        # Hash the provided key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # In production, lookup in database
        # For now, return mock data
        return {
            "key_id": "mock_key_id",
            "user_id": "mock_user_id",
            "name": "Mock API Key",
            "scopes": ["read", "write"],
            "is_active": True,
            "last_used_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=365)
        }

    # === Role-Based Access Control (RBAC) ===

    def check_permission(
        self,
        user_role: UserRole,
        resource: str,
        action: str,
        resource_owner_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Check if user has permission for action on resource"""

        # Define permissions matrix
        permissions = {
            UserRole.ADMIN: {
                "*": ["*"]  # Admin has access to everything
            },
            UserRole.USER: {
                "agents": ["read", "create", "update", "delete"],
                "workflows": ["read", "create", "update", "delete"],
                "executions": ["read", "create"],
                "marketplace": ["read", "publish"],
                "billing": ["read"],
                "profile": ["read", "update"],
                "api_keys": ["read", "create", "delete"],
                "sessions": ["read", "delete"]
            },
            UserRole.VIEWER: {
                "agents": ["read"],
                "workflows": ["read"],
                "executions": ["read"],
                "marketplace": ["read"],
                "profile": ["read"],
                "billing": ["read"]
            },
            UserRole.API_USER: {
                "agents": ["read", "create", "update", "delete"],
                "workflows": ["read", "create", "update", "delete"],
                "executions": ["read", "create"],
                "marketplace": ["read"]
            }
        }

        user_permissions = permissions.get(user_role, {})

        # Check wildcard permission (admin)
        if "*" in user_permissions and "*" in user_permissions["*"]:
            return True

        # Check specific resource permission
        if resource in user_permissions:
            allowed_actions = user_permissions[resource]

            if "*" in allowed_actions or action in allowed_actions:
                # Additional check for resource ownership
                if resource_owner_id and user_id and resource_owner_id != user_id:
                    # Only admins can access other users' resources
                    return user_role == UserRole.ADMIN

                return True

        return False

    def get_user_permissions(self, user_role: UserRole) -> Dict[str, List[str]]:
        """Get all permissions for a user role"""

        permissions = {
            UserRole.ADMIN: {"*": ["*"]},
            UserRole.USER: {
                "agents": ["read", "create", "update", "delete"],
                "workflows": ["read", "create", "update", "delete"],
                "executions": ["read", "create"],
                "marketplace": ["read", "publish"],
                "billing": ["read"],
                "profile": ["read", "update"],
                "api_keys": ["read", "create", "delete"],
                "sessions": ["read", "delete"]
            },
            UserRole.VIEWER: {
                "agents": ["read"],
                "workflows": ["read"],
                "executions": ["read"],
                "marketplace": ["read"],
                "profile": ["read"],
                "billing": ["read"]
            },
            UserRole.API_USER: {
                "agents": ["read", "create", "update", "delete"],
                "workflows": ["read", "create", "update", "delete"],
                "executions": ["read", "create"],
                "marketplace": ["read"]
            }
        }

        return permissions.get(user_role, {})

    # === Login Attempt Tracking ===

    async def track_login_attempt(
        self,
        identifier: str,
        ip_address: str,
        user_agent: str,
        success: bool,
        failure_reason: Optional[str] = None
    ):
        """Track login attempt"""

        attempt = LoginAttempt(
            identifier=identifier,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            timestamp=datetime.utcnow(),
            failure_reason=failure_reason
        )

        self.login_attempts.append(attempt)

        # Keep only recent attempts (last 24 hours)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.login_attempts = [
            attempt for attempt in self.login_attempts
            if attempt.timestamp > cutoff
        ]

        # Track by IP and user for rate limiting
        if not success:
            # Track by IP
            if ip_address not in self.login_attempts_by_ip:
                self.login_attempts_by_ip[ip_address] = []
            self.login_attempts_by_ip[ip_address].append(datetime.utcnow())

            # Track by user
            if identifier not in self.failed_attempts_by_user:
                self.failed_attempts_by_user[identifier] = []
            self.failed_attempts_by_user[identifier].append(datetime.utcnow())

    async def is_account_locked(self, identifier: str) -> Tuple[bool, Optional[datetime]]:
        """Check if account is locked due to failed attempts"""

        if identifier not in self.failed_attempts_by_user:
            return False, None

        # Check recent failed attempts
        cutoff = datetime.utcnow() - timedelta(minutes=self.config.lockout_duration_minutes)
        recent_failures = [
            attempt for attempt in self.failed_attempts_by_user[identifier]
            if attempt > cutoff
        ]

        if len(recent_failures) >= self.config.max_login_attempts:
            # Account is locked, calculate unlock time
            latest_failure = max(recent_failures)
            unlock_time = latest_failure + timedelta(minutes=self.config.lockout_duration_minutes)
            return True, unlock_time

        return False, None

    async def is_ip_rate_limited(self, ip_address: str) -> bool:
        """Check if IP is rate limited"""

        if ip_address not in self.login_attempts_by_ip:
            return False

        # Allow max 20 attempts per hour from same IP
        cutoff = datetime.utcnow() - timedelta(hours=1)
        recent_attempts = [
            attempt for attempt in self.login_attempts_by_ip[ip_address]
            if attempt > cutoff
        ]

        return len(recent_attempts) >= 20

    async def reset_failed_attempts(self, identifier: str):
        """Reset failed login attempts for user"""

        if identifier in self.failed_attempts_by_user:
            del self.failed_attempts_by_user[identifier]

    # === Password Reset ===

    def generate_password_reset_token(self, user_id: str, email: str) -> str:
        """Generate password reset token"""

        token = secrets.token_urlsafe(32)

        self.password_reset_tokens[token] = {
            "user_id": user_id,
            "email": email,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=1),
            "used": False
        }

        return token

    async def verify_password_reset_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify password reset token"""

        token_data = self.password_reset_tokens.get(token)

        if not token_data:
            return None

        if token_data["used"]:
            return None

        if datetime.utcnow() > token_data["expires_at"]:
            del self.password_reset_tokens[token]
            return None

        return token_data

    async def use_password_reset_token(self, token: str):
        """Mark password reset token as used"""

        if token in self.password_reset_tokens:
            self.password_reset_tokens[token]["used"] = True

    # === Email Verification ===

    def generate_email_verification_token(self, user_id: str, email: str) -> str:
        """Generate email verification token"""

        token = secrets.token_urlsafe(32)

        self.email_verification_tokens[token] = {
            "user_id": user_id,
            "email": email,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=24),
            "verified": False
        }

        return token

    async def verify_email_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify email verification token"""

        token_data = self.email_verification_tokens.get(token)

        if not token_data:
            return None

        if token_data["verified"]:
            return None

        if datetime.utcnow() > token_data["expires_at"]:
            del self.email_verification_tokens[token]
            return None

        # Mark as verified
        token_data["verified"] = True

        return token_data

    # === Security Headers ===

    def get_security_headers(self) -> Dict[str, str]:
        """Get security headers for responses"""

        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()"
        }

    # === Utility Methods ===

    def generate_device_fingerprint(self, request: Request) -> str:
        """Generate device fingerprint for session tracking"""

        # Combine user agent, accept headers, and other characteristics
        fingerprint_data = [
            request.headers.get("user-agent", ""),
            request.headers.get("accept", ""),
            request.headers.get("accept-language", ""),
            request.headers.get("accept-encoding", ""),
            str(request.client.host if request.client else "")
        ]

        fingerprint_string = "|".join(fingerprint_data)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:16]

    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed session information"""

        session = self.active_sessions.get(session_id)

        if not session:
            return None

        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "status": session.status.value,
            "remember_me": session.remember_me,
            "device_fingerprint": session.device_fingerprint
        }

    async def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user"""

        user_sessions = []

        for session_id, session in self.active_sessions.items():
            if session.user_id == user_id and session.status == SessionStatus.ACTIVE:
                session_info = await self.get_session_info(session_id)
                if session_info:
                    user_sessions.append(session_info)

        return user_sessions

    def mask_sensitive_data(self, data: str, show_chars: int = 4) -> str:
        """Mask sensitive data for display"""

        if len(data) <= show_chars * 2:
            return "*" * len(data)

        return data[:show_chars] + "*" * (len(data) - show_chars * 2) + data[-show_chars:]

# Global instance
auth_manager = AuthManager()

# FastAPI Dependencies
async def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Security(auth_manager.security)
) -> Dict[str, Any]:
    """FastAPI dependency to get current user from JWT token"""

    token = credentials.credentials
    payload = await auth_manager.verify_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    # In production, fetch user from database
    return {
        "id": user_id,
        "email": payload.get("email"),
        "role": UserRole(payload.get("role", "user")),
        "is_active": True,
        "email_verified": payload.get("email_verified", False),
        "2fa_enabled": payload.get("2fa_enabled", False)
    }

async def get_current_user_from_session(
    request: Request
) -> Optional[Dict[str, Any]]:
    """Get current user from session cookie"""

    session_id = request.cookies.get("session_id")
    if not session_id:
        return None

    session = await auth_manager.verify_session(session_id)
    if not session:
        return None

    # In production, fetch user from database
    return {
        "id": session.user_id,
        "session_id": session_id
    }

def require_permission(resource: str, action: str):
    """FastAPI dependency factory for permission checking"""

    async def permission_checker(
        current_user: Dict = Depends(get_current_user_from_token)
    ):
        user_role = current_user.get("role", UserRole.USER)
        user_id = current_user.get("id")

        if not auth_manager.check_permission(user_role, resource, action, user_id=user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {action} on {resource}"
            )

        return current_user

    return permission_checker

def require_2fa(
    current_user: Dict = Depends(get_current_user_from_token)
):
    """Require 2FA for sensitive operations"""

    if not current_user.get("2fa_enabled"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Two-factor authentication required for this operation"
        )

    return current_user

async def verify_api_key_dependency(
    request: Request
) -> Dict[str, Any]:
    """FastAPI dependency for API key authentication"""

    # Check Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )

    api_key = auth_header.split(" ")[1]
    key_info = await auth_manager.verify_api_key(api_key)

    if not key_info or not key_info.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key"
        )

    return key_info