# Subtask 11.6 — Tests

## Goal

Write 12 mocked + 2 live tests for `StructuringAgent` and `_make_confirm_fn`, validating
batch inference, context injection, data store accumulation, and the confirm save path.

- **Prior subtask (11.5) delivered:** `StructuringAgent` exported from `core/__init__.py`.
- **Next subtask (11.7) needs:** a passing test suite to include in the closure report.

---

## Files to Modify / Create

| File | Action | Summary |
|------|--------|---------|
| `tests/unit/test_structuring_agent.py` | Create | 12 mocked + 2 live tests |

---

## Dependencies

- Subtask 11.3 done — `StructuringAgent` importable from `core.agents`
- Subtask 11.4 done — `_make_confirm_fn` exists in `gradio_app/sections/estructura.py`
- Subtask 11.5 done — `from core import StructuringAgent` resolves
- `unittest` (stdlib) — no new packages required

---

## Key design decisions

- Follow `test_alignment_agent.py` patterns exactly: same `_MockProvider`,
  `_make_data_lake`, seed helpers, class grouping, test numbering style.
- Mocked tests use JSON DataLake (no SQLite schema required; faster and stateless).
- `test_confirm_fn_saves_inventory_items` uses JSON DataLake — `_make_confirm_fn` only
  calls `save_entity` / `load_entity` / `list_entity_ids`, no SQL needed.
- Live tests guarded by `@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), ...)`,
  consistent with all other live test classes in the suite.

---

## Implementation steps

### Step 1 — Module header + imports

```python
"""
Tests for StructuringAgent — batch inference, context injection, data store
accumulation, confirm/save flow, and live LLM compliance.

Tests 1–12: mocked (offline, no API key required).
Tests 13–14: live (skipped unless ANTHROPIC_API_KEY is set).
"""
import json
import os
import tempfile
import unittest

from core.agents.structuring_agent import StructuringAgent
from core.agents.utils import create_agent
from core.ai.providers import LlmProvider
from core.domain.data_model import FamilyInventory, InventoryItem, InventoryUnit
from core.domain.serialization import (
    family_inventory_to_dict,
    inventory_item_to_dict,
    inventory_unit_to_dict,
)
from core.storage.persistence import DataLake
from gradio_app.sections.estructura import _make_confirm_fn
```

### Step 2 — DataLake helpers

```python
def _make_data_lake() -> DataLake:
    return DataLake(data_dir=tempfile.mkdtemp())
```

### Step 3 — Response builder

```python
def _structuring_response(
    reply: str = "Ok.",
    proposals: list | None = None,
    gap_questions: list | None = None,
    needs_supplier_doc: bool | None = None,
) -> str:
    return json.dumps({
        "reply":              reply,
        "proposals":          proposals,
        "gap_questions":      gap_questions,
        "needs_supplier_doc": needs_supplier_doc,
    })
```

### Step 4 — Mock provider

Same pattern as `test_alignment_agent.py`:

```python
class _MockProvider(LlmProvider):
    def __init__(self, response: str | None = None) -> None:
        super().__init__(model_name="mock")
        self.response = response or _structuring_response()
        self.last_system: str = ""
        self.call_count: int = 0

    def _do_generate(self, *, prompt, system, tools, structured_output,
                     messages, max_tokens, temperature) -> str:
        self.last_system = system or ""
        self.call_count += 1
        return self.response
```

### Step 5 — Seed helpers

```python
def _seed_inventory_unit(dl: DataLake, uid: int, symbol: str, is_standard: bool = True) -> None:
    iu = InventoryUnit(id=uid, name=symbol, symbol=symbol, is_standard=is_standard, factor_to_base=1.0)
    dl.save_entity("inventory_unit", uid, inventory_unit_to_dict(iu))

def _seed_inventory_item(dl: DataLake, iid: int, name: str, category_id: int = 1) -> None:
    item = InventoryItem(id=iid, name=name, stock_unit_id=1, purchase_unit_id=1, category_id=category_id)
    dl.save_entity("inventory_item", iid, inventory_item_to_dict(item))

def _seed_family_inventory(dl: DataLake, fid: int, name: str) -> None:
    fam = FamilyInventory(id=fid, name=name)
    dl.save_entity("family_inventory", fid, family_inventory_to_dict(fam))
```

### Step 6 — `TestStructuringAgentCore` (tests 1–11)

