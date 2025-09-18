import time
import os
import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import init_db, close_db, check_db_connection
from app.api import (
    auth_router,
    onboarding_router,
    agents_router,
    health_router,
    specialized_agents_router,
    orchestration_router,
    marketplace_router,
    feedback_router,
    security_router,
    chat_router,
    websocket_router,
    performance_router
)
from app.api.websocket import startup_websocket_tasks, shutdown_websocket_tasks
from app.utils.rate_limiting import limiter, rate_limit_handler
from app.utils.security import request_validator, csp
from app.middleware.security import SecurityMiddleware
from app.core.cache import cache_manager
from app.core.performance_monitor import performance_monitor
from app.core.websocket_manager import connection_pool

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting AgentOS Backend...")

    # Initialize database
    try:
        await init_db()
        db_connected = await check_db_connection()
        if db_connected:
            logger.info("Database connection established")
        else:
            logger.error("Database connection failed")
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))

    # Initialize cache
    try:
        await cache_manager.connect()
        logger.info("Redis cache connection established")
    except Exception as e:
        logger.warning("Redis cache connection failed - continuing without cache", error=str(e))

    # Initialize WebSocket background tasks
    try:
        await startup_websocket_tasks()
        logger.info("WebSocket background tasks started")
    except Exception as e:
        logger.warning("WebSocket startup failed - continuing without WebSocket", error=str(e))

    # Initialize performance monitoring
    try:
        await performance_monitor.start_monitoring()
        logger.info("Performance monitoring started")
    except Exception as e:
        logger.warning("Performance monitoring startup failed - continuing without monitoring", error=str(e))

    logger.info("AgentOS Backend started successfully")

    yield

    # Shutdown
    logger.info("Shutting down AgentOS Backend...")

    # Stop WebSocket background tasks
    try:
        await shutdown_websocket_tasks()
        logger.info("WebSocket background tasks stopped")
    except Exception as e:
        logger.warning("WebSocket shutdown error", error=str(e))

    # Stop performance monitoring
    try:
        await performance_monitor.stop_monitoring()
        logger.info("Performance monitoring stopped")
    except Exception as e:
        logger.warning("Performance monitoring shutdown error", error=str(e))

    await close_db()

    # Close cache connection
    try:
        await cache_manager.close()
        logger.info("Redis cache connection closed")
    except Exception as e:
        logger.warning("Cache shutdown error", error=str(e))

    logger.info("AgentOS Backend shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Multi-agent orchestration platform for SMEs",
    debug=settings.debug,
    lifespan=lifespan,
    openapi_url=f"{settings.api_v1_prefix}/openapi.json" if settings.debug else None,
    docs_url=f"{settings.api_v1_prefix}/docs" if settings.debug else None,
    redoc_url=f"{settings.api_v1_prefix}/redoc" if settings.debug else None,
)

# Add trusted host middleware (security) - Railway compatible
railway_hosts = [
    "*.railway.app",
    "*.up.railway.app",
    "localhost",
    "127.0.0.1",
    "0.0.0.0"
]
if settings.host not in ["localhost", "127.0.0.1", "0.0.0.0"]:
    railway_hosts.append(settings.host)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=railway_hosts
)

# Add comprehensive security middleware
app.add_middleware(
    SecurityMiddleware,
    rate_limit_requests=settings.rate_limit_requests,
    rate_limit_window=settings.rate_limit_window,
    max_request_size=settings.max_request_size,
    enable_xss_protection=settings.enable_xss_protection,
    enable_sql_injection_detection=settings.enable_sql_injection_detection,
    enable_path_traversal_detection=settings.enable_path_traversal_detection
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=settings.allowed_methods,
    allow_headers=settings.allowed_headers,
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


@app.middleware("http")
async def logging_middleware(request: Request, call_next) -> Response:
    """
    Logging and performance tracking middleware.
    """
    start_time = time.time()

    # Log request
    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )

    # Process request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        process_time_ms = process_time * 1000

        # Log response
        logger.info(
            "Request completed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            process_time=round(process_time, 4)
        )

        # Track API performance
        try:
            # Extract endpoint pattern (remove query params and IDs)
            endpoint = str(request.url.path)
            # Simple endpoint normalization (could be more sophisticated)
            if "/api/v1/" in endpoint:
                endpoint_parts = endpoint.split("/")
                # Replace numeric IDs with placeholders
                normalized_parts = []
                for part in endpoint_parts:
                    if part.isdigit() or (part and part.replace("-", "").replace("_", "").isalnum() and len(part) > 10):
                        normalized_parts.append("{id}")
                    else:
                        normalized_parts.append(part)
                endpoint = "/".join(normalized_parts)

            await performance_monitor.track_api_request(
                endpoint=endpoint,
                method=request.method,
                response_time=process_time_ms,
                status_code=response.status_code
            )
        except Exception as perf_error:
            logger.warning(f"Failed to track API performance: {perf_error}")

        # Add process time header
        response.headers["X-Process-Time"] = str(process_time)
        return response

    except Exception as e:
        process_time = time.time() - start_time
        process_time_ms = process_time * 1000

        # Log error
        logger.error(
            "Request failed",
            method=request.method,
            url=str(request.url),
            error=str(e),
            process_time=round(process_time, 4)
        )

        # Track failed request
        try:
            endpoint = str(request.url.path)
            await performance_monitor.track_api_request(
                endpoint=endpoint,
                method=request.method,
                response_time=process_time_ms,
                status_code=500
            )
        except Exception as perf_error:
            logger.warning(f"Failed to track API performance for error: {perf_error}")

        # Return error response
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error_id": str(int(time.time() * 1000))
            }
        )


