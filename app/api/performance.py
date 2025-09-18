"""
Performance monitoring API endpoints for AgentOS.

This module provides:
- Real-time performance metrics
- Performance dashboard data
- Alert management
- Performance reports
- System health checks
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import structlog

from app.core.auth import get_current_user, require_admin
from app.core.performance_monitor import performance_monitor
from app.models.users import User

logger = structlog.get_logger(__name__)
router = APIRouter()

# Pydantic models for API responses
class PerformanceSummaryResponse(BaseModel):
    timestamp: str
    uptime_seconds: float
    system: Dict[str, Any]
    api: Dict[str, Any]
    database: Dict[str, Any]
    websocket: Dict[str, Any]
    thresholds: Dict[str, Any]
    alerts_triggered: int

class MetricDataPoint(BaseModel):
    timestamp: str
    value: float
    tags: Dict[str, str]
    metadata: Dict[str, Any]

class AlertThreshold(BaseModel):
    metric_name: str
    threshold_value: float
    comparison: str = "greater_than"  # greater_than, less_than, equals

class PerformanceReport(BaseModel):
    period: str
    generated_at: str
    summary: Dict[str, Any]
    top_slow_endpoints: List[Dict[str, Any]]
    top_slow_queries: List[Dict[str, Any]]
    performance_trends: Dict[str, Any]
    recommendations: List[str]

@router.get("/performance/summary", response_model=PerformanceSummaryResponse)
async def get_performance_summary(
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive performance summary.

    Returns real-time performance metrics across all system components.
    """
    try:
        summary = performance_monitor.get_performance_summary()
        return PerformanceSummaryResponse(**summary)
    except Exception as e:
        logger.error(f"Failed to get performance summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve performance data")

@router.get("/performance/metrics/{metric_name}")
async def get_metric_data(
    metric_name: str,
    hours: int = Query(1, ge=1, le=24),
    current_user: User = Depends(get_current_user)
) -> List[MetricDataPoint]:
    """
    Get historical data for a specific metric.

    Args:
        metric_name: Name of the metric to retrieve
        hours: Number of hours of historical data (1-24)
    """
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        metrics = performance_monitor.get_metrics_for_timerange(
            metric_name, start_time, end_time
        )

        return [
            MetricDataPoint(
                timestamp=metric.timestamp.isoformat(),
                value=metric.value,
                tags=metric.tags,
                metadata=metric.metadata
            )
            for metric in metrics
        ]
    except Exception as e:
        logger.error(f"Failed to get metric data for {metric_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metric data")

@router.get("/performance/system")
async def get_system_metrics(
    current_user: User = Depends(get_current_user)
):
    """Get current system resource metrics."""
    try:
        summary = performance_monitor.get_performance_summary()
        return {
            "status": "success",
            "data": {
                "system": summary.get("system", {}),
                "uptime_seconds": summary.get("uptime_seconds", 0),
                "timestamp": summary.get("timestamp")
            }
        }
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system metrics")

@router.get("/performance/api")
async def get_api_metrics(
    current_user: User = Depends(get_current_user)
):
    """Get API performance metrics."""
    try:
        summary = performance_monitor.get_performance_summary()
        return {
            "status": "success",
            "data": {
                "api": summary.get("api", {}),
                "timestamp": summary.get("timestamp")
            }
        }
    except Exception as e:
        logger.error(f"Failed to get API metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve API metrics")

@router.get("/performance/database")
async def get_database_metrics(
    current_user: User = Depends(get_current_user)
):
    """Get database performance metrics."""
    try:
        summary = performance_monitor.get_performance_summary()
        db_metrics = performance_monitor.db_metrics

        return {
            "status": "success",
            "data": {
                "database": summary.get("database", {}),
                "slow_queries": db_metrics.slow_queries[-10:],  # Last 10 slow queries
                "timestamp": summary.get("timestamp")
            }
        }
    except Exception as e:
        logger.error(f"Failed to get database metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve database metrics")

@router.get("/performance/websocket")
async def get_websocket_metrics(
    current_user: User = Depends(get_current_user)
):
    """Get WebSocket performance metrics."""
    try:
        summary = performance_monitor.get_performance_summary()
        return {
            "status": "success",
            "data": {
                "websocket": summary.get("websocket", {}),
                "timestamp": summary.get("timestamp")
            }
        }
    except Exception as e:
        logger.error(f"Failed to get WebSocket metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve WebSocket metrics")

@router.get("/performance/thresholds")
async def get_performance_thresholds(
    admin_user: User = Depends(require_admin)
):
    """Get current performance thresholds (admin only)."""
    try:
        return {
            "status": "success",
            "data": performance_monitor.thresholds
        }
    except Exception as e:
        logger.error(f"Failed to get performance thresholds: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve thresholds")

