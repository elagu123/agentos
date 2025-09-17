import time
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
from app.api import auth_router, onboarding_router, agents_router, health_router
from app.api.specialized_agents import router as specialized_agents_router
from app.api.orchestration import router as orchestration_router
from app.api.marketplace import router as marketplace_router
from app.api.feedback import router as feedback_router
from app.api.security_dashboard import router as security_router
from app.utils.rate_limiting import limiter, rate_limit_handler
from app.utils.security import request_validator, csp
from app.middleware.security import SecurityMiddleware

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

    logger.info("AgentOS Backend started successfully")

    yield

    # Shutdown
    logger.info("Shutting down AgentOS Backend...")
    await close_db()
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
    Logging middleware to track request/response cycle.
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

        # Log response
        logger.info(
            "Request completed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            process_time=round(process_time, 4)
        )

        # Add process time header
        response.headers["X-Process-Time"] = str(process_time)
        return response

    except Exception as e:
        process_time = time.time() - start_time

        # Log error
        logger.error(
            "Request failed",
            method=request.method,
            url=str(request.url),
            error=str(e),
            process_time=round(process_time, 4)
        )

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
app.include_router(specialized_agents_router, prefix=settings.api_v1_prefix)
app.include_router(orchestration_router, prefix=settings.api_v1_prefix)
app.include_router(marketplace_router, prefix=f"{settings.api_v1_prefix}/marketplace", tags=["marketplace"])
app.include_router(feedback_router, prefix=settings.api_v1_prefix, tags=["feedback"])
app.include_router(security_router, prefix=settings.api_v1_prefix, tags=["security"])


# Health check endpoint (legacy)
@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    db_status = await check_db_connection()

    return {
        "status": "healthy" if db_status else "unhealthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "database": "connected" if db_status else "disconnected",
        "timestamp": time.time()
    }


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

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level="debug" if settings.debug else "info"
    )