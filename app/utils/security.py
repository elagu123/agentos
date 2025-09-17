"""
Security utilities for template validation and content scanning.
"""
import re
import json
import ast
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class SecurityScanResult:
    """Result of a security scan."""
    is_safe: bool
    issues: List[str]
    warnings: List[str]
    risk_level: str  # low, medium, high, critical


class TemplateSecurityValidator:
    """
    Validates template security by scanning for potential malicious content.
    """

    # Dangerous patterns to look for
    DANGEROUS_PATTERNS = [
        # Code execution patterns
        r'eval\s*\(',
        r'exec\s*\(',
        r'__import__\s*\(',
        r'compile\s*\(',
        r'globals\s*\(',
        r'locals\s*\(',

        # File system access
        r'open\s*\(',
        r'file\s*\(',
        r'\.read\s*\(',
        r'\.write\s*\(',
        r'\.delete\s*\(',

        # Network access
        r'urllib',
        r'requests\.',
        r'http\.',
        r'socket\.',

        # System commands
        r'os\.system',
        r'subprocess',
        r'popen',
        r'shell=True',

        # Environment access
        r'os\.environ',
        r'getenv',

        # SQL injection patterns
        r'DROP\s+TABLE',
        r'DELETE\s+FROM',
        r'UPDATE\s+\w+\s+SET',
        r'UNION\s+SELECT',

        # Script injection
        r'<script\b',
        r'javascript:',
        r'onload\s*=',
        r'onerror\s*=',
    ]

    # Suspicious URL patterns
    SUSPICIOUS_URLS = [
        r'data:text/html',
        r'javascript:',
        r'vbscript:',
        r'file://',
        r'ftp://',
    ]

    # Allowed webhook domains (whitelist)
    ALLOWED_WEBHOOK_DOMAINS = [
        'api.openai.com',
        'api.anthropic.com',
        'hooks.slack.com',
        'discord.com',
        'teams.microsoft.com',
        'zapier.com',
        'ifttt.com',
        'n8n.io',
        'make.com',
    ]

    def __init__(self):
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.DANGEROUS_PATTERNS]
        self.compiled_url_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.SUSPICIOUS_URLS]

    def validate_workflow(self, workflow_definition: Dict[str, Any]) -> SecurityScanResult:
        """
        Validate a complete workflow definition for security issues.
        """
        issues = []
        warnings = []
        risk_level = "low"

        try:
            # Convert workflow to string for pattern matching
            workflow_str = json.dumps(workflow_definition, indent=2)

            # Scan for dangerous patterns
            pattern_issues = self._scan_dangerous_patterns(workflow_str)
            issues.extend(pattern_issues)

            # Validate individual steps
            if 'steps' in workflow_definition:
                for i, step in enumerate(workflow_definition['steps']):
                    step_issues, step_warnings = self._validate_step(step, i)
                    issues.extend(step_issues)
                    warnings.extend(step_warnings)

            # Validate connections for injection attempts
            if 'connections' in workflow_definition:
                connection_issues = self._validate_connections(workflow_definition['connections'])
                issues.extend(connection_issues)

            # Validate variables for injection
            for var_type in ['input_variables', 'output_variables']:
                if var_type in workflow_definition:
                    var_issues = self._validate_variables(workflow_definition[var_type])
                    issues.extend(var_issues)

            # Determine risk level
            if any('CRITICAL' in issue for issue in issues):
                risk_level = "critical"
            elif any('HIGH' in issue for issue in issues):
                risk_level = "high"
            elif any('MEDIUM' in issue for issue in issues):
                risk_level = "medium"
            elif issues:
                risk_level = "medium"

            return SecurityScanResult(
                is_safe=len(issues) == 0,
                issues=issues,
                warnings=warnings,
                risk_level=risk_level
            )

        except Exception as e:
            return SecurityScanResult(
                is_safe=False,
                issues=[f"CRITICAL: Failed to parse workflow definition: {str(e)}"],
                warnings=[],
                risk_level="critical"
            )

    def _scan_dangerous_patterns(self, content: str) -> List[str]:
        """Scan content for dangerous patterns."""
        issues = []

        for pattern in self.compiled_patterns:
            matches = pattern.findall(content)
            if matches:
                issues.append(f"HIGH: Potentially dangerous code pattern detected: {pattern.pattern}")

        return issues

    def _validate_step(self, step: Dict[str, Any], step_index: int) -> tuple[List[str], List[str]]:
        """Validate an individual workflow step."""
        issues = []
        warnings = []

        step_type = step.get('type', 'unknown')
        config = step.get('config', {})

        # Validate based on step type
        if step_type == 'webhook':
            webhook_issues, webhook_warnings = self._validate_webhook_step(config)
            issues.extend(webhook_issues)
            warnings.extend(webhook_warnings)

        elif step_type == 'agent_task':
            agent_issues, agent_warnings = self._validate_agent_step(config)
            issues.extend(agent_issues)
            warnings.extend(agent_warnings)

        elif step_type == 'data_transformation':
            transform_issues = self._validate_transformation_step(config)
            issues.extend(transform_issues)

        # Validate task/prompt content for injection
        task_content = config.get('task', '') or config.get('prompt', '')
        if task_content:
            prompt_issues = self._validate_prompt_content(task_content)
            issues.extend([f"Step {step_index + 1}: {issue}" for issue in prompt_issues])

        return issues, warnings

    def _validate_webhook_step(self, config: Dict[str, Any]) -> tuple[List[str], List[str]]:
        """Validate webhook step configuration."""
        issues = []
        warnings = []

        webhook_url = config.get('webhook_url', '')
        if not webhook_url:
            return issues, warnings

        try:
            parsed_url = urlparse(webhook_url)

            # Check for suspicious URL schemes
            for pattern in self.compiled_url_patterns:
                if pattern.search(webhook_url):
                    issues.append(f"HIGH: Suspicious webhook URL pattern: {webhook_url}")
                    break

            # Validate domain against whitelist for external webhooks
            if parsed_url.netloc and not self._is_allowed_webhook_domain(parsed_url.netloc):
                warnings.append(f"External webhook domain not in whitelist: {parsed_url.netloc}")

            # Check for localhost/internal IPs
            if self._is_internal_url(parsed_url):
                issues.append(f"MEDIUM: Webhook points to internal/localhost URL: {webhook_url}")

        except Exception:
            issues.append(f"MEDIUM: Invalid webhook URL format: {webhook_url}")

        return issues, warnings

    def _validate_agent_step(self, config: Dict[str, Any]) -> tuple[List[str], List[str]]:
        """Validate agent step configuration."""
        issues = []
        warnings = []

        # Check for code injection in agent parameters
        data = config.get('data', {})
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    param_issues = self._validate_prompt_content(value)
                    issues.extend([f"Agent parameter '{key}': {issue}" for issue in param_issues])

        # Validate agent type
        agent_type = config.get('agent_type')
        if agent_type and not self._is_valid_agent_type(agent_type):
            warnings.append(f"Unknown agent type: {agent_type}")

        return issues, warnings

    def _validate_transformation_step(self, config: Dict[str, Any]) -> List[str]:
        """Validate data transformation step."""
        issues = []

        # Check for code in transformation config
        transform_code = config.get('code', '') or config.get('script', '')
        if transform_code:
            # Look for dangerous Python/JS patterns
            code_issues = self._scan_dangerous_patterns(transform_code)
            issues.extend([f"Transformation code: {issue}" for issue in code_issues])

        return issues

    def _validate_connections(self, connections: List[Dict[str, Any]]) -> List[str]:
        """Validate workflow connections for injection attempts."""
        issues = []

        for i, connection in enumerate(connections):
            condition = connection.get('condition')
            if condition and isinstance(condition, dict):
                # Check condition values for injection
                condition_value = str(condition.get('value', ''))
                if condition_value:
                    value_issues = self._validate_prompt_content(condition_value)
                    issues.extend([f"Connection {i + 1} condition: {issue}" for issue in value_issues])

        return issues

    def _validate_variables(self, variables: List[Dict[str, Any]]) -> List[str]:
        """Validate workflow variables for injection."""
        issues = []

        for var in variables:
            # Check default values
            default_value = var.get('default_value')
            if default_value and isinstance(default_value, str):
                var_issues = self._validate_prompt_content(default_value)
                issues.extend([f"Variable '{var.get('name', 'unknown')}': {issue}" for issue in var_issues])

        return issues

    def _validate_prompt_content(self, content: str) -> List[str]:
        """Validate prompt/text content for injection attempts."""
        issues = []

        # Check for dangerous patterns in content
        pattern_issues = self._scan_dangerous_patterns(content)
        issues.extend(pattern_issues)

        # Check for potential prompt injection patterns
        injection_patterns = [
            r'ignore\s+previous\s+instructions',
            r'forget\s+everything',
            r'you\s+are\s+now',
            r'new\s+instructions:',
            r'system\s*:\s*',
            r'admin\s*:\s*',
            r'root\s*:\s*',
        ]

        for pattern in injection_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                issues.append(f"MEDIUM: Potential prompt injection pattern detected")
                break

        return issues

    def _is_allowed_webhook_domain(self, domain: str) -> bool:
        """Check if webhook domain is in the allowed list."""
        domain = domain.lower()
        return any(allowed in domain for allowed in self.ALLOWED_WEBHOOK_DOMAINS)

    def _is_internal_url(self, parsed_url) -> bool:
        """Check if URL points to internal/localhost."""
        hostname = parsed_url.hostname
        if not hostname:
            return False

        internal_patterns = [
            r'^localhost$',
            r'^127\.',
            r'^10\.',
            r'^172\.(1[6-9]|2[0-9]|3[01])\.',
            r'^192\.168\.',
            r'^::1$',
            r'^fc00:',
            r'^fe80:',
        ]

        return any(re.match(pattern, hostname) for pattern in internal_patterns)

    def _is_valid_agent_type(self, agent_type: str) -> bool:
        """Check if agent type is valid."""
        valid_agents = [
            'copywriter',
            'researcher',
            'scheduler',
            'email_responder',
            'data_analyzer'
        ]
        return agent_type in valid_agents


