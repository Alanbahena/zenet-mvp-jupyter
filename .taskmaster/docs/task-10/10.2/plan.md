# Subtask 10.2 — AlignmentAgent

## Goal

Create `AlignmentAgent` — the core agent that extracts recipes from operator conversation
or file content, proposes inventory item shells with per-ingredient equivalents, handles
deduplication against existing inventory, and supports entity creation with operator
confirmation.

**Builds on:** Subtask 10.1 — `STANDARD_RECIPE_UNIT_SYMBOLS`, `RecipeUnitConversionEntry.source`,
`recipe_unit_conversion` persistence, `load_inventory_item_registry()`, and extended
`ingredients_to_display()` all in place.
**Required by:** Subtask 10.3 (LangGraph graph) — needs a fully-working `AlignmentAgent`
class to wrap as LangGraph nodes in the conditional graph.

---

## Dependencies

- Subtask 10.1 `done`
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in `.env`
- File parsing libraries deferred to 10.3/10.4 — conversational path only in this subtask

---

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| Single agent handles extraction + inventory proposal | Simpler, fewer API calls; LLM handles Spanish shorthand naturally in one call |
| LLM-driven deduplication via context injection | Load existing `InventoryItem` names into prompt; LLM matches semantically — no rule-based pipeline |
| `create_entity` tool registered in `__post_init__` via `register_tool()` | Follows BaseAgent tool pattern; `data_lake` stored on `self` during `_generate_prompt()` for tool access |
| Draft accumulates across turns via `self.store()` | Non-None fields from each turn overwrite previous; None fields leave prior values intact |
| `page_index` in INPUT_SCHEMA | Enables multi-recipe file pagination without re-uploading |
| Per-ingredient equivalents proposed by agent | Volume-to-mass is ingredient-specific; agent reasons culinary knowledge and asks operator to confirm |

---

## Files to create

| File | Action | Summary |
|------|--------|---------|
| `core/agents/alignment_agent.py` | Create | Full `AlignmentAgent` with response models, schemas, system prompt, `create_entity` tool, `_process_response` |

---

## Verified signatures (from codebase)

- `BaseAgent.register_tool(name, func, *, description, parameters_schema=None)` — line 417
- `BaseAgent.store(key, value)` — line 168
- `BaseAgent.retrieve(key, default=None)` — line 182
- `BaseAgent._parse_response(response)` — line 257
- `BaseAgent.__post_init__()` — line 67 (calls `super().__post_init__()` not needed — base validates `name`)
- `STANDARD_RECIPE_UNIT_SYMBOLS` — `core.domain.data_model` (added in 10.1)
- `load_inventory_item_registry(data_lake, session_id)` — `core.domain.data_model_utils` (added in 10.1)

---

## Implementation steps

### Step 1 — Imports

```python
from __future__ import annotations

import json
from typing import Any, ClassVar

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent
from core.domain.data_model import STANDARD_RECIPE_UNIT_SYMBOLS
```

---

### Step 2 — Response models (module-private)

```python
class _IngredientProposal(BaseModel):
    name: str
    quantity: float
    unit_symbol: str
    equivalent: str | None = None          # per-ingredient mass equivalent, e.g. "≈ 120 g" for 1 taza de harina
    inventory_link_status: str             # "matched_existing" | "new" | "needs_resolution"
    matched_item_name: str | None = None   # canonical name if matched_existing


class _InventoryProposal(BaseModel):
    name: str                              # canonical inventory item name
    category: str                          # "Perecedero" | "No perecedero"
    family: str | None = None              # FamilyInventory name from context list; null if none fits
    status: str                            # "new" | "matched_existing"


class _AlignmentResponse(BaseModel):
    reply: str
    recipe_name: str | None = None
    recipe_category: str | None = None
    recipe_description: str | None = None
    recipe_steps: list[str] | None = None
    ingredients: list[_IngredientProposal] | None = None
    inventory_proposals: list[_InventoryProposal] | None = None
```

---

### Step 3 — AlignmentAgent class declaration + schemas

```python
class AlignmentAgent(BaseAgent):
    """
    Conversational recipe extraction and inventory proposal agent for the Alineamiento section.

    Extracts recipes from operator messages or uploaded file content, proposes inventory
    item shells from ingredients, handles deduplication against existing inventory, and
    supports entity creation with operator confirmation.

    No-hallucination rule: only extract data present in the file or operator's words.
    Draft accumulates across turns; nothing is persisted until the operator confirms
    via the UI Confirm button.
    """

    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "Message from operator or extracted file content.",
        "recipe_source": "'file_content' or 'conversation'",
        "page_index": "Which recipe in a multi-recipe file (0-based). 0 for single.",
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "reply": "Conversational response in Spanish.",
        "recipe_draft": "Dict with recipe fields for UI preview.",
        "inventory_proposals": "List of dicts for inventory panel.",
        "raw_response": "Full LLM response string.",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = _AlignmentResponse
```

