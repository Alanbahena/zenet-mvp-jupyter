# Task 9 — Configuración Section: Configuration Agent + Gradio UI

## Context

Task 9 is the third user-facing section of Zenet MVP 0.1. It guides the operator through
setting up the structural skeleton of their restaurant's data model: recipe categories,
inventory families, standard recipe units, and standard inventory units. This skeleton is
the prerequisite for Task 10 (Alineamiento), which needs categories and units to already
exist in DataLake before it can classify extracted recipes and normalize ingredient quantities.

**Prior task (8):** Delivered `classification` entity in DataLake with `standardization_level`
(1/2/3) and the propose→preview→confirm pattern used as the base for this section.

**Next task (10):** Reads `category_recipe`, `family_inventory`, `recipe_unit`, and
`inventory_unit` entities from DataLake to classify extracted recipes and normalize
ingredient quantities from uploaded files.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `ConfigurationAgent` — one agent, all 4 steps | File upload (Task 10) |
| `ConsistencyCheckAgent` — per-step + final cross-entity checks | Inventory unit equivalences (Task 10) |
| Sequential step UI with progress indicator | `schema.py` changes — entity tables already exist |
| Resume on load — skip completed steps | `persistence.py` changes — handlers already exist |
| Level-based agent tone (Level 1 vs 2/3) | `data_model.py` changes — templates already exist |
| Save via confirm button | Multi-agent LangGraph orchestration |
| Non-standard units saved without equivalences | Progressive tab locking |
| Exports, tests, architecture doc, task closure | Editing confirmed steps from previous sessions |

---

## Key Finding: Persistence Layer Already Complete

**`schema.py` and `persistence.py` require zero changes.**

All four entity types are already fully supported:
- `recipe_unit`, `inventory_unit`, `category_recipe`, `family_inventory` are in `_SQLITE_ENTITY_TYPES`
- Full save/load/delete/list_ids handlers exist in `SqliteStorage`
- Object-Level API (`save_entity_obj` / `load_entity_obj`) supports all four types
- Serializers (`recipe_unit_to_dict`, `category_recipe_to_dict`, etc.) exist in `serialization.py`

Task 9 calls `data_lake.save_entity_obj()` and `data_lake.list_ids()` directly.

**Templates are already fully built in `data_model.py`:**
- `get_category_recipe_template(restaurant_type_id)` → `tuple[CategoryRecipe, ...]`
- `get_family_inventory_template(restaurant_type_id)` → `tuple[FamilyInventory, ...]`
- `get_recipe_unit_template(restaurant_type_id)` → `tuple[RecipeUnit, ...]`
- `get_inventory_unit_template(restaurant_type_id)` → `tuple[InventoryUnit, ...]`

All template entries use `id=0`. Task 9 assigns sequential integer IDs starting from 1
when saving to DataLake.

---

## Architectural Decisions

### Decision 1: One ConfigurationAgent across all four steps

**Choice:** A single `ConfigurationAgent` handles the full configuration conversation —
categories, families, recipe units, and inventory units — in one continuous session.

