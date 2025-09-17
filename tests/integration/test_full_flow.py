"""
Comprehensive End-to-End Integration Test for AgentOS
Tests the complete user journey from registration to agent execution
"""

import pytest
import asyncio
import httpx
import tempfile
import os
from typing import Dict, Any, List
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text
import json
import time

from app.main import app
from app.database import get_db, Base
from app.models.user import User
from app.models.organization import Organization
from app.models.business_context import BusinessContext
from app.models.agent import Agent
from app.config import settings


class TestFullFlow:
    """Complete end-to-end integration test suite"""

    @pytest.fixture(scope="class")
    async def setup_test_environment(self):
        """Setup test environment with clean database"""
        # Create test database engine
        test_db_url = settings.database_url.replace("agentos", "agentos_test")
        engine = create_async_engine(test_db_url, echo=False)

        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        # Override dependency
        async def get_test_db():
            async with AsyncSession(engine) as session:
                yield session

        app.dependency_overrides[get_db] = get_test_db

        yield engine

        # Cleanup
        app.dependency_overrides.clear()
        await engine.dispose()

    @pytest.fixture
    def client(self):
        """FastAPI test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_user_data(self):
        """Mock user data for testing"""
        return {
            "clerk_user_id": "user_test123",
            "email": "test@company.com",
            "first_name": "John",
            "last_name": "Doe",
            "role": "admin"
        }

    @pytest.fixture
    def mock_organization_data(self):
        """Mock organization data for testing"""
        return {
            "name": "Test Company Inc",
            "industry": "technology",
            "size": "medium",
            "description": "A test technology company focused on AI solutions",
            "website": "https://testcompany.com",
            "goals": [
                "Improve customer service response time",
                "Automate content creation",
                "Enhance data analysis capabilities"
            ]
        }

    @pytest.fixture
    def sample_documents(self):
        """Create sample documents for testing"""
        docs = []

        # Company overview document
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("""
            Test Company Inc - Company Overview

            Founded in 2020, Test Company Inc is a leading technology company
            specializing in AI-powered business solutions. Our mission is to
            democratize AI for small and medium enterprises.

            Our core values:
            - Innovation and excellence
            - Customer-first approach
            - Ethical AI practices
            - Continuous learning

            Key services:
            - AI consulting
            - Custom software development
            - Data analytics
            - Process automation
            """)
            docs.append(f.name)

        # Product information document
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("""
            Product Catalog - Test Company Inc

            AgentOS Platform:
            - Multi-agent orchestration system
            - Business context training
            - Real-time chat interfaces
            - Integration capabilities
            - Starting at $99/month

            Custom AI Solutions:
            - Tailored to business needs
            - Full implementation support
            - Ongoing maintenance
            - Enterprise pricing available

            Support Services:
            - 24/7 technical support
            - Training and onboarding
            - Best practices consulting
            """)
            docs.append(f.name)

        yield docs

        # Cleanup
        for doc in docs:
            try:
                os.unlink(doc)
            except FileNotFoundError:
                pass

    async def test_complete_user_journey(
        self,
        setup_test_environment,
        client,
        mock_user_data,
        mock_organization_data,
        sample_documents
    ):
        """Test the complete user journey from registration to agent execution"""

        # Phase 1: User Authentication
        print("=== Phase 1: User Authentication ===")

        # Mock Clerk authentication for testing
        auth_headers = {"Authorization": "Bearer test_token"}

        # Test auth status endpoint
        response = client.get("/api/v1/auth/status", headers=auth_headers)
        print(f"Auth status response: {response.status_code}")

        # Phase 2: Organization Onboarding
        print("=== Phase 2: Organization Onboarding ===")

        # Start onboarding process
        onboarding_data = {
            "user": mock_user_data,
            "organization": mock_organization_data
        }

        response = client.post(
            "/api/v1/onboarding/start",
            json=onboarding_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        onboarding_result = response.json()

        print(f"Onboarding started: {onboarding_result}")

        organization_id = onboarding_result["organization"]["id"]
        user_id = onboarding_result["user"]["id"]

        # Verify organization was created
        assert onboarding_result["organization"]["name"] == mock_organization_data["name"]
        assert onboarding_result["organization"]["industry"] == mock_organization_data["industry"]

        # Phase 3: Document Upload and Processing
        print("=== Phase 3: Document Upload and Processing ===")

        uploaded_docs = []

        for doc_path in sample_documents:
            with open(doc_path, 'rb') as f:
                files = {"file": (os.path.basename(doc_path), f, "text/plain")}
                data = {"organization_id": organization_id}

                response = client.post(
                    "/api/v1/onboarding/upload-documents",
                    files=files,
                    data=data,
                    headers=auth_headers
                )

                assert response.status_code == 200
                upload_result = response.json()
                uploaded_docs.append(upload_result)

                print(f"Document uploaded: {upload_result['filename']}")

                # Verify document was processed
                assert upload_result["status"] == "processed"
                assert "document_id" in upload_result
                assert upload_result["chunks_created"] > 0

        # Phase 4: Integration Configuration
        print("=== Phase 4: Integration Configuration ===")

        integrations_config = {
            "organization_id": organization_id,
            "integrations": {
                "email": {
                    "enabled": True,
                    "provider": "gmail",
                    "auto_response": True
                },
                "calendar": {
                    "enabled": True,
                    "provider": "google_calendar"
                },
                "crm": {
                    "enabled": False
                }
            }
        }

        response = client.post(
            "/api/v1/onboarding/configure-integrations",
            json=integrations_config,
            headers=auth_headers
        )

        assert response.status_code == 200
        integrations_result = response.json()
        print(f"Integrations configured: {integrations_result}")

        # Phase 5: Agent Training
        print("=== Phase 5: Agent Training ===")

        training_config = {
            "organization_id": organization_id,
            "agent_name": "Test Company Assistant",
            "agent_description": "AI assistant for Test Company Inc",
            "personality": "professional and helpful",
            "specializations": ["customer_service", "product_information", "general_inquiry"],
            "training_goals": mock_organization_data["goals"]
        }

        response = client.post(
            "/api/v1/onboarding/train-agent",
            json=training_config,
            headers=auth_headers
        )

        assert response.status_code == 200
        training_result = response.json()
        print(f"Agent training started: {training_result}")

        agent_id = training_result["agent"]["id"]

        # Wait for training to complete (or simulate completion)
        max_wait = 30  # seconds
        start_time = time.time()

        while time.time() - start_time < max_wait:
            response = client.get(
                f"/api/v1/agents/{agent_id}",
                headers=auth_headers
            )

            if response.status_code == 200:
                agent_data = response.json()
                if agent_data["status"] == "trained":
                    print(f"Agent training completed: {agent_data}")
                    break

            await asyncio.sleep(2)
        else:
            pytest.fail("Agent training did not complete within timeout")

        # Phase 6: Agent Functionality Testing
        print("=== Phase 6: Agent Functionality Testing ===")

        # Test agent conversation
        test_messages = [
            "What services does your company offer?",
            "What are your core values?",
            "How much does AgentOS cost?",
            "What support do you provide?"
        ]

        for message in test_messages:
            conversation_data = {
                "agent_id": agent_id,
                "message": message,
                "context": {
                    "user_id": user_id,
                    "session_id": "test_session_123"
                }
            }

            response = client.post(
                "/api/v1/agents/chat",
                json=conversation_data,
                headers=auth_headers
            )

            assert response.status_code == 200
            chat_result = response.json()

            print(f"Q: {message}")
            print(f"A: {chat_result['response'][:100]}...")

            # Verify response quality
            assert len(chat_result["response"]) > 10
            assert chat_result["confidence"] > 0.5
            assert "sources" in chat_result

        # Phase 7: System Health Validation
        print("=== Phase 7: System Health Validation ===")

        # Test health endpoints
        response = client.get("/health")
        assert response.status_code == 200
        health_data = response.json()
        assert health_data["status"] == "healthy"

        response = client.get("/api/v1/health/detailed", headers=auth_headers)
        assert response.status_code == 200
        detailed_health = response.json()

        print(f"System health: {detailed_health}")

        # Verify all components are healthy
        assert detailed_health["database"]["status"] == "healthy"
        assert detailed_health["redis"]["status"] == "healthy"
        assert detailed_health["qdrant"]["status"] == "healthy"
        assert detailed_health["llm_providers"]["openai"]["status"] == "healthy"

        # Phase 8: Performance Validation
        print("=== Phase 8: Performance Validation ===")

        # Test response times
        start_time = time.time()
        response = client.get(f"/api/v1/agents/{agent_id}", headers=auth_headers)
        response_time = time.time() - start_time

        assert response.status_code == 200
        assert response_time < 2.0  # Should respond within 2 seconds

        print(f"Agent retrieval time: {response_time:.3f}s")

        # Phase 9: Data Validation
        print("=== Phase 9: Data Validation ===")

        # Verify all data was properly stored
        response = client.get("/api/v1/onboarding/status", headers=auth_headers)
        assert response.status_code == 200

        onboarding_status = response.json()
        print(f"Final onboarding status: {onboarding_status}")

        # Verify completion
        assert onboarding_status["step"] == "completed"
        assert onboarding_status["organization_created"] is True
        assert onboarding_status["documents_uploaded"] is True
        assert onboarding_status["integrations_configured"] is True
        assert onboarding_status["agent_trained"] is True

        print("=== End-to-End Test PASSED ===")

    async def test_error_handling_and_recovery(self, client, mock_user_data):
        """Test error handling and system recovery"""

        auth_headers = {"Authorization": "Bearer test_token"}

        # Test invalid organization data
        invalid_org_data = {
            "user": mock_user_data,
            "organization": {
                "name": "",  # Invalid empty name
                "industry": "invalid_industry",
                "size": "invalid_size"
            }
        }

        response = client.post(
            "/api/v1/onboarding/start",
            json=invalid_org_data,
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error
        error_data = response.json()
        assert "detail" in error_data

        # Test file upload limits
        large_content = "x" * (11 * 1024 * 1024)  # 11MB (over limit)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(large_content)
            large_file = f.name

        try:
            with open(large_file, 'rb') as f:
                files = {"file": ("large_file.txt", f, "text/plain")}
                data = {"organization_id": "test_org_id"}

                response = client.post(
                    "/api/v1/onboarding/upload-documents",
                    files=files,
                    data=data,
                    headers=auth_headers
                )

                assert response.status_code == 413  # File too large
        finally:
            os.unlink(large_file)

    async def test_concurrent_requests(self, client, mock_user_data):
        """Test system under concurrent load"""

        auth_headers = {"Authorization": "Bearer test_token"}

        async def make_request(session_id: int):
            """Make a concurrent request"""
            org_data = {
                "user": {**mock_user_data, "clerk_user_id": f"user_test{session_id}"},
                "organization": {
                    "name": f"Test Company {session_id}",
                    "industry": "technology",
                    "size": "small"
                }
            }

            response = client.post(
                "/api/v1/onboarding/start",
                json=org_data,
                headers=auth_headers
            )

            return response.status_code == 200

        # Run 10 concurrent requests
        tasks = [make_request(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # At least 8 out of 10 should succeed (allowing for some rate limiting)
        success_count = sum(1 for result in results if result is True)
        assert success_count >= 8

        print(f"Concurrent requests: {success_count}/10 successful")

    async def test_security_validation(self, client):
        """Test security measures"""

        # Test XSS attempt
        xss_payload = {
            "user": {
                "clerk_user_id": "user_test",
                "email": "test@example.com",
                "first_name": "<script>alert('xss')</script>",
                "last_name": "User"
            },
            "organization": {
                "name": "Test Company",
                "industry": "technology"
            }
        }

        response = client.post("/api/v1/onboarding/start", json=xss_payload)

        # Should either sanitize or reject
        if response.status_code == 200:
            result = response.json()
            # Should be sanitized
            assert "<script>" not in result["user"]["first_name"]
        else:
            # Should be rejected
            assert response.status_code in [400, 422]

        # Test SQL injection attempt
        sql_payload = {
            "user": {
                "clerk_user_id": "user_test'; DROP TABLE users; --",
                "email": "test@example.com"
            }
        }

        response = client.post("/api/v1/onboarding/start", json=sql_payload)
        # Should be rejected or sanitized
        assert response.status_code in [200, 400, 422]

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])