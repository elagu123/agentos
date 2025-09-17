"""
Connection Pool and Background Jobs Optimizer for AgentOS
Advanced connection management, job queue optimization and resource pooling
"""

from typing import Dict, Any, Optional, List, Callable, Union
import asyncio
import time
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import json
import uuid
from contextlib import asynccontextmanager
import weakref

import asyncpg
import redis.asyncio as redis
import httpx
from sqlalchemy.pool import QueuePool, StaticPool
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class JobPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class JobDefinition:
    id: str
    name: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: JobPriority = JobPriority.NORMAL
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    timeout: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    scheduled_at: Optional[datetime] = None
    retry_count: int = 0
    status: JobStatus = JobStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    execution_time: Optional[float] = None

class ConnectionPoolManager:
    """Gestor avanzado de pools de conexión"""

    def __init__(self):
        self.pools: Dict[str, Any] = {}
        self.pool_stats: Dict[str, Dict[str, Any]] = {}
        self.max_pool_sizes = {
            "database": 20,
            "redis": 10,
            "http": 100,
            "external_api": 5
        }

    async def create_database_pool(
        self,
        connection_string: str,
        pool_name: str = "default",
        min_size: int = 5,
        max_size: int = 20
    ) -> asyncpg.Pool:
        """Crear pool de conexiones PostgreSQL optimizado"""

        if pool_name in self.pools:
            return self.pools[pool_name]

        try:
            pool = await asyncpg.create_pool(
                connection_string,
                min_size=min_size,
                max_size=max_size,
                max_queries=50000,  # Máximo queries por conexión
                max_inactive_connection_lifetime=300,  # 5 minutos
                setup=self._setup_connection,
                server_settings={
                    'application_name': 'agentos_backend',
                    'tcp_keepalives_idle': '600',
                    'tcp_keepalives_interval': '30',
                    'tcp_keepalives_count': '3'
                }
            )

            self.pools[pool_name] = pool
            self.pool_stats[pool_name] = {
                "type": "postgresql",
                "created_at": datetime.utcnow(),
                "connections_created": 0,
                "connections_closed": 0,
                "active_connections": 0,
                "total_queries": 0,
                "failed_queries": 0,
                "avg_query_time": 0.0
            }

            logger.info(f"Created PostgreSQL pool '{pool_name}' with {min_size}-{max_size} connections")
            return pool

        except Exception as e:
            logger.error(f"Failed to create database pool '{pool_name}': {str(e)}")
            raise

    async def _setup_connection(self, connection: asyncpg.Connection):
        """Configurar conexión PostgreSQL"""
        await connection.execute("SET timezone = 'UTC'")
        await connection.execute("SET statement_timeout = '30s'")
        await connection.execute("SET lock_timeout = '10s'")

    async def create_redis_pool(
        self,
        redis_url: str,
        pool_name: str = "default",
        max_connections: int = 10
    ) -> redis.ConnectionPool:
        """Crear pool de conexiones Redis optimizado"""

        if pool_name in self.pools:
            return self.pools[pool_name]

        try:
            pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=max_connections,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={
                    'TCP_KEEPIDLE': 600,
                    'TCP_KEEPINTVL': 30,
                    'TCP_KEEPCNT': 3
                },
                health_check_interval=30
            )

            self.pools[f"redis_{pool_name}"] = pool
            self.pool_stats[f"redis_{pool_name}"] = {
                "type": "redis",
                "created_at": datetime.utcnow(),
                "connections_created": 0,
                "active_connections": 0,
                "total_operations": 0,
                "failed_operations": 0
            }

            logger.info(f"Created Redis pool '{pool_name}' with max {max_connections} connections")
            return pool

        except Exception as e:
            logger.error(f"Failed to create Redis pool '{pool_name}': {str(e)}")
            raise

    async def create_http_pool(
        self,
        pool_name: str = "default",
        max_connections: int = 100,
        max_keepalive: int = 20
    ) -> httpx.AsyncClient:
        """Crear pool de conexiones HTTP optimizado"""

        if pool_name in self.pools:
            return self.pools[pool_name]

        try:
            limits = httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive,
                keepalive_expiry=30.0
            )

            timeout = httpx.Timeout(
                connect=5.0,
                read=30.0,
                write=10.0,
                pool=5.0
            )

            client = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                http2=True,
                follow_redirects=True
            )

            self.pools[f"http_{pool_name}"] = client
            self.pool_stats[f"http_{pool_name}"] = {
                "type": "http",
                "created_at": datetime.utcnow(),
                "requests_made": 0,
                "requests_failed": 0,
                "avg_response_time": 0.0,
                "total_bytes_sent": 0,
                "total_bytes_received": 0
            }

            logger.info(f"Created HTTP pool '{pool_name}' with max {max_connections} connections")
            return client

        except Exception as e:
            logger.error(f"Failed to create HTTP pool '{pool_name}': {str(e)}")
            raise

    @asynccontextmanager
    async def get_db_connection(self, pool_name: str = "default"):
        """Context manager para conexiones de base de datos"""
        pool = self.pools.get(pool_name)
        if not pool:
            raise ValueError(f"Database pool '{pool_name}' not found")

        async with pool.acquire() as connection:
            start_time = time.time()
            try:
                yield connection
                self.pool_stats[pool_name]["total_queries"] += 1
            except Exception as e:
                self.pool_stats[pool_name]["failed_queries"] += 1
                raise
            finally:
                query_time = time.time() - start_time
                stats = self.pool_stats[pool_name]
                total_queries = stats["total_queries"]
                if total_queries > 0:
                    current_avg = stats["avg_query_time"]
                    stats["avg_query_time"] = (current_avg * (total_queries - 1) + query_time) / total_queries

    @asynccontextmanager
    async def get_redis_connection(self, pool_name: str = "default"):
        """Context manager para conexiones Redis"""
        pool = self.pools.get(f"redis_{pool_name}")
        if not pool:
            raise ValueError(f"Redis pool '{pool_name}' not found")

        client = redis.Redis(connection_pool=pool)
        try:
            yield client
            self.pool_stats[f"redis_{pool_name}"]["total_operations"] += 1
        except Exception as e:
            self.pool_stats[f"redis_{pool_name}"]["failed_operations"] += 1
            raise

    async def get_pool_stats(self, pool_name: Optional[str] = None) -> Dict[str, Any]:
        """Obtener estadísticas de pools"""
        if pool_name:
            return self.pool_stats.get(pool_name, {})

        stats = {}
        for name, pool_stats in self.pool_stats.items():
            pool_type = pool_stats["type"]
            pool = self.pools.get(name)

            if pool_type == "postgresql" and pool:
                stats[name] = {
                    **pool_stats,
                    "size": pool.get_size(),
                    "free_connections": pool.get_size() - pool.get_idle_size(),
                    "idle_connections": pool.get_idle_size()
                }
            elif pool_type == "redis" and pool:
                stats[name] = {
                    **pool_stats,
                    "available_connections": pool.connection_kwargs.get("max_connections", 0)
                }
            else:
                stats[name] = pool_stats

        return stats

    async def cleanup_pools(self):
        """Limpiar y cerrar todos los pools"""
        for name, pool in self.pools.items():
            try:
                if hasattr(pool, 'close'):
                    if asyncio.iscoroutinefunction(pool.close):
                        await pool.close()
                    else:
                        pool.close()
                logger.info(f"Closed pool '{name}'")
            except Exception as e:
                logger.error(f"Error closing pool '{name}': {str(e)}")

        self.pools.clear()
        self.pool_stats.clear()

