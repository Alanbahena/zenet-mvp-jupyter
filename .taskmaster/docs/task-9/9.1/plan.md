# Subtask 9.1 — ConfigurationAgent (`core/agents/configuration_agent.py`)

## Context

Creates the single agent that handles the full 4-step configuration conversation
(categories → families → recipe units → inventory units) in one continuous session.
Runs in parallel with 9.2 (ConsistencyCheckAgent). 9.3 (Section UI) depends on both.

**Prior:** Nothing precedes 9.1 — it is the first subtask.
**Next (9.3) needs:** `ConfigurationAgent` importable from `core.agents`, with `run()`,
`save_state()`, `load_state()`, and `retrieve("current_step")` working correctly.

---

## File to Create

| File | Action | Summary |
|------|--------|---------|
| `core/agents/configuration_agent.py` | Create | `_ConfigurationResponse` + `ConfigurationAgent` |

---

## Dependencies

- `core/agents/base_agent.py` — `BaseAgent`, `store()`, `retrieve()`, `_parse_response()`,
  `save_state(data_lake, *, session_id=)`, `load_state(data_lake, *, session_id=)`
- `core/domain/data_model.py` — `get_category_recipe_template(restaurant_type_id: int)`,
  `get_family_inventory_template(...)`, `get_recipe_unit_template(...)`,
  `get_inventory_unit_template(...)` — all take `int`, return `tuple[Entity, ...]`
- `pydantic` — `BaseModel`
- `core/agents/utils.py` — `create_agent()` factory (for tests)
- 9.2 (`ConsistencyCheckAgent`) is NOT a dependency — 9.1 and 9.2 run in parallel

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| One agent for all 4 steps | Single `ConfigurationAgent` | Agent remembers context from categories when discussing families — conversation continuity |
| `RESPONSE_MODEL` | `_ConfigurationResponse` (structured output) | Enables extraction of `entities` list and `step_complete` flag alongside the conversational reply |
| `entities: list[dict] \| None` | `None` means no change — preserve existing draft | Prevents overwriting a confirmed list on every conversational turn |
| `step_complete: bool \| None` | LLM signals readiness; UI reacts by enabling confirm button | Explicit handoff — UI does not guess when the agent is done |
| `current_step` stored in `_data_store` | Set in `_generate_prompt()`, read in `_process_response()` | `_process_response()` receives only the response string — no context; the store bridges the gap |

---

## _data_store Schema

```python
{
    "current_step":    "categories",   # "categories" | "families" | "recipe_units" | "inventory_units"
    "categories":      [{"name": str, "description": str | None}, ...],
    "families":        [{"name": str, "description": str | None}, ...],
    # Note: FamilyInventory has base_unit_id: Optional[int] = None.
    # Do not include it in the dict — it defaults to None. Task 10 sets real values.
    "recipe_units":    [{"name": str, "symbol": str, "description": str | None}, ...],
    "inventory_units": [{"name": str, "symbol": str, "is_standard": bool, "description": str | None}, ...],
    # Note: InventoryUnit has base_unit_id=None and factor_to_base=1.0 as defaults.
    # Non-standard units are saved with factor_to_base=1.0 placeholder. Task 10 sets equivalences.
}
```

`save_state` / `load_state` persists all keys together under
`"configuration_agent_{session_id}"`.

---

## Context Dict Contract

`_generate_prompt()` reads the following keys from `context`:

| Key | Type | Source (9.3) | Required |
|-----|------|--------------|----------|
| `restaurant_type_id` | `int` | `_load_configuration_context()` — must return this | Yes — needed by template getters |
| `restaurant_type` | `str` | `_load_configuration_context()` | Yes — injected into prompt |
| `restaurant_name` | `str` | `_load_configuration_context()` | Optional |
| `standardization_level` | `int` | `_load_configuration_context()` | Yes — controls agent tone |
| `current_step` | `str` | `gr.State` resolved by UI before `agent.run()` call | Yes — selects template and store key |

**Important:** The parent plan's `_load_configuration_context()` return dict omits
`restaurant_type_id`. This must be added in 9.3 before the agent can call the template
getters. The agent must not perform the name→id lookup internally.

---

## Implementation Prompt

