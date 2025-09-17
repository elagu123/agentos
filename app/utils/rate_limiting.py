from typing import Optional, Dict, Any
import time
from functools import wraps
from fastapi import Request, HTTPException, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import redis.asyncio as redis

from app.config import settings


class CustomLimiter:
    """Custom rate limiter with Redis backend and advanced features"""

    def __init__(self):
        self.redis_client = None
        self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis connection for rate limiting"""
        try:
            self.redis_client = redis.from_url(
                str(settings.redis_url),
                encoding="utf-8",
                decode_responses=True
            )
        except Exception as e:
            print(f"Warning: Redis not available for rate limiting: {str(e)}")
            self.redis_client = None

    async def is_rate_limited(
        self,
        key: str,
        limit: int,
        window: int,
        identifier: str = "default"
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Check if a request should be rate limited

        Args:
            key: Unique key for the rate limit (e.g., user_id, ip_address)
            limit: Maximum number of requests allowed
            window: Time window in seconds
            identifier: Additional identifier for different endpoints

        Returns:
            Tuple of (is_limited, metadata)
        """
        if not self.redis_client:
            # If Redis is not available, allow all requests
            return False, {"requests": 0, "limit": limit, "window": window}

        try:
            current_time = int(time.time())
            redis_key = f"rate_limit:{identifier}:{key}:{current_time // window}"

            # Get current count
            current_count = await self.redis_client.get(redis_key)
            current_count = int(current_count) if current_count else 0

            # Check if limit exceeded
            if current_count >= limit:
                return True, {
                    "requests": current_count,
                    "limit": limit,
                    "window": window,
                    "reset_time": ((current_time // window) + 1) * window
                }

            # Increment counter
            pipe = self.redis_client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, window + 1)  # Add 1 second buffer
            await pipe.execute()

            return False, {
                "requests": current_count + 1,
                "limit": limit,
                "window": window,
                "reset_time": ((current_time // window) + 1) * window
            }

        except Exception as e:
            print(f"Rate limiting error: {str(e)}")
            # On error, allow the request
            return False, {"requests": 0, "limit": limit, "window": window}

    async def reset_rate_limit(self, key: str, identifier: str = "default"):
        """Reset rate limit for a specific key"""
        if not self.redis_client:
            return

        try:
            # Get all keys matching the pattern
            pattern = f"rate_limit:{identifier}:{key}:*"
            keys = await self.redis_client.keys(pattern)

            if keys:
                await self.redis_client.delete(*keys)

        except Exception as e:
            print(f"Error resetting rate limit: {str(e)}")


# Global rate limiter instance
custom_limiter = CustomLimiter()

# Standard SlowAPI limiter for basic usage
limiter = Limiter(key_func=get_remote_address)


def rate_limit_by_user(limit: str):
    """
    Rate limit decorator by user ID

    Args:
        limit: Rate limit string (e.g., "10/minute", "100/hour")
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and user from arguments
            request = None
            current_user = None

            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                elif hasattr(arg, 'id'):  # Likely a User object
                    current_user = arg

            if not request or not current_user:
                # If we can't identify user, fall back to IP-based limiting
                return await func(*args, **kwargs)

            # Parse limit string
            parts = limit.split("/")
            if len(parts) != 2:
                raise ValueError(f"Invalid limit format: {limit}")

            count = int(parts[0])
            period = parts[1]

            # Convert period to seconds
            period_seconds = {
                "second": 1,
                "minute": 60,
                "hour": 3600,
                "day": 86400
            }.get(period, 60)

            # Check rate limit
            is_limited, metadata = await custom_limiter.is_rate_limited(
                key=str(current_user.id),
                limit=count,
                window=period_seconds,
                identifier=func.__name__
            )

            if is_limited:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": metadata["limit"],
                        "window": metadata["window"],
                        "reset_time": metadata["reset_time"]
                    }
                )

            # Add rate limit headers to response
            response = await func(*args, **kwargs)
            if hasattr(response, 'headers'):
                response.headers["X-RateLimit-Limit"] = str(metadata["limit"])
                response.headers["X-RateLimit-Remaining"] = str(
                    max(0, metadata["limit"] - metadata["requests"])
                )
                response.headers["X-RateLimit-Reset"] = str(metadata.get("reset_time", 0))

            return response

        return wrapper
    return decorator


def rate_limit_by_organization(limit: str):
    """
    Rate limit decorator by organization ID

    Args:
        limit: Rate limit string (e.g., "1000/hour")
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and user from arguments
            request = None
            current_user = None

            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                elif hasattr(arg, 'organization_id'):
                    current_user = arg

            if not request or not current_user or not current_user.organization_id:
                return await func(*args, **kwargs)

            # Parse limit string
            parts = limit.split("/")
            if len(parts) != 2:
                raise ValueError(f"Invalid limit format: {limit}")

            count = int(parts[0])
            period = parts[1]

            period_seconds = {
                "second": 1,
                "minute": 60,
                "hour": 3600,
                "day": 86400
            }.get(period, 3600)

            # Check rate limit
            is_limited, metadata = await custom_limiter.is_rate_limited(
                key=str(current_user.organization_id),
                limit=count,
                window=period_seconds,
                identifier=f"org_{func.__name__}"
            )

            if is_limited:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Organization rate limit exceeded",
                        "limit": metadata["limit"],
                        "window": metadata["window"],
                        "reset_time": metadata["reset_time"]
                    }
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def adaptive_rate_limit(base_limit: str, multiplier_key: Optional[str] = None):
    """
    Adaptive rate limiting based on user tier or organization plan

    Args:
        base_limit: Base rate limit string
        multiplier_key: Key to determine multiplier (e.g., user plan)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user
            current_user = None
            for arg in args:
                if hasattr(arg, 'id'):
                    current_user = arg
                    break

            if not current_user:
                return await func(*args, **kwargs)

            # Parse base limit
            parts = base_limit.split("/")
            base_count = int(parts[0])
            period = parts[1]

            # Determine multiplier based on user/organization plan
            multiplier = 1.0
            if multiplier_key and hasattr(current_user, multiplier_key):
                plan = getattr(current_user, multiplier_key)
                multiplier_map = {
                    "free": 1.0,
                    "pro": 5.0,
                    "enterprise": 20.0
                }
                multiplier = multiplier_map.get(plan, 1.0)

            # Apply multiplier
            adjusted_limit = int(base_count * multiplier)

            period_seconds = {
                "minute": 60,
                "hour": 3600,
                "day": 86400
            }.get(period, 3600)

            # Check rate limit
            is_limited, metadata = await custom_limiter.is_rate_limited(
                key=str(current_user.id),
                limit=adjusted_limit,
                window=period_seconds,
                identifier=f"adaptive_{func.__name__}"
            )

            if is_limited:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": metadata["limit"],
                        "window": metadata["window"],
                        "reset_time": metadata["reset_time"]
                    }
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


async def cleanup_expired_rate_limits():
    """Cleanup expired rate limit keys (run periodically)"""
    if not custom_limiter.redis_client:
        return

    try:
        # Get all rate limit keys
        keys = await custom_limiter.redis_client.keys("rate_limit:*")

        # Check TTL and remove expired keys
        for key in keys:
            ttl = await custom_limiter.redis_client.ttl(key)
            if ttl == -1:  # No expiration set
                await custom_limiter.redis_client.expire(key, 3600)  # Set 1 hour expiration

    except Exception as e:
        print(f"Error cleaning up rate limits: {str(e)}")


# Rate limit exception handler
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded"""
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please try again later.",
            "retry_after": getattr(exc, 'retry_after', 60)
        }
    )