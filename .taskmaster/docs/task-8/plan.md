# Task 8 — Clasificación Section: Classification Agent + Gradio UI

## Context

Task 8 is the second user-facing section of Zenet MVP 0.1. It diagnoses the operator's
standardization level (1–3) and what documentation they currently have, accumulates a draft
classification via agent conversation, and lets the operator confirm before writing to
DataLake. The result is a routing config that Tasks 9–12 read to adapt their UI.

**Prior task (7):** Delivered the section wiring pattern (save_fn / chat_fn / agent
load-save per turn), `Restaurant` + `User` entities in DataLake, and the session architecture.

**Next task (9 — Configuración):** Reads the `classification` entity to know which sections
show base templates vs. empty tables.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `ClassificationAgent` — conversational diagnosis + structured draft | File upload (PDF, Excel, photos) |
| `classification` persistence (schema + SQLite handlers) | Upload-vs-manual choice per section |
| `render_draft_preview()` reusable component | Modifying `Restaurant` dataclass |
| Clasificación section UI (chat + live preview + confirm) | LangGraph (single agent, no graph) |
| Propose → preview → confirm pattern | Reset / undo of confirmed classification |
| `ClassificationAgent` re-exports | Any Task 9+ section UI |
| Mocked + live tests | |
| Architecture doc + plan.md | |

---

## Architectural Decisions

### Decision 1: Agent leads conversation, proposes level, operator confirms

**Choice:** The agent reads the conversation and proposes a standardization level. The
operator confirms or corrects via chat — not a menu selection.

**Rationale:** Feels like Zenet "interpreting" rather than presenting a form. Consistent
with the companion-agent UX established in Task 7.

---

### Decision 2: Hybrid RESPONSE_MODEL — conversational reply + structured fields

**Choice:** `ClassificationAgent` uses a Pydantic `RESPONSE_MODEL` with `reply: str`
(shown to operator) plus `standardization_level: int | None` and `sections: dict | None`.

**Rationale:** One LLM call per turn produces both the conversational reply and the
structured draft update. Avoids a second extraction call per turn.

---

### Decision 3: Propose → preview → confirm — nothing hits DataLake until confirmed

**Choice:** Agent accumulates draft in `_data_store` across turns. Confirm button triggers
`save_entity("classification", entity_id, ...)`.

**Rationale:** Operator must explicitly approve before data is persisted. Matches the
mental model of "review before committing."

---

### Decision 4: `_data_store` merged incrementally — prior turns never overwritten

**Choice:** `_process_response()` merges new fields into `_data_store` without wiping
existing entries. Early turns may return `None` for some fields.

**Rationale:** The agent may not capture everything in one turn. Conversation builds up
the draft progressively.

---

### Decision 5: `render_draft_preview()` is reusable across Tasks 9–12

**Choice:** Built once in Task 8 in `gradio_app/components.py`. Takes a dict and renders
a live table with a Confirm button.

**Rationale:** Every section from Task 8 onwards follows propose→preview→confirm. Building
it once avoids duplication across six section files.

---

### Decision 6: `classification` stored as JSON blob in SQLite

**Choice:** `id INTEGER PRIMARY KEY, data TEXT NOT NULL` — same pattern as `agent_state`.
Entity_id derived via `abs(hash(session_id)) % (2**31 - 1)`.

**Rationale:** No relational queries needed on classification data. JSON blob is simpler
and consistent with how agent_state is stored.

---

### Decision 7: Chat is the universal input — no upload in Task 8

**Choice:** Clasificación only asks what documentation exists, not how to ingest it.
File upload deferred to Task 10 (Alineamiento).

**Rationale:** Keeps Clasificación focused on diagnosis. Task 10 is already designed for
file ingestion and handles upload natively.

---

## Classification Dict Schema

```python
{
    "standardization_level": 2,       # 1, 2, or 3
    "sections": {
        "recipe_categories": {
            "has_data": True,
        },
        "inventory_families": {
            "has_data": False,
        },
        "recipes": {
            "has_data": True,
        },
        "inventory": {
            "has_data": False,
        },
    },
    "use_templates": {
        "recipe_categories": False,   # has data → don't use template
        "inventory_families": True,   # no data → use base template
        "recipes": False,
        "inventory": True,
    }
}
```

---

## Files to Create/Modify