---

### Step 4 — `__post_init__`

Override to register the `create_entity` tool. Call `super().__post_init__()` first to
run BaseAgent's name validation:

```python
def __post_init__(self) -> None:
    super().__post_init__()
    self.register_tool(
        name="create_entity",
        func=self._create_entity_tool,
        description=(
            "Create a new category_recipe, family_inventory, or recipe_unit. "
            "Only call after the operator has explicitly confirmed they want to create it."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["category_recipe", "family_inventory", "recipe_unit"],
                    "description": "Type of entity to create.",
                },
                "name": {
                    "type": "string",
                    "description": "Display name for the new entity.",
                },
                "symbol": {
                    "type": "string",
                    "description": "Symbol (required only for recipe_unit, e.g. 'manojo').",
                },
            },
            "required": ["entity_type", "name"],
        },
    )
```

---

### Step 5 — `_create_entity_tool` method

The tool is a bound method — it references `self._data_lake` which is set during
`_generate_prompt()` before any tool calls can occur.

```python
def _create_entity_tool(
    self,
    entity_type: str,
    name: str,
    symbol: str | None = None,
) -> str:
    """Create a new category_recipe, family_inventory, or recipe_unit.

    Only called after explicit operator confirmation. Saves to DataLake, assigns
    next sequential ID, updates in-memory context, and returns a confirmation string.
    """
    if entity_type not in {"category_recipe", "family_inventory", "recipe_unit"}:
        return f"Error: unknown entity_type '{entity_type}'."

    data_lake = getattr(self, "_data_lake", None)
    if data_lake is None:
        return "Error: data_lake not available — tool called before context was set."

    session_id = getattr(self, "_session_id", "")

    # Load existing entities to determine next ID
    existing_ids = data_lake.list_entity_ids(entity_type)
    next_id = max((int(eid) for eid in existing_ids), default=0) + 1

    # Build and save entity dict
    if entity_type == "category_recipe":
        data_lake.save_entity(entity_type, next_id, {"id": next_id, "name": name})
        self._context["categories"].append(name)
        return f"Categoría '{name}' creada con id {next_id}."

    elif entity_type == "family_inventory":
        data_lake.save_entity(entity_type, next_id, {"id": next_id, "name": name})
        self._context["families"].append(name)
        return f"Familia '{name}' creada con id {next_id}."

    elif entity_type == "recipe_unit":
        if not symbol:
            return "Error: symbol es requerido para recipe_unit."
        data_lake.save_entity(
            entity_type, next_id, {"id": next_id, "name": name, "symbol": symbol}
        )
        self._context["recipe_units"].append(symbol)
        is_nonstandard = symbol not in STANDARD_RECIPE_UNIT_SYMBOLS
        confirmation = f"Unidad '{name}' ({symbol}) creada con id {next_id}."
        if is_nonstandard:
            confirmation += (
                f" Como '{symbol}' no es una unidad estándar, "
                "pregunta al operador cuántos gramos o ml equivale aproximadamente 1 unidad."
            )
        return confirmation

    return "Error: entity_type no reconocido."
```

Note: `self._context` is set in `_generate_prompt()` (step 6) so the tool can read the
live context lists. `self._data_lake` and `self._session_id` are also set there.

---

### Step 6 — `_generate_prompt`

