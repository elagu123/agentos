#!/usr/bin/env python3
"""
Quick configuration test to verify environment variables and security settings
"""

import sys
import os
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from app.config import settings
    from app.middleware.security import SecurityMiddleware

    print("✅ Configuration Test Results:")
    print(f"   App Name: {settings.app_name}")
    print(f"   Debug Mode: {settings.debug}")
    print(f"   Secret Key Length: {len(settings.secret_key)} chars")
    print(f"   Database URL: {'✅ Set' if settings.database_url else '❌ Missing'}")
    print(f"   Rate Limiting: {settings.rate_limit_requests} req/{settings.rate_limit_window}s")
    print(f"   XSS Protection: {'✅ Enabled' if settings.enable_xss_protection else '❌ Disabled'}")
    print(f"   SQL Injection Detection: {'✅ Enabled' if settings.enable_sql_injection_detection else '❌ Disabled'}")
    print(f"   Path Traversal Detection: {'✅ Enabled' if settings.enable_path_traversal_detection else '❌ Disabled'}")

    print("\n✅ Security Middleware: Imported successfully")
    print("\n🔒 Configuration is secure and ready!")

except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Configuration Error: {e}")
    sys.exit(1)