### Reference implementation

Before writing anything, read `core/agents/classification_agent.py` in full.
`ConfigurationAgent` follows the exact same structural pattern:
module docstring → `_SYSTEM_PROMPT` constant → `_ResponseModel(BaseModel)` →
`Agent(BaseAgent)` with `INPUT_SCHEMA`, `OUTPUT_SCHEMA`, `RESPONSE_MODEL`,
`_generate_prompt()`, `_process_response()`.

Also read:
- `core/agents/base_agent.py` lines 77–100 — abstract method signatures for
  `_generate_prompt` and `_process_response`
- `core/domain/data_model.py` lines 148–340 — the four template getter functions
  and the entity dataclasses (`CategoryRecipe`, `FamilyInventory`, `RecipeUnit`,
  `InventoryUnit`)

### File structure (in this exact order)

```
module docstring
imports
_SYSTEM_PROMPT constant
_STEP_TEMPLATE_MAP dict
_STEP_LABELS dict
_ConfigurationResponse(BaseModel)
ConfigurationAgent(BaseAgent)
```

### Imports

```python
from __future__ import annotations

import json
from typing import Any, ClassVar

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent
from core.domain.data_model import (
    get_category_recipe_template,
    get_family_inventory_template,
    get_inventory_unit_template,
    get_recipe_unit_template,
)
```

### `_SYSTEM_PROMPT`

Write it as a triple-quoted string constant. It must contain all of the following
sections, in this order:

**Role:** You are Zeni, Zenet's configuration assistant. Your role is to guide the
restaurant operator through the structural setup of their data model — recipe categories,
inventory families, recipe units, and inventory units — in a single conversation.

**What each entity is for (include all four):**
- *Categorías de recetas:* Groupings that organize recipes for reports and analysis
  (e.g. Desayunos, Comidas, Bebidas). Zenet uses them to calculate readiness and cost
  by category.
- *Familias de inventario:* Groupings for inventory items (e.g. Lácteos, Carnes,
  Verduras). They define the base unit for deduction and cost tracking per product type.
- *Unidades de receta:* The units used inside recipe ingredient lists (e.g. g, kg,
  taza, cucharada). They must match how recipes are written.
- *Unidades de inventario:* The units used when purchasing and tracking stock (e.g. kg,
  L, caja, bolsa). Standard units (kg, g, L, ml, pza) have universal conversions;
  non-standard units (caja, bolsa) will be mapped to standard units later.

**Level-based behavior (this section is critical):**
- Level 1 — "Operación en la cabeza": Operator likely has no existing lists. Walk
  through the template step by step. Explain why each suggested item exists. Invite
  additions or removals. Be encouraging — this is probably the first time they've
  structured this.
- Level 2/3 — "Parcialmente documentado / Estructurado": Operator has some context.
  Present the template as "what Zenet suggests for your type of restaurant" and ask
  them to confirm, adjust, or add. Be more concise.

**Conversation rules:**
- Always in Spanish. Warm, direct tone — like a knowledgeable colleague, not a form.
- 2–4 sentences per reply. Never list everything at once without asking first.
- Work on exactly one step at a time. Never reference another step until the current
  one is confirmed.
- When the operator seems satisfied with the current list (confirms, says "sí", "bien",
  "así está bien", "continua") or explicitly wants to skip: set `step_complete: true`.
- If the operator wants to skip without reviewing: accept the template as-is, set
  `entities` to the template list, set `step_complete: true`.
- If the operator asks what something is for: explain it in 1–2 sentences in plain
  language.

**Response format (final section of system prompt):**
```
Responde SIEMPRE con JSON usando exactamente estos tres campos:
- "reply": tu respuesta conversacional (nunca JSON dentro de este campo)
- "entities": la lista propuesta de entidades para el paso actual como array de objetos,
  o null si no hay cambios respecto al borrador anterior
- "step_complete": true cuando el operador ha confirmado el paso actual, null en caso contrario
```

### `_STEP_TEMPLATE_MAP` and `_STEP_LABELS`

