"""
Chat API endpoints for Principal Agent interactions.
"""
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.core.auth import get_current_user
from app.agents.base_agent import AgentContext, AgentResponse
from app.core.multi_llm_router import TaskType
from app.core.memory_manager import memory_manager

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str = Field(default="main")
    include_sources: bool = Field(default=True)
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    response: str
    confidence: float
    sources: List[Dict[str, Any]]
    execution_time: float
    tokens_used: int
    cost: float
    conversation_id: str
    timestamp: str


@router.post("/principal/chat", response_model=ChatResponse)
async def chat_with_principal_agent(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Chat with the Principal Agent using business context.
    """
    try:
        # Get user's organization
        organization = db.query(Organization).filter(
            Organization.id == current_user.organization_id
        ).first()

        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Create agent context
        context = AgentContext(
            organization_id=str(organization.id),
            user_id=str(current_user.id),
            session_id=request.conversation_id,
            task_context=request.context or {}
        )

        # Import and create principal agent
        from app.agents.principal_agent import PrincipalAgent

        agent = PrincipalAgent(organization=organization)

        # Execute chat
        response: AgentResponse = await agent.execute(
            task=request.message,
            context=context
        )

        # Store conversation in memory
        await memory_manager.add_message(
            user_id=str(current_user.id),
            session_id=request.conversation_id,
            role="user",
            content=request.message
        )

        await memory_manager.add_message(
            user_id=str(current_user.id),
            session_id=request.conversation_id,
            role="assistant",
            content=response.response,
            metadata={
                "agent": "principal",
                "confidence": response.confidence,
                "tokens_used": response.tokens_used,
                "cost": response.cost
            }
        )

        return ChatResponse(
            response=response.response,
            confidence=response.confidence,
            sources=response.sources if request.include_sources else [],
            execution_time=response.execution_time,
            tokens_used=response.tokens_used,
            cost=response.cost,
            conversation_id=request.conversation_id,
            timestamp=response.timestamp
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(e)}"
        )


@router.get("/principal/conversation/{conversation_id}")
async def get_conversation_history(
    conversation_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """
    Get conversation history for a specific conversation.
    """
    try:
        history = await memory_manager.get_conversation_history(
            user_id=str(current_user.id),
            session_id=conversation_id,
            limit=limit
        )

        return {
            "conversation_id": conversation_id,
            "messages": history,
            "count": len(history)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get conversation history: {str(e)}"
        )


@router.delete("/principal/conversation/{conversation_id}")
async def clear_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Clear conversation history for a specific conversation.
    """
    try:
        # Clear conversation from memory
        await memory_manager.clear_conversation(
            user_id=str(current_user.id),
            session_id=conversation_id
        )

        return {
            "message": "Conversation cleared successfully",
            "conversation_id": conversation_id
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear conversation: {str(e)}"
        )


@router.get("/principal/status")
async def get_principal_agent_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get status and capabilities of the Principal Agent.
    """
    try:
        organization = db.query(Organization).filter(
            Organization.id == current_user.organization_id
        ).first()

        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Import and create principal agent
        from app.agents.principal_agent import PrincipalAgent

        agent = PrincipalAgent(organization=organization)

        return {
            "agent_name": agent.config.name,
            "status": "ready",
            "capabilities": [cap.value for cap in agent.capabilities],
            "organization": organization.name,
            "business_context_available": True,  # TODO: Check if context is loaded
            "metrics": agent.get_metrics()
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent status: {str(e)}"
        )