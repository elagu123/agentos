from .auth import router as auth_router
from .onboarding import router as onboarding_router
from .agents import router as agents_router
from .health import router as health_router
from .specialized_agents import router as specialized_agents_router
from .orchestration import router as orchestration_router
from .marketplace import router as marketplace_router
from .chat import router as chat_router
from .performance import router as performance_router
from .websocket import router as websocket_router
from .feedback import router as feedback_router
from .security_dashboard import router as security_router

__all__ = [
    "auth_router",
    "onboarding_router",
    "agents_router",
    "health_router",
    "specialized_agents_router",
    "orchestration_router",
    "marketplace_router",
    "chat_router",
    "performance_router",
    "websocket_router",
    "feedback_router",
    "security_router"
]