| # | Test name | Setup | Assertion |
|---|-----------|-------|-----------|
| 1 | `test_create_via_factory` | `create_agent(StructuringAgent, provider=_MockProvider(), name="sa")` | `isinstance(agent, StructuringAgent)`; tool names include `"create_inventory_unit"` and `"create_family_inventory"` |
| 2 | `test_response_model_fields` | mock response with all fields present; `agent.run(...)` | result dict has keys `reply`, `proposals`, `gap_questions`, `needs_supplier_doc`, `raw_response` |
| 3 | `test_bulk_inference_standard_units` | proposals with `purchase_unit_symbol="kg"`, `stock_unit_symbol="kg"`, `purchase_to_stock_factor=1.0`, `confidence="high"`, `gap_questions=[]` | `result["proposals"][0]["purchase_to_stock_factor"] == 1.0`; `result["gap_questions"] == []` |
| 4 | `test_bulk_inference_non_standard_unit` | proposals with `purchase_unit_symbol="caja"`, `stock_unit_symbol="kg"`, `purchase_to_stock_factor=None`, `confidence="missing"`, `gap_questions=["¿Cuántos kg tiene una caja de Pollo?"]` | `result["proposals"][0]["purchase_to_stock_factor"] is None`; `len(result["gap_questions"]) >= 1` |
| 5 | `test_missing_purchase_unit_flag` | mock response with `needs_supplier_doc=True` | `result["needs_supplier_doc"] is True` |
| 6 | `test_no_equivalence_for_pza` | proposals with `purchase_unit_symbol="pza"`, `stock_unit_symbol="pza"`, `purchase_to_stock_factor=1.0`, `gap_questions=[]` | `result["gap_questions"] == []`; `result["proposals"][0]["purchase_to_stock_factor"] == 1.0` |
| 7 | `test_new_item_detection` | proposals with `is_new_item=True` on one item | `result["proposals"][0]["is_new_item"] is True` |
| 8 | `test_data_store_accumulation` | two `agent.run()` turns using `save_state` / `load_state` on a DataLake; second response has new proposals | after second turn, `agent.retrieve("proposals")` is non-empty and matches second response proposals |
| 9 | `test_perecedero_category_inference` | proposals with `category_name="Perecedero"` | `result["proposals"][0]["category_name"] == "Perecedero"` |
| 10 | `test_no_perecedero_category_inference` | proposals with `category_name="No perecedero"` | `result["proposals"][0]["category_name"] == "No perecedero"` |
| 11 | `test_context_injection` | `agent.run(context={"restaurant_name": "El Paisa", "restaurant_type": "Taquería", "families": ["Lácteos"], "inventory_units": ["kg"], "inventory_items": ["Pollo"], "category": "Perecedero"})` | `provider.last_system` contains `"El Paisa"` and `"Lácteos"` |

### Step 7 — `TestStructuringConfirm` (test 12)

`test_confirm_fn_saves_inventory_items`:
- Setup: `_make_data_lake()`, seed `inventory_unit` "kg" id=1, seed `inventory_item` "Pollo" shell
  (stock_unit_id=1, purchase_unit_id=1, category_id=1)
- Run:
  ```python
  confirm_fn = _make_confirm_fn(dl)
  rows = [["Pollo", "kg", "kg", 1.0, "", "Perecedero"]]
  results = list(confirm_fn(rows, "test_session", "Perecedero"))
  ```
- Assert: `results[-1][1] is True` (success); reload "Pollo" from DataLake →
  `entity["stock_unit_id"] == 1` and `entity["purchase_to_stock_factor"] == 1.0`

### Step 8 — `TestStructuringAgentLive` (tests 13–14)

Decorated `@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY not set")`.

`test_live_bulk_inference_taqueria`:
- Run real Claude call with context `restaurant_type="Taquería"`, `inventory_items=["Bistec", "Limón", "Cilantro"]`, `category="Perecedero"`
- Assert: `result["proposals"]` non-empty; each proposal has `stock_unit_symbol` and `purchase_unit_symbol`

`test_live_gap_question_non_standard_unit`:
- Run real Claude call describing an item with clearly non-standard purchase unit (e.g. "caja de 10 kg de harina")
- Assert: `result["gap_questions"]` non-empty OR `result["proposals"][0]["purchase_to_stock_factor"] is None`

---

## Edge cases

- `test_data_store_accumulation`: `self.store("proposals", proposals)` is a REPLACE, not append.
  The test must assert that `agent.retrieve("proposals")` matches the *latest* batch only.
- `test_confirm_fn_saves_inventory_items`: `results[-1]` is the final generator yield
  `(status_string, True)`. Assert `results[-1][1] is True`, not on the exact status string,
  to avoid fragility on message wording.
- Tool registration: `test_create_via_factory` checks tool names via `agent._tool_registry`
  or `list(agent._tools.keys())` — use whichever attribute `BaseAgent` exposes.

---

## Out of scope

- Tests for `_load_structuring_context` — covered implicitly by `test_context_injection`
- Tests for `_initial_greeting`, `_proposals_to_rows` — trivial pure functions
- Tests for Gradio event wiring — not unit-testable without a browser
- Tests for `create_inventory_unit` / `create_family_inventory` tool implementations

---

## Risks and open questions

### Tool registry attribute name
`test_create_via_factory` needs to inspect registered tool names. The exact attribute
on `BaseAgent` that exposes registered tools (e.g. `_tools`, `_tool_registry`, or a
`get_tools()` method) must be verified before writing that assertion. Read
`core/agents/base_agent.py` lines around `register_tool` before implementing.

---

## Deliverable checklist

### `tests/unit/test_structuring_agent.py`
- [ ] `test_create_via_factory`
- [ ] `test_response_model_fields`
- [ ] `test_bulk_inference_standard_units`
- [ ] `test_bulk_inference_non_standard_unit`
- [ ] `test_missing_purchase_unit_flag`
- [ ] `test_no_equivalence_for_pza`
- [ ] `test_new_item_detection`
- [ ] `test_data_store_accumulation`
- [ ] `test_perecedero_category_inference`
- [ ] `test_no_perecedero_category_inference`
- [ ] `test_context_injection`
- [ ] `test_confirm_fn_saves_inventory_items`
- [ ] `test_live_bulk_inference_taqueria` (guarded by `ANTHROPIC_API_KEY`)
- [ ] `test_live_gap_question_non_standard_unit` (guarded by `ANTHROPIC_API_KEY`)
- [ ] `uv run python -m pytest tests/unit/test_structuring_agent.py -v` passes (12 mocked, 2 skipped or passing)
