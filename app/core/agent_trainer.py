import time
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from langchain_core.messages import SystemMessage, HumanMessage

from app.models import Agent, BusinessContext, Organization
from app.core.multi_llm_router import llm_router, LLMProvider
from app.core.embeddings import embedding_manager
from app.core.document_processor import document_processor
from app.utils.exceptions import AgentTrainingException


class TestCase:
    """Test case for agent validation"""
    def __init__(self, input_text: str, expected_topics: List[str], context_required: bool = True):
        self.input_text = input_text
        self.expected_topics = expected_topics
        self.context_required = context_required


class ValidationResult:
    """Agent validation result"""
    def __init__(self, passed: bool, score: float, details: Dict[str, Any]):
        self.passed = passed
        self.score = score
        self.details = details


class AgentTrainer:
    """Agent trainer for creating and configuring business-specific agents"""

    def __init__(self):
        self.llm_router = llm_router

    async def train_principal_agent(
        self,
        db: AsyncSession,
        organization_id: str,
        business_context: BusinessContext
    ) -> Agent:
        """
        Train the principal agent for an organization

        Args:
            db: Database session
            organization_id: Organization ID
            business_context: Business context data

        Returns:
            Trained Agent instance
        """
        try:
            # Generate system prompt
            system_prompt = self.generate_system_prompt(business_context)

            # Create RAG configuration
            rag_config = self.create_rag_config(business_context.vector_store_id)

            # Create LLM configuration
            llm_config = self.create_llm_config(business_context)

            # Create tools configuration
            tools_config = self.create_tools_config(business_context)

            # Create memory configuration
            memory_config = self.create_memory_config(business_context)

            # Create agent instance
            agent = Agent(
                organization_id=organization_id,
                name=f"{business_context.business_name} Principal Agent",
                description=f"Principal AI agent for {business_context.business_name}",
                type="principal",
                status="training",
                system_prompt=system_prompt,
                llm_config=llm_config,
                tools_config=tools_config,
                memory_config=memory_config,
                vector_store_collection=f"org_{organization_id}",
                retrieval_config=rag_config,
                response_style=business_context.communication_style,
                max_response_length=business_context.response_length,
                training_started_at=datetime.utcnow()
            )

            # Add to database
            db.add(agent)
            await db.commit()
            await db.refresh(agent)

            # Generate test cases
            test_cases = self.generate_test_cases(business_context)

            # Validate agent
            validation_result = await self.validate_agent(agent, test_cases)

            # Update agent with validation results
            agent.validation_score = validation_result.score
            agent.validation_details = validation_result.details
            agent.training_completed = validation_result.passed
            agent.training_completed_at = datetime.utcnow()
            agent.status = "ready" if validation_result.passed else "error"

            await db.commit()
            await db.refresh(agent)

            return agent

        except Exception as e:
            raise AgentTrainingException(f"Agent training failed: {str(e)}")

    def generate_system_prompt(self, context: BusinessContext) -> str:
        """
        Generate personalized system prompt based on business context

        Args:
            context: Business context

        Returns:
            Generated system prompt
        """
        brand_personality = context.get_brand_personality()

        # Base template
        template = f"""You are the Principal AI Agent for {context.business_name}.

BUSINESS CONTEXT:
- Company: {context.business_name}
- Industry: {context.industry}
- Description: {context.business_description or 'Not specified'}

TARGET AUDIENCE:
{context.target_audience}

PRODUCTS & SERVICES:
"""

        # Add products
        if context.products:
            template += "Products:\n"
            for product in context.products:
                name = product.get('name', 'Unnamed Product')
                description = product.get('description', 'No description')
                template += f"- {name}: {description}\n"

        # Add services
        if context.services:
            template += "Services:\n"
            for service in context.services:
                name = service.get('name', 'Unnamed Service')
                description = service.get('description', 'No description')
                template += f"- {name}: {description}\n"

        # Add value proposition
        if context.value_proposition:
            template += f"\nVALUE PROPOSITION:\n{context.value_proposition}\n"

        # Brand guidelines
        template += f"""
BRAND PERSONALITY:
{brand_personality}

COMMUNICATION GUIDELINES:
- Tone: {context.brand_tone}
- Style: {context.communication_style}
- Response Length: {context.response_length}
- Language: {context.preferred_language}
"""

        # Add brand guidelines if available
        if context.brand_guidelines:
            template += f"\nBRAND GUIDELINES:\n{context.brand_guidelines}\n"

        # Add brand voice if available
        if context.brand_voice:
            template += f"\nBRAND VOICE:\n{context.brand_voice}\n"

        # Add policies
        if context.policies:
            template += "\nIMPORTANT POLICIES:\n"
            for policy_type, policy_content in context.policies.items():
                template += f"- {policy_type.title()}: {policy_content}\n"

        # Add FAQ data
        if context.faq_data:
            template += "\nFREQUENTLY ASKED QUESTIONS:\n"
            for faq in context.faq_data[:10]:  # Limit to first 10 FAQs
                question = faq.get('question', '')
                answer = faq.get('answer', '')
                template += f"Q: {question}\nA: {answer}\n\n"

        # Contact information
        if context.contact_info:
            template += "\nCONTACT INFORMATION:\n"
            for contact_type, contact_value in context.contact_info.items():
                template += f"- {contact_type.title()}: {contact_value}\n"

        # Business hours
        if context.business_hours:
            template += "\nBUSINESS HOURS:\n"
            for day, hours in context.business_hours.items():
                template += f"- {day.title()}: {hours}\n"

        # Core instructions
        template += """
YOUR ROLE:
1. Answer customer questions using the business context and knowledge base
2. Maintain the brand tone and communication style at all times
3. Provide accurate information about products, services, and policies
4. Escalate to human agents when appropriate
5. Always be helpful, professional, and aligned with the business values

IMPORTANT INSTRUCTIONS:
- Use the knowledge base to provide accurate, contextual responses
- Stay within your role as a representative of this business
- Do not make up information not found in the knowledge base
- Always maintain the specified brand tone and communication style
- If you don't know something, admit it and offer to connect them with someone who can help
"""

        # Add escalation triggers
        if context.escalation_triggers:
            template += "\nESCALATE TO HUMAN WHEN:\n"
            for trigger in context.escalation_triggers:
                template += f"- {trigger}\n"

        # Add topics to avoid
        if context.do_not_answer:
            template += "\nDO NOT DISCUSS:\n"
            for topic in context.do_not_answer:
                template += f"- {topic}\n"

        return template

    def create_rag_config(self, vector_store_id: Optional[str]) -> Dict[str, Any]:
        """
        Create RAG (Retrieval-Augmented Generation) configuration

        Args:
            vector_store_id: Vector store collection ID

        Returns:
            RAG configuration dictionary
        """
        return {
            "enabled": vector_store_id is not None,
            "vector_store_collection": vector_store_id,
            "similarity_threshold": 0.7,
            "max_results": 5,
            "include_metadata": True,
            "rerank_results": True,
            "context_window_tokens": 3000
        }

    def create_llm_config(self, context: BusinessContext) -> Dict[str, Any]:
        """
        Create LLM configuration based on business context

        Args:
            context: Business context

        Returns:
            LLM configuration dictionary
        """
        # Determine temperature based on communication style
        temperature_map = {
            "formal": 0.3,
            "professional": 0.5,
            "helpful": 0.7,
            "friendly": 0.8,
            "creative": 0.9
        }

        temperature = temperature_map.get(context.communication_style, 0.7)

        # Determine max tokens based on response length preference
        max_tokens_map = {
            "short": 500,
            "medium": 1000,
            "long": 2000,
            "detailed": 3000
        }

        max_tokens = max_tokens_map.get(context.response_length, 1000)

        return {
            "provider": "openai",  # Default provider
            "model": "gpt-4-turbo-preview",
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": 0.9,
            "frequency_penalty": 0.1,
            "presence_penalty": 0.1
        }

    def create_tools_config(self, context: BusinessContext) -> List[Dict[str, Any]]:
        """
        Create tools configuration

        Args:
            context: Business context

        Returns:
            List of tool configurations
        """
        tools = [
            {
                "name": "knowledge_search",
                "type": "retrieval",
                "description": "Search the business knowledge base",
                "enabled": True,
                "config": {
                    "collection": f"org_{context.organization_id}",
                    "max_results": 5,
                    "threshold": 0.7
                }
            }
        ]

        # Add integration tools based on configured integrations
        if context.integrations_config:
            integrations = context.integrations_config

            if integrations.get("email_integration", {}).get("enabled"):
                tools.append({
                    "name": "email_tool",
                    "type": "integration",
                    "description": "Send emails or manage email communications",
                    "enabled": True,
                    "config": integrations["email_integration"]
                })

            if integrations.get("calendar_integration", {}).get("enabled"):
                tools.append({
                    "name": "calendar_tool",
                    "type": "integration",
                    "description": "Manage calendar and scheduling",
                    "enabled": True,
                    "config": integrations["calendar_integration"]
                })

        return tools

    def create_memory_config(self, context: BusinessContext) -> Dict[str, Any]:
        """
        Create memory configuration

        Args:
            context: Business context

        Returns:
            Memory configuration dictionary
        """
        return {
            "type": "conversation_buffer_window",
            "window_size": 10,
            "max_token_limit": 2000,
            "summarize_old_conversations": True,
            "persist_important_info": True,
            "memory_store": {
                "type": "redis",
                "ttl": 3600  # 1 hour
            }
        }

    def generate_test_cases(self, context: BusinessContext) -> List[TestCase]:
        """
        Generate test cases for agent validation

        Args:
            context: Business context

        Returns:
            List of test cases
        """
        test_cases = []

        # Basic greeting test
        test_cases.append(TestCase(
            input_text="Hello, how can you help me?",
            expected_topics=["greeting", "help", "assistance"],
            context_required=False
        ))

        # Business information test
        test_cases.append(TestCase(
            input_text=f"Tell me about {context.business_name}",
            expected_topics=["business", "company", "information"],
            context_required=True
        ))

        # Product/service inquiry
        if context.products or context.services:
            test_cases.append(TestCase(
                input_text="What products or services do you offer?",
                expected_topics=["products", "services", "offerings"],
                context_required=True
            ))

        # Contact information test
        test_cases.append(TestCase(
            input_text="How can I contact you?",
            expected_topics=["contact", "phone", "email", "address"],
            context_required=True
        ))

        # FAQ test
        if context.faq_data:
            faq = context.faq_data[0]
            test_cases.append(TestCase(
                input_text=faq.get("question", "What are your business hours?"),
                expected_topics=["faq", "information"],
                context_required=True
            ))

        # Brand tone test
        test_cases.append(TestCase(
            input_text="I'm frustrated with my order",
            expected_topics=["support", "order", "concern"],
            context_required=False
        ))

        return test_cases

    async def validate_agent(
        self,
        agent: Agent,
        test_cases: List[TestCase]
    ) -> ValidationResult:
        """
        Validate agent performance with test cases

        Args:
            agent: Agent to validate
            test_cases: List of test cases

        Returns:
            Validation result
        """
        try:
            total_score = 0.0
            results = []

            for i, test_case in enumerate(test_cases):
                try:
                    # Generate response using the agent's configuration
                    response_data = await self._generate_test_response(agent, test_case)

                    # Score the response
                    score = self._score_response(test_case, response_data)

                    total_score += score
                    results.append({
                        "test_case_index": i,
                        "input": test_case.input_text,
                        "response": response_data.get("response", ""),
                        "score": score,
                        "passed": score >= 0.6,
                        "execution_time": response_data.get("execution_time", 0)
                    })

                except Exception as e:
                    results.append({
                        "test_case_index": i,
                        "input": test_case.input_text,
                        "response": "",
                        "score": 0.0,
                        "passed": False,
                        "error": str(e)
                    })

            # Calculate overall score
            average_score = total_score / len(test_cases) if test_cases else 0.0
            passed = average_score >= 0.7

            return ValidationResult(
                passed=passed,
                score=average_score,
                details={
                    "total_tests": len(test_cases),
                    "passed_tests": sum(1 for r in results if r.get("passed", False)),
                    "average_score": average_score,
                    "test_results": results
                }
            )

        except Exception as e:
            raise AgentTrainingException(f"Agent validation failed: {str(e)}")

    async def _generate_test_response(
        self,
        agent: Agent,
        test_case: TestCase
    ) -> Dict[str, Any]:
        """Generate a response for a test case"""
        messages = [
            SystemMessage(content=agent.system_prompt),
            HumanMessage(content=test_case.input_text)
        ]

        # Use the configured LLM provider
        provider = LLMProvider(agent.llm_config.get("provider", "openai"))

        response_data = await self.llm_router.generate_chat_with_fallback(
            messages=messages,
            preferred_provider=provider,
            temperature=agent.llm_config.get("temperature", 0.7),
            max_tokens=agent.llm_config.get("max_tokens", 1000)
        )

        return response_data

    def _score_response(self, test_case: TestCase, response_data: Dict[str, Any]) -> float:
        """Score a response based on test case criteria"""
        response = response_data.get("response", "").lower()

        if not response:
            return 0.0

        # Basic scoring criteria
        score = 0.0

        # Check if response is appropriate length (not too short, not too long)
        if 10 <= len(response) <= 2000:
            score += 0.3

        # Check if response contains expected topics
        topic_matches = 0
        for topic in test_case.expected_topics:
            if topic.lower() in response:
                topic_matches += 1

        if test_case.expected_topics:
            topic_score = topic_matches / len(test_case.expected_topics)
            score += topic_score * 0.4

        # Check response quality (basic heuristics)
        # - Contains helpful language
        helpful_phrases = ["help", "assist", "support", "provide", "offer", "available"]
        if any(phrase in response for phrase in helpful_phrases):
            score += 0.2

        # - Doesn't contain obvious errors or inappropriate content
        error_phrases = ["error", "sorry, i can't", "i don't understand", "not working"]
        if not any(phrase in response for phrase in error_phrases):
            score += 0.1

        return min(score, 1.0)  # Cap at 1.0


# Global agent trainer instance
agent_trainer = AgentTrainer()