| File | Action | Summary |
|------|--------|---------|
| `core/agents/classification_agent.py` | Create | `ClassificationAgent` — hybrid structured + conversational |
| `core/storage/schema.py` | Modify | Add `classification` table |
| `core/storage/persistence.py` | Modify | Add `"classification"` to `_SQLITE_ENTITY_TYPES` + handlers |
| `gradio_app/components.py` | Modify | Add `render_draft_preview()` reusable component |
| `gradio_app/sections/clasificacion.py` | Replace stub | Full `render()`: chat + preview + confirm |
| `core/agents/__init__.py` | Modify | Export `ClassificationAgent` |
| `core/__init__.py` | Modify | Export `ClassificationAgent` |
| `tests/unit/test_classification_agent.py` | Create | 12 mocked + 3 live tests |
| `docs/Architecture/sections/clasificacion.md` | Create | Section architecture doc |
| `docs/Architecture/architecture-persistence.md` | Modify | Update SQLite table count (9 → 10) + add `classification` to entity type list |
| `.taskmaster/tasks/tasks.json` | Modify | Subtask status tracking |
| `CLAUDE.md` | Modify | Task 8 status updates |

---

## Subtask Breakdown

### 8.1 — ClassificationAgent (`core/agents/classification_agent.py`)

Create `_ClassificationResponse(BaseModel)` with `reply: str`, `standardization_level: int | None`,
and `sections: dict | None`. Create `ClassificationAgent(BaseAgent)` with
`RESPONSE_MODEL = _ClassificationResponse`.

- `INPUT_SCHEMA`: `{"user_message": "A message from the restaurant operator."}`
- `OUTPUT_SCHEMA`: `{"reply": "Conversational response.", "standardization_level": "Diagnosed level (1/2/3) or None.", "sections": "Dict of section has_data flags or None.", "raw_response": "Full LLM response string."}`
- `_generate_prompt()`: injects restaurant name from context + current `_data_store` draft so agent knows what's already captured
- `_process_response()`: merges non-None structured fields into `_data_store` without overwriting existing entries; returns `reply` and `raw_response`

**Standardization levels the agent diagnoses:**
- **Level 1** — Operation in their head: everything structured from base templates
- **Level 2** — Partially documented: has some Excel, notes, photos, or partial recipes
- **Level 3** — Structured operation: has most categories, recipes, and inventory documented

**Two-phase conversation structure (system prompt must enforce):**

Phase 1 — Level diagnosis (2–3 broad questions):
- How many years has the restaurant been operating?
- On a scale of 1–10, how standardized do you feel your operation is?
- Can you leave for a weekend without the operation falling apart?
- When a new employee joins, how do they learn?

Phase 2 — Section-by-section documentation check (required, drives `use_templates`):
- All 4 sections must be resolved before the agent proposes a final classification
- `recipe_categories`, `inventory_families`, `recipes`, `inventory` — each needs a `has_data` value
- The agent may blend phase 1 and phase 2 questions naturally in conversation

**Impatient operator fallback (system prompt must include):**
- If the operator wants to skip ahead or says "just set it up for me", the agent proposes
  Level 1 with all sections as `has_data: false` as a safe default
- The agent communicates this is a starting point and they can correct it later
- This ensures the confirm button always becomes available even if the conversation is short

---

### 8.2 — Classification persistence (`schema.py` + `persistence.py`)

**`schema.py`:** Add after `agent_state` table:
```python
cursor.execute("""
    CREATE TABLE IF NOT EXISTS classification (
        id INTEGER PRIMARY KEY,
        data TEXT NOT NULL
    )
""")
```

**`persistence.py`:** Add `"classification"` to `_SQLITE_ENTITY_TYPES`. Add save/load/delete/list_ids
handlers using the JSON blob pattern (same as `agent_state`):
- `save`: `INSERT OR REPLACE INTO classification (id, data) VALUES (?, ?)`
- `load`: `SELECT data FROM classification WHERE id = ?` → `json.loads(row[0])`
- `delete`: `DELETE FROM classification WHERE id = ?`
- `list_ids`: `SELECT id FROM classification`

---

### 8.3 — Draft preview component (`gradio_app/components.py`)

Add `render_draft_preview()`:

```python
def render_draft_preview(
    draft: gr.State,
    confirm_fn: Callable,
    session_id: gr.State,
) -> gr.Button:
    ...
```

