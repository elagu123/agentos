"""
Comprehensive Performance Monitoring System for AgentOS.

This module provides:
- Real-time performance metrics collection
- Database query performance tracking
- API endpoint monitoring
- WebSocket connection analytics
- Cache performance statistics
- LLM usage and cost tracking
- Performance alerting and notifications
"""
import time
import asyncio
import psutil
import structlog
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from app.core.cache import cache_manager
from app.core.websocket_manager import connection_pool
from app.database import get_db

logger = structlog.get_logger(__name__)

@dataclass
class PerformanceMetric:
    """Individual performance metric data point."""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ApiMetrics:
    """API endpoint performance metrics."""
    endpoint: str
    method: str
    response_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    status_codes: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    total_requests: int = 0
    error_count: int = 0
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class DatabaseMetrics:
    """Database performance metrics."""
    query_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    connection_pool_size: int = 0
    active_connections: int = 0
    slow_queries: List[Dict[str, Any]] = field(default_factory=list)
    total_queries: int = 0
    failed_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

@dataclass
class SystemMetrics:
    """System resource metrics."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    disk_usage_percent: float = 0.0
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

class PerformanceMonitor:
    """
    Comprehensive performance monitoring system.

    Features:
    - Real-time metrics collection
    - Performance threshold alerting
    - Historical data storage
    - Automated performance reports
    """

    def __init__(self):
        # Metrics storage
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.api_metrics: Dict[str, ApiMetrics] = {}
        self.db_metrics = DatabaseMetrics()
        self.system_metrics: deque = deque(maxlen=1440)  # 24 hours of minute-by-minute data

        # Performance thresholds
        self.thresholds = {
            'api_response_time': 200,  # ms
            'db_query_time': 100,      # ms
            'cpu_usage': 80,           # %
            'memory_usage': 85,        # %
            'error_rate': 5,           # %
            'cache_hit_rate': 60       # %
        }

        # Alert callbacks
        self.alert_callbacks: List[Callable] = []

        # Background tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        # Performance tracking state
        self._startup_time = time.time()
        self._request_counters = defaultdict(int)

        logger.info("Performance monitor initialized")

    async def start_monitoring(self):
        """Start background monitoring tasks."""
        if not self._monitoring_task:
            self._monitoring_task = asyncio.create_task(self._collect_system_metrics())

        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_old_metrics())

        logger.info("Performance monitoring started")

    async def stop_monitoring(self):
        """Stop background monitoring tasks."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            self._monitoring_task = None

        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

        logger.info("Performance monitoring stopped")

    @asynccontextmanager
    async def track_operation(self, operation_name: str, tags: Dict[str, str] = None):
        """Context manager for tracking operation performance."""
        start_time = time.perf_counter()
        tags = tags or {}

        try:
            yield
        except Exception as e:
            tags['error'] = str(type(e).__name__)
            raise
        finally:
            duration = (time.perf_counter() - start_time) * 1000  # Convert to milliseconds
            await self.record_metric(
                name=f"operation.{operation_name}",
                value=duration,
                tags=tags
            )

    async def record_metric(
        self,
        name: str,
        value: float,
        tags: Dict[str, str] = None,
        metadata: Dict[str, Any] = None
    ):
        """Record a performance metric."""
        metric = PerformanceMetric(
            name=name,
            value=value,
            timestamp=datetime.now(),
            tags=tags or {},
            metadata=metadata or {}
        )

        self.metrics[name].append(metric)

        # Check thresholds and trigger alerts
        await self._check_thresholds(metric)

    async def track_api_request(
        self,
        endpoint: str,
        method: str,
        response_time: float,
        status_code: int
    ):
        """Track API request performance."""
        key = f"{method}:{endpoint}"

        if key not in self.api_metrics:
            self.api_metrics[key] = ApiMetrics(endpoint=endpoint, method=method)

        metrics = self.api_metrics[key]
        metrics.response_times.append(response_time)
        metrics.status_codes[status_code] += 1
        metrics.total_requests += 1

        if status_code >= 400:
            metrics.error_count += 1

        metrics.last_updated = datetime.now()

        # Record as general metric
        await self.record_metric(
            name="api.response_time",
            value=response_time,
            tags={
                'endpoint': endpoint,
                'method': method,
                'status_code': str(status_code)
            }
        )

    async def track_database_query(
        self,
        query_time: float,
        query_type: str = "unknown",
        success: bool = True,
        query_text: str = None
    ):
        """Track database query performance."""
        self.db_metrics.query_times.append(query_time)
        self.db_metrics.total_queries += 1

        if not success:
            self.db_metrics.failed_queries += 1

        # Track slow queries
        if query_time > self.thresholds['db_query_time']:
            self.db_metrics.slow_queries.append({
                'query_time': query_time,
                'query_type': query_type,
                'query_text': query_text[:200] if query_text else None,
                'timestamp': datetime.now().isoformat()
            })

            # Keep only last 100 slow queries
            if len(self.db_metrics.slow_queries) > 100:
                self.db_metrics.slow_queries.pop(0)

        # Record as general metric
        await self.record_metric(
            name="database.query_time",
            value=query_time,
            tags={
                'query_type': query_type,
                'success': str(success)
            }
        )

    async def track_cache_operation(self, operation: str, hit: bool):
        """Track cache operation performance."""
        if hit:
            self.db_metrics.cache_hits += 1
        else:
            self.db_metrics.cache_misses += 1

        await self.record_metric(
            name="cache.operation",
            value=1,
            tags={
                'operation': operation,
                'result': 'hit' if hit else 'miss'
            }
        )

    async def _collect_system_metrics(self):
        """Background task to collect system metrics."""
        while True:
            try:
                # Get system metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')

                # Network metrics (calculate delta from previous reading)
                network = psutil.net_io_counters()

                system_metric = SystemMetrics(
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    memory_used_mb=memory.used / 1024 / 1024,
                    disk_usage_percent=disk.percent,
                    network_sent_mb=network.bytes_sent / 1024 / 1024,
                    network_recv_mb=network.bytes_recv / 1024 / 1024
                )

                self.system_metrics.append(system_metric)

                # Record individual metrics
                await self.record_metric("system.cpu_percent", cpu_percent)
                await self.record_metric("system.memory_percent", memory.percent)
                await self.record_metric("system.disk_percent", disk.percent)

                # WebSocket metrics
                ws_stats = connection_pool.get_connection_stats()
                await self.record_metric("websocket.active_connections", ws_stats.get('active_connections', 0))
                await self.record_metric("websocket.total_messages", ws_stats.get('messages_sent', 0))

                # Cache metrics
                try:
                    cache_stats = await cache_manager.get_stats()
                    if cache_stats:
                        for key, value in cache_stats.items():
                            await self.record_metric(f"cache.{key}", value)
                except Exception as e:
                    logger.warning(f"Failed to collect cache metrics: {e}")

                await asyncio.sleep(60)  # Collect every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
                await asyncio.sleep(60)

    async def _cleanup_old_metrics(self):
        """Background task to clean up old metrics."""
        while True:
            try:
                cutoff_time = datetime.now() - timedelta(hours=24)

                # Clean up metrics older than 24 hours
                for name, metric_deque in self.metrics.items():
                    # Convert to list, filter, and convert back to deque
                    recent_metrics = [
                        metric for metric in metric_deque
                        if metric.timestamp > cutoff_time
                    ]

                    self.metrics[name] = deque(recent_metrics, maxlen=10000)

                # Clean up API metrics
                for key, api_metric in list(self.api_metrics.items()):
                    if api_metric.last_updated < cutoff_time:
                        del self.api_metrics[key]

                logger.debug("Cleaned up old performance metrics")
                await asyncio.sleep(3600)  # Clean up every hour

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error cleaning up metrics: {e}")
                await asyncio.sleep(3600)

    async def _check_thresholds(self, metric: PerformanceMetric):
        """Check if metric exceeds thresholds and trigger alerts."""
        # API response time threshold
        if metric.name == "api.response_time" and metric.value > self.thresholds['api_response_time']:
            await self._trigger_alert(
                "API_SLOW_RESPONSE",
                f"Slow API response: {metric.value:.2f}ms for {metric.tags.get('endpoint', 'unknown')}",
                metric
            )

        # Database query time threshold
        elif metric.name == "database.query_time" and metric.value > self.thresholds['db_query_time']:
            await self._trigger_alert(
                "DATABASE_SLOW_QUERY",
                f"Slow database query: {metric.value:.2f}ms",
                metric
            )

        # System metrics thresholds
        elif metric.name == "system.cpu_percent" and metric.value > self.thresholds['cpu_usage']:
            await self._trigger_alert(
                "HIGH_CPU_USAGE",
                f"High CPU usage: {metric.value:.1f}%",
                metric
            )

        elif metric.name == "system.memory_percent" and metric.value > self.thresholds['memory_usage']:
            await self._trigger_alert(
                "HIGH_MEMORY_USAGE",
                f"High memory usage: {metric.value:.1f}%",
                metric
            )

    async def _trigger_alert(self, alert_type: str, message: str, metric: PerformanceMetric):
        """Trigger performance alert."""
        alert_data = {
            'type': alert_type,
            'message': message,
            'metric': metric,
            'timestamp': datetime.now().isoformat(),
            'severity': 'warning'
        }

        logger.warning(f"Performance alert: {message}", alert_type=alert_type)

        # Call registered alert callbacks
        for callback in self.alert_callbacks:
            try:
                await callback(alert_data)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def register_alert_callback(self, callback: Callable):
        """Register a callback for performance alerts."""
        self.alert_callbacks.append(callback)

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        now = datetime.now()
        uptime = now.timestamp() - self._startup_time

        # Calculate API performance statistics
        api_stats = {}
        for key, metrics in self.api_metrics.items():
            if metrics.response_times:
                response_times = list(metrics.response_times)
                api_stats[key] = {
                    'avg_response_time': sum(response_times) / len(response_times),
                    'p95_response_time': sorted(response_times)[int(len(response_times) * 0.95)],
                    'total_requests': metrics.total_requests,
                    'error_rate': (metrics.error_count / metrics.total_requests * 100) if metrics.total_requests > 0 else 0,
                    'status_codes': dict(metrics.status_codes)
                }

        # Calculate database statistics
        db_stats = {}
        if self.db_metrics.query_times:
            query_times = list(self.db_metrics.query_times)
            cache_total = self.db_metrics.cache_hits + self.db_metrics.cache_misses

            db_stats = {
                'avg_query_time': sum(query_times) / len(query_times),
                'p95_query_time': sorted(query_times)[int(len(query_times) * 0.95)] if query_times else 0,
                'total_queries': self.db_metrics.total_queries,
                'failed_queries': self.db_metrics.failed_queries,
                'slow_queries_count': len(self.db_metrics.slow_queries),
                'cache_hit_rate': (self.db_metrics.cache_hits / cache_total * 100) if cache_total > 0 else 0
            }

        # Get latest system metrics
        current_system = self.system_metrics[-1] if self.system_metrics else None

        # WebSocket statistics
        ws_stats = connection_pool.get_connection_stats()

        return {
            'timestamp': now.isoformat(),
            'uptime_seconds': uptime,
            'system': {
                'cpu_percent': current_system.cpu_percent if current_system else 0,
                'memory_percent': current_system.memory_percent if current_system else 0,
                'memory_used_mb': current_system.memory_used_mb if current_system else 0,
                'disk_usage_percent': current_system.disk_usage_percent if current_system else 0,
            } if current_system else {},
            'api': api_stats,
            'database': db_stats,
            'websocket': ws_stats,
            'thresholds': self.thresholds,
            'alerts_triggered': len(self.alert_callbacks)
        }

    def get_metrics_for_timerange(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[PerformanceMetric]:
        """Get metrics for a specific time range."""
        if metric_name not in self.metrics:
            return []

        return [
            metric for metric in self.metrics[metric_name]
            if start_time <= metric.timestamp <= end_time
        ]

    def clear_metrics(self, older_than: timedelta = None):
        """Clear metrics data."""
        if older_than:
            cutoff_time = datetime.now() - older_than
            for name, metric_deque in self.metrics.items():
                recent_metrics = [
                    metric for metric in metric_deque
                    if metric.timestamp > cutoff_time
                ]
                self.metrics[name] = deque(recent_metrics, maxlen=10000)
        else:
            self.metrics.clear()
            self.api_metrics.clear()
            self.db_metrics = DatabaseMetrics()
            self.system_metrics.clear()

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

# Convenience decorator for tracking function performance
def track_performance(operation_name: str = None, tags: Dict[str, str] = None):
    """Decorator to track function performance."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            async with performance_monitor.track_operation(name, tags):
                return await func(*args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = (time.perf_counter() - start_time) * 1000
                # Schedule metric recording for sync functions
                asyncio.create_task(
                    performance_monitor.record_metric(
                        name=f"operation.{name}",
                        value=duration,
                        tags=tags or {}
                    )
                )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator