#!/usr/bin/env python3
"""
Railway startup script for AgentOS
"""
import os
import sys
import uvicorn

def main():
    """Start the AgentOS application"""

    # Get port from Railway environment
    port = int(os.getenv("PORT", 8000))
    host = "0.0.0.0"

    print(f"🚀 Starting AgentOS on {host}:{port}")
    print(f"📊 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"🔍 Debug mode: {os.getenv('DEBUG', 'false')}")

    # Check critical environment variables (without showing values)
    required_vars = ["DATABASE_URL", "SECRET_KEY"]
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
            print(f"❌ Missing environment variable: {var}")
        else:
            print(f"✅ Found environment variable: {var}")

    if missing_vars:
        print(f"⚠️  Missing variables: {missing_vars}")
        print("🔧 App will start with defaults where possible")

    try:
        # Start uvicorn server
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            log_level="info",
            access_log=True,
            reload=False
        )
    except Exception as e:
        print(f"💥 Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()