**Rationale:** Conversation continuity. The agent remembers context from the Categorías
discussion when it gets to Familias ("you mentioned your restaurant focuses on lunch —
that should shape your inventory families too"). Four separate agents would reset this
context at each step boundary.

---

### Decision 2: Separate ConsistencyCheckAgent

**Choice:** A dedicated `ConsistencyCheckAgent` handles all structural checks — called
once per step (per-step check) and once at the end (final cross-entity check).

**Rationale:** Different input schema, output schema, and prompt from `ConfigurationAgent`.
Keeping it separate follows single-responsibility and makes each agent testable in isolation.

---

### Decision 3: Sequential step UI — one entity type at a time

**Choice:** Right column shows one step at a time: progress indicator at top, single
entity table below, confirm button at bottom. Confirm saves current step and advances
to next.

**Rationale:** The agent converses about one entity type at a time. A UI showing all four
tables simultaneously (tabs or otherwise) would create a mismatch between where the
conversation is and what the operator is looking at. Sequential keeps agent and UI in sync.

---

### Decision 4: Per-step consistency check + final cross-entity check

**Choice:** Before each confirm, `ConsistencyCheckAgent` checks the current step's
entities for structural gaps. On the final step confirm, it also runs a cross-entity
check across all four lists.

**Rationale:** Per-step checks catch issues when they're cheapest to fix — the operator
is still looking at that entity type. The final check catches cross-entity issues (e.g.
recipe units with no inventory unit equivalent) that only become visible when all four
lists are seen together.

---

### Decision 5: Save via confirm button

**Choice:** Confirm button triggers the consistency check and, after operator approval,
persists entities to DataLake. No agent-triggered save.

**Rationale:** Explicit operator control. Consistent with the pattern established in
Tasks 7 and 8. The operator must consciously commit before data is written.

---

### Decision 6: Resume on load

**Choice:** On section init, check DataLake via `list_ids()` for each entity type. Steps
with existing entities are marked complete and skipped. Section opens at the first
incomplete step.

**Rationale:** Operators may complete Categorías one day and return the next. Restarting
from scratch would destroy already-confirmed data.

---

### Decision 7: Level-based agent tone, not level-based UI

**Choice:** Level 1 and Level 2/3 use the same UI. The agent tone differs:
Level 1 — "vamos a construir esto juntos desde las plantillas base."
Level 2/3 — "aquí está lo que Zenet sugiere para tu tipo de restaurante — ajusta lo
que no cuadre."

**Rationale:** Same screens reduces implementation complexity. The meaningful difference
is the agent's conversational approach, not the layout. Templates are pre-loaded for all
levels — Level 1 operators just need more guidance accepting them.

---

### Decision 8: Classification fallback to Level 1

**Choice:** If no `classification` entity exists in DataLake when Task 9 loads, default
to Level 1.

**Rationale:** Safe default. Never blocks the section from rendering. The agent's guidance
at Level 1 is the most thorough, so it's the right fallback for an unknown state.

---

### Decision 9: Non-standard units saved without equivalences

**Choice:** Non-standard inventory units (`is_standard=False`: caja, bolsa, bote, etc.)
are saved to DataLake with `factor_to_base=1.0` as a placeholder. Equivalences are
not asked in Task 9.

**Rationale:** Operators don't know equivalences in the abstract. They discover them
when looking at actual recipes and purchase orders in Task 10. Asking "1 caja = how
many kg?" in Task 9 produces guesses, not real data.

---

## _data_store Schema for ConfigurationAgent

```python
{
    "current_step": "categories",   # "categories" | "families" | "recipe_units" | "inventory_units"
    "categories":     [{"name": str, "description": str | None}, ...],
    "families":       [{"name": str, "description": str | None}, ...],
    "recipe_units":   [{"name": str, "symbol": str, "description": str | None}, ...],
    "inventory_units": [{"name": str, "symbol": str, "is_standard": bool, "description": str | None}, ...],
}
```

`save_state` / `load_state` persists all five keys together under
`"configuration_agent_{session_id}"`.

---

## Files to Create / Modify

| File | Action | Summary |
|------|--------|---------|
| `core/agents/configuration_agent.py` | Create | ConfigurationAgent — one agent, all 4 steps |
| `core/agents/consistency_check_agent.py` | Create | ConsistencyCheckAgent — per-step + final checks |
| `gradio_app/sections/configuracion.py` | Modify | Replace stub with full render() |
| `core/agents/__init__.py` | Modify | Export both new agents |
| `core/__init__.py` | Modify | Export both new agents |
| `tests/unit/test_configuration_agent.py` | Create | 16 mocked + 3 live tests |
| `docs/Architecture/sections/configuracion.md` | Create | Section architecture doc |
| `docs/Architecture/architecture-agent-framework.md` | Modify | Mark ConfigurationAgent done |
| `docs/Architecture/architecture-gradio-and-langgraph.md` | Modify | Mark Configuración done in section table |
| `.taskmaster/tasks/tasks.json` | Modify | Mark all Task 9 subtasks and parent done |
| `CLAUDE.md` | Modify | Update Task 9 status to done, advance to Task 10 |

---

## Subtask Breakdown

### 9.1 — ConfigurationAgent (`core/agents/configuration_agent.py`)

Create `_ConfigurationResponse(BaseModel)`:
```python
class _ConfigurationResponse(BaseModel):
    reply: str
    entities: list[dict] | None = None   # current step's proposed entity list
    step_complete: bool | None = None    # True when agent judges step ready to confirm
```

Create `ConfigurationAgent(BaseAgent)`:
- `INPUT_SCHEMA`: `{"user_message": "A message from the restaurant operator."}`
- `OUTPUT_SCHEMA`: `{"reply": str, "entities": list[dict] | None, "step_complete": bool | None}`
- `RESPONSE_MODEL`: `_ConfigurationResponse`
- `_generate_prompt()`: injects restaurant type, classification level, current step name,
  template defaults for current step, and current `_data_store` draft
- `_process_response()`: if `entities` is not None, stores to `_data_store[current_step]`;
  if None, preserves existing entries

**System prompt must enforce:**
- Always Spanish, warm tone
- Level 1: build from scratch with templates, explain each entity's purpose
- Level 2/3: present template as suggestion, invite operator to adjust
- One topic at a time — do not jump between steps
- When operator seems satisfied, set `step_complete: true`
- If operator wants to skip: accept template as-is and set `step_complete: true`

---

### 9.2 — ConsistencyCheckAgent (`core/agents/consistency_check_agent.py`)

Create `_ConsistencyCheckResponse(BaseModel)`:
```python
class _ConsistencyCheckResponse(BaseModel):
    issues: list[str]        # structural gaps found
    suggestions: list[str]   # optional improvements
    looks_good: bool         # True if no blocking issues
```

Create `ConsistencyCheckAgent(BaseAgent)`:
- Per-step call input: `{"step": str, "entities": list[dict], "restaurant_type": str}`
- Final call input: `{"categories": list, "families": list, "recipe_units": list, "inventory_units": list, "restaurant_type": str}`

**Per-step checks (examples):**
- Categorías: missing expected categories for restaurant type
- Familias: no family for perishables, no family for cleaning supplies
- Recipe units: no liquid unit (ml/L), no weight unit (g/kg)
- Inventory units: no standard weight or volume unit

**Final cross-entity checks (examples):**
- Recipe units include "taza" / "cucharada" but no equivalent inventory unit
- Families configured but no recipe categories that correspond

---

### 9.3 — Configuración section UI (`gradio_app/sections/configuracion.py`)

Replace stub with full `render()`. Layout:

```
gr.Row
├── gr.Column (scale=1) — Chat
│   ├── gr.Markdown("## Asistente de configuración")
│   ├── gr.Chatbot (value=_INITIAL_GREETING)
│   ├── gr.Textbox
│   └── gr.Button("Enviar")
│
└── gr.Column (scale=1) — Sequential step UI
    ├── gr.Markdown  ← progress indicator: [Categorías ✓] → [Familias →] → [Unidades R] → [Unidades I]
    ├── gr.Markdown  ← current step title
    ├── gr.Dataframe ← entity table for current step (read-only display)
    ├── gr.Button("Confirmar y continuar")  ← disabled until step_complete
    └── gr.Markdown  ← status / consistency check results
```

**State vars:**
```python
current_step     = gr.State(0)          # 0=categories, 1=families, 2=recipe_units, 3=inv_units
draft_categories = gr.State([])
draft_families   = gr.State([])
draft_recipe_units = gr.State([])
draft_inv_units  = gr.State([])
step_complete    = gr.State(False)
```

**`_load_configuration_context(data_lake, session_id) -> dict`:**
- Loads `restaurant` entity → `restaurant_type_id`, `name`
- Loads `classification` entity → `standardization_level` (default 1 if missing)
- Returns `{"restaurant_type": str, "standardization_level": int, "restaurant_name": str}`

**`_init_section(data_lake, session_id) -> int`:**
- Calls `data_lake.list_ids()` for each entity type
- Returns index of first incomplete step (0–3), or 4 if all complete

**`_make_chat_fn(provider, data_lake)`:**
- Same load_state/run/save_state pattern as Tasks 7–8
- Returns `(history, "", updated_draft_for_current_step, step_complete_bool)`

**`_make_confirm_fn(data_lake)`:**
- Runs `ConsistencyCheckAgent` on current step entities
- If `looks_good=False`: shows issues in status markdown, asks operator to confirm anyway
  or continue adjusting (two-click confirm: first click shows issues, second click saves)
- On final confirm: assigns sequential IDs, calls `data_lake.save_entity_obj()` for each entity
- Advances `current_step`; on step 3 final save, runs cross-entity check first

**`_chat_and_format(message, history, session_id, current_step, draft_categories, ...)`:**
Single handler returning all outputs from `send_btn.click()` — same pattern as Task 8.

**Initial greeting:**
```python
_INITIAL_GREETING = [{
    "role": "assistant",
    "content": (
        "Perfecto. Ahora vamos a configurar la estructura base de tu restaurante — "
        "las categorías de recetas, familias de inventario, y unidades de medida. "
        "Esto le permitirá a Zenet organizar toda tu información correctamente. "
        "Empecemos con las categorías de recetas. "
        "Para un restaurante como el tuyo, Zenet sugiere: [template]. ¿Te parece bien o quieres ajustar algo?"
    )
}]
```

---

### 9.4 — Exports

**`core/agents/__init__.py`:**
```python
from core.agents.configuration_agent import ConfigurationAgent
from core.agents.consistency_check_agent import ConsistencyCheckAgent
__all__ = [..., "ConfigurationAgent", "ConsistencyCheckAgent"]
```

**`core/__init__.py`:** Add both to `from core.agents import ...` and `__all__`.

---

### 9.5 — Tests (`tests/unit/test_configuration_agent.py`)

See Test Coverage section below.

---

### 9.6 — Documentation and task closure

- Create `docs/Architecture/sections/configuracion.md`
- Update `docs/Architecture/architecture-agent-framework.md` — mark ConfigurationAgent done
- Update `docs/Architecture/architecture-gradio-and-langgraph.md` — mark Configuración done
- Mark all Task 9 subtasks and parent done in `tasks.json`
- Update `CLAUDE.md`: Task 9 → done, Task 10 → next

---

## Dependencies

- Task 8 marked done ✓
- `core/domain/data_model.py` — entity classes, templates, getter functions (no changes needed)
- `core/storage/persistence.py` — all 4 entity type handlers (no changes needed)
- `core/storage/schema.py` — all 4 entity tables (no changes needed)
- `core/domain/serialization.py` — to_dict/from_dict for all 4 types (no changes needed)
- `core/agents/base_agent.py` — `BaseAgent.run()`, `save_state()`, `load_state()`
- `core/agents/utils.py` — `create_agent()` factory
- `gradio_app/components.py` — no changes; `render_draft_preview()` not used here
- `ANTHROPIC_API_KEY` in `.env` for live tests

**Subtask execution order:**
```
9.1 (ConfigurationAgent)  ┐
9.2 (ConsistencyCheckAgent) ┘ parallel
        ↓
9.3 (Section UI — depends on 9.1 + 9.2)
        ↓
9.4 (Exports — depends on 9.1 + 9.2)
        ↓
9.5 (Tests — depends on 9.4)
        ↓
9.6 (Documentation + closure — depends on 9.5)
```

---

## Test Coverage

### Mocked tests (16)

| Test | Validates |
|------|-----------|
| `test_agent_instantiates_via_factory` | `create_agent(ConfigurationAgent, ...)` returns correct type |
| `test_response_model_is_set` | `RESPONSE_MODEL` is not None |
| `test_run_returns_reply` | `result["reply"]` is non-empty string |
| `test_run_stores_entities_in_data_store` | After run with entities, `_data_store["categories"]` populated |
| `test_run_does_not_overwrite_existing_entities` | Second turn with `entities=None` preserves first turn |
| `test_context_injects_restaurant_type` | System prompt contains restaurant type from context |
| `test_context_injects_classification_level` | System prompt contains standardization level from context |
| `test_draft_injected_in_prompt` | Existing `_data_store` entities appear in system prompt on second turn |
| `test_save_load_state_preserves_all_steps` | `save_state`/`load_state` round-trip preserves all four entity lists |
| `test_missing_user_message_raises` | `run(input_data={})` raises `ValueError` |
| `test_consistency_check_returns_issues` | `ConsistencyCheckAgent.run()` returns `issues` list and `looks_good` bool |
| `test_consistency_check_no_issues_looks_good` | Well-configured step returns `looks_good=True` |
| `test_consistency_check_cross_entity` | Final check with mismatched recipe/inventory units returns relevant issue |
| `test_confirm_fn_persists_entities` | `confirm_fn()` calls `data_lake.save_entity_obj()` for each entity |
| `test_confirm_fn_empty_session_returns_error` | `session_id=""` → error message, no DB write |
| `test_id_assignment_sequential` | Saved entities receive sequential IDs starting from 1 |

### Live tests (3, guarded by `ANTHROPIC_API_KEY`)

| Test | Validates |
|------|-----------|
| `test_live_responds_in_spanish` | Reply is Spanish prose, no raw JSON in output |
| `test_live_proposes_categories_for_casual` | After casual restaurant context, agent proposes relevant categories |
| `test_live_consistency_check_flags_missing_unit` | ConsistencyCheckAgent flags missing liquid unit when none configured |

---

## Risks and Open Questions

### [OPEN] — Two-click confirm flow for consistency issues
**Problem:** When `ConsistencyCheckAgent` finds issues, the confirm button needs a two-stage
flow: first click shows issues, second click saves. The exact Gradio wiring for this
(tracking whether issues have been shown via `gr.State`) needs to be defined during 9.3
implementation.
**Suggested action:** Add `issues_acknowledged = gr.State(False)` to section state. First
confirm click: run check, if issues found set flag and show in status. Second confirm click:
save regardless.

### [OPEN] — `gr.Dataframe` vs `gr.Markdown` table
**Problem:** Session decisions say "visualization as a table." `gr.Dataframe` supports
direct cell editing; `gr.Markdown` table is read-only. If the operator should be able to
edit cells directly (not only through chat), `gr.Dataframe` is needed but adds state sync
complexity between the Dataframe and the draft `gr.State`.
**Suggested action:** Use `gr.Dataframe` with `interactive=False` for MVP — read-only
display, all edits go through chat. Avoids state sync complexity while keeping the table
format.

### [OPEN] — Initial greeting template injection
**Problem:** The initial greeting should show the template for the operator's restaurant
type. But the greeting is a static constant — it can't reference DataLake. It needs to
be generated dynamically in `render()` after loading context.
**Suggested action:** In 9.3, make `_INITIAL_GREETING` a function that takes `restaurant_type`
and `template_preview` as arguments, called inside `render()` after `_load_configuration_context()`.

---

## Deliverable Checklist

### `core/agents/configuration_agent.py`
- [ ] `_ConfigurationResponse` with `reply`, `entities`, `step_complete`
- [ ] `ConfigurationAgent` with `INPUT_SCHEMA`, `OUTPUT_SCHEMA`, `RESPONSE_MODEL`
- [ ] `_generate_prompt()` injects restaurant type, classification level, current step, current draft, template defaults
- [ ] `_process_response()` merges entities into `_data_store` without overwriting on None

### `core/agents/consistency_check_agent.py`
- [ ] `_ConsistencyCheckResponse` with `issues`, `suggestions`, `looks_good`
- [ ] Per-step check: single entity list + restaurant type
- [ ] Final check: all four lists for cross-entity validation

### `gradio_app/sections/configuracion.py`
- [ ] Stub replaced with full `render()`
- [ ] Sequential step UI with progress indicator
- [ ] Resume on load — completed steps detected and skipped automatically
- [ ] `_chat_and_format()` single-handler pattern (no `gr.State.change()`)
- [ ] Per-step consistency check before confirm (two-click flow for issues)
- [ ] Final cross-entity check before last save
- [ ] All entities persisted with sequential IDs starting from 1
- [ ] Classification fallback to Level 1 when entity missing

### `core/agents/__init__.py` + `core/__init__.py`
- [ ] `ConfigurationAgent` and `ConsistencyCheckAgent` exported from both

### `tests/unit/test_configuration_agent.py`
- [ ] 16 mocked tests pass
- [ ] 3 live tests guarded by `ANTHROPIC_API_KEY`
- [ ] Full suite passes: `uv run python -m pytest tests/unit/ -v`

### `docs/Architecture/sections/configuracion.md`
- [ ] Sequential step pattern documented
- [ ] Consistency check pattern documented
- [ ] Resume behavior documented
- [ ] `_data_store` schema documented

### `docs/Architecture/architecture-agent-framework.md`
- [ ] `ConfigurationAgent` marked done

### `docs/Architecture/architecture-gradio-and-langgraph.md`
- [ ] Configuración row updated to `**done** (Task 9)`

### `.taskmaster/tasks/tasks.json` + `CLAUDE.md`
- [ ] All 4 existing Task 9 subtask entries marked `"done"`
- [ ] Parent Task 9 marked `"done"`
- [ ] Task 10 noted as next

---

### [OPEN] — tasks.json Task 9 subtasks don't match plan structure
**Source:** Validation of task 9
**Problem:** tasks.json has 4 pre-existing Task 9 subtasks (old design: notebooks, validation.py, equivalences) that don't correspond to plan subtasks 9.1–9.6. Prior "both sets" language in the checklist (inherited from Task 8) does not apply here — there is only one set.
**Impact:** Implementer in 9.6 may be confused about which entries to mark done and whether to create new entries for 9.1–9.6.
**Suggested action:** In 9.6, mark all 4 existing Task 9 subtask entries done and mark parent done. No need to create new subtask entries. "Both sets" language has been corrected to "all 4 existing entries" above.