```python
_STEP_TEMPLATE_MAP: dict[str, Any] = {
    "categories":      get_category_recipe_template,
    "families":        get_family_inventory_template,
    "recipe_units":    get_recipe_unit_template,
    "inventory_units": get_inventory_unit_template,
}

_STEP_LABELS: dict[str, str] = {
    "categories":      "Categorías de recetas",
    "families":        "Familias de inventario",
    "recipe_units":    "Unidades de receta",
    "inventory_units": "Unidades de inventario",
}
```

### `_ConfigurationResponse`

```python
class _ConfigurationResponse(BaseModel):
    reply: str
    entities: list[dict] | None = None
    step_complete: bool | None = None
```

No validators needed. `entities=None` is the "no change" signal — it must remain
`None` in the model default (do not default to `[]`).

### `ConfigurationAgent`

```python
class ConfigurationAgent(BaseAgent):
    """
    Conversational configuration agent for the Configuración section.

    Guides the operator through four sequential steps: recipe categories,
    inventory families, recipe units, and inventory units. Runs as a single
    continuous session so context from earlier steps carries forward.

    Each turn may update the draft entity list for the current step via the
    `entities` field and signal readiness via `step_complete`. The UI uses
    `step_complete` to enable the confirm button; confirmed entities are
    persisted to DataLake by the section UI (not by this agent).

    Input:
        user_message: A message from the restaurant operator.

    Context (all provided by the section UI before calling run()):
        restaurant_type_id:    int  — used to load the correct template
        restaurant_type:       str  — injected into prompt for display
        restaurant_name:       str  — injected into prompt for display
        standardization_level: int  — controls agent tone (1 vs 2/3)
        current_step:          str  — "categories" | "families" |
                                      "recipe_units" | "inventory_units"

    Output:
        reply:         Conversational response shown to the operator.
        entities:      Proposed entity list for the current step, or None.
        step_complete: True when agent judges current step ready to confirm.
        raw_response:  Full LLM response string.
    """

    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "A message from the restaurant operator.",
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "reply":         "Conversational response shown to the operator.",
        "entities":      "Proposed entity list for current step, or None if no update.",
        "step_complete": "True when agent judges current step ready to confirm.",
        "raw_response":  "Full LLM response string.",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = _ConfigurationResponse
```

### `_generate_prompt()`

```python
def _generate_prompt(
    self,
    input_data: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str]:
    restaurant_type_id: int = context.get("restaurant_type_id", 1)
    restaurant_type: str = context.get("restaurant_type", "")
    restaurant_name: str = context.get("restaurant_name", "")
    level: int = context.get("standardization_level", 1)
    current_step: str = context.get("current_step", "categories")

    # Store current_step so _process_response() knows which key to write to.
    # _process_response() receives only the response string — no context.
    self.store("current_step", current_step)

    # Load template for current step and format as a readable list for the prompt.
    template_fn = _STEP_TEMPLATE_MAP.get(current_step)
    template_items = template_fn(restaurant_type_id) if template_fn else ()
    template_lines = []
    for item in template_items:
        if hasattr(item, "symbol"):
            template_lines.append(f"- {item.name} ({item.symbol})")
        else:
            template_lines.append(f"- {item.name}")
    template_preview = "\n".join(template_lines) if template_lines else "(sin plantilla)"

    # Build context block appended to the system prompt.
    context_parts: list[str] = ["## Contexto del operador"]
    if restaurant_name:
        context_parts.append(f"Restaurante: {restaurant_name}")
    if restaurant_type:
        context_parts.append(f"Tipo: {restaurant_type}")
    context_parts.append(f"Nivel de estandarización: {level}")
    context_parts.append(
        f"Paso actual: {_STEP_LABELS.get(current_step, current_step)}\n"
        f"Plantilla sugerida:\n{template_preview}"
    )

    # Inject existing draft if the operator has already built a list this session.
    existing = self.retrieve(current_step)
    if existing:
        context_parts.append(
            "Borrador actual (ya revisado en esta conversación):\n"
            + json.dumps(existing, ensure_ascii=False, indent=2)
        )

    system = _SYSTEM_PROMPT + "\n\n" + "\n\n".join(context_parts)
    return system, input_data["user_message"]
```

### `_process_response()`