class BackgroundJobManager:
    """Gestor avanzado de trabajos en segundo plano"""

    def __init__(self, max_workers: int = 10, max_queue_size: int = 1000):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size

        # Colas por prioridad
        self.job_queues: Dict[JobPriority, queue.PriorityQueue] = {
            priority: queue.PriorityQueue(maxsize=max_queue_size)
            for priority in JobPriority
        }

        # Tracking de jobs
        self.jobs: Dict[str, JobDefinition] = {}
        self.completed_jobs: queue.Queue = queue.Queue(maxsize=1000)

        # Workers
        self.workers: List[threading.Thread] = []
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.running = False

        # Estadísticas
        self.stats = {
            "jobs_submitted": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "jobs_cancelled": 0,
            "avg_execution_time": 0.0,
            "workers_active": 0,
            "queue_sizes": {priority.name: 0 for priority in JobPriority}
        }

        # Lock para thread safety
        self.lock = threading.RLock()

    def start(self):
        """Iniciar el gestor de jobs"""
        if self.running:
            return

        self.running = True

        # Crear workers para cada prioridad
        for priority in JobPriority:
            worker = threading.Thread(
                target=self._worker_loop,
                args=(priority,),
                daemon=True,
                name=f"JobWorker-{priority.name}"
            )
            worker.start()
            self.workers.append(worker)

        # Worker para jobs scheduled
        scheduled_worker = threading.Thread(
            target=self._scheduled_job_worker,
            daemon=True,
            name="ScheduledJobWorker"
        )
        scheduled_worker.start()
        self.workers.append(scheduled_worker)

        logger.info(f"Started background job manager with {len(self.workers)} workers")

    def stop(self):
        """Detener el gestor de jobs"""
        self.running = False

        # Esperar a que terminen los workers
        for worker in self.workers:
            worker.join(timeout=5.0)

        self.thread_pool.shutdown(wait=True)
        logger.info("Stopped background job manager")

    def submit_job(
        self,
        func: Callable,
        *args,
        name: Optional[str] = None,
        priority: JobPriority = JobPriority.NORMAL,
        max_retries: int = 3,
        retry_delay: int = 60,
        timeout: Optional[int] = None,
        scheduled_at: Optional[datetime] = None,
        **kwargs
    ) -> str:
        """Enviar job para ejecución"""

        job_id = str(uuid.uuid4())
        job_name = name or f"{func.__name__}_{job_id[:8]}"

        job = JobDefinition(
            id=job_id,
            name=job_name,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            scheduled_at=scheduled_at
        )

        with self.lock:
            self.jobs[job_id] = job
            self.stats["jobs_submitted"] += 1

            if scheduled_at and scheduled_at > datetime.utcnow():
                # Job programado para el futuro
                logger.debug(f"Scheduled job '{job_name}' for {scheduled_at}")
            else:
                # Job inmediato
                priority_value = priority.value
                queue_item = (priority_value, time.time(), job_id)

                try:
                    self.job_queues[priority].put_nowait(queue_item)
                    self.stats["queue_sizes"][priority.name] += 1
                    logger.debug(f"Queued job '{job_name}' with priority {priority.name}")
                except queue.Full:
                    job.status = JobStatus.FAILED
                    job.error = "Queue is full"
                    logger.error(f"Failed to queue job '{job_name}': queue is full")

        return job_id

    def _worker_loop(self, priority: JobPriority):
        """Loop principal del worker"""
        job_queue = self.job_queues[priority]

        while self.running:
            try:
                # Esperar por job con timeout
                try:
                    priority_value, queued_time, job_id = job_queue.get(timeout=1.0)
                    with self.lock:
                        self.stats["queue_sizes"][priority.name] -= 1
                except queue.Empty:
                    continue

                # Ejecutar job
                self._execute_job(job_id)

            except Exception as e:
                logger.error(f"Worker error in {priority.name} worker: {str(e)}")

    def _scheduled_job_worker(self):
        """Worker para jobs programados"""
        while self.running:
            try:
                current_time = datetime.utcnow()

                # Buscar jobs programados listos para ejecutar
                ready_jobs = []
                with self.lock:
                    for job_id, job in self.jobs.items():
                        if (job.status == JobStatus.PENDING and
                            job.scheduled_at and
                            job.scheduled_at <= current_time):
                            ready_jobs.append(job_id)

                # Mover jobs listos a las colas de prioridad
                for job_id in ready_jobs:
                    job = self.jobs[job_id]
                    job.scheduled_at = None  # Ya no está programado

                    priority_value = job.priority.value
                    queue_item = (priority_value, time.time(), job_id)

                    try:
                        self.job_queues[job.priority].put_nowait(queue_item)
                        with self.lock:
                            self.stats["queue_sizes"][job.priority.name] += 1
                        logger.debug(f"Moved scheduled job '{job.name}' to execution queue")
                    except queue.Full:
                        job.status = JobStatus.FAILED
                        job.error = "Queue is full when moving from scheduled"

                time.sleep(1)  # Check every second

            except Exception as e:
                logger.error(f"Scheduled job worker error: {str(e)}")

    def _execute_job(self, job_id: str):
        """Ejecutar un job específico"""
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job.status != JobStatus.PENDING:
                return

            job.status = JobStatus.RUNNING
            self.stats["workers_active"] += 1

        start_time = time.time()

        try:
            # Ejecutar función
            if asyncio.iscoroutinefunction(job.func):
                # Función async
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(
                        asyncio.wait_for(
                            job.func(*job.args, **job.kwargs),
                            timeout=job.timeout
                        )
                    )
                finally:
                    loop.close()
            else:
                # Función sync
                if job.timeout:
                    future = self.thread_pool.submit(job.func, *job.args, **job.kwargs)
                    result = future.result(timeout=job.timeout)
                else:
                    result = job.func(*job.args, **job.kwargs)

            # Job completado exitosamente
            execution_time = time.time() - start_time

            with self.lock:
                job.status = JobStatus.COMPLETED
                job.result = result
                job.execution_time = execution_time

                self.stats["jobs_completed"] += 1
                self.stats["workers_active"] -= 1

                # Actualizar tiempo promedio
                total_completed = self.stats["jobs_completed"]
                current_avg = self.stats["avg_execution_time"]
                self.stats["avg_execution_time"] = (
                    (current_avg * (total_completed - 1) + execution_time) / total_completed
                )

                # Mover a completed_jobs
                try:
                    self.completed_jobs.put_nowait(job_id)
                except queue.Full:
                    pass  # No critical if completed queue is full

            logger.debug(f"Job '{job.name}' completed in {execution_time:.3f}s")

        except Exception as e:
            execution_time = time.time() - start_time

            with self.lock:
                job.execution_time = execution_time
                job.error = str(e)

                # Manejar retry
                if job.retry_count < job.max_retries:
                    job.retry_count += 1
                    job.status = JobStatus.RETRYING

                    # Programar retry
                    retry_time = datetime.utcnow() + timedelta(seconds=job.retry_delay)
                    job.scheduled_at = retry_time

                    self.stats["workers_active"] -= 1
                    logger.warning(f"Job '{job.name}' failed, retrying in {job.retry_delay}s (attempt {job.retry_count}/{job.max_retries})")

                else:
                    job.status = JobStatus.FAILED
                    self.stats["jobs_failed"] += 1
                    self.stats["workers_active"] -= 1
                    logger.error(f"Job '{job.name}' failed permanently: {str(e)}")

    def get_job_status(self, job_id: str) -> Optional[JobDefinition]:
        """Obtener estado de un job"""
        return self.jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancelar un job"""
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return False

            if job.status in [JobStatus.PENDING, JobStatus.RETRYING]:
                job.status = JobStatus.CANCELLED
                self.stats["jobs_cancelled"] += 1
                return True

            return False

    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del gestor"""
        with self.lock:
            # Actualizar tamaños de cola
            for priority in JobPriority:
                self.stats["queue_sizes"][priority.name] = self.job_queues[priority].qsize()

            return {
                **self.stats,
                "total_jobs": len(self.jobs),
                "pending_jobs": len([j for j in self.jobs.values() if j.status == JobStatus.PENDING]),
                "running_jobs": len([j for j in self.jobs.values() if j.status == JobStatus.RUNNING]),
                "completed_jobs": len([j for j in self.jobs.values() if j.status == JobStatus.COMPLETED]),
                "failed_jobs": len([j for j in self.jobs.values() if j.status == JobStatus.FAILED]),
                "uptime": time.time() - getattr(self, '_start_time', time.time())
            }

    def cleanup_completed_jobs(self, max_age_hours: int = 24):
        """Limpiar jobs completados antiguos"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        removed_count = 0

        with self.lock:
            jobs_to_remove = []
            for job_id, job in self.jobs.items():
                if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] and
                    job.created_at < cutoff_time):
                    jobs_to_remove.append(job_id)

            for job_id in jobs_to_remove:
                del self.jobs[job_id]
                removed_count += 1

        logger.info(f"Cleaned up {removed_count} old completed jobs")
        return removed_count

# Instancias globales
connection_pool_manager = ConnectionPoolManager()
job_manager = BackgroundJobManager()

# Decorators de conveniencia
def background_job(
    priority: JobPriority = JobPriority.NORMAL,
    max_retries: int = 3,
    timeout: Optional[int] = None
):
    """Decorator para ejecutar función como background job"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            return job_manager.submit_job(
                func,
                *args,
                priority=priority,
                max_retries=max_retries,
                timeout=timeout,
                **kwargs
            )
        return wrapper
    return decorator

