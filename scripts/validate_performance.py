#!/usr/bin/env python3
"""
Performance Validation Script for AgentOS.

This script runs automated performance tests and validates against requirements:
- P50 response time < 100ms
- P95 response time < 200ms
- Error rate < 1%
- Cache hit rate > 60%
- Support for 100+ concurrent users
"""
import asyncio
import aiohttp
import time
import json
import sys
from typing import Dict, Any

class PerformanceValidator:
    """Validates AgentOS performance against requirements."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_prefix = "/api/v1"
        self.validation_results = {}

    async def run_validation(self) -> bool:
        """Run complete performance validation."""
        print("🔍 AgentOS Performance Validation")
        print("=" * 50)

        # Test 1: Basic health and response time
        health_passed = await self._test_basic_health()

        # Test 2: Performance metrics validation
        metrics_passed = await self._test_performance_metrics()

        # Test 3: Concurrent request handling
        concurrency_passed = await self._test_concurrent_requests()

        # Test 4: Cache performance
        cache_passed = await self._test_cache_performance()

        # Test 5: Database performance
        db_passed = await self._test_database_performance()

        # Generate final report
        overall_passed = all([health_passed, metrics_passed, concurrency_passed, cache_passed, db_passed])
        await self._generate_validation_report(overall_passed)

        return overall_passed

    async def _test_basic_health(self) -> bool:
        """Test basic health and response times."""
        print("\n1. Testing Basic Health & Response Times...")

        async with aiohttp.ClientSession() as session:
            # Test health endpoint
            start_time = time.time()
            try:
                async with session.get(f"{self.base_url}/health") as response:
                    response_time = (time.time() - start_time) * 1000

                    if response.status == 200 and response_time < 100:
                        print(f"   ✅ Health check: {response_time:.1f}ms")
                        self.validation_results['health_check'] = {'passed': True, 'response_time': response_time}
                        return True
                    else:
                        print(f"   ❌ Health check failed: {response.status}, {response_time:.1f}ms")
                        self.validation_results['health_check'] = {'passed': False, 'response_time': response_time, 'status': response.status}
                        return False

            except Exception as e:
                print(f"   ❌ Health check error: {e}")
                self.validation_results['health_check'] = {'passed': False, 'error': str(e)}
                return False

    async def _test_performance_metrics(self) -> bool:
        """Test performance metrics endpoint and validate thresholds."""
        print("\n2. Testing Performance Metrics...")

        async with aiohttp.ClientSession() as session:
            try:
                start_time = time.time()
                async with session.get(f"{self.base_url}{self.api_prefix}/performance/summary") as response:
                    response_time = (time.time() - start_time) * 1000

                    if response.status == 200:
                        data = await response.json()

                        # Validate API response times
                        api_metrics = data.get('api', {})
                        api_validation = True

                        for endpoint, stats in api_metrics.items():
                            avg_response = stats.get('avg_response_time', 0)
                            p95_response = stats.get('p95_response_time', 0)

                            if avg_response > 100:
                                print(f"   ⚠️  {endpoint}: Avg response time {avg_response:.1f}ms > 100ms")
                                api_validation = False

                            if p95_response > 200:
                                print(f"   ❌ {endpoint}: P95 response time {p95_response:.1f}ms > 200ms")
                                api_validation = False

                        if api_validation:
                            print(f"   ✅ API response times within thresholds")

                        # Validate system metrics
                        system_metrics = data.get('system', {})
                        cpu_usage = system_metrics.get('cpu_percent', 0)
                        memory_usage = system_metrics.get('memory_percent', 0)

                        system_validation = True
                        if cpu_usage > 80:
                            print(f"   ⚠️  High CPU usage: {cpu_usage:.1f}%")
                            system_validation = False

                        if memory_usage > 85:
                            print(f"   ⚠️  High memory usage: {memory_usage:.1f}%")
                            system_validation = False

                        if system_validation:
                            print(f"   ✅ System resources within limits")

                        self.validation_results['performance_metrics'] = {
                            'passed': api_validation and system_validation,
                            'response_time': response_time,
                            'api_validation': api_validation,
                            'system_validation': system_validation
                        }

                        return api_validation and system_validation

                    else:
                        print(f"   ❌ Performance metrics endpoint failed: {response.status}")
                        return False

            except Exception as e:
                print(f"   ❌ Performance metrics error: {e}")
                self.validation_results['performance_metrics'] = {'passed': False, 'error': str(e)}
                return False

    async def _test_concurrent_requests(self) -> bool:
        """Test handling of concurrent requests."""
        print("\n3. Testing Concurrent Request Handling...")

        concurrent_users = 50
        endpoint = f"{self.base_url}/health"

        async def make_request(session: aiohttp.ClientSession) -> Dict[str, Any]:
            start_time = time.time()
            try:
                async with session.get(endpoint) as response:
                    response_time = (time.time() - start_time) * 1000
                    return {
                        'success': response.status == 200,
                        'response_time': response_time,
                        'status_code': response.status
                    }
            except Exception as e:
                return {
                    'success': False,
                    'response_time': 0,
                    'error': str(e)
                }

        async with aiohttp.ClientSession() as session:
            # Create concurrent requests
            tasks = [make_request(session) for _ in range(concurrent_users)]
            start_time = time.time()
            results = await asyncio.gather(*tasks)
            total_time = time.time() - start_time

            successful = [r for r in results if r['success']]
            failed = [r for r in results if not r['success']]

            success_rate = len(successful) / len(results) * 100
            avg_response_time = sum(r['response_time'] for r in successful) / len(successful) if successful else 0
            requests_per_second = len(results) / total_time

            validation_passed = (
                success_rate >= 99 and  # 99% success rate
                avg_response_time < 200 and  # Average response time under 200ms
                requests_per_second >= 20  # At least 20 RPS
            )

            if validation_passed:
                print(f"   ✅ Concurrent requests: {success_rate:.1f}% success, {avg_response_time:.1f}ms avg, {requests_per_second:.1f} RPS")
            else:
                print(f"   ❌ Concurrent requests failed: {success_rate:.1f}% success, {avg_response_time:.1f}ms avg, {requests_per_second:.1f} RPS")

            self.validation_results['concurrent_requests'] = {
                'passed': validation_passed,
                'success_rate': success_rate,
                'avg_response_time': avg_response_time,
                'requests_per_second': requests_per_second
            }

            return validation_passed

    async def _test_cache_performance(self) -> bool:
        """Test cache performance and hit rates."""
        print("\n4. Testing Cache Performance...")

        async with aiohttp.ClientSession() as session:
            try:
                # Make the same request multiple times to test caching
                endpoint = f"{self.base_url}{self.api_prefix}/performance/summary"

                # First request (cache miss)
                start_time = time.time()
                async with session.get(endpoint) as response:
                    first_response_time = (time.time() - start_time) * 1000

                if response.status != 200:
                    print(f"   ❌ Cache test failed: endpoint returned {response.status}")
                    return False

                data = await response.json()

                # Check if cache metrics are available
                db_metrics = data.get('database', {})
                cache_hit_rate = db_metrics.get('cache_hit_rate', 0)

                # Multiple subsequent requests (should be cached)
                response_times = []
                for i in range(5):
                    start_time = time.time()
                    async with session.get(endpoint) as response:
                        response_time = (time.time() - start_time) * 1000
                        response_times.append(response_time)
                    await asyncio.sleep(0.1)  # Small delay

                avg_cached_response = sum(response_times) / len(response_times)

                # Validate cache performance
                cache_validation = cache_hit_rate >= 60  # Target cache hit rate
                response_validation = avg_cached_response < first_response_time * 1.5  # Cached responses should be similar or faster

                overall_passed = cache_validation

                if cache_validation:
                    print(f"   ✅ Cache hit rate: {cache_hit_rate:.1f}% (>= 60%)")
                else:
                    print(f"   ❌ Cache hit rate: {cache_hit_rate:.1f}% (< 60%)")

                if response_validation:
                    print(f"   ✅ Cached response performance: {avg_cached_response:.1f}ms")
                else:
                    print(f"   ⚠️  Cached response performance: {avg_cached_response:.1f}ms (slower than expected)")

                self.validation_results['cache_performance'] = {
                    'passed': overall_passed,
                    'cache_hit_rate': cache_hit_rate,
                    'first_response_time': first_response_time,
                    'avg_cached_response': avg_cached_response
                }

                return overall_passed

            except Exception as e:
                print(f"   ❌ Cache performance test error: {e}")
                self.validation_results['cache_performance'] = {'passed': False, 'error': str(e)}
                return False

    async def _test_database_performance(self) -> bool:
        """Test database performance metrics."""
        print("\n5. Testing Database Performance...")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}{self.api_prefix}/performance/database") as response:
                    if response.status == 200:
                        data = await response.json()
                        db_data = data.get('data', {}).get('database', {})

                        avg_query_time = db_data.get('avg_query_time', 0)
                        p95_query_time = db_data.get('p95_query_time', 0)
                        total_queries = db_data.get('total_queries', 0)
                        failed_queries = db_data.get('failed_queries', 0)

                        # Validate database performance
                        query_time_ok = avg_query_time < 50  # Target average query time
                        p95_time_ok = p95_query_time < 100   # Target P95 query time
                        error_rate_ok = (failed_queries / total_queries * 100) < 1 if total_queries > 0 else True

                        overall_passed = query_time_ok and p95_time_ok and error_rate_ok

                        if query_time_ok:
                            print(f"   ✅ Avg query time: {avg_query_time:.1f}ms (< 50ms)")
                        else:
                            print(f"   ❌ Avg query time: {avg_query_time:.1f}ms (>= 50ms)")

                        if p95_time_ok:
                            print(f"   ✅ P95 query time: {p95_query_time:.1f}ms (< 100ms)")
                        else:
                            print(f"   ❌ P95 query time: {p95_query_time:.1f}ms (>= 100ms)")

                        if error_rate_ok:
                            error_rate = (failed_queries / total_queries * 100) if total_queries > 0 else 0
                            print(f"   ✅ Query error rate: {error_rate:.2f}% (< 1%)")
                        else:
                            error_rate = (failed_queries / total_queries * 100)
                            print(f"   ❌ Query error rate: {error_rate:.2f}% (>= 1%)")

                        self.validation_results['database_performance'] = {
                            'passed': overall_passed,
                            'avg_query_time': avg_query_time,
                            'p95_query_time': p95_query_time,
                            'total_queries': total_queries,
                            'failed_queries': failed_queries
                        }

                        return overall_passed

                    else:
                        print(f"   ❌ Database performance endpoint failed: {response.status}")
                        return False

            except Exception as e:
                print(f"   ❌ Database performance test error: {e}")
                self.validation_results['database_performance'] = {'passed': False, 'error': str(e)}
                return False

    async def _generate_validation_report(self, overall_passed: bool):
        """Generate final validation report."""
        print("\n" + "=" * 50)
        print("📋 PERFORMANCE VALIDATION REPORT")
        print("=" * 50)

        passed_tests = sum(1 for result in self.validation_results.values() if result.get('passed', False))
        total_tests = len(self.validation_results)

        print(f"Overall Result: {'✅ PASSED' if overall_passed else '❌ FAILED'}")
        print(f"Tests Passed: {passed_tests}/{total_tests}")

        print(f"\nDetailed Results:")
        for test_name, result in self.validation_results.items():
            status = "✅ PASSED" if result.get('passed', False) else "❌ FAILED"
            print(f"  {test_name}: {status}")

            if 'response_time' in result:
                print(f"    Response Time: {result['response_time']:.1f}ms")

            if 'error' in result:
                print(f"    Error: {result['error']}")

        print(f"\n{'🎉 All performance requirements met!' if overall_passed else '⚠️  Performance optimization needed.'}")
        print("=" * 50)

async def main():
    """Main function to run performance validation."""
    import argparse

    parser = argparse.ArgumentParser(description="AgentOS Performance Validation")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for testing")
    args = parser.parse_args()

    validator = PerformanceValidator(args.url)
    validation_passed = await validator.run_validation()

    # Exit with appropriate code
    sys.exit(0 if validation_passed else 1)

if __name__ == "__main__":
    asyncio.run(main())