# Global validator instance
template_validator = TemplateSecurityValidator()


async def validate_template_security(workflow_definition: Dict[str, Any]) -> SecurityScanResult:
    """
    Main function to validate template security.
    """
    return template_validator.validate_workflow(workflow_definition)


def sanitize_template_content(content: str) -> str:
    """
    Sanitize template content by removing potentially dangerous elements.
    """
    # Remove script tags
    content = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', content, flags=re.IGNORECASE)

    # Remove javascript: URLs
    content = re.sub(r'javascript:[^"\']*', '', content, flags=re.IGNORECASE)

    # Remove event handlers
    content = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', content, flags=re.IGNORECASE)

    return content
import secrets
import time
from typing import Optional, Dict, Any, List
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import re
import bleach
from urllib.parse import urlparse

from app.config import settings


class SecurityUtils:
    """Collection of security utilities and validators"""

    @staticmethod
    def sanitize_input(text: str, allowed_tags: Optional[List[str]] = None) -> str:
        """
        Sanitize user input to prevent XSS attacks

        Args:
            text: Input text to sanitize
            allowed_tags: List of allowed HTML tags

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Default allowed tags (none for strict sanitization)
        allowed_tags = allowed_tags or []

        # Clean HTML and potentially malicious content
        cleaned_text = bleach.clean(text, tags=allowed_tags, strip=True)

        return cleaned_text

    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email format

        Args:
            email: Email address to validate

        Returns:
            True if valid email format
        """
        if not email:
            return False

        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email) is not None

    @staticmethod
    def validate_url(url: str, allowed_schemes: Optional[List[str]] = None) -> bool:
        """
        Validate URL format and scheme

        Args:
            url: URL to validate
            allowed_schemes: List of allowed URL schemes

        Returns:
            True if valid URL
        """
        if not url:
            return False

        allowed_schemes = allowed_schemes or ['http', 'https']

        try:
            parsed = urlparse(url)
            return (
                parsed.scheme in allowed_schemes and
                bool(parsed.netloc) and
                len(url) <= 2048  # Reasonable URL length limit
            )
        except Exception:
            return False

    @staticmethod
    def validate_file_name(filename: str) -> bool:
        """
        Validate file name for security

        Args:
            filename: File name to validate

        Returns:
            True if safe file name
        """
        if not filename:
            return False

        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            return False

        # Check for dangerous file extensions
        dangerous_extensions = [
            '.exe', '.bat', '.cmd', '.scr', '.pif', '.com',
            '.js', '.jar', '.vbs', '.ps1', '.sh'
        ]

        filename_lower = filename.lower()
        if any(filename_lower.endswith(ext) for ext in dangerous_extensions):
            return False

        # Check filename length
        if len(filename) > 255:
            return False

        return True

    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """
        Generate cryptographically secure random token

        Args:
            length: Length of token in bytes

        Returns:
            Hex-encoded secure token
        """
        return secrets.token_hex(length)

    @staticmethod
    def hash_sensitive_data(data: str, salt: Optional[str] = None) -> Dict[str, str]:
        """
        Hash sensitive data with salt

        Args:
            data: Data to hash
            salt: Optional salt (generated if not provided)

        Returns:
            Dictionary with hash and salt
        """
        if salt is None:
            salt = secrets.token_hex(16)

        # Use SHA-256 for hashing
        hash_obj = hashlib.sha256()
        hash_obj.update((data + salt).encode('utf-8'))
        hashed = hash_obj.hexdigest()

        return {
            "hash": hashed,
            "salt": salt
        }

    @staticmethod
    def verify_hash(data: str, stored_hash: str, salt: str) -> bool:
        """
        Verify data against stored hash

        Args:
            data: Data to verify
            stored_hash: Stored hash
            salt: Salt used for hashing

        Returns:
            True if data matches hash
        """
        try:
            computed = SecurityUtils.hash_sensitive_data(data, salt)
            return computed["hash"] == stored_hash
        except Exception:
            return False