def scheduled_job(scheduled_at: datetime, priority: JobPriority = JobPriority.NORMAL):
    """Decorator para jobs programados"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            return job_manager.submit_job(
                func,
                *args,
                scheduled_at=scheduled_at,
                priority=priority,
                **kwargs
            )
        return wrapper
    return decorator

# Funciones de utilidad
async def optimize_connection_pools():
    """Optimizar configuración de pools basado en uso"""
    stats = await connection_pool_manager.get_pool_stats()

    recommendations = []

    for pool_name, pool_stats in stats.items():
        if pool_stats.get("type") == "postgresql":
            # Analizar uso de conexiones
            size = pool_stats.get("size", 0)
            idle = pool_stats.get("idle_connections", 0)
            active = size - idle

            if idle / size > 0.8 and size > 5:
                recommendations.append(f"Pool '{pool_name}': Consider reducing pool size (80%+ idle)")

            if active / size > 0.9:
                recommendations.append(f"Pool '{pool_name}': Consider increasing pool size (90%+ active)")

            avg_query_time = pool_stats.get("avg_query_time", 0)
            if avg_query_time > 1.0:
                recommendations.append(f"Pool '{pool_name}': High average query time ({avg_query_time:.3f}s)")

    return recommendations

def get_system_health() -> Dict[str, Any]:
    """Obtener salud general del sistema de conexiones y jobs"""
    return {
        "connection_pools": connection_pool_manager.pool_stats,
        "background_jobs": job_manager.get_stats(),
        "recommendations": []  # Poblado por optimize_connection_pools()
    }