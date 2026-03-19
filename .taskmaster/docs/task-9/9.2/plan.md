# Subtask 9.2 — ConsistencyCheckAgent (`core/agents/consistency_check_agent.py`)

## Context

Creates the structural validator that checks each entity step for gaps before the
operator confirms, and runs a final cross-entity check before the last save.
Runs in parallel with 9.1 (ConfigurationAgent). 9.3 (Section UI) depends on both.

**Prior:** 9.1 delivered `ConfigurationAgent` — the conversational agent that builds
entity drafts. 9.2 runs in parallel with it.
**Next (9.3) needs:** `ConsistencyCheckAgent` importable and callable with two distinct
input shapes — per-step and final cross-entity.

---

## File to Create

| File | Action | Summary |
|------|--------|---------|
| `core/agents/consistency_check_agent.py` | Create | `_ConsistencyCheckResponse` + `ConsistencyCheckAgent` |

---

## Dependencies

- `core/agents/base_agent.py` — `BaseAgent`, `_parse_response()`
- `pydantic` — `BaseModel`
- 9.1 (`ConfigurationAgent`) is NOT a dependency — 9.1 and 9.2 run in parallel
- No env vars required for the agent file itself (live tests in 9.5 need `ANTHROPIC_API_KEY`)

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Separate from `ConfigurationAgent` | Dedicated `ConsistencyCheckAgent` | Different input/output schemas and prompt; single-responsibility; independently testable |
| `INPUT_SCHEMA = {}` | Validation disabled | Agent handles two distinct call shapes; a single schema cannot cover both |
| Two call shapes, one agent | Per-step: `{"step", "entities", "restaurant_type"}` / Final: `{"categories", "families", "recipe_units", "inventory_units", "restaurant_type"}` | `_generate_prompt()` detects which shape is present and builds the appropriate prompt |
| `looks_good: bool` (not Optional) | Always present in response | UI needs a definitive boolean — `None` is not acceptable for the confirm gate |
| `looks_good` defaults to `True` on parse failure | Safe default when `_parse_response()` returns `{}` | A broken response should not silently block the operator; UI shows raw response as fallback |
| `issues` vs `suggestions` | `issues` = blocking gaps / `suggestions` = optional improvements | UI treats them differently — issues warn/block; suggestions are informational |
| Stateless agent | No `store()`/`retrieve()`, no `save_state()`/`load_state()` | Each call is independent; no conversation history needed for structural validation |

---

## Two Call Shapes

### Per-step call

Called before the operator confirms each individual step.

**Input dict:**
```python
{
    "step":            str,         # "categories" | "families" | "recipe_units" | "inventory_units"
    "entities":        list[dict],  # the draft entity list for that step
    "restaurant_type": str,         # e.g. "Casual", "Gourmet"
}
```

**Detection in `_generate_prompt()`:** `"step" in input_data`

### Final cross-entity call

Called before the last step (inventory_units) is saved. Checks all four lists together.

**Input dict:**
```python
{
    "categories":      list[dict],
    "families":        list[dict],
    "recipe_units":    list[dict],
    "inventory_units": list[dict],
    "restaurant_type": str,
}
```

**Detection in `_generate_prompt()`:** `"categories" in input_data`

---

## System Prompts

### `_PER_STEP_SYSTEM_PROMPT`

```
Eres un validador estructural para Zenet, un sistema operativo para restaurantes.

Recibirás un JSON con tres campos:
- "step": el paso que se está validando ("categories", "families", "recipe_units" o "inventory_units")
- "entities": la lista de entidades propuestas por el operador
- "restaurant_type": el tipo de restaurante (ej. "Casual", "Rápida", "Gourmet", "Cafetería")

Tu tarea es revisar si la lista tiene huecos estructurales para ese tipo de restaurante.
No juzgues el estilo ni el nombre — solo identifica lo que falta o está mal configurado.

## Criterios por paso

**categories (Categorías de recetas)**
- ¿Hay al menos una categoría para comida sólida y una para bebidas?
- ¿Falta alguna categoría obvia para el tipo de restaurante?
  (ej. un café sin "Bebidas calientes", un restaurante casual sin "Comidas")
- ¿Hay menos de 2 categorías en total?

**families (Familias de inventario)**
- ¿Hay al menos una familia para productos perecederos (Carnes, Lácteos, Verduras, Frutas)?
- ¿Hay al menos una familia para no perecederos (Granos, Abarrotes, Condimentos)?
- ¿Falta alguna familia crítica para el tipo de restaurante?
  (ej. un café sin "Bebidas calientes" o "Lácteos", un gourmet sin "Mariscos" o "Vinos")
- ¿Hay menos de 3 familias en total?

**recipe_units (Unidades de receta)**
- ¿Hay al menos una unidad de peso (g o kg)?
- ¿Hay al menos una unidad de volumen (ml o L)?
- ¿Hay al menos una unidad de conteo (pza, pieza o similar)?
- ¿Hay unidades duplicadas (mismo nombre o símbolo)?

**inventory_units (Unidades de inventario)**
- ¿Hay al menos una unidad estándar de peso (kg o g, is_standard: true)?
- ¿Hay al menos una unidad estándar de volumen (L o ml, is_standard: true)?
- ¿Hay unidades no estándar sin descripción que mencione "equivalencia"?
- ¿Hay unidades duplicadas (mismo nombre o símbolo)?

## Reglas

- `issues`: problemas bloqueantes — la configuración producirá errores o datos incompletos.
- `suggestions`: mejoras opcionales — la configuración funciona pero podría ser más completa.
- `looks_good`: true si no hay issues (puede haber suggestions); false si hay al menos un issue.
- Si la lista tiene 0 entidades: ese es siempre un issue bloqueante.
- No inventes checks fuera de los criterios listados arriba.
- Responde siempre en español.

## Formato de respuesta

Responde SIEMPRE con JSON usando exactamente estos tres campos:
- "issues": array de strings con los problemas bloqueantes encontrados (vacío si ninguno)
- "suggestions": array de strings con mejoras opcionales (vacío si ninguna)
- "looks_good": true si no hay issues, false si hay al menos uno
```

### `_FINAL_SYSTEM_PROMPT`

```
Eres un validador estructural para Zenet, un sistema operativo para restaurantes.

Recibirás un JSON con cinco campos:
- "categories": lista de categorías de recetas configuradas
- "families": lista de familias de inventario configuradas
- "recipe_units": lista de unidades de receta configuradas
- "inventory_units": lista de unidades de inventario configuradas
- "restaurant_type": el tipo de restaurante

Tu tarea es revisar si las cuatro listas son consistentes entre sí.
No repitas los checks individuales de cada lista — ya fueron validados.
Busca únicamente inconsistencias que solo se ven cuando las cuatro listas se ven juntas.

## Criterios de consistencia cruzada

**Unidades de receta vs unidades de inventario**
- ¿Hay unidades de receta volumétricas no estándar (taza, cucharada, cucharadita)
  pero ninguna unidad de inventario de volumen estándar (L, ml)?
  → El sistema no podrá normalizar esas cantidades.
- ¿Hay unidades de receta de conteo no estándar (pieza, tortilla, rebanada)
  pero ninguna unidad de inventario de conteo (pza)?
  → Ingredientes en esas unidades quedarán sin normalizar.

**Familias vs categorías de recetas**
- ¿Hay categorías de recetas configuradas pero 0 familias de inventario?
  → Zenet no podrá asignar ingredientes a familias al procesar recetas.
- ¿Hay familias de inventario configuradas pero 0 categorías de recetas?
  → Los reportes de costo por categoría no tendrán datos.

**Cobertura general**
- ¿Alguna de las cuatro listas quedó completamente vacía?
  → Es un issue bloqueante independientemente de las demás.

## Reglas

- `issues`: inconsistencias que causarán problemas reales en normalización o reportes.
- `suggestions`: mejoras opcionales de alineación entre listas.
- `looks_good`: true si no hay issues; false si hay al menos uno.
- No repitas issues que ya se detectaron en los checks individuales por paso.
- No inventes checks fuera de los criterios listados arriba.
- Responde siempre en español.

## Formato de respuesta

Responde SIEMPRE con JSON usando exactamente estos tres campos:
- "issues": array de strings con inconsistencias bloqueantes (vacío si ninguna)
- "suggestions": array de strings con mejoras opcionales (vacío si ninguna)
- "looks_good": true si no hay issues, false si hay al menos uno
```

---

## Implementation Prompt

### Reference implementation

Before writing anything, read `core/agents/classification_agent.py` in full.
`ConsistencyCheckAgent` follows the same structural pattern but is simpler —
no `store()`/`retrieve()`, no `_data_store` usage, and no conversation continuity.
Each call is fully independent.

Also read:
- `core/agents/base_agent.py` lines 77–110 — abstract method signatures and
  `_parse_response()` behavior (returns `{}` on malformed JSON)

### File structure (in this exact order)

```
module docstring
imports
_PER_STEP_SYSTEM_PROMPT constant
_FINAL_SYSTEM_PROMPT constant
_ConsistencyCheckResponse(BaseModel)
ConsistencyCheckAgent(BaseAgent)
```

### Imports

```python
from __future__ import annotations

import json
from typing import Any, ClassVar

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent
```

### `_ConsistencyCheckResponse`

```python
class _ConsistencyCheckResponse(BaseModel):
    issues: list[str]       # blocking structural gaps
    suggestions: list[str]  # optional improvements
    looks_good: bool        # True if no blocking issues; always present
```

`looks_good` is `bool`, not `bool | None`. The LLM must always return it.

### `ConsistencyCheckAgent`

```python
class ConsistencyCheckAgent(BaseAgent):
    """
    Structural validation agent for the Configuración section.

    Called by the section UI (subtask 9.3) in two distinct modes:

    Per-step mode — called before the operator confirms each step:
        Input: {"step": str, "entities": list[dict], "restaurant_type": str}
        Checks a single entity list for structural gaps.

    Final cross-entity mode — called before the last step is saved:
        Input: {"categories": list, "families": list,
                "recipe_units": list, "inventory_units": list,
                "restaurant_type": str}
        Checks all four lists together for cross-entity inconsistencies.

    INPUT_SCHEMA is empty ({}) to disable validation — the two call shapes
    have incompatible keys and cannot share a single schema.

    This agent is stateless: no store()/retrieve(), no save_state()/load_state().
    Each call is fully independent.

    Output:
        issues:       List of blocking structural gaps found.
        suggestions:  List of optional improvements.
        looks_good:   True if no blocking issues found.
        raw_response: Full LLM response string.
    """

    INPUT_SCHEMA:   ClassVar[dict[str, str]] = {}
    OUTPUT_SCHEMA:  ClassVar[dict[str, str]] = {
        "issues":       "List of blocking structural gaps found.",
        "suggestions":  "List of optional improvements.",
        "looks_good":   "True if no blocking issues found.",
        "raw_response": "Full LLM response string.",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = _ConsistencyCheckResponse
```

### `_generate_prompt()`

```python
def _generate_prompt(
    self,
    input_data: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str]:
    if "step" in input_data:
        # Per-step call: validate a single entity list
        system = _PER_STEP_SYSTEM_PROMPT
        user = json.dumps({
            "step":            input_data["step"],
            "entities":        input_data.get("entities", []),
            "restaurant_type": input_data.get("restaurant_type", ""),
        }, ensure_ascii=False)
    else:
        # Final cross-entity call: validate all four lists together
        system = _FINAL_SYSTEM_PROMPT
        user = json.dumps({
            "categories":      input_data.get("categories", []),
            "families":        input_data.get("families", []),
            "recipe_units":    input_data.get("recipe_units", []),
            "inventory_units": input_data.get("inventory_units", []),
            "restaurant_type": input_data.get("restaurant_type", ""),
        }, ensure_ascii=False)
    return system, user
```

### `_process_response()`

```python
def _process_response(self, response: str) -> dict[str, Any]:
    data = self._parse_response(response)
    return {
        "issues":       data.get("issues", []),
        "suggestions":  data.get("suggestions", []),
        "looks_good":   data.get("looks_good", True),  # safe default — don't block on parse failure
        "raw_response": response,
    }
```

### Constraints

- Do not call `self.store()`, `self.retrieve()`, `save_state()`, or `load_state()`.
  This agent is stateless — no conversation memory is needed for structural validation.
- Do not call `self.memory.add_user()` or `self.memory.add_assistant()` —
  `BaseAgent.run()` manages memory automatically.
- `INPUT_SCHEMA = {}` is intentional — do not add keys to it.
- `looks_good` defaults to `True` on parse failure. This is intentional — a broken
  LLM response should not silently block the operator from saving.
- The `_SYSTEM_PROMPT` constants must be defined at module level, not inside the class.

---

## Test Coverage (implemented in 9.5)

| Test | Mock / Setup | Assertion |
|------|-------------|-----------|
| `test_consistency_check_returns_issues` | Patch provider to return `{"issues": ["Falta familia para perecederos"], "suggestions": [], "looks_good": false}` | `result["issues"]` is non-empty; `result["looks_good"] == False` |
| `test_consistency_check_no_issues_looks_good` | Patch provider to return `{"issues": [], "suggestions": ["Considera agregar Mariscos"], "looks_good": true}` | `result["looks_good"] == True`; `result["issues"] == []` |
| `test_consistency_check_cross_entity` | Patch provider; call with final shape: `recipe_units=[{"name": "taza", "symbol": "tza", ...}]`, `inventory_units` with no volume unit | `result["looks_good"] == False`; at least one issue string present |

**Live (1 test — guarded by `ANTHROPIC_API_KEY`, implemented in 9.5):**

| Test | Validates | Guard |
|------|-----------|-------|
| `test_live_consistency_check_flags_missing_unit` | Real LLM call with per-step shape; `recipe_units` list with no liquid unit → agent flags it | `ANTHROPIC_API_KEY` |

---

## Out of Scope

- `ConfigurationAgent` — 9.1
- Section UI wiring — 9.3
- Exports (`__init__.py`) — 9.4
- Test file creation — 9.5
- No changes to `base_agent.py`, `data_model.py`, `persistence.py`, `schema.py`

---

## Risks and Open Questions

### [RISK] — `looks_good` default on parse failure is silent
When `_parse_response()` returns `{}` (malformed JSON), `looks_good` defaults to `True`
and `issues` to `[]`. The UI will see a clean check and enable the confirm button.
**Fix in 9.3:** When `issues == []` but `raw_response` contains no valid JSON structure,
the UI should display a warning that the check could not be completed, and still allow
the operator to proceed.

---

## Deliverable Checklist

- [ ] `_ConsistencyCheckResponse` with `issues: list[str]`, `suggestions: list[str]`, `looks_good: bool`
- [ ] `INPUT_SCHEMA = {}` — validation disabled
- [ ] `_generate_prompt()` detects per-step shape via `"step" in input_data`
- [ ] `_generate_prompt()` detects final shape via `"categories" in input_data`
- [ ] `_PER_STEP_SYSTEM_PROMPT` covers all four step types with explicit check criteria
- [ ] `_FINAL_SYSTEM_PROMPT` covers cross-entity checks only (no repeat of per-step checks)
- [ ] Both prompts enforce Spanish response and JSON format with exactly three fields
- [ ] `_process_response()` defaults `looks_good` to `True` on parse failure
- [ ] No `store()`, `retrieve()`, `save_state()`, or `load_state()` calls in the agent
