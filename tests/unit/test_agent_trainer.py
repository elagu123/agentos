import pytest
from unittest.mock import AsyncMock, Mock, patch
from app.core.agent_trainer import AgentTrainer, TestCase, ValidationResult
from app.models import BusinessContext, Agent


class TestAgentTrainer:
    """Test cases for AgentTrainer"""

    @pytest.fixture
    def trainer(self):
        return AgentTrainer()

    @pytest.fixture
    def mock_business_context(self, test_organization):
        context = BusinessContext(
            organization_id=test_organization.id,
            business_name="Test Business",
            industry="technology",
            target_audience="Small businesses",
            brand_tone="professional",
            communication_style="helpful",
            response_length="medium",
            products=[{"name": "Test Product", "description": "A test product"}],
            faq_data=[{"question": "What do you do?", "answer": "We provide testing services"}],
            brand_guidelines="Be professional and helpful"
        )
        return context

    def test_generate_system_prompt(self, trainer, mock_business_context):
        """Test system prompt generation"""
        prompt = trainer.generate_system_prompt(mock_business_context)

        assert "Test Business" in prompt
        assert "technology" in prompt
        assert "Small businesses" in prompt
        assert "professional" in prompt
        assert "Test Product" in prompt
        assert "What do you do?" in prompt

    def test_create_rag_config(self, trainer):
        """Test RAG configuration creation"""
        config = trainer.create_rag_config("test_collection")

        assert config["enabled"] is True
        assert config["vector_store_collection"] == "test_collection"
        assert config["similarity_threshold"] == 0.7
        assert config["max_results"] == 5

    def test_create_llm_config(self, trainer, mock_business_context):
        """Test LLM configuration creation"""
        config = trainer.create_llm_config(mock_business_context)

        assert "provider" in config
        assert "model" in config
        assert "temperature" in config
        assert "max_tokens" in config
        assert config["temperature"] == 0.7  # helpful style
        assert config["max_tokens"] == 1000  # medium length

    def test_create_tools_config(self, trainer, mock_business_context):
        """Test tools configuration creation"""
        tools = trainer.create_tools_config(mock_business_context)

        assert len(tools) >= 1
        assert tools[0]["name"] == "knowledge_search"
        assert tools[0]["type"] == "retrieval"
        assert tools[0]["enabled"] is True

    def test_create_memory_config(self, trainer, mock_business_context):
        """Test memory configuration creation"""
        config = trainer.create_memory_config(mock_business_context)

        assert config["type"] == "conversation_buffer_window"
        assert config["window_size"] == 10
        assert config["max_token_limit"] == 2000

    def test_generate_test_cases(self, trainer, mock_business_context):
        """Test test case generation"""
        test_cases = trainer.generate_test_cases(mock_business_context)

        assert len(test_cases) > 0
        assert any("Hello" in tc.input_text for tc in test_cases)
        assert any("Test Business" in tc.input_text for tc in test_cases)

    @pytest.mark.asyncio
    async def test_train_principal_agent(self, trainer, db_session, test_organization, mock_business_context):
        """Test principal agent training"""
        with patch.object(trainer, 'validate_agent') as mock_validate:
            mock_validate.return_value = ValidationResult(
                passed=True,
                score=0.8,
                details={"test_results": []}
            )

            agent = await trainer.train_principal_agent(
                db=db_session,
                organization_id=str(test_organization.id),
                business_context=mock_business_context
            )

            assert agent.name == "Test Business Principal Agent"
            assert agent.type == "principal"
            assert agent.status == "ready"
            assert agent.training_completed is True
            assert agent.validation_score == 0.8

    def test_score_response(self, trainer):
        """Test response scoring"""
        test_case = TestCase(
            input_text="Hello, how can you help me?",
            expected_topics=["help", "assistance"]
        )

        response_data = {
            "response": "Hello! I can help you with your questions and provide assistance with our services."
        }

        score = trainer._score_response(test_case, response_data)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should score well for containing expected topics

    def test_score_response_empty(self, trainer):
        """Test response scoring with empty response"""
        test_case = TestCase(
            input_text="Test",
            expected_topics=["test"]
        )

        response_data = {"response": ""}

        score = trainer._score_response(test_case, response_data)
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_validate_agent(self, trainer, test_agent):
        """Test agent validation"""
        test_cases = [
            TestCase("Hello", ["greeting"], False),
            TestCase("What do you do?", ["business"], True)
        ]

        with patch.object(trainer, '_generate_test_response') as mock_generate:
            mock_generate.return_value = {
                "response": "Hello! I can help you with business questions.",
                "execution_time": 0.5
            }

            result = await trainer.validate_agent(test_agent, test_cases)

            assert isinstance(result, ValidationResult)
            assert result.score >= 0.0
            assert "total_tests" in result.details
            assert result.details["total_tests"] == 2


class TestValidationResult:
    """Test ValidationResult class"""

    def test_validation_result_creation(self):
        """Test ValidationResult creation"""
        result = ValidationResult(
            passed=True,
            score=0.85,
            details={"test_count": 5}
        )

        assert result.passed is True
        assert result.score == 0.85
        assert result.details["test_count"] == 5


class TestTestCase:
    """Test TestCase class"""

    def test_test_case_creation(self):
        """Test TestCase creation"""
        test_case = TestCase(
            input_text="Test input",
            expected_topics=["test", "input"],
            context_required=True
        )

        assert test_case.input_text == "Test input"
        assert test_case.expected_topics == ["test", "input"]
        assert test_case.context_required is True

    def test_test_case_default_context(self):
        """Test TestCase with default context_required"""
        test_case = TestCase(
            input_text="Test",
            expected_topics=["test"]
        )

        assert test_case.context_required is True