```python
def _generate_prompt(
    self,
    input_data: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str]:
    # Store data_lake reference for create_entity tool
    self._data_lake = context.get("data_lake")
    self._session_id = context.get("session_id", "")
    self._context = context  # tool can append to categories/families/recipe_units lists

    # Build system prompt
    system = _SYSTEM_PROMPT  # module-level constant (see Step 7)

    # Inject restaurant context
    context_parts: list[str] = []
    if context.get("restaurant_name"):
        context_parts.append(f"Restaurante: {context['restaurant_name']}")
    if context.get("restaurant_type"):
        context_parts.append(f"Tipo: {context['restaurant_type']}")
    if context.get("restaurant_description"):
        context_parts.append(f"Descripción: {context['restaurant_description']}")
    if context.get("standardization_level"):
        context_parts.append(f"Nivel de estandarización: {context['standardization_level']}")
    if context.get("categories"):
        context_parts.append(f"Categorías de receta disponibles: {', '.join(context['categories'])}")
    if context.get("families"):
        context_parts.append(f"Familias de inventario disponibles: {', '.join(context['families'])}")
    if context.get("existing_inventory_items"):
        context_parts.append(
            f"Artículos de inventario existentes: {', '.join(context['existing_inventory_items'])}"
        )
    if context.get("recipe_units"):
        context_parts.append(f"Unidades de receta disponibles: {', '.join(context['recipe_units'])}")
    if context.get("inventory_units"):
        context_parts.append(f"Unidades de inventario disponibles: {', '.join(context['inventory_units'])}")

    if context_parts:
        system = system + "\n\n## Contexto del restaurante\n" + "\n".join(context_parts)

    # Inject current draft so agent knows what has already been captured
    draft = self.retrieve("recipe_draft", {})
    if draft:
        system = (
            system
            + "\n\n## Borrador actual (ya capturado en esta conversación)\n"
            + json.dumps(draft, ensure_ascii=False, indent=2)
        )

    # Build user message — include source framing for file content
    page_index = input_data.get("page_index", 0)
    recipe_source = input_data.get("recipe_source", "conversation")
    user_msg = input_data["user_message"]
    if recipe_source == "file_content":
        user_prefix = f"[Contenido de archivo, receta #{page_index + 1}]\n"
        user_msg = user_prefix + user_msg

    return system, user_msg
```

---

### Step 7 — `_SYSTEM_PROMPT` module-level constant

Define before the class. The prompt must enforce these rules (in this order):

1. **Role:** Eres Zeni, asistente de alineamiento de Zenet.
2. **Task:** Extraer recetas y proponer artículos de inventario.
3. **No-hallucination:** Solo extrae información presente en las palabras del operador o en el archivo. No inventes, no asumas, no infieras ingredientes no mencionados.
4. **Pasos de preparación:** Si no encuentras pasos, pregunta una sola vez. Si el operador no los proporciona, `recipe_steps` queda en null. No repitas la pregunta.
5. **Equivalentes por ingrediente:** Para unidades no estándar (taza, cda, cdta, oz, etc.), razona el equivalente en masa por ingrediente. Ejemplo: "1 taza de harina ≈ 120 g", "1 taza de arroz ≈ 185 g". Propón el equivalente y pide confirmación. Nunca apliques una conversión universal de volumen a masa.
6. **Unidades estándar:** Solo `{g, kg, ml, L, pza}` son estándar y no requieren equivalente.
7. **Fallback de unidad de inventario:** Si la unidad de receta no tiene equivalente directo en inventario: sólidos → `g`/`kg`, líquidos → `ml`/`L`, contables → `pza`.
8. **Categoría:** Debe ser exactamente `"Perecedero"` o `"No perecedero"`.
9. **Familia:** Debe ser elegida de la lista de familias del contexto. `null` si ninguna aplica.
10. **Creación de entidades:** Si la receta usa una categoría, familia, o unidad de receta que no está en el contexto, primero propón mapear a una existente. Solo crea una nueva entidad si el operador lo confirma explícitamente. Nunca crees entidades sin confirmación.
11. **Comunicación:** Siempre en español. Tono cercano y directo. Máximo 3-4 oraciones de respuesta conversacional.
12. **Formato JSON:** Siempre responde con los campos del schema — `reply`, `recipe_name`, `recipe_category`, `recipe_description`, `recipe_steps`, `ingredients`, `inventory_proposals`.

---

### Step 8 — `_process_response`

```python
def _process_response(self, response: str) -> dict[str, Any]:
    data = self._parse_response(response)

    # Build recipe_draft — merge non-None fields with existing draft
    existing_draft: dict[str, Any] = self.retrieve("recipe_draft", {})
    new_fields: dict[str, Any] = {}
    for field in ("recipe_name", "recipe_category", "recipe_description", "recipe_steps"):
        val = data.get(field)
        if val is not None:
            new_fields[field] = val

    # Ingredients: overwrite if present, keep existing if None
    # Note: _parse_response() returns dict[str, Any] (already model_dump'd by BaseAgent).
    # list items are already dicts — no .model_dump() needed.
    ingredients = data.get("ingredients")
    if ingredients is not None:
        new_fields["ingredients"] = ingredients   # already list[dict]

    merged_draft = {**existing_draft, **new_fields}
    self.store("recipe_draft", merged_draft)

    # Inventory proposals: overwrite if present
    raw_proposals = data.get("inventory_proposals") or []
    proposals = list(raw_proposals)               # already list[dict]
    self.store("inventory_proposals", proposals)

    return {
        "reply": data.get("reply", ""),
        "recipe_draft": merged_draft,
        "inventory_proposals": proposals,
        "raw_response": response,
    }
```