- Renders `draft` dict as a human-readable `gr.Markdown` block — NOT `gr.JSON`
- The Markdown renderer should translate the raw dict into operator-friendly language:
  - Level shown as "Nivel 1 / 2 / 3" with a one-line description of what that means
  - Each section shown as a labeled row with a plain-language status:
    - `has_data: true` → "Tienes información"
    - `has_data: false` → "Usarás plantilla base"
  - Example output:
    ```
    **Nivel de estandarización:** Nivel 2 — Parcialmente documentado

    | Sección | Estado |
    |---------|--------|
    | Categorías de recetas | Tienes información |
    | Familias de inventario | Usarás plantilla base |
    | Recetas | Tienes información |
    | Inventario | Usarás plantilla base |
    ```
  - When draft is empty or incomplete: show a neutral placeholder ("El asistente irá completando esta sección durante la conversación.")
- Confirm `gr.Button` wired to `confirm_fn(draft_dict, session_id)`
- No-op / greyed-out Confirm button when `standardization_level` is not yet set
- Returns the Confirm button so the calling section can wire additional outputs

---

### 8.4 — Clasificación section UI (`gradio_app/sections/clasificacion.py`)

Replace stub with full `render()`. Layout:

```
gr.Row
├── gr.Column (scale=1) — Chat
│   ├── gr.Markdown("## Asistente de clasificación")
│   └── render_chat_panel(chat_fn, session_id, data_lake)
│
└── gr.Column (scale=1) — Draft preview
    ├── gr.Markdown("## Clasificación propuesta")
    └── render_draft_preview(draft_state, confirm_fn, session_id)
```

**`_make_chat_fn(provider, data_lake)`:** Same load_state/run/save_state pattern as Task 7.
After each turn, updates `gr.State` holding the draft dict so the preview re-renders.

**`_make_confirm_fn(data_lake)`:** Reads current draft from `gr.State`, builds the full
classification dict (adding `use_templates` derived from `has_data` flags), calls
`data_lake.save_entity("classification", entity_id, classification_dict)`. Returns
confirmation status message.

**`_load_classification_context(data_lake, session_id)`:** Loads `Restaurant` entity to
inject `restaurant_name` and `restaurant_type` into agent context.

---

### 8.5 — Exports (`core/agents/__init__.py` + `core/__init__.py`)

Follow the WelcomeAgent pattern from Task 7.5:
- `core/agents/__init__.py`: add `from core.agents.classification_agent import ClassificationAgent` and `"ClassificationAgent"` to `__all__`
- `core/__init__.py`: add `ClassificationAgent` to `from core.agents import ...` and `__all__`

---

### 8.6 — Tests (`tests/unit/test_classification_agent.py`)

**12 mocked tests:**

| Test | Validates |
|------|-----------|
| `test_agent_instantiates_via_factory` | `create_agent(ClassificationAgent, ...)` returns correct type |
| `test_response_model_is_set` | `RESPONSE_MODEL` is not None |
| `test_input_schema_has_user_message` | `"user_message"` in `INPUT_SCHEMA` |
| `test_run_returns_reply` | `result["reply"]` is a non-empty string |
| `test_run_stores_level_in_data_store` | After run with level hint, `agent.retrieve("standardization_level")` is set |
| `test_run_accumulates_sections_across_turns` | Two turns → `_data_store["sections"]` grows |
| `test_context_injects_restaurant_name` | System prompt contains restaurant name from context |
| `test_draft_injected_in_prompt` | Existing `_data_store` appears in system prompt on second turn |
| `test_missing_user_message_raises` | `run(input_data={})` raises `ValueError` |
| `test_save_load_state_preserves_draft` | save_state/load_state preserves `_data_store` in new instance |
| `test_confirm_fn_persists_classification` | `confirm_fn()` calls `save_entity("classification", ...)` |
| `test_confirm_fn_empty_session_returns_error` | `session_id=""` → error message, no DB write |

**3 live tests (guarded by `ANTHROPIC_API_KEY`):**

| Test | Validates |
|------|-----------|
| `test_live_responds_in_spanish` | Reply is Spanish prose, no JSON in output |
| `test_live_diagnoses_level` | After Level 1 description, `standardization_level` set in `_data_store` |
| `test_live_multi_turn_accumulates` | Two turns → `_data_store` has more fields than after one turn |

---

### 8.7 — Documentation and task closure

- Create `docs/Architecture/sections/clasificacion.md` — documents propose→preview→confirm
  as the canonical pattern for Tasks 9–12
