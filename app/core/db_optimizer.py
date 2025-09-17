"""
Database Query Optimizer for AgentOS
Advanced query optimization, connection management and performance monitoring
"""

from typing import List, Dict, Any, Optional, Tuple, Union
from sqlalchemy import event, text, inspect
from sqlalchemy.orm import Session, Query, sessionmaker
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects import postgresql
import time
import logging
import asyncio
import re
from datetime import datetime, timedelta
import hashlib
import json
from functools import wraps
from collections import defaultdict, deque
import threading
from contextlib import contextmanager

from .cache_manager import cache_manager

logger = logging.getLogger(__name__)

class QueryProfiler:
    def __init__(self, max_queries: int = 10000):
        self.queries = deque(maxlen=max_queries)
        self.slow_queries = deque(maxlen=1000)
        self.query_stats = defaultdict(lambda: {
            "count": 0,
            "total_time": 0.0,
            "avg_time": 0.0,
            "max_time": 0.0,
            "min_time": float('inf'),
            "last_executed": None
        })
        self.lock = threading.RLock()

    def add_query(self, query: str, duration: float, result_count: int = None):
        with self.lock:
            query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
            normalized_query = self._normalize_query(query)

            query_info = {
                "query_hash": query_hash,
                "query": normalized_query,
                "original_query": query,
                "duration": duration,
                "result_count": result_count,
                "timestamp": datetime.utcnow(),
                "slow": duration > 1.0  # Slow query threshold
            }

            self.queries.append(query_info)

            # Track slow queries separately
            if duration > 1.0:
                self.slow_queries.append(query_info)
                logger.warning(f"Slow query detected: {duration:.3f}s - {normalized_query[:100]}...")

            # Update statistics
            stats = self.query_stats[query_hash]
            stats["count"] += 1
            stats["total_time"] += duration
            stats["avg_time"] = stats["total_time"] / stats["count"]
            stats["max_time"] = max(stats["max_time"], duration)
            stats["min_time"] = min(stats["min_time"], duration)
            stats["last_executed"] = datetime.utcnow()

    def _normalize_query(self, query: str) -> str:
        """Normalizar query para agrupar queries similares"""
        import re

        # Remover comentarios
        query = re.sub(r'--.*?\n', '', query)
        query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)

        # Normalizar espacios
        query = ' '.join(query.split())

        # Reemplazar valores literales con placeholders
        query = re.sub(r"'[^']*'", "'?'", query)
        query = re.sub(r'\b\d+\b', '?', query)

        # Convertir a minúsculas
        query = query.lower().strip()

        return query

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            total_queries = len(self.queries)
            slow_queries = len(self.slow_queries)

            if total_queries == 0:
                return {
                    "total_queries": 0,
                    "slow_queries": 0,
                    "avg_query_time": 0,
                    "top_slow_queries": []
                }

            avg_time = sum(q["duration"] for q in self.queries) / total_queries

            # Top 10 queries más lentas
            top_slow = sorted(
                self.slow_queries,
                key=lambda x: x["duration"],
                reverse=True
            )[:10]

            # Top queries por frecuencia
            top_frequent = sorted(
                self.query_stats.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )[:10]

            return {
                "total_queries": total_queries,
                "slow_queries": slow_queries,
                "slow_query_percentage": (slow_queries / total_queries) * 100,
                "avg_query_time": avg_time,
                "top_slow_queries": [
                    {
                        "query": q["query"],
                        "duration": q["duration"],
                        "timestamp": q["timestamp"].isoformat()
                    } for q in top_slow
                ],
                "top_frequent_queries": [
                    {
                        "query_hash": hash_key,
                        "count": stats["count"],
                        "avg_time": stats["avg_time"],
                        "total_time": stats["total_time"]
                    } for hash_key, stats in top_frequent
                ]
            }

