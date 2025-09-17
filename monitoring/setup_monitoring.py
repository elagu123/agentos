#!/usr/bin/env python3
"""
Complete Monitoring Setup for AgentOS Production
Configures Sentry, Datadog, Prometheus, and custom metrics
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from datadog import initialize, api
    from prometheus_client import start_http_server, Counter, Histogram, Gauge, Info
    import structlog
except ImportError as e:
    print(f"Missing monitoring dependencies: {e}")
    print("Install with: pip install sentry-sdk datadog prometheus-client structlog")
    sys.exit(1)

@dataclass
class MonitoringConfig:
    """Configuration for monitoring services"""

    # Sentry Configuration
    sentry_dsn: str = ""
    sentry_environment: str = "production"
    sentry_traces_sample_rate: float = 0.1
    sentry_profiles_sample_rate: float = 0.1

    # Datadog Configuration
    datadog_api_key: str = ""
    datadog_app_key: str = ""
    datadog_site: str = "datadoghq.com"

    # Prometheus Configuration
    prometheus_port: int = 9090
    prometheus_host: str = "0.0.0.0"

    # Application Metadata
    app_name: str = "agentos"
    app_version: str = "1.0.0"
    environment: str = "production"

    # Feature Flags
    enable_sentry: bool = True
    enable_datadog: bool = True
    enable_prometheus: bool = True
    enable_structured_logging: bool = True

class AgentOSMetrics:
    """Custom metrics for AgentOS application"""

    def __init__(self):
        # API Metrics
        self.api_requests_total = Counter(
            'agentos_api_requests_total',
            'Total API requests',
            ['method', 'endpoint', 'status_code']
        )

        self.api_request_duration = Histogram(
            'agentos_api_request_duration_seconds',
            'API request duration in seconds',
            ['method', 'endpoint'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )

        # Agent Metrics
        self.agent_executions_total = Counter(
            'agentos_agent_executions_total',
            'Total agent executions',
            ['agent_type', 'status', 'user_id']
        )

        self.agent_execution_duration = Histogram(
            'agentos_agent_execution_duration_seconds',
            'Agent execution duration in seconds',
            ['agent_type'],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0]
        )

        self.agent_token_usage = Counter(
            'agentos_agent_token_usage_total',
            'Total LLM tokens used by agents',
            ['agent_type', 'model', 'token_type']
        )

        # Workflow Metrics
        self.workflow_executions_total = Counter(
            'agentos_workflow_executions_total',
            'Total workflow executions',
            ['workflow_type', 'status', 'user_id']
        )

        self.workflow_step_duration = Histogram(
            'agentos_workflow_step_duration_seconds',
            'Workflow step duration in seconds',
            ['workflow_type', 'step_name'],
            buckets=[0.5, 1.0, 5.0, 15.0, 30.0, 60.0, 300.0]
        )

        # User Metrics
        self.active_users = Gauge(
            'agentos_active_users',
            'Currently active users'
        )

        self.user_sessions_total = Counter(
            'agentos_user_sessions_total',
            'Total user sessions',
            ['session_type']
        )

        # System Metrics
        self.database_connections = Gauge(
            'agentos_database_connections',
            'Current database connections',
            ['pool_name']
        )

        self.redis_connections = Gauge(
            'agentos_redis_connections',
            'Current Redis connections'
        )

        self.cache_hit_rate = Gauge(
            'agentos_cache_hit_rate',
            'Cache hit rate percentage',
            ['cache_type']
        )

        # Business Metrics
        self.revenue_total = Counter(
            'agentos_revenue_total_cents',
            'Total revenue in cents',
            ['plan_type', 'billing_cycle']
        )

        self.subscription_changes = Counter(
            'agentos_subscription_changes_total',
            'Total subscription changes',
            ['change_type', 'from_plan', 'to_plan']
        )

        # Integration Metrics
        self.integration_requests = Counter(
            'agentos_integration_requests_total',
            'Total integration requests',
            ['integration', 'operation', 'status']
        )

        self.integration_latency = Histogram(
            'agentos_integration_latency_seconds',
            'Integration request latency',
            ['integration', 'operation'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        )

        # Application Info
        self.app_info = Info(
            'agentos_app_info',
            'Application information'
        )

class MonitoringService:
    """Main monitoring service orchestrator"""

    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.metrics = AgentOSMetrics()
        self.logger = None

    def setup_sentry(self):
        """Configure Sentry error tracking"""
        if not self.config.enable_sentry or not self.config.sentry_dsn:
            print("❌ Sentry disabled or DSN not configured")
            return

        try:
            sentry_sdk.init(
                dsn=self.config.sentry_dsn,
                environment=self.config.sentry_environment,
                traces_sample_rate=self.config.sentry_traces_sample_rate,
                profiles_sample_rate=self.config.sentry_profiles_sample_rate,

                # Integrations
                integrations=[
                    FastApiIntegration(auto_enabling_integrations=False),
                    SqlalchemyIntegration(),
                    RedisIntegration(),
                ],

                # Configuration
                attach_stacktrace=True,
                send_default_pii=False,
                max_breadcrumbs=50,

                # Release information
                release=f"{self.config.app_name}@{self.config.app_version}",

                # Before send hooks
                before_send=self._sentry_before_send,
                before_send_transaction=self._sentry_before_send_transaction,
            )

            # Set user context
            sentry_sdk.set_tag("service", self.config.app_name)
            sentry_sdk.set_tag("environment", self.config.environment)

            print("✅ Sentry configured successfully")

        except Exception as e:
            print(f"❌ Failed to configure Sentry: {e}")

    def _sentry_before_send(self, event, hint):
        """Filter Sentry events before sending"""
        # Skip health check errors
        if 'request' in event and event['request'].get('url', '').endswith('/health'):
            return None

        # Skip rate limiting errors
        if 'exception' in event:
            for exc in event['exception'].get('values', []):
                if 'rate limit' in exc.get('value', '').lower():
                    return None

        return event

    def _sentry_before_send_transaction(self, event, hint):
        """Filter Sentry transactions before sending"""
        # Skip health check transactions
        if event.get('transaction', '').endswith('/health'):
            return None

        return event

    def setup_datadog(self):
        """Configure Datadog monitoring"""
        if not self.config.enable_datadog or not self.config.datadog_api_key:
            print("❌ Datadog disabled or API key not configured")
            return

        try:
            # Initialize Datadog
            initialize(
                api_key=self.config.datadog_api_key,
                app_key=self.config.datadog_app_key,
                api_host=f"https://api.{self.config.datadog_site}"
            )

            # Test connection
            api.Metric.send(
                metric='agentos.monitoring.startup',
                points=[(time.time(), 1)],
                tags=[
                    f'environment:{self.config.environment}',
                    f'service:{self.config.app_name}',
                    f'version:{self.config.app_version}'
                ]
            )

            print("✅ Datadog configured successfully")

        except Exception as e:
            print(f"❌ Failed to configure Datadog: {e}")

    def setup_prometheus(self):
        """Configure Prometheus metrics"""
        if not self.config.enable_prometheus:
            print("❌ Prometheus disabled")
            return

        try:
            # Start Prometheus metrics server
            start_http_server(
                port=self.config.prometheus_port,
                addr=self.config.prometheus_host
            )

            # Set application info
            self.metrics.app_info.info({
                'name': self.config.app_name,
                'version': self.config.app_version,
                'environment': self.config.environment,
                'started_at': datetime.now().isoformat()
            })

            print(f"✅ Prometheus metrics server started on {self.config.prometheus_host}:{self.config.prometheus_port}")

        except Exception as e:
            print(f"❌ Failed to start Prometheus server: {e}")

    def setup_structured_logging(self):
        """Configure structured logging"""
        if not self.config.enable_structured_logging:
            print("❌ Structured logging disabled")
            return

        try:
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
                    self._add_service_context,
                    structlog.processors.JSONRenderer()
                ],
                context_class=dict,
                logger_factory=structlog.stdlib.LoggerFactory(),
                wrapper_class=structlog.stdlib.BoundLogger,
                cache_logger_on_first_use=True,
            )

            self.logger = structlog.get_logger()

            print("✅ Structured logging configured successfully")

        except Exception as e:
            print(f"❌ Failed to configure structured logging: {e}")

    def _add_service_context(self, logger, method_name, event_dict):
        """Add service context to log events"""
        event_dict.update({
            'service': self.config.app_name,
            'version': self.config.app_version,
            'environment': self.config.environment
        })
        return event_dict

    def setup_alerts(self):
        """Configure monitoring alerts"""
        if not self.config.enable_datadog:
            return

        alerts = [
            {
                "name": "AgentOS - High Error Rate",
                "query": "avg(last_5m):sum:agentos.api.errors{environment:production} by {service} > 100",
                "message": """
                🚨 **High Error Rate Alert**

                Error rate is above threshold for AgentOS.

                **Service**: {{service.name}}
                **Environment**: {{environment.name}}
                **Current Rate**: {{value}} errors/5min

                **Runbook**: https://docs.agentos.io/runbooks/high-error-rate

                @slack-agentos-alerts @pagerduty
                """,
                "tags": [
                    f"service:{self.config.app_name}",
                    f"environment:{self.config.environment}",
                    "severity:critical"
                ],
                "options": {
                    "thresholds": {
                        "critical": 100,
                        "warning": 50
                    },
                    "notify_no_data": True,
                    "no_data_timeframe": 10,
                    "evaluation_delay": 60
                }
            },
            {
                "name": "AgentOS - High Response Time",
                "query": "avg(last_5m):avg:agentos.api.response_time{environment:production} > 2000",
                "message": """
                ⏱️ **High Response Time Alert**

                API response time is above threshold.

                **Current P95**: {{value}}ms
                **Threshold**: 2000ms

                @slack-agentos-alerts
                """,
                "tags": [
                    f"service:{self.config.app_name}",
                    f"environment:{self.config.environment}",
                    "severity:warning"
                ],
                "options": {
                    "thresholds": {
                        "critical": 5000,
                        "warning": 2000
                    }
                }
            },
            {
                "name": "AgentOS - Database Connection Pool",
                "query": "avg(last_5m):avg:agentos.database.connections.used{environment:production} / avg:agentos.database.connections.max{environment:production} > 0.9",
                "message": """
                🗄️ **Database Connection Pool Alert**

                Database connection pool utilization is high.

                **Current Utilization**: {{value}}%
                **Threshold**: 90%

                @slack-agentos-alerts
                """,
                "tags": [
                    f"service:{self.config.app_name}",
                    f"environment:{self.config.environment}",
                    "severity:warning"
                ]
            }
        ]

        try:
            for alert in alerts:
                response = api.Monitor.create(
                    type="metric alert",
                    query=alert["query"],
                    name=alert["name"],
                    message=alert["message"],
                    tags=alert["tags"],
                    options=alert.get("options", {})
                )
                print(f"✅ Created alert: {alert['name']}")

        except Exception as e:
            print(f"❌ Failed to create alerts: {e}")

    def create_dashboards(self):
        """Create monitoring dashboards"""
        if not self.config.enable_datadog:
            return

        dashboard_config = {
            "title": "AgentOS Production Dashboard",
            "description": "Comprehensive monitoring for AgentOS production environment",
            "widgets": [
                {
                    "definition": {
                        "type": "timeseries",
                        "requests": [{
                            "q": "avg:agentos.api.requests{*} by {endpoint}.as_rate()",
                            "display_type": "line",
                            "style": {
                                "palette": "dog_classic",
                                "line_type": "solid",
                                "line_width": "normal"
                            }
                        }],
                        "title": "API Requests per Second",
                        "title_size": "16",
                        "title_align": "left",
                        "yaxis": {
                            "min": "auto",
                            "max": "auto",
                            "scale": "linear"
                        }
                    },
                    "layout": {"x": 0, "y": 0, "width": 4, "height": 3}
                },
                {
                    "definition": {
                        "type": "query_value",
                        "requests": [{
                            "q": "avg:agentos.api.response_time{*}",
                            "aggregator": "avg"
                        }],
                        "title": "Average Response Time",
                        "title_size": "16",
                        "title_align": "center",
                        "precision": 2
                    },
                    "layout": {"x": 4, "y": 0, "width": 2, "height": 3}
                },
                {
                    "definition": {
                        "type": "toplist",
                        "requests": [{
                            "q": "top(avg:agentos.agent.executions{*} by {agent_type}.as_rate(), 10, 'mean', 'desc')"
                        }],
                        "title": "Top Agent Types by Usage"
                    },
                    "layout": {"x": 6, "y": 0, "width": 6, "height": 3}
                }
            ],
            "layout_type": "ordered",
            "is_read_only": False,
            "notify_list": [],
            "template_variables": [
                {
                    "name": "environment",
                    "default": "production",
                    "prefix": "environment"
                }
            ]
        }

        try:
            response = api.Dashboard.create(**dashboard_config)
            dashboard_url = f"https://app.{self.config.datadog_site}/dashboard/{response['id']}"
            print(f"✅ Created dashboard: {dashboard_url}")

        except Exception as e:
            print(f"❌ Failed to create dashboard: {e}")

    def initialize_all(self):
        """Initialize all monitoring services"""
        print("🚀 Initializing AgentOS Monitoring...")
        print("=" * 50)

        # Setup services
        self.setup_sentry()
        self.setup_datadog()
        self.setup_prometheus()
        self.setup_structured_logging()

        # Configure advanced features
        if self.config.enable_datadog:
            self.setup_alerts()
            self.create_dashboards()

        print("\n" + "=" * 50)
        print("✅ Monitoring initialization complete!")

        # Log startup event
        if self.logger:
            self.logger.info(
                "Monitoring services initialized",
                sentry_enabled=self.config.enable_sentry,
                datadog_enabled=self.config.enable_datadog,
                prometheus_enabled=self.config.enable_prometheus
            )

        return self.metrics

def load_config_from_env() -> MonitoringConfig:
    """Load monitoring configuration from environment variables"""
    return MonitoringConfig(
        # Sentry
        sentry_dsn=os.getenv("SENTRY_DSN", ""),
        sentry_environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
        sentry_traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        sentry_profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),

        # Datadog
        datadog_api_key=os.getenv("DATADOG_API_KEY", ""),
        datadog_app_key=os.getenv("DATADOG_APP_KEY", ""),
        datadog_site=os.getenv("DATADOG_SITE", "datadoghq.com"),

        # Prometheus
        prometheus_port=int(os.getenv("PROMETHEUS_PORT", "9090")),
        prometheus_host=os.getenv("PROMETHEUS_HOST", "0.0.0.0"),

        # Application
        app_name=os.getenv("APP_NAME", "agentos"),
        app_version=os.getenv("APP_VERSION", "1.0.0"),
        environment=os.getenv("ENVIRONMENT", "production"),

        # Feature flags
        enable_sentry=os.getenv("ENABLE_SENTRY", "true").lower() == "true",
        enable_datadog=os.getenv("ENABLE_DATADOG", "true").lower() == "true",
        enable_prometheus=os.getenv("ENABLE_PROMETHEUS", "true").lower() == "true",
        enable_structured_logging=os.getenv("ENABLE_STRUCTURED_LOGGING", "true").lower() == "true"
    )

def main():
    """Main function for standalone execution"""
    config = load_config_from_env()
    service = MonitoringService(config)
    metrics = service.initialize_all()

    # Keep the script running for testing
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        print("\n🔄 Running in daemon mode... Press Ctrl+C to stop")
        try:
            while True:
                time.sleep(60)
                if service.logger:
                    service.logger.info("Monitoring heartbeat")
        except KeyboardInterrupt:
            print("\n👋 Monitoring service stopped")

if __name__ == "__main__":
    main()