- Update `docs/Architecture/architecture-persistence.md`:
  - Change "9 entity tables" → "10 entity tables" in the SqliteStorage section
  - Add `classification` to the `_SQLITE_ENTITY_TYPES` list and note the JSON blob pattern
- Mark subtask 8.7 and Task 8 parent `done` in `tasks.json`
- Update `CLAUDE.md` task status table

---

## Dependencies

- Task 7 marked done ✓
- `data/zenet.db` contains `restaurant` + `user` entities written by Task 7
- `ANTHROPIC_API_KEY` in `.env` for live tests and manual smoke testing
- `core/agents/base_agent.py` — `BaseAgent.run()`, `save_state()`, `load_state()`, `_data_store`
- `core/agents/utils.py` — `create_agent()` factory
- `gradio_app/components.py` — `render_chat_panel()` (used as-is)
- `core/domain/data_model.py` — `DEFAULT_RESTAURANT_TYPES` for context injection
- `core/storage/persistence.py` — `DataLake`, `_SQLITE_ENTITY_TYPES`

**Subtask execution order:**
`8.1 → 8.2 (parallel with 8.3) → 8.3 (parallel with 8.2) → 8.4 (depends on 8.1, 8.2, 8.3) → 8.5 → 8.6 → 8.7`

---

## Risks and Open Questions

### [OPEN] — Preview re-render mechanism
**Problem:** After each chat turn, the preview must re-render with updated `_data_store`.
Requires `gr.State` holding the draft dict to be updated by `chat_fn` return value, chained
via `.then()` to the send button. This is a new Gradio pattern not established in Task 7.
**Suggested action:** Spike this in 8.3/8.4 before committing to the component API.

### [OPEN] — `_ClassificationResponse` None handling
**Problem:** Early turns may return `None` for `standardization_level` and `sections`.
`_process_response()` must merge only non-None fields without wiping prior entries.
**Suggested action:** Use `if value is not None: self.store(key, value)` pattern.

### [OPEN] — `render_chat_panel` incompatible with 3-output chat_fn
**Source:** Validation of Task 8
**Problem:** `render_chat_panel` hardwires `outputs=[chatbot, textbox]`. clasificacion.py's `chat_fn` must return `(history, "", draft_dict)` to update draft state. There is no hook for a 3rd output through the existing component.
**Impact:** Draft gr.State never updates; preview never re-renders; confirm button stays disabled regardless of conversation.
**Suggested action:** In 8.4, build the chat panel inline in `clasificacion.py` (not via `render_chat_panel`) and wire `outputs=[chatbot, textbox, draft_state]` directly. Do NOT modify `render_chat_panel`.

### [OPEN] — `confirm_fn` signature inconsistency
**Source:** Validation of Task 8
**Problem:** Plan spec says "Confirm button wired to `confirm_fn(session_id)`" but `_make_confirm_fn` description says it "reads current draft from gr.State". Only session_id as input makes the draft dict inaccessible.
**Impact:** `confirm_fn` cannot build `use_templates` mapping — the core output of the Clasificación section — without the draft dict.
**Suggested action:** In 8.3/8.4, wire confirm button with `inputs=[draft, session_id]` and use `confirm_fn(draft_dict, session_id) -> str` as the signature.

### [OPEN] — `sections` deep-merge underspecified
**Source:** Validation of Task 8
**Problem:** Plan says "use `if value is not None: self.store(key, value)` pattern" for sections. For a dict value, `store("sections", new_dict)` replaces the entire dict, wiping data from prior turns.
**Impact:** Multi-turn section accumulation silently loses early-turn section data.
**Suggested action:** In 8.1 `_process_response()`, for `sections` specifically: `existing = self.retrieve("sections") or {}; existing.update(new_sections); self.store("sections", existing)`.

### [OPEN] — No type validation on sections dict content
**Source:** Validation of Task 8
**Problem:** `sections: dict | None` accepts any dict. LLM could return unexpected keys or values missing `has_data`.
**Impact:** `use_templates` derivation in `_make_confirm_fn` silently defaults to `True` for malformed sections, persisting wrong routing config.
**Suggested action:** In 8.4, guard `_make_confirm_fn` with explicit per-key `.get("has_data", False)` defaults before computing `use_templates`.

