# AgentOS Load Testing Suite

This directory contains comprehensive load testing and performance validation tools for AgentOS.

## Overview

The load testing suite validates that AgentOS meets the Phase 8 performance requirements:
- **P50 response time < 100ms**
- **P95 response time < 200ms**
- **Support for 100+ concurrent users**
- **Cache hit rate > 60%**
- **System uptime and stability**

## Files

### `load_testing.py`
Comprehensive load testing script that simulates real-world usage patterns.

**Features:**
- API endpoint load testing
- WebSocket connection testing
- Mixed scenario testing
- Stress testing with progressive load
- System resource monitoring
- Detailed performance reporting

**Usage:**
```bash
# Basic load test
python scripts/load_testing.py

# Custom configuration
python scripts/load_testing.py \
  --url http://localhost:8000 \
  --users 100 \
  --duration 300 \
  --scenarios api websocket mixed

# Stress test
python scripts/load_testing.py \
  --users 200 \
  --scenarios stress
```

### `validate_performance.py`
Automated performance validation against specific requirements.

**Features:**
- Health check validation
- Response time validation
- Concurrent request handling
- Cache performance testing
- Database performance validation

**Usage:**
```bash
# Run validation
python scripts/validate_performance.py

# Custom URL
python scripts/validate_performance.py --url http://your-server:8000
```

### `optimize_performance.py`
Database optimization script (from earlier Phase 8 implementation).

**Usage:**
```bash
python scripts/optimize_performance.py
```

## Installation

Install load testing dependencies:

```bash
pip install -r requirements-load-testing.txt
```

## Test Scenarios

### 1. API Load Test
- Tests REST API endpoints under load
- Simulates realistic user behavior
- Validates response times and error rates

### 2. WebSocket Load Test
- Tests WebSocket connections and messaging
- Validates real-time communication performance
- Tests connection stability under load

### 3. Mixed Load Test
- Combines API and WebSocket testing
- Simulates real-world usage patterns
- Tests system performance under mixed workloads

### 4. Stress Test
- Progressive load testing
- Identifies system breaking points
- Validates graceful degradation

## Performance Targets

| Metric | Target | Validation |
|--------|--------|------------|
| P50 Response Time | < 100ms | ✅ Critical |
| P95 Response Time | < 200ms | ✅ Critical |
| Error Rate | < 1% | ✅ Critical |
| Cache Hit Rate | > 60% | ✅ Important |
| Concurrent Users | 100+ | ✅ Critical |
| RPS (Requests/sec) | 100+ | ⚠️ Target |

## Interpreting Results

### Response Times
- **Good**: P95 < 150ms
- **Acceptable**: P95 < 200ms
- **Needs Optimization**: P95 > 200ms

### Error Rates
- **Excellent**: < 0.1%
- **Good**: < 1%
- **Needs Attention**: > 1%

### System Resources
- **CPU Usage**: Should stay < 80% under load
- **Memory Usage**: Should stay < 85% under load
- **Cache Hit Rate**: Should be > 60%

## Continuous Integration

Add to your CI/CD pipeline:

```yaml
# Example GitHub Actions
- name: Performance Validation
  run: |
    python scripts/validate_performance.py
    if [ $? -ne 0 ]; then
      echo "Performance validation failed"
      exit 1
    fi
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure AgentOS is running on the specified URL
   - Check firewall settings

2. **High Response Times**
   - Check database indexes (run `optimize_performance.py`)
   - Verify Redis cache is running
   - Check system resources

3. **WebSocket Connection Failures**
   - Verify authentication tokens
   - Check WebSocket endpoint configuration
   - Ensure proper CORS settings

4. **Memory Issues During Testing**
   - Reduce concurrent users
   - Check for memory leaks in application
   - Monitor system resources during tests

### Performance Optimization Tips

1. **Database**
   - Run database optimization script regularly
   - Monitor slow queries
   - Ensure proper indexing

2. **Caching**
   - Verify Redis is properly configured
   - Check cache hit rates
   - Optimize cache TTL settings

3. **Frontend**
   - Use bundle optimization
   - Implement lazy loading
   - Optimize image assets

4. **System**
   - Monitor resource usage
   - Scale horizontally if needed
   - Optimize WebSocket connections

## Monitoring Integration

The load testing suite integrates with the AgentOS performance monitoring system to provide real-time insights during testing.

Access performance dashboard at: `http://your-server:8000/dashboard/performance`

## Support

For issues with load testing:
1. Check the troubleshooting section above
2. Review application logs during test runs
3. Monitor system resources
4. Verify all dependencies are installed correctly