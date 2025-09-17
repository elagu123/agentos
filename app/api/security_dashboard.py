"""
Security Dashboard API endpoints
Real-time security monitoring and metrics for AgentOS
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Dict, List, Any, Optional
import json
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["security-monitoring"])

# Global security metrics storage (in production, use Redis or database)
security_metrics = {
    "requests_total": 0,
    "requests_blocked": 0,
    "unique_ips": set(),
    "threat_types": defaultdict(int),
    "blocked_ips": defaultdict(int),
    "recent_events": deque(maxlen=1000),
    "hourly_stats": defaultdict(lambda: {"total": 0, "blocked": 0})
}

@router.get("/metrics")
async def get_security_metrics():
    """Get current security metrics"""
    try:
        # Convert sets to lists for JSON serialization
        metrics = {
            "total_requests": security_metrics["requests_total"],
            "blocked_requests": security_metrics["requests_blocked"],
            "block_rate": (security_metrics["requests_blocked"] / security_metrics["requests_total"] * 100)
                         if security_metrics["requests_total"] > 0 else 0,
            "unique_ips_count": len(security_metrics["unique_ips"]),
            "threat_types": dict(security_metrics["threat_types"]),
            "top_blocked_ips": dict(sorted(security_metrics["blocked_ips"].items(),
                                         key=lambda x: x[1], reverse=True)[:10]),
            "timestamp": datetime.now().isoformat()
        }

        return {
            "status": "success",
            "data": metrics
        }

    except Exception as e:
        logger.error(f"Error getting security metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve security metrics")

@router.get("/events/recent")
async def get_recent_security_events(
    limit: int = Query(50, ge=1, le=1000, description="Number of recent events to return")
):
    """Get recent security events"""
    try:
        recent_events = list(security_metrics["recent_events"])[-limit:]

        return {
            "status": "success",
            "data": {
                "events": recent_events,
                "total_count": len(recent_events)
            }
        }

    except Exception as e:
        logger.error(f"Error getting recent security events: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve security events")

@router.get("/threats/analysis")
async def get_threat_analysis():
    """Get detailed threat analysis"""
    try:
        threat_analysis = {
            "threat_distribution": dict(security_metrics["threat_types"]),
            "risk_level": "LOW",  # Calculate based on metrics
            "recommendations": [],
            "trends": {
                "hourly": dict(security_metrics["hourly_stats"])
            }
        }

        # Calculate risk level
        block_rate = (security_metrics["requests_blocked"] / security_metrics["requests_total"] * 100) \
                    if security_metrics["requests_total"] > 0 else 0

        if block_rate > 10:
            threat_analysis["risk_level"] = "HIGH"
            threat_analysis["recommendations"].append("High block rate detected - review security rules")
        elif block_rate > 5:
            threat_analysis["risk_level"] = "MEDIUM"
            threat_analysis["recommendations"].append("Moderate security activity - monitor closely")
        else:
            threat_analysis["risk_level"] = "LOW"

        # Check for suspicious patterns
        if len(security_metrics["blocked_ips"]) > 20:
            threat_analysis["recommendations"].append("Multiple IPs blocked - possible coordinated attack")

        if security_metrics["threat_types"].get("sql_injection_detected", 0) > 0:
            threat_analysis["recommendations"].append("SQL injection attempts detected - review database security")

        return {
            "status": "success",
            "data": threat_analysis
        }

    except Exception as e:
        logger.error(f"Error getting threat analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze threats")

@router.get("/ips/blocked")
async def get_blocked_ips():
    """Get list of currently blocked IPs"""
    try:
        # In a real implementation, this would query the security middleware's blocked IP list
        blocked_ips_data = []

        for ip, count in security_metrics["blocked_ips"].items():
            blocked_ips_data.append({
                "ip_address": ip,
                "block_count": count,
                "threat_types": ["multiple"],  # Would track actual threat types per IP
                "first_seen": datetime.now().isoformat(),  # Would track actual timestamps
                "status": "blocked"
            })

        return {
            "status": "success",
            "data": {
                "blocked_ips": sorted(blocked_ips_data, key=lambda x: x["block_count"], reverse=True),
                "total_count": len(blocked_ips_data)
            }
        }

    except Exception as e:
        logger.error(f"Error getting blocked IPs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve blocked IPs")

@router.post("/ips/{ip_address}/unblock")
async def unblock_ip(ip_address: str):
    """Unblock a specific IP address"""
    try:
        # In a real implementation, this would communicate with the security middleware
        # to remove the IP from the blocked list

        if ip_address in security_metrics["blocked_ips"]:
            del security_metrics["blocked_ips"][ip_address]

        return {
            "status": "success",
            "message": f"IP {ip_address} has been unblocked",
            "data": {
                "ip_address": ip_address,
                "unblocked_at": datetime.now().isoformat()
            }
        }

    except Exception as e:
        logger.error(f"Error unblocking IP {ip_address}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to unblock IP {ip_address}")

@router.get("/stream/events")
async def stream_security_events():
    """Stream real-time security events using Server-Sent Events"""
    async def generate_events():
        """Generate security event stream"""
        last_event_count = 0

        while True:
            try:
                # Check for new events
                current_event_count = len(security_metrics["recent_events"])

                if current_event_count > last_event_count:
                    # New events available
                    new_events = list(security_metrics["recent_events"])[last_event_count:]

                    for event in new_events:
                        event_data = {
                            "type": "security_event",
                            "data": event,
                            "timestamp": datetime.now().isoformat()
                        }

                        yield f"data: {json.dumps(event_data)}\n\n"

                    last_event_count = current_event_count

                # Send periodic heartbeat
                heartbeat = {
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat(),
                    "active_connections": 1  # Would track actual connections
                }

                yield f"data: {json.dumps(heartbeat)}\n\n"

                await asyncio.sleep(2)  # Check every 2 seconds

            except Exception as e:
                logger.error(f"Error in event stream: {e}")
                error_event = {
                    "type": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                yield f"data: {json.dumps(error_event)}\n\n"
                break

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@router.get("/config")
async def get_security_config():
    """Get current security configuration"""
    try:
        # In a real implementation, this would get the actual security middleware config
        config = {
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute": 100,
                "window_seconds": 60
            },
            "threat_detection": {
                "xss_protection": True,
                "sql_injection_detection": True,
                "path_traversal_detection": True
            },
            "ip_blocking": {
                "enabled": True,
                "auto_block_threshold": 5,
                "block_duration_minutes": 15
            },
            "request_limits": {
                "max_request_size": 10485760,  # 10MB
                "max_payload_depth": 10
            }
        }

        return {
            "status": "success",
            "data": config
        }

    except Exception as e:
        logger.error(f"Error getting security config: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve security configuration")

@router.post("/config/update")
async def update_security_config(config_update: Dict[str, Any]):
    """Update security configuration"""
    try:
        # In a real implementation, this would update the security middleware configuration
        # For now, just validate the input structure

        allowed_sections = ["rate_limiting", "threat_detection", "ip_blocking", "request_limits"]

        for section in config_update:
            if section not in allowed_sections:
                raise HTTPException(status_code=400, detail=f"Invalid configuration section: {section}")

        return {
            "status": "success",
            "message": "Security configuration updated successfully",
            "data": {
                "updated_sections": list(config_update.keys()),
                "updated_at": datetime.now().isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating security config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update security configuration")

# Utility function to record security events (called by security middleware)
def record_security_event(event_type: str, ip_address: str, endpoint: str, details: Dict[str, Any] = None):
    """Record a security event for monitoring"""
    try:
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "ip_address": ip_address,
            "endpoint": endpoint,
            "details": details or {},
            "blocked": True
        }

        # Update metrics
        security_metrics["requests_total"] += 1
        security_metrics["requests_blocked"] += 1
        security_metrics["unique_ips"].add(ip_address)
        security_metrics["threat_types"][event_type] += 1
        security_metrics["blocked_ips"][ip_address] += 1
        security_metrics["recent_events"].append(event)

        # Update hourly stats
        hour_key = datetime.now().strftime("%Y-%m-%d %H")
        security_metrics["hourly_stats"][hour_key]["total"] += 1
        security_metrics["hourly_stats"][hour_key]["blocked"] += 1

        logger.info(f"Security event recorded: {event_type} from {ip_address} on {endpoint}")

    except Exception as e:
        logger.error(f"Error recording security event: {e}")

# Utility function to record normal requests
def record_normal_request(ip_address: str, endpoint: str):
    """Record a normal (non-blocked) request"""
    try:
        security_metrics["requests_total"] += 1
        security_metrics["unique_ips"].add(ip_address)

        # Update hourly stats
        hour_key = datetime.now().strftime("%Y-%m-%d %H")
        security_metrics["hourly_stats"][hour_key]["total"] += 1

    except Exception as e:
        logger.error(f"Error recording normal request: {e}")