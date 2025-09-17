from typing import Optional
from pydantic import Field, PostgresDsn, RedisDsn, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
import sys


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application Settings
    app_name: str = "AgentOS Backend"
    app_version: str = "1.0.0"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Server Settings - Railway compatible
    host: str = "0.0.0.0"
    port: int = Field(default=8000, description="Port number (Railway uses PORT env var)")
    reload: bool = False

    @validator('port', pre=True)
    def get_port(cls, v):
        # Railway sets PORT environment variable
        railway_port = os.getenv('PORT')
        if railway_port:
            return int(railway_port)
        return v

    # Database Settings
    database_url: PostgresDsn = Field(
        ..., description="Database URL - MUST be set via environment variable"
    )
    database_echo: bool = False

    # Redis Settings
    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0"
    )

    # Qdrant Settings
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: Optional[str] = None
    qdrant_collection_name: str = "business_context"

    # Clerk Authentication
    clerk_publishable_key: str = Field(default="")
    clerk_secret_key: str = Field(default="")
    clerk_jwt_key: str = Field(default="")

    # LLM Settings
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    together_api_key: Optional[str] = None
    default_llm_provider: str = "openai"
    default_model: str = "gpt-4o-mini"

    # Security Settings
    secret_key: str = Field(..., description="JWT secret key - MUST be set via environment variable")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Security Middleware Settings
    rate_limit_requests: int = Field(default=100, description="Rate limit requests per window")
    rate_limit_window: int = Field(default=60, description="Rate limit window in seconds")
    max_request_size: int = Field(default=10 * 1024 * 1024, description="Maximum request size")
    enable_xss_protection: bool = Field(default=True, description="Enable XSS protection")
    enable_sql_injection_detection: bool = Field(default=True, description="Enable SQL injection detection")
    enable_path_traversal_detection: bool = Field(default=True, description="Enable path traversal detection")

    @validator('secret_key')
    def validate_secret_key(cls, v):
        if not v or v in ['your-secret-key-change-in-production', 'CHANGE-ME-use-openssl-rand-base64-32-to-generate-secure-key']:
            raise ValueError('SECRET_KEY must be set to a secure value. Use: openssl rand -base64 32')
        if len(v) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters long')
        return v

    # CORS Settings - Railway compatible
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://*.railway.app",
        "https://*.up.railway.app",
        "https://*.vercel.app",
        "https://*.netlify.app"
    ]
    allowed_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allowed_headers: list[str] = ["*"]

    @validator('allowed_origins', pre=True)
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v

    # File Upload Settings
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: list[str] = [
        "application/pdf",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword"
    ]

    # Vector Embeddings
    embedding_model: str = "text-embedding-ada-002"
    embedding_dimension: int = 1536
    max_chunk_size: int = 1000
    chunk_overlap: int = 200


settings = Settings()