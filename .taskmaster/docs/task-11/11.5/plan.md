# Subtask 11.5 — Exports

## Goal

Add `StructuringAgent` to `core/__init__.py`'s public API so it is importable from the
top-level `core` package, consistent with all other agents.

- **Prior subtask (11.4) delivered:** full `estructura.py` UI implementation.
- **Next subtask (11.6) needs:** `StructuringAgent` available via `from core import StructuringAgent`
  or `from core.agents import StructuringAgent`.

---

## Files to Modify / Create

| File | Action | Summary |
|------|--------|---------|
| `core/agents/__init__.py` | Already done (11.3) | `StructuringAgent` already imported and in `__all__` — no change needed |
| `core/__init__.py` | Modify | Add `StructuringAgent` to import block and `__all__` |

---

## Dependencies

- Subtask 11.3 done — `StructuringAgent` exists at `core/agents/structuring_agent.py`
- `core/agents/__init__.py` already exports `StructuringAgent` (completed in 11.3)
- No `InventoryUnitEquivalence` cleanup needed in `core/__init__.py` — already absent (removed in 11.2)

---

## Key design decisions

- Add `StructuringAgent` to the existing `from core.agents import (...)` block — consistent
  with all other agents; no new import block needed.
- Insert alphabetically between `RestaurantInfoAgent` and `WelcomeAgent` in both the import
  block and `__all__`.

---

## Implementation steps

### Step 1 — `core/__init__.py` import block

Add `StructuringAgent` to the existing `from core.agents import (...)` block (currently
lines 105–115), between `RestaurantInfoAgent` and `WelcomeAgent`:

```python
from core.agents import (
    AgentRegistry,
    AlignmentAgent,
    BaseAgent,
    ClassificationAgent,
    ConfigurationAgent,
    ConsistencyCheckAgent,
    create_agent,
    RestaurantInfoAgent,
    StructuringAgent,   # ADD
    WelcomeAgent,
)
```

### Step 2 — `core/__init__.py` `__all__` agents section

Add `"StructuringAgent"` between `"RestaurantInfoAgent"` and `"WelcomeAgent"` in the
agents section of `__all__` (currently lines 219–229):

```python
    # agents
    "AgentRegistry",
    "AlignmentAgent",
    "BaseAgent",
    "ClassificationAgent",
    "ConfigurationAgent",
    "ConsistencyCheckAgent",
    "create_agent",
    "RestaurantInfoAgent",
    "StructuringAgent",   # ADD
    "WelcomeAgent",
```

---

## Verification

After implementation, confirm clean import:

```bash
PYTHONPATH=. uv run python -c "from core import StructuringAgent; print('OK')"
```

---

## Out of scope

- Any changes to `core/agents/__init__.py` — already done in 11.3
- Any changes to `gradio_app/` — done in 11.4
- `InventoryUnitEquivalence` removal — already absent from `core/__init__.py`

---

## Risks and open questions

None. This is a 2-line change with no logic.

---

## Deliverable checklist

### `core/agents/__init__.py`
- [x] `StructuringAgent` imported and in `__all__` *(already done in 11.3)*

### `core/__init__.py`
- [ ] `StructuringAgent` added to `from core.agents import (...)` block
- [ ] `"StructuringAgent"` added to `__all__` under agents section
- [ ] `PYTHONPATH=. uv run python -c "from core import StructuringAgent; print('OK')"` passes
