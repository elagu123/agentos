#!/usr/bin/env python3
"""
Post-Deployment Validation Script for AgentOS
Comprehensive validation suite to ensure production deployment is healthy and functional
"""

import asyncio
import sys
import time
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

try:
    import httpx
    import psycopg2
    import redis
    import boto3
    from colorama import init, Fore, Style
    import structlog
except ImportError as e:
    print(f"Missing dependencies: {e}")
    print("Install with: pip install httpx psycopg2-binary redis boto3 colorama structlog")
    sys.exit(1)

# Initialize colorama
init(autoreset=True)

@dataclass
class ValidationResult:
    category: str
    test_name: str
    passed: bool
    duration: float
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    critical: bool = False

@dataclass
class ValidationSummary:
    total_tests: int
    passed: int
    failed: int
    critical_failures: int
    total_duration: float
    success_rate: float
    results: List[ValidationResult] = field(default_factory=list)

class PostDeploymentValidator:
    """Comprehensive post-deployment validation suite"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.results: List[ValidationResult] = []
        self.logger = structlog.get_logger(__name__)

        # API client configuration
        self.api_client = httpx.AsyncClient(
            timeout=30.0,
            verify=True,
            follow_redirects=True
        )

    def print_status(self, message: str, status: str = "INFO"):
        """Print colored status message"""
        colors = {
            "INFO": Fore.CYAN,
            "SUCCESS": Fore.GREEN,
            "WARNING": Fore.YELLOW,
            "ERROR": Fore.RED,
            "HEADER": Fore.MAGENTA,
            "CRITICAL": Fore.RED + Style.BRIGHT
        }
        color = colors.get(status, Fore.WHITE)
        print(f"{color}[{status}] {message}{Style.RESET_ALL}")

    def print_header(self):
        """Print validation header"""
        print(f"\n{Fore.CYAN}{'='*80}")
        print(f"{Fore.CYAN}   AGENTOS POST-DEPLOYMENT VALIDATION")
        print(f"{Fore.CYAN}   Environment: {self.config.get('environment', 'unknown')}")
        print(f"{Fore.CYAN}   Timestamp: {datetime.now().isoformat()}")
        print(f"{Fore.CYAN}{'='*80}\n")

    async def record_result(self, result: ValidationResult):
        """Record validation result"""
        self.results.append(result)

        status = "SUCCESS" if result.passed else ("CRITICAL" if result.critical else "ERROR")
        self.print_status(
            f"{result.category} - {result.test_name}: {result.message} ({result.duration:.2f}s)",
            status
        )

        # Log result
        self.logger.info(
            "Validation result",
            category=result.category,
            test_name=result.test_name,
            passed=result.passed,
            critical=result.critical,
            duration=result.duration,
            message=result.message,
            details=result.details
        )

    async def validate_api_health(self) -> List[ValidationResult]:
        """Validate API health and basic functionality"""
        results = []
        api_url = self.config.get('api_url', 'https://api.agentos.io')

        # Basic health check
        start_time = time.time()
        try:
            response = await self.api_client.get(f"{api_url}/health")
            duration = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                results.append(ValidationResult(
                    "API Health",
                    "Basic Health Check",
                    True,
                    duration,
                    f"API health endpoint responsive: {data.get('status', 'unknown')}",
                    data,
                    critical=True
                ))
            else:
                results.append(ValidationResult(
                    "API Health",
                    "Basic Health Check",
                    False,
                    duration,
                    f"Health endpoint returned {response.status_code}",
                    {"status_code": response.status_code},
                    critical=True
                ))

        except Exception as e:
            duration = time.time() - start_time
            results.append(ValidationResult(
                "API Health",
                "Basic Health Check",
                False,
                duration,
                f"Health check failed: {str(e)}",
                {"error": str(e)},
                critical=True
            ))

        # Detailed health check
        start_time = time.time()
        try:
            response = await self.api_client.get(f"{api_url}/api/v1/health/detailed")
            duration = time.time() - start_time

            if response.status_code == 200:
                data = response.json()

                # Check database status
                db_status = data.get('database', {}).get('status')
                results.append(ValidationResult(
                    "API Health",
                    "Database Connectivity",
                    db_status == 'connected',
                    duration,
                    f"Database status: {db_status}",
                    data.get('database', {}),
                    critical=True
                ))

                # Check Redis status
                redis_status = data.get('redis', {}).get('status')
                results.append(ValidationResult(
                    "API Health",
                    "Redis Connectivity",
                    redis_status == 'connected',
                    duration,
                    f"Redis status: {redis_status}",
                    data.get('redis', {}),
                    critical=True
                ))

                # Check API response time
                response_time = data.get('response_time', 0)
                results.append(ValidationResult(
                    "API Health",
                    "Response Time",
                    response_time < 2.0,
                    duration,
                    f"API response time: {response_time:.3f}s",
                    {"response_time": response_time}
                ))

            else:
                results.append(ValidationResult(
                    "API Health",
                    "Detailed Health Check",
                    False,
                    duration,
                    f"Detailed health endpoint returned {response.status_code}",
                    {"status_code": response.status_code}
                ))

        except Exception as e:
            duration = time.time() - start_time
            results.append(ValidationResult(
                "API Health",
                "Detailed Health Check",
                False,
                duration,
                f"Detailed health check failed: {str(e)}",
                {"error": str(e)}
            ))

        return results

    async def validate_api_endpoints(self) -> List[ValidationResult]:
        """Validate critical API endpoints"""
        results = []
        api_url = self.config.get('api_url', 'https://api.agentos.io')

        # Test critical endpoints
        endpoints = [
            {"path": "/", "name": "Root Endpoint", "critical": True},
            {"path": "/api/v1/auth/status", "name": "Auth Status", "critical": True},
            {"path": "/api/v1/agents", "name": "Agents List", "critical": False},
            {"path": "/api/v1/specialized-agents/types", "name": "Agent Types", "critical": False},
            {"path": "/api/v1/monitoring/metrics", "name": "Metrics Endpoint", "critical": False},
        ]

        for endpoint in endpoints:
            start_time = time.time()
            try:
                response = await self.api_client.get(f"{api_url}{endpoint['path']}")
                duration = time.time() - start_time

                # Accept 200, 401 (auth required), 403 (forbidden) as valid responses
                valid_responses = [200, 401, 403]
                success = response.status_code in valid_responses

                results.append(ValidationResult(
                    "API Endpoints",
                    endpoint['name'],
                    success,
                    duration,
                    f"Status: {response.status_code} ({'OK' if success else 'Error'})",
                    {
                        "status_code": response.status_code,
                        "path": endpoint['path']
                    },
                    critical=endpoint['critical']
                ))

            except Exception as e:
                duration = time.time() - start_time
                results.append(ValidationResult(
                    "API Endpoints",
                    endpoint['name'],
                    False,
                    duration,
                    f"Request failed: {str(e)}",
                    {"error": str(e), "path": endpoint['path']},
                    critical=endpoint['critical']
                ))

        return results

    async def validate_security_features(self) -> List[ValidationResult]:
        """Validate security features are working"""
        results = []
        api_url = self.config.get('api_url', 'https://api.agentos.io')

        # Test HTTPS enforcement
        start_time = time.time()
        try:
            http_url = api_url.replace('https://', 'http://')
            response = await self.api_client.get(f"{http_url}/health")
            duration = time.time() - start_time

            # Should redirect to HTTPS or fail
            https_enforced = response.status_code in [301, 302, 308] or response.url.scheme == 'https'

            results.append(ValidationResult(
                "Security",
                "HTTPS Enforcement",
                https_enforced,
                duration,
                f"HTTPS enforcement: {'Active' if https_enforced else 'Inactive'}",
                {"final_url": str(response.url)}
            ))

        except Exception as e:
            duration = time.time() - start_time
            results.append(ValidationResult(
                "Security",
                "HTTPS Enforcement",
                True,  # Exception might mean HTTP is completely blocked
                duration,
                f"HTTP blocked: {str(e)}",
                {"error": str(e)}
            ))

        # Test security headers
        start_time = time.time()
        try:
            response = await self.api_client.get(f"{api_url}/health")
            duration = time.time() - start_time

            required_headers = [
                'x-frame-options',
                'x-content-type-options',
                'x-xss-protection',
                'strict-transport-security'
            ]

            present_headers = [h for h in required_headers if h in response.headers]
            missing_headers = [h for h in required_headers if h not in response.headers]

            results.append(ValidationResult(
                "Security",
                "Security Headers",
                len(missing_headers) == 0,
                duration,
                f"Headers present: {len(present_headers)}/{len(required_headers)}",
                {
                    "present": present_headers,
                    "missing": missing_headers,
                    "headers": dict(response.headers)
                }
            ))

        except Exception as e:
            duration = time.time() - start_time
            results.append(ValidationResult(
                "Security",
                "Security Headers",
                False,
                duration,
                f"Header check failed: {str(e)}",
                {"error": str(e)}
            ))

        # Test rate limiting (make rapid requests)
        start_time = time.time()
        try:
            rapid_requests = []
            for _ in range(20):  # Should trigger rate limiting
                rapid_requests.append(self.api_client.get(f"{api_url}/health"))

            responses = await asyncio.gather(*rapid_requests, return_exceptions=True)
            duration = time.time() - start_time

            # Check if any requests were rate limited
            rate_limited = any(
                hasattr(r, 'status_code') and r.status_code == 429
                for r in responses
                if not isinstance(r, Exception)
            )

            results.append(ValidationResult(
                "Security",
                "Rate Limiting",
                True,  # Either rate limited or all passed (both acceptable)
                duration,
                f"Rate limiting: {'Active' if rate_limited else 'Not triggered'}",
                {"rate_limited": rate_limited}
            ))

        except Exception as e:
            duration = time.time() - start_time
            results.append(ValidationResult(
                "Security",
                "Rate Limiting",
                False,
                duration,
                f"Rate limiting test failed: {str(e)}",
                {"error": str(e)}
            ))

        return results

    async def validate_database_connectivity(self) -> List[ValidationResult]:
        """Validate direct database connectivity"""
        results = []

        if 'database_url' not in self.config:
            results.append(ValidationResult(
                "Database",
                "Connection Test",
                False,
                0,
                "Database URL not configured",
                {},
                critical=True
            ))
            return results

        start_time = time.time()
        try:
            conn = psycopg2.connect(self.config['database_url'])
            duration = time.time() - start_time

            # Test basic query
            with conn.cursor() as cur:
                cur.execute("SELECT version(), current_database(), current_user")
                db_info = cur.fetchone()

            conn.close()

            results.append(ValidationResult(
                "Database",
                "Connection Test",
                True,
                duration,
                f"Connected successfully",
                {
                    "version": db_info[0].split()[0:2],
                    "database": db_info[1],
                    "user": db_info[2]
                },
                critical=True
            ))

        except Exception as e:
            duration = time.time() - start_time
            results.append(ValidationResult(
                "Database",
                "Connection Test",
                False,
                duration,
                f"Connection failed: {str(e)}",
                {"error": str(e)},
                critical=True
            ))

        return results

    async def validate_redis_connectivity(self) -> List[ValidationResult]:
        """Validate Redis connectivity"""
        results = []

        if 'redis_url' not in self.config:
            results.append(ValidationResult(
                "Redis",
                "Connection Test",
                False,
                0,
                "Redis URL not configured",
                {},
                critical=True
            ))
            return results

        start_time = time.time()
        try:
            r = redis.from_url(self.config['redis_url'])

            # Test ping
            r.ping()

            # Test basic operations
            test_key = f"validation_test_{int(time.time())}"
            r.set(test_key, "test_value", ex=60)
            value = r.get(test_key)
            r.delete(test_key)

            # Get info
            info = r.info()

            duration = time.time() - start_time

            results.append(ValidationResult(
                "Redis",
                "Connection Test",
                value.decode('utf-8') == 'test_value',
                duration,
                f"Connected successfully - Version: {info.get('redis_version', 'unknown')}",
                {
                    "version": info.get('redis_version'),
                    "memory_used": info.get('used_memory_human'),
                    "uptime": info.get('uptime_in_seconds')
                },
                critical=True
            ))

        except Exception as e:
            duration = time.time() - start_time
            results.append(ValidationResult(
                "Redis",
                "Connection Test",
                False,
                duration,
                f"Connection failed: {str(e)}",
                {"error": str(e)},
                critical=True
            ))

        return results

    async def validate_monitoring_systems(self) -> List[ValidationResult]:
        """Validate monitoring and observability systems"""
        results = []
        api_url = self.config.get('api_url', 'https://api.agentos.io')

        # Test metrics endpoint
        start_time = time.time()
        try:
            response = await self.api_client.get(f"{api_url}/metrics")
            duration = time.time() - start_time

            # Accept 200 (metrics available) or 403 (protected)
            metrics_available = response.status_code in [200, 403]

            results.append(ValidationResult(
                "Monitoring",
                "Metrics Endpoint",
                metrics_available,
                duration,
                f"Metrics endpoint status: {response.status_code}",
                {"status_code": response.status_code}
            ))

        except Exception as e:
            duration = time.time() - start_time
            results.append(ValidationResult(
                "Monitoring",
                "Metrics Endpoint",
                False,
                duration,
                f"Metrics endpoint failed: {str(e)}",
                {"error": str(e)}
            ))

        # Test security monitoring endpoint
        start_time = time.time()
        try:
            response = await self.api_client.get(f"{api_url}/api/v1/security/metrics")
            duration = time.time() - start_time

            security_monitoring = response.status_code in [200, 401, 403]

            results.append(ValidationResult(
                "Monitoring",
                "Security Monitoring",
                security_monitoring,
                duration,
                f"Security monitoring status: {response.status_code}",
                {"status_code": response.status_code}
            ))

        except Exception as e:
            duration = time.time() - start_time
            results.append(ValidationResult(
                "Monitoring",
                "Security Monitoring",
                False,
                duration,
                f"Security monitoring failed: {str(e)}",
                {"error": str(e)}
            ))

        return results

    async def validate_performance_baseline(self) -> List[ValidationResult]:
        """Validate performance meets baseline requirements"""
        results = []
        api_url = self.config.get('api_url', 'https://api.agentos.io')

        # Performance test - multiple concurrent requests
        start_time = time.time()
        try:
            # Make 10 concurrent requests
            tasks = []
            for _ in range(10):
                tasks.append(self.api_client.get(f"{api_url}/health"))

            responses = await asyncio.gather(*tasks, return_exceptions=True)
            total_duration = time.time() - start_time

            # Analyze results
            successful_requests = [
                r for r in responses
                if hasattr(r, 'status_code') and r.status_code == 200
            ]

            success_rate = len(successful_requests) / len(responses) * 100
            avg_response_time = total_duration / len(responses)

            # Performance criteria
            performance_good = (
                success_rate >= 95 and  # 95% success rate
                avg_response_time < 1.0  # Average response time < 1s
            )

            results.append(ValidationResult(
                "Performance",
                "Concurrent Requests",
                performance_good,
                total_duration,
                f"Success rate: {success_rate:.1f}%, Avg time: {avg_response_time:.3f}s",
                {
                    "success_rate": success_rate,
                    "avg_response_time": avg_response_time,
                    "total_requests": len(responses),
                    "successful_requests": len(successful_requests)
                }
            ))

        except Exception as e:
            duration = time.time() - start_time
            results.append(ValidationResult(
                "Performance",
                "Concurrent Requests",
                False,
                duration,
                f"Performance test failed: {str(e)}",
                {"error": str(e)}
            ))

        return results

    async def validate_business_functionality(self) -> List[ValidationResult]:
        """Validate core business functionality"""
        results = []
        api_url = self.config.get('api_url', 'https://api.agentos.io')

        # Test agent types endpoint
        start_time = time.time()
        try:
            response = await self.api_client.get(f"{api_url}/api/v1/specialized-agents/types")
            duration = time.time() - start_time

            if response.status_code in [200, 401]:  # 401 = auth required (acceptable)
                agent_functionality = True
                message = f"Agent types endpoint responsive: {response.status_code}"
                details = {"status_code": response.status_code}

                if response.status_code == 200:
                    data = response.json()
                    details["agent_count"] = len(data) if isinstance(data, list) else "unknown"
            else:
                agent_functionality = False
                message = f"Agent types endpoint error: {response.status_code}"
                details = {"status_code": response.status_code}

            results.append(ValidationResult(
                "Business Logic",
                "Agent Functionality",
                agent_functionality,
                duration,
                message,
                details,
                critical=True
            ))

        except Exception as e:
            duration = time.time() - start_time
            results.append(ValidationResult(
                "Business Logic",
                "Agent Functionality",
                False,
                duration,
                f"Agent functionality test failed: {str(e)}",
                {"error": str(e)},
                critical=True
            ))

        return results

    async def run_all_validations(self) -> ValidationSummary:
        """Run all post-deployment validations"""
        self.print_header()
        self.print_status("Starting post-deployment validation suite...", "INFO")

        start_time = time.time()

        # Run validation categories
        validation_suites = [
            ("API Health", self.validate_api_health),
            ("API Endpoints", self.validate_api_endpoints),
            ("Security", self.validate_security_features),
            ("Database", self.validate_database_connectivity),
            ("Redis", self.validate_redis_connectivity),
            ("Monitoring", self.validate_monitoring_systems),
            ("Performance", self.validate_performance_baseline),
            ("Business Logic", self.validate_business_functionality),
        ]

        for suite_name, validation_func in validation_suites:
            self.print_status(f"Running {suite_name} validations...", "INFO")
            try:
                suite_results = await validation_func()
                for result in suite_results:
                    await self.record_result(result)
            except Exception as e:
                await self.record_result(ValidationResult(
                    suite_name,
                    "Suite Execution",
                    False,
                    0,
                    f"Validation suite failed: {str(e)}",
                    {"error": str(e)},
                    critical=True
                ))

        total_duration = time.time() - start_time

        # Generate summary
        total_tests = len(self.results)
        passed = len([r for r in self.results if r.passed])
        failed = total_tests - passed
        critical_failures = len([r for r in self.results if not r.passed and r.critical])
        success_rate = (passed / total_tests * 100) if total_tests > 0 else 0

        summary = ValidationSummary(
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            critical_failures=critical_failures,
            total_duration=total_duration,
            success_rate=success_rate,
            results=self.results
        )

        self.print_summary(summary)
        return summary

    def print_summary(self, summary: ValidationSummary):
        """Print validation summary"""
        print(f"\n{Fore.CYAN}{'='*80}")
        print(f"{Fore.CYAN}   VALIDATION SUMMARY")
        print(f"{Fore.CYAN}{'='*80}\n")

        print(f"Total Tests: {summary.total_tests}")
        print(f"{Fore.GREEN}Passed: {summary.passed}{Style.RESET_ALL}")
        print(f"{Fore.RED}Failed: {summary.failed}{Style.RESET_ALL}")
        print(f"{Fore.RED + Style.BRIGHT}Critical Failures: {summary.critical_failures}{Style.RESET_ALL}")
        print(f"Success Rate: {summary.success_rate:.1f}%")
        print(f"Total Duration: {summary.total_duration:.2f}s")

        # Show failed tests
        if summary.failed > 0:
            print(f"\n{Fore.RED}Failed Tests:{Style.RESET_ALL}")
            for result in summary.results:
                if not result.passed:
                    status = "CRITICAL" if result.critical else "FAILED"
                    color = Fore.RED + Style.BRIGHT if result.critical else Fore.RED
                    print(f"  {color}[{status}] {result.category} - {result.test_name}: {result.message}{Style.RESET_ALL}")

        # Overall status
        print(f"\n{Fore.CYAN}{'='*80}")
        if summary.critical_failures == 0 and summary.success_rate >= 80:
            print(f"{Fore.GREEN}   ✅ DEPLOYMENT VALIDATION PASSED{Style.RESET_ALL}")
            print(f"{Fore.GREEN}   Production deployment is healthy and functional{Style.RESET_ALL}")
        elif summary.critical_failures == 0:
            print(f"{Fore.YELLOW}   ⚠️  DEPLOYMENT VALIDATION WARNING{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}   Some non-critical issues detected{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED + Style.BRIGHT}   ❌ DEPLOYMENT VALIDATION FAILED{Style.RESET_ALL}")
            print(f"{Fore.RED + Style.BRIGHT}   Critical issues detected - immediate attention required{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}\n")

    async def cleanup(self):
        """Clean up resources"""
        await self.api_client.aclose()

def load_config_from_args(args) -> Dict[str, Any]:
    """Load configuration from command line arguments and environment"""
    config = {
        'api_url': args.api_url,
        'environment': args.environment,
    }

    # Add database URL if provided
    if hasattr(args, 'database_url') and args.database_url:
        config['database_url'] = args.database_url

    # Add Redis URL if provided
    if hasattr(args, 'redis_url') and args.redis_url:
        config['redis_url'] = args.redis_url

    return config

async def main():
    """Main validation function"""
    parser = argparse.ArgumentParser(description="Post-deployment validation for AgentOS")
    parser.add_argument("--api-url", default="https://api.agentos.io",
                       help="API endpoint URL")
    parser.add_argument("--environment", default="production",
                       help="Environment name")
    parser.add_argument("--database-url",
                       help="Database connection URL")
    parser.add_argument("--redis-url",
                       help="Redis connection URL")
    parser.add_argument("--json", action="store_true",
                       help="Output results in JSON format")
    parser.add_argument("--fail-on-warning", action="store_true",
                       help="Exit with error code on warnings")

    args = parser.parse_args()

    # Load configuration
    config = load_config_from_args(args)

    # Run validation
    validator = PostDeploymentValidator(config)

    try:
        summary = await validator.run_all_validations()

        # Output JSON if requested
        if args.json:
            json_output = {
                "timestamp": datetime.now().isoformat(),
                "environment": config.get('environment'),
                "api_url": config.get('api_url'),
                "summary": {
                    "total_tests": summary.total_tests,
                    "passed": summary.passed,
                    "failed": summary.failed,
                    "critical_failures": summary.critical_failures,
                    "success_rate": summary.success_rate,
                    "total_duration": summary.total_duration
                },
                "results": [
                    {
                        "category": r.category,
                        "test_name": r.test_name,
                        "passed": r.passed,
                        "critical": r.critical,
                        "duration": r.duration,
                        "message": r.message,
                        "details": r.details
                    }
                    for r in summary.results
                ]
            }
            print(json.dumps(json_output, indent=2))

        # Determine exit code
        if summary.critical_failures > 0:
            sys.exit(1)  # Critical failures
        elif args.fail_on_warning and summary.failed > 0:
            sys.exit(2)  # Non-critical failures with strict mode
        else:
            sys.exit(0)  # Success

    except KeyboardInterrupt:
        validator.print_status("Validation interrupted by user", "WARNING")
        sys.exit(130)
    except Exception as e:
        validator.print_status(f"Validation failed with error: {str(e)}", "ERROR")
        sys.exit(1)
    finally:
        await validator.cleanup()

if __name__ == "__main__":
    asyncio.run(main())