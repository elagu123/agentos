from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Agent
from app.schemas import AgentSummary
from app.utils import require_organization_member, raise_not_found

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/", response_model=List[AgentSummary])
async def list_organization_agents(
    current_user: User = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db)
):
    """List all agents for the current organization"""
    result = await db.execute(
        select(Agent)
        .where(Agent.organization_id == current_user.organization_id)
        .order_by(Agent.created_at.desc())
    )
    agents = result.scalars().all()

    return [
        AgentSummary(
            id=agent.id,
            name=agent.name,
            type=agent.type,
            status=agent.status,
            success_rate=agent.success_rate,
            total_executions=agent.total_executions,
            avg_response_time=agent.avg_response_time,
            training_completed=agent.training_completed,
            is_ready=agent.is_ready,
            created_at=agent.created_at
        )
        for agent in agents
    ]


@router.get("/{agent_id}", response_model=AgentSummary)
async def get_agent(
    agent_id: UUID,
    current_user: User = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db)
):
    """Get specific agent details"""
    result = await db.execute(
        select(Agent)
        .where(
            Agent.id == agent_id,
            Agent.organization_id == current_user.organization_id
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise_not_found("Agent not found")

    return AgentSummary(
        id=agent.id,
        name=agent.name,
        type=agent.type,
        status=agent.status,
        success_rate=agent.success_rate,
        total_executions=agent.total_executions,
        avg_response_time=agent.avg_response_time,
        training_completed=agent.training_completed,
        is_ready=agent.is_ready,
        created_at=agent.created_at
    )