"""
Monitoring Dashboard API for AgentOS
Real-time performance metrics, system health and analytics endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
import asyncio
import json
import time
from datetime import datetime, timedelta
import logging

from app.database import get_db
from app.core.cache_manager import cache_manager
from app.core.embedding_optimizer import get_embedding_optimizer
from app.core.db_optimizer import get_db_optimizer
from app.core.frontend_optimizer import asset_optimizer, performance_middleware
from app.core.connection_optimizer import connection_pool_manager, job_manager
from app.config import settings

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])
logger = logging.getLogger(__name__)

@router.get("/health/overview")
async def health_overview():
    """Health check general de todos los componentes"""
    try:
        health_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",
            "version": "1.0.0",
            "components": {}
        }

        # Database health
        try:
            db_optimizer = get_db_optimizer()
            if db_optimizer:
                db_metrics = db_optimizer.get_performance_metrics()
                health_data["components"]["database"] = {
                    "status": "healthy",
                    "metrics": db_metrics
                }
            else:
                health_data["components"]["database"] = {"status": "not_initialized"}
        except Exception as e:
            health_data["components"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_data["status"] = "degraded"

        # Cache health
        try:
            cache_health = await cache_manager.health_check()
            health_data["components"]["cache"] = cache_health
            if cache_health["status"] != "healthy":
                health_data["status"] = "degraded"
        except Exception as e:
            health_data["components"]["cache"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_data["status"] = "degraded"

        # Connection pools health
        try:
            pool_stats = await connection_pool_manager.get_pool_stats()
            health_data["components"]["connection_pools"] = {
                "status": "healthy" if pool_stats else "no_pools",
                "pools": pool_stats
            }
        except Exception as e:
            health_data["components"]["connection_pools"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # Background jobs health
        try:
            job_stats = job_manager.get_stats()
            health_data["components"]["background_jobs"] = {
                "status": "healthy",
                "stats": job_stats
            }
        except Exception as e:
            health_data["components"]["background_jobs"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        # Frontend optimizer health
        try:
            frontend_metrics = asset_optimizer.get_performance_metrics()
            health_data["components"]["frontend"] = {
                "status": "healthy",
                "metrics": frontend_metrics
            }
        except Exception as e:
            health_data["components"]["frontend"] = {
                "status": "unhealthy",
                "error": str(e)
            }

        return health_data

    except Exception as e:
        logger.error(f"Error getting health overview: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@router.get("/metrics/performance")
async def performance_metrics():
    """Métricas de performance en tiempo real"""
    try:
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "performance": {}
        }

        # Database performance
        db_optimizer = get_db_optimizer()
        if db_optimizer:
            db_metrics = db_optimizer.get_performance_metrics()
            metrics["performance"]["database"] = {
                "query_stats": db_metrics.get("query_profiler_stats", {}),
                "connection_stats": {
                    "cache_hit_ratio": db_metrics.get("cache_hit_ratio", 0),
                    "active_connections": db_metrics.get("active_connections", 0)
                }
            }

        # Cache performance
        cache_stats = await cache_manager.get_stats()
        metrics["performance"]["cache"] = cache_stats

        # HTTP performance
        http_stats = performance_middleware.get_performance_stats()
        metrics["performance"]["http"] = http_stats

        # Frontend performance
        frontend_metrics = asset_optimizer.get_performance_metrics()
        metrics["performance"]["frontend"] = frontend_metrics

        # Background jobs performance
        job_stats = job_manager.get_stats()
        metrics["performance"]["background_jobs"] = job_stats

        return metrics

    except Exception as e:
        logger.error(f"Error getting performance metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/system")
async def system_metrics():
    """Métricas del sistema y recursos"""
    try:
        import psutil
        import os

        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Process metrics
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info()

        system_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "cpu_percent": cpu_percent,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "percent": memory.percent
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100
                }
            },
            "process": {
                "memory_rss": process_memory.rss,
                "memory_vms": process_memory.vms,
                "cpu_percent": process.cpu_percent(),
                "num_threads": process.num_threads(),
                "connections": len(process.connections()),
                "open_files": len(process.open_files())
            }
        }

        return system_data

    except ImportError:
        return {
            "error": "psutil not installed",
            "message": "Install psutil for system metrics: pip install psutil"
        }
    except Exception as e:
        logger.error(f"Error getting system metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/database")
async def database_metrics(
    include_slow_queries: bool = Query(False, description="Include slow queries analysis")
):
    """Métricas detalladas de base de datos"""
    try:
        db_optimizer = get_db_optimizer()
        if not db_optimizer:
            raise HTTPException(status_code=503, detail="Database optimizer not initialized")

        metrics = db_optimizer.get_performance_metrics()

        if include_slow_queries:
            # Agregar análisis de queries lentas
            slow_queries = db_optimizer.profiler.get_stats()
            metrics["slow_query_analysis"] = slow_queries

        # Sugerencias de índices
        index_suggestions = db_optimizer.suggest_indexes()
        metrics["index_suggestions"] = index_suggestions[:10]  # Top 10

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "database_metrics": metrics
        }

    except Exception as e:
        logger.error(f"Error getting database metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/cache")
async def cache_metrics():
    """Métricas detalladas del sistema de cache"""
    try:
        cache_stats = await cache_manager.get_stats()

        # Embedding optimizer stats si está disponible
        embedding_stats = {}
        try:
            embedding_optimizer = get_embedding_optimizer()
            if embedding_optimizer:
                embedding_stats = embedding_optimizer.get_stats()
        except Exception:
            pass

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cache": cache_stats,
            "embedding_cache": embedding_stats
        }

    except Exception as e:
        logger.error(f"Error getting cache metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/jobs")
async def background_jobs_metrics():
    """Métricas de trabajos en segundo plano"""
    try:
        job_stats = job_manager.get_stats()

        # Jobs recientes (últimos 50 completados)
        recent_jobs = []
        for job_id, job in list(job_manager.jobs.items())[-50:]:
            if job.status.value in ["completed", "failed"]:
                recent_jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "status": job.status.value,
                    "execution_time": job.execution_time,
                    "created_at": job.created_at.isoformat(),
                    "error": job.error if job.status.value == "failed" else None
                })

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "job_stats": job_stats,
            "recent_jobs": recent_jobs
        }

    except Exception as e:
        logger.error(f"Error getting job metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/dashboard")
async def analytics_dashboard(
    period: str = Query("24h", description="Time period: 1h, 6h, 24h, 7d, 30d")
):
    """Dashboard de analíticas con métricas agregadas"""
    try:
        # Calcular período
        period_mapping = {
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }

        if period not in period_mapping:
            period = "24h"

        time_range = period_mapping[period]
        start_time = datetime.utcnow() - time_range

        # Recopilar métricas
        dashboard_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "period": period,
            "start_time": start_time.isoformat(),
            "overview": {},
            "trends": {},
            "alerts": []
        }

        # Overview general
        db_optimizer = get_db_optimizer()
        if db_optimizer:
            db_metrics = db_optimizer.get_performance_metrics()
            dashboard_data["overview"]["database"] = {
                "total_queries": db_metrics.get("query_profiler_stats", {}).get("total_queries", 0),
                "slow_queries": db_metrics.get("query_profiler_stats", {}).get("slow_queries", 0),
                "avg_query_time": db_metrics.get("query_profiler_stats", {}).get("avg_query_time", 0),
                "cache_hit_ratio": db_metrics.get("cache_hit_ratio", 0)
            }

        # Cache overview
        cache_stats = await cache_manager.get_stats()
        dashboard_data["overview"]["cache"] = {
            "hit_rate": cache_stats.get("hit_rate", "0%"),
            "total_keys": cache_stats.get("cache_keys", 0),
            "memory_used": cache_stats.get("memory_used", "0B")
        }

        # HTTP overview
        http_stats = performance_middleware.get_performance_stats()
        dashboard_data["overview"]["http"] = {
            "total_requests": http_stats.get("total_requests", 0),
            "avg_response_time": http_stats.get("avg_response_time", 0),
            "slow_requests": http_stats.get("slow_requests", 0)
        }

        # Jobs overview
        job_stats = job_manager.get_stats()
        dashboard_data["overview"]["jobs"] = {
            "total_submitted": job_stats.get("jobs_submitted", 0),
            "completed": job_stats.get("jobs_completed", 0),
            "failed": job_stats.get("jobs_failed", 0),
            "avg_execution_time": job_stats.get("avg_execution_time", 0)
        }

        # Generar alertas basadas en thresholds
        alerts = []

        # Database alerts
        if db_metrics:
            slow_query_pct = (
                db_metrics.get("query_profiler_stats", {}).get("slow_query_percentage", 0)
            )
            if slow_query_pct > 10:
                alerts.append({
                    "type": "warning",
                    "component": "database",
                    "message": f"High slow query percentage: {slow_query_pct:.1f}%",
                    "threshold": "10%"
                })

            cache_hit_ratio = db_metrics.get("cache_hit_ratio", 0)
            if cache_hit_ratio < 80:
                alerts.append({
                    "type": "warning",
                    "component": "database",
                    "message": f"Low cache hit ratio: {cache_hit_ratio:.1f}%",
                    "threshold": "80%"
                })

        # HTTP alerts
        if http_stats.get("avg_response_time", 0) > 2.0:
            alerts.append({
                "type": "warning",
                "component": "http",
                "message": f"High average response time: {http_stats['avg_response_time']:.3f}s",
                "threshold": "2.0s"
            })

        # Jobs alerts
        failure_rate = 0
        total_jobs = job_stats.get("jobs_submitted", 0)
        if total_jobs > 0:
            failure_rate = (job_stats.get("jobs_failed", 0) / total_jobs) * 100

        if failure_rate > 5:
            alerts.append({
                "type": "error",
                "component": "jobs",
                "message": f"High job failure rate: {failure_rate:.1f}%",
                "threshold": "5%"
            })

        dashboard_data["alerts"] = alerts

        return dashboard_data

    except Exception as e:
        logger.error(f"Error getting analytics dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream/metrics")
async def stream_metrics():
    """Stream de métricas en tiempo real (Server-Sent Events)"""
    async def generate():
        try:
            while True:
                # Recopilar métricas básicas
                metrics = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "http": performance_middleware.get_performance_stats(),
                    "jobs": {
                        "active": job_manager.stats.get("workers_active", 0),
                        "pending": sum(job_manager.stats.get("queue_sizes", {}).values())
                    }
                }

                # Obtener métricas del sistema si está disponible
                try:
                    import psutil
                    metrics["system"] = {
                        "cpu": psutil.cpu_percent(),
                        "memory": psutil.virtual_memory().percent
                    }
                except ImportError:
                    pass

                yield f"data: {json.dumps(metrics)}\n\n"
                await asyncio.sleep(5)  # Update every 5 seconds

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in metrics stream: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )

@router.post("/optimize/database")
async def optimize_database(background_tasks: BackgroundTasks):
    """Trigger de optimización de base de datos"""
    try:
        db_optimizer = get_db_optimizer()
        if not db_optimizer:
            raise HTTPException(status_code=503, detail="Database optimizer not initialized")

        # Ejecutar VACUUM ANALYZE en background
        def run_vacuum():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(db_optimizer.vacuum_analyze_tables())
                logger.info(f"Database optimization completed: {result}")
            finally:
                loop.close()

        background_tasks.add_task(run_vacuum)

        return {
            "message": "Database optimization started in background",
            "status": "initiated",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error starting database optimization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/clear")
async def clear_cache(
    cache_type: str = Query("all", description="Cache type: all, redis, embedding, local")
):
    """Limpiar diferentes tipos de cache"""
    try:
        results = {}

        if cache_type in ["all", "redis"]:
            cleared_redis = await cache_manager.clear_all()
            results["redis"] = f"Cleared {cleared_redis} keys"

        if cache_type in ["all", "embedding"]:
            embedding_optimizer = get_embedding_optimizer()
            if embedding_optimizer:
                cleared_local = embedding_optimizer.clear_local_cache()
                cleared_redis_emb = await embedding_optimizer.clear_redis_cache()
                results["embedding"] = {
                    "local": f"Cleared {cleared_local} embeddings",
                    "redis": f"Cleared {cleared_redis_emb} embeddings"
                }

        return {
            "message": "Cache clearing completed",
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/cleanup")
async def cleanup_jobs(
    max_age_hours: int = Query(24, description="Maximum age for completed jobs in hours")
):
    """Limpiar jobs completados antiguos"""
    try:
        removed_count = job_manager.cleanup_completed_jobs(max_age_hours)

        return {
            "message": f"Cleaned up {removed_count} old jobs",
            "removed_count": removed_count,
            "max_age_hours": max_age_hours,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error cleaning up jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations")
async def get_optimization_recommendations():
    """Obtener recomendaciones de optimización del sistema"""
    try:
        recommendations = {
            "timestamp": datetime.utcnow().isoformat(),
            "categories": {
                "database": [],
                "cache": [],
                "frontend": [],
                "jobs": [],
                "system": []
            }
        }

        # Database recommendations
        db_optimizer = get_db_optimizer()
        if db_optimizer:
            db_metrics = db_optimizer.get_performance_metrics()
            index_suggestions = db_metrics.get("index_suggestions", [])

            for suggestion in index_suggestions[:5]:  # Top 5
                recommendations["categories"]["database"].append({
                    "type": "index_optimization",
                    "priority": suggestion.get("priority", "medium"),
                    "description": suggestion.get("recommendation", ""),
                    "details": suggestion
                })

        # Cache recommendations
        cache_stats = await cache_manager.get_stats()
        hit_rate_str = cache_stats.get("hit_rate", "0%")
        hit_rate = float(hit_rate_str.replace("%", ""))

        if hit_rate < 80:
            recommendations["categories"]["cache"].append({
                "type": "cache_optimization",
                "priority": "high",
                "description": f"Low cache hit rate ({hit_rate_str}). Consider increasing TTL or cache size.",
                "current_value": hit_rate_str,
                "target_value": ">80%"
            })

        # Frontend recommendations
        frontend_metrics = asset_optimizer.get_performance_metrics()
        frontend_recs = frontend_metrics.get("cache_hit_recommendations", [])

        for rec in frontend_recs:
            recommendations["categories"]["frontend"].append({
                "type": "frontend_optimization",
                "priority": "medium",
                "description": rec
            })

        # Jobs recommendations
        job_stats = job_manager.get_stats()
        failure_rate = 0
        total_jobs = job_stats.get("jobs_submitted", 0)
        if total_jobs > 0:
            failure_rate = (job_stats.get("jobs_failed", 0) / total_jobs) * 100

        if failure_rate > 5:
            recommendations["categories"]["jobs"].append({
                "type": "job_reliability",
                "priority": "high",
                "description": f"High job failure rate ({failure_rate:.1f}%). Review job error patterns.",
                "current_value": f"{failure_rate:.1f}%",
                "target_value": "<5%"
            })

        # System recommendations
        try:
            import psutil
            memory = psutil.virtual_memory()
            if memory.percent > 85:
                recommendations["categories"]["system"].append({
                    "type": "memory_optimization",
                    "priority": "high",
                    "description": f"High memory usage ({memory.percent:.1f}%). Consider scaling or optimization.",
                    "current_value": f"{memory.percent:.1f}%",
                    "target_value": "<85%"
                })
        except ImportError:
            pass

        return recommendations

    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))