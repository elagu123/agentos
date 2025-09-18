"""
Database performance optimization utilities for AgentOS.

This module provides tools for:
- Creating performance indexes
- Query optimization
- Batch operations
- Database statistics updates
"""
from sqlalchemy import text, Index, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.dialects.postgresql import insert
from typing import List, Dict, Any, Optional
import structlog
from datetime import datetime, timedelta

from app.database import get_db

logger = structlog.get_logger(__name__)


class DatabaseOptimizer:
    """
    Database performance optimization utilities.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_performance_indexes(self):
        """
        Create all necessary indexes for optimal performance.

        This creates indexes for the most common query patterns in AgentOS:
        - Organization-based filtering
        - Workflow execution tracking
        - Message/conversation queries
        - Agent activity monitoring
        - Template marketplace queries
        """
        indexes = [
            # High-frequency organization-based queries
            {
                "name": "idx_workflows_org_status",
                "sql": """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workflows_org_status
                ON workflows(organization_id, status)
                WHERE deleted_at IS NULL
                """,
                "description": "Optimize workflow queries by organization and status"
            },

            {
                "name": "idx_agents_org_type",
                "sql": """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agents_org_type
                ON agents(organization_id, agent_type)
                WHERE is_active = true
                """,
                "description": "Optimize active agent queries by organization"
            },

            # Conversation and messaging performance
            {
                "name": "idx_messages_conv_created",
                "sql": """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_conv_created
                ON messages(conversation_id, created_at DESC)
                """,
                "description": "Optimize conversation history retrieval"
            },

            {
                "name": "idx_conversations_user_updated",
                "sql": """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_user_updated
                ON conversations(user_id, updated_at DESC)
                """,
                "description": "Optimize user conversation listing"
            },

            # RAG and document search optimization
            {
                "name": "idx_documents_org_embedded",
                "sql": """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_org_embedded
                ON documents(organization_id)
                WHERE embedding IS NOT NULL
                """,
                "description": "Optimize document search by organization"
            },

            {
                "name": "idx_document_chunks_doc_created",
                "sql": """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_chunks_doc_created
                ON document_chunks(document_id, created_at)
                """,
                "description": "Optimize document chunk retrieval"
            },

            # Workflow execution performance
            {
                "name": "idx_executions_workflow_created",
                "sql": """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_executions_workflow_created
                ON workflow_executions(workflow_id, created_at DESC)
                """,
                "description": "Optimize workflow execution history"
            },

            {
                "name": "idx_executions_status_created",
                "sql": """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_executions_status_created
                ON workflow_executions(status, created_at DESC)
                """,
                "description": "Optimize execution monitoring by status"
            },

            # User activity and analytics
            {
                "name": "idx_activities_user_created",
                "sql": """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activities_user_created
                ON user_activities(user_id, created_at DESC)
                """,
                "description": "Optimize user activity tracking"
            },

            {
                "name": "idx_activities_org_type_created",
                "sql": """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activities_org_type_created
                ON user_activities(organization_id, activity_type, created_at DESC)
                """,
                "description": "Optimize organization analytics"
            },

            # Template marketplace performance
            {
                "name": "idx_templates_rating_public",
                "sql": """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_templates_rating_public
                ON workflow_templates(average_rating DESC, download_count DESC)
                WHERE is_public = true AND status = 'approved'
                """,
                "description": "Optimize marketplace template browsing"
            },

            {
                "name": "idx_templates_category_rating",
                "sql": """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_templates_category_rating
                ON workflow_templates(category, average_rating DESC)
                WHERE is_public = true
                """,
                "description": "Optimize template category filtering"
            },

            # Authentication and session management
            {
                "name": "idx_users_clerk_id",
                "sql": """
                CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_users_clerk_id
                ON users(clerk_id)
                """,
                "description": "Optimize user authentication lookups"
            },

            {
                "name": "idx_organizations_slug",
                "sql": """
                CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_organizations_slug
                ON organizations(slug)
                """,
                "description": "Optimize organization slug lookups"
            },

            # Performance monitoring
            {
                "name": "idx_performance_metrics_created",
                "sql": """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_created
                ON performance_metrics(created_at DESC)
                """,
                "description": "Optimize performance metric queries"
            }
        ]

        created_count = 0
        for index_config in indexes:
            try:
                await self.session.execute(text(index_config["sql"]))
                await self.session.commit()
                logger.info(f"✅ Index created: {index_config['name']} - {index_config['description']}")
                created_count += 1
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.debug(f"🔍 Index already exists: {index_config['name']}")
                else:
                    logger.warning(f"❌ Failed to create index {index_config['name']}: {e}")
                await self.session.rollback()

        logger.info(f"📊 Database optimization complete: {created_count} indexes processed")

    async def analyze_and_vacuum(self):
        """
        Run ANALYZE and VACUUM for query planner optimization.

        This updates table statistics that PostgreSQL uses to generate
        optimal query execution plans.
        """
        tables = [
            "workflows", "agents", "messages", "conversations", "documents",
            "document_chunks", "workflow_executions", "user_activities",
            "workflow_templates", "users", "organizations", "performance_metrics"
        ]

        for table in tables:
            try:
                # Update table statistics
                await self.session.execute(text(f"ANALYZE {table}"))
                logger.debug(f"📈 Analyzed table: {table}")

                # Vacuum for space reclamation (non-blocking)
                await self.session.execute(text(f"VACUUM (ANALYZE) {table}"))
                logger.debug(f"🧹 Vacuumed table: {table}")

            except Exception as e:
                logger.warning(f"Failed to analyze/vacuum {table}: {e}")

        await self.session.commit()
        logger.info("📊 Database statistics updated and space optimized")

    async def get_query_performance_stats(self) -> Dict[str, Any]:
        """
        Get database performance statistics.

        Returns information about:
        - Most expensive queries
        - Index usage
        - Cache hit rates
        - Connection statistics
        """
        try:
            # Get cache hit ratio
            cache_hit_ratio = await self.session.execute(text("""
                SELECT
                    round(
                        100 * sum(blks_hit) / (sum(blks_hit) + sum(blks_read)), 2
                    ) as cache_hit_ratio
                FROM pg_stat_database
                WHERE datname = current_database()
            """))
            cache_ratio = cache_hit_ratio.scalar() or 0

            # Get index usage stats
            index_usage = await self.session.execute(text("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan as times_used,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
                FROM pg_stat_user_indexes
                ORDER BY idx_scan DESC
                LIMIT 10
            """))

            # Get slow queries (if pg_stat_statements is available)
            try:
                slow_queries = await self.session.execute(text("""
                    SELECT
                        query,
                        calls,
                        total_time,
                        mean_time,
                        rows
                    FROM pg_stat_statements
                    ORDER BY mean_time DESC
                    LIMIT 5
                """))
                slow_query_data = [dict(row) for row in slow_queries]
            except Exception:
                slow_query_data = []

            return {
                "cache_hit_ratio": cache_ratio,
                "index_usage": [dict(row) for row in index_usage],
                "slow_queries": slow_query_data,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get performance stats: {e}")
            return {"error": str(e)}


class QueryOptimizer:
    """
    Optimized query patterns for common operations.

    This class provides pre-optimized query patterns that use proper
    eager loading, indexing, and other performance optimizations.
    """

    @staticmethod
    def workflow_with_relations():
        """
        Eager load all workflow relations in one query.

        This prevents N+1 query problems when accessing workflow
        relationships like agents, executions, and organization.
        """
        from app.models.workflow import Workflow

        return (
            select(Workflow)
            .options(
                selectinload(Workflow.agents),
                selectinload(Workflow.executions),
                joinedload(Workflow.organization)
            )
        )

    @staticmethod
    def agent_with_recent_messages(limit: int = 10):
        """
        Load agent with recent messages efficiently.

        Uses selectinload to avoid N+1 queries and limits
        the number of messages loaded.
        """
        from app.models.agent import Agent
        from app.models.message import Message

        return (
            select(Agent)
            .options(
                selectinload(Agent.messages.limit(limit))
            )
        )

    @staticmethod
    def user_dashboard_data():
        """
        Optimized query for user dashboard data.

        Loads user with organization, recent workflows, and agents
        in a single optimized query.
        """
        from app.models.user import User

        return (
            select(User)
            .options(
                joinedload(User.organization),
                selectinload(User.workflows.limit(5)),
                selectinload(User.agents.limit(10))
            )
        )

    @staticmethod
    async def bulk_insert_documents(session: AsyncSession, documents: List[Dict]):
        """
        Bulk insert documents efficiently using PostgreSQL UPSERT.

        This is much faster than individual INSERT statements
        for large batches of documents.
        """
        from app.models.document import Document

        try:
            stmt = insert(Document).values(documents)
            stmt = stmt.on_conflict_do_update(
                index_elements=['id'],
                set_={
                    'content': stmt.excluded.content,
                    'metadata': stmt.excluded.metadata,
                    'updated_at': stmt.excluded.updated_at
                }
            )

            result = await session.execute(stmt)
            await session.commit()

            logger.info(f"📝 Bulk inserted {len(documents)} documents")
            return result.rowcount

        except Exception as e:
            await session.rollback()
            logger.error(f"Bulk insert failed: {e}")
            raise

    @staticmethod
    async def bulk_update_workflow_status(
        session: AsyncSession,
        workflow_ids: List[str],
        status: str
    ):
        """
        Bulk update workflow statuses efficiently.
        """
        from app.models.workflow import Workflow

        try:
            stmt = text("""
                UPDATE workflows
                SET status = :status, updated_at = CURRENT_TIMESTAMP
                WHERE id = ANY(:workflow_ids)
            """)

            result = await session.execute(
                stmt,
                {"status": status, "workflow_ids": workflow_ids}
            )
            await session.commit()

            logger.info(f"📊 Bulk updated {result.rowcount} workflow statuses")
            return result.rowcount

        except Exception as e:
            await session.rollback()
            logger.error(f"Bulk update failed: {e}")
            raise

    @staticmethod
    async def get_organization_analytics(
        session: AsyncSession,
        org_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get comprehensive organization analytics with a single optimized query.
        """
        from app.models.user_activity import UserActivity
        from app.models.workflow_execution import WorkflowExecution

        try:
            # Single query for multiple metrics
            result = await session.execute(text("""
                WITH date_range AS (
                    SELECT CURRENT_DATE - INTERVAL '%s days' as start_date
                ),
                workflow_stats AS (
                    SELECT
                        COUNT(*) as total_executions,
                        COUNT(*) FILTER (WHERE status = 'completed') as completed,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed,
                        AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) as avg_duration
                    FROM workflow_executions we
                    JOIN workflows w ON we.workflow_id = w.id
                    WHERE w.organization_id = :org_id
                    AND we.created_at >= (SELECT start_date FROM date_range)
                ),
                activity_stats AS (
                    SELECT
                        COUNT(*) as total_activities,
                        COUNT(DISTINCT user_id) as active_users
                    FROM user_activities ua
                    WHERE ua.organization_id = :org_id
                    AND ua.created_at >= (SELECT start_date FROM date_range)
                )
                SELECT
                    ws.*,
                    ast.total_activities,
                    ast.active_users
                FROM workflow_stats ws, activity_stats ast
            """ % days), {"org_id": org_id})

            row = result.fetchone()
            if row:
                return {
                    "total_executions": row.total_executions or 0,
                    "completed_executions": row.completed or 0,
                    "failed_executions": row.failed or 0,
                    "success_rate": (row.completed / max(row.total_executions, 1)) * 100,
                    "average_duration_seconds": row.avg_duration or 0,
                    "total_activities": row.total_activities or 0,
                    "active_users": row.active_users or 0,
                    "period_days": days
                }
            else:
                return {
                    "total_executions": 0,
                    "completed_executions": 0,
                    "failed_executions": 0,
                    "success_rate": 0,
                    "average_duration_seconds": 0,
                    "total_activities": 0,
                    "active_users": 0,
                    "period_days": days
                }

        except Exception as e:
            logger.error(f"Analytics query failed: {e}")
            return {"error": str(e)}


# Convenience function for running optimizations
async def optimize_database():
    """
    Run complete database optimization.

    This function can be called during startup or maintenance
    to ensure optimal database performance.
    """
    async for session in get_db():
        optimizer = DatabaseOptimizer(session)

        logger.info("🚀 Starting database optimization...")

        # Create performance indexes
        await optimizer.create_performance_indexes()

        # Update statistics
        await optimizer.analyze_and_vacuum()

        # Get performance report
        stats = await optimizer.get_query_performance_stats()
        logger.info(f"📊 Database performance stats: {stats}")

        logger.info("✅ Database optimization complete!")
        break  # Only use first session