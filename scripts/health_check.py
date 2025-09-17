#!/usr/bin/env python3
"""
System Health Checker for AgentOS Backend
Comprehensive validation of all system components
"""

import asyncio
import sys
import time
import json
import asyncpg
import aioredis
import httpx
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.config import settings
from app.core.multi_llm_router import llm_router
from app.core.embeddings import embedding_manager


class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Component health information"""
    name: str
    status: HealthStatus
    response_time: float
    details: Dict[str, Any]
    errors: List[str]
    timestamp: float


@dataclass
class SystemHealth:
    """Overall system health"""
    status: HealthStatus
    components: Dict[str, ComponentHealth]
    summary: Dict[str, Any]
    timestamp: float


class HealthChecker:
    """Comprehensive system health checker"""

    def __init__(self, timeout: int = 30, detailed: bool = True):
        self.timeout = timeout
        self.detailed = detailed
        self.logger = structlog.get_logger()

    async def check_all_components(self) -> SystemHealth:
        """Check all system components and return overall health"""

        print("🔍 Starting comprehensive system health check...")
        start_time = time.time()

        # Run all health checks concurrently
        tasks = {
            "database": self._check_database(),
            "redis": self._check_redis(),
            "qdrant": self._check_qdrant(),
            "llm_providers": self._check_llm_providers(),
            "api_endpoints": self._check_api_endpoints(),
            "file_system": self._check_file_system(),
            "security": self._check_security_config(),
            "performance": self._check_performance_metrics()
        }

        components = {}

        for name, task in tasks.items():
            try:
                print(f"  ➤ Checking {name}...")
                components[name] = await asyncio.wait_for(task, timeout=self.timeout)
                status_icon = "✅" if components[name].status == HealthStatus.HEALTHY else "⚠️" if components[name].status == HealthStatus.DEGRADED else "❌"
                print(f"    {status_icon} {name}: {components[name].status.value} ({components[name].response_time:.3f}s)")
            except asyncio.TimeoutError:
                components[name] = ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    response_time=self.timeout,
                    details={"error": "Health check timeout"},
                    errors=[f"Health check timeout after {self.timeout}s"],
                    timestamp=time.time()
                )
                print(f"    ❌ {name}: timeout")
            except Exception as e:
                components[name] = ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    response_time=0.0,
                    details={"error": str(e)},
                    errors=[str(e)],
                    timestamp=time.time()
                )
                print(f"    ❌ {name}: error - {str(e)}")

        # Calculate overall health status
        overall_status = self._calculate_overall_status(components)

        # Generate summary
        summary = self._generate_summary(components, time.time() - start_time)

        print(f"\n📊 Health check completed in {time.time() - start_time:.2f}s")
        print(f"🎯 Overall status: {overall_status.value.upper()}")

        return SystemHealth(
            status=overall_status,
            components=components,
            summary=summary,
            timestamp=time.time()
        )

    async def _check_database(self) -> ComponentHealth:
        """Check PostgreSQL database health"""
        start_time = time.time()
        errors = []
        details = {}

        try:
            # Parse database URL
            db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

            # Test connection
            conn = await asyncpg.connect(db_url)

            # Test basic query
            version = await conn.fetchval("SELECT version()")
            details["version"] = version

            # Test pgvector extension
            try:
                extensions = await conn.fetch(
                    "SELECT name, default_version, installed_version FROM pg_available_extensions WHERE name = 'vector'"
                )
                if extensions:
                    details["pgvector"] = {
                        "available": True,
                        "version": extensions[0]["installed_version"]
                    }
                else:
                    details["pgvector"] = {"available": False}
                    errors.append("pgvector extension not available")
            except Exception as e:
                errors.append(f"pgvector check failed: {str(e)}")

            # Test table existence
            tables = await conn.fetch("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
            """)
            details["tables"] = [row["tablename"] for row in tables]

            # Check connection pool
            details["connection_info"] = {
                "database": conn.get_server_pid(),
                "transaction_status": str(conn.get_transaction_status())
            }

            await conn.close()

            status = HealthStatus.HEALTHY if not errors else HealthStatus.DEGRADED

        except Exception as e:
            errors.append(str(e))
            status = HealthStatus.UNHEALTHY

        return ComponentHealth(
            name="database",
            status=status,
            response_time=time.time() - start_time,
            details=details,
            errors=errors,
            timestamp=time.time()
        )

    async def _check_redis(self) -> ComponentHealth:
        """Check Redis health"""
        start_time = time.time()
        errors = []
        details = {}

        try:
            # Connect to Redis
            redis = aioredis.from_url(settings.redis_url)

            # Test ping
            pong = await redis.ping()
            details["ping"] = pong

            # Test set/get
            test_key = "health_check_test"
            await redis.set(test_key, "test_value", ex=60)
            test_value = await redis.get(test_key)

            if test_value == b"test_value":
                details["read_write"] = "success"
            else:
                errors.append("Redis read/write test failed")

            # Get Redis info
            info = await redis.info()
            details["version"] = info.get("redis_version")
            details["used_memory"] = info.get("used_memory_human")
            details["connected_clients"] = info.get("connected_clients")

            # Cleanup test key
            await redis.delete(test_key)
            await redis.close()

            status = HealthStatus.HEALTHY if not errors else HealthStatus.DEGRADED

        except Exception as e:
            errors.append(str(e))
            status = HealthStatus.UNHEALTHY

        return ComponentHealth(
            name="redis",
            status=status,
            response_time=time.time() - start_time,
            details=details,
            errors=errors,
            timestamp=time.time()
        )

    async def _check_qdrant(self) -> ComponentHealth:
        """Check Qdrant vector database health"""
        start_time = time.time()
        errors = []
        details = {}

        try:
            # Test Qdrant connection
            qdrant_url = f"http://{settings.qdrant_host}:{settings.qdrant_port}"

            async with httpx.AsyncClient() as client:
                # Test health endpoint
                response = await client.get(f"{qdrant_url}/")

                if response.status_code == 200:
                    details["api_response"] = "healthy"
                else:
                    errors.append(f"Qdrant API returned status {response.status_code}")

                # Test collections endpoint
                try:
                    collections_response = await client.get(f"{qdrant_url}/collections")
                    if collections_response.status_code == 200:
                        collections_data = collections_response.json()
                        details["collections"] = collections_data.get("result", {}).get("collections", [])
                    else:
                        errors.append("Could not retrieve collections")
                except Exception as e:
                    errors.append(f"Collections check failed: {str(e)}")

            status = HealthStatus.HEALTHY if not errors else HealthStatus.DEGRADED

        except Exception as e:
            errors.append(str(e))
            status = HealthStatus.UNHEALTHY

        return ComponentHealth(
            name="qdrant",
            status=status,
            response_time=time.time() - start_time,
            details=details,
            errors=errors,
            timestamp=time.time()
        )

    async def _check_llm_providers(self) -> ComponentHealth:
        """Check LLM provider health"""
        start_time = time.time()
        errors = []
        details = {}

        try:
            # Test OpenAI
            if settings.openai_api_key:
                try:
                    from openai import AsyncOpenAI
                    client = AsyncOpenAI(api_key=settings.openai_api_key)

                    # Test with a simple completion
                    response = await client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": "Hello"}],
                        max_tokens=5
                    )

                    details["openai"] = {
                        "status": "healthy",
                        "model": response.model,
                        "response_length": len(response.choices[0].message.content)
                    }
                except Exception as e:
                    details["openai"] = {"status": "unhealthy", "error": str(e)}
                    errors.append(f"OpenAI: {str(e)}")
            else:
                details["openai"] = {"status": "not_configured"}

            # Test Anthropic
            if settings.anthropic_api_key:
                try:
                    import anthropic
                    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

                    response = await client.messages.create(
                        model="claude-3-haiku-20240307",
                        max_tokens=5,
                        messages=[{"role": "user", "content": "Hello"}]
                    )

                    details["anthropic"] = {
                        "status": "healthy",
                        "model": response.model,
                        "response_length": len(response.content[0].text)
                    }
                except Exception as e:
                    details["anthropic"] = {"status": "unhealthy", "error": str(e)}
                    errors.append(f"Anthropic: {str(e)}")
            else:
                details["anthropic"] = {"status": "not_configured"}

            # Test Together AI
            if settings.together_api_key:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            "https://api.together.xyz/v1/chat/completions",
                            headers={"Authorization": f"Bearer {settings.together_api_key}"},
                            json={
                                "model": "meta-llama/Llama-2-7b-chat-hf",
                                "messages": [{"role": "user", "content": "Hello"}],
                                "max_tokens": 5
                            }
                        )

                        if response.status_code == 200:
                            details["together"] = {"status": "healthy"}
                        else:
                            details["together"] = {"status": "unhealthy", "status_code": response.status_code}
                            errors.append(f"Together AI returned status {response.status_code}")

                except Exception as e:
                    details["together"] = {"status": "unhealthy", "error": str(e)}
                    errors.append(f"Together AI: {str(e)}")
            else:
                details["together"] = {"status": "not_configured"}

            # Overall LLM status
            healthy_providers = sum(1 for provider in details.values()
                                  if isinstance(provider, dict) and provider.get("status") == "healthy")

            if healthy_providers == 0:
                status = HealthStatus.UNHEALTHY
            elif errors:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY

        except Exception as e:
            errors.append(str(e))
            status = HealthStatus.UNHEALTHY

        return ComponentHealth(
            name="llm_providers",
            status=status,
            response_time=time.time() - start_time,
            details=details,
            errors=errors,
            timestamp=time.time()
        )

    async def _check_api_endpoints(self) -> ComponentHealth:
        """Check API endpoints health"""
        start_time = time.time()
        errors = []
        details = {}

        try:
            base_url = f"http://{settings.host}:{settings.port}"

            async with httpx.AsyncClient() as client:
                # Test health endpoint
                response = await client.get(f"{base_url}/health")

                if response.status_code == 200:
                    details["health_endpoint"] = "healthy"
                    health_data = response.json()
                    details["health_response"] = health_data
                else:
                    errors.append(f"Health endpoint returned {response.status_code}")

                # Test API docs (if in debug mode)
                if settings.debug:
                    docs_response = await client.get(f"{base_url}{settings.api_v1_prefix}/docs")
                    if docs_response.status_code == 200:
                        details["docs_endpoint"] = "healthy"
                    else:
                        errors.append(f"Docs endpoint returned {docs_response.status_code}")

                # Test OpenAPI spec
                openapi_response = await client.get(f"{base_url}{settings.api_v1_prefix}/openapi.json")
                if openapi_response.status_code == 200:
                    details["openapi"] = "healthy"
                    openapi_data = openapi_response.json()
                    details["api_version"] = openapi_data.get("info", {}).get("version")
                else:
                    errors.append(f"OpenAPI endpoint returned {openapi_response.status_code}")

            status = HealthStatus.HEALTHY if not errors else HealthStatus.DEGRADED

        except Exception as e:
            errors.append(str(e))
            status = HealthStatus.UNHEALTHY

        return ComponentHealth(
            name="api_endpoints",
            status=status,
            response_time=time.time() - start_time,
            details=details,
            errors=errors,
            timestamp=time.time()
        )

    async def _check_file_system(self) -> ComponentHealth:
        """Check file system health"""
        start_time = time.time()
        errors = []
        details = {}

        try:
            import shutil

            # Check disk space
            total, used, free = shutil.disk_usage("/")
            details["disk_space"] = {
                "total": f"{total // (1024**3)}GB",
                "used": f"{used // (1024**3)}GB",
                "free": f"{free // (1024**3)}GB",
                "usage_percent": round((used / total) * 100, 2)
            }

            # Warn if disk usage is high
            usage_percent = (used / total) * 100
            if usage_percent > 90:
                errors.append(f"High disk usage: {usage_percent:.1f}%")
            elif usage_percent > 80:
                details["warning"] = f"Disk usage is {usage_percent:.1f}%"

            # Check write permissions
            import tempfile
            try:
                with tempfile.NamedTemporaryFile(delete=True) as f:
                    f.write(b"test")
                    details["write_permissions"] = "healthy"
            except Exception as e:
                errors.append(f"Write permission test failed: {str(e)}")

            # Check project directories
            project_dirs = ["app", "tests", "migrations"]
            for dir_name in project_dirs:
                dir_path = Path(dir_name)
                if dir_path.exists():
                    details[f"{dir_name}_directory"] = "exists"
                else:
                    errors.append(f"Missing directory: {dir_name}")

            status = HealthStatus.HEALTHY if not errors else HealthStatus.DEGRADED

        except Exception as e:
            errors.append(str(e))
            status = HealthStatus.UNHEALTHY

        return ComponentHealth(
            name="file_system",
            status=status,
            response_time=time.time() - start_time,
            details=details,
            errors=errors,
            timestamp=time.time()
        )

    async def _check_security_config(self) -> ComponentHealth:
        """Check security configuration"""
        start_time = time.time()
        errors = []
        details = {}

        try:
            # Check required environment variables
            required_vars = [
                "SECRET_KEY", "CLERK_SECRET_KEY", "DATABASE_URL", "REDIS_URL"
            ]

            missing_vars = []
            for var in required_vars:
                if not hasattr(settings, var.lower()) or not getattr(settings, var.lower()):
                    missing_vars.append(var)

            if missing_vars:
                errors.extend([f"Missing environment variable: {var}" for var in missing_vars])

            details["required_env_vars"] = {
                "total": len(required_vars),
                "configured": len(required_vars) - len(missing_vars),
                "missing": missing_vars
            }

            # Check secret key strength
            if hasattr(settings, 'secret_key') and settings.secret_key:
                if len(settings.secret_key) < 32:
                    errors.append("SECRET_KEY is too short (should be at least 32 characters)")
                elif settings.secret_key in ["your-super-secret-key", "changeme"]:
                    errors.append("SECRET_KEY appears to be a default value")
                else:
                    details["secret_key"] = "properly_configured"

            # Check CORS configuration
            if hasattr(settings, 'allowed_origins'):
                if "*" in settings.allowed_origins and not settings.debug:
                    errors.append("CORS allows all origins in production mode")
                details["cors_origins"] = len(settings.allowed_origins)

            # Check debug mode in production
            if settings.debug:
                details["debug_mode"] = "enabled"
                if not settings.host in ["localhost", "127.0.0.1"]:
                    errors.append("Debug mode is enabled in production")
            else:
                details["debug_mode"] = "disabled"

            status = HealthStatus.HEALTHY if not errors else HealthStatus.DEGRADED

        except Exception as e:
            errors.append(str(e))
            status = HealthStatus.UNHEALTHY

        return ComponentHealth(
            name="security",
            status=status,
            response_time=time.time() - start_time,
            details=details,
            errors=errors,
            timestamp=time.time()
        )

    async def _check_performance_metrics(self) -> ComponentHealth:
        """Check performance metrics"""
        start_time = time.time()
        errors = []
        details = {}

        try:
            import psutil

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            details["cpu_usage"] = f"{cpu_percent}%"

            if cpu_percent > 90:
                errors.append(f"High CPU usage: {cpu_percent}%")
            elif cpu_percent > 80:
                details["cpu_warning"] = f"Elevated CPU usage: {cpu_percent}%"

            # Memory usage
            memory = psutil.virtual_memory()
            details["memory"] = {
                "total": f"{memory.total // (1024**3)}GB",
                "available": f"{memory.available // (1024**3)}GB",
                "percent": f"{memory.percent}%"
            }

            if memory.percent > 90:
                errors.append(f"High memory usage: {memory.percent}%")
            elif memory.percent > 80:
                details["memory_warning"] = f"Elevated memory usage: {memory.percent}%"

            # Load average (Unix-like systems)
            try:
                load = psutil.getloadavg()
                details["load_average"] = {
                    "1min": round(load[0], 2),
                    "5min": round(load[1], 2),
                    "15min": round(load[2], 2)
                }
            except AttributeError:
                # Windows doesn't have load average
                details["load_average"] = "not_available_on_windows"

            status = HealthStatus.HEALTHY if not errors else HealthStatus.DEGRADED

        except ImportError:
            details["psutil"] = "not_installed"
            status = HealthStatus.DEGRADED
        except Exception as e:
            errors.append(str(e))
            status = HealthStatus.UNHEALTHY

        return ComponentHealth(
            name="performance",
            status=status,
            response_time=time.time() - start_time,
            details=details,
            errors=errors,
            timestamp=time.time()
        )

    def _calculate_overall_status(self, components: Dict[str, ComponentHealth]) -> HealthStatus:
        """Calculate overall system health status"""

        critical_components = ["database", "redis", "api_endpoints"]
        important_components = ["qdrant", "llm_providers"]

        # Check critical components
        for comp_name in critical_components:
            if comp_name in components:
                if components[comp_name].status == HealthStatus.UNHEALTHY:
                    return HealthStatus.UNHEALTHY

        # Check for any unhealthy components
        unhealthy_count = sum(1 for comp in components.values()
                            if comp.status == HealthStatus.UNHEALTHY)

        degraded_count = sum(1 for comp in components.values()
                           if comp.status == HealthStatus.DEGRADED)

        if unhealthy_count > 0:
            return HealthStatus.DEGRADED
        elif degraded_count > 2:
            return HealthStatus.DEGRADED
        elif degraded_count > 0:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def _generate_summary(self, components: Dict[str, ComponentHealth], total_time: float) -> Dict[str, Any]:
        """Generate health check summary"""

        status_counts = {}
        for status in HealthStatus:
            status_counts[status.value] = sum(1 for comp in components.values()
                                            if comp.status == status)

        total_errors = sum(len(comp.errors) for comp in components.values())
        avg_response_time = sum(comp.response_time for comp in components.values()) / len(components)

        return {
            "total_components": len(components),
            "status_distribution": status_counts,
            "total_errors": total_errors,
            "average_response_time": round(avg_response_time, 3),
            "total_check_time": round(total_time, 3),
            "timestamp": time.time()
        }

    def print_detailed_report(self, system_health: SystemHealth):
        """Print detailed health report"""

        print(f"\n{'='*80}")
        print(f"🏥 AGENTOS SYSTEM HEALTH REPORT")
        print(f"{'='*80}")
        print(f"Overall Status: {system_health.status.value.upper()}")
        print(f"Check Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(system_health.timestamp))}")
        print(f"Total Components: {system_health.summary['total_components']}")
        print(f"Total Errors: {system_health.summary['total_errors']}")

        print(f"\n📊 STATUS DISTRIBUTION:")
        for status, count in system_health.summary['status_distribution'].items():
            icon = "✅" if status == "healthy" else "⚠️" if status == "degraded" else "❌"
            print(f"  {icon} {status.title()}: {count}")

        print(f"\n🔍 COMPONENT DETAILS:")
        for name, component in system_health.components.items():
            status_icon = "✅" if component.status == HealthStatus.HEALTHY else "⚠️" if component.status == HealthStatus.DEGRADED else "❌"
            print(f"\n{status_icon} {name.upper().replace('_', ' ')}")
            print(f"  Status: {component.status.value}")
            print(f"  Response Time: {component.response_time:.3f}s")

            if component.errors:
                print(f"  ❌ Errors:")
                for error in component.errors:
                    print(f"    • {error}")

            if self.detailed and component.details:
                print(f"  📝 Details:")
                for key, value in component.details.items():
                    if isinstance(value, dict):
                        print(f"    {key}:")
                        for sub_key, sub_value in value.items():
                            print(f"      {sub_key}: {sub_value}")
                    else:
                        print(f"    {key}: {value}")

        print(f"\n{'='*80}")

    def save_report(self, system_health: SystemHealth, file_path: str = "health_report.json"):
        """Save health report to file"""

        # Convert to serializable format
        report_data = {
            "status": system_health.status.value,
            "timestamp": system_health.timestamp,
            "summary": system_health.summary,
            "components": {}
        }

        for name, component in system_health.components.items():
            report_data["components"][name] = {
                "status": component.status.value,
                "response_time": component.response_time,
                "details": component.details,
                "errors": component.errors,
                "timestamp": component.timestamp
            }

        with open(file_path, 'w') as f:
            json.dump(report_data, f, indent=2)

        print(f"📄 Health report saved to: {file_path}")


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="AgentOS System Health Checker")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout for health checks")
    parser.add_argument("--brief", action="store_true", help="Brief output (less detail)")
    parser.add_argument("--save", type=str, help="Save report to file")
    parser.add_argument("--exit-code", action="store_true", help="Exit with non-zero code if unhealthy")

    args = parser.parse_args()

    # Create health checker
    checker = HealthChecker(timeout=args.timeout, detailed=not args.brief)

    # Run health check
    try:
        health = await checker.check_all_components()

        # Print report
        checker.print_detailed_report(health)

        # Save if requested
        if args.save:
            checker.save_report(health, args.save)

        # Exit with appropriate code
        if args.exit_code:
            if health.status == HealthStatus.UNHEALTHY:
                sys.exit(2)
            elif health.status == HealthStatus.DEGRADED:
                sys.exit(1)
            else:
                sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n❌ Health check interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n💥 Health check failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())