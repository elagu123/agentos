"""
Monitoring Middleware for AgentOS
Integrates metrics collection and tracing with FastAPI
"""

import time
import logging
from typing import Callable, Dict, Any, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import structlog
from prometheus_client import Counter, Histogram, Gauge
import sentry_sdk
from sentry_sdk import set_tag, set_user, capture_exception

logger = structlog.get_logger(__name__)

class MonitoringMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive monitoring middleware for FastAPI applications.
    Collects metrics, traces requests, and integrates with monitoring services.
    """

    def __init__(
        self,
        app: ASGIApp,
        metrics: Optional[Any] = None,
        enable_detailed_logging: bool = True,
        exclude_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.metrics = metrics
        self.enable_detailed_logging = enable_detailed_logging
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/favicon.ico"]

        # Initialize basic metrics if not provided
        if not self.metrics:
            self._init_default_metrics()

    def _init_default_metrics(self):
        """Initialize default metrics"""
        class DefaultMetrics:
            def __init__(self):
                self.api_requests_total = Counter(
                    'http_requests_total',
                    'Total HTTP requests',
                    ['method', 'endpoint', 'status_code']
                )
                self.api_request_duration = Histogram(
                    'http_request_duration_seconds',
                    'HTTP request duration',
                    ['method', 'endpoint']
                )
                self.active_requests = Gauge(
                    'http_requests_active',
                    'Currently active HTTP requests'
                )

        self.metrics = DefaultMetrics()

    def _should_monitor_request(self, path: str) -> bool:
        """Check if request should be monitored"""
        return not any(excluded in path for excluded in self.exclude_paths)

    def _extract_endpoint_pattern(self, request: Request) -> str:
        """Extract endpoint pattern from request"""
        # Try to get the route pattern
        if hasattr(request, 'scope') and 'route' in request.scope:
            route = request.scope['route']
            if hasattr(route, 'path'):
                return route.path

        # Fallback to path with parameter normalization
        path = request.url.path

        # Normalize common patterns
        path_parts = path.split('/')
        normalized_parts = []

        for part in path_parts:
            # Replace UUIDs with placeholder
            if len(part) == 36 and part.count('-') == 4:
                normalized_parts.append('{id}')
            # Replace numeric IDs with placeholder
            elif part.isdigit():
                normalized_parts.append('{id}')
            else:
                normalized_parts.append(part)

        return '/'.join(normalized_parts)

    def _extract_user_context(self, request: Request) -> Dict[str, Any]:
        """Extract user context from request"""
        user_context = {}

        # Check for user in request state
        if hasattr(request.state, 'user'):
            user = request.state.user
            user_context.update({
                'user_id': getattr(user, 'id', None),
                'user_email': getattr(user, 'email', None),
                'organization_id': getattr(user, 'organization_id', None)
            })

        # Check authorization header
        auth_header = request.headers.get('authorization')
        if auth_header:
            user_context['has_auth'] = True

        return user_context

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Main middleware processing function"""
        start_time = time.time()

        # Skip monitoring for excluded paths
        if not self._should_monitor_request(request.url.path):
            return await call_next(request)

        # Extract request information
        method = request.method
        endpoint = self._extract_endpoint_pattern(request)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Increment active requests
        if hasattr(self.metrics, 'active_requests'):
            self.metrics.active_requests.inc()

        # Set Sentry context
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("endpoint", endpoint)
            scope.set_tag("method", method)
            scope.set_context("request", {
                "url": str(request.url),
                "method": method,
                "headers": dict(request.headers),
                "client_ip": client_ip
            })

            # Set user context
            user_context = self._extract_user_context(request)
            if user_context:
                scope.set_user(user_context)

        # Start transaction for tracing
        transaction = sentry_sdk.start_transaction(
            op="http.server",
            name=f"{method} {endpoint}"
        )

        response = None
        status_code = 500
        error = None

        try:
            # Process request
            response = await call_next(request)
            status_code = response.status_code

        except Exception as e:
            error = e
            capture_exception(e)
            status_code = 500

            # Create error response
            from fastapi.responses import JSONResponse
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )

        finally:
            # Calculate duration
            duration = time.time() - start_time

            # Decrement active requests
            if hasattr(self.metrics, 'active_requests'):
                self.metrics.active_requests.dec()

            # Record metrics
            self._record_metrics(method, endpoint, status_code, duration)

            # Log request
            self._log_request(
                request, response, duration, status_code,
                client_ip, user_agent, error
            )

            # Finish transaction
            transaction.set_http_status(status_code)
            transaction.finish()

            # Add response headers
            if response:
                response.headers["X-Process-Time"] = str(duration)
                response.headers["X-Request-ID"] = getattr(request.state, 'request_id', 'unknown')

        return response

    def _record_metrics(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record request metrics"""
        try:
            # Record request count
            if hasattr(self.metrics, 'api_requests_total'):
                self.metrics.api_requests_total.labels(
                    method=method,
                    endpoint=endpoint,
                    status_code=str(status_code)
                ).inc()

            # Record request duration
            if hasattr(self.metrics, 'api_request_duration'):
                self.metrics.api_request_duration.labels(
                    method=method,
                    endpoint=endpoint
                ).observe(duration)

        except Exception as e:
            logger.error("Failed to record metrics", error=str(e))

    def _log_request(
        self,
        request: Request,
        response: Response,
        duration: float,
        status_code: int,
        client_ip: str,
        user_agent: str,
        error: Optional[Exception] = None
    ):
        """Log request details"""
        if not self.enable_detailed_logging:
            return

        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration": round(duration, 4),
            "client_ip": client_ip,
            "user_agent": user_agent,
            "query_params": dict(request.query_params),
        }

        # Add user context if available
        user_context = self._extract_user_context(request)
        if user_context:
            log_data["user"] = user_context

        # Add response size if available
        if response and hasattr(response, 'headers'):
            content_length = response.headers.get('content-length')
            if content_length:
                log_data["response_size"] = int(content_length)

        # Log based on status code
        if error:
            logger.error("Request failed", **log_data, error=str(error))
        elif status_code >= 500:
            logger.error("Server error", **log_data)
        elif status_code >= 400:
            logger.warning("Client error", **log_data)
        else:
            logger.info("Request completed", **log_data)


class MetricsCollector:
    """Centralized metrics collection for AgentOS"""

    def __init__(self, metrics):
        self.metrics = metrics
        self.logger = structlog.get_logger(__name__)

    def record_agent_execution(
        self,
        agent_type: str,
        duration: float,
        status: str,
        user_id: Optional[str] = None,
        token_usage: Optional[Dict[str, int]] = None
    ):
        """Record agent execution metrics"""
        try:
            # Record execution count
            if hasattr(self.metrics, 'agent_executions_total'):
                self.metrics.agent_executions_total.labels(
                    agent_type=agent_type,
                    status=status,
                    user_id=user_id or "anonymous"
                ).inc()

            # Record execution duration
            if hasattr(self.metrics, 'agent_execution_duration'):
                self.metrics.agent_execution_duration.labels(
                    agent_type=agent_type
                ).observe(duration)

            # Record token usage
            if token_usage and hasattr(self.metrics, 'agent_token_usage'):
                for token_type, count in token_usage.items():
                    self.metrics.agent_token_usage.labels(
                        agent_type=agent_type,
                        model=token_usage.get('model', 'unknown'),
                        token_type=token_type
                    ).inc(count)

            self.logger.info(
                "Agent execution recorded",
                agent_type=agent_type,
                duration=duration,
                status=status,
                user_id=user_id,
                token_usage=token_usage
            )

        except Exception as e:
            self.logger.error("Failed to record agent metrics", error=str(e))

    def record_workflow_execution(
        self,
        workflow_type: str,
        status: str,
        user_id: Optional[str] = None,
        step_durations: Optional[Dict[str, float]] = None
    ):
        """Record workflow execution metrics"""
        try:
            # Record workflow count
            if hasattr(self.metrics, 'workflow_executions_total'):
                self.metrics.workflow_executions_total.labels(
                    workflow_type=workflow_type,
                    status=status,
                    user_id=user_id or "anonymous"
                ).inc()

            # Record step durations
            if step_durations and hasattr(self.metrics, 'workflow_step_duration'):
                for step_name, duration in step_durations.items():
                    self.metrics.workflow_step_duration.labels(
                        workflow_type=workflow_type,
                        step_name=step_name
                    ).observe(duration)

            self.logger.info(
                "Workflow execution recorded",
                workflow_type=workflow_type,
                status=status,
                user_id=user_id,
                step_durations=step_durations
            )

        except Exception as e:
            self.logger.error("Failed to record workflow metrics", error=str(e))

    def update_system_metrics(self, metrics_data: Dict[str, Any]):
        """Update system-level metrics"""
        try:
            # Update database connections
            if 'database_connections' in metrics_data and hasattr(self.metrics, 'database_connections'):
                for pool_name, count in metrics_data['database_connections'].items():
                    self.metrics.database_connections.labels(pool_name=pool_name).set(count)

            # Update Redis connections
            if 'redis_connections' in metrics_data and hasattr(self.metrics, 'redis_connections'):
                self.metrics.redis_connections.set(metrics_data['redis_connections'])

            # Update cache hit rates
            if 'cache_hit_rates' in metrics_data and hasattr(self.metrics, 'cache_hit_rate'):
                for cache_type, rate in metrics_data['cache_hit_rates'].items():
                    self.metrics.cache_hit_rate.labels(cache_type=cache_type).set(rate)

            # Update active users
            if 'active_users' in metrics_data and hasattr(self.metrics, 'active_users'):
                self.metrics.active_users.set(metrics_data['active_users'])

        except Exception as e:
            self.logger.error("Failed to update system metrics", error=str(e))

    def record_business_metric(self, metric_type: str, value: float, labels: Dict[str, str]):
        """Record business metrics"""
        try:
            if metric_type == "revenue" and hasattr(self.metrics, 'revenue_total'):
                self.metrics.revenue_total.labels(**labels).inc(value)

            elif metric_type == "subscription_change" and hasattr(self.metrics, 'subscription_changes'):
                self.metrics.subscription_changes.labels(**labels).inc()

            self.logger.info(
                "Business metric recorded",
                metric_type=metric_type,
                value=value,
                labels=labels
            )

        except Exception as e:
            self.logger.error("Failed to record business metric", error=str(e))

    def record_integration_request(
        self,
        integration: str,
        operation: str,
        status: str,
        duration: float
    ):
        """Record integration request metrics"""
        try:
            # Record request count
            if hasattr(self.metrics, 'integration_requests'):
                self.metrics.integration_requests.labels(
                    integration=integration,
                    operation=operation,
                    status=status
                ).inc()

            # Record latency
            if hasattr(self.metrics, 'integration_latency'):
                self.metrics.integration_latency.labels(
                    integration=integration,
                    operation=operation
                ).observe(duration)

            self.logger.info(
                "Integration request recorded",
                integration=integration,
                operation=operation,
                status=status,
                duration=duration
            )

        except Exception as e:
            self.logger.error("Failed to record integration metrics", error=str(e))