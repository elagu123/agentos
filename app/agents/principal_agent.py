"""
Principal Agent - The main business representative agent with full business context.
"""
from typing import Dict, Any, Optional
from app.agents.base_agent import BaseAgent, AgentConfig, AgentCapability, AgentContext
from app.models.organization import Organization
from app.core.multi_llm_router import TaskType


class PrincipalAgent(BaseAgent):
    """
    Principal Agent that serves as the main business representative.

    This agent has access to:
    - Full business context from uploaded documents
    - Organization-specific information
    - Previous conversation history
    - All available capabilities
    """

    def __init__(self, organization: Organization):
        self.organization = organization

        config = AgentConfig(
            name="Principal Agent",
            description=f"Main business representative agent for {organization.name}",
            capabilities=[
                AgentCapability.TEXT_GENERATION,
                AgentCapability.DATA_ANALYSIS,
                AgentCapability.RESEARCH,
                AgentCapability.CONTENT_OPTIMIZATION,
                AgentCapability.SENTIMENT_ANALYSIS,
                AgentCapability.WORKFLOW_AUTOMATION
            ],
            model_preferences={
                TaskType.REALTIME_CHAT.value: "gpt-4o-mini",
                TaskType.COMPLEX_REASONING.value: "gpt-4o",
                TaskType.BULK_PROCESSING.value: "gpt-3.5-turbo"
            },
            temperature=0.7,
            max_tokens=2000,
            custom_instructions=self._build_system_prompt()
        )

        super().__init__(config)

    def _build_system_prompt(self) -> str:
        """Build a comprehensive system prompt based on organization context."""

        base_prompt = f"""You are the Principal Agent for {self.organization.name}, an AI assistant with deep knowledge about this business.

BUSINESS CONTEXT:
- Organization: {self.organization.name}
- Industry: {self.organization.industry}
- Size: {self.organization.size_range}
- Description: {self.organization.description or 'Not provided'}

YOUR ROLE:
You are the primary AI representative for this business. You have access to:
- Business documents and context via RAG system
- Previous conversations and interactions
- Ability to coordinate with specialized agents when needed

CAPABILITIES:
- Answer questions about the business
- Help with content creation and optimization
- Analyze data and provide insights
- Assist with workflow automation
- Provide strategic recommendations
- Help with customer service scenarios

COMMUNICATION STYLE:
- Professional but friendly
- Knowledgeable about the business context
- Proactive in suggesting solutions
- Clear and actionable responses
- Always consider the business context in your responses

When you don't have specific information, be honest about it and suggest ways to get the information or how specialized agents could help."""

        return base_prompt

    async def _execute_core_task(
        self,
        task: str,
        context: AgentContext,
        **kwargs
    ) -> str:
        """
        Execute the core chat task with business context.
        """

        # Build enhanced prompt with business context
        enhanced_prompt = self._build_enhanced_prompt(task, context)

        # Generate response using LLM router
        response = await self.generate_llm_response(
            prompt=enhanced_prompt,
            task_type=TaskType.REALTIME_CHAT,
            **kwargs
        )

        return response

    def _build_enhanced_prompt(self, task: str, context: AgentContext) -> str:
        """Build an enhanced prompt with business context and conversation history."""

        # Start with system prompt
        prompt_parts = [self.config.custom_instructions]

        # Add conversation history if available
        if context.conversation_history:
            prompt_parts.append("\nRECENT CONVERSATION HISTORY:")
            for msg in context.conversation_history[-5:]:  # Last 5 messages
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                prompt_parts.append(f"{role.upper()}: {content}")

        # Add business context from RAG if available
        if context.business_context and context.business_context.get('retrieved_contexts'):
            prompt_parts.append("\nRELEVANT BUSINESS CONTEXT:")
            for ctx in context.business_context['retrieved_contexts']:
                content = ctx.get('content', '')[:300]  # Limit context length
                source = ctx.get('source', 'business_documents')
                prompt_parts.append(f"From {source}: {content}")

        # Add current task context if provided
        if context.task_context:
            prompt_parts.append(f"\nTASK CONTEXT: {context.task_context}")

        # Add the current user request
        prompt_parts.append(f"\nUSER REQUEST: {task}")

        # Add instruction for response
        prompt_parts.append("""
INSTRUCTIONS:
- Provide a helpful, contextual response based on the business knowledge available
- If you reference business context, be specific about what information you're using
- If you don't have enough context, suggest ways to get more information
- Keep responses clear, actionable, and professional
- Always consider how your response can help this specific business

RESPONSE:""")

        return "\n".join(prompt_parts)

    async def _apply_agent_specific_processing(self, response: str, context: AgentContext) -> str:
        """Apply Principal Agent specific post-processing."""

        # Basic formatting and cleanup
        processed = response.strip()

        # Ensure response maintains professional tone
        if not processed:
            processed = "I apologize, but I wasn't able to generate a proper response. Could you please rephrase your question or provide more context?"

        return processed

    def _calculate_confidence(self, response: str, context: AgentContext) -> float:
        """Calculate confidence score for Principal Agent responses."""

        base_confidence = 0.8  # Higher base for principal agent

        # Increase confidence if we have business context
        if context.business_context and context.business_context.get('retrieved_contexts'):
            num_contexts = len(context.business_context['retrieved_contexts'])
            base_confidence += min(0.15, num_contexts * 0.03)

        # Increase confidence if we have conversation history
        if context.conversation_history:
            base_confidence += 0.05

        # Adjust based on response quality
        if len(response) > 200:  # Detailed response
            base_confidence += 0.05
        elif len(response) < 50:  # Very short response
            base_confidence -= 0.1

        # Check for uncertainty indicators
        uncertainty_phrases = [
            "i don't know", "i'm not sure", "i can't help",
            "i don't have", "unclear", "uncertain"
        ]

        if any(phrase in response.lower() for phrase in uncertainty_phrases):
            base_confidence -= 0.2

        return min(max(base_confidence, 0.0), 1.0)

    async def get_business_summary(self) -> Dict[str, Any]:
        """Get a summary of the business context available to this agent."""

        return {
            "organization": {
                "name": self.organization.name,
                "industry": self.organization.industry,
                "size": self.organization.size_range,
                "description": self.organization.description
            },
            "capabilities": [cap.value for cap in self.capabilities],
            "agent_status": "ready",
            "context_available": True  # TODO: Check if business context is actually loaded
        }