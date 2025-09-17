from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class AgentOSException(Exception):
    """Base exception for AgentOS"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class DatabaseException(AgentOSException):
    """Database operation exceptions"""
    pass


class AuthenticationException(AgentOSException):
    """Authentication related exceptions"""
    pass


class AuthorizationException(AgentOSException):
    """Authorization related exceptions"""
    pass


class ValidationException(AgentOSException):
    """Data validation exceptions"""
    pass


class DocumentProcessingException(AgentOSException):
    """Document processing exceptions"""
    pass


class AgentTrainingException(AgentOSException):
    """Agent training related exceptions"""
    pass


class LLMException(AgentOSException):
    """LLM provider exceptions"""
    pass


class VectorStoreException(AgentOSException):
    """Vector store related exceptions"""
    pass


class OnboardingException(AgentOSException):
    """Onboarding process exceptions"""
    pass


# HTTP Exception helpers
def raise_bad_request(message: str, details: Optional[Dict[str, Any]] = None):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"message": message, "details": details or {}}
    )


def raise_unauthorized(message: str = "Authentication required"):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"message": message},
        headers={"WWW-Authenticate": "Bearer"}
    )


def raise_forbidden(message: str = "Insufficient permissions"):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"message": message}
    )


def raise_not_found(message: str, resource: str = "Resource"):
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"message": message, "resource": resource}
    )


def raise_conflict(message: str, details: Optional[Dict[str, Any]] = None):
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"message": message, "details": details or {}}
    )


def raise_unprocessable_entity(message: str, errors: Optional[Dict[str, Any]] = None):
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"message": message, "errors": errors or {}}
    )


def raise_internal_server_error(message: str = "Internal server error", details: Optional[Dict[str, Any]] = None):
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"message": message, "details": details or {}}
    )