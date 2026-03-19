# Configuracion Section Architecture

## 1. Overview

The Configuracion section is the third tab in the pipeline. It guides the operator through
configuring the structural skeleton of their restaurant's data model: recipe categories,
inventory families, recipe units, and inventory units — all in a single continuous conversation.

Layout: **two-column** — chat on the left, sequential step UI on the right.

Data produced by this section:

| Entity | Entity type | Used by |
|--------|-------------|---------|
| Recipe categories | `category_recipe` | Tasks 10–12 to classify extracted recipes |
| Inventory families | `family_inventory` | Tasks 10–12 to group ingredients by product type |
| Recipe units | `recipe_unit` | Tasks 10–12 to parse ingredient quantities |
| Inventory units | `inventory_unit` | Tasks 10–12 to normalize stock and purchase quantities |
| Agent conversation state | `agent_state` | Resumed on next chat turn |

**Implementation files:**

| File | Role |
|------|------|
| `gradio_app/sections/configuracion.py` | `render()`, `_make_chat_fn()`, `_make_confirm_fn()`, step UI, context loader, persistence helpers |
| `core/agents/configuration_agent.py` | `ConfigurationAgent` — conversational agent for all 4 steps |
| `core/agents/consistency_check_agent.py` | `ConsistencyCheckAgent` — structural and semantic validation |

---

## 2. Sequential Step Pattern

Four steps in fixed order, one visible at a time:

```
categories → families → recipe_units → inventory_units
```

The right column shows: progress indicator at top, current step title, entity table
(`gr.Dataframe`), confirm button, and status area below.

### Module-level constants

| Constant | Purpose |
|----------|---------|
| `_STEP_KEYS` | `["categories", "families", "recipe_units", "inventory_units"]` — canonical step order |
| `_STEP_ENTITY_TYPES` | DataLake entity type strings parallel to `_STEP_KEYS` |
| `_STEP_TITLES` | Spanish display titles per step |
| `_STEP_DESCRIPTIONS` | One-line Spanish description per step (used in status messages) |
| `_STEP_COLUMNS` | Dict keys for extracting values from entity dicts per step |
| `_STEP_COLUMN_LABELS` | Spanish display headers for `gr.Dataframe` per step |
| `_STEP_COLUMN_WIDTHS` | Percentage widths for `gr.Dataframe` columns per step |
| `_ENTITY_BUILDERS` | Lambda dict mapping step key to entity constructor |

### Entity table

```python
gr.Dataframe(
    headers=_STEP_COLUMN_LABELS["categories"],
    column_widths=_STEP_COLUMN_WIDTHS["categories"],
    wrap=True,
    interactive=False,
)
```

- `interactive=False` — all edits go through chat, not direct cell editing
- `wrap=True` — long descriptions wrap within cells
- Headers and widths update dynamically via `gr.update()` on step change
- `is_standard` field is not displayed to the operator (internal system flag)

### Resume on load

`_init_section(data_lake) -> int` checks `data_lake.list_entity_ids()` for each entity
type. Steps with existing entities are skipped. Returns the index of the first incomplete
step (0–3), or 4 if all complete.

---

## 3. ConfigurationAgent

Single agent across all 4 steps. Continuous conversation — context from earlier steps
carries forward naturally.

### `_data_store` schema

```python
{
    "current_step": "categories",   # set by _generate_prompt(), read by _process_response()
    "categories":     [{"name": str, "description": str | None}, ...],
    "families":       [{"name": str, "description": str | None}, ...],
    "recipe_units":   [{"name": str, "symbol": str, "description": str | None}, ...],
    "inventory_units": [{"name": str, "symbol": str, "is_standard": bool, "description": str | None}, ...],
}
```

### Level-based tone

- **Level 1:** Build from scratch with templates. Explain each entity's purpose. Encouraging.
- **Level 2/3:** Present template as suggestion. Invite adjustments. More concise.

### Conversation triggers

| Trigger | When sent | Agent behavior |
|---------|-----------|---------------|
| Regular message | Operator types in chat | Normal conversation about current step |
| `__confirmed__` | After confirm saves a step | Introduce the next step with template preview, ask to start |
| `__issues__:` | After consistency check finds problems | Acknowledge issues, propose corrected `entities` list, ask to proceed |

Trigger messages are sent silently — only the assistant reply appears in the chatbot.
No user message is shown for triggers.

### Memory injection

On the first chat turn, the static initial greeting is injected into agent memory
(`agent.memory.add_assistant(initial_greeting_text)`) so the agent continues naturally
instead of re-greeting.

### Description field rules

- Always filled — never null unless operator explicitly asks
- Short, operator-facing: "what goes in here?"
- No costs, calculations, or Zenet internals
- Recipe units: describe what the unit measures, no equivalences (conversion is ingredient-dependent)
- Non-standard inventory units: note that equivalence will be defined later

### Symbol field rules

- Always required for recipe and inventory units
- Standard kitchen abbreviations: g, kg, L, ml, pza, cda, cdta, tza, oz, lb

---

## 4. ConsistencyCheckAgent