---

## Test coverage

Tests written in subtask 10.5. Import directly from `core.agents.alignment_agent` until
exports are added in 10.5.

### Mocked tests

| Test | Validates |
|------|-----------|
| `test_extracts_recipe_from_plain_text` | name, category, ingredients parsed from Spanish recipe text |
| `test_matches_existing_inventory_item` | ingredient matched; `inventory_link_status = "matched_existing"` |
| `test_proposes_new_inventory_item_with_category_and_family` | new item gets correct category/family from context |
| `test_nonstandard_unit_per_ingredient_equivalent` | taza de harina → `"≈ 120 g"` in equivalent column |
| `test_per_ingredient_equivalent_differs_by_ingredient` | same unit (taza) → different equivalents for harina vs arroz |
| `test_no_hallucination_on_sparse_input` | agent does not add ingredients not present in source |
| `test_draft_accumulates_across_turns` | `_data_store` retains `recipe_draft` across multiple messages |
| `test_missing_steps_asks_once_then_saves_none` | no steps found → agent asks once; on skip, `steps=None` in draft |
| `test_create_entity_tool_creates_category` | new category saved to DataLake with correct next ID |
| `test_create_entity_tool_creates_recipe_unit` | new recipe unit saved with name and symbol |
| `test_create_entity_tool_updates_agent_context` | context `categories`/`recipe_units` list includes new entity |
| `test_agent_does_not_create_without_confirmation` | agent proposes mapping first; tool not called unprompted |

### Live tests (skip unless `ANTHROPIC_API_KEY`)

| Test | Validates |
|------|-----------|
| `test_live_alignment_agent_spanish_recipe_text` | full LLM round-trip; extracts real recipe with ≥1 ingredient |
| `test_live_alignment_agent_multi_recipe_pagination` | two recipe extractions from same content via `page_index` |

---

## Out of scope

- LangGraph graph — 10.3
- Gradio UI — 10.4
- `__init__.py` exports — 10.5 (import directly from `core.agents.alignment_agent` for tests)
- Architecture docs — 10.6
- File parsing (PDF/image/Excel) — 10.3/10.4
- `RecipeUnitConversion` save (happens in `_make_confirm_fn`, not in the agent) — 10.4

---

## Risks and open questions

### [RISK] — `_data_lake` not set if `_generate_prompt` is never called before tool fires
**Problem:** `self._data_lake` is set during `_generate_prompt()`. If a tool call were
somehow triggered before `_generate_prompt()` runs, `_data_lake` would be missing.
**Fix:** `_create_entity_tool` uses `getattr(self, "_data_lake", None)` and returns an
error string if `None` — already handled in step 5. No silent failure.

### [CONFIRMED] — `_parse_response()` return type and Pydantic version
`BaseAgent._parse_response()` (line 257) always returns `dict[str, Any]` — it calls
`validated.model_dump()` internally before returning. List items in `data.get("ingredients")`
and `data.get("inventory_proposals")` are already plain dicts. Do NOT call `.model_dump()`
on them. Project uses Pydantic v2 (`pydantic>=2.12.5` in `pyproject.toml`) — confirmed.

---

## Deliverable checklist

### `core/agents/alignment_agent.py`
- [ ] `_IngredientProposal`, `_InventoryProposal`, `_AlignmentResponse` models defined
- [ ] `AlignmentAgent` with `INPUT_SCHEMA`, `OUTPUT_SCHEMA`, `RESPONSE_MODEL`
- [ ] `_generate_prompt()` injects all 9 context keys
- [ ] `_generate_prompt()` stores `self._data_lake`, `self._session_id`, `self._context`
- [ ] No-hallucination rule in system prompt
- [ ] Missing steps rule in system prompt (ask once, accept null)
- [ ] Per-ingredient equivalent reasoning rule in system prompt
- [ ] Standard recipe unit rule in system prompt
- [ ] Entity creation rule in system prompt (propose mapping first, create only on confirmation)
- [ ] `create_entity` tool registered via `register_tool()` in `__post_init__()`
- [ ] `_create_entity_tool()` saves entity, updates context list, handles non-standard recipe unit case
- [ ] `_process_response()` merges non-None fields across turns into `recipe_draft`
- [ ] `_process_response()` returns `reply`, `recipe_draft`, `inventory_proposals`, `raw_response`