@router.put("/performance/thresholds")
async def update_performance_thresholds(
    thresholds: Dict[str, float],
    admin_user: User = Depends(require_admin)
):
    """Update performance thresholds (admin only)."""
    try:
        # Validate threshold values
        valid_thresholds = {
            'api_response_time', 'db_query_time', 'cpu_usage',
            'memory_usage', 'error_rate', 'cache_hit_rate'
        }

        for key in thresholds.keys():
            if key not in valid_thresholds:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid threshold key: {key}"
                )

        # Update thresholds
        performance_monitor.thresholds.update(thresholds)

        logger.info(f"Performance thresholds updated by {admin_user.email}", thresholds=thresholds)

        return {
            "status": "success",
            "message": "Thresholds updated successfully",
            "data": performance_monitor.thresholds
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update performance thresholds: {e}")
        raise HTTPException(status_code=500, detail="Failed to update thresholds")

@router.get("/performance/report")
async def generate_performance_report(
    period: str = Query("24h", regex="^(1h|6h|24h|7d|30d)$"),
    current_user: User = Depends(get_current_user)
) -> PerformanceReport:
    """
    Generate comprehensive performance report.

    Args:
        period: Time period for the report (1h, 6h, 24h, 7d, 30d)
    """
    try:
        # Parse period to timedelta
        period_map = {
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }

        time_delta = period_map[period]
        end_time = datetime.now()
        start_time = end_time - time_delta

        # Get summary
        summary = performance_monitor.get_performance_summary()

        # Find top slow endpoints
        top_slow_endpoints = []
        for key, api_metric in performance_monitor.api_metrics.items():
            if api_metric.response_times:
                avg_time = sum(api_metric.response_times) / len(api_metric.response_times)
                top_slow_endpoints.append({
                    "endpoint": api_metric.endpoint,
                    "method": api_metric.method,
                    "avg_response_time": avg_time,
                    "total_requests": api_metric.total_requests,
                    "error_rate": (api_metric.error_count / api_metric.total_requests * 100) if api_metric.total_requests > 0 else 0
                })

        top_slow_endpoints.sort(key=lambda x: x["avg_response_time"], reverse=True)
        top_slow_endpoints = top_slow_endpoints[:10]

        # Get top slow queries
        top_slow_queries = performance_monitor.db_metrics.slow_queries[-10:]

        # Generate performance trends
        performance_trends = {
            "api_response_time": "stable",  # This would be calculated from historical data
            "database_performance": "improving",
            "system_resources": "stable",
            "websocket_connections": "growing"
        }

        # Generate recommendations
        recommendations = []

        # API recommendations
        if summary.get("api", {}):
            api_stats = summary["api"]
            slow_endpoints = [ep for ep in top_slow_endpoints if ep["avg_response_time"] > performance_monitor.thresholds["api_response_time"]]
            if slow_endpoints:
                recommendations.append(f"Optimize {len(slow_endpoints)} slow API endpoints")

        # Database recommendations
        if summary.get("database", {}):
            db_stats = summary["database"]
            if db_stats.get("cache_hit_rate", 0) < performance_monitor.thresholds["cache_hit_rate"]:
                recommendations.append("Improve cache hit rate by optimizing cache strategies")

            if len(performance_monitor.db_metrics.slow_queries) > 10:
                recommendations.append("Optimize slow database queries")

        # System recommendations
        if summary.get("system", {}):
            system_stats = summary["system"]
            if system_stats.get("cpu_percent", 0) > 70:
                recommendations.append("Consider scaling up CPU resources")

            if system_stats.get("memory_percent", 0) > 80:
                recommendations.append("Consider scaling up memory resources")

        if not recommendations:
            recommendations.append("System performance is within acceptable ranges")

        report = PerformanceReport(
            period=period,
            generated_at=datetime.now().isoformat(),
            summary=summary,
            top_slow_endpoints=top_slow_endpoints,
            top_slow_queries=top_slow_queries,
            performance_trends=performance_trends,
            recommendations=recommendations
        )

        logger.info(f"Performance report generated for {period}", user_id=current_user.id)

        return report

    except Exception as e:
        logger.error(f"Failed to generate performance report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate performance report")

@router.post("/performance/clear-metrics")
async def clear_performance_metrics(
    hours: Optional[int] = Query(None, ge=1, le=168),  # Max 1 week
    admin_user: User = Depends(require_admin)
):
    """Clear performance metrics (admin only)."""
    try:
        if hours:
            older_than = timedelta(hours=hours)
            performance_monitor.clear_metrics(older_than=older_than)
            message = f"Cleared metrics older than {hours} hours"
        else:
            performance_monitor.clear_metrics()
            message = "Cleared all performance metrics"

        logger.info(f"Performance metrics cleared by {admin_user.email}", hours=hours)

        return {
            "status": "success",
            "message": message
        }
    except Exception as e:
        logger.error(f"Failed to clear performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear metrics")

@router.get("/performance/health")
async def performance_health_check():
    """Performance monitoring system health check."""
    try:
        summary = performance_monitor.get_performance_summary()

        # Determine overall health status
        health_status = "healthy"
        issues = []

        # Check system metrics
        system = summary.get("system", {})
        if system.get("cpu_percent", 0) > performance_monitor.thresholds["cpu_usage"]:
            health_status = "degraded"
            issues.append("High CPU usage")

        if system.get("memory_percent", 0) > performance_monitor.thresholds["memory_usage"]:
            health_status = "degraded"
            issues.append("High memory usage")

        # Check API performance
        api = summary.get("api", {})
        for endpoint, stats in api.items():
            if stats.get("avg_response_time", 0) > performance_monitor.thresholds["api_response_time"]:
                health_status = "degraded"
                issues.append(f"Slow API endpoint: {endpoint}")
                break

        # Check database performance
        database = summary.get("database", {})
        if database.get("cache_hit_rate", 100) < performance_monitor.thresholds["cache_hit_rate"]:
            health_status = "degraded"
            issues.append("Low cache hit rate")

        return {
            "status": health_status,
            "timestamp": summary.get("timestamp"),
            "uptime_seconds": summary.get("uptime_seconds"),
            "issues": issues,
            "metrics_collected": len(performance_monitor.metrics),
            "monitoring_active": performance_monitor._monitoring_task is not None
        }

    except Exception as e:
        logger.error(f"Performance health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "monitoring_active": False
        }