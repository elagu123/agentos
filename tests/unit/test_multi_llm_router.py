import pytest
from unittest.mock import AsyncMock, Mock, patch
from app.core.multi_llm_router import (
    MultiLLMRouter,
    TaskType,
    LLMProvider,
    OpenAIClient,
    AnthropicClient,
    TogetherClient
)


class TestMultiLLMRouter:
    """Test cases for MultiLLMRouter"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with API keys"""
        mock = Mock()
        mock.openai_api_key = "test_openai_key"
        mock.anthropic_api_key = "test_anthropic_key"
        mock.together_api_key = "test_together_key"
        mock.default_llm_provider = "openai"
        return mock

    @pytest.fixture
    def router(self, mock_settings):
        """Create router with mocked settings"""
        with patch('app.core.multi_llm_router.settings', mock_settings):
            with patch.object(MultiLLMRouter, '_initialize_clients'):
                router = MultiLLMRouter()
                # Manually set up mock clients
                router.clients = {
                    "gpt-4-mini": Mock(),
                    "claude-haiku": Mock(),
                    "llama-3-70b": Mock(),
                    "mixtral-8x7b": Mock()
                }
                return router

    def test_select_optimal_model_real_time_chat(self, router):
        """Test model selection for real-time chat"""
        model = router._select_optimal_model(TaskType.REAL_TIME_CHAT)
        assert model == "claude-haiku"

    def test_select_optimal_model_complex_reasoning(self, router):
        """Test model selection for complex reasoning"""
        model = router._select_optimal_model(TaskType.COMPLEX_REASONING)
        assert model == "gpt-4-mini"

    def test_select_optimal_model_bulk_processing(self, router):
        """Test model selection for bulk processing"""
        model = router._select_optimal_model(TaskType.BULK_PROCESSING)
        assert model == "mixtral-8x7b"

    def test_select_optimal_model_privacy_high(self, router):
        """Test model selection with high privacy requirement"""
        context = {"privacy": "high"}
        model = router._select_optimal_model(TaskType.REAL_TIME_CHAT, context)
        assert model == "llama-3-70b"

    def test_select_optimal_model_cost_priority(self, router):
        """Test model selection with cost priority"""
        context = {"cost_priority": "low"}
        model = router._select_optimal_model(TaskType.REAL_TIME_CHAT, context)
        assert model == "mixtral-8x7b"

    def test_select_optimal_model_speed_priority(self, router):
        """Test model selection with speed priority"""
        context = {"speed_priority": "high"}
        model = router._select_optimal_model(TaskType.COMPLEX_REASONING, context)
        assert model == "claude-haiku"

    def test_get_fallback_model(self, router):
        """Test fallback model selection"""
        model = router._get_fallback_model()
        assert model in router.clients

    def test_get_fallback_model_privacy_requirement(self, router):
        """Test fallback model with privacy requirement"""
        context = {"privacy": "high"}
        model = router._get_fallback_model(context)
        # Should prefer privacy-compliant models
        assert model in ["llama-3-70b", "mixtral-8x7b"]

    def test_get_routing_reason(self, router):
        """Test routing reason generation"""
        reason = router._get_routing_reason(
            "claude-haiku",
            TaskType.REAL_TIME_CHAT,
            {"privacy": "high"}
        )
        assert isinstance(reason, str)
        assert len(reason) > 0

    @pytest.mark.asyncio
    async def test_route_success(self, router):
        """Test successful routing"""
        mock_client = Mock()
        mock_client.generate_text = AsyncMock(return_value="Test response")
        router.clients["claude-haiku"] = mock_client

        result = await router.route(
            TaskType.REAL_TIME_CHAT,
            "Test prompt"
        )

        assert result["success"] is True
        assert result["response"] == "Test response"
        assert result["model_used"] == "claude-haiku"
        assert "execution_time" in result

    @pytest.mark.asyncio
    async def test_route_fallback(self, router):
        """Test routing with fallback"""
        # First model fails
        mock_client_1 = Mock()
        mock_client_1.generate_text = AsyncMock(side_effect=Exception("API Error"))

        # Second model succeeds
        mock_client_2 = Mock()
        mock_client_2.generate_text = AsyncMock(return_value="Fallback response")

        router.clients["claude-haiku"] = mock_client_1
        router.clients["gpt-4-mini"] = mock_client_2

        with patch.object(router, '_fallback_route') as mock_fallback:
            mock_fallback.return_value = {
                "response": "Fallback response",
                "model_used": "gpt-4-mini",
                "success": True
            }

            result = await router.route(
                TaskType.REAL_TIME_CHAT,
                "Test prompt"
            )

            assert result["success"] is True
            assert result["response"] == "Fallback response"

    @pytest.mark.asyncio
    async def test_fallback_route(self, router):
        """Test fallback routing logic"""
        mock_client = Mock()
        mock_client.generate_text = AsyncMock(return_value="Fallback response")
        router.clients["gpt-4-mini"] = mock_client

        result = await router._fallback_route(
            "Test prompt",
            exclude_model="claude-haiku"
        )

        assert result["success"] is True
        assert result["response"] == "Fallback response"
        assert result["routing_reason"] == "fallback from claude-haiku"

    def test_get_model_info(self, router):
        """Test getting model information"""
        info = router.get_model_info()

        assert "available_models" in info
        assert "model_configs" in info
        assert "providers" in info
        assert "task_types" in info

        assert set(info["available_models"]) == set(router.clients.keys())


class TestLLMClients:
    """Test cases for individual LLM clients"""

    def test_openai_client_creation(self):
        """Test OpenAI client creation"""
        client = OpenAIClient(
            api_key="test_key",
            model="gpt-4o-mini",
            temperature=0.7
        )

        assert client.api_key == "test_key"
        assert client.model == "gpt-4o-mini"
        assert client.temperature == 0.7

    def test_anthropic_client_creation(self):
        """Test Anthropic client creation"""
        client = AnthropicClient(
            api_key="test_key",
            model="claude-3-haiku-20240307",
            temperature=0.3
        )

        assert client.api_key == "test_key"
        assert client.model == "claude-3-haiku-20240307"
        assert client.temperature == 0.3

    def test_together_client_creation(self):
        """Test Together client creation"""
        client = TogetherClient(
            api_key="test_key",
            model="meta-llama/Llama-3-70b-chat-hf",
            temperature=0.5
        )

        assert client.api_key == "test_key"
        assert client.model == "meta-llama/Llama-3-70b-chat-hf"
        assert client.temperature == 0.5

    def test_token_count_estimation(self):
        """Test token count estimation"""
        client = OpenAIClient(api_key="test")
        count = client.get_token_count("This is a test sentence with multiple words.")

        assert isinstance(count, (int, float))
        assert count > 0


class TestTaskTypes:
    """Test TaskType enum"""

    def test_task_types_exist(self):
        """Test that all expected task types exist"""
        expected_types = [
            "real_time_chat",
            "complex_reasoning",
            "bulk_processing",
            "creative_writing",
            "code_generation",
            "document_analysis"
        ]

        for task_type in expected_types:
            assert hasattr(TaskType, task_type.upper())

    def test_task_type_values(self):
        """Test task type string values"""
        assert TaskType.REAL_TIME_CHAT.value == "real_time_chat"
        assert TaskType.COMPLEX_REASONING.value == "complex_reasoning"
        assert TaskType.BULK_PROCESSING.value == "bulk_processing"


class TestLLMProviders:
    """Test LLMProvider enum"""

    def test_providers_exist(self):
        """Test that all expected providers exist"""
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.ANTHROPIC.value == "anthropic"
        assert LLMProvider.TOGETHER.value == "together"