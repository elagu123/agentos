"""
Advanced Redis Cache Management System for AgentOS Performance Optimization
"""
import redis.asyncio as redis
import hashlib
import json
import pickle
from typing import Optional, Any, Callable, List, Dict, Union
from datetime import timedelta
from functools import wraps
import asyncio
import structlog
from app.config import settings

logger = structlog.get_logger(__name__)


class CacheManager:
    """
    Centralized cache management with multiple strategies for optimal performance.

    Features:
    - Automatic caching decorators
    - RAG search result caching
    - LLM response caching
    - Workflow state caching
    - Batch operations
    - Intelligent cache invalidation
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url or "redis://localhost:6379/0"
        self.redis = None
        self._connection_pool = None

    async def connect(self):
        """Initialize Redis connection with optimized settings."""
        if not self.redis:
            self._connection_pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=20,
                retry_on_timeout=True,
                decode_responses=False
            )
            self.redis = redis.Redis(connection_pool=self._connection_pool)

            # Test connection
            try:
                await self.redis.ping()
                logger.info("Redis cache connection established")
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                raise

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            self.redis = None

    def cache_result(self,
                    expire_time: int = 3600,
                    key_prefix: str = "cache",
                    key_builder: Optional[Callable] = None,
                    condition: Optional[Callable] = None):
        """
        Decorator to cache function results automatically.

        Args:
            expire_time: Cache expiration in seconds
            key_prefix: Prefix for cache keys
            key_builder: Custom function to build cache key
            condition: Function to determine if result should be cached

        Example:
            @cache_manager.cache_result(expire_time=3600, key_prefix="llm")
            async def get_llm_response(prompt: str, model: str):
                return await llm.complete(prompt, model)
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if not self.redis:
                    await self.connect()

                # Build cache key
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    # Default: hash all arguments
                    key_data = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
                    cache_key = f"{key_prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"

                # Check cache
                try:
                    cached = await self.redis.get(cache_key)
                    if cached:
                        result = pickle.loads(cached)
                        logger.debug(f"Cache HIT: {cache_key}")
                        return result
                except Exception as e:
                    logger.warning(f"Cache read error: {e}")

                # Compute result
                logger.debug(f"Cache MISS: {cache_key}")
                result = await func(*args, **kwargs)

                # Store in cache if condition is met
                should_cache = condition(result) if condition else True
                if should_cache:
                    try:
                        await self.redis.setex(
                            cache_key,
                            expire_time,
                            pickle.dumps(result)
                        )
                        logger.debug(f"Cache STORE: {cache_key}")
                    except Exception as e:
                        logger.warning(f"Cache write error: {e}")

                return result
            return wrapper
        return decorator

    async def cache_rag_search(self,
                               query: str,
                               org_id: str,
                               results: List[Dict],
                               expire_time: int = 3600):
        """
        Cache RAG search results with intelligent similarity matching.

        Args:
            query: Search query
            org_id: Organization ID
            results: Search results to cache
            expire_time: Cache expiration in seconds
        """
        if not self.redis:
            await self.connect()

        # Normalize query for better hit rate
        normalized_query = self._normalize_query(query)
        cache_key = f"rag:{org_id}:{hashlib.md5(normalized_query.encode()).hexdigest()}"

        try:
            # Store results
            await self.redis.setex(
                cache_key,
                expire_time,
                json.dumps(results)
            )

            # Store query in similarity index for fuzzy matching
            await self.redis.zadd(
                f"rag_queries:{org_id}",
                {normalized_query: expire_time}
            )

            logger.debug(f"RAG cache stored: {cache_key}")
        except Exception as e:
            logger.warning(f"RAG cache error: {e}")

    async def get_cached_rag(self, query: str, org_id: str) -> Optional[List[Dict]]:
        """
        Get cached RAG results with fuzzy matching capability.

        Args:
            query: Search query
            org_id: Organization ID

        Returns:
            Cached results if found, None otherwise
        """
        if not self.redis:
            await self.connect()

        normalized_query = self._normalize_query(query)
        cache_key = f"rag:{org_id}:{hashlib.md5(normalized_query.encode()).hexdigest()}"

        try:
            # Try exact match first
            cached = await self.redis.get(cache_key)
            if cached:
                logger.debug(f"RAG cache HIT (exact): {cache_key}")
                return json.loads(cached)

            # TODO: Implement fuzzy matching for similar queries
            # This would use string similarity algorithms to find
            # semantically similar cached queries

            logger.debug(f"RAG cache MISS: {cache_key}")
            return None
        except Exception as e:
            logger.warning(f"RAG cache read error: {e}")
            return None

    async def cache_llm_response(self,
                                 prompt: str,
                                 model: str,
                                 response: str,
                                 temperature: float = 0,
                                 expire_time: Optional[int] = None):
        """
        Cache LLM responses for deterministic calls.

        Args:
            prompt: LLM prompt
            model: Model name
            response: LLM response
            temperature: Model temperature (only cache if deterministic)
            expire_time: Custom expiration time
        """
        if not self.redis:
            await self.connect()

        # Only cache deterministic responses
        if temperature > 0:
            return

        cache_key = f"llm:{model}:{hashlib.md5(prompt.encode()).hexdigest()}"

        # Set expiration based on model cost
        if expire_time is None:
            expire_time = 86400 if "gpt-4" in model.lower() else 3600

        try:
            await self.redis.setex(
                cache_key,
                expire_time,
                response
            )
            logger.debug(f"LLM cache stored: {cache_key}")
        except Exception as e:
            logger.warning(f"LLM cache error: {e}")

    async def get_cached_llm_response(self, prompt: str, model: str) -> Optional[str]:
        """Get cached LLM response if available."""
        if not self.redis:
            await self.connect()

        cache_key = f"llm:{model}:{hashlib.md5(prompt.encode()).hexdigest()}"

        try:
            cached = await self.redis.get(cache_key)
            if cached:
                logger.debug(f"LLM cache HIT: {cache_key}")
                return cached.decode('utf-8')

            logger.debug(f"LLM cache MISS: {cache_key}")
            return None
        except Exception as e:
            logger.warning(f"LLM cache read error: {e}")
            return None

    async def cache_workflow_state(self,
                                  workflow_id: str,
                                  state: Dict[str, Any],
                                  expire_time: int = 300):
        """
        Cache workflow execution state for real-time updates.

        Args:
            workflow_id: Workflow execution ID
            state: Current execution state
            expire_time: Cache expiration in seconds
        """
        if not self.redis:
            await self.connect()

        cache_key = f"workflow_state:{workflow_id}"

        try:
            await self.redis.setex(
                cache_key,
                expire_time,
                json.dumps(state)
            )

            # Publish update for WebSocket subscribers
            await self.redis.publish(
                f"workflow_updates:{workflow_id}",
                json.dumps(state)
            )

            logger.debug(f"Workflow state cached: {cache_key}")
        except Exception as e:
            logger.warning(f"Workflow cache error: {e}")

    async def get_workflow_state(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get cached workflow state."""
        if not self.redis:
            await self.connect()

        cache_key = f"workflow_state:{workflow_id}"

        try:
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.warning(f"Workflow cache read error: {e}")
            return None

    async def cache_user_session(self,
                                user_id: str,
                                session_data: Dict[str, Any],
                                expire_time: int = 7200):
        """
        Cache user session data to avoid database hits.

        Args:
            user_id: User ID
            session_data: Session data to cache
            expire_time: Cache expiration in seconds
        """
        if not self.redis:
            await self.connect()

        cache_key = f"session:{user_id}"

        try:
            await self.redis.setex(
                cache_key,
                expire_time,
                json.dumps(session_data)
            )
            logger.debug(f"User session cached: {cache_key}")
        except Exception as e:
            logger.warning(f"Session cache error: {e}")

    async def get_user_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user session data."""
        if not self.redis:
            await self.connect()

        cache_key = f"session:{user_id}"

        try:
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.warning(f"Session cache read error: {e}")
            return None

    async def batch_get(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple cache entries in one round trip.

        Args:
            keys: List of cache keys

        Returns:
            Dictionary mapping keys to values
        """
        if not self.redis:
            await self.connect()

        try:
            pipeline = self.redis.pipeline()
            for key in keys:
                pipeline.get(key)

            results = await pipeline.execute()

            return {
                key: pickle.loads(result) if result else None
                for key, result in zip(keys, results)
                if result is not None
            }
        except Exception as e:
            logger.warning(f"Batch cache read error: {e}")
            return {}

    async def invalidate_pattern(self, pattern: str):
        """
        Invalidate all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "user:123:*")
        """
        if not self.redis:
            await self.connect()

        try:
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(
                    cursor,
                    match=pattern,
                    count=100
                )
                if keys:
                    await self.redis.delete(*keys)
                    logger.debug(f"Invalidated {len(keys)} keys matching {pattern}")
                if cursor == 0:
                    break
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")

    async def invalidate_org_cache(self, org_id: str):
        """
        Invalidate all cache for an organization.

        Args:
            org_id: Organization ID
        """
        patterns = [
            f"rag:{org_id}:*",
            f"workflow_state:*:{org_id}:*",
            f"session:*:{org_id}:*"
        ]

        for pattern in patterns:
            await self.invalidate_pattern(pattern)

        logger.info(f"Organization cache invalidated: {org_id}")

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        if not self.redis:
            await self.connect()

        try:
            info = await self.redis.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": (
                    info.get("keyspace_hits", 0) /
                    max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1)
                ) * 100
            }
        except Exception as e:
            logger.warning(f"Cache stats error: {e}")
            return {}

    def _normalize_query(self, query: str) -> str:
        """Normalize query for better cache hit rates."""
        return query.lower().strip()


# Global cache manager instance
cache_manager = CacheManager()


# Convenience decorators for common caching patterns
def cache_rag_results(expire_time: int = 3600):
    """Decorator specifically for RAG search results."""
    return cache_manager.cache_result(
        expire_time=expire_time,
        key_prefix="rag_search",
        condition=lambda x: x is not None and len(x) > 0
    )


def cache_llm_responses(expire_time: int = 3600):
    """Decorator specifically for LLM responses."""
    return cache_manager.cache_result(
        expire_time=expire_time,
        key_prefix="llm_response",
        condition=lambda x: x is not None and len(str(x).strip()) > 0
    )


def cache_database_queries(expire_time: int = 300):
    """Decorator for database query results."""
    return cache_manager.cache_result(
        expire_time=expire_time,
        key_prefix="db_query",
        condition=lambda x: x is not None
    )