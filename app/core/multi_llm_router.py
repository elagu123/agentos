from typing import Dict, Any, Optional, List, Union
from abc import ABC, abstractmethod
import asyncio
import time
from enum import Enum

from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI, ChatAnthropic
from langchain.llms import Together
from langchain.schema import BaseMessage, HumanMessage, SystemMessage, AIMessage

from app.config import settings
from app.utils.exceptions import LLMException


class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    TOGETHER = "together"


class TaskType(Enum):
    REAL_TIME_CHAT = "real_time_chat"
    COMPLEX_REASONING = "complex_reasoning"
    BULK_PROCESSING = "bulk_processing"
    CREATIVE_WRITING = "creative_writing"
    CODE_GENERATION = "code_generation"
    DOCUMENT_ANALYSIS = "document_analysis"


class BaseLLMClient(ABC):
    """Base class for LLM clients"""

    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.config = kwargs

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate text from prompt"""
        pass

    @abstractmethod
    async def generate_chat(
        self,
        messages: List[BaseMessage],
        **kwargs
    ) -> str:
        """Generate response from chat messages"""
        pass

    @abstractmethod
    def get_token_count(self, text: str) -> int:
        """Estimate token count for text"""
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI LLM client"""

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.model = kwargs.get("model", "gpt-4-turbo-preview")
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 2000)

        self.chat_model = ChatOpenAI(
            openai_api_key=api_key,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate text using OpenAI"""
        try:
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))

            response = await self.chat_model.agenerate([messages])
            return response.generations[0][0].text.strip()
        except Exception as e:
            raise LLMException(f"OpenAI generation failed: {str(e)}")

    async def generate_chat(
        self,
        messages: List[BaseMessage],
        **kwargs
    ) -> str:
        """Generate chat response using OpenAI"""
        try:
            response = await self.chat_model.agenerate([messages])
            return response.generations[0][0].text.strip()
        except Exception as e:
            raise LLMException(f"OpenAI chat generation failed: {str(e)}")

    def get_token_count(self, text: str) -> int:
        """Estimate token count (rough approximation)"""
        return len(text.split()) * 1.3  # Rough estimation


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude LLM client"""

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.model = kwargs.get("model", "claude-3-sonnet-20240229")
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 2000)

        self.chat_model = ChatAnthropic(
            anthropic_api_key=api_key,
            model=self.model,
            temperature=self.temperature,
            max_tokens_to_sample=self.max_tokens
        )

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate text using Anthropic Claude"""
        try:
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))

            response = await self.chat_model.agenerate([messages])
            return response.generations[0][0].text.strip()
        except Exception as e:
            raise LLMException(f"Anthropic generation failed: {str(e)}")

    async def generate_chat(
        self,
        messages: List[BaseMessage],
        **kwargs
    ) -> str:
        """Generate chat response using Anthropic Claude"""
        try:
            response = await self.chat_model.agenerate([messages])
            return response.generations[0][0].text.strip()
        except Exception as e:
            raise LLMException(f"Anthropic chat generation failed: {str(e)}")

    def get_token_count(self, text: str) -> int:
        """Estimate token count (rough approximation)"""
        return len(text.split()) * 1.3  # Rough estimation


class TogetherClient(BaseLLMClient):
    """Together AI LLM client for open-source models"""

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.model = kwargs.get("model", "meta-llama/Llama-3-70b-chat-hf")
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 2000)

        self.llm = Together(
            together_api_key=api_key,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate text using Together AI"""
        try:
            # Format prompt with system message if provided
            formatted_prompt = prompt
            if system_prompt:
                formatted_prompt = f"System: {system_prompt}\n\nUser: {prompt}\n\nAssistant:"

            response = await self.llm.agenerate([formatted_prompt])
            return response.generations[0][0].text.strip()
        except Exception as e:
            raise LLMException(f"Together AI generation failed: {str(e)}")

    async def generate_chat(
        self,
        messages: List[BaseMessage],
        **kwargs
    ) -> str:
        """Generate chat response using Together AI"""
        try:
            # Convert messages to formatted prompt
            formatted_prompt = ""
            for message in messages:
                if isinstance(message, SystemMessage):
                    formatted_prompt += f"System: {message.content}\n\n"
                elif isinstance(message, HumanMessage):
                    formatted_prompt += f"User: {message.content}\n\n"
                elif isinstance(message, AIMessage):
                    formatted_prompt += f"Assistant: {message.content}\n\n"

            formatted_prompt += "Assistant:"

            response = await self.llm.agenerate([formatted_prompt])
            return response.generations[0][0].text.strip()
        except Exception as e:
            raise LLMException(f"Together AI chat generation failed: {str(e)}")

    def get_token_count(self, text: str) -> int:
        """Estimate token count (rough approximation)"""
        return len(text.split()) * 1.3  # Rough estimation


