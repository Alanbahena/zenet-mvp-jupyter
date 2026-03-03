"""
Agent framework for Zenet MVP 0.1.

Provides BaseAgent and concrete agent implementations used across
the notebook pipeline (Tasks 7-12).
"""

from core.agents.base_agent import BaseAgent
from core.agents.simple_agent import RestaurantInfoAgent

__all__ = ["BaseAgent", "RestaurantInfoAgent"]
