"""
API endpoints for specialized agents
"""

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
import asyncio
from datetime import datetime

from app.utils.clerk_auth import get_current_user, require_permission
from app.database import get_db
from app.models.user import User
from app.models.organization import Organization
from sqlalchemy import select
from app.agents import (
    BaseAgent, AgentCapability, AgentContext, AgentConfig,
    CopywriterAgent, ResearcherAgent, SchedulerAgent,
    EmailResponderAgent, DataAnalyzerAgent
)

router = APIRouter(prefix="/specialized-agents", tags=["specialized-agents"])
security = HTTPBearer()


# Request/Response Models
class AgentRequest(BaseModel):
    task: str = Field(..., description="Task description for the agent")
    agent_type: str = Field(..., description="Type of agent to use")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Agent-specific parameters")


class AgentResponse(BaseModel):
    agent_name: str
    response: str
    confidence: float
    sources: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    execution_time: float
    tokens_used: int
    cost: float
    timestamp: float


class BatchAgentRequest(BaseModel):
    tasks: List[Dict[str, Any]] = Field(..., description="List of tasks for batch processing")
    agent_type: str = Field(..., description="Type of agent to use")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Shared context")


class AgentCapabilityResponse(BaseModel):
    agent_type: str
    capabilities: List[str]
    description: str
    available: bool


class AgentMetricsResponse(BaseModel):
    agent_type: str
    execution_count: int
    total_execution_time: float
    average_execution_time: float
    last_execution: Optional[str]
    capabilities: List[str]


# Agent Manager
class SpecializedAgentManager:
    """Manager for specialized agents"""

    def __init__(self):
        self._agents = {
            "copywriter": CopywriterAgent(),
            "researcher": ResearcherAgent(),
            "scheduler": SchedulerAgent(),
            "email_responder": EmailResponderAgent(),
            "data_analyzer": DataAnalyzerAgent()
        }

    def get_agent(self, agent_type: str) -> BaseAgent:
        """Get agent by type"""
        agent = self._agents.get(agent_type.lower())
        if not agent:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown agent type: {agent_type}. Available types: {list(self._agents.keys())}"
            )
        return agent

    def get_available_agents(self) -> Dict[str, BaseAgent]:
        """Get all available agents"""
        return self._agents

    async def execute_task(
        self,
        agent_type: str,
        task: str,
        context: AgentContext,
        **kwargs
    ) -> AgentResponse:
        """Execute task with specified agent"""
        agent = self.get_agent(agent_type)
        result = await agent.execute(task, context, **kwargs)
        return result


# Global agent manager instance
agent_manager = SpecializedAgentManager()


@router.get("/", response_model=List[AgentCapabilityResponse])
async def list_available_agents(
    current_user: User = Depends(get_current_user)
):
    """List all available specialized agents and their capabilities"""

    agents_info = []

    for agent_type, agent in agent_manager.get_available_agents().items():
        agents_info.append(AgentCapabilityResponse(
            agent_type=agent_type,
            capabilities=[cap.value for cap in agent.capabilities],
            description=agent.config.description,
            available=True
        ))

    return agents_info


@router.post("/{agent_type}/execute", response_model=AgentResponse)
async def execute_agent_task(
    agent_type: str,
    request: AgentRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Execute a task with a specific specialized agent"""

    try:
        # Get user's organization
        organization = await db.execute(
            select(Organization).where(Organization.id == current_user.organization_id)
        )
        organization = organization.scalar_one_or_none()

        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Create agent context
        context = AgentContext(
            organization_id=str(organization.id),
            user_id=str(current_user.id),
            session_id=f"api_session_{datetime.now().timestamp()}",
            task_context=request.context,
            metadata={"api_request": True, "user_role": current_user.role}
        )

        # Execute task
        result = await agent_manager.execute_task(
            agent_type=agent_type,
            task=request.task,
            context=context,
            **(request.parameters or {})
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")


@router.post("/{agent_type}/batch", response_model=List[AgentResponse])
async def execute_batch_tasks(
    agent_type: str,
    request: BatchAgentRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Execute multiple tasks with a specialized agent in batch"""

    try:
        # Get user's organization
        organization = await db.execute(
            select(Organization).where(Organization.id == current_user.organization_id)
        )
        organization = organization.scalar_one_or_none()

        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Validate batch size
        if len(request.tasks) > 50:  # Limit batch size
            raise HTTPException(status_code=400, detail="Batch size exceeds maximum limit of 50 tasks")

        # Create shared context
        base_context = AgentContext(
            organization_id=str(organization.id),
            user_id=str(current_user.id),
            session_id=f"batch_session_{datetime.now().timestamp()}",
            task_context=request.context,
            metadata={"api_request": True, "batch_processing": True}
        )

        # Execute tasks concurrently
        tasks = []
        for i, task_data in enumerate(request.tasks):
            task_context = AgentContext(
                organization_id=base_context.organization_id,
                user_id=base_context.user_id,
                session_id=f"{base_context.session_id}_task_{i}",
                task_context={**(base_context.task_context or {}), **task_data.get("context", {})},
                metadata={**base_context.metadata, "task_index": i}
            )

            task_coro = agent_manager.execute_task(
                agent_type=agent_type,
                task=task_data["task"],
                context=task_context,
                **task_data.get("parameters", {})
            )
            tasks.append(task_coro)

        # Execute with timeout
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=300  # 5 minute timeout for batch
        )

        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Create error response
                processed_results.append(AgentResponse(
                    agent_name=f"{agent_type}_agent",
                    response=f"Task failed: {str(result)}",
                    confidence=0.0,
                    sources=[],
                    metadata={"error": True, "task_index": i},
                    execution_time=0.0,
                    tokens_used=0,
                    cost=0.0,
                    timestamp=datetime.now().timestamp()
                ))
            else:
                processed_results.append(result)

        return processed_results

    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Batch processing timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch execution failed: {str(e)}")