class MultiLLMRouter:
    """Router for multiple LLM providers with fallback and load balancing"""

    def __init__(self):
        self.clients: Dict[str, BaseLLMClient] = {}
        self.default_provider = LLMProvider(settings.default_llm_provider)
        self.fallback_order = [LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.TOGETHER]

        # Model configurations for intelligent routing
        self.model_configs = {
            "gpt-4-mini": {
                "provider": LLMProvider.OPENAI,
                "model": "gpt-4o-mini",
                "strengths": ["reasoning", "code", "analysis"],
                "speed": "medium",
                "cost": "low",
                "privacy": "cloud"
            },
            "claude-haiku": {
                "provider": LLMProvider.ANTHROPIC,
                "model": "claude-3-haiku-20240307",
                "strengths": ["speed", "chat", "simple_tasks"],
                "speed": "fast",
                "cost": "very_low",
                "privacy": "cloud"
            },
            "llama-3-70b": {
                "provider": LLMProvider.TOGETHER,
                "model": "meta-llama/Llama-3-70b-chat-hf",
                "strengths": ["reasoning", "bulk_processing", "privacy"],
                "speed": "medium",
                "cost": "low",
                "privacy": "high"
            },
            "mixtral-8x7b": {
                "provider": LLMProvider.TOGETHER,
                "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "strengths": ["bulk_processing", "multilingual", "cost_effective"],
                "speed": "fast",
                "cost": "very_low",
                "privacy": "high"
            }
        }

        # Initialize available clients
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize LLM clients based on available API keys"""
        # Initialize OpenAI models
        if settings.openai_api_key:
            self.clients["gpt-4-mini"] = OpenAIClient(
                api_key=settings.openai_api_key,
                model="gpt-4o-mini",
                temperature=0.7,
                max_tokens=2000
            )

        # Initialize Anthropic models
        if settings.anthropic_api_key:
            self.clients["claude-haiku"] = AnthropicClient(
                api_key=settings.anthropic_api_key,
                model="claude-3-haiku-20240307",
                temperature=0.3,
                max_tokens=2000
            )

        # Initialize Together AI models
        if hasattr(settings, 'together_api_key') and settings.together_api_key:
            self.clients["llama-3-70b"] = TogetherClient(
                api_key=settings.together_api_key,
                model="meta-llama/Llama-3-70b-chat-hf",
                temperature=0.5,
                max_tokens=2000
            )

            self.clients["mixtral-8x7b"] = TogetherClient(
                api_key=settings.together_api_key,
                model="mistralai/Mixtral-8x7B-Instruct-v0.1",
                temperature=0.5,
                max_tokens=2000
            )

        if not self.clients:
            raise LLMException("No LLM providers configured. Please set API keys.")

    def get_client(self, provider: Optional[LLMProvider] = None) -> BaseLLMClient:
        """Get LLM client for specified provider"""
        target_provider = provider or self.default_provider

        if target_provider not in self.clients:
            raise LLMException(f"Provider {target_provider.value} not available")

        return self.clients[target_provider]

    async def generate_with_fallback(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        preferred_provider: Optional[LLMProvider] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text with automatic fallback to other providers
        """
        providers_to_try = [preferred_provider] if preferred_provider else []
        providers_to_try.extend([p for p in self.fallback_order if p not in providers_to_try])

        # Filter only available providers
        providers_to_try = [p for p in providers_to_try if p in self.clients]

        last_error = None
        start_time = time.time()

        for provider in providers_to_try:
            try:
                client = self.get_client(provider)
                response = await client.generate_text(prompt, system_prompt, **kwargs)
                end_time = time.time()

                return {
                    "response": response,
                    "provider": provider.value,
                    "execution_time": end_time - start_time,
                    "success": True,
                    "error": None
                }

            except Exception as e:
                last_error = e
                continue

        # All providers failed
        end_time = time.time()
        raise LLMException(f"All LLM providers failed. Last error: {str(last_error)}")

    async def generate_chat_with_fallback(
        self,
        messages: List[BaseMessage],
        preferred_provider: Optional[LLMProvider] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate chat response with automatic fallback
        """
        providers_to_try = [preferred_provider] if preferred_provider else []
        providers_to_try.extend([p for p in self.fallback_order if p not in providers_to_try])

        # Filter only available providers
        providers_to_try = [p for p in providers_to_try if p in self.clients]

        last_error = None
        start_time = time.time()

        for provider in providers_to_try:
            try:
                client = self.get_client(provider)
                response = await client.generate_chat(messages, **kwargs)
                end_time = time.time()

                return {
                    "response": response,
                    "provider": provider.value,
                    "execution_time": end_time - start_time,
                    "success": True,
                    "error": None
                }

            except Exception as e:
                last_error = e
                continue

        # All providers failed
        end_time = time.time()
        raise LLMException(f"All LLM providers failed. Last error: {str(last_error)}")

    async def batch_generate(
        self,
        requests: List[Dict[str, Any]],
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple responses concurrently
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_request(request):
            async with semaphore:
                return await self.generate_with_fallback(**request)

        tasks = [process_request(req) for req in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def get_available_providers(self) -> List[str]:
        """Get list of available LLM providers"""
        return [provider.value for provider in self.clients.keys()]

    def estimate_cost(
        self,
        text: str,
        provider: Optional[LLMProvider] = None
    ) -> float:
        """
        Estimate cost for text generation (rough approximation)
        """
        target_provider = provider or self.default_provider
        client = self.get_client(target_provider)
        token_count = client.get_token_count(text)

        # Rough cost estimates (per 1K tokens)
        cost_per_1k_tokens = {
            LLMProvider.OPENAI: 0.01,  # GPT-4 input pricing
            LLMProvider.ANTHROPIC: 0.008,  # Claude-3 Sonnet pricing
        }

        base_cost = cost_per_1k_tokens.get(target_provider, 0.01)
        return (token_count / 1000) * base_cost

    async def route(
        self,
        task_type: TaskType,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Intelligent routing based on task type, context, and requirements

        Args:
            task_type: Type of task to perform
            prompt: Input prompt
            context: Additional context with requirements

        Returns:
            Response with routing information
        """
        # Select best model based on task type and context
        model_name = self._select_optimal_model(task_type, context)

        if model_name not in self.clients:
            # Fallback to available model
            model_name = self._get_fallback_model(context)

        try:
            client = self.clients[model_name]
            start_time = time.time()

            response = await client.generate_text(prompt, **kwargs)
            execution_time = time.time() - start_time

            return {
                "response": response,
                "model_used": model_name,
                "provider": self.model_configs[model_name]["provider"].value,
                "execution_time": execution_time,
                "success": True,
                "error": None,
                "routing_reason": self._get_routing_reason(model_name, task_type, context)
            }

        except Exception as e:
            # Implement fallback routing
            return await self._fallback_route(prompt, exclude_model=model_name, **kwargs)

    def _select_optimal_model(
        self,
        task_type: TaskType,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Select the optimal model based on task type and context"""
        context = context or {}

        # Priority routing based on task type
        if task_type == TaskType.REAL_TIME_CHAT:
            return "claude-haiku"  # Fastest response
        elif task_type == TaskType.COMPLEX_REASONING:
            return "gpt-4-mini"  # Best reasoning capabilities
        elif task_type == TaskType.BULK_PROCESSING:
            return "mixtral-8x7b"  # Most cost-effective for bulk
        elif task_type == TaskType.CREATIVE_WRITING:
            return "llama-3-70b"  # Good creative capabilities
        elif task_type == TaskType.CODE_GENERATION:
            return "gpt-4-mini"  # Best for code
        elif task_type == TaskType.DOCUMENT_ANALYSIS:
            return "claude-haiku"  # Good analysis, fast

        # Context-based routing
        if context.get("privacy") == "high":
            return "llama-3-70b"  # On-premise/private option
        elif context.get("cost_priority") == "low":
            return "mixtral-8x7b"  # Most cost-effective
        elif context.get("speed_priority") == "high":
            return "claude-haiku"  # Fastest

        # Default to GPT-4 mini for balanced performance
        return "gpt-4-mini"

    def _get_fallback_model(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Get fallback model when preferred model is unavailable"""
        context = context or {}

        # Try to find available model based on context requirements
        for model_name, config in self.model_configs.items():
            if model_name in self.clients:
                # Check if model meets privacy requirements
                if context.get("privacy") == "high" and config["privacy"] != "high":
                    continue
                return model_name

        # If no model meets requirements, return any available
        available_models = list(self.clients.keys())
        if available_models:
            return available_models[0]

        raise LLMException("No LLM models available")

    def _get_routing_reason(
        self,
        model_name: str,
        task_type: TaskType,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Get human-readable reason for model selection"""
        config = self.model_configs.get(model_name, {})

        reasons = []

        if task_type == TaskType.REAL_TIME_CHAT and "speed" in config.get("strengths", []):
            reasons.append("optimized for speed")
        elif task_type == TaskType.COMPLEX_REASONING and "reasoning" in config.get("strengths", []):
            reasons.append("superior reasoning capabilities")
        elif task_type == TaskType.BULK_PROCESSING and "bulk_processing" in config.get("strengths", []):
            reasons.append("cost-effective for bulk processing")

        if context and context.get("privacy") == "high" and config.get("privacy") == "high":
            reasons.append("meets privacy requirements")

        if not reasons:
            reasons.append("general purpose capabilities")

        return ", ".join(reasons)

    async def _fallback_route(
        self,
        prompt: str,
        exclude_model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Fallback routing when primary model fails"""
        start_time = time.time()

        # Try other available models
        for model_name, client in self.clients.items():
            if model_name == exclude_model:
                continue

            try:
                response = await client.generate_text(prompt, **kwargs)
                execution_time = time.time() - start_time

                return {
                    "response": response,
                    "model_used": model_name,
                    "provider": self.model_configs[model_name]["provider"].value,
                    "execution_time": execution_time,
                    "success": True,
                    "error": None,
                    "routing_reason": f"fallback from {exclude_model}"
                }
            except Exception:
                continue

        # All models failed
        raise LLMException(f"All available models failed. Excluded: {exclude_model}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about available models and their capabilities"""
        return {
            "available_models": list(self.clients.keys()),
            "model_configs": self.model_configs,
            "providers": [provider.value for provider in LLMProvider],
            "task_types": [task_type.value for task_type in TaskType]
        }


# Global router instance
llm_router = MultiLLMRouter()