```python
def _process_response(self, response: str) -> dict[str, Any]:
    data = self._parse_response(response)

    # Retrieve the step that was active when _generate_prompt() ran.
    current_step = self.retrieve("current_step")
    entities = data.get("entities")

    # Only overwrite the stored draft when the LLM returned a non-null entities list.
    # None means "no change" — the existing draft is preserved.
    if entities is not None and current_step is not None:
        self.store(current_step, entities)

    return {
        "reply":         data.get("reply", ""),
        "entities":      entities,
        "step_complete": data.get("step_complete"),
        "raw_response":  response,
    }
```

### Constraints

- Do not call `dataclasses.asdict()` anywhere. Template items are formatted with
  `item.name`, `item.symbol` attribute access only (for display in the prompt — not
  for persistence).
- Do not call `self.memory.add_user()` or `self.memory.add_assistant()` — `BaseAgent.run()`
  manages memory.
- Do not persist anything to DataLake inside this agent. Persistence is the UI's
  responsibility (9.3).
- `INPUT_SCHEMA` has exactly one key: `"user_message"`. No other keys are validated.
- The `_SYSTEM_PROMPT` constant must be defined at module level, not inside the class
  or any method.
- `RESPONSE_MODEL = _ConfigurationResponse` — not `None`. This causes the provider to
  enforce JSON output.

---

## Test Coverage (implemented in 9.5)

| Test | Validates |
|------|-----------|
| `test_agent_instantiates_via_factory` | `create_agent(ConfigurationAgent, ...)` returns correct type |
| `test_response_model_is_set` | `RESPONSE_MODEL` is not None |
| `test_run_returns_reply` | `result["reply"]` is non-empty string |
| `test_run_stores_entities_in_data_store` | After run with entities in response, `agent.retrieve("categories")` is populated |
| `test_run_does_not_overwrite_existing_entities` | Second turn with `entities=None` preserves first turn's stored list |
| `test_context_injects_restaurant_type` | System prompt passed to provider contains restaurant type string |
| `test_context_injects_classification_level` | System prompt contains the level number |
| `test_draft_injected_in_prompt` | After storing entities, second `run()` injects existing draft into system prompt |
| `test_save_load_state_preserves_all_steps` | `save_state`/`load_state` round-trip with all four lists populated |
| `test_missing_user_message_raises` | `run(input_data={})` raises `ValueError` |

---

## Out of Scope

- `ConsistencyCheckAgent` — 9.2
- Section UI wiring — 9.3
- Exports (`__init__.py`) — 9.4
- Test file creation — 9.5
- No changes to `base_agent.py`, `data_model.py`, `persistence.py`, `schema.py`

---

## Risks and Open Questions

### [RISK] — `restaurant_type_id` missing from `_load_configuration_context()` return dict
**Problem:** The parent plan's `_load_configuration_context()` (implemented in 9.3) returns
`{"restaurant_type": str, "standardization_level": int, "restaurant_name": str}` — it does NOT
include `restaurant_type_id: int`. The template getters require an integer.
**Impact:** Without `restaurant_type_id` in context, `_generate_prompt()` falls back to
`restaurant_type_id=1` (Casual), ignoring the operator's actual restaurant type.
**Fix:** Add `"restaurant_type_id": int` to the return dict of `_load_configuration_context()`
in 9.3 before wiring the chat handler.

---

## Deliverable Checklist

- [ ] `_ConfigurationResponse` with `reply`, `entities: list[dict] | None`, `step_complete: bool | None`
- [ ] `ConfigurationAgent` with `INPUT_SCHEMA`, `OUTPUT_SCHEMA`, `RESPONSE_MODEL`
- [ ] `_STEP_TEMPLATE_MAP` maps all four step names to the correct getter function
- [ ] `_generate_prompt()` reads `restaurant_type_id` (int) from context and calls template getter
- [ ] `_generate_prompt()` calls `self.store("current_step", current_step)` before returning
- [ ] `_generate_prompt()` injects existing draft via `self.retrieve(current_step)` when present
- [ ] `_process_response()` reads `current_step` via `self.retrieve("current_step")`
- [ ] `_process_response()` only calls `self.store(step, entities)` when `entities is not None`
- [ ] System prompt enforces Spanish, level-based tone, one-step-at-a-time, JSON format