### [OPEN] — standardization_level range not validated
**Source:** Validation of subtask 8.1
**Problem:** `_ClassificationResponse` declares `standardization_level: int | None` with no range constraint. The LLM could return 0, 4, or any integer.
**Impact:** 8.3's preview renderer maps level → "Nivel 1/2/3" label — an out-of-range value produces a blank or broken label. The wrong level would also be persisted to SQLite via confirm_fn.
**Suggested action:** Before implementing 8.3, add a Pydantic `field_validator` in `_ClassificationResponse` clamping `standardization_level` to `{1, 2, 3}` or `None`, OR handle unknown values gracefully in 8.3's Markdown renderer.

### [OPEN] — Entity type count in architecture-persistence.md
**Source:** Validation of subtask 8.2
**Problem:** Parent plan says "9 entity tables → 10" for the 8.7 doc update. `_SQLITE_ENTITY_TYPES` currently has 10 entries. Adding `classification` makes 11, not 10.
**Impact:** `architecture-persistence.md` will be incorrect on first write in 8.7.
**Suggested action:** In 8.7, update `architecture-persistence.md` to read "10 → 11", not "9 → 10". Correct the 8.7 section description in this plan accordingly.

### [OPEN] — No direct SqliteStorage round-trip test for classification
**Source:** Validation of subtask 8.2
**Problem:** 8.6 test table covers `confirm_fn_persists_classification` (DataLake path) but not `SqliteStorage.save/load` directly for `classification`.
**Impact:** A SQL typo or wrong `int()` cast in the new handlers only surfaces at UI test time, not unit test time.
**Suggested action:** Add `test_classification_save_load_round_trip` to 8.6 test plan: `storage.save("classification", 1, dict)` → `storage.load("classification", 1) == dict`.

---

## Verification

```bash
# Mocked tests only
PYTHONPATH=. uv run python -m pytest tests/unit/test_classification_agent.py -k "not live" -v

# Live tests
PYTHONPATH=. uv run python -m pytest tests/unit/test_classification_agent.py -k "live" -v

# Full suite — must not regress
PYTHONPATH=. uv run python -m pytest tests/unit/ -v

# Smoke test
PYTHONPATH=. uv run python -c "from gradio_app.app import build_app; build_app(); print('OK')"
```

---

## Deliverable Checklist

### `core/agents/classification_agent.py`
- [ ] `_ClassificationResponse` Pydantic model with `reply`, `standardization_level`, `sections`
- [ ] `ClassificationAgent` with correct `INPUT_SCHEMA`, `OUTPUT_SCHEMA`, `RESPONSE_MODEL`
- [ ] `_generate_prompt()` injects restaurant context + current `_data_store` draft
- [ ] `_process_response()` merges non-None fields into `_data_store` incrementally

### `core/storage/schema.py`
- [ ] `classification` table added (`id INTEGER PRIMARY KEY, data TEXT NOT NULL`)

### `core/storage/persistence.py`
- [ ] `"classification"` added to `_SQLITE_ENTITY_TYPES`
- [ ] save/load/delete/list_ids handlers for `classification` (JSON blob pattern)

### `gradio_app/components.py`
- [ ] `render_draft_preview()` renders draft dict as human-readable `gr.Markdown` (level + section table in Spanish)
- [ ] Empty/incomplete draft shows neutral placeholder text
- [ ] No-op / greyed-out Confirm button when `standardization_level` is not yet set
- [ ] Returns Confirm button for external wiring

### `gradio_app/sections/clasificacion.py`
- [ ] Stub replaced with full `render()`
- [ ] Chat wired to `ClassificationAgent` (load_state / run / save_state per turn)
- [ ] Draft `gr.State` updated after each chat turn
- [ ] Preview re-renders after each chat turn
- [ ] Confirm button persists classification dict to DataLake

### `core/agents/__init__.py` + `core/__init__.py`
- [ ] `ClassificationAgent` exported from both

### `tests/unit/test_classification_agent.py`
- [ ] 12 mocked tests pass
- [ ] 3 live tests guarded by `ANTHROPIC_API_KEY`
- [ ] Full suite passes: `uv run python -m pytest tests/unit/ -v`

### `docs/Architecture/sections/clasificacion.md`
- [ ] Propose→preview→confirm pattern documented as canonical reference for Tasks 9–12

### `docs/Architecture/architecture-persistence.md`
- [ ] SQLite table count updated (9 → 10)
- [ ] `classification` added to entity type list with JSON blob pattern noted

### `.taskmaster/tasks/tasks.json` + `CLAUDE.md`
- [ ] All subtask statuses tracked
- [ ] Task 8 marked done on completion
