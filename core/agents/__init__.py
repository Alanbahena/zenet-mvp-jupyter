"""
Agent framework for Zenet MVP 0.1.

Provides BaseAgent and concrete agent implementations used across
the notebook pipeline (Tasks 7-12).
"""

from core.agents.alignment_agent import AlignmentAgent
from core.agents.base_agent import BaseAgent
from core.agents.classification_agent import ClassificationAgent
from core.agents.configuration_agent import ConfigurationAgent
from core.agents.consistency_check_agent import ConsistencyCheckAgent
from core.agents.simple_agent import RestaurantInfoAgent
from core.agents.structuring_agent import StructuringAgent
from core.agents.utils import AgentRegistry, create_agent
from core.agents.welcome_agent import WelcomeAgent
from core.agents.manual_operativo_agent import ManualOperativoAgent

__all__ = [
    "AgentRegistry",
    "AlignmentAgent",
    "BaseAgent",
    "ClassificationAgent",
    "ConfigurationAgent",
    "ConsistencyCheckAgent",
    "create_agent",
    "ManualOperativoAgent",
    "RestaurantInfoAgent",
    "StructuringAgent",
    "WelcomeAgent",
]
