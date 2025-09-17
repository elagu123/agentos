"""
Intelligent Cache Manager for AgentOS
Provides multi-level caching with Redis backend and automatic invalidation
"""

import redis.asyncio as redis
from functools import wraps
import hashlib
import json
import pickle
from typing import Any, Optional, Union, List, Dict, Callable
from datetime import timedelta
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis_client = None
        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }

    async def get_redis(self) -> redis.Redis:
        """Get or create Redis connection"""
        if not self._redis_client:
            self._redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False,  # Para manejar bytes
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )
        return self._redis_client

    def _generate_key(self, namespace: str, *args, **kwargs) -> str:
        """Generar cache key única"""
        key_data = {
            "args": args,
            "kwargs": kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return f"cache:{namespace}:{key_hash}"

    async def get(self, key: str) -> Optional[Any]:
        """Obtener valor del cache"""
        try:
            r = await self.get_redis()
            value = await r.get(key)

            if value:
                self._cache_stats["hits"] += 1
                try:
                    # Intentar deserializar JSON primero
                    if isinstance(value, bytes):
                        value = value.decode('utf-8')
                    return json.loads(value)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Si falla JSON, intentar pickle
                    try:
                        if isinstance(value, str):
                            value = value.encode('utf-8')
                        return pickle.loads(value)
                    except:
                        # Fallback a string
                        return value.decode() if isinstance(value, bytes) else value
            else:
                self._cache_stats["misses"] += 1
                return None
        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache get error for key {key}: {str(e)}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = 3600
    ) -> bool:
        """Guardar valor en cache"""
        try:
            r = await self.get_redis()

            # Serializar valor
            try:
                # Intentar JSON primero (más rápido y legible)
                serialized = json.dumps(value, default=str)
            except (TypeError, ValueError):
                # Fallback a pickle para objetos complejos
                serialized = pickle.dumps(value)

            self._cache_stats["sets"] += 1

            if ttl:
                return await r.setex(key, ttl, serialized)
            else:
                return await r.set(key, serialized)
        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache set error for key {key}: {str(e)}")
            return False

    async def delete(self, key: str) -> bool:
        """Eliminar del cache"""
        try:
            r = await self.get_redis()
            self._cache_stats["deletes"] += 1
            result = await r.delete(key)
            return result > 0
        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache delete error for key {key}: {str(e)}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Eliminar keys por patrón"""
        try:
            r = await self.get_redis()
            keys = []

            # Usar SCAN para evitar bloquear Redis
            async for key in r.scan_iter(match=pattern, count=100):
                keys.append(key)

            if keys:
                deleted = await r.delete(*keys)
                self._cache_stats["deletes"] += deleted
                return deleted
            return 0
        except Exception as e:
            self._cache_stats["errors"] += 1
            logger.error(f"Cache delete pattern error for {pattern}: {str(e)}")
            return 0

    async def get_or_set(
        self,
        key: str,
        func: Callable,
        ttl: Optional[int] = 3600,
        force_refresh: bool = False
    ) -> Any:
        """Get from cache o ejecutar función y cachear"""
        if not force_refresh:
            cached = await self.get(key)
            if cached is not None:
                return cached

        # Ejecutar función
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func()
            else:
                result = func()

            # Cachear resultado solo si no es None
            if result is not None:
                await self.set(key, result, ttl)

            return result
        except Exception as e:
            logger.error(f"Function execution error for cache key {key}: {str(e)}")
            raise

    def cached(
        self,
        namespace: str,
        ttl: Union[int, timedelta] = 3600,
        key_prefix: str = "",
        exclude_kwargs: List[str] = None,
        invalidate_on: List[str] = None
    ):
        """
        Decorator para cachear resultados de funciones

        Args:
            namespace: Namespace para la cache key
            ttl: Time to live en segundos o timedelta
            key_prefix: Prefijo adicional para la key
            exclude_kwargs: Lista de kwargs a excluir de la cache key
            invalidate_on: Lista de eventos que invalidan este cache
        """

        if isinstance(ttl, timedelta):
            ttl = int(ttl.total_seconds())

        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Filtrar kwargs excluidos
                cache_kwargs = {
                    k: v for k, v in kwargs.items()
                    if not exclude_kwargs or k not in exclude_kwargs
                }

                # Generar cache key
                cache_key = self._generate_key(
                    f"{namespace}:{key_prefix}{func.__name__}",
                    *args,
                    **cache_kwargs
                )

                # Check cache
                force_refresh = kwargs.pop("force_refresh", False)
                if not force_refresh:
                    cached_value = await self.get(cache_key)
                    if cached_value is not None:
                        return cached_value

                # Execute function
                result = await func(*args, **kwargs)

                # Cache result
                if result is not None:
                    await self.set(cache_key, result, ttl)

                return result

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Para funciones síncronas, crear un wrapper async
                async def async_exec():
                    return await async_wrapper(*args, **kwargs)

                # Ejecutar en loop existente o crear uno nuevo
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Si ya hay un loop corriendo, crear task
                        return asyncio.create_task(async_exec())
                    else:
                        return loop.run_until_complete(async_exec())
                except RuntimeError:
                    # No hay loop, crear uno nuevo
                    return asyncio.run(async_exec())

            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

        return decorator

    async def get_stats(self) -> Dict:
        """Obtener estadísticas del cache"""
        total = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_rate = (self._cache_stats["hits"] / total * 100) if total > 0 else 0

        try:
            r = await self.get_redis()
            info = await r.info("memory")
            keyspace_info = await r.info("keyspace")

            # Contar keys de cache
            cache_keys = 0
            async for key in r.scan_iter(match="cache:*", count=1000):
                cache_keys += 1

            return {
                **self._cache_stats,
                "hit_rate": f"{hit_rate:.1f}%",
                "cache_keys": cache_keys,
                "memory_used": info.get("used_memory_human", "N/A"),
                "memory_peak": info.get("used_memory_peak_human", "N/A"),
                "redis_version": info.get("redis_version", "unknown"),
                "keyspace": keyspace_info
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {
                **self._cache_stats,
                "hit_rate": f"{hit_rate:.1f}%",
                "error": str(e)
            }

    async def clear_all(self) -> int:
        """Limpiar todo el cache (¡cuidado!)"""
        try:
            return await self.delete_pattern("cache:*")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return 0

    async def warm_cache(self, warm_functions: List[Dict]):
        """
        Precalentar cache con funciones especificadas

        Args:
            warm_functions: Lista de dicts con 'func', 'args', 'kwargs'
        """
        logger.info(f"Warming cache with {len(warm_functions)} functions")

        for func_config in warm_functions:
            try:
                func = func_config['func']
                args = func_config.get('args', ())
                kwargs = func_config.get('kwargs', {})

                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)

                logger.debug(f"Warmed cache for {func.__name__}")
            except Exception as e:
                logger.error(f"Error warming cache for {func_config}: {str(e)}")

        logger.info("Cache warming completed")

    async def cleanup_expired(self):
        """Limpiar keys expiradas manualmente (Redis lo hace automáticamente, pero esto es para logging)"""
        try:
            r = await self.get_redis()

            # Obtener estadísticas antes
            stats_before = await self.get_stats()

            # Redis maneja la expiración automáticamente, pero podemos forzar una limpieza
            # Esto es principalmente para logging/monitoreo

            expired_count = 0
            async for key in r.scan_iter(match="cache:*", count=100):
                ttl = await r.ttl(key)
                if ttl == -2:  # Key doesn't exist (expired)
                    expired_count += 1

            stats_after = await self.get_stats()

            logger.info(f"Cache cleanup: found {expired_count} expired keys")
            return expired_count

        except Exception as e:
            logger.error(f"Error during cache cleanup: {str(e)}")
            return 0

    async def health_check(self) -> Dict[str, Any]:
        """Verificar salud del cache"""
        try:
            r = await self.get_redis()

            # Test básico
            start_time = time.time()
            await r.ping()
            ping_time = (time.time() - start_time) * 1000

            # Test de escritura/lectura
            test_key = "cache:health:test"
            test_value = f"health_check_{time.time()}"

            await r.set(test_key, test_value, ex=60)
            retrieved = await r.get(test_key)
            await r.delete(test_key)

            write_read_ok = retrieved.decode() == test_value

            return {
                "status": "healthy" if write_read_ok else "degraded",
                "ping_ms": round(ping_time, 2),
                "write_read_test": "passed" if write_read_ok else "failed",
                "connection": "ok"
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "connection": "failed"
            }

# Instancia global
cache_manager = CacheManager()

# Decorators de conveniencia para diferentes tipos de cache
def cache_user_data(ttl: int = 3600):
    """Cache para datos de usuario"""
    return cache_manager.cached("user_data", ttl=ttl)

def cache_agent_responses(ttl: int = 1800):
    """Cache para respuestas de agentes (30 min)"""
    return cache_manager.cached("agent_responses", ttl=ttl)

def cache_embeddings(ttl: int = 7200):
    """Cache para embeddings (2 horas)"""
    return cache_manager.cached("embeddings", ttl=ttl)

def cache_marketplace_data(ttl: int = 600):
    """Cache para datos del marketplace (10 min)"""
    return cache_manager.cached("marketplace", ttl=ttl)

def cache_analytics(ttl: int = 300):
    """Cache para analíticas (5 min)"""
    return cache_manager.cached("analytics", ttl=ttl)

# Cache layers para diferentes frecuencias de acceso
CACHE_LAYERS = {
    "hot": {"ttl": 300, "description": "Datos muy frecuentes (5 min)"},
    "warm": {"ttl": 1800, "description": "Datos frecuentes (30 min)"},
    "cold": {"ttl": 7200, "description": "Datos ocasionales (2 horas)"},
    "frozen": {"ttl": 86400, "description": "Datos raramente cambiantes (24 horas)"}
}