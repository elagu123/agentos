"""
Security Middleware for AgentOS
Comprehensive security features including rate limiting, input validation, and request sanitization
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import json
import logging
import re
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict, deque
from datetime import datetime, timedelta
import ipaddress

logger = logging.getLogger(__name__)

class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive security middleware that provides:
    - Rate limiting per IP and endpoint
    - Input validation and sanitization
    - XSS protection
    - SQL injection detection
    - Path traversal prevention
    - Request size limits
    """

    def __init__(
        self,
        app,
        rate_limit_requests: int = 100,  # requests per minute
        rate_limit_window: int = 60,     # window in seconds
        max_request_size: int = 10 * 1024 * 1024,  # 10MB
        blocked_user_agents: Optional[List[str]] = None,
        allowed_origins: Optional[List[str]] = None,
        enable_xss_protection: bool = True,
        enable_sql_injection_detection: bool = True,
        enable_path_traversal_detection: bool = True
    ):
        super().__init__(app)
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window = rate_limit_window
        self.max_request_size = max_request_size
        self.blocked_user_agents = blocked_user_agents or []
        self.allowed_origins = allowed_origins or []
        self.enable_xss_protection = enable_xss_protection
        self.enable_sql_injection_detection = enable_sql_injection_detection
        self.enable_path_traversal_detection = enable_path_traversal_detection

        # Rate limiting storage
        self.request_counts: Dict[str, deque] = defaultdict(lambda: deque())
        self.blocked_ips: Dict[str, datetime] = {}

        # Security patterns
        self.xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>.*?</iframe>',
            r'<object[^>]*>.*?</object>',
            r'<embed[^>]*>.*?</embed>'
        ]

        self.sql_injection_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)",
            r"(UNION\s+SELECT)",
            r"(\'\s*OR\s+\'\d+\'\s*=\s*\'\d+)",
            r"(\'\s*OR\s+\d+\s*=\s*\d+)",
            r"(--\s*$)",
            r"(/\*.*?\*/)",
            r"(\'\s*;\s*DROP)",
            r"(\bxp_cmdshell\b)"
        ]

        self.path_traversal_patterns = [
            r'\.\./',
            r'\.\.\\',
            r'\.\./\.\.',
            r'\.\.\\\.\.',
            r'%2e%2e%2f',
            r'%2e%2e/',
            r'\.\.%2f',
            r'%2e%2e%5c'
        ]

        # Sensitive endpoints that need extra protection
        self.sensitive_endpoints = {
            "/api/v1/auth",
            "/api/v1/onboarding",
            "/api/v1/orchestration/execute",
            "/api/v1/monitoring/optimize",
            "/api/v1/monitoring/cache/clear"
        }

    async def dispatch(self, request: Request, call_next):
        """Main middleware processing function"""
        try:
            # Get client IP
            client_ip = self._get_client_ip(request)

            # Check if IP is blocked
            if self._is_ip_blocked(client_ip):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "IP temporarily blocked due to suspicious activity"}
                )

            # Check user agent
            if self._is_blocked_user_agent(request):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Blocked user agent"}
                )

            # Check request size
            if not await self._check_request_size(request):
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": "Request too large"}
                )

            # Rate limiting
            if not self._check_rate_limit(client_ip, request.url.path):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded",
                        "retry_after": self.rate_limit_window
                    }
                )

            # Security validation for requests with body
            if request.method in ["POST", "PUT", "PATCH"]:
                if not await self._validate_request_security(request):
                    self._block_ip_temporarily(client_ip)
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"detail": "Request contains potentially malicious content"}
                    )

            # Process the request
            response = await call_next(request)

            # Add security headers
            self._add_security_headers(response)

            return response

        except Exception as e:
            logger.error(f"Security middleware error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal security error"}
            )

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def _is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is temporarily blocked"""
        if ip in self.blocked_ips:
            if datetime.now() < self.blocked_ips[ip]:
                return True
            else:
                del self.blocked_ips[ip]
        return False

    def _block_ip_temporarily(self, ip: str, duration_minutes: int = 15):
        """Temporarily block an IP address"""
        self.blocked_ips[ip] = datetime.now() + timedelta(minutes=duration_minutes)
        logger.warning(f"IP {ip} blocked temporarily for {duration_minutes} minutes")

    def _is_blocked_user_agent(self, request: Request) -> bool:
        """Check if user agent is blocked"""
        user_agent = request.headers.get("User-Agent", "").lower()
        return any(blocked in user_agent for blocked in self.blocked_user_agents)

    async def _check_request_size(self, request: Request) -> bool:
        """Check if request size is within limits"""
        content_length = request.headers.get("Content-Length")
        if content_length:
            return int(content_length) <= self.max_request_size
        return True

    def _check_rate_limit(self, ip: str, path: str) -> bool:
        """Check rate limiting per IP and path"""
        now = time.time()
        window_start = now - self.rate_limit_window

        # Clean old entries
        request_times = self.request_counts[f"{ip}:{path}"]
        while request_times and request_times[0] < window_start:
            request_times.popleft()

        # Check if under limit
        if len(request_times) >= self.rate_limit_requests:
            return False

        # Add current request
        request_times.append(now)
        return True

    async def _validate_request_security(self, request: Request) -> bool:
        """Validate request for security threats"""
        try:
            # Read request body
            body = await request.body()
            if not body:
                return True

            # Try to parse as JSON
            try:
                data = json.loads(body.decode('utf-8'))
                content = json.dumps(data).lower()
            except:
                content = body.decode('utf-8', errors='ignore').lower()

            # Check for XSS
            if self.enable_xss_protection and self._contains_xss(content):
                logger.warning(f"XSS attempt detected from {self._get_client_ip(request)}")
                return False

            # Check for SQL injection
            if self.enable_sql_injection_detection and self._contains_sql_injection(content):
                logger.warning(f"SQL injection attempt detected from {self._get_client_ip(request)}")
                return False

            # Check for path traversal
            if self.enable_path_traversal_detection and self._contains_path_traversal(content):
                logger.warning(f"Path traversal attempt detected from {self._get_client_ip(request)}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating request security: {str(e)}")
            return False

    def _contains_xss(self, content: str) -> bool:
        """Check for XSS patterns"""
        for pattern in self.xss_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def _contains_sql_injection(self, content: str) -> bool:
        """Check for SQL injection patterns"""
        for pattern in self.sql_injection_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def _contains_path_traversal(self, content: str) -> bool:
        """Check for path traversal patterns"""
        for pattern in self.path_traversal_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def _add_security_headers(self, response):
        """Add security headers to response"""
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }

        for header, value in security_headers.items():
            response.headers[header] = value


class InputSanitizer:
    """Input sanitization utilities"""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            return str(value)[:max_length]

        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\'\\\x00-\x1f\x7f-\x9f]', '', value)
        return sanitized[:max_length]

    @staticmethod
    def sanitize_dict(data: Dict[str, Any], max_depth: int = 10) -> Dict[str, Any]:
        """Recursively sanitize dictionary data"""
        if max_depth <= 0:
            return {}

        sanitized = {}
        for key, value in data.items():
            # Sanitize key
            clean_key = InputSanitizer.sanitize_string(str(key), 100)

            # Sanitize value based on type
            if isinstance(value, str):
                sanitized[clean_key] = InputSanitizer.sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[clean_key] = InputSanitizer.sanitize_dict(value, max_depth - 1)
            elif isinstance(value, list):
                sanitized[clean_key] = [
                    InputSanitizer.sanitize_string(str(item))
                    if isinstance(item, str) else item
                    for item in value[:100]  # Limit list size
                ]
            else:
                sanitized[clean_key] = value

        return sanitized