"""
AgentOS Specialized Agents Module

This module contains the specialized agent implementations for various business tasks.
"""

from .base_agent import BaseAgent, AgentCapability, AgentContext, AgentConfig
from .copywriter_agent import CopywriterAgent
from .researcher_agent import ResearcherAgent
from .scheduler_agent import SchedulerAgent
from .email_responder_agent import EmailResponderAgent
from .data_analyzer_agent import DataAnalyzerAgent

__all__ = [
    "BaseAgent",
    "AgentCapability",
    "AgentContext",
    "AgentConfig",
    "CopywriterAgent",
    "ResearcherAgent",
    "SchedulerAgent",
    "EmailResponderAgent",
    "DataAnalyzerAgent"
]