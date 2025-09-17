#!/usr/bin/env python3
"""
Security Endpoint Testing Script
Tests all API endpoints with the new security middleware to ensure functionality
"""

import asyncio
import aiohttp
import json
import time
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from colorama import init, Fore, Style
import logging

# Initialize colorama for colored output
init(autoreset=True)

@dataclass
class TestResult:
    endpoint: str
    method: str
    status_code: int
    response_time: float
    success: bool
    error_message: Optional[str] = None
    security_headers: Dict[str, str] = None

class SecurityEndpointTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[TestResult] = []
        self.session: Optional[aiohttp.ClientSession] = None

        # Test endpoints to validate
        self.endpoints = [
            # Health endpoints
            {"method": "GET", "path": "/health", "description": "Legacy health check"},
            {"method": "GET", "path": "/api/v1/health", "description": "API health check"},
            {"method": "GET", "path": "/api/v1/health/detailed", "description": "Detailed health check"},

            # Auth endpoints (no auth required)
            {"method": "GET", "path": "/api/v1/auth/status", "description": "Auth status check"},

            # Public endpoints
            {"method": "GET", "path": "/", "description": "Root endpoint"},

            # Protected endpoints (will fail auth but should pass security)
            {"method": "GET", "path": "/api/v1/auth/me", "description": "Get current user"},
            {"method": "GET", "path": "/api/v1/onboarding/steps", "description": "Onboarding steps"},
            {"method": "GET", "path": "/api/v1/specialized-agents/types", "description": "Agent types"},

            # POST endpoints with test payloads
            {"method": "POST", "path": "/api/v1/feedback/submit", "description": "Submit feedback",
             "payload": {"type": "bug", "message": "Test feedback", "rating": 5}},

            # Monitoring endpoints
            {"method": "GET", "path": "/api/v1/monitoring/metrics", "description": "System metrics"},
            {"method": "GET", "path": "/api/v1/monitoring/health", "description": "System health"},
        ]

        # Security test payloads
        self.security_test_payloads = [
            # XSS attempts
            {"type": "xss", "payload": {"message": "<script>alert('xss')</script>"}},
            {"type": "xss", "payload": {"content": "javascript:alert('xss')"}},

            # SQL Injection attempts
            {"type": "sql", "payload": {"query": "'; DROP TABLE users; --"}},
            {"type": "sql", "payload": {"filter": "1' OR '1'='1"}},

            # Path traversal attempts
            {"type": "path", "payload": {"file": "../../../etc/passwd"}},
            {"type": "path", "payload": {"path": "..\\..\\windows\\system32\\config\\sam"}},
        ]

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=10)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

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

    async def test_endpoint(self, endpoint: Dict[str, Any]) -> TestResult:
        """Test a single endpoint"""
        method = endpoint["method"]
        path = endpoint["path"]
        url = f"{self.base_url}{path}"
        payload = endpoint.get("payload")

        start_time = time.time()

        try:
            if method == "GET":
                async with self.session.get(url) as response:
                    response_time = time.time() - start_time

                    # Get security headers
                    security_headers = {
                        key: value for key, value in response.headers.items()
                        if key.lower().startswith(('x-', 'strict-transport', 'content-security'))
                    }

                    return TestResult(
                        endpoint=path,
                        method=method,
                        status_code=response.status,
                        response_time=response_time,
                        success=response.status < 500,  # Any status < 500 is considered success for testing
                        security_headers=security_headers
                    )

            elif method == "POST":
                headers = {"Content-Type": "application/json"}
                async with self.session.post(url, json=payload, headers=headers) as response:
                    response_time = time.time() - start_time

                    security_headers = {
                        key: value for key, value in response.headers.items()
                        if key.lower().startswith(('x-', 'strict-transport', 'content-security'))
                    }

                    return TestResult(
                        endpoint=path,
                        method=method,
                        status_code=response.status,
                        response_time=response_time,
                        success=response.status < 500,
                        security_headers=security_headers
                    )

        except Exception as e:
            response_time = time.time() - start_time
            return TestResult(
                endpoint=path,
                method=method,
                status_code=0,
                response_time=response_time,
                success=False,
                error_message=str(e)
            )

    async def test_security_protection(self) -> List[TestResult]:
        """Test security middleware protection against malicious payloads"""
        security_results = []

        self.print_status("Testing security middleware protection...", "HEADER")

        for test_case in self.security_test_payloads:
            test_type = test_case["type"]
            payload = test_case["payload"]

            # Test against feedback endpoint (accepts POST)
            url = f"{self.base_url}/api/v1/feedback/submit"

            start_time = time.time()

            try:
                headers = {"Content-Type": "application/json"}
                async with self.session.post(url, json=payload, headers=headers) as response:
                    response_time = time.time() - start_time

                    # Security middleware should block malicious requests (400 status)
                    blocked = response.status == 400

                    result = TestResult(
                        endpoint=f"/api/v1/feedback/submit ({test_type})",
                        method="POST",
                        status_code=response.status,
                        response_time=response_time,
                        success=blocked,  # Success means the request was blocked
                        error_message=None if blocked else "Malicious request not blocked"
                    )

                    security_results.append(result)

                    if blocked:
                        self.print_status(f"✓ {test_type.upper()} attack blocked", "SUCCESS")
                    else:
                        self.print_status(f"✗ {test_type.upper()} attack not blocked", "ERROR")

            except Exception as e:
                response_time = time.time() - start_time
                result = TestResult(
                    endpoint=f"/api/v1/feedback/submit ({test_type})",
                    method="POST",
                    status_code=0,
                    response_time=response_time,
                    success=False,
                    error_message=str(e)
                )
                security_results.append(result)
                self.print_status(f"✗ Error testing {test_type}: {str(e)}", "ERROR")

        return security_results

    async def test_rate_limiting(self) -> TestResult:
        """Test rate limiting functionality"""
        self.print_status("Testing rate limiting...", "HEADER")

        url = f"{self.base_url}/api/v1/health"

        # Send requests rapidly to trigger rate limiting
        tasks = []
        for i in range(110):  # Exceed the rate limit of 100 requests
            tasks.append(self.session.get(url))

        start_time = time.time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        response_time = time.time() - start_time

        # Count rate limited responses (429 status)
        rate_limited_count = 0
        success_count = 0

        for response in responses:
            if isinstance(response, Exception):
                continue

            if hasattr(response, 'status'):
                if response.status == 429:
                    rate_limited_count += 1
                elif response.status == 200:
                    success_count += 1
                response.close()

        # Rate limiting is working if some requests were limited
        rate_limiting_works = rate_limited_count > 0

        if rate_limiting_works:
            self.print_status(f"✓ Rate limiting working: {rate_limited_count} requests limited", "SUCCESS")
        else:
            self.print_status("✗ Rate limiting not working", "ERROR")

        return TestResult(
            endpoint="/api/v1/health (rate limit test)",
            method="GET",
            status_code=429 if rate_limiting_works else 200,
            response_time=response_time,
            success=rate_limiting_works,
            error_message=None if rate_limiting_works else "Rate limiting not triggered"
        )

    async def run_tests(self) -> Dict[str, Any]:
        """Run all endpoint tests"""
        self.print_status("Starting security endpoint testing...", "HEADER")

        # Test regular endpoints
        self.print_status("Testing API endpoints...", "HEADER")
        for endpoint in self.endpoints:
            result = await self.test_endpoint(endpoint)
            self.results.append(result)

            status = "SUCCESS" if result.success else "ERROR"
            response_info = f"{result.status_code} ({result.response_time:.3f}s)"

            if result.error_message:
                self.print_status(f"{endpoint['method']} {result.endpoint}: {response_info} - {result.error_message}", status)
            else:
                self.print_status(f"{endpoint['method']} {result.endpoint}: {response_info}", status)

        # Test security protection
        security_results = await self.test_security_protection()
        self.results.extend(security_results)

        # Test rate limiting
        rate_limit_result = await self.test_rate_limiting()
        self.results.append(rate_limit_result)

        # Generate summary
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r.success])
        failed_tests = total_tests - successful_tests

        # Check security headers
        endpoints_with_security_headers = len([
            r for r in self.results
            if r.security_headers and len(r.security_headers) > 0
        ])

        summary = {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "success_rate": (successful_tests / total_tests) * 100 if total_tests > 0 else 0,
            "endpoints_with_security_headers": endpoints_with_security_headers,
            "average_response_time": sum(r.response_time for r in self.results) / total_tests if total_tests > 0 else 0,
            "results": self.results
        }

        return summary

    def print_summary(self, summary: Dict[str, Any]):
        """Print test summary"""
        print("\n" + "="*60)
        self.print_status("SECURITY ENDPOINT TEST SUMMARY", "HEADER")
        print("="*60)

        print(f"Total Tests: {summary['total_tests']}")
        print(f"Successful: {Fore.GREEN}{summary['successful_tests']}{Style.RESET_ALL}")
        print(f"Failed: {Fore.RED}{summary['failed_tests']}{Style.RESET_ALL}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Endpoints with Security Headers: {summary['endpoints_with_security_headers']}")
        print(f"Average Response Time: {summary['average_response_time']:.3f}s")

        if summary['failed_tests'] > 0:
            print(f"\n{Fore.RED}Failed Tests:{Style.RESET_ALL}")
            for result in summary['results']:
                if not result.success:
                    error_msg = result.error_message or f"Status: {result.status_code}"
                    print(f"  - {result.method} {result.endpoint}: {error_msg}")

        # Security headers check
        print(f"\n{Fore.CYAN}Security Headers Found:{Style.RESET_ALL}")
        security_headers_found = set()
        for result in summary['results']:
            if result.security_headers:
                security_headers_found.update(result.security_headers.keys())

        for header in sorted(security_headers_found):
            print(f"  ✓ {header}")

async def main():
    """Main test function"""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8000"

    async with SecurityEndpointTester(base_url) as tester:
        try:
            summary = await tester.run_tests()
            tester.print_summary(summary)

            # Exit with error code if tests failed
            if summary['failed_tests'] > 0:
                sys.exit(1)
            else:
                tester.print_status("All tests passed!", "SUCCESS")
                sys.exit(0)

        except KeyboardInterrupt:
            tester.print_status("Testing interrupted by user", "WARNING")
            sys.exit(1)
        except Exception as e:
            tester.print_status(f"Testing failed with error: {str(e)}", "ERROR")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())