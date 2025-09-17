import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.database import Base, get_db
from app.models import User, Organization, BusinessContext, Agent
from app.config import settings


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    # Use in-memory SQLite for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def override_get_db(db_session: AsyncSession):
    """Override the get_db dependency for testing."""
    async def _override_get_db():
        yield db_session

    return _override_get_db


@pytest.fixture
def client(override_get_db) -> TestClient:
    """Create a test client."""
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# Test data fixtures
@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "clerk_id": "user_test123",
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User"
    }


@pytest.fixture
def sample_organization_data():
    """Sample organization data for testing."""
    return {
        "name": "Test Organization",
        "industry": "technology",
        "size_range": "1-10",
        "description": "A test organization"
    }


@pytest.fixture
def sample_business_context_data():
    """Sample business context data for testing."""
    return {
        "business_name": "Test Business",
        "industry": "technology",
        "target_audience": "Small businesses",
        "brand_tone": "professional",
        "products": [
            {"name": "Test Product", "description": "A test product"}
        ],
        "faq_data": [
            {"question": "What do you do?", "answer": "We provide testing services"}
        ]
    }


@pytest.fixture
async def test_user(db_session: AsyncSession, sample_user_data):
    """Create a test user."""
    user = User(**sample_user_data)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_organization(db_session: AsyncSession, sample_organization_data):
    """Create a test organization."""
    org = Organization(
        **sample_organization_data,
        slug="test-organization"
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture
async def test_business_context(
    db_session: AsyncSession,
    test_organization: Organization,
    sample_business_context_data
):
    """Create a test business context."""
    context = BusinessContext(
        **sample_business_context_data,
        organization_id=test_organization.id
    )
    db_session.add(context)
    await db_session.commit()
    await db_session.refresh(context)
    return context


@pytest.fixture
async def test_agent(
    db_session: AsyncSession,
    test_organization: Organization
):
    """Create a test agent."""
    agent = Agent(
        organization_id=test_organization.id,
        name="Test Agent",
        type="principal",
        status="ready",
        system_prompt="You are a test agent."
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest.fixture
async def test_user_with_org(
    db_session: AsyncSession,
    test_user: User,
    test_organization: Organization
):
    """Create a test user with organization."""
    test_user.organization_id = test_organization.id
    test_user.role = "owner"
    await db_session.commit()
    await db_session.refresh(test_user)
    return test_user


# Mock fixtures
@pytest.fixture
def mock_clerk_auth():
    """Mock Clerk authentication."""
    mock = Mock()
    mock.verify_token = AsyncMock(return_value={
        "id": "user_test123",
        "email_addresses": [{"email_address": "test@example.com"}],
        "first_name": "Test",
        "last_name": "User"
    })
    return mock


@pytest.fixture
def mock_llm_router():
    """Mock LLM router."""
    mock = Mock()
    mock.route = AsyncMock(return_value={
        "response": "Test response",
        "model_used": "gpt-4-mini",
        "success": True
    })
    return mock


@pytest.fixture
def mock_embedding_manager():
    """Mock embedding manager."""
    mock = Mock()
    mock.create_collection = AsyncMock(return_value=True)
    mock.add_documents = AsyncMock(return_value=5)
    mock.search_similar = AsyncMock(return_value=[
        {
            "id": "doc1",
            "content": "Test document",
            "metadata": {"source": "test"},
            "score": 0.9
        }
    ])
    return mock


@pytest.fixture
def mock_document_processor():
    """Mock document processor."""
    mock = Mock()
    mock.process_documents = AsyncMock(return_value={
        "total_files": 1,
        "processed_files": 1,
        "failed_files": 0,
        "total_chunks": 5,
        "collection_name": "test_collection"
    })
    return mock


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock = AsyncMock()
    mock.lpush = AsyncMock(return_value=1)
    mock.lrange = AsyncMock(return_value=[])
    mock.expire = AsyncMock(return_value=True)
    return mock