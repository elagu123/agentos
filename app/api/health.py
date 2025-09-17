"""
Health Check Endpoints for AgentOS
Comprehensive service monitoring and validation
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from typing import Dict, Any
import asyncio
import time
import os

router = APIRouter(prefix="/api/v1/health", tags=["health"])

@router.get("/")
async def health_check():
    """Health check básico"""
    return {
        "status": "healthy",
        "service": "AgentOS API",
        "version": "1.0.0",
        "timestamp": time.time()
    }

@router.get("/db")
async def database_health(db: Session = Depends(get_db)):
    """Verificar conexión a PostgreSQL"""
    try:
        start_time = time.time()
        result = db.execute(text("SELECT 1 as test, NOW() as timestamp"))
        query_time = time.time() - start_time

        row = result.fetchone()

        return {
            "status": "healthy",
            "database": "connected",
            "query_time_ms": round(query_time * 1000, 2),
            "server_time": str(row[1]) if row else None
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }, 503

@router.get("/redis")
async def redis_health():
    """Verificar conexión a Redis"""
    try:
        import redis.asyncio as redis

        start_time = time.time()
        r = await redis.from_url(
            getattr(settings, 'REDIS_URL', 'redis://localhost:6379'),
            encoding="utf-8",
            decode_responses=True
        )

        # Test básico
        await r.ping()

        # Test de escritura/lectura
        test_key = "health_check_test"
        test_value = f"test_{int(time.time())}"
        await r.set(test_key, test_value, ex=60)  # Expira en 60 segundos
        retrieved_value = await r.get(test_key)
        await r.delete(test_key)

        response_time = time.time() - start_time

        # Obtener info del servidor Redis
        info = await r.info("server")

        await r.close()

        return {
            "status": "healthy",
            "redis": "connected",
            "response_time_ms": round(response_time * 1000, 2),
            "write_read_test": "passed" if retrieved_value == test_value else "failed",
            "redis_version": info.get("redis_version", "unknown"),
            "memory_usage": info.get("used_memory_human", "unknown")
        }
    except ImportError:
        return {
            "status": "unavailable",
            "redis": "redis library not installed",
            "error": "pip install redis required"
        }, 503
    except Exception as e:
        return {
            "status": "unhealthy",
            "redis": "connection_failed",
            "error": str(e)
        }, 503

@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Health check detallado de todos los componentes"""

    checks = {}
    overall_healthy = True

    # API básico
    checks["api"] = {
        "status": "healthy",
        "response_time_ms": 0
    }

    # Database check
    try:
        start_time = time.time()
        db.execute(text("SELECT 1"))
        checks["database"] = {
            "status": "healthy",
            "response_time_ms": round((time.time() - start_time) * 1000, 2)
        }
    except Exception as e:
        checks["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        overall_healthy = False

    # Redis check
    try:
        import redis.asyncio as redis
        start_time = time.time()
        r = await redis.from_url(
            getattr(settings, 'REDIS_URL', 'redis://localhost:6379'),
            encoding="utf-8"
        )
        await r.ping()
        await r.close()
        checks["redis"] = {
            "status": "healthy",
            "response_time_ms": round((time.time() - start_time) * 1000, 2)
        }
    except Exception as e:
        checks["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        overall_healthy = False

    healthy_components = sum(1 for check in checks.values() if check["status"] == "healthy")
    total_components = len(checks)

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "checks": checks,
        "healthy_components": healthy_components,
        "total_components": total_components,
        "health_percentage": round((healthy_components / total_components) * 100, 1),
        "timestamp": time.time()
    }