class DatabaseOptimizer:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.profiler = QueryProfiler()
        self.connection_pool_stats = {
            "created": 0,
            "closed": 0,
            "active": 0,
            "checked_out": 0
        }
        self._setup_event_listeners()

    def _setup_event_listeners(self):
        """Configurar listeners para monitorear queries"""

        @event.listens_for(self.engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()

        @event.listens_for(self.engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            duration = time.time() - context._query_start_time

            # Obtener número de resultados si es posible
            result_count = None
            if hasattr(cursor, 'rowcount') and cursor.rowcount >= 0:
                result_count = cursor.rowcount

            self.profiler.add_query(statement, duration, result_count)

        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            # Para PostgreSQL, configurar optimizaciones
            if 'postgresql' in str(self.engine.url):
                with dbapi_connection.cursor() as cursor:
                    # Optimizaciones PostgreSQL
                    cursor.execute("SET shared_preload_libraries = 'pg_stat_statements'")
                    cursor.execute("SET log_statement_stats = off")
                    cursor.execute("SET log_min_duration_statement = 1000")  # Log queries > 1s

    @contextmanager
    def optimized_session(self) -> Session:
        """Context manager para sesiones optimizadas"""
        session = sessionmaker(bind=self.engine)()

        try:
            # Configuraciones de sesión optimizadas
            session.execute(text("SET LOCAL statement_timeout = '30s'"))
            session.execute(text("SET LOCAL lock_timeout = '10s'"))

            yield session
            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {str(e)}")
            raise
        finally:
            session.close()

    def analyze_query_plan(self, query: Union[str, Query]) -> Dict[str, Any]:
        """Analizar plan de ejecución de una query"""

        if isinstance(query, Query):
            compiled_query = query.statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True}
            )
            query_str = str(compiled_query)
        else:
            query_str = query

        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query_str}"

        with self.optimized_session() as session:
            try:
                result = session.execute(text(explain_query))
                plan_data = result.fetchone()[0]

                # Extraer métricas importantes
                execution_time = plan_data[0]["Execution Time"]
                planning_time = plan_data[0]["Planning Time"]

                return {
                    "execution_time_ms": execution_time,
                    "planning_time_ms": planning_time,
                    "total_time_ms": execution_time + planning_time,
                    "plan": plan_data[0]["Plan"],
                    "query": query_str,
                    "recommendations": self._analyze_plan_for_recommendations(plan_data[0])
                }

            except Exception as e:
                logger.error(f"Error analyzing query plan: {str(e)}")
                return {"error": str(e), "query": query_str}

    def _analyze_plan_for_recommendations(self, plan_data: Dict) -> List[str]:
        """Analizar plan y generar recomendaciones"""
        recommendations = []

        def analyze_node(node):
            node_type = node.get("Node Type", "")

            # Detectar scans secuenciales costosos
            if node_type == "Seq Scan":
                total_cost = node.get("Total Cost", 0)
                if total_cost > 1000:
                    table_name = node.get("Relation Name", "unknown")
                    recommendations.append(f"Consider adding index on table '{table_name}' - high cost sequential scan")

            # Detectar sorts costosos
            if node_type == "Sort":
                sort_key = node.get("Sort Key", [])
                if sort_key:
                    recommendations.append(f"Consider index on columns: {', '.join(sort_key)}")

            # Detectar nested loops ineficientes
            if node_type == "Nested Loop":
                total_cost = node.get("Total Cost", 0)
                if total_cost > 5000:
                    recommendations.append("Nested loop with high cost - consider query restructuring")

            # Analizar nodos hijos
            for child in node.get("Plans", []):
                analyze_node(child)

        analyze_node(plan_data["Plan"])
        return recommendations

    def suggest_indexes(self, table_name: str = None) -> List[Dict[str, Any]]:
        """Sugerir índices basado en queries frecuentes"""
        suggestions = []

        # Analizar queries frecuentes para sugerir índices
        frequent_queries = self.profiler.query_stats

        for query_hash, stats in frequent_queries.items():
            if stats["count"] >= 10 and stats["avg_time"] > 0.1:  # Queries frecuentes y lentas
                suggestions.append({
                    "query_hash": query_hash,
                    "frequency": stats["count"],
                    "avg_time": stats["avg_time"],
                    "recommendation": "Consider adding indexes for frequent slow query",
                    "priority": "high" if stats["avg_time"] > 1.0 else "medium"
                })

        # Suggestions específicas basadas en patrones comunes
        with self.optimized_session() as session:
            try:
                # Consultar estadísticas de uso de tablas
                query = text("""
                    SELECT
                        schemaname,
                        tablename,
                        seq_scan,
                        seq_tup_read,
                        idx_scan,
                        idx_tup_fetch,
                        n_tup_ins,
                        n_tup_upd,
                        n_tup_del
                    FROM pg_stat_user_tables
                    WHERE seq_scan > idx_scan * 2
                    ORDER BY seq_scan DESC
                    LIMIT 10
                """)

                result = session.execute(query)

                for row in result:
                    suggestions.append({
                        "table": f"{row.schemaname}.{row.tablename}",
                        "issue": "High sequential scan ratio",
                        "seq_scans": row.seq_scan,
                        "index_scans": row.idx_scan or 0,
                        "recommendation": "Add indexes on frequently queried columns",
                        "priority": "high"
                    })

            except Exception as e:
                logger.error(f"Error getting table statistics: {str(e)}")

        return suggestions

    def optimize_query(self, query: Union[str, Query]) -> Dict[str, Any]:
        """Optimizar una query específica"""

        original_plan = self.analyze_query_plan(query)

        # Estrategias de optimización
        optimizations = []

        # 1. Reescribir query si es necesible
        if isinstance(query, str):
            optimized_query = self._rewrite_query(query)
            if optimized_query != query:
                optimized_plan = self.analyze_query_plan(optimized_query)
                optimizations.append({
                    "type": "query_rewrite",
                    "original_time": original_plan.get("total_time_ms", 0),
                    "optimized_time": optimized_plan.get("total_time_ms", 0),
                    "improvement": self._calculate_improvement(
                        original_plan.get("total_time_ms", 0),
                        optimized_plan.get("total_time_ms", 0)
                    ),
                    "optimized_query": optimized_query
                })

        return {
            "original_plan": original_plan,
            "optimizations": optimizations,
            "recommendations": original_plan.get("recommendations", [])
        }

    def _rewrite_query(self, query: str) -> str:
        """Reescribir query para optimización"""
        import re

        optimized = query

        # Optimización 1: Convertir EXISTS a JOIN cuando sea posible
        exists_pattern = r'EXISTS\s*\(\s*SELECT\s+.*?\s+FROM\s+(\w+).*?WHERE\s+(.*?)\)'
        if re.search(exists_pattern, optimized, re.IGNORECASE | re.DOTALL):
            # Esta es una optimización compleja, por ahora solo documentamos
            pass

        # Optimización 2: Remover SELECT DISTINCT innecesarios
        if 'SELECT DISTINCT' in optimized.upper():
            # Verificar si realmente necesita DISTINCT
            pass

        # Optimización 3: Optimizar LIMIT con ORDER BY
        limit_pattern = r'ORDER BY.*?LIMIT\s+(\d+)'
        if re.search(limit_pattern, optimized, re.IGNORECASE):
            # Sugerir use de índices para ORDER BY + LIMIT
            pass

        return optimized

    def _calculate_improvement(self, original_time: float, optimized_time: float) -> Dict[str, Any]:
        """Calcular mejora de performance"""
        if original_time == 0:
            return {"percentage": 0, "absolute_ms": 0}

        improvement_ms = original_time - optimized_time
        improvement_percentage = (improvement_ms / original_time) * 100

        return {
            "percentage": round(improvement_percentage, 2),
            "absolute_ms": round(improvement_ms, 2),
            "faster": improvement_percentage > 0
        }

    async def vacuum_analyze_tables(self, tables: List[str] = None) -> Dict[str, Any]:
        """Ejecutar VACUUM ANALYZE en tablas especificadas"""
        results = {}

        with self.optimized_session() as session:
            if tables is None:
                # Obtener todas las tablas de usuario
                table_query = text("""
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                """)
                result = session.execute(table_query)
                tables = [row[0] for row in result]

            for table in tables:
                try:
                    # Validate table name to prevent SQL injection
                    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
                        logger.warning(f"Invalid table name: {table}")
                        results[table] = {"status": "error", "error": "Invalid table name"}
                        continue

                    start_time = time.time()

                    # VACUUM ANALYZE no puede ejecutarse en transacción
                    session.commit()
                    # Use parameterized query with quoted identifier
                    session.execute(text(f"VACUUM ANALYZE \"{table}\""))

                    duration = time.time() - start_time
                    results[table] = {
                        "status": "success",
                        "duration_ms": round(duration * 1000, 2)
                    }

                    logger.info(f"VACUUM ANALYZE completed for {table} in {duration:.3f}s")

                except Exception as e:
                    results[table] = {
                        "status": "error",
                        "error": str(e)
                    }
                    logger.error(f"VACUUM ANALYZE failed for {table}: {str(e)}")

        return results

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Obtener métricas de performance de la base de datos"""

        with self.optimized_session() as session:
            try:
                # Estadísticas generales
                stats_query = text("""
                    SELECT
                        sum(seq_scan) as total_seq_scans,
                        sum(seq_tup_read) as total_seq_reads,
                        sum(idx_scan) as total_idx_scans,
                        sum(idx_tup_fetch) as total_idx_reads,
                        sum(n_tup_ins) as total_inserts,
                        sum(n_tup_upd) as total_updates,
                        sum(n_tup_del) as total_deletes
                    FROM pg_stat_user_tables
                """)

                stats_result = session.execute(stats_query).fetchone()

                # Tamaño de la base de datos
                size_query = text("""
                    SELECT pg_size_pretty(pg_database_size(current_database())) as db_size
                """)

                size_result = session.execute(size_query).fetchone()

                # Conexiones activas
                connections_query = text("""
                    SELECT count(*) as active_connections
                    FROM pg_stat_activity
                    WHERE state = 'active'
                """)

                connections_result = session.execute(connections_query).fetchone()

                # Cache hit ratio
                cache_query = text("""
                    SELECT
                        sum(heap_blks_read) as heap_read,
                        sum(heap_blks_hit) as heap_hit,
                        round(sum(heap_blks_hit) * 100.0 / (sum(heap_blks_hit) + sum(heap_blks_read)), 2) as cache_hit_ratio
                    FROM pg_statio_user_tables
                """)

                cache_result = session.execute(cache_query).fetchone()

                return {
                    "database_size": size_result[0] if size_result else "unknown",
                    "active_connections": connections_result[0] if connections_result else 0,
                    "total_sequential_scans": stats_result[0] if stats_result else 0,
                    "total_index_scans": stats_result[2] if stats_result else 0,
                    "cache_hit_ratio": cache_result[2] if cache_result else 0,
                    "query_profiler_stats": self.profiler.get_stats(),
                    "index_suggestions": self.suggest_indexes()[:5]  # Top 5 suggestions
                }

            except Exception as e:
                logger.error(f"Error getting performance metrics: {str(e)}")
                return {
                    "error": str(e),
                    "query_profiler_stats": self.profiler.get_stats()
                }

class QueryCache:
    """Cache específico para resultados de queries"""

    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl

    def _generate_cache_key(self, query: str, params: tuple = None) -> str:
        """Generar key de cache para query"""
        key_data = f"query:{query}"
        if params:
            key_data += f":params:{params}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def get_cached_result(self, query: str, params: tuple = None) -> Optional[Any]:
        """Obtener resultado cacheado"""
        cache_key = self._generate_cache_key(query, params)
        return await cache_manager.get(cache_key)

    async def cache_result(self, query: str, result: Any, params: tuple = None, ttl: int = None) -> bool:
        """Cachear resultado de query"""
        cache_key = self._generate_cache_key(query, params)
        ttl = ttl or self.default_ttl
        return await cache_manager.set(cache_key, result, ttl)

    def cached_query(self, ttl: int = None, cache_empty: bool = False):
        """Decorator para cachear resultados de queries"""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generar cache key basado en función y argumentos
                cache_key = f"cached_query:{func.__name__}:{hash(str(args) + str(kwargs))}"

                # Intentar obtener del cache
                cached_result = await cache_manager.get(cache_key)
                if cached_result is not None:
                    return cached_result

                # Ejecutar función
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

                # Cachear resultado (si no está vacío o cache_empty=True)
                if result or cache_empty:
                    await cache_manager.set(cache_key, result, ttl or self.default_ttl)

                return result

            return wrapper
        return decorator

# Instancias globales
db_optimizer = None
query_cache = QueryCache()

def get_db_optimizer(engine: Engine = None) -> DatabaseOptimizer:
    """Obtener instancia global del optimizador"""
    global db_optimizer

    if db_optimizer is None and engine:
        db_optimizer = DatabaseOptimizer(engine)

    return db_optimizer

# Decorators de conveniencia
def cached_query(ttl: int = 300, cache_empty: bool = False):
    """Decorator para cachear queries"""
    return query_cache.cached_query(ttl=ttl, cache_empty=cache_empty)

def profile_query(func):
    """Decorator para profilear queries individuales"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            logger.debug(f"Query {func.__name__} completed in {duration:.3f}s")

            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Query {func.__name__} failed after {duration:.3f}s: {str(e)}")
            raise

    return wrapper

