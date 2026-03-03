"""
Agent utilities for Zenet MVP 0.1.

Provides:
    _RETRYABLE_TYPE_NAMES  -- frozenset of exception class names that warrant retry
    _is_retryable()        -- predicate used by BaseAgent._generate_with_retry()
    create_agent()         -- factory for instantiating concrete agents
    AgentRegistry          -- registry for tracking active agent instances by name
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.agents.base_agent import BaseAgent

from core.ai.providers import LlmProvider


_RETRYABLE_TYPE_NAMES: frozenset[str] = frozenset({
    "RateLimitError",
    "APITimeoutError",
    "APIConnectionError",
    "ServiceUnavailableError",
    "InternalServerError",
    "Timeout",
    "ConnectionError",
})


def _is_retryable(exc: Exception) -> bool:
    """
    Return True if the exception is a transient API error that warrants retry.

    Checks by class name (not isinstance) to avoid importing SDK-specific
    exception types. Covers both anthropic and openai error hierarchies.
    """
    return type(exc).__name__ in _RETRYABLE_TYPE_NAMES


def create_agent(
    agent_class: type[BaseAgent],
    *,
    provider: LlmProvider,
    **kwargs: Any,
) -> BaseAgent:
    """
    Factory function for creating agents.

    Args:
        agent_class: A concrete BaseAgent subclass.
        provider:    LlmProvider instance to use.
        **kwargs:    Additional init args forwarded to agent_class (name, memory, etc.).

    Returns:
        Initialized agent instance.

    Raises:
        TypeError: If agent_class is not a BaseAgent subclass.
    """
    from core.agents.base_agent import BaseAgent  # lazy import -- avoids circular

    if not (isinstance(agent_class, type) and issubclass(agent_class, BaseAgent)):
        raise TypeError(
            f"agent_class must be a BaseAgent subclass, got {agent_class!r}."
        )
    return agent_class(provider=provider, **kwargs)


class AgentRegistry:
    """
    Registry for tracking active agent instances by name.

    Uses agent.name as the dictionary key. Registering a second agent with the
    same name silently overwrites the first.

    Useful for the workflow engine (Task 6) to look up agents by role.
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Add agent to the registry under agent.name."""
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent | None:
        """Return agent by name, or None if not registered."""
        return self._agents.get(name)

    def list_names(self) -> list[str]:
        """Return list of all registered agent names in insertion order."""
        return list(self._agents.keys())

    def clear(self) -> None:
        """Remove all agents from the registry."""
        self._agents.clear()