class RequestValidator:
    """Validate and secure incoming requests"""

    def __init__(self):
        self.max_request_size = 10 * 1024 * 1024  # 10MB
        self.max_header_size = 8192  # 8KB
        self.blocked_user_agents = [
            'bot', 'crawler', 'spider', 'scraper'
        ]

    async def validate_request(self, request: Request) -> bool:
        """
        Validate incoming request for security

        Args:
            request: FastAPI request object

        Returns:
            True if request is valid

        Raises:
            HTTPException: If request is invalid
        """
        # Check content length
        content_length = request.headers.get('content-length')
        if content_length and int(content_length) > self.max_request_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request too large"
            )

        # Check for suspicious headers
        self._check_headers(request)

        # Check user agent
        self._check_user_agent(request)

        # Check for common attack patterns
        self._check_attack_patterns(request)

        return True

    def _check_headers(self, request: Request):
        """Check for suspicious headers"""
        for name, value in request.headers.items():
            # Check header size
            if len(name) + len(value) > self.max_header_size:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Header too large"
                )

            # Check for malicious content in headers
            if any(pattern in value.lower() for pattern in ['<script', 'javascript:', 'data:']):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Malicious content detected in headers"
                )

    def _check_user_agent(self, request: Request):
        """Check user agent for suspicious patterns"""
        user_agent = request.headers.get('user-agent', '').lower()

        # Block known malicious user agents
        for blocked_agent in self.blocked_user_agents:
            if blocked_agent in user_agent:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )

    def _check_attack_patterns(self, request: Request):
        """Check for common attack patterns in URL and query parameters"""
        url = str(request.url)
        query_params = str(request.query_params)

        # SQL injection patterns
        sql_patterns = [
            'union select', 'drop table', 'insert into',
            'delete from', 'update set', '--', ';--'
        ]

        # XSS patterns
        xss_patterns = [
            '<script', 'javascript:', 'onclick=', 'onerror=',
            'onload=', 'eval(', 'alert('
        ]

        # Path traversal patterns
        traversal_patterns = [
            '../', '..\\', '%2e%2e%2f', '%2e%2e%5c'
        ]

        all_patterns = sql_patterns + xss_patterns + traversal_patterns
        check_text = (url + query_params).lower()

        for pattern in all_patterns:
            if pattern in check_text:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Malicious pattern detected"
                )


class CSRFProtection:
    """CSRF protection utilities"""

    def __init__(self):
        self.token_lifetime = 3600  # 1 hour
        self.secret_key = settings.secret_key

    def generate_csrf_token(self, user_id: str) -> str:
        """Generate CSRF token for user"""
        timestamp = str(int(time.time()))
        data = f"{user_id}:{timestamp}:{self.secret_key}"

        token_hash = hashlib.sha256(data.encode()).hexdigest()
        return f"{timestamp}:{token_hash}"

    def validate_csrf_token(self, token: str, user_id: str) -> bool:
        """Validate CSRF token"""
        try:
            timestamp_str, token_hash = token.split(':', 1)
            timestamp = int(timestamp_str)

            # Check if token is expired
            if time.time() - timestamp > self.token_lifetime:
                return False

            # Regenerate expected hash
            data = f"{user_id}:{timestamp_str}:{self.secret_key}"
            expected_hash = hashlib.sha256(data.encode()).hexdigest()

            return token_hash == expected_hash

        except (ValueError, TypeError):
            return False


class IPWhitelist:
    """IP address whitelist management"""

    def __init__(self):
        self.whitelist: List[str] = []
        self.blacklist: List[str] = []

    def add_to_whitelist(self, ip: str):
        """Add IP to whitelist"""
        if ip not in self.whitelist:
            self.whitelist.append(ip)

    def add_to_blacklist(self, ip: str):
        """Add IP to blacklist"""
        if ip not in self.blacklist:
            self.blacklist.append(ip)

    def is_allowed(self, ip: str) -> bool:
        """Check if IP is allowed"""
        # Check blacklist first
        if ip in self.blacklist:
            return False

        # If whitelist is empty, allow all (except blacklisted)
        if not self.whitelist:
            return True

        # Check whitelist
        return ip in self.whitelist


class ContentSecurityPolicy:
    """Content Security Policy utilities"""

    @staticmethod
    def get_csp_header() -> str:
        """Get Content Security Policy header value"""
        policies = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https:",
            "connect-src 'self' https:",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'"
        ]

        return "; ".join(policies)


# Global security instances
security_utils = SecurityUtils()
request_validator = RequestValidator()
csrf_protection = CSRFProtection()
ip_whitelist = IPWhitelist()
csp = ContentSecurityPolicy()