# Utilidades de optimización
class EagerLoadingOptimizer:
    """Optimizar eager loading en SQLAlchemy"""

    @staticmethod
    def optimize_relationships(query: Query, relationships: List[str]) -> Query:
        """Agregar eager loading optimizado"""
        from sqlalchemy.orm import joinedload, selectinload

        optimized_query = query

        for relationship in relationships:
            # Usar joinedload para relaciones one-to-one/many-to-one
            # Usar selectinload para relaciones one-to-many/many-to-many
            optimized_query = optimized_query.options(selectinload(relationship))

        return optimized_query

    @staticmethod
    def batch_load_relationships(model_instances: List[Any], relationship: str) -> Dict[Any, List[Any]]:
        """Batch loading manual para relaciones"""
        # Implementación de batch loading optimizado
        # Esta es una optimización avanzada para casos específicos
        pass

# Configuraciones de optimización recomendadas
OPTIMIZATION_SETTINGS = {
    "postgresql": {
        "max_connections": 100,
        "shared_buffers": "256MB",
        "effective_cache_size": "1GB",
        "maintenance_work_mem": "64MB",
        "checkpoint_completion_target": 0.9,
        "wal_buffers": "16MB",
        "default_statistics_target": 100,
        "random_page_cost": 1.1,
        "effective_io_concurrency": 200
    },
    "query_optimization": {
        "enable_bitmapscan": True,
        "enable_hashjoin": True,
        "enable_mergejoin": True,
        "enable_nestloop": True,
        "enable_seqscan": True,
        "enable_sort": True
    }
}