Stateless agent. Two call modes, different input schemas.

### Per-step check

Called before confirming each step (steps 0–2).

Input: `{"step": str, "entities": list[dict], "restaurant_type": str}`

Checks:
- Structural gaps (e.g. no liquid unit, fewer than N entities)
- Semantic relevance (e.g. "azucar" is an ingredient, not a recipe category)

### Final cross-entity check

Called before confirming the last step (step 3).

Input: `{"categories": list, "families": list, "recipe_units": list, "inventory_units": list, "restaurant_type": str}`

Checks cross-list compatibility (e.g. recipe units use "taza" but no standard volume
inventory unit exists).

### Response model

```python
class _ConsistencyCheckResponse(BaseModel):
    issues: list[str]       # blocking structural gaps
    suggestions: list[str]  # optional improvements
    looks_good: bool        # True if no blocking issues
```

---

## 5. Consistency Check + Agent Correction Flow

The confirm button uses a generator pattern for intermediate loading states.

```
Operator clicks Confirm
    │
    ▼
yield "Verificando consistencia..." (intermediate state)
    │
    ▼
ConsistencyCheckAgent runs (LLM call)
    │
    ├── looks_good=True ──► save entities ──► agent fires __confirmed__ ──► next step
    │
    └── looks_good=False
            │
            ▼
        Warning shown in status_md
            │
            ▼
        yield warning (intermediate state)
            │
            ▼
        ConfigurationAgent fires with __issues__: trigger
            │
            ▼
        Agent proposes corrected entities ──► table updates
            │
            ▼
        issues_ack resets to False (corrected list gets re-validated on next confirm)
```

If the agent returns no entities after `__issues__:`, `issues_ack` stays `True` — operator
can override with a second click.

`show_progress="hidden"` is set on the confirm button click to suppress Gradio's default
orange outline loading indicators.

---

## 6. Persistence

### `_save_step(data_lake, step_key, draft)`

Assigns sequential IDs starting from 1. Calls `data_lake.save_entity_obj()` for each
entity. Uses `_ENTITY_BUILDERS[step_key]` to construct the correct dataclass instance.

### `_load_configuration_context(data_lake, session_id) -> dict`

Loads from DataLake:
- `restaurant` entity → `restaurant_type_id`, `restaurant_type`, `restaurant_name`
- `classification` entity → `standardization_level` (defaults to 1 if missing)

Returns a dict consumed by `ConfigurationAgent._generate_prompt()` and
`ConsistencyCheckAgent` input construction.

### Non-standard units

Non-standard inventory units (`is_standard=False`) are saved with `factor_to_base=1.0`
as a placeholder. Equivalences are discovered in Task 10 (Alineamiento) when processing
actual recipes and purchase orders.

---

## 7. Status Messages

After a successful save, `status_md` shows:

```
**{saved step title}** guardadas. Siguiente: **{next step title}** — {next step description}.
```

On the final step:

```
**{last step title}** guardadas. Configuracion completa — ya puedes continuar con Alineamiento.
```

`_STEP_DESCRIPTIONS` provides the one-line description per step:
- categories: "agrupan tus recetas por tipo de servicio o turno"
- families: "agrupan tus ingredientes por tipo de producto"
- recipe_units: "son las unidades que aparecen en tus listas de ingredientes"
- inventory_units: "son las unidades con las que compras y controlas tu stock"

---

## 8. Gradio Wiring

Same single-handler pattern as Task 8 (no `gr.State.change()`).

### `_chat_and_format`

Wired to `send_btn.click()`. Returns 11 values: chatbot history, textbox clear, 4 draft
states, step_complete flag, confirm button update, entity table update, progress markdown,
step title.

### `_confirm_and_advance`

Generator function wired to `confirm_btn.click()`. Yields intermediate loading states
before the final result. Returns 13 values: chatbot history, status, issues_ack, step
index, step_complete, confirm button, entity table, progress, step title, 4 draft states.

---

## 9. Error Handling

| Scenario | Where caught | User sees |
|----------|-------------|-----------|
| Empty session_id (chat) | `chat_fn` guard | Error appended to history |
| Empty message | `chat_fn` guard | No-op |
| All steps complete (chat) | `chat_fn` guard | "Configuracion completa" message |
| Agent API failure (chat) | `chat_fn` try/except | "Hubo un problema al conectar con el asistente." |
| Empty session_id (confirm) | `confirm_fn` guard | "Sesion no iniciada. Recarga la pagina." |
| Consistency check failure | `confirm_fn` try/except | Falls back to `looks_good=True` (save proceeds) |
| Agent transition failure | `_confirm_and_advance` try/except | No transition message, step still advances |

---

## See Also

- [Clasificacion Section Architecture](clasificacion.md) — prior section, propose-preview-confirm pattern
- [Agent Framework Architecture](../architecture-agent-framework.md) — `BaseAgent`, `save_state`, `load_state`
- [Gradio and LangGraph Architecture](../architecture-gradio-and-langgraph.md) — session model, `render()` contract
- [Persistence Architecture](../architecture-persistence.md) — `DataLake`, entity types
