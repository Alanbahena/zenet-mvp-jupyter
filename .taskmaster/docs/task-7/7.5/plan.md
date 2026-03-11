# Subtask 7.5 — Exports and task status

## Context

**Parent task:** Task 7 — Bienvenida Section: Welcome Agent + Onboarding Form
**Source of truth:** `.taskmaster/docs/task-7/plan.md` §7.5

Adds `WelcomeAgent` to the public re-export chain so downstream code (Tasks 8–12
and tests) can import it from `core` or `core.agents` directly. Also updates task
tracking to reflect the current state of Task 7.

**Prior (7.4):** Full error handling and validation in `bienvenida.py` — all
bienvenida logic is complete.

**Next (7.6):** Test imports (`from core import WelcomeAgent` or
`from core.agents import WelcomeAgent`) must resolve before the test file is written.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `WelcomeAgent` added to `core/agents/__init__.py` | Any other agent re-exports (Tasks 8–12) |
| `WelcomeAgent` added to `core/__init__.py` | Architecture doc updates |
| Subtask 7.5 marked `done` in `tasks.json` | Marking task 7 parent `done` (requires 7.6 + 7.7) |
| Task 7 row updated in `CLAUDE.md` to `in-progress` | Marking Task 7 `done` in `CLAUDE.md` (deferred to 7.7) |

---

## Architectural Decisions

### Decision 1: Two-level export chain

**Choice:** `welcome_agent.py` → `core/agents/__init__.py` → `core/__init__.py`

**Rationale:** Matches the existing pattern for `BaseAgent`, `RestaurantInfoAgent`,
`create_agent`, and `AgentRegistry`. Callers can import from either level depending
on how specific they want to be.

---

### Decision 2: Task 7 parent not marked `done` here

**Choice:** Only subtask 7.5 is marked `done` in `tasks.json`. Task 7 parent
remains `in-progress`.

**Rationale:** Subtasks 7.6 (tests) and 7.7 (documentation) are still pending.
Marking the parent done before tests exist would misrepresent the actual state.

---

### Decision 3: CLAUDE.md row split

**Choice:** The current single row `| 7–16 | ... | pending |` is split into
`| 7 | ... | in-progress |` and `| 8–16 | ... | pending |`.

**Rationale:** Task 7 is partially complete (7.1–7.5 done, 7.6–7.7 pending).
Grouping it with 8–16 as `pending` is no longer accurate.

---

## Files to Modify

| File | Action | Summary |
|------|--------|---------|
| `core/agents/__init__.py` | Modify | Add `WelcomeAgent` import and `__all__` entry |
| `core/__init__.py` | Modify | Add `WelcomeAgent` to `from core.agents import ...` and `__all__` |
| `.taskmaster/tasks/tasks.json` | Modify | Mark subtask 7.5 `done` |
| `CLAUDE.md` | Modify | Split task row; mark Task 7 `in-progress` |

---

## Current state of affected lines

### `core/agents/__init__.py` (line 9–12)
```python
from core.agents.base_agent import BaseAgent
from core.agents.simple_agent import RestaurantInfoAgent
from core.agents.utils import AgentRegistry, create_agent

__all__ = ["BaseAgent", "RestaurantInfoAgent", "create_agent", "AgentRegistry"]
```

### `core/__init__.py` (line 109 + agents block in `__all__`)
```python
from core.agents import BaseAgent, RestaurantInfoAgent, create_agent, AgentRegistry
# ...
    # agents
    "BaseAgent",
    "RestaurantInfoAgent",
    "create_agent",
    "AgentRegistry",
```

### `CLAUDE.md` (task status table)
```
| 7–16 | Section agents, workflow engine, notebooks, tests, docs | pending |
```

---

## Implementation Steps

### Step 1 — `core/agents/__init__.py`

Add `WelcomeAgent` import and `__all__` entry:

```python
from core.agents.base_agent import BaseAgent
from core.agents.simple_agent import RestaurantInfoAgent
from core.agents.utils import AgentRegistry, create_agent
from core.agents.welcome_agent import WelcomeAgent

__all__ = ["BaseAgent", "RestaurantInfoAgent", "WelcomeAgent", "create_agent", "AgentRegistry"]
```

---

### Step 2 — `core/__init__.py`

**2a.** Extend the agents import line:

```python
from core.agents import BaseAgent, RestaurantInfoAgent, WelcomeAgent, create_agent, AgentRegistry
```

**2b.** Add `"WelcomeAgent"` to `__all__` under the `# agents` block:

```python
    # agents
    "BaseAgent",
    "RestaurantInfoAgent",
    "WelcomeAgent",
    "create_agent",
    "AgentRegistry",
```

---

### Step 3 — `tasks.json`

Set subtask 7.5 `status` → `"done"`. Task 7 parent stays `"in-progress"`.

---

### Step 4 — `CLAUDE.md`

Replace:
```
| 7–16 | Section agents, workflow engine, notebooks, tests, docs | pending |
```

With:
```
| 7 | Bienvenida section agent (subtasks 7.1–7.5 done; 7.6–7.7 pending) | in-progress |
| 8–16 | Section agents, workflow engine, notebooks, tests, docs | pending |
```

---

## Verification

```bash
# Both import paths must resolve
PYTHONPATH=. uv run python -c "
from core import WelcomeAgent
from core.agents import WelcomeAgent
print('OK')
"

# Full smoke test
PYTHONPATH=. uv run python -c "from gradio_app.app import build_app; build_app(); print('App OK')"
```

---

## Deliverable Checklist

### `core/agents/__init__.py`
- [ ] `from core.agents.welcome_agent import WelcomeAgent` added
- [ ] `"WelcomeAgent"` added to `__all__`

### `core/__init__.py`
- [ ] `WelcomeAgent` added to `from core.agents import ...` line
- [ ] `"WelcomeAgent"` added to `__all__` under `# agents` block

### `.taskmaster/tasks/tasks.json`
- [ ] Subtask 7.5 `status` set to `"done"`
- [ ] Task 7 parent remains `"in-progress"`

### `CLAUDE.md`
- [ ] `7–16` row split into Task 7 (`in-progress`) and Tasks `8–16` (`pending`)