@router.get("/{agent_type}/capabilities", response_model=AgentCapabilityResponse)
async def get_agent_capabilities(
    agent_type: str,
    current_user: User = Depends(get_current_user)
):
    """Get capabilities of a specific agent"""

    try:
        agent = agent_manager.get_agent(agent_type)

        return AgentCapabilityResponse(
            agent_type=agent_type,
            capabilities=[cap.value for cap in agent.capabilities],
            description=agent.config.description,
            available=True
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get capabilities: {str(e)}")


@router.get("/{agent_type}/metrics", response_model=AgentMetricsResponse)
async def get_agent_metrics(
    agent_type: str,
    current_user: User = Depends(get_current_user)
):
    """Get performance metrics for a specific agent"""

    try:
        agent = agent_manager.get_agent(agent_type)
        metrics = agent.get_metrics()

        return AgentMetricsResponse(
            agent_type=agent_type,
            execution_count=metrics["execution_count"],
            total_execution_time=metrics["total_execution_time"],
            average_execution_time=metrics["average_execution_time"],
            last_execution=metrics["last_execution"],
            capabilities=metrics["capabilities"]
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.post("/{agent_type}/test", response_model=Dict[str, bool])
async def test_agent_capabilities(
    agent_type: str,
    current_user: User = Depends(get_current_user)
):
    """Test all capabilities of a specific agent"""

    try:
        agent = agent_manager.get_agent(agent_type)
        test_results = await agent.test_capabilities()

        return test_results

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Capability testing failed: {str(e)}")


# Specialized endpoints for each agent type

@router.post("/copywriter/variations")
async def create_content_variations(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Create multiple variations of content for A/B testing"""

    try:
        agent = agent_manager.get_agent("copywriter")
        base_content = request.get("content", "")
        variation_count = request.get("variation_count", 3)

        context = AgentContext(
            organization_id=str(current_user.organization_id),
            user_id=str(current_user.id),
            session_id=f"variations_{datetime.now().timestamp()}"
        )

        variations = await agent.create_content_variations(
            base_content, variation_count, context
        )

        return {"variations": variations}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Content variation failed: {str(e)}")


@router.post("/researcher/competitive-analysis")
async def conduct_competitive_analysis(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Conduct detailed competitive analysis"""

    try:
        agent = agent_manager.get_agent("researcher")
        company_name = request.get("company_name", "")
        industry = request.get("industry", "")

        context = AgentContext(
            organization_id=str(current_user.organization_id),
            user_id=str(current_user.id),
            session_id=f"competitive_analysis_{datetime.now().timestamp()}"
        )

        analysis = await agent.conduct_competitive_analysis(
            company_name, industry, context
        )

        return analysis

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Competitive analysis failed: {str(e)}")


@router.post("/email-responder/batch-process")
async def process_email_batch(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Process multiple emails in batch"""

    try:
        agent = agent_manager.get_agent("email_responder")
        emails = request.get("emails", [])

        context = AgentContext(
            organization_id=str(current_user.organization_id),
            user_id=str(current_user.id),
            session_id=f"email_batch_{datetime.now().timestamp()}"
        )

        # Convert email dicts to EmailData objects
        from app.agents.email_responder_agent import EmailData
        email_objects = []

        for email_dict in emails:
            email_objects.append(EmailData(
                subject=email_dict.get("subject", ""),
                sender=email_dict.get("sender", ""),
                recipients=email_dict.get("recipients", []),
                body=email_dict.get("body", ""),
                timestamp=datetime.fromisoformat(email_dict.get("timestamp", datetime.now().isoformat())),
                attachments=email_dict.get("attachments", [])
            ))

        results = await agent.process_email_batch(email_objects, context)

        return {"processed_emails": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email batch processing failed: {str(e)}")


@router.post("/data-analyzer/dashboard")
async def create_dashboard_summary(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Create dashboard summary with key metrics"""

    try:
        agent = agent_manager.get_agent("data_analyzer")

        context = AgentContext(
            organization_id=str(current_user.organization_id),
            user_id=str(current_user.id),
            session_id=f"dashboard_{datetime.now().timestamp()}"
        )

        # In production, this would load real data
        # For now, use the agent's sample data generation
        data = {"business_metrics": await agent._generate_sample_data(context)}

        dashboard = await agent.create_dashboard_summary(data, context)

        return dashboard

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard creation failed: {str(e)}")


# Add to main router
def include_specialized_agents_router(app):
    """Include specialized agents router in main app"""
    app.include_router(router)