@app.middleware("http")
async def security_validation_middleware(request: Request, call_next) -> Response:
    """
    Validate requests for security threats
    """
    try:
        # Validate request for security
        await request_validator.validate_request(request)
    except Exception as e:
        # If validation fails, return error response
        return JSONResponse(
            status_code=400,
            content={"detail": str(e)}
        )

    response = await call_next(request)
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next) -> Response:
    """
    Add security headers to all responses.
    """
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = csp.get_csp_header()
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["X-Download-Options"] = "noopen"

    if not settings.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


# Include API routers
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(onboarding_router, prefix=settings.api_v1_prefix)
app.include_router(agents_router, prefix=settings.api_v1_prefix)
app.include_router(chat_router, prefix=f"{settings.api_v1_prefix}/agents", tags=["chat"])
app.include_router(specialized_agents_router, prefix=settings.api_v1_prefix)
app.include_router(orchestration_router, prefix=settings.api_v1_prefix)
app.include_router(marketplace_router, prefix=f"{settings.api_v1_prefix}/marketplace", tags=["marketplace"])
app.include_router(feedback_router, prefix=settings.api_v1_prefix, tags=["feedback"])
app.include_router(security_router, prefix=settings.api_v1_prefix, tags=["security"])
app.include_router(websocket_router, prefix=settings.api_v1_prefix, tags=["websocket"])
app.include_router(performance_router, prefix=settings.api_v1_prefix, tags=["performance"])


# Health check endpoint optimizado para Railway
@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint optimized for Railway.
    Verifies all critical services and dependencies.
    """
    health_status = {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "timestamp": time.time(),
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "unknown"),
        "replica_id": os.getenv("RAILWAY_REPLICA_ID", "unknown"),
        "checks": {}
    }

    # Check database connection
    try:
        db_status = await check_db_connection()
        health_status["checks"]["database"] = "connected" if db_status else "disconnected"

        if not db_status:
            health_status["status"] = "unhealthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["checks"]["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"

    # Check Redis cache
    try:
        await cache_manager.redis_client.ping()
        health_status["checks"]["redis"] = "connected"
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        health_status["checks"]["redis"] = f"warning: {str(e)}"
        # Redis no es crítico, no marcamos como unhealthy

    # Check performance monitoring
    try:
        perf_summary = performance_monitor.get_performance_summary()
        health_status["checks"]["performance_monitor"] = "active"
        health_status["uptime_seconds"] = perf_summary.get("uptime_seconds", 0)
    except Exception as e:
        logger.warning(f"Performance monitor check failed: {e}")
        health_status["checks"]["performance_monitor"] = f"warning: {str(e)}"

    # Check WebSocket connections
    try:
        ws_stats = connection_pool.get_connection_stats()
        health_status["checks"]["websockets"] = "active"
        health_status["active_connections"] = ws_stats.get("active_connections", 0)
    except Exception as e:
        logger.warning(f"WebSocket check failed: {e}")
        health_status["checks"]["websockets"] = f"warning: {str(e)}"

    # Return appropriate status code
    status_code = 200 if health_status["status"] == "healthy" else 503

    return JSONResponse(
        status_code=status_code,
        content=health_status
    )


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint.
    """
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs_url": f"{settings.api_v1_prefix}/docs" if settings.debug else None
    }


if __name__ == "__main__":
    import uvicorn
    import os

    # Railway compatibility - use PORT from environment
    port = int(os.getenv("PORT", settings.port))

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=port,
        reload=settings.reload,
        log_level="debug" if settings.debug else "info"
    )