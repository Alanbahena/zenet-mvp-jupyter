# Subtask 5.5 — Agent Utilities, Error Handling, and Recovery

## Context

Subtask 5.5 adds supporting infrastructure: a factory function for creating agents,
a registry for tracking active agents, and robust error handling with exponential
backoff retry for transient LLM API failures.

**Prior subtask (5.4):** Delivered `RestaurantInfoAgent` — the first concrete
production agent, validating that `BaseAgent` can be subclassed and that structured
output extraction works end-to-end.

**Next subtask (5.6):** Comprehensive test coverage for the full agent framework.
Subtask 5.6 will rely on `create_agent()` to instantiate agents in tests and
`AgentRegistry` for workflow-level tests.

---

## Files to Modify / Create

| File | Action | Summary |
|------|--------|---------|
| `core/agents/utils.py` | Create | `_RETRYABLE_TYPE_NAMES`, `_is_retryable()`, `create_agent()`, `AgentRegistry` |
| `core/agents/base_agent.py` | Modify | Add `import time`, import `_is_retryable`, add `_generate_with_retry()`, add empty response check, update `_generate_response()` docstring |
| `core/agents/__init__.py` | Modify | Export `create_agent` and `AgentRegistry` |

---

## Design Decisions

### Decision 1: `_is_retryable()` uses class name matching, not isinstance

**Choice:** `type(exc).__name__ in _RETRYABLE_TYPE_NAMES` where `_RETRYABLE_TYPE_NAMES`
is a `frozenset[str]`.

**Rationale:** Both `anthropic` and `openai` SDKs expose identically-named error
classes (e.g. `RateLimitError`) but they are distinct types from distinct packages.
Checking by class name avoids importing both SDKs in `utils.py` and decouples retry
logic from provider-specific exception hierarchies. This means `utils.py` has no
dependency on either SDK.

---

### Decision 2: Circular import resolved via lazy import + TYPE_CHECKING guard

**Choice:** `utils.py` declares `from core.agents.base_agent import BaseAgent` only
under `if TYPE_CHECKING` (for annotations). Inside `create_agent()`, the same import
is repeated as a lazy runtime import inside the function body. `AgentRegistry` methods
do not check `isinstance(agent, BaseAgent)` at runtime, so they need no runtime import.

**Rationale:** `base_agent.py` imports `_is_retryable` from `utils.py` at module level.
If `utils.py` also imported `BaseAgent` at module level, a circular import would occur.
The TYPE_CHECKING guard keeps annotations intact for IDEs while breaking the cycle.
The lazy import inside `create_agent()` is the only runtime usage that requires the
actual class object.

---

### Decision 3: `_generate_with_retry()` wraps no-tools path only

**Choice:** Only `provider.generate()` (no-tools path in `_generate_response()`) is
wrapped with retry logic. The tool calling loop (`provider.generate_raw()`) is not
retried in this subtask.

**Rationale:** Retrying mid-loop tool calls requires tracking which tool calls were
already dispatched and whether memory was already mutated. This complexity is deferred
to avoid scope creep. The no-tools path covers the primary use case — it is the path
used by every agent that does not register tools, including `RestaurantInfoAgent`.

---

### Decision 4: Empty response check in no-tools path only

**Choice:** After `_generate_with_retry()` returns, if the result is `""`, raise
`RuntimeError` with the agent name and a descriptive message. The tool loop path
is unchanged.

**Rationale:** The tool loop already handles `raw.text or ""` gracefully — empty text
at an intermediate step means the LLM issued tool calls, which is expected behavior.
The no-tools path has no such fallback; a silent `""` would propagate to
`_process_response()` and produce garbage output with no traceable error.

---

### Decision 5: `AgentRegistry` uses `agent.name` as key, no uniqueness enforcement

**Choice:** `self._agents[agent.name] = agent` — registering a second agent with the
same name silently overwrites the first.

**Rationale:** Task 6 (workflow engine) is the primary consumer of `AgentRegistry`.
The workflow engine is responsible for name collision avoidance. Silent overwrite is
the simplest correct contract; adding a duplicate-name exception here would enforce a
rule that may not apply in all workflow configurations.

---

## Implementation

### `core/agents/utils.py` (Create)

```python
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
```

---

### `core/agents/base_agent.py` (Modify)

**Four changes, in order:**

**1. Add `import time` to the stdlib imports block (after `import json`):**
```python
import json
import time
```

**2. Add `_is_retryable` import after existing `core.ai` imports:**
```python
from core.ai.utils import parse_structured_output
from core.agents.utils import _is_retryable   # <-- add here
```

Note: this import goes in `base_agent.py`, NOT the other way around. `utils.py` does
not import from `base_agent` at module level, so no circular import occurs.

**3. Modify `_generate_response()` no-tools path (add retry + empty response check):**

Before:
```python
if self.tools is None:
    return self.provider.generate(
        prompt=None,
        system=system_prompt,
        messages=self.memory.get_messages(),
        structured_output=self.RESPONSE_MODEL is not None,
    )
```

After:
```python
if self.tools is None:
    result = self._generate_with_retry(
        prompt=None,
        system=system_prompt,
        messages=self.memory.get_messages(),
        structured_output=self.RESPONSE_MODEL is not None,
    )
    if not result:
        raise RuntimeError(
            f"[{self.name}] LLM returned an empty response."
        )
    return result
```

Also update the docstring — remove the stub note:
```
Subtask 5.5 wraps the provider call with retry logic.
```
Replace with:
```
The no-tools path uses _generate_with_retry() with exponential backoff.
The tool calling loop does not retry individual generate_raw() calls.
```

**4. Add `_generate_with_retry()` method in the internal helpers section,
after `_generate_response()`:**

```python
def _generate_with_retry(
    self,
    *,
    max_retries: int = 3,
    **kwargs: Any,
) -> str:
    """
    Generate LLM response with exponential backoff on transient API errors.

    Retries on: RateLimitError, APITimeoutError, APIConnectionError,
                ServiceUnavailableError, InternalServerError, Timeout, ConnectionError.
    Does not retry on: authentication errors, invalid request errors.

    Args:
        max_retries: Maximum number of attempts (default 3). On the final attempt,
                     the exception is re-raised regardless of type.
        **kwargs:    Forwarded to provider.generate(). Must match its signature.

    Returns:
        LLM response string. May be "" if the provider returns no content
        (caller is responsible for checking emptiness).

    Raises:
        Exception: The last exception raised by the provider when all retries
                   are exhausted, or immediately if the error is not retryable.
    """
    delay = 1.0
    for attempt in range(max_retries):
        try:
            return self.provider.generate(**kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            if _is_retryable(e):
                time.sleep(delay)
                delay *= 2
            else:
                raise
```

---

### `core/agents/__init__.py` (Modify)

Add `create_agent` and `AgentRegistry` to the exports:

```python
from core.agents.base_agent import BaseAgent
from core.agents.simple_agent import RestaurantInfoAgent
from core.agents.utils import AgentRegistry, create_agent

__all__ = ["BaseAgent", "RestaurantInfoAgent", "create_agent", "AgentRegistry"]
```

---

## Test Plan

All tests go in `tests/unit/test_agents.py`. Add two new test classes.

**Import additions needed at the top of the test file:**
```python
import unittest.mock
from core.agents.utils import AgentRegistry, _is_retryable, create_agent
```

---

### Class: `TestAgentUtils` (5 tests)

**Test 1: `test_create_agent_returns_correct_instance`**
- Call `create_agent(RestaurantInfoAgent, provider=mock_provider, name="info-agent")`
- Assert result is `RestaurantInfoAgent` instance
- Assert `result.name == "info-agent"` and `result.provider is mock_provider`

**Test 2: `test_create_agent_with_non_baseagent_class_raises_type_error`**
- Call `create_agent(str, provider=mock_provider, name="x")` — `str` is not a BaseAgent
- Assert `TypeError` is raised

**Test 3: `test_agent_registry_register_and_get`**
- Create two agents with names `"agent-a"` and `"agent-b"`
- Register both; call `get("agent-a")` and `get("agent-b")`
- Assert each `get()` returns the correct instance

**Test 4: `test_agent_registry_get_unknown_name_returns_none`**
- Create empty `AgentRegistry`
- Assert `registry.get("nonexistent")` returns `None`

**Test 5: `test_agent_registry_list_names_reflects_registered_agents`**
- Register two agents with names `"alpha"` and `"beta"` (in that order)
- Assert `registry.list_names()` contains both `"alpha"` and `"beta"`
- Do not assert ordering

---

### Class: `TestBaseAgentRetry` (4 tests)

All retry tests must patch `time.sleep` to avoid real delays:
```python
@unittest.mock.patch("core.agents.base_agent.time.sleep")
def test_...(self, mock_sleep):
    ...
```

**Test 6: `test_retry_succeeds_on_transient_error`**

Setup:
- Define a custom `_RateLimitError` exception with `__name__ == "RateLimitError"`:
  ```python
  class _RateLimitError(Exception):
      pass
  _RateLimitError.__name__ = "RateLimitError"
  ```
  Or simpler: define a class named `RateLimitError` directly (its `__name__` is
  already `"RateLimitError"`).
- Subclass `_MockProvider` to raise `RateLimitError` on the first two calls,
  then return a valid JSON string on the third.

Assertions:
- `agent.run(input_data={"user_message": "..."})` succeeds and returns a dict
- `mock_sleep` called exactly 2 times (once per retry before the final success)

**Test 7: `test_retry_raises_after_max_retries_exhausted`**

Setup:
- Mock provider always raises `RateLimitError`.

Assertions:
- `agent.run(...)` raises `RateLimitError`
- `mock_sleep` called exactly 2 times (attempts 0 and 1 sleep; attempt 2 raises)

**Test 8: `test_no_retry_on_non_retryable_error`**

Setup:
- Define `class AuthenticationError(Exception): pass` (name not in `_RETRYABLE_TYPE_NAMES`)
- Mock provider raises `AuthenticationError` on first call.

Assertions:
- `agent.run(...)` raises `AuthenticationError`
- `mock_sleep` called 0 times (no sleep before re-raise)

**Test 9: `test_empty_response_raises_runtime_error`**

Setup:
- `_MockProvider` initialized with `response=""`.

Assertions:
- `agent.run(input_data={"user_message": "..."})` raises `RuntimeError`
- `RuntimeError` message contains the agent name

---

## Out of Scope

- Retry logic for the tool calling loop (`provider.generate_raw()`) — deferred
- Duplicate-name enforcement in `AgentRegistry`
- Agent serialization to dict (beyond existing `save_state`/`load_state`)
- Any changes to `run()`, `_validate_input()`, `_parse_response()`, or `_process_response()`
- Any changes to `RestaurantInfoAgent` or `simple_agent.py`

---

## Risks and Open Questions

1. **Stub note in `_generate_response()` docstring** — the current docstring contains
   `"Subtask 5.5 wraps the provider call with retry logic."` This must be resolved
   (replaced with accurate description) during implementation.

2. **`time.sleep` patch path** — the patch must target `core.agents.base_agent.time.sleep`
   (where `time` is used), not `time.sleep` globally. If the import is `import time`
   (not `from time import sleep`), the patch path is `core.agents.base_agent.time.sleep`.

3. **`_generate_with_retry()` kwargs forwarding** — kwargs are forwarded verbatim to
   `provider.generate()`. A naming mismatch (e.g. `system_prompt` vs `system`) would
   fail silently at runtime and only be caught by a live test. The kwargs in the call
   site inside `_generate_response()` must exactly match `provider.generate()`'s
   parameter names: `prompt`, `system`, `messages`, `structured_output`.

4. **`_is_retryable` import placement in `base_agent.py`** — the import
   `from core.agents.utils import _is_retryable` must be placed after all `core.ai`
   imports to avoid any ordering issues. Verify no circular import occurs by running
   `python -c "from core.agents.base_agent import BaseAgent"` after adding the import.

---

## Deliverable Checklist

### `core/agents/utils.py`
- [ ] `_RETRYABLE_TYPE_NAMES` frozenset defined with 7 exception class names
- [ ] `_is_retryable(exc: Exception) -> bool` function defined
- [ ] `create_agent(agent_class, *, provider, **kwargs)` defined
- [ ] `create_agent()` raises `TypeError` for non-BaseAgent class
- [ ] `create_agent()` contains lazy `from core.agents.base_agent import BaseAgent`
- [ ] `AgentRegistry` class defined
- [ ] `AgentRegistry.register(agent)` stores agent under `agent.name`
- [ ] `AgentRegistry.get(name)` returns agent or `None`
- [ ] `AgentRegistry.list_names()` returns list of registered names
- [ ] `AgentRegistry.clear()` empties the registry

### `core/agents/base_agent.py`
- [ ] `import time` added to stdlib imports block
- [ ] `from core.agents.utils import _is_retryable` added after `core.ai` imports
- [ ] `_generate_with_retry(*, max_retries=3, **kwargs)` method added
- [ ] No-tools path in `_generate_response()` calls `_generate_with_retry()` instead of direct `provider.generate()`
- [ ] Empty response (`not result`) after `_generate_with_retry()` raises `RuntimeError`
- [ ] `_generate_response()` docstring stub note resolved

### `core/agents/__init__.py`
- [ ] `create_agent` imported and added to `__all__`
- [ ] `AgentRegistry` imported and added to `__all__`

### `tests/unit/test_agents.py`
- [ ] `AgentRegistry`, `create_agent` imported at top of file
- [ ] `TestAgentUtils` class with 5 tests added
- [ ] `TestBaseAgentRetry` class with 4 tests added
- [ ] All retry tests patch `core.agents.base_agent.time.sleep`
- [ ] All 9 new tests pass
- [ ] Full test suite (including prior subtask tests) passes
