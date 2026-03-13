# Subtask 8.5 — Exports

## Context

Adds `ClassificationAgent` to the two-level re-export chain so downstream code and
tests can import it via `from core.agents import ClassificationAgent` or
`from core import ClassificationAgent`. Follows the WelcomeAgent pattern from Task 7.5.

**Prior:** 8.4 delivered the full Clasificación section UI. `clasificacion.py` currently
imports `ClassificationAgent` directly from `core.agents.classification_agent` — this
subtask makes the canonical import path available.

**Next:** 8.6 tests import `ClassificationAgent` via `core.agents` — must be exported
before the test file is written.

---

## Files to Modify

| File | Action | Summary |
|------|--------|---------|
| `core/agents/__init__.py` | Modify | Add `ClassificationAgent` import + `__all__` entry |
| `core/__init__.py` | Modify | Add `ClassificationAgent` to agents import line + `__all__` entry |

---

## Dependencies

- 8.1 done — `ClassificationAgent` exists at `core/agents/classification_agent.py`
- No new packages or env vars required

---

## Design Decisions

### Decision 1: Follow WelcomeAgent pattern exactly

Same import style and `__all__` placement as Task 7.5 — consistency across all agents
in the two-level export chain.

---

## Implementation Steps

### 1. `core/agents/__init__.py`

Add after the `WelcomeAgent` import line:

```python
from core.agents.classification_agent import ClassificationAgent
```

Add `"ClassificationAgent"` to `__all__` after `"WelcomeAgent"`:

```python
__all__ = ["BaseAgent", "RestaurantInfoAgent", "WelcomeAgent", "ClassificationAgent", "create_agent", "AgentRegistry"]
```

### 2. `core/__init__.py`

Extend the agents import line to include `ClassificationAgent`:

```python
from core.agents import BaseAgent, ClassificationAgent, RestaurantInfoAgent, WelcomeAgent, create_agent, AgentRegistry
```

Add `"ClassificationAgent"` to the `# agents` section of `__all__` after `"WelcomeAgent"`:

```python
    # agents
    "BaseAgent",
    "RestaurantInfoAgent",
    "WelcomeAgent",
    "ClassificationAgent",
    "create_agent",
    "AgentRegistry",
```

---

## Plan Completeness

| Category | Status |
|----------|--------|
| Unit tests | Not needed — import correctness verified by 8.6's `test_agent_instantiates_via_factory` |
| Live tests | Not applicable |
| Error handling | Not applicable — pure re-export |
| Status updates | Covered in 8.7 |
| Documentation | Not applicable — no new public API beyond the export itself |

---

## Out of Scope

- No changes to any other file
- No changes to `clasificacion.py` (direct import is valid and can stay as-is)
- No new agent logic

---

## Risks and Open Questions

None identified.

---

## Deliverable Checklist

### `core/agents/__init__.py`
- [ ] `from core.agents.classification_agent import ClassificationAgent` added
- [ ] `"ClassificationAgent"` added to `__all__`

### `core/__init__.py`
- [ ] `ClassificationAgent` added to agents import line
- [ ] `"ClassificationAgent"` added to `__all__` under `# agents` section
