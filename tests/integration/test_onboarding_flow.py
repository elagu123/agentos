import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from app.main import app


class TestOnboardingFlow:
    """Integration tests for the complete onboarding flow"""

    @pytest.fixture
    def auth_headers(self):
        """Mock authorization headers"""
        return {"Authorization": "Bearer test_token"}

    @pytest.fixture
    def organization_data(self):
        """Sample organization data"""
        return {
            "name": "Test Company",
            "industry": "technology",
            "size_range": "1-10",
            "description": "A test company"
        }

    @pytest.fixture
    def business_context_data(self):
        """Sample business context data"""
        return {
            "business_name": "Test Company",
            "industry": "technology",
            "target_audience": "Small businesses",
            "brand_tone": "professional",
            "communication_style": "helpful",
            "response_length": "medium",
            "products": [
                {"name": "Test Product", "description": "A test product"}
            ],
            "faq_data": [
                {"question": "What do you do?", "answer": "We provide testing services"}
            ]
        }

    @pytest.mark.asyncio
    async def test_complete_onboarding_flow(
        self,
        async_client: AsyncClient,
        auth_headers,
        organization_data,
        business_context_data,
        mock_clerk_auth,
        mock_document_processor,
        mock_agent_trainer
    ):
        """Test the complete onboarding flow from start to finish"""

        # Mock all external dependencies
        with patch('app.utils.clerk_auth.clerk_auth', mock_clerk_auth), \
             patch('app.core.document_processor.document_processor', mock_document_processor), \
             patch('app.core.agent_trainer.agent_trainer', mock_agent_trainer):

            # Mock agent trainer
            mock_agent_trainer.train_principal_agent = AsyncMock(return_value=type('Agent', (), {
                'id': 'agent123',
                'status': 'ready',
                'validation_score': 0.85,
                'training_completed': True
            })())

            # Step 1: Start onboarding (create organization and business context)
            response = await async_client.post(
                "/api/v1/onboarding/start",
                json={
                    **organization_data,
                    **business_context_data
                },
                headers=auth_headers
            )

            assert response.status_code == 200
            start_data = response.json()
            assert start_data["step"] == "business_context"
            assert start_data["completed"] is True
            assert start_data["next_step"] == "documents"

            organization_id = start_data["data"]["organization_id"]

            # Step 2: Check onboarding status
            response = await async_client.get(
                "/api/v1/onboarding/status",
                headers=auth_headers
            )

            assert response.status_code == 200
            status_data = response.json()
            assert status_data["current_step"] == "business_context"
            assert status_data["business_context_complete"] is True

            # Step 3: Upload documents (mocked)
            files = [("files", ("test.txt", b"Test document content", "text/plain"))]

            response = await async_client.post(
                "/api/v1/onboarding/upload-documents",
                files=files,
                headers=auth_headers
            )

            assert response.status_code == 200
            upload_data = response.json()
            assert upload_data["step"] == "documents"
            assert upload_data["completed"] is True
            assert upload_data["next_step"] == "integrations"

            # Step 4: Configure integrations
            integrations_data = {
                "email_integration": {
                    "enabled": True,
                    "provider": "gmail",
                    "settings": {"auto_reply": False}
                }
            }

            response = await async_client.post(
                "/api/v1/onboarding/configure-integrations",
                json=integrations_data,
                headers=auth_headers
            )

            assert response.status_code == 200
            integrations_response = response.json()
            assert integrations_response["step"] == "integrations"
            assert integrations_response["completed"] is True
            assert integrations_response["next_step"] == "training"

            # Step 5: Train the principal agent
            response = await async_client.post(
                "/api/v1/onboarding/train-agent",
                headers=auth_headers
            )

            assert response.status_code == 200
            training_data = response.json()
            assert training_data["step"] == "training"
            assert training_data["completed"] is True
            assert training_data["next_step"] is None
            assert training_data["data"]["agent_status"] == "ready"

            # Step 6: Final status check
            response = await async_client.get(
                "/api/v1/onboarding/status",
                headers=auth_headers
            )

            assert response.status_code == 200
            final_status = response.json()
            assert final_status["current_step"] == "completed"
            assert final_status["progress_percentage"] == 100.0
            assert final_status["agent_trained"] is True

    @pytest.mark.asyncio
    async def test_onboarding_start_validation_error(
        self,
        async_client: AsyncClient,
        auth_headers,
        mock_clerk_auth
    ):
        """Test onboarding start with validation errors"""

        with patch('app.utils.clerk_auth.clerk_auth', mock_clerk_auth):
            # Missing required fields
            incomplete_data = {
                "name": "Test Company"
                # Missing business_name, industry, target_audience, brand_tone
            }

            response = await async_client.post(
                "/api/v1/onboarding/start",
                json=incomplete_data,
                headers=auth_headers
            )

            assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_onboarding_document_upload_invalid_file(
        self,
        async_client: AsyncClient,
        auth_headers,
        mock_clerk_auth,
        mock_document_processor
    ):
        """Test document upload with invalid file"""

        with patch('app.utils.clerk_auth.clerk_auth', mock_clerk_auth), \
             patch('app.core.document_processor.document_processor', mock_document_processor):

            # Mock validation failure
            mock_document_processor.validate_files = AsyncMock(return_value=[
                {
                    "filename": "invalid.exe",
                    "valid": False,
                    "errors": ["Unsupported file type: application/exe"]
                }
            ])

            files = [("files", ("invalid.exe", b"Invalid content", "application/exe"))]

            response = await async_client.post(
                "/api/v1/onboarding/upload-documents",
                files=files,
                headers=auth_headers
            )

            assert response.status_code == 400  # Bad request due to invalid file

    @pytest.mark.asyncio
    async def test_onboarding_unauthorized_access(self, async_client: AsyncClient):
        """Test onboarding endpoints without authentication"""

        # Try to start onboarding without auth
        response = await async_client.post(
            "/api/v1/onboarding/start",
            json={"name": "Test"}
        )

        assert response.status_code == 401  # Unauthorized

    @pytest.mark.asyncio
    async def test_onboarding_status_no_organization(
        self,
        async_client: AsyncClient,
        auth_headers,
        mock_clerk_auth
    ):
        """Test getting onboarding status when user has no organization"""

        # Mock user without organization
        mock_user = type('User', (), {
            'organization_id': None
        })()

        with patch('app.utils.clerk_auth.get_current_user', return_value=mock_user):
            response = await async_client.get(
                "/api/v1/onboarding/status",
                headers=auth_headers
            )

            assert response.status_code == 404  # Not found

    @pytest.mark.asyncio
    async def test_update_business_context(
        self,
        async_client: AsyncClient,
        auth_headers,
        mock_clerk_auth,
        test_user_with_org,
        test_business_context
    ):
        """Test updating business context during onboarding"""

        with patch('app.utils.clerk_auth.get_current_user', return_value=test_user_with_org):
            update_data = {
                "brand_tone": "friendly",
                "communication_style": "casual",
                "products": [
                    {"name": "Updated Product", "description": "An updated product"}
                ]
            }

            response = await async_client.put(
                "/api/v1/onboarding/business-context",
                json=update_data,
                headers=auth_headers
            )

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["step"] == "business_context_update"
            assert response_data["completed"] is True
            assert "brand_tone" in response_data["data"]["updated_fields"]

    @pytest.mark.asyncio
    async def test_training_status(
        self,
        async_client: AsyncClient,
        auth_headers,
        mock_clerk_auth,
        test_user_with_org,
        test_agent
    ):
        """Test getting agent training status"""

        with patch('app.utils.clerk_auth.get_current_user', return_value=test_user_with_org):
            response = await async_client.get(
                f"/api/v1/onboarding/training-status/{test_agent.id}",
                headers=auth_headers
            )

            assert response.status_code == 200
            training_status = response.json()
            assert training_status["agent_id"] == str(test_agent.id)
            assert training_status["status"] == test_agent.status
            assert "progress" in training_status