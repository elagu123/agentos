#!/usr/bin/env python3
"""
Comprehensive Load Testing Suite for AgentOS.

This script provides:
- Multi-scenario load testing
- Performance validation
- Stress testing
- WebSocket connection testing
- Database performance testing
- Cache performance testing
- Concurrent user simulation
- Performance metrics collection and reporting
"""
import asyncio
import aiohttp
import websockets
import json
import time
import statistics
import random
import argparse
import sys
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import uuid
import psutil

# Test configuration
@dataclass
class LoadTestConfig:
    """Configuration for load testing."""
    base_url: str = "http://localhost:8000"
    websocket_url: str = "ws://localhost:8000"
    api_prefix: str = "/api/v1"
    concurrent_users: int = 100
    test_duration_seconds: int = 300  # 5 minutes
    ramp_up_seconds: int = 60
    auth_token: str = ""
    scenarios: List[str] = field(default_factory=lambda: ["api", "websocket", "mixed"])

@dataclass
class TestResult:
    """Individual test result."""
    test_name: str
    start_time: float
    end_time: float
    success: bool
    response_time_ms: float
    status_code: int = 0
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ScenarioResult:
    """Results for a complete test scenario."""
    scenario_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    min_response_time: float
    max_response_time: float
    requests_per_second: float
    error_rate: float
    errors: Dict[str, int] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime = field(default_factory=datetime.now)

class LoadTester:
    """Main load testing class."""

    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results: List[TestResult] = []
        self.scenario_results: List[ScenarioResult] = []
        self.system_metrics: List[Dict[str, Any]] = []
        self.start_time = time.time()

    async def run_load_test(self):
        """Run the complete load testing suite."""
        print(f"🚀 Starting AgentOS Load Testing Suite")
        print(f"   Target: {self.config.base_url}")
        print(f"   Concurrent Users: {self.config.concurrent_users}")
        print(f"   Test Duration: {self.config.test_duration_seconds}s")
        print(f"   Scenarios: {', '.join(self.config.scenarios)}")
        print("=" * 60)

        # Start system monitoring
        monitoring_task = asyncio.create_task(self._monitor_system_resources())

        try:
            # Run authentication test first
            await self._test_authentication()

            # Run scenarios
            for scenario in self.config.scenarios:
                if scenario == "api":
                    await self._run_api_load_test()
                elif scenario == "websocket":
                    await self._run_websocket_load_test()
                elif scenario == "mixed":
                    await self._run_mixed_load_test()
                elif scenario == "stress":
                    await self._run_stress_test()

            # Generate final report
            await self._generate_report()

        finally:
            # Stop monitoring
            monitoring_task.cancel()
            try:
                await monitoring_task
            except asyncio.CancelledError:
                pass

    async def _test_authentication(self):
        """Test authentication endpoints."""
        print("\n📋 Testing Authentication...")

        async with aiohttp.ClientSession() as session:
            # Test health endpoint
            start_time = time.time()
            try:
                async with session.get(f"{self.config.base_url}/health") as response:
                    end_time = time.time()
                    success = response.status == 200
                    result = TestResult(
                        test_name="health_check",
                        start_time=start_time,
                        end_time=end_time,
                        success=success,
                        response_time_ms=(end_time - start_time) * 1000,
                        status_code=response.status
                    )
                    self.results.append(result)

                    if success:
                        print(f"   ✅ Health check: {result.response_time_ms:.1f}ms")
                    else:
                        print(f"   ❌ Health check failed: {response.status}")

            except Exception as e:
                result = TestResult(
                    test_name="health_check",
                    start_time=start_time,
                    end_time=time.time(),
                    success=False,
                    response_time_ms=0,
                    error=str(e)
                )
                self.results.append(result)
                print(f"   ❌ Health check error: {e}")

    async def _run_api_load_test(self):
        """Run API-focused load test."""
        print(f"\n🔥 Running API Load Test ({self.config.concurrent_users} concurrent users)")

        # Define API endpoints to test
        endpoints = [
            {"method": "GET", "path": "/health", "weight": 0.3},
            {"method": "GET", "path": f"{self.config.api_prefix}/performance/summary", "weight": 0.2},
            {"method": "GET", "path": f"{self.config.api_prefix}/auth/me", "weight": 0.2, "auth": True},
            {"method": "GET", "path": f"{self.config.api_prefix}/agents", "weight": 0.15, "auth": True},
            {"method": "GET", "path": f"{self.config.api_prefix}/workflows", "weight": 0.15, "auth": True},
        ]

        start_time = datetime.now()

        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.config.concurrent_users)

        # Run test for specified duration
        tasks = []
        end_test_time = time.time() + self.config.test_duration_seconds

        # Ramp up users gradually
        ramp_up_delay = self.config.ramp_up_seconds / self.config.concurrent_users

        for i in range(self.config.concurrent_users):
            task = asyncio.create_task(
                self._api_user_simulation(semaphore, endpoints, end_test_time, i * ramp_up_delay)
            )
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        # Calculate results
        api_results = [r for r in self.results if r.test_name.startswith("api_")]
        scenario_result = self._calculate_scenario_results("API Load Test", api_results, start_time)
        self.scenario_results.append(scenario_result)

        print(f"   📊 API Results: {scenario_result.successful_requests}/{scenario_result.total_requests} successful")
        print(f"   ⏱️  Avg Response Time: {scenario_result.avg_response_time:.1f}ms")
        print(f"   📈 Requests/sec: {scenario_result.requests_per_second:.1f}")
        print(f"   🎯 P95 Response Time: {scenario_result.p95_response_time:.1f}ms")

    async def _api_user_simulation(self, semaphore: asyncio.Semaphore, endpoints: List[Dict], end_time: float, initial_delay: float = 0):
        """Simulate a single user's API usage pattern."""
        # Initial delay for ramp-up
        if initial_delay > 0:
            await asyncio.sleep(initial_delay)

        async with aiohttp.ClientSession() as session:
            while time.time() < end_time:
                async with semaphore:
                    # Select random endpoint based on weights
                    endpoint = self._weighted_choice(endpoints)

                    await self._make_api_request(session, endpoint)

                    # Random delay between requests (1-3 seconds)
                    await asyncio.sleep(random.uniform(1, 3))

    async def _make_api_request(self, session: aiohttp.ClientSession, endpoint: Dict):
        """Make a single API request."""
        url = f"{self.config.base_url}{endpoint['path']}"
        headers = {}

        if endpoint.get("auth") and self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"

        start_time = time.time()
        try:
            async with session.request(
                endpoint["method"],
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                end_time = time.time()

                result = TestResult(
                    test_name=f"api_{endpoint['method'].lower()}_{endpoint['path'].split('/')[-1]}",
                    start_time=start_time,
                    end_time=end_time,
                    success=response.status < 400,
                    response_time_ms=(end_time - start_time) * 1000,
                    status_code=response.status,
                    metadata={"endpoint": endpoint["path"], "method": endpoint["method"]}
                )
                self.results.append(result)

        except Exception as e:
            result = TestResult(
                test_name=f"api_{endpoint['method'].lower()}_{endpoint['path'].split('/')[-1]}",
                start_time=start_time,
                end_time=time.time(),
                success=False,
                response_time_ms=0,
                error=str(e),
                metadata={"endpoint": endpoint["path"], "method": endpoint["method"]}
            )
            self.results.append(result)

    async def _run_websocket_load_test(self):
        """Run WebSocket-focused load test."""
        print(f"\n🔌 Running WebSocket Load Test ({self.config.concurrent_users} concurrent connections)")

        start_time = datetime.now()

        # Simulate WebSocket connections
        tasks = []
        end_test_time = time.time() + self.config.test_duration_seconds
        ramp_up_delay = self.config.ramp_up_seconds / self.config.concurrent_users

        for i in range(self.config.concurrent_users):
            task = asyncio.create_task(
                self._websocket_user_simulation(end_test_time, i * ramp_up_delay, f"user_{i}")
            )
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        # Calculate results
        ws_results = [r for r in self.results if r.test_name.startswith("websocket_")]
        scenario_result = self._calculate_scenario_results("WebSocket Load Test", ws_results, start_time)
        self.scenario_results.append(scenario_result)

        print(f"   📊 WebSocket Results: {scenario_result.successful_requests}/{scenario_result.total_requests} successful")
        print(f"   ⏱️  Avg Connection Time: {scenario_result.avg_response_time:.1f}ms")

    async def _websocket_user_simulation(self, end_time: float, initial_delay: float, user_id: str):
        """Simulate a single user's WebSocket usage."""
        if initial_delay > 0:
            await asyncio.sleep(initial_delay)

        ws_url = f"{self.config.websocket_url.replace('http', 'ws')}{self.config.api_prefix}/ws/{user_id}"
        if self.config.auth_token:
            ws_url += f"?token={self.config.auth_token}"

        start_time = time.time()
        try:
            async with websockets.connect(ws_url, timeout=10) as websocket:
                connection_time = time.time()

                # Record successful connection
                result = TestResult(
                    test_name="websocket_connect",
                    start_time=start_time,
                    end_time=connection_time,
                    success=True,
                    response_time_ms=(connection_time - start_time) * 1000,
                    metadata={"user_id": user_id}
                )
                self.results.append(result)

                # Send periodic messages
                message_count = 0
                while time.time() < end_time:
                    try:
                        # Send ping
                        ping_start = time.time()
                        await websocket.send(json.dumps({
                            "type": "ping",
                            "timestamp": ping_start,
                            "message_id": message_count
                        }))

                        # Wait for response
                        response = await asyncio.wait_for(websocket.recv(), timeout=5)
                        ping_end = time.time()

                        result = TestResult(
                            test_name="websocket_ping",
                            start_time=ping_start,
                            end_time=ping_end,
                            success=True,
                            response_time_ms=(ping_end - ping_start) * 1000,
                            metadata={"user_id": user_id, "message_id": message_count}
                        )
                        self.results.append(result)

                        message_count += 1
                        await asyncio.sleep(random.uniform(5, 15))  # Random interval

                    except asyncio.TimeoutError:
                        result = TestResult(
                            test_name="websocket_ping",
                            start_time=ping_start,
                            end_time=time.time(),
                            success=False,
                            response_time_ms=0,
                            error="Timeout waiting for response",
                            metadata={"user_id": user_id, "message_id": message_count}
                        )
                        self.results.append(result)

        except Exception as e:
            result = TestResult(
                test_name="websocket_connect",
                start_time=start_time,
                end_time=time.time(),
                success=False,
                response_time_ms=0,
                error=str(e),
                metadata={"user_id": user_id}
            )
            self.results.append(result)

    async def _run_mixed_load_test(self):
        """Run mixed API and WebSocket load test."""
        print(f"\n🔀 Running Mixed Load Test ({self.config.concurrent_users} concurrent users)")

        start_time = datetime.now()

        # Mix of API and WebSocket users (70% API, 30% WebSocket)
        api_users = int(self.config.concurrent_users * 0.7)
        ws_users = self.config.concurrent_users - api_users

        # API endpoints
        endpoints = [
            {"method": "GET", "path": "/health", "weight": 0.4},
            {"method": "GET", "path": f"{self.config.api_prefix}/performance/summary", "weight": 0.3},
            {"method": "GET", "path": f"{self.config.api_prefix}/agents", "weight": 0.3, "auth": True},
        ]

        tasks = []
        end_test_time = time.time() + self.config.test_duration_seconds
        ramp_up_delay = self.config.ramp_up_seconds / self.config.concurrent_users

        # Start API users
        semaphore = asyncio.Semaphore(api_users)
        for i in range(api_users):
            task = asyncio.create_task(
                self._api_user_simulation(semaphore, endpoints, end_test_time, i * ramp_up_delay)
            )
            tasks.append(task)

        # Start WebSocket users
        for i in range(ws_users):
            task = asyncio.create_task(
                self._websocket_user_simulation(end_test_time, (api_users + i) * ramp_up_delay, f"mixed_user_{i}")
            )
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        # Calculate results
        mixed_results = [r for r in self.results if r.test_name.startswith(("api_", "websocket_"))]
        scenario_result = self._calculate_scenario_results("Mixed Load Test", mixed_results, start_time)
        self.scenario_results.append(scenario_result)

        print(f"   📊 Mixed Results: {scenario_result.successful_requests}/{scenario_result.total_requests} successful")
        print(f"   ⏱️  Avg Response Time: {scenario_result.avg_response_time:.1f}ms")

    async def _run_stress_test(self):
        """Run stress test with increasing load."""
        print(f"\n🔥 Running Stress Test (Progressive Load)")

        # Test with increasing concurrent users: 50, 100, 200, 400
        stress_levels = [50, 100, 200, 400]

        for level in stress_levels:
            if level > self.config.concurrent_users * 4:
                break  # Don't exceed 4x the configured load

            print(f"   Testing with {level} concurrent users...")

            start_time = datetime.now()

            # Simple API endpoint for stress testing
            endpoints = [{"method": "GET", "path": "/health", "weight": 1.0}]

            semaphore = asyncio.Semaphore(level)
            tasks = []
            test_duration = 60  # 1 minute per stress level
            end_test_time = time.time() + test_duration

            for i in range(level):
                task = asyncio.create_task(
                    self._api_user_simulation(semaphore, endpoints, end_test_time, 0)
                )
                tasks.append(task)

            await asyncio.gather(*tasks, return_exceptions=True)

            # Calculate results for this stress level
            level_results = [r for r in self.results
                           if r.start_time >= start_time.timestamp() and r.test_name.startswith("api_")]

            if level_results:
                scenario_result = self._calculate_scenario_results(f"Stress Test - {level} users", level_results, start_time)
                self.scenario_results.append(scenario_result)

                print(f"     Success Rate: {(scenario_result.successful_requests/scenario_result.total_requests)*100:.1f}%")
                print(f"     Avg Response: {scenario_result.avg_response_time:.1f}ms")
                print(f"     P95 Response: {scenario_result.p95_response_time:.1f}ms")

                # Check if system is stressed (high response times or errors)
                if scenario_result.p95_response_time > 1000 or scenario_result.error_rate > 10:
                    print(f"     ⚠️  System stress detected at {level} users")
                    break

    async def _monitor_system_resources(self):
        """Monitor system resources during testing."""
        while True:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()

                metric = {
                    "timestamp": time.time(),
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_mb": memory.used / 1024 / 1024
                }
                self.system_metrics.append(metric)

                await asyncio.sleep(10)  # Sample every 10 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error monitoring system: {e}")
                await asyncio.sleep(10)

    def _weighted_choice(self, choices: List[Dict]) -> Dict:
        """Select a random choice based on weights."""
        total_weight = sum(choice.get("weight", 1) for choice in choices)
        random_value = random.uniform(0, total_weight)

        current_weight = 0
        for choice in choices:
            current_weight += choice.get("weight", 1)
            if random_value <= current_weight:
                return choice

        return choices[-1]  # Fallback

    def _calculate_scenario_results(self, scenario_name: str, results: List[TestResult], start_time: datetime) -> ScenarioResult:
        """Calculate aggregated results for a scenario."""
        if not results:
            return ScenarioResult(
                scenario_name=scenario_name,
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                avg_response_time=0,
                p50_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
                min_response_time=0,
                max_response_time=0,
                requests_per_second=0,
                error_rate=0,
                start_time=start_time,
                end_time=datetime.now()
            )

        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        response_times = [r.response_time_ms for r in successful]

        # Calculate duration
        duration_seconds = (datetime.now() - start_time).total_seconds()

        # Calculate error breakdown
        errors = {}
        for result in failed:
            error_key = result.error or f"HTTP_{result.status_code}"
            errors[error_key] = errors.get(error_key, 0) + 1

        return ScenarioResult(
            scenario_name=scenario_name,
            total_requests=len(results),
            successful_requests=len(successful),
            failed_requests=len(failed),
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            p50_response_time=statistics.median(response_times) if response_times else 0,
            p95_response_time=self._percentile(response_times, 95) if response_times else 0,
            p99_response_time=self._percentile(response_times, 99) if response_times else 0,
            min_response_time=min(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            requests_per_second=len(results) / duration_seconds if duration_seconds > 0 else 0,
            error_rate=(len(failed) / len(results)) * 100 if results else 0,
            errors=errors,
            start_time=start_time,
            end_time=datetime.now()
        )

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of a dataset."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]

    async def _generate_report(self):
        """Generate comprehensive test report."""
        print("\n" + "=" * 60)
        print("📊 LOAD TEST REPORT")
        print("=" * 60)

        # Overall summary
        total_requests = sum(sr.total_requests for sr in self.scenario_results)
        total_successful = sum(sr.successful_requests for sr in self.scenario_results)
        overall_error_rate = ((total_requests - total_successful) / total_requests * 100) if total_requests > 0 else 0

        print(f"Overall Results:")
        print(f"  Total Requests: {total_requests:,}")
        print(f"  Successful: {total_successful:,}")
        print(f"  Error Rate: {overall_error_rate:.2f}%")
        print(f"  Test Duration: {time.time() - self.start_time:.1f} seconds")

        # Scenario results
        print(f"\nScenario Results:")
        for result in self.scenario_results:
            print(f"\n{result.scenario_name}:")
            print(f"  Requests: {result.total_requests:,} ({result.successful_requests:,} successful)")
            print(f"  Avg Response Time: {result.avg_response_time:.1f}ms")
            print(f"  P95 Response Time: {result.p95_response_time:.1f}ms")
            print(f"  P99 Response Time: {result.p99_response_time:.1f}ms")
            print(f"  Requests/sec: {result.requests_per_second:.1f}")
            print(f"  Error Rate: {result.error_rate:.2f}%")

            if result.errors:
                print(f"  Errors:")
                for error, count in result.errors.items():
                    print(f"    {error}: {count}")

        # System metrics summary
        if self.system_metrics:
            cpu_values = [m["cpu_percent"] for m in self.system_metrics]
            memory_values = [m["memory_percent"] for m in self.system_metrics]

            print(f"\nSystem Resource Usage:")
            print(f"  Avg CPU: {statistics.mean(cpu_values):.1f}%")
            print(f"  Max CPU: {max(cpu_values):.1f}%")
            print(f"  Avg Memory: {statistics.mean(memory_values):.1f}%")
            print(f"  Max Memory: {max(memory_values):.1f}%")

        # Performance validation
        print(f"\nPerformance Validation:")
        validation_passed = True

        # Check P95 response time < 200ms
        for result in self.scenario_results:
            if result.p95_response_time > 200:
                print(f"  ❌ {result.scenario_name}: P95 response time {result.p95_response_time:.1f}ms > 200ms")
                validation_passed = False
            else:
                print(f"  ✅ {result.scenario_name}: P95 response time {result.p95_response_time:.1f}ms ≤ 200ms")

        # Check error rate < 1%
        if overall_error_rate > 1:
            print(f"  ❌ Error rate {overall_error_rate:.2f}% > 1%")
            validation_passed = False
        else:
            print(f"  ✅ Error rate {overall_error_rate:.2f}% ≤ 1%")

        # Check requests per second
        total_rps = sum(sr.requests_per_second for sr in self.scenario_results)
        if total_rps < 100:
            print(f"  ⚠️  Total RPS {total_rps:.1f} < 100 (may need optimization)")
        else:
            print(f"  ✅ Total RPS {total_rps:.1f} ≥ 100")

        print(f"\n{'🎉 PERFORMANCE VALIDATION PASSED' if validation_passed else '❌ PERFORMANCE VALIDATION FAILED'}")
        print("=" * 60)

        return validation_passed

async def main():
    """Main function to run load tests."""
    parser = argparse.ArgumentParser(description="AgentOS Load Testing Suite")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for testing")
    parser.add_argument("--users", type=int, default=100, help="Number of concurrent users")
    parser.add_argument("--duration", type=int, default=300, help="Test duration in seconds")
    parser.add_argument("--ramp-up", type=int, default=60, help="Ramp-up time in seconds")
    parser.add_argument("--token", help="Authentication token")
    parser.add_argument("--scenarios", nargs="+", default=["api", "websocket", "mixed"],
                       choices=["api", "websocket", "mixed", "stress"],
                       help="Test scenarios to run")

    args = parser.parse_args()

    config = LoadTestConfig(
        base_url=args.url,
        websocket_url=args.url.replace("http://", "ws://").replace("https://", "wss://"),
        concurrent_users=args.users,
        test_duration_seconds=args.duration,
        ramp_up_seconds=args.ramp_up,
        auth_token=args.token or "",
        scenarios=args.scenarios
    )

    tester = LoadTester(config)
    validation_passed = await tester.run_load_test()

    # Exit with appropriate code
    sys.exit(0 if validation_passed else 1)

if __name__ == "__main__":
    asyncio.run(main())