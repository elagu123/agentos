"""
Base Agent Class for AgentOS Specialized Agents

Provides the foundational framework for all specialized agents including
capabilities system, context management, and execution framework.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import time
import uuid
import asyncio
from datetime import datetime

from app.core.multi_llm_router import llm_router, TaskType
from app.core.memory_manager import memory_manager
from app.core.embeddings import embedding_manager
from app.models.organization import Organization
from app.models.business_context import BusinessContext


class AgentCapability(Enum):
    """Available agent capabilities"""
    TEXT_GENERATION = "text_generation"
    DATA_ANALYSIS = "data_analysis"
    WEB_SEARCH = "web_search"
    EMAIL_PROCESSING = "email_processing"
    CALENDAR_MANAGEMENT = "calendar_management"
    FILE_PROCESSING = "file_processing"
    API_INTEGRATION = "api_integration"
    WORKFLOW_AUTOMATION = "workflow_automation"
    CONTENT_OPTIMIZATION = "content_optimization"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    SCHEDULING = "scheduling"
    RESEARCH = "research"
    COPYWRITING = "copywriting"


@dataclass
class AgentContext:
    """Context information for agent execution"""
    organization_id: str
    user_id: str
    session_id: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    business_context: Optional[Dict[str, Any]] = None
    task_context: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    """Configuration for specialized agents"""
    name: str
    description: str
    capabilities: List[AgentCapability]
    model_preferences: Dict[str, str] = field(default_factory=dict)
    max_tokens: int = 2000
    temperature: float = 0.7
    timeout: int = 30
    retry_attempts: int = 3
    custom_instructions: str = ""
    tools: List[str] = field(default_factory=list)


@dataclass
class AgentResponse:
    """Response from agent execution"""
    agent_name: str
    response: str
    confidence: float
    sources: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    tokens_used: int = 0
    cost: float = 0.0
    timestamp: float = field(default_factory=time.time)


class BaseAgent(ABC):
    """
    Abstract base class for all specialized agents in AgentOS.

    Provides the core functionality including:
    - Capability management
    - Context processing
    - LLM interaction
    - Memory management
    - Error handling and retry logic
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.capabilities = set(config.capabilities)
        self.execution_count = 0
        self.total_execution_time = 0.0
        self.last_execution = None
        self._tools = {}
        self._initialize_tools()

    def _initialize_tools(self):
        """Initialize agent-specific tools"""
        for tool_name in self.config.tools:
            tool_func = self._get_tool_function(tool_name)
            if tool_func:
                self._tools[tool_name] = tool_func

    def _get_tool_function(self, tool_name: str) -> Optional[Callable]:
        """Get tool function by name (to be overridden by subclasses)"""
        return None

    async def execute(
        self,
        task: str,
        context: AgentContext,
        **kwargs
    ) -> AgentResponse:
        """
        Execute a task with the given context.

        Args:
            task: The task description
            context: Execution context
            **kwargs: Additional parameters

        Returns:
            AgentResponse with the execution result
        """
        start_time = time.time()
        execution_id = str(uuid.uuid4())

        try:
            # Pre-execution validation
            await self._validate_execution_context(task, context)

            # Process business context
            enhanced_context = await self._enhance_context(context)

            # Execute the core task
            response = await self._execute_core_task(task, enhanced_context, **kwargs)

            # Post-process response
            processed_response = await self._post_process_response(response, enhanced_context)

            # Update execution metrics
            execution_time = time.time() - start_time
            self._update_metrics(execution_time)

            # Store in memory if needed
            await self._store_execution_memory(task, processed_response, enhanced_context)

            return AgentResponse(
                agent_name=self.config.name,
                response=processed_response,
                confidence=self._calculate_confidence(processed_response, enhanced_context),
                sources=await self._get_sources(enhanced_context),
                metadata={
                    "execution_id": execution_id,
                    "capabilities_used": list(self.capabilities),
                    "model_used": self._get_preferred_model(TaskType.REAL_TIME_CHAT),
                    **kwargs
                },
                execution_time=execution_time,
                tokens_used=self._estimate_tokens_used(task, processed_response),
                cost=self._estimate_cost(task, processed_response)
            )

        except Exception as e:
            # Handle execution errors
            return await self._handle_execution_error(e, task, context, start_time)

    @abstractmethod
    async def _execute_core_task(
        self,
        task: str,
        context: AgentContext,
        **kwargs
    ) -> str:
        """
        Core task execution logic (must be implemented by subclasses).

        Args:
            task: The task description
            context: Enhanced execution context
            **kwargs: Additional parameters

        Returns:
            Raw response string
        """
        pass

    async def _validate_execution_context(self, task: str, context: AgentContext):
        """Validate that the context has all required information"""
        if not context.organization_id:
            raise ValueError("Organization ID is required")

        if not context.user_id:
            raise ValueError("User ID is required")

        if not task or not task.strip():
            raise ValueError("Task cannot be empty")

    async def _enhance_context(self, context: AgentContext) -> AgentContext:
        """Enhance context with business-specific information"""
        # Retrieve business context from vector store
        if not context.business_context:
            try:
                # Get relevant business context based on the task
                similar_contexts = await embedding_manager.search_similar(
                    query="business context organization information",
                    collection_name=f"org_{context.organization_id}",
                    limit=5
                )

                context.business_context = {
                    "retrieved_contexts": similar_contexts
                }
            except Exception as e:
                # Continue without business context if retrieval fails
                context.business_context = {"error": str(e)}

        # Retrieve conversation history if not provided
        if not context.conversation_history:
            try:
                history = await memory_manager.get_conversation_history(
                    user_id=context.user_id,
                    session_id=context.session_id,
                    limit=10
                )
                context.conversation_history = history
            except Exception:
                context.conversation_history = []

        return context

    async def _post_process_response(self, response: str, context: AgentContext) -> str:
        """Post-process the raw response"""
        # Basic sanitization and formatting
        processed = response.strip()

        # Apply agent-specific post-processing
        processed = await self._apply_agent_specific_processing(processed, context)

        return processed

    async def _apply_agent_specific_processing(self, response: str, context: AgentContext) -> str:
        """Apply agent-specific post-processing (to be overridden)"""
        return response

    def _calculate_confidence(self, response: str, context: AgentContext) -> float:
        """Calculate confidence score for the response"""
        # Basic confidence calculation based on response length and context
        base_confidence = 0.7

        # Increase confidence if we have business context
        if context.business_context and context.business_context.get("retrieved_contexts"):
            base_confidence += 0.1

        # Increase confidence if response is detailed
        if len(response) > 100:
            base_confidence += 0.1

        # Decrease confidence if response is very short
        if len(response) < 50:
            base_confidence -= 0.2

        return min(max(base_confidence, 0.0), 1.0)

    async def _get_sources(self, context: AgentContext) -> List[Dict[str, Any]]:
        """Get sources used for the response"""
        sources = []

        if context.business_context and context.business_context.get("retrieved_contexts"):
            for ctx in context.business_context["retrieved_contexts"]:
                sources.append({
                    "type": "business_context",
                    "content": ctx.get("content", "")[:200] + "...",
                    "source": ctx.get("source", "business_documents"),
                    "score": ctx.get("score", 0.0)
                })

        return sources

    def _update_metrics(self, execution_time: float):
        """Update execution metrics"""
        self.execution_count += 1
        self.total_execution_time += execution_time
        self.last_execution = datetime.now()

    async def _store_execution_memory(
        self,
        task: str,
        response: str,
        context: AgentContext
    ):
        """Store execution in memory for future reference"""
        try:
            await memory_manager.add_message(
                user_id=context.user_id,
                session_id=context.session_id,
                role="user",
                content=task
            )

            await memory_manager.add_message(
                user_id=context.user_id,
                session_id=context.session_id,
                role="assistant",
                content=response,
                metadata={
                    "agent": self.config.name,
                    "capabilities": list(self.capabilities)
                }
            )
        except Exception as e:
            # Continue silently if memory storage fails
            pass

    def _estimate_tokens_used(self, task: str, response: str) -> int:
        """Estimate tokens used in the execution"""
        # Rough estimation: 1 token ≈ 4 characters
        total_chars = len(task) + len(response)
        return total_chars // 4

    def _estimate_cost(self, task: str, response: str) -> float:
        """Estimate cost of the execution"""
        tokens = self._estimate_tokens_used(task, response)
        # Rough cost estimation based on OpenAI pricing
        return tokens * 0.000002  # $0.002 per 1K tokens

    async def _handle_execution_error(
        self,
        error: Exception,
        task: str,
        context: AgentContext,
        start_time: float
    ) -> AgentResponse:
        """Handle execution errors gracefully"""
        execution_time = time.time() - start_time

        error_response = f"I apologize, but I encountered an error while processing your request: {str(error)}"

        return AgentResponse(
            agent_name=self.config.name,
            response=error_response,
            confidence=0.0,
            sources=[],
            metadata={
                "error": str(error),
                "error_type": type(error).__name__
            },
            execution_time=execution_time,
            tokens_used=0,
            cost=0.0
        )

    def _get_preferred_model(self, task_type: TaskType) -> str:
        """Get preferred model for task type"""
        return self.config.model_preferences.get(
            task_type.value,
            "gpt-4o-mini"  # Default model
        )

    async def generate_llm_response(
        self,
        prompt: str,
        task_type: TaskType = TaskType.REAL_TIME_CHAT,
        **kwargs
    ) -> str:
        """Generate response using LLM router"""
        try:
            response = await llm_router.route(
                task_type=task_type,
                prompt=prompt,
                context={
                    "agent": self.config.name,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                    **kwargs
                }
            )
            return response.get("response", "")
        except Exception as e:
            raise RuntimeError(f"LLM generation failed: {str(e)}")

    def has_capability(self, capability: AgentCapability) -> bool:
        """Check if agent has specific capability"""
        return capability in self.capabilities

    def get_metrics(self) -> Dict[str, Any]:
        """Get agent execution metrics"""
        avg_execution_time = (
            self.total_execution_time / self.execution_count
            if self.execution_count > 0 else 0.0
        )

        return {
            "execution_count": self.execution_count,
            "total_execution_time": round(self.total_execution_time, 3),
            "average_execution_time": round(avg_execution_time, 3),
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
            "capabilities": [cap.value for cap in self.capabilities]
        }

    async def test_capabilities(self) -> Dict[str, bool]:
        """Test all agent capabilities"""
        results = {}

        for capability in self.capabilities:
            try:
                # Create a simple test task for each capability
                test_task = f"Test {capability.value} capability"
                test_context = AgentContext(
                    organization_id="test",
                    user_id="test",
                    session_id="test"
                )

                # Execute a minimal test
                response = await self._execute_core_task(test_task, test_context)
                results[capability.value] = len(response) > 0

            except Exception:
                results[capability.value] = False

        return results

    def __str__(self) -> str:
        return f"{self.config.name} ({len(self.capabilities)} capabilities)"

    def __repr__(self) -> str:
        return f"BaseAgent(name='{self.config.name}', capabilities={list(self.capabilities)})"