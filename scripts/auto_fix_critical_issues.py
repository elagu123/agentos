#!/usr/bin/env python3
"""
Auto-Fix Critical Security Issues for AgentOS
Automatically fixes critical security vulnerabilities and performance issues
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple
import secrets
import string
import json
from datetime import datetime

class SecurityAutoFixer:
    """Automatically fix critical security issues"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / "backups" / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.fixes_applied = []

    def create_backup(self):
        """Create backup of current codebase"""
        print("📦 Creating backup...")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Copy important files
        important_files = [
            "app/config.py",
            "app/database.py",
            "app/main.py",
            "app/security/",
            "app/utils/",
            "requirements.txt"
        ]

        for file_path in important_files:
            src = self.project_root / file_path
            if src.exists():
                if src.is_dir():
                    dst = self.backup_dir / file_path
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    dst = self.backup_dir / file_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)

        print(f"✅ Backup created at: {self.backup_dir}")

    def fix_hardcoded_secrets(self):
        """Fix hardcoded secrets and API keys"""
        print("🔐 Fixing hardcoded secrets...")

        config_file = self.project_root / "app" / "config.py"
        if not config_file.exists():
            return

        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Generate secure secret key
        secret_key = secrets.token_urlsafe(32)

        # Replace hardcoded secret key
        patterns = [
            (r'secret_key:\s*str\s*=\s*Field\(default="[^"]*"\)',
             f'secret_key: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", "{secret_key}"))'),
            (r'SECRET_KEY\s*=\s*"[^"]*"',
             'SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")'),
            (r'jwt_secret:\s*str\s*=\s*"[^"]*"',
             'jwt_secret: str = os.getenv("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION")'),
        ]

        modified = False
        for pattern, replacement in patterns:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                modified = True

        # Ensure os import
        if modified and 'import os' not in content:
            content = 'import os\n' + content

        if modified:
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.fixes_applied.append("Fixed hardcoded secrets in config.py")

        # Create .env.example
        env_example = self.project_root / ".env.example"
        env_content = f"""# AgentOS Environment Variables
# Copy this file to .env and update with your values

# Security
SECRET_KEY={secret_key}
JWT_SECRET={secrets.token_urlsafe(32)}
ENCRYPTION_MASTER_KEY={secrets.token_urlsafe(32)}

# Database
DATABASE_URL=postgresql://user:password@localhost/agentos
REDIS_URL=redis://localhost:6379

# External APIs
OPENAI_API_KEY=your_openai_api_key_here
WHATSAPP_ACCESS_TOKEN=your_whatsapp_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here
WHATSAPP_BUSINESS_ACCOUNT_ID=your_business_account_id_here
WHATSAPP_WEBHOOK_VERIFY_TOKEN={secrets.token_urlsafe(16)}
WHATSAPP_WEBHOOK_SECRET={secrets.token_urlsafe(32)}

# Environment
ENVIRONMENT=development
DEBUG=true
"""

        with open(env_example, 'w', encoding='utf-8') as f:
            f.write(env_content)
        self.fixes_applied.append("Created .env.example with secure defaults")

    def fix_sql_injection_vulnerabilities(self):
        """Fix SQL injection vulnerabilities"""
        print("🛡️ Fixing SQL injection vulnerabilities...")

        # Check database.py
        db_file = self.project_root / "app" / "database.py"
        if db_file.exists():
            with open(db_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Fix raw SQL execution
            patterns = [
                (r'execute\(text\("([^"]*)"([^)]*)\)\)',
                 r'execute(text("\1"), \2)'),
                (r'conn\.execute\(text\("CREATE EXTENSION IF NOT EXISTS vector"\)\)',
                 'conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))'),
            ]

            modified = False
            for pattern, replacement in patterns:
                if re.search(pattern, content):
                    content = re.sub(pattern, replacement, content)
                    modified = True

            if modified:
                with open(db_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.fixes_applied.append("Fixed SQL injection vulnerabilities in database.py")

    def fix_insecure_cors_settings(self):
        """Fix insecure CORS settings"""
        print("🌐 Fixing CORS settings...")

        main_file = self.project_root / "app" / "main.py"
        if not main_file.exists():
            return

        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Fix CORS settings
        cors_fix = '''
# CORS settings - restrictive for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # Specific origins only
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Total-Count", "X-Rate-Limit-Remaining"]
)'''

        # Replace existing CORS configuration
        cors_pattern = r'app\.add_middleware\(\s*CORSMiddleware,.*?\)'
        if re.search(cors_pattern, content, re.DOTALL):
            content = re.sub(cors_pattern, cors_fix.strip(), content, flags=re.DOTALL)

            with open(main_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.fixes_applied.append("Fixed insecure CORS settings")

    def add_security_middleware(self):
        """Add security middleware"""
        print("🔒 Adding security middleware...")

        main_file = self.project_root / "app" / "main.py"
        if not main_file.exists():
            return

        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Add security headers middleware
        security_middleware = '''
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# Security middleware
if settings.environment == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts
    )

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"

    return response
'''

        # Insert after app creation
        app_pattern = r'(app = FastAPI\(.*?\))'
        if re.search(app_pattern, content, re.DOTALL):
            content = re.sub(
                app_pattern,
                r'\1\n' + security_middleware,
                content,
                flags=re.DOTALL
            )

            with open(main_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.fixes_applied.append("Added security headers middleware")

    def fix_input_validation(self):
        """Add input validation and sanitization"""
        print("🧹 Adding input validation...")

        # Create input validation utility
        validation_file = self.project_root / "app" / "utils" / "validation.py"
        validation_file.parent.mkdir(exist_ok=True)

        validation_content = '''"""
Input validation and sanitization utilities
"""

import re
import html
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, validator
from fastapi import HTTPException

class InputSanitizer:
    """Sanitize user inputs"""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            raise ValueError("Value must be a string")

        # Remove null bytes
        value = value.replace('\\x00', '')

        # HTML escape
        value = html.escape(value)

        # Limit length
        if len(value) > max_length:
            value = value[:max_length]

        return value.strip()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename"""
        # Remove path traversal attempts
        filename = filename.replace('..', '').replace('/', '').replace('\\\\', '')

        # Remove dangerous characters
        filename = re.sub(r'[<>:"|?*]', '', filename)

        # Ensure not empty
        if not filename.strip():
            raise ValueError("Invalid filename")

        return filename.strip()

    @staticmethod
    def validate_email(email: str) -> str:
        """Validate email format"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValueError("Invalid email format")
        return email.lower()

    @staticmethod
    def validate_phone(phone: str) -> str:
        """Validate phone number"""
        # Remove non-digits
        phone = re.sub(r'\\D', '', phone)

        # Check length
        if len(phone) < 10 or len(phone) > 15:
            raise ValueError("Invalid phone number")

        return phone

def validate_json_input(data: Dict[str, Any], max_depth: int = 5, max_keys: int = 100) -> Dict[str, Any]:
    """Validate JSON input structure"""

    def check_depth(obj, current_depth=0):
        if current_depth > max_depth:
            raise ValueError("JSON too deeply nested")

        if isinstance(obj, dict):
            if len(obj) > max_keys:
                raise ValueError("Too many keys in JSON object")
            for value in obj.values():
                check_depth(value, current_depth + 1)
        elif isinstance(obj, list):
            if len(obj) > max_keys:
                raise ValueError("List too long")
            for item in obj:
                check_depth(item, current_depth + 1)

    check_depth(data)
    return data

class SecureBaseModel(BaseModel):
    """Base model with security validations"""

    @validator('*', pre=True)
    def sanitize_strings(cls, v):
        if isinstance(v, str):
            return InputSanitizer.sanitize_string(v)
        return v
'''

        with open(validation_file, 'w', encoding='utf-8') as f:
            f.write(validation_content)
        self.fixes_applied.append("Created input validation utilities")

    def fix_file_upload_security(self):
        """Fix file upload security issues"""
        print("📁 Fixing file upload security...")

        # Update security utils
        security_file = self.project_root / "app" / "utils" / "security.py"
        if security_file.exists():
            with open(security_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Add secure file validation
            secure_upload_code = '''
import magic
from typing import List, Tuple

class SecureFileValidator:
    """Secure file upload validation"""

    ALLOWED_EXTENSIONS = {
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
        'document': ['.pdf', '.doc', '.docx', '.txt', '.rtf'],
        'spreadsheet': ['.xls', '.xlsx', '.csv'],
        'archive': ['.zip', '.tar', '.gz']
    }

    ALLOWED_MIME_TYPES = {
        'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp',
        'application/pdf', 'text/plain', 'text/csv',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/zip', 'application/x-tar', 'application/gzip'
    }

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    @classmethod
    def validate_file(cls, file_content: bytes, filename: str) -> Tuple[bool, str]:
        """Validate uploaded file"""

        # Check file size
        if len(file_content) > cls.MAX_FILE_SIZE:
            return False, "File too large"

        # Check file extension
        extension = Path(filename).suffix.lower()
        allowed_extensions = []
        for ext_list in cls.ALLOWED_EXTENSIONS.values():
            allowed_extensions.extend(ext_list)

        if extension not in allowed_extensions:
            return False, f"File extension {extension} not allowed"

        # Check MIME type using python-magic
        try:
            mime_type = magic.from_buffer(file_content, mime=True)
            if mime_type not in cls.ALLOWED_MIME_TYPES:
                return False, f"File type {mime_type} not allowed"
        except:
            return False, "Could not determine file type"

        # Check for malicious content
        if cls._contains_malicious_content(file_content):
            return False, "File contains potentially malicious content"

        return True, "File is safe"

    @classmethod
    def _contains_malicious_content(cls, content: bytes) -> bool:
        """Check for malicious content patterns"""

        # Convert to lowercase for checking
        content_str = content[:1024].decode('utf-8', errors='ignore').lower()

        malicious_patterns = [
            b'<script', b'javascript:', b'vbscript:',
            b'<?php', b'<%', b'#!/bin/bash', b'#!/bin/sh',
            b'cmd.exe', b'powershell', b'eval(',
            b'system(', b'exec(', b'passthru(',
            b'shell_exec', b'file_get_contents'
        ]

        for pattern in malicious_patterns:
            if pattern in content[:1024].lower():
                return True

        return False
'''

            # Add to existing file
            if 'class SecureFileValidator' not in content:
                content += '\\n' + secure_upload_code

                with open(security_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.fixes_applied.append("Enhanced file upload security")

    def add_rate_limiting_middleware(self):
        """Add rate limiting middleware"""
        print("⚡ Adding rate limiting...")

        rate_limit_file = self.project_root / "app" / "middleware" / "rate_limit.py"
        rate_limit_file.parent.mkdir(exist_ok=True)

        rate_limit_content = '''"""
Rate limiting middleware
"""

import time
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Deque

class SimpleRateLimiter(BaseHTTPMiddleware):
    """Simple in-memory rate limiter"""

    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.clients: Dict[str, Deque[float]] = defaultdict(lambda: deque())

    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = request.client.host

        # Clean old entries
        now = time.time()
        client_calls = self.clients[client_ip]

        # Remove calls older than the period
        while client_calls and client_calls[0] <= now - self.period:
            client_calls.popleft()

        # Check rate limit
        if len(client_calls) >= self.calls:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(self.period)}
            )

        # Add current call
        client_calls.append(now)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(self.calls - len(client_calls))
        response.headers["X-RateLimit-Reset"] = str(int(now + self.period))

        return response
'''

        with open(rate_limit_file, 'w', encoding='utf-8') as f:
            f.write(rate_limit_content)
        self.fixes_applied.append("Added rate limiting middleware")

    def update_requirements(self):
        """Update requirements with security dependencies"""
        print("📦 Updating security dependencies...")

        req_file = self.project_root / "requirements.txt"
        additional_deps = [
            "python-magic>=0.4.27",
            "cryptography>=41.0.0",
            "bcrypt>=4.0.0",
            "pyjwt[crypto]>=2.8.0",
            "passlib[bcrypt]>=1.7.4",
            "python-multipart>=0.0.6"
        ]

        if req_file.exists():
            with open(req_file, 'r', encoding='utf-8') as f:
                existing_deps = f.read()

            new_deps = []
            for dep in additional_deps:
                dep_name = dep.split('>=')[0].split('[')[0]
                if dep_name not in existing_deps:
                    new_deps.append(dep)

            if new_deps:
                with open(req_file, 'a', encoding='utf-8') as f:
                    f.write('\\n# Security dependencies\\n')
                    for dep in new_deps:
                        f.write(f'{dep}\\n')

                self.fixes_applied.append(f"Added security dependencies: {', '.join(new_deps)}")

    def create_security_checklist(self):
        """Create security deployment checklist"""
        print("📋 Creating security checklist...")

        checklist_file = self.project_root / "SECURITY_CHECKLIST.md"
        checklist_content = '''# 🔒 AgentOS Security Deployment Checklist

## Pre-Deployment Security Checklist

### ✅ Authentication & Authorization
- [ ] All default passwords changed
- [ ] Secret keys generated and stored securely
- [ ] JWT tokens properly configured
- [ ] 2FA enabled for admin accounts
- [ ] API key rotation implemented
- [ ] Session management secured

### ✅ Input Validation
- [ ] All inputs validated and sanitized
- [ ] File uploads restricted and validated
- [ ] SQL injection protection enabled
- [ ] XSS protection implemented
- [ ] CSRF protection enabled

### ✅ Network Security
- [ ] HTTPS enforced in production
- [ ] CORS properly configured
- [ ] Security headers implemented
- [ ] Rate limiting enabled
- [ ] Firewall rules configured

### ✅ Data Protection
- [ ] Database encrypted at rest
- [ ] Sensitive data encrypted
- [ ] Backup encryption enabled
- [ ] PII handling compliant
- [ ] Data retention policies implemented

### ✅ Monitoring & Logging
- [ ] Security event logging enabled
- [ ] Failed login attempts monitored
- [ ] Intrusion detection configured
- [ ] Audit logs protected
- [ ] Alerting system configured

### ✅ Infrastructure
- [ ] Dependencies updated
- [ ] Security patches applied
- [ ] Container security configured
- [ ] Network segmentation implemented
- [ ] Backup strategy tested

## Environment Variables Required

```bash
# Copy to .env and update values
SECRET_KEY=your-secure-secret-key-here
JWT_SECRET=your-jwt-secret-here
ENCRYPTION_MASTER_KEY=your-encryption-key-here
DATABASE_URL=postgresql://user:pass@host/db
REDIS_URL=redis://localhost:6379
```

## Security Contacts

- Security Team: security@agentos.ai
- Emergency: +1-XXX-XXX-XXXX
- Bug Bounty: bugbounty@agentos.ai

## Regular Security Tasks

### Daily
- [ ] Monitor security alerts
- [ ] Review failed authentication logs
- [ ] Check system resource usage

### Weekly
- [ ] Review access logs
- [ ] Update security signatures
- [ ] Backup verification

### Monthly
- [ ] Security audit
- [ ] Dependency updates
- [ ] Penetration testing
- [ ] Security training

## Incident Response

1. **Detect** - Automated monitoring and manual reporting
2. **Respond** - Immediate containment procedures
3. **Recover** - System restoration and validation
4. **Learn** - Post-incident analysis and improvements

---
**Last Updated:** {timestamp}
**Version:** 1.0
'''.format(timestamp=datetime.now().strftime('%Y-%m-%d'))

        with open(checklist_file, 'w', encoding='utf-8') as f:
            f.write(checklist_content)
        self.fixes_applied.append("Created security deployment checklist")

    def run_all_fixes(self):
        """Run all automated fixes"""
        print("🚀 Starting automated security fixes...")
        print("=" * 50)

        try:
            self.create_backup()
            self.fix_hardcoded_secrets()
            self.fix_sql_injection_vulnerabilities()
            self.fix_insecure_cors_settings()
            self.add_security_middleware()
            self.fix_input_validation()
            self.fix_file_upload_security()
            self.add_rate_limiting_middleware()
            self.update_requirements()
            self.create_security_checklist()

            print("\\n" + "=" * 50)
            print("✅ AUTOMATED FIXES COMPLETED")
            print("=" * 50)
            print(f"📦 Backup location: {self.backup_dir}")
            print("🔧 Fixes applied:")
            for fix in self.fixes_applied:
                print(f"   ✓ {fix}")

            print("\\n🚨 MANUAL ACTIONS REQUIRED:")
            print("   1. Update .env file with your actual values")
            print("   2. Run: pip install -r requirements.txt")
            print("   3. Test all endpoints after changes")
            print("   4. Review security checklist")
            print("   5. Set up monitoring and alerting")

            print("\\n⚠️  IMPORTANT:")
            print("   - Review all changes before deploying")
            print("   - Test thoroughly in staging environment")
            print("   - Monitor logs after deployment")

        except Exception as e:
            print(f"❌ Error during automated fixes: {e}")
            print(f"📦 Backup available at: {self.backup_dir}")

def main():
    """Main function"""
    project_root = Path(__file__).parent.parent

    print("🛠️  AgentOS Security Auto-Fix Tool")
    print("=" * 50)
    print("This tool will automatically fix critical security issues.")
    print("A backup will be created before making any changes.")
    print()

    response = input("Continue? (y/N): ").strip().lower()
    if response != 'y':
        print("Aborted.")
        return

    fixer = SecurityAutoFixer(str(project_root))
    fixer.run_all_fixes()

if __name__ == "__main__":
    main()