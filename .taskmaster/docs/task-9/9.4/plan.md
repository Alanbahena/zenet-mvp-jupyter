# Subtask 9.4 — Exports (`core/agents/__init__.py` + `core/__init__.py`)

## Context

Adds `ConfigurationAgent` and `ConsistencyCheckAgent` to the package public APIs so
downstream code and tests can import them from the package root.

**Prior (9.3):** Section UI implemented. Both agents currently imported directly from
their modules (`core.agents.configuration_agent`, `core.agents.consistency_check_agent`).

**Next (9.5):** Test file imports agents via the package root
(`from core.agents import ConfigurationAgent, ConsistencyCheckAgent`).
Exports must exist before the test file is written.

---

## Files to Modify

| File | Action | Summary |
|------|--------|---------|
| `core/agents/__init__.py` | Modify | Add imports + `__all__` entries for both agents |
| `core/__init__.py` | Modify | Add both agents to `from core.agents import ...` and `__all__` |

---

## Dependencies

- 9.1 done — `core/agents/configuration_agent.py` with `ConfigurationAgent`
- 9.2 done — `core/agents/consistency_check_agent.py` with `ConsistencyCheckAgent`
- Both files are import-clean (verified during 9.3 execution)

---

## Current State of Target Files

### `core/agents/__init__.py` (current)

```python
from core.agents.base_agent import BaseAgent
from core.agents.classification_agent import ClassificationAgent
from core.agents.simple_agent import RestaurantInfoAgent
from core.agents.utils import AgentRegistry, create_agent
from core.agents.welcome_agent import WelcomeAgent

__all__ = ["BaseAgent", "ClassificationAgent", "RestaurantInfoAgent", "WelcomeAgent", "create_agent", "AgentRegistry"]
```

### `core/__init__.py` (current, agents section — line 109)

```python
from core.agents import BaseAgent, ClassificationAgent, RestaurantInfoAgent, WelcomeAgent, create_agent, AgentRegistry
```

`__all__` agents block (lines 217–223):
```python
    # agents
    "BaseAgent",
    "ClassificationAgent",
    "RestaurantInfoAgent",
    "WelcomeAgent",
    "create_agent",
    "AgentRegistry",
```

---

## Implementation Steps

### 1. `core/agents/__init__.py`

Add two import lines after the existing agent imports, in alphabetical order:

```python
from core.agents.base_agent import BaseAgent
from core.agents.classification_agent import ClassificationAgent
from core.agents.configuration_agent import ConfigurationAgent          # add
from core.agents.consistency_check_agent import ConsistencyCheckAgent  # add
from core.agents.simple_agent import RestaurantInfoAgent
from core.agents.utils import AgentRegistry, create_agent
from core.agents.welcome_agent import WelcomeAgent

__all__ = [
    "AgentRegistry",
    "BaseAgent",
    "ClassificationAgent",
    "ConfigurationAgent",       # add
    "ConsistencyCheckAgent",    # add
    "create_agent",
    "RestaurantInfoAgent",
    "WelcomeAgent",
]
```

### 2. `core/__init__.py`

Extend line 109 to include both new agents:

```python
from core.agents import (
    AgentRegistry,
    BaseAgent,
    ClassificationAgent,
    ConfigurationAgent,
    ConsistencyCheckAgent,
    create_agent,
    RestaurantInfoAgent,
    WelcomeAgent,
)
```

Add both to the `# agents` block in `__all__`:

```python
    # agents
    "AgentRegistry",
    "BaseAgent",
    "ClassificationAgent",
    "ConfigurationAgent",
    "ConsistencyCheckAgent",
    "create_agent",
    "RestaurantInfoAgent",
    "WelcomeAgent",
```

---

## Test Coverage

No standalone tests for this subtask. Re-export correctness is validated implicitly
by the 9.5 test file, which imports via the package root. A quick smoke-check import
after implementation is sufficient:

```bash
uv run python -c "from core.agents import ConfigurationAgent, ConsistencyCheckAgent; print('OK')"
uv run python -c "from core import ConfigurationAgent, ConsistencyCheckAgent; print('OK')"
```

---

## Out of Scope

- Logic changes to either agent
- Changes to any other `__init__.py` file
- Changes to `gradio_app/`
- Tests (9.5)
- Documentation (9.6)

---

## Deliverable Checklist

### `core/agents/__init__.py`
- [ ] `ConfigurationAgent` imported from `core.agents.configuration_agent`
- [ ] `ConsistencyCheckAgent` imported from `core.agents.consistency_check_agent`
- [ ] Both names present in `__all__`

### `core/__init__.py`
- [ ] `ConfigurationAgent` added to `from core.agents import ...`
- [ ] `ConsistencyCheckAgent` added to `from core.agents import ...`
- [ ] Both names present in `__all__` under `# agents`
