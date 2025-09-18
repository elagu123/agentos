#!/usr/bin/env python3
"""
Minimal AgentOS application for Railway deployment
"""
import os
from fastapi import FastAPI

# Create FastAPI app
app = FastAPI(
    title="AgentOS API",
    version="1.0.0",
    description="Multi-agent orchestration platform"
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AgentOS is running!",
        "status": "healthy",
        "port": os.getenv("PORT", "8000"),
        "environment": os.getenv("ENVIRONMENT", "development")
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AgentOS",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))

    print(f"🚀 Starting minimal AgentOS on port {port}")

    uvicorn.run(
        "app_simple:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )