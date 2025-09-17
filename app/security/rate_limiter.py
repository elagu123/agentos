"""
Advanced Rate Limiter for AgentOS
Tier-based rate limiting with Redis backend and sliding window algorithm
"""

from fastapi import Request, HTTPException, status
from datetime import datetime, timedelta
import redis.asyncio as redis
from typing import Dict, Optional, Tuple, List
import json
import hashlib
from enum import Enum
import asyncio
import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

class RateLimitTier(Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"

@dataclass
class RateLimitConfig:
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    agent_executions_per_hour: int = 100
    workflow_executions_per_day: int = 500
    api_calls_per_minute: int = 20
    concurrent_executions: int = 3
    storage_mb: int = 1000
    bandwidth_mb_per_day: int = 1000

@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    current: int
    remaining: int
    reset_at: str
    retry_after: Optional[int] = None
    tier: Optional[str] = None

class AdvancedRateLimiter:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis_client = None

        # Tier-based rate limits
        self.tier_limits = {
            RateLimitTier.FREE: RateLimitConfig(
                requests_per_minute=20,
                requests_per_hour=100,
                requests_per_day=500,
                agent_executions_per_hour=10,
                workflow_executions_per_day=20,
                api_calls_per_minute=5,
                concurrent_executions=1,
                storage_mb=100,
                bandwidth_mb_per_day=100
            ),
            RateLimitTier.STARTER: RateLimitConfig(
                requests_per_minute=60,
                requests_per_hour=1000,
                requests_per_day=10000,
                agent_executions_per_hour=100,
                workflow_executions_per_day=500,
                api_calls_per_minute=20,
                concurrent_executions=3,
                storage_mb=1000,
                bandwidth_mb_per_day=1000
            ),
            RateLimitTier.PRO: RateLimitConfig(
                requests_per_minute=200,
                requests_per_hour=5000,
                requests_per_day=50000,
                agent_executions_per_hour=500,
                workflow_executions_per_day=2000,
                api_calls_per_minute=50,
                concurrent_executions=10,
                storage_mb=10000,
                bandwidth_mb_per_day=10000
            ),
            RateLimitTier.ENTERPRISE: RateLimitConfig(
                requests_per_minute=-1,  # Unlimited
                requests_per_hour=-1,
                requests_per_day=-1,
                agent_executions_per_hour=-1,
                workflow_executions_per_day=-1,
                api_calls_per_minute=200,  # Still some limit
                concurrent_executions=50,
                storage_mb=-1,
                bandwidth_mb_per_day=-1
            )
        }

        # Time windows in seconds
        self.windows = {
            "minute": 60,
            "hour": 3600,
            "day": 86400,
            "week": 604800,
            "month": 2592000
        }

        # Sliding window configurations
        self.sliding_windows = {
            "minute": {"bucket_size": 10, "buckets": 6},  # 10-second buckets
            "hour": {"bucket_size": 300, "buckets": 12},  # 5-minute buckets
            "day": {"bucket_size": 3600, "buckets": 24}   # 1-hour buckets
        }

    async def get_redis(self) -> redis.Redis:
        """Get or create Redis connection"""
        if not self._redis_client:
            self._redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_keepalive=True,
                health_check_interval=30
            )
        return self._redis_client

    def _get_sliding_window_key(
        self,
        identifier: str,
        resource: str,
        window: str,
        bucket_time: int
    ) -> str:
        """Generate sliding window bucket key"""
        return f"rate_limit:sliding:{identifier}:{resource}:{window}:{bucket_time}"

    def _get_counter_key(
        self,
        identifier: str,
        resource: str,
        window: str
    ) -> str:
        """Generate counter key for fixed windows"""
        now = datetime.utcnow()

        if window == "minute":
            window_start = now.replace(second=0, microsecond=0)
        elif window == "hour":
            window_start = now.replace(minute=0, second=0, microsecond=0)
        elif window == "day":
            window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif window == "week":
            # Start of week (Monday)
            days_since_monday = now.weekday()
            week_start = now - timedelta(days=days_since_monday)
            window_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif window == "month":
            window_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            window_start = now

        window_key = window_start.isoformat()
        return f"rate_limit:counter:{identifier}:{resource}:{window}:{window_key}"

    async def check_rate_limit_sliding(
        self,
        identifier: str,
        resource: str,
        tier: RateLimitTier = RateLimitTier.FREE,
        increment: int = 1,
        window: str = "minute"
    ) -> RateLimitResult:
        """Check rate limit using sliding window algorithm"""

        r = await self.get_redis()
        config = self.tier_limits[tier]

        # Get limit for this resource and window
        limit_attr = f"{resource}_per_{window}"
        limit = getattr(config, limit_attr, -1)

        # Unlimited
        if limit == -1:
            return RateLimitResult(
                allowed=True,
                limit=limit,
                current=0,
                remaining=-1,
                reset_at="never",
                tier=tier.value
            )

        # Get sliding window config
        window_config = self.sliding_windows.get(window, {"bucket_size": 60, "buckets": 60})
        bucket_size = window_config["bucket_size"]
        num_buckets = window_config["buckets"]

        now = int(time.time())
        current_bucket = now // bucket_size

        # Use pipeline for atomic operations
        pipe = r.pipeline()

        # Clean old buckets and count current usage
        bucket_keys = []
        for i in range(num_buckets):
            bucket_time = current_bucket - i
            bucket_key = self._get_sliding_window_key(identifier, resource, window, bucket_time)
            bucket_keys.append(bucket_key)
            pipe.get(bucket_key)

        # Get all bucket values
        bucket_values = await pipe.execute()

        # Calculate current usage
        current_usage = sum(int(val) if val else 0 for val in bucket_values)

        # Check if adding increment would exceed limit
        if current_usage + increment > limit:
            # Calculate when oldest bucket expires
            oldest_bucket_time = (current_bucket - num_buckets + 1) * bucket_size
            reset_time = oldest_bucket_time + self.windows[window]
            reset_at = datetime.fromtimestamp(reset_time).isoformat()

            return RateLimitResult(
                allowed=False,
                limit=limit,
                current=current_usage,
                remaining=0,
                reset_at=reset_at,
                retry_after=max(1, reset_time - now),
                tier=tier.value
            )

        # Increment current bucket
        current_bucket_key = self._get_sliding_window_key(identifier, resource, window, current_bucket)

        pipe = r.pipeline()
        pipe.incrby(current_bucket_key, increment)
        pipe.expire(current_bucket_key, self.windows[window])

        await pipe.execute()

        # Calculate reset time
        reset_time = (current_bucket + 1) * bucket_size
        reset_at = datetime.fromtimestamp(reset_time).isoformat()

        return RateLimitResult(
            allowed=True,
            limit=limit,
            current=current_usage + increment,
            remaining=max(0, limit - current_usage - increment),
            reset_at=reset_at,
            tier=tier.value
        )

    async def check_rate_limit(
        self,
        identifier: str,
        resource: str,
        tier: RateLimitTier = RateLimitTier.FREE,
        increment: int = 1,
        use_sliding_window: bool = True
    ) -> RateLimitResult:
        """Check rate limit with automatic window detection"""

        # Determine appropriate window based on resource
        if "_per_minute" in resource:
            window = "minute"
            limit_key = resource
        elif "_per_hour" in resource:
            window = "hour"
            limit_key = resource
        elif "_per_day" in resource:
            window = "day"
            limit_key = resource
        elif "_per_week" in resource:
            window = "week"
            limit_key = resource
        elif "_per_month" in resource:
            window = "month"
            limit_key = resource
        else:
            # Default for generic resources
            window = "hour"
            limit_key = f"{resource}_per_hour"

        if use_sliding_window and window in self.sliding_windows:
            return await self.check_rate_limit_sliding(
                identifier, resource, tier, increment, window
            )
        else:
            return await self.check_rate_limit_fixed(
                identifier, resource, tier, increment, window
            )

    async def check_rate_limit_fixed(
        self,
        identifier: str,
        resource: str,
        tier: RateLimitTier = RateLimitTier.FREE,
        increment: int = 1,
        window: str = "hour"
    ) -> RateLimitResult:
        """Check rate limit using fixed window algorithm"""

        r = await self.get_redis()
        config = self.tier_limits[tier]

        # Get limit for this resource
        limit_attr = f"{resource}_per_{window}"
        limit = getattr(config, limit_attr, -1)

        # Unlimited
        if limit == -1:
            return RateLimitResult(
                allowed=True,
                limit=limit,
                current=0,
                remaining=-1,
                reset_at="never",
                tier=tier.value
            )

        # Generate key for current window
        key = self._get_counter_key(identifier, resource, window)

        # Use pipeline for atomic operations
        pipe = r.pipeline()
        pipe.get(key)
        pipe.incrby(key, increment)
        pipe.expire(key, self.windows[window])

        results = await pipe.execute()
        current = int(results[0]) if results[0] else 0
        new_value = results[1]

        # Calculate reset time
        ttl = await r.ttl(key)
        reset_at = datetime.utcnow() + timedelta(seconds=ttl if ttl > 0 else self.windows[window])

        # Check if limit exceeded
        if new_value > limit:
            # Revert increment
            await r.decrby(key, increment)

            return RateLimitResult(
                allowed=False,
                limit=limit,
                current=current,
                remaining=0,
                reset_at=reset_at.isoformat(),
                retry_after=ttl,
                tier=tier.value
            )

        return RateLimitResult(
            allowed=True,
            limit=limit,
            current=new_value,
            remaining=max(0, limit - new_value),
            reset_at=reset_at.isoformat(),
            tier=tier.value
        )

    async def check_concurrent_limit(
        self,
        user_id: str,
        tier: RateLimitTier = RateLimitTier.FREE,
        resource_type: str = "execution"
    ) -> Tuple[bool, int, int]:
        """Check concurrent execution limit"""

        r = await self.get_redis()
        config = self.tier_limits[tier]
        limit = config.concurrent_executions

        if limit == -1:
            return True, 0, -1

        key = f"concurrent:{user_id}:{resource_type}"
        current = await r.get(key)
        current = int(current) if current else 0

        if current >= limit:
            return False, current, limit

        return True, current, limit

    async def acquire_concurrent_slot(
        self,
        user_id: str,
        execution_id: str,
        tier: RateLimitTier = RateLimitTier.FREE,
        resource_type: str = "execution",
        timeout: int = 300
    ) -> bool:
        """Acquire slot for concurrent execution"""

        r = await self.get_redis()

        # Check if slot is available
        allowed, current, limit = await self.check_concurrent_limit(user_id, tier, resource_type)

        if not allowed:
            return False

        # Increment counter atomically
        key = f"concurrent:{user_id}:{resource_type}"
        exec_key = f"concurrent_execs:{user_id}:{resource_type}"

        pipe = r.pipeline()
        pipe.incr(key)
        pipe.sadd(exec_key, execution_id)
        pipe.expire(key, timeout)
        pipe.expire(exec_key, timeout)

        results = await pipe.execute()
        new_count = results[0]

        # Check if we exceeded limit after increment
        if new_count > limit and limit != -1:
            # Revert
            await r.decr(key)
            await r.srem(exec_key, execution_id)
            return False

        return True

    async def release_concurrent_slot(
        self,
        user_id: str,
        execution_id: str,
        resource_type: str = "execution"
    ):
        """Release concurrent execution slot"""

        r = await self.get_redis()

        key = f"concurrent:{user_id}:{resource_type}"
        exec_key = f"concurrent_execs:{user_id}:{resource_type}"

        pipe = r.pipeline()
        pipe.decr(key)
        pipe.srem(exec_key, execution_id)

        await pipe.execute()

    async def get_usage_stats(
        self,
        identifier: str,
        tier: RateLimitTier = RateLimitTier.FREE,
        detailed: bool = False
    ) -> Dict:
        """Get usage statistics for identifier"""

        r = await self.get_redis()
        config = self.tier_limits[tier]

        stats = {
            "tier": tier.value,
            "usage": {},
            "limits": {}
        }

        # Get limits
        for attr in dir(config):
            if not attr.startswith('_') and not callable(getattr(config, attr)):
                value = getattr(config, attr)
                stats["limits"][attr] = value

        # Get current usage for each resource type
        resource_types = ["requests", "agent_executions", "workflow_executions", "api_calls"]
        windows = ["minute", "hour", "day"]

        for resource in resource_types:
            stats["usage"][resource] = {}

            for window in windows:
                limit_attr = f"{resource}_per_{window}"
                limit = getattr(config, limit_attr, None)

                if limit is None:
                    continue

                if limit == -1:
                    stats["usage"][resource][window] = "unlimited"
                    continue

                # Get current usage
                key = self._get_counter_key(identifier, resource, window)
                current = await r.get(key)
                current = int(current) if current else 0

                usage_info = {
                    "current": current,
                    "limit": limit,
                    "remaining": max(0, limit - current),
                    "percentage": round((current / limit * 100), 2) if limit > 0 else 0
                }

                if detailed:
                    # Add TTL info
                    ttl = await r.ttl(key)
                    if ttl > 0:
                        usage_info["resets_in_seconds"] = ttl
                        usage_info["resets_at"] = (
                            datetime.utcnow() + timedelta(seconds=ttl)
                        ).isoformat()

                stats["usage"][resource][window] = usage_info

        # Get concurrent usage
        concurrent_key = f"concurrent:{identifier}:execution"
        concurrent_current = await r.get(concurrent_key)
        concurrent_current = int(concurrent_current) if concurrent_current else 0

        stats["usage"]["concurrent_executions"] = {
            "current": concurrent_current,
            "limit": config.concurrent_executions,
            "remaining": max(0, config.concurrent_executions - concurrent_current) if config.concurrent_executions > 0 else -1
        }

        return stats

    async def reset_limits(
        self,
        identifier: str,
        resource: Optional[str] = None,
        window: Optional[str] = None
    ) -> Dict:
        """Reset rate limits (admin operation)"""

        r = await self.get_redis()

        if resource and window:
            # Reset specific resource/window
            key = self._get_counter_key(identifier, resource, window)
            deleted = await r.delete(key)
            return {
                "reset": True,
                "identifier": identifier,
                "resource": resource,
                "window": window,
                "keys_deleted": deleted
            }

        elif resource:
            # Reset all windows for resource
            pattern = f"rate_limit:counter:{identifier}:{resource}:*"
            keys = []
            async for key in r.scan_iter(match=pattern):
                keys.append(key)

            deleted = 0
            if keys:
                deleted = await r.delete(*keys)

            return {
                "reset": True,
                "identifier": identifier,
                "resource": resource,
                "keys_deleted": deleted
            }

        else:
            # Reset all limits for identifier
            patterns = [
                f"rate_limit:counter:{identifier}:*",
                f"rate_limit:sliding:{identifier}:*",
                f"concurrent:{identifier}:*",
                f"concurrent_execs:{identifier}:*"
            ]

            total_deleted = 0
            for pattern in patterns:
                keys = []
                async for key in r.scan_iter(match=pattern):
                    keys.append(key)

                if keys:
                    deleted = await r.delete(*keys)
                    total_deleted += deleted

            return {
                "reset": True,
                "identifier": identifier,
                "keys_deleted": total_deleted
            }

    async def get_global_stats(self) -> Dict:
        """Get global rate limiting statistics"""

        r = await self.get_redis()

        # Count active rate limit keys
        patterns = [
            "rate_limit:counter:*",
            "rate_limit:sliding:*",
            "concurrent:*"
        ]

        stats = {
            "total_keys": 0,
            "keys_by_type": {},
            "active_users": set(),
            "top_users": {}
        }

        for pattern in patterns:
            key_type = pattern.split(':')[1]
            key_count = 0

            async for key in r.scan_iter(match=pattern):
                key_count += 1
                # Extract user ID from key
                parts = key.split(':')
                if len(parts) >= 3:
                    stats["active_users"].add(parts[2])

            stats["keys_by_type"][key_type] = key_count
            stats["total_keys"] += key_count

        stats["active_users"] = len(stats["active_users"])

        return stats

    async def check_burst_protection(
        self,
        identifier: str,
        max_burst: int = 10,
        burst_window: int = 60
    ) -> bool:
        """Check if identifier is making burst requests"""

        r = await self.get_redis()

        key = f"burst:{identifier}"
        current = await r.get(key)

        if not current:
            # First request in window
            await r.setex(key, burst_window, 1)
            return True

        current = int(current)
        if current >= max_burst:
            return False

        # Increment
        await r.incr(key)
        return True

    async def whitelist_identifier(
        self,
        identifier: str,
        expiry: Optional[int] = None
    ):
        """Add identifier to whitelist (bypasses rate limits)"""

        r = await self.get_redis()
        key = f"whitelist:{identifier}"

        if expiry:
            await r.setex(key, expiry, "true")
        else:
            await r.set(key, "true")

    async def is_whitelisted(self, identifier: str) -> bool:
        """Check if identifier is whitelisted"""

        r = await self.get_redis()
        key = f"whitelist:{identifier}"
        return bool(await r.get(key))

    async def blacklist_identifier(
        self,
        identifier: str,
        reason: str = "abuse",
        expiry: Optional[int] = None
    ):
        """Add identifier to blacklist (blocks all requests)"""

        r = await self.get_redis()
        key = f"blacklist:{identifier}"
        data = {"reason": reason, "blocked_at": datetime.utcnow().isoformat()}

        if expiry:
            await r.setex(key, expiry, json.dumps(data))
        else:
            await r.set(key, json.dumps(data))

    async def is_blacklisted(self, identifier: str) -> Tuple[bool, Optional[str]]:
        """Check if identifier is blacklisted"""

        r = await self.get_redis()
        key = f"blacklist:{identifier}"
        data = await r.get(key)

        if data:
            try:
                parsed = json.loads(data)
                return True, parsed.get("reason", "unknown")
            except:
                return True, "unknown"

        return False, None

    async def cleanup_expired_keys(self) -> int:
        """Clean up expired rate limit keys"""

        r = await self.get_redis()
        patterns = [
            "rate_limit:counter:*",
            "rate_limit:sliding:*",
            "concurrent:*",
            "burst:*"
        ]

        cleaned = 0
        for pattern in patterns:
            async for key in r.scan_iter(match=pattern, count=100):
                ttl = await r.ttl(key)
                if ttl == -2:  # Key doesn't exist (expired)
                    cleaned += 1

        logger.info(f"Rate limiter cleanup: found {cleaned} expired keys")
        return cleaned

# Global instance
rate_limiter = AdvancedRateLimiter()

# FastAPI middleware
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

async def rate_limit_middleware(request: Request, call_next):
    """FastAPI middleware for automatic rate limiting"""

    # Skip rate limiting for health checks and static files
    if request.url.path in ["/health", "/metrics"] or request.url.path.startswith("/static"):
        return await call_next(request)

    # Get identifier (user_id or IP)
    user = getattr(request.state, "user", None)
    if user:
        identifier = f"user:{user.id}"
        tier = RateLimitTier(getattr(user, "tier", "free"))
    else:
        # Rate limit by IP for unauthenticated users
        identifier = f"ip:{request.client.host}"
        tier = RateLimitTier.FREE

    # Check if blacklisted
    is_blocked, reason = await rate_limiter.is_blacklisted(identifier)
    if is_blocked:
        return JSONResponse(
            status_code=403,
            content={
                "error": "Access denied",
                "reason": reason,
                "blocked": True
            }
        )

    # Check if whitelisted
    if await rate_limiter.is_whitelisted(identifier):
        return await call_next(request)

    # Check burst protection
    if not await rate_limiter.check_burst_protection(identifier):
        return JSONResponse(
            status_code=429,
            content={
                "error": "Too many requests in burst",
                "detail": "Please slow down your request rate"
            }
        )

    # Determine resource type based on endpoint
    path = request.url.path
    method = request.method

    if "/api/agents/execute" in path:
        resource = "agent_executions"
    elif "/api/workflows/execute" in path:
        resource = "workflow_executions"
    elif "/api/" in path:
        resource = "api_calls"
    else:
        resource = "requests"

    # Check appropriate rate limit
    if resource in ["agent_executions", "workflow_executions"]:
        # These are typically hourly/daily limits
        result = await rate_limiter.check_rate_limit(
            identifier,
            f"{resource}_per_hour",
            tier
        )
    else:
        # API calls and general requests use minute limits
        result = await rate_limiter.check_rate_limit(
            identifier,
            f"{resource}_per_minute",
            tier
        )

    if not result.allowed:
        response_data = {
            "error": "Rate limit exceeded",
            "detail": {
                "tier": result.tier,
                "limit": result.limit,
                "current": result.current,
                "remaining": result.remaining,
                "reset_at": result.reset_at
            }
        }

        headers = {
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": result.reset_at,
            "X-RateLimit-Tier": result.tier
        }

        if result.retry_after:
            headers["Retry-After"] = str(result.retry_after)

        return JSONResponse(
            status_code=429,
            content=response_data,
            headers=headers
        )

    # Proceed with request
    response = await call_next(request)

    # Add rate limit headers to response
    response.headers["X-RateLimit-Limit"] = str(result.limit)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = result.reset_at
    response.headers["X-RateLimit-Tier"] = result.tier

    return response

# Utility functions
def get_tier_from_user(user) -> RateLimitTier:
    """Get rate limit tier from user object"""
    if not user:
        return RateLimitTier.FREE

    tier_mapping = {
        "free": RateLimitTier.FREE,
        "starter": RateLimitTier.STARTER,
        "pro": RateLimitTier.PRO,
        "enterprise": RateLimitTier.ENTERPRISE
    }

    user_tier = getattr(user, "tier", "free").lower()
    return tier_mapping.get(user_tier, RateLimitTier.FREE)

async def check_endpoint_rate_limit(
    identifier: str,
    endpoint: str,
    tier: RateLimitTier = RateLimitTier.FREE
) -> RateLimitResult:
    """Check rate limit for specific endpoint"""

    endpoint_mappings = {
        "agent_create": "api_calls_per_minute",
        "agent_execute": "agent_executions_per_hour",
        "workflow_create": "api_calls_per_minute",
        "workflow_execute": "workflow_executions_per_day",
        "file_upload": "api_calls_per_minute",
        "marketplace_browse": "requests_per_minute"
    }

    resource = endpoint_mappings.get(endpoint, "requests_per_minute")
    return await rate_limiter.check_rate_limit(identifier, resource, tier)