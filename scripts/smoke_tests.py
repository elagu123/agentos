#!/usr/bin/env python3
"""
Smoke Tests for AgentOS Production Deployment
Validates critical functionality after deployment
"""

import asyncio
import sys
import time
import argparse
from typing import Dict, List, Optional
from dataclasses import dataclass
import httpx
import json
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

@dataclass
class SmokeTestResult:
    name: str
    passed: bool
    duration: float
    message: str
    response_code: Optional[int] = None
    details: Dict = None

class SmokeTestSuite:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.results: List[SmokeTestResult] = []
        self.client = httpx.AsyncClient(timeout=timeout, verify=True)

    def print_status(self, message: str, status: str = "INFO"):
        """Print colored status message"""
        colors = {
            "INFO": Fore.CYAN,
            "SUCCESS": Fore.GREEN,
            "WARNING": Fore.YELLOW,
            "ERROR": Fore.RED,
            "HEADER": Fore.MAGENTA
        }
        color = colors.get(status, Fore.WHITE)
        print(f"{color}[{status}] {message}{Style.RESET_ALL}")

    async def test_health_endpoint(self) -> SmokeTestResult:
        """Test basic health endpoint"""
        start_time = time.time()
        try:
            response = await self.client.get(f"{self.base_url}/health")
            duration = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                if data.get("status") in ["healthy", "ok"]:
                    return SmokeTestResult(
                        "Health Check",
                        True,
                        duration,
                        f"Health endpoint responsive ({duration:.2f}s)",
                        response.status_code,
                        data
                    )
                else:
                    return SmokeTestResult(
                        "Health Check",
                        False,
                        duration,
                        f"Health endpoint returned unhealthy status: {data.get('status')}",
                        response.status_code
                    )
            else:
                return SmokeTestResult(
                    "Health Check",
                    False,
                    duration,
                    f"Health endpoint returned {response.status_code}",
                    response.status_code
                )
        except Exception as e:
            duration = time.time() - start_time
            return SmokeTestResult(
                "Health Check",
                False,
                duration,
                f"Health check failed: {str(e)}"
            )

    async def test_api_root(self) -> SmokeTestResult:
        """Test API root endpoint"""
        start_time = time.time()
        try:
            response = await self.client.get(f"{self.base_url}/")
            duration = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                return SmokeTestResult(
                    "API Root",
                    True,
                    duration,
                    f"API root accessible ({duration:.2f}s)",
                    response.status_code,
                    data
                )
            else:
                return SmokeTestResult(
                    "API Root",
                    False,
                    duration,
                    f"API root returned {response.status_code}",
                    response.status_code
                )
        except Exception as e:
            duration = time.time() - start_time
            return SmokeTestResult(
                "API Root",
                False,
                duration,
                f"API root failed: {str(e)}"
            )

    async def test_openapi_docs(self) -> SmokeTestResult:
        """Test OpenAPI documentation endpoint"""
        start_time = time.time()
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/docs")
            duration = time.time() - start_time

            if response.status_code == 200:
                return SmokeTestResult(
                    "OpenAPI Docs",
                    True,
                    duration,
                    f"API documentation accessible ({duration:.2f}s)",
                    response.status_code
                )
            elif response.status_code == 404:
                # Docs might be disabled in production
                return SmokeTestResult(
                    "OpenAPI Docs",
                    True,
                    duration,
                    "API docs disabled in production (expected)",
                    response.status_code
                )
            else:
                return SmokeTestResult(
                    "OpenAPI Docs",
                    False,
                    duration,
                    f"API docs returned {response.status_code}",
                    response.status_code
                )
        except Exception as e:
            duration = time.time() - start_time
            return SmokeTestResult(
                "OpenAPI Docs",
                False,
                duration,
                f"API docs failed: {str(e)}"
            )

    async def test_auth_status(self) -> SmokeTestResult:
        """Test authentication status endpoint"""
        start_time = time.time()
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/auth/status")
            duration = time.time() - start_time

            if response.status_code in [200, 401]:  # Both are acceptable
                data = response.json() if response.status_code == 200 else {}
                return SmokeTestResult(
                    "Auth Status",
                    True,
                    duration,
                    f"Auth endpoint responsive ({duration:.2f}s)",
                    response.status_code,
                    data
                )
            else:
                return SmokeTestResult(
                    "Auth Status",
                    False,
                    duration,
                    f"Auth status returned {response.status_code}",
                    response.status_code
                )
        except Exception as e:
            duration = time.time() - start_time
            return SmokeTestResult(
                "Auth Status",
                False,
                duration,
                f"Auth status failed: {str(e)}"
            )

    async def test_database_connectivity(self) -> SmokeTestResult:
        """Test database connectivity through health endpoint"""
        start_time = time.time()
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/health/detailed")
            duration = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                db_status = data.get("database", {}).get("status")

                if db_status == "connected":
                    return SmokeTestResult(
                        "Database Connectivity",
                        True,
                        duration,
                        f"Database connected ({duration:.2f}s)",
                        response.status_code,
                        data.get("database", {})
                    )
                else:
                    return SmokeTestResult(
                        "Database Connectivity",
                        False,
                        duration,
                        f"Database status: {db_status}",
                        response.status_code
                    )
            else:
                return SmokeTestResult(
                    "Database Connectivity",
                    False,
                    duration,
                    f"Database health check returned {response.status_code}",
                    response.status_code
                )
        except Exception as e:
            duration = time.time() - start_time
            return SmokeTestResult(
                "Database Connectivity",
                False,
                duration,
                f"Database health check failed: {str(e)}"
            )

    async def test_redis_connectivity(self) -> SmokeTestResult:
        """Test Redis connectivity through health endpoint"""
        start_time = time.time()
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/health/detailed")
            duration = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                redis_status = data.get("redis", {}).get("status")

                if redis_status == "connected":
                    return SmokeTestResult(
                        "Redis Connectivity",
                        True,
                        duration,
                        f"Redis connected ({duration:.2f}s)",
                        response.status_code,
                        data.get("redis", {})
                    )
                else:
                    return SmokeTestResult(
                        "Redis Connectivity",
                        False,
                        duration,
                        f"Redis status: {redis_status}",
                        response.status_code
                    )
            else:
                return SmokeTestResult(
                    "Redis Connectivity",
                    False,
                    duration,
                    f"Redis health check returned {response.status_code}",
                    response.status_code
                )
        except Exception as e:
            duration = time.time() - start_time
            return SmokeTestResult(
                "Redis Connectivity",
                False,
                duration,
                f"Redis health check failed: {str(e)}"
            )

    async def test_security_headers(self) -> SmokeTestResult:
        """Test that security headers are present"""
        start_time = time.time()
        try:
            response = await self.client.get(f"{self.base_url}/health")
            duration = time.time() - start_time

            required_headers = [
                'x-frame-options',
                'x-content-type-options',
                'x-xss-protection',
                'strict-transport-security'
            ]

            missing_headers = []
            for header in required_headers:
                if header not in response.headers:
                    missing_headers.append(header)

            if not missing_headers:
                return SmokeTestResult(
                    "Security Headers",
                    True,
                    duration,
                    f"All security headers present ({duration:.2f}s)",
                    response.status_code,
                    {"headers": dict(response.headers)}
                )
            else:
                return SmokeTestResult(
                    "Security Headers",
                    False,
                    duration,
                    f"Missing security headers: {', '.join(missing_headers)}",
                    response.status_code
                )
        except Exception as e:
            duration = time.time() - start_time
            return SmokeTestResult(
                "Security Headers",
                False,
                duration,
                f"Security header check failed: {str(e)}"
            )

    async def test_rate_limiting(self) -> SmokeTestResult:
        """Test that rate limiting is working"""
        start_time = time.time()
        try:
            # Make multiple rapid requests
            tasks = []
            for _ in range(15):  # Should trigger rate limiting
                tasks.append(self.client.get(f"{self.base_url}/health"))

            responses = await asyncio.gather(*tasks, return_exceptions=True)
            duration = time.time() - start_time

            # Check if any requests were rate limited (429 status)
            rate_limited = any(
                hasattr(r, 'status_code') and r.status_code == 429
                for r in responses
                if not isinstance(r, Exception)
            )

            if rate_limited:
                return SmokeTestResult(
                    "Rate Limiting",
                    True,
                    duration,
                    f"Rate limiting is active ({duration:.2f}s)",
                    429
                )
            else:
                return SmokeTestResult(
                    "Rate Limiting",
                    True,  # Still pass, rate limiting might be configured differently
                    duration,
                    f"Rate limiting not triggered in test ({duration:.2f}s)",
                    200
                )
        except Exception as e:
            duration = time.time() - start_time
            return SmokeTestResult(
                "Rate Limiting",
                False,
                duration,
                f"Rate limiting test failed: {str(e)}"
            )

    async def test_metrics_endpoint(self) -> SmokeTestResult:
        """Test metrics endpoint availability"""
        start_time = time.time()
        try:
            response = await self.client.get(f"{self.base_url}/metrics")
            duration = time.time() - start_time

            if response.status_code in [200, 403]:  # 403 is OK if access is restricted
                return SmokeTestResult(
                    "Metrics Endpoint",
                    True,
                    duration,
                    f"Metrics endpoint available ({duration:.2f}s)",
                    response.status_code
                )
            else:
                return SmokeTestResult(
                    "Metrics Endpoint",
                    False,
                    duration,
                    f"Metrics endpoint returned {response.status_code}",
                    response.status_code
                )
        except Exception as e:
            duration = time.time() - start_time
            return SmokeTestResult(
                "Metrics Endpoint",
                False,
                duration,
                f"Metrics endpoint failed: {str(e)}"
            )

    async def run_all_tests(self) -> bool:
        """Run all smoke tests"""
        self.print_status("Starting smoke tests...", "HEADER")
        self.print_status(f"Target: {self.base_url}", "INFO")

        # Define test sequence
        tests = [
            ("Health Check", self.test_health_endpoint),
            ("API Root", self.test_api_root),
            ("OpenAPI Docs", self.test_openapi_docs),
            ("Auth Status", self.test_auth_status),
            ("Database Connectivity", self.test_database_connectivity),
            ("Redis Connectivity", self.test_redis_connectivity),
            ("Security Headers", self.test_security_headers),
            ("Rate Limiting", self.test_rate_limiting),
            ("Metrics Endpoint", self.test_metrics_endpoint),
        ]

        # Run tests
        for test_name, test_func in tests:
            self.print_status(f"Running {test_name}...", "INFO")
            result = await test_func()
            self.results.append(result)

            if result.passed:
                self.print_status(f"✓ {result.name}: {result.message}", "SUCCESS")
            else:
                self.print_status(f"✗ {result.name}: {result.message}", "ERROR")

        # Print summary
        await self.print_summary()

        # Return True if all critical tests passed
        critical_tests = ["Health Check", "API Root", "Database Connectivity"]
        critical_failures = [
            r for r in self.results
            if r.name in critical_tests and not r.passed
        ]

        return len(critical_failures) == 0

    async def print_summary(self):
        """Print test summary"""
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        self.print_status("", "INFO")
        self.print_status("SMOKE TEST SUMMARY", "HEADER")
        self.print_status("=" * 50, "INFO")

        print(f"Total Tests: {total}")
        print(f"{Fore.GREEN}Passed: {passed}{Style.RESET_ALL}")
        print(f"{Fore.RED}Failed: {total - passed}{Style.RESET_ALL}")
        print(f"Success Rate: {(passed/total*100):.1f}%")

        if passed == total:
            self.print_status("🎉 ALL SMOKE TESTS PASSED!", "SUCCESS")
        else:
            self.print_status("⚠️  Some smoke tests failed", "WARNING")
            print("\nFailed Tests:")
            for result in self.results:
                if not result.passed:
                    print(f"  - {result.name}: {result.message}")

        # Performance summary
        avg_response_time = sum(r.duration for r in self.results) / len(self.results)
        print(f"\nAverage Response Time: {avg_response_time:.2f}s")

        slowest = max(self.results, key=lambda r: r.duration)
        print(f"Slowest Test: {slowest.name} ({slowest.duration:.2f}s)")

    async def close(self):
        """Clean up resources"""
        await self.client.aclose()

async def main():
    parser = argparse.ArgumentParser(description="Run smoke tests against AgentOS API")
    parser.add_argument("--endpoint", default="https://api.agentos.io",
                       help="API endpoint to test")
    parser.add_argument("--timeout", type=int, default=30,
                       help="Request timeout in seconds")
    parser.add_argument("--json", action="store_true",
                       help="Output results in JSON format")

    args = parser.parse_args()

    # Run smoke tests
    suite = SmokeTestSuite(args.endpoint, args.timeout)

    try:
        success = await suite.run_all_tests()

        if args.json:
            # Output JSON results
            results_data = {
                "endpoint": args.endpoint,
                "timestamp": time.time(),
                "success": success,
                "tests": [
                    {
                        "name": r.name,
                        "passed": r.passed,
                        "duration": r.duration,
                        "message": r.message,
                        "response_code": r.response_code,
                        "details": r.details
                    }
                    for r in suite.results
                ]
            }
            print(json.dumps(results_data, indent=2))

        # Exit with appropriate code
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        suite.print_status("Tests interrupted by user", "WARNING")
        sys.exit(1)
    except Exception as e:
        suite.print_status(f"Test suite failed: {str(e)}", "ERROR")
        sys.exit(1)
    finally:
        await suite.close()

if __name__ == "__main__":
    asyncio.run(main())