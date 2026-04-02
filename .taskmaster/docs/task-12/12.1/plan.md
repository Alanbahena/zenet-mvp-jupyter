# Subtask 12.1 — `_build_manual_context` + `ManualOperativoAgent` + re-exports

## Goal

Create the agent class (`ManualOperativoAgent`), the context builder
(`_build_manual_context`), and wire both into the re-export chain.
This is the foundation all subsequent subtasks depend on — no UI is built here.

- **Prior step delivered:** Task 11 — fully structured `InventoryItem` records with
  `stock_unit_id`, `purchase_unit_id`, `purchase_to_stock_factor`, and `family_id`
  saved to DataLake.
- **Next subtask (12.2) needs:** `ManualOperativoAgent` importable from `core.agents`,
  `_build_manual_context` callable inside the section file, and
  `compute_readiness_report()` already wired inside `_build_manual_context`.

---

## Key design decisions

### Context injection (not tool-based)

`ManualOperativoAgent` receives all restaurant data as a structured plain-text string
in its system prompt via `context["manual_context"]`. No tool calls for MVP.

**Rationale:** Phase A restaurant data (~10–20 recipes, ~30–50 items) fits in
3,000–6,000 tokens — well within Claude's 200k window. Tool-based lookup adds
3–4x implementation complexity and per-call latency with no benefit at this data
scale. The agent also needs to reason across all entities at once (e.g. "¿qué recetas
usan pollo?"), which context injection handles naturally.

**Validation step:** measure the character/token count of the `_build_manual_context`
output against `scripts/seed_data.py` before closing 12.1. If the string exceeds
~15,000 tokens on the seeded dataset, escalate to tool-based in a follow-up subtask.

### Plain-text output (`RESPONSE_MODEL = None`)

Agent answers in natural language prose. No structured JSON response needed.
Same pattern as `WelcomeAgent`.

### `_build_manual_context` lives in the section file

Private module-level helper in `gradio_app/sections/manual_operativo.py`.
Matches the pattern of `_load_configuration_context` in `configuracion.py` and
`_load_structuring_context` in `estructura.py`. Not a separate module.

### Context key contract

The section passes context under a fixed key:
```python
context = {"manual_context": _build_manual_context(data_lake, session_id)}
result = agent.run(input_data={"user_message": message}, context=context)
```
The agent reads: `context.get("manual_context", "")`.

---

## Files to create / modify

| File | Action | Summary |
|------|--------|---------|
| `core/agents/manual_operativo_agent.py` | Create | `ManualOperativoAgent` class |
| `core/agents/__init__.py` | Modify | Import + `__all__` entry |
| `core/__init__.py` | Modify | Agents block import + `__all__` entry |
| `gradio_app/sections/manual_operativo.py` | Modify | Add `_build_manual_context`; keep stub `render()` |

---

## Dependencies

- Task 11 done
- `core/agents/base_agent.py` — `BaseAgent` (exists)
- `core/agents/utils.py` — `create_agent()` (exists)
- `core/operations/readiness_kpis.py` — `compute_readiness_report()` (exists)
- `core/domain/serialization.py` — all `from_dict` functions including
  `recipe_unit_conversion_from_dict` (line 271) (exists)
- `core/__init__.py` — `RecipeUnitConversionRegistry` already re-exported (lines 87–88)
- `gradio_app/session.py` — `stable_entity_id(session_id: str) -> int` (exists)
- `ANTHROPIC_API_KEY` in `.env`

---

## Implementation steps

### Step 1 — Create `core/agents/manual_operativo_agent.py`

```python
from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent


class ManualOperativoAgent(BaseAgent):
    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "Operator question or deduction request in natural language.",
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "reply": "Agent response in Spanish.",
        "raw_response": "Full LLM response string.",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = None  # plain prose

    def _generate_prompt(
        self, input_data: dict[str, Any], context: dict[str, Any]
    ) -> tuple[str, str]:
        manual_text = context.get("manual_context", "")
        system = (
            "Eres el Asistente Operativo de Zenet. Tienes acceso completo al manual "
            "operativo del restaurante que se muestra a continuación. Responde siempre "
            "en español, de forma clara y directa para un operador de restaurante.\n\n"
            "Puedes:\n"
            "- Responder preguntas sobre los datos del restaurante (recetas, inventario, "
            "configuración, calificación de estandarización)\n"
            "- Calcular deducciones de ingredientes: si el operador pregunta cuánto "
            "necesita para N porciones de un platillo, multiplica las cantidades de la "
            "receta por N. Para ingredientes con unidad de compra distinta a la unidad "
            "de stock, calcula también las unidades de compra necesarias usando el "
            "factor de conversión. Indica explícitamente los ingredientes sin vínculo "
            "de inventario.\n"
            "- Explicar qué se necesita para mejorar la calificación de estandarización\n\n"
            "No puedes modificar datos. Si el operador pide hacer un cambio, "
            "indícale que regrese a la sección correspondiente del notebook.\n\n"
            f"MANUAL OPERATIVO DEL RESTAURANTE\n"
            f"{'=' * 40}\n"
            f"{manual_text}"
        )
        return system, input_data["user_message"]

    def _process_response(self, response: str) -> dict[str, Any]:
        return {"reply": response, "raw_response": response}
```

### Step 2 — Modify `core/agents/__init__.py`

Add after the last existing import:
```python
from core.agents.manual_operativo_agent import ManualOperativoAgent
```

Add `"ManualOperativoAgent"` to `__all__`.

### Step 3 — Modify `core/__init__.py`

In the agents import block (alongside `AlignmentAgent`, `StructuringAgent`, etc.):
```python
from core.agents.manual_operativo_agent import ManualOperativoAgent
```

Add `"ManualOperativoAgent"` to `__all__`.

### Step 4 — Modify `gradio_app/sections/manual_operativo.py`

Add imports at the top of the file:
```python
from gradio_app.session import stable_entity_id
from core import (
    RecipeUnitRegistry, InventoryUnitRegistry,
    CategoryRecipeRegistry, FamilyInventoryRegistry,
    InventoryItemRegistry,
)
from core.domain.serialization import (
    restaurant_from_dict,
    recipe_from_dict,
    inventory_item_from_dict,
    recipe_unit_from_dict,
    inventory_unit_from_dict,
    category_recipe_from_dict,
    family_inventory_from_dict,
    recipe_unit_conversion_from_dict,
)
from core.operations.normalization import RecipeUnitConversionRegistry
from core.operations.readiness_kpis import compute_readiness_report
```

Add `_build_manual_context` as a private module-level function:

```python
def _build_manual_context(data_lake, session_id: str) -> str:
    """
    Assembles all DataLake entities for a session into a structured plain-text block
    suitable for injection into ManualOperativoAgent's system prompt.

    Returns a minimal placeholder string if the session has no restaurant entity.

    Note: recipe_unit_conversion is a SQLite-only entity type. If the backend is
    ever JSON, the conversion registry will be empty and deductionCoveragePct
    will report 0% regardless of confirmed conversions.
    """
    entity_id = stable_entity_id(session_id)

    # Load restaurant
    restaurant_data = data_lake.load_entity("restaurant", entity_id)
    if not restaurant_data:
        return "Sin datos de restaurante para esta sesión."

    restaurant = restaurant_from_dict(restaurant_data)

    # Load user and classification
    user_data = data_lake.load_entity("user", entity_id) or {}
    classification_data = data_lake.load_entity("classification", entity_id) or {}

    # Load registries
    # Single-session MVP assumption: list_entity_ids returns all IDs globally.
    # Revisit if multi-session support is added.
    recipe_unit_ids = data_lake.list_entity_ids("recipe_unit")
    recipe_units = [
        recipe_unit_from_dict(data_lake.load_entity("recipe_unit", uid))
        for uid in recipe_unit_ids
    ]

    inventory_unit_ids = data_lake.list_entity_ids("inventory_unit")
    inventory_units = [
        inventory_unit_from_dict(data_lake.load_entity("inventory_unit", uid))
        for uid in inventory_unit_ids
    ]

    category_ids = data_lake.list_entity_ids("category_recipe")
    categories = [
        category_recipe_from_dict(data_lake.load_entity("category_recipe", cid))
        for cid in category_ids
    ]

    family_ids = data_lake.list_entity_ids("family_inventory")
    families = [
        family_inventory_from_dict(data_lake.load_entity("family_inventory", fid))
        for fid in family_ids
    ]

    recipe_ids = data_lake.list_entity_ids("recipe")
    recipes = [
        recipe_from_dict(data_lake.load_entity("recipe", rid))
        for rid in recipe_ids
    ]

    item_ids = data_lake.list_entity_ids("inventory_item")
    items = [
        inventory_item_from_dict(data_lake.load_entity("inventory_item", iid))
        for iid in item_ids
    ]

    conversion_ids = data_lake.list_entity_ids("recipe_unit_conversion")

    # Build in-memory registries
    recipe_unit_registry = RecipeUnitRegistry()
    for u in recipe_units:
        recipe_unit_registry.add(u)

    inventory_unit_registry = InventoryUnitRegistry()
    for u in inventory_units:
        inventory_unit_registry.add(u)

    category_registry = CategoryRecipeRegistry()
    for c in categories:
        category_registry.add(c)

    family_registry = FamilyInventoryRegistry()
    for f in families:
        family_registry.add(f)

    item_registry = InventoryItemRegistry()
    for item in items:
        item_registry.add(item)

    conversion_table = RecipeUnitConversionRegistry()
    for cid in conversion_ids:
        raw = data_lake.load_entity("recipe_unit_conversion", cid)
        if raw:
            key, entry = recipe_unit_conversion_from_dict(raw)
            conversion_table.add(
                key.recipe_unit_id,
                entry.quantity,
                entry.base_unit_id,
                family_id=key.family_id,
                inventory_item_id=key.inventory_item_id,
                source=entry.source,
            )

    # Compute readiness report
    report = compute_readiness_report(
        restaurant,
        recipes=recipes,
        recipe_unit_registry=recipe_unit_registry,
        inventory_unit_registry=inventory_unit_registry,
        category_recipe_registry=category_registry,
        family_inventory_registry=family_registry,
        inventory_item_registry=item_registry,
        conversion_table=conversion_table,
    )

    # --- Assemble plain-text context ---
    operator_name = user_data.get("name", "Operador")
    std_level = classification_data.get("standardization_level", "N/D")
    restaurant_description = classification_data.get("restaurant_description", "")

    lines = []

    lines.append("PERFIL DEL RESTAURANTE")
    lines.append(f"  Nombre: {restaurant.name}")
    lines.append(f"  Tipo: {restaurant.restaurant_type}")
    lines.append(f"  Operador: {operator_name}")
    lines.append(f"  Nivel de estandarización: {std_level}")
    if restaurant_description:
        lines.append(f"  Descripción: {restaurant_description}")
    lines.append("")

    overall = report.get("overall_score", 0)
    grade = report.get("grade", "N/D")
    lines.append("PUNTUACIÓN DE ESTANDARIZACIÓN")
    lines.append(f"  Puntuación general: {overall} / 100   Calificación: {grade}")
    dimensions = report.get("dimensions", {})
    for dim_name, dim_data in dimensions.items():
        score = dim_data.get("score", 0)
        status = dim_data.get("status", "na")
        lines.append(f"  {dim_name}: {score}%  [{status}]")
    lines.append("")

    fail_warn_kpis = [
        kpi for kpi in report.get("kpis", [])
        if kpi.get("status") in ("fail", "warn")
    ]
    if fail_warn_kpis:
        lines.append("ÁREAS DE OPORTUNIDAD")
        for kpi in fail_warn_kpis:
            lines.append(f"  [{kpi['status'].upper()}] {kpi['title']}")
            for ev in kpi.get("evidence", [])[:5]:
                lines.append(f"    - {ev}")
        lines.append("")

    lines.append(f"RECETAS ({len(recipes)} total)")
    for recipe in recipes:
        cat_name = ""
        if recipe.category_id is not None:
            cat = category_registry.get(recipe.category_id)
            cat_name = cat.name if cat else str(recipe.category_id)
        lines.append(f"  Receta: {recipe.name}  Categoría: {cat_name}")
        for ing in recipe.ingredients:
            unit = recipe_unit_registry.get(ing.unit_id)
            unit_symbol = unit.symbol if unit else str(ing.unit_id)
            linked_item = item_registry.get_by_name(ing.name)
            link_status = "vinculado" if (ing.inventory_item_id or linked_item) else "sin vincular"
            lines.append(
                f"    - {ing.name}: {ing.quantity} {unit_symbol}  [{link_status}]"
            )
    lines.append("")

    lines.append(f"INVENTARIO ({len(items)} artículos)")
    for item in items:
        pu = inventory_unit_registry.get(item.purchase_unit_id)
        su = inventory_unit_registry.get(item.stock_unit_id)
        fam = family_registry.get(item.family_id) if item.family_id else None
        pu_sym = pu.symbol if pu else str(item.purchase_unit_id)
        su_sym = su.symbol if su else str(item.stock_unit_id)
        fam_name = fam.name if fam else "sin familia"
        lines.append(
            f"  {item.name}  compra: {pu_sym}  stock: {su_sym}  "
            f"factor: {item.purchase_to_stock_factor}  familia: {fam_name}"
        )
    lines.append("")

    lines.append("INSTRUCCIONES PARA DEDUCCIÓN")
    lines.append(
        "  Para calcular ingredientes necesarios: multiplica la cantidad de cada "
        "ingrediente en la receta por el número de porciones solicitadas. "
        "El resultado estará en la unidad de stock del ingrediente. "
        "Para convertir a unidades de compra: divide entre purchase_to_stock_factor. "
        "Si un ingrediente está marcado como 'sin vincular', indícalo explícitamente "
        "en la respuesta."
    )

    context_string = "\n".join(lines)
    return context_string
```

Keep the existing stub `render()` unchanged — it will be replaced in subtask 12.2.

---

## Out of scope (12.1)

- Any Gradio UI rendering (two-state layout, tabs, agent sidebar) — deferred to 12.2–12.4
- `_build_resumen_md` helper and unit mismatch formatting — deferred to 12.2
- All tests — deferred to 12.5
- Architecture doc — deferred to 12.6
- `CLAUDE.md` and `tasks.json` status updates — deferred to 12.6

---

## Test coverage

All tests are written in subtask 12.5. No test file is created in this subtask.

Mocked tests (deferred to 12.5):
- `test_build_manual_context_returns_string`
- `test_build_manual_context_includes_recipe`
- `test_build_manual_context_includes_inventory`
- `test_build_manual_context_empty_session`
- `test_manual_operativo_agent_process_response`
- `test_manual_operativo_agent_output_schema`
- `test_manual_operativo_agent_input_schema`

Live tests (deferred to 12.5, guarded by `ANTHROPIC_API_KEY`):
- `test_manual_operativo_agent_qa_live`
- `test_manual_operativo_agent_deduction_live`

---

## Risks and open questions

### [OPEN] — list_entity_ids has no session filter
**Source:** Validation of subtask 12.1
**Problem:** `list_entity_ids(entity_type)` returns all entity IDs across all sessions. `_build_manual_context` loads all recipes/items globally, not scoped to the current `session_id`. This matches the MVP (one session = one restaurant), but the function's signature implies session isolation.
**Impact:** If multi-session support is ever added, `_build_manual_context` will silently return data mixed from all sessions.
**Suggested action:** Add a comment in `_build_manual_context` noting "single-session MVP assumption — revisit if multi-session is added." Defer review to Task 15.

- **Context size validation:** Print `len(context_string)` against `scripts/seed_data.py`
  output before closing 12.1. If output exceeds ~15,000 tokens (~60,000 characters),
  escalate to tool-based agent in a follow-up subtask.
- **`recipe_unit_conversion` SQLite-only:** Documented in `_build_manual_context` docstring.
  If backend is ever JSON, conversion registry will be empty and `deductionCoveragePct`
  will report 0%.
- **`list_entity_ids` / `load_entity` API:** Confirm exact DataLake method signatures
  match usage in `_build_manual_context` before implementation. Reference `estructura.py`
  for the canonical pattern used in Task 11.
- **`RecipeUnitConversionRegistry` import path:** Re-exported from `core/__init__.py`
  (lines 87–88) but also importable from `core.operations.normalization` directly.
  Use the direct import inside `_build_manual_context` to avoid circular import risk.

---

## Deliverable checklist

`core/agents/manual_operativo_agent.py`:
- [ ] `ManualOperativoAgent` extends `BaseAgent` with `RESPONSE_MODEL = None`
- [ ] `INPUT_SCHEMA` has `user_message`; `OUTPUT_SCHEMA` has `reply` and `raw_response`
- [ ] `_generate_prompt()` injects full context string into system prompt in Spanish
- [ ] `_process_response()` returns `{"reply": response, "raw_response": response}`

`core/agents/__init__.py`:
- [ ] `ManualOperativoAgent` imported and added to `__all__`

`core/__init__.py`:
- [ ] `ManualOperativoAgent` added to agents import block and `__all__`

`gradio_app/sections/manual_operativo.py`:
- [ ] `_build_manual_context(data_lake, session_id) -> str` uses `stable_entity_id`,
  reads all entities, calls `compute_readiness_report()`, returns plain-text string
- [ ] Empty session handled: returns minimal string without crashing
- [ ] Context size validated against seeded data (character count printed/logged)
- [ ] stub `render()` left unchanged
