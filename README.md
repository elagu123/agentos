# AgentOS Backend

A multi-agent orchestration platform for SMEs that provides personalized AI agents trained on business-specific context.

## 🚀 Features

### Core Platform
- **Multi-Tenant Architecture**: Isolated data and agents per organization
- **Business Context Training**: AI agents trained on company-specific documents and data
- **Document Intelligence**: Automatic processing and indexing of business documents
- **Multi-LLM Support**: Intelligent routing between OpenAI, Anthropic, and Together AI
- **Memory Management**: Short-term and long-term conversation memory
- **Rate Limiting**: Advanced rate limiting with Redis backend
- **Security**: Comprehensive security middleware and input validation

### Agent System
- **Principal Agents**: Main business representative agents
- **Specialized Agents**: Task-specific agents (copywriting, research, customer service)
- **Agent Training**: Automated training with validation and performance metrics
- **RAG Integration**: Retrieval-Augmented Generation with vector search

### Developer Experience
- **FastAPI Backend**: Modern async Python API
- **Type Safety**: Comprehensive Pydantic schemas and SQLAlchemy models
- **Testing**: Full test suite with pytest
- **Documentation**: OpenAPI/Swagger documentation
- **Migrations**: Alembic database migrations

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15 + pgvector
- **Cache**: Redis
- **Vector Store**: Qdrant (self-hosted)
- **Authentication**: Clerk

### AI/ML
- **LLM Framework**: LangChain
- **LLM Providers**: OpenAI, Anthropic, Together AI
- **Embeddings**: OpenAI text-embedding-ada-002
- **Document Processing**: LangChain document loaders

### Infrastructure
- **Containerization**: Docker & Docker Compose
- **Environment**: Python virtual environments
- **Testing**: pytest with async support

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 6+
- Docker & Docker Compose (optional)
- API Keys for LLM providers

## 🔧 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd agentos-backend
```

### 2. Set Up Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
```

### 4. Start Services with Docker

```bash
# Start PostgreSQL, Redis, and Qdrant
docker-compose up -d
```

### 5. Initialize Database

```bash
# Run migrations
alembic upgrade head
```

### 6. Start the Application

```bash
# Development server with auto-reload
uvicorn app.main:app --reload

# Or run directly
python -m app.main
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | Required |
| `QDRANT_HOST` | Qdrant host | localhost |
| `QDRANT_PORT` | Qdrant port | 6333 |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `ANTHROPIC_API_KEY` | Anthropic API key | Optional |
| `TOGETHER_API_KEY` | Together AI API key | Optional |
| `CLERK_SECRET_KEY` | Clerk authentication key | Required |
| `SECRET_KEY` | Application secret key | Required |

### LLM Configuration

The system supports multiple LLM providers with intelligent routing:

- **OpenAI**: Best for reasoning and code generation
- **Anthropic Claude**: Optimized for speed and chat
- **Together AI**: Cost-effective open-source models

Models are automatically selected based on:
- Task type (real-time chat, complex reasoning, bulk processing)
- Performance requirements (speed, cost, privacy)
- Context requirements

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/unit/test_agent_trainer.py

# Run integration tests
pytest tests/integration/
```

## 📊 Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## 🏗️ Project Structure

```
agentos-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application
│   ├── config.py                  # Configuration settings
│   ├── database.py                # Database setup
│   │
│   ├── models/                    # SQLAlchemy models
│   │   ├── user.py
│   │   ├── organization.py
│   │   ├── agent.py
│   │   └── business_context.py
│   │
│   ├── schemas/                   # Pydantic schemas
│   │   ├── user.py
│   │   ├── organization.py
│   │   ├── agent.py
│   │   └── onboarding.py
│   │
│   ├── api/                       # API routes
│   │   ├── auth.py
│   │   ├── onboarding.py
│   │   ├── agents.py
│   │   └── health.py
│   │
│   ├── core/                      # Business logic
│   │   ├── agent_trainer.py       # Agent training logic
│   │   ├── document_processor.py  # Document processing
│   │   ├── embeddings.py          # Vector embeddings
│   │   ├── multi_llm_router.py    # LLM routing
│   │   └── memory_manager.py      # Conversation memory
│   │
│   └── utils/                     # Utilities
│       ├── clerk_auth.py          # Authentication
│       ├── exceptions.py          # Custom exceptions
│       ├── rate_limiting.py       # Rate limiting
│       └── security.py            # Security utilities
│
├── migrations/                    # Database migrations
├── tests/                         # Test suite
├── docker-compose.yml             # Development services
├── requirements.txt               # Python dependencies
├── alembic.ini                    # Migration configuration
└── README.md
```

## 🔒 Security Features

### Rate Limiting
- User-based rate limiting
- Organization-based limits
- Adaptive limits based on subscription tier
- Redis-backed distributed rate limiting

### Input Validation
- XSS protection with input sanitization
- SQL injection prevention
- Path traversal protection
- File upload validation

### Security Headers
- Content Security Policy (CSP)
- HSTS for HTTPS enforcement
- XSS protection headers
- Frame options for clickjacking prevention

### Authentication
- Clerk integration for user management
- JWT token validation
- Role-based access control
- Organization-level permissions

## 📈 Performance

### Caching
- Redis caching for frequent queries
- Vector search result caching
- Rate limit counters in Redis

### Database Optimization
- Connection pooling
- Query optimization with indexes
- Async database operations

### LLM Optimization
- Intelligent model routing
- Request batching for bulk operations
- Response caching for repeated queries

## 🚀 Deployment

### Docker Deployment

```bash
# Build application image
docker build -t agentos-backend .

# Run with Docker Compose
docker-compose -f docker-compose.prod.yml up -d
```

### Environment-Specific Configurations

- **Development**: Debug mode, verbose logging
- **Staging**: Production-like environment for testing
- **Production**: Optimized for performance and security

## 📚 API Documentation

Once the application is running, visit:
- **Swagger UI**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc

### Key Endpoints

#### Authentication
- `GET /api/v1/auth/me` - Get current user profile
- `GET /api/v1/auth/status` - Get authentication status

#### Onboarding
- `POST /api/v1/onboarding/start` - Start organization onboarding
- `POST /api/v1/onboarding/upload-documents` - Upload business documents
- `POST /api/v1/onboarding/configure-integrations` - Configure integrations
- `POST /api/v1/onboarding/train-agent` - Train principal agent
- `GET /api/v1/onboarding/status` - Get onboarding status

#### Agents
- `GET /api/v1/agents/` - List organization agents
- `GET /api/v1/agents/{agent_id}` - Get agent details

#### Health
- `GET /health` - Basic health check
- `GET /api/v1/health/detailed` - Detailed system health

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Write comprehensive tests for new features
- Update documentation for API changes
- Use type hints throughout the codebase
- Follow async/await patterns for I/O operations

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the documentation and FAQ

## 🔮 Roadmap

### Phase 1 (Current)
- ✅ Core platform and onboarding
- ✅ Multi-LLM routing
- ✅ Document processing
- ✅ Agent training system

### Phase 2 (Next)
- 🔄 Frontend dashboard (Next.js)
- 🔄 Real-time chat interface
- 🔄 Advanced integrations (Gmail, Slack, WhatsApp)
- 🔄 Performance analytics

### Phase 3 (Future)
- 📅 Multi-agent collaboration
- 📅 Custom tool integration
- 📅 Advanced workflow automation
- 📅 Enterprise features