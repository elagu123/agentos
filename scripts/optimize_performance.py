#!/usr/bin/env python3
"""
Database Performance Optimization Script

This script runs all database optimizations including:
- Creating performance indexes
- Updating table statistics
- Running VACUUM ANALYZE
- Generating performance reports

Usage:
    python scripts/optimize_performance.py
"""
import asyncio
import sys
import time
from pathlib import Path

# Add the parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database_optimizer import DatabaseOptimizer
from app.database import get_db
import structlog

# Configure logging for script
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def main():
    """Run database optimization."""
    logger.info("🚀 Starting AgentOS Database Performance Optimization")
    start_time = time.time()

    try:
        # Get database session
        async for session in get_db():
            optimizer = DatabaseOptimizer(session)

            logger.info("📊 Step 1: Creating performance indexes...")
            await optimizer.create_performance_indexes()

            logger.info("📈 Step 2: Updating table statistics...")
            await optimizer.analyze_and_vacuum()

            logger.info("📋 Step 3: Generating performance report...")
            stats = await optimizer.get_query_performance_stats()

            # Print performance report
            print("\n" + "="*60)
            print("📊 DATABASE PERFORMANCE REPORT")
            print("="*60)

            if "error" not in stats:
                print(f"💾 Cache Hit Ratio: {stats.get('cache_hit_ratio', 0)}%")
                print(f"⏰ Report Generated: {stats.get('timestamp', 'N/A')}")

                print(f"\n🔍 Top Used Indexes:")
                for idx in stats.get('index_usage', [])[:5]:
                    print(f"  • {idx['indexname']}: {idx['times_used']} uses ({idx['index_size']})")

                if stats.get('slow_queries'):
                    print(f"\n🐌 Slow Queries:")
                    for query in stats['slow_queries'][:3]:
                        print(f"  • Avg: {query['mean_time']:.2f}ms, Calls: {query['calls']}")
                        print(f"    {query['query'][:100]}...")
                else:
                    print(f"\n✅ No slow queries detected (pg_stat_statements not available)")

            else:
                print(f"❌ Error generating report: {stats['error']}")

            elapsed = time.time() - start_time
            print(f"\n⏱️  Optimization completed in {elapsed:.2f} seconds")
            print("="*60)

            # Recommendations
            print("\n💡 PERFORMANCE RECOMMENDATIONS:")
            cache_ratio = stats.get('cache_hit_ratio', 0)

            if cache_ratio < 95:
                print(f"  ⚠️  Cache hit ratio is {cache_ratio}% (target: >95%)")
                print("     Consider increasing shared_buffers or adding more RAM")
            else:
                print(f"  ✅ Cache hit ratio is excellent: {cache_ratio}%")

            print("  ✅ Performance indexes created")
            print("  ✅ Table statistics updated")
            print("  ✅ Space optimized with VACUUM")

            print(f"\n🎯 Next Steps:")
            print(f"  1. Monitor cache hit ratio over time")
            print(f"  2. Run load tests to validate improvements")
            print(f"  3. Schedule regular maintenance (weekly VACUUM ANALYZE)")
            print(f"  4. Consider pg_stat_statements for query monitoring")

            logger.info("✅ Database optimization completed successfully!")
            break  # Only use first session

    except Exception as e:
        logger.error(f"❌ Optimization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())