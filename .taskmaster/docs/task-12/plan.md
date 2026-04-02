# Task 12 — Manual Operativo section plan

## Goal

Implement the Manual Operativo section: the final step of the pipeline where the operator
receives a structured, visual operational manual generated from all their DataLake data.
Includes a readiness scorecard, tabbed catalog views, and a persistent Q&A + deduction agent.

- **Prior step delivered:** fully structured `InventoryItem` records with `stock_unit_id`,
  `purchase_unit_id`, `purchase_to_stock_factor`, and `family_id` saved to DataLake by
  Estructura (Task 11).
- **This section delivers:** a read-only operational manual (the restaurant's "bible") with
  KPI-driven areas of opportunity, and a persistent agent that handles business Q&A and
  ingredient deduction queries.

---

## Emotional design principle

This section must make the operator feel **relief and accomplishment** — not overwhelm them
with data. Every design decision should be filtered through this lens:
- Start with a single call-to-action (one button)
- Land on a scorecard that celebrates what they completed before showing what's missing
- Organize content into tabs so each mental context is isolated
- Keep the agent visible but secondary — a helper, not a distraction

---

## Key design decisions

### 1. Two-state UI (empty → generated)

**State 1 — Empty:** A single "Generar Manual Operativo" button centered on screen.
No other content. The operator signals intent before any loading occurs.

**State 2 — Generated:** Two-column layout:
- Left (~70%): 4 tabs — the "bible"
- Right (~30%): persistent `ManualOperativoAgent` chat panel, always visible

**Rationale:** The button ceremony marks the transition from "I've been entering data" to
"I now have a complete operational system." It gives the section weight. The persistent
agent sidebar means the operator never loses their place in the manual to ask a question.

### 2. Four tabs in the manual

| Tab | Content |
|-----|---------|
| Resumen | Overall score, KPI progress bars, achievements, top 3 areas of opportunity |
| Mi Restaurante | Restaurant profile, configuration summary (units, categories, families) |
| Recetas | Recipe catalog with deduction-readiness badges, expandable ingredient lists |
| Inventario | Items grouped by Perecederos / No Perecederos with full unit and family info |

**Rationale:** Each tab is one mental context. The operator can explore at their own pace
without being overwhelmed by one long scrollable page.

### 3. Resumen tab is purely visual/static

The Resumen tab contains no chat, no agent interaction, no input fields.
It shows: overall score (number + grade), per-dimension progress bars (color-coded),
a "Logros completados" checklist, and "Áreas de oportunidad" with specific entity names.

**Rationale:** The first thing the operator sees after generating must feel like a reward,
not a task list. Static content renders immediately and cannot be interrupted by LLM latency.

### 4. KPIs from readiness_kpis.py

`compute_readiness_report()` is called once at generation time. Its output feeds:
- The overall score and grade (A/B/C/D) in Resumen
- The per-dimension progress bars (setup, recipes, inventory, normalization)
- The "Áreas de oportunidad" list — populated from `evidence` arrays in fail/warn KPIs,
  which already contain specific entity names (recipe names, ingredient names)
- The agent's context — the KPI report is serialized into the system prompt

**Rationale:** All KPI logic already exists and is tested. No new computation needed.
Evidence arrays make the areas of opportunity specific and actionable, not generic.

### 5. Context injection (not tool-based) for the agent

`ManualOperativoAgent` receives all restaurant data as structured text in its system prompt
via `_build_manual_context(data_lake, session_id)`. No tool calls needed for MVP.

`_build_manual_context` assembles:
- Restaurant profile (name, type, operator)
- KPI report summary (scores, fail/warn KPIs with evidence)
- All recipes with ingredients and deduction status
- All inventory items with units and families

**Rationale:** The full dataset for a restaurant in Phase A fits comfortably in one prompt
(~3,000–8,000 tokens). Tool-based lookup adds round-trip latency and implementation
complexity with no benefit at this data scale.

### 6. Agent scope: Q&A + deduction only (read-only)

`ManualOperativoAgent` never modifies DataLake. It handles:
- Natural language Q&A about the restaurant's data
- Ingredient deduction: "If I sell X portions of Y dish, how much do I need?"
  Uses `normalize_recipe_for_deduction` from `core/operations/normalization.py`
- KPI explanation: "What do I need to improve my score?"

**Rationale:** Manual Operativo is the end of the pipeline. Modifying data here would
require re-running upstream sections. Q&A + deduction covers the primary use cases
operators have at this stage.

### 7. Deduction inside the agent (not a separate form)

The operator asks deduction questions in natural language. The agent computes the result
using `normalize_recipe_for_deduction` and replies with a formatted ingredient list.

**Rationale:** Natural language is more accessible than a form for operators who are not
technical. The agent can also handle follow-ups ("what if I sell 100 instead of 50?")
in the same conversation flow.

---

## UI layout (generated state)

```
┌────────────────────────────────────────┬───────────────────────┐
│  gr.Tabs (scale=7)                     │  gr.Column (scale=3)  │
│                                        │                       │
│  [Resumen][Mi Restaurante][Recetas]    │  Asistente Operativo  │
│  [Inventario]                          │  ─────────────────    │
│                                        │  [chat history]       │
│  [active tab content]                  │                       │
│                                        │  [input + send]       │
└────────────────────────────────────────┴───────────────────────┘
```

### Resumen tab layout

```
Tu restaurante está estandarizado
──────────────────────────────────
Puntuación general: 78 / 100   Calificación: B

[Configuración]   ████████████████████  100%  ✓ ok
[Recetas]         ████████████░░░░░░░░   72%  ⚠ warn
[Inventario]      ████████████████░░░░   85%  ✓ ok
[Normalización]   ████████░░░░░░░░░░░░   60%  ✗ fail

Cobertura de deducción: 9 de 15 recetas listas

Logros completados:
  ✓ Restaurante registrado
  ✓ Nivel de estandarización definido
  ✓ N unidades de receta configuradas
  ✓ N familias de inventario configuradas
  ✓ N recetas capturadas
  ✓ N artículos de inventario estructurados

Áreas de oportunidad:
  ⚠ [specific KPI title]: [specific entity names from evidence]
  ✗ [specific KPI title]: [specific entity names from evidence]
  ...
```

### Áreas de oportunidad — unit mismatch formatting rule

The normalization evidence list includes a `reason` string per skipped ingredient.
`_build_resumen_md` must translate these technical reasons into plain operator language,
grouped by reason type:

**Reason: `"Missing conversion entry (ingredient unit family differs from inventory item unit family)"`**

This is the unit mismatch case — recipe unit and inventory unit are in different dimensions
(e.g. recipe says "2 pza tortillas", inventory stores in "kg"). The operator needs to know
which specific units are in conflict so they can define the conversion.

Format in Resumen as:

```
✗ Ingredientes sin conversión de unidades definida:
    → Tortillas (Tacos al pastor): receta usa "pza", inventario usa "kg"
    → Agua (Horchata): receta usa "vaso", inventario usa "L"
    (Define la equivalencia para que Zenet pueda calcular el consumo)
```

To build this display, `_build_resumen_md` needs access to:
- The evidence `ref` field (ingredient name + recipe name)
- The ingredient's `unit_id` → symbol (from `RecipeUnitRegistry`)
- The inventory item's `stock_unit_id` → symbol (from `InventoryUnitRegistry`)

This means `_build_resumen_md` must receive the loaded registries (or the full context
dict) in addition to the KPI report, so it can resolve unit IDs to human-readable symbols.

**Other reason strings → generic fallback:**
- `"No inventory item found by id or name"` → already handled as unlinked ingredient
- `"Invalid quantity"` / `"Unit chain error"` → show as generic "error de configuración"
- `"Inventory unit_id not in registry"` → show as "unidad de inventario no configurada"

**Agent benefit:** The agent's context includes the full evidence list with reasons.
When the operator asks "¿por qué no puedo deducir las tortillas?", the agent reads the
reason and explains in plain Spanish: "La receta usa piezas pero el inventario registra
tortillas en kilogramos. Necesitas definir cuántos kg equivale una tortilla."

### Mi Restaurante tab layout

```
[Restaurant name]
Tipo: [restaurant type]    Operador: [user name]
Nivel de estandarización: [1/2/3]

Configuración:
  Unidades de receta:    N
  Unidades de inventario: N
  Categorías de receta:  N
  Familias de inventario: N
  Artículos de inventario: N
  Recetas:               N
```

### Recetas tab layout

```
[Recipe name]  [badge: ✓ Lista / ⚠ Incompleta / ✗ No puede deducirse]  ▼
  Categoría: [category]
  Ingredientes:
    [name]  [qty] [unit]  [✓ vinculado / ⚠ sin vincular]
  Pasos: [steps...]

[Recipe name]  [badge]  ▼
  ...
```

### Inventario tab layout

```
Perecederos (N artículos)
  [name]   compra: [purchase_unit]   stock: [stock_unit]   factor: [X]   [family]
  ...

No Perecederos (N artículos)
  [name]   compra: [purchase_unit]   stock: [stock_unit]   factor: [X]   [family]
  ...
```

---

## ManualOperativoAgent

### Class signature

```python
class ManualOperativoAgent(BaseAgent):
    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "Operator question or deduction request in natural language.",
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "reply": "Agent response in Spanish.",
        "raw_response": "Full LLM response string.",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = None  # plain prose
```

### Context key contract

The Gradio section passes the manual context under a fixed key:

```python
# In the section's chat_fn:
context = {"manual_context": _build_manual_context(data_lake, session_id)}
result = agent.run(input_data={"user_message": message}, context=context)
```

Inside `_generate_prompt`, the agent reads:

```python
manual_text = context.get("manual_context", "")
```

### Context structure (injected into system prompt)

```
PERFIL DEL RESTAURANTE
  nombre, tipo, operador, nivel de estandarización

PUNTUACIÓN DE ESTANDARIZACIÓN
  overall_score, grade, dimension scores
  KPIs en fail/warn con evidencia específica

RECETAS (N total, X listas para deducción)
  Por receta: nombre, categoría, ingredientes (nombre, cantidad, unidad, vinculado/no)

INVENTARIO (N artículos)
  Por artículo: nombre, categoria, familia, unidad_compra, unidad_stock, factor

INSTRUCCIONES PARA DEDUCCIÓN
  Reglas de cálculo usando purchase_to_stock_factor y stock units
```

### Deduction calculation

When the operator asks "Si vendo 80 porciones de tacos al pastor, ¿cuánto necesito?":

1. Agent identifies the recipe from context
2. Multiplies each ingredient quantity × portions requested
3. For ingredients with `purchase_unit ≠ stock_unit`, also computes purchase units needed
4. For unlinked ingredients, notes them explicitly ("no incluido por falta de vínculo")
5. Returns a formatted list

For MVP: the agent performs this calculation in natural language reasoning over the
context (no tool call). The full recipe data is in the prompt.

---

## _build_manual_context function

Lives in `gradio_app/sections/manual_operativo.py` as a private module-level helper
(same pattern as `_load_configuration_context` in `configuracion.py` and
`_load_structuring_context` in `estructura.py`). Not a separate module.

Uses `stable_entity_id(session_id)` (imported from `gradio_app.session`) to resolve
the session into a DataLake entity id — same pattern as all other sections.

```python
def _build_manual_context(data_lake, session_id: str) -> str:
    """
    Assembles all DataLake entities for a session into a structured text block
    suitable for injection into ManualOperativoAgent's system prompt.
    """
```

Reads from DataLake:
- `restaurant` entity
- `user` entity
- `classification` entity (for `standardization_level` and `restaurant_description`)
- `recipe_unit`, `inventory_unit`, `category_recipe`, `family_inventory` entities (by listed ids)
- All `recipe` entities (with embedded ingredients)
- All `inventory_item` entities
- All `recipe_unit_conversion` entries (SQLite-only) → builds `RecipeUnitConversionRegistry`

Note: `recipe_unit_conversion` is a SQLite-only entity type (`_SQLITE_ENTITY_TYPES` in
`persistence.py`). MVP always uses SQLite (see `session.py`). If this ever runs on a JSON
backend, the conversion registry will be empty and `normalization.deductionCoveragePct`
will report 0% regardless of confirmed conversions.

Builds in-memory registries from loaded entities.
Calls `compute_readiness_report()` with loaded registries — including the conversion table.

Returns a structured plain-text string (not JSON — easier for the LLM to reason over).

**Empty session handling:** If DataLake has no restaurant entity for the session,
`_build_manual_context` returns a minimal placeholder string. The agent still
initializes without crashing. `compute_readiness_report()` with empty registries
returns all-`na` KPIs — the Resumen tab renders with 0/100 score and empty lists.

---

## Files to create / modify

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/sections/manual_operativo.py` | Modify | Full implementation replacing stub |
| `core/agents/manual_operativo_agent.py` | Create | `ManualOperativoAgent` class |
| `core/agents/__init__.py` | Modify | Add `ManualOperativoAgent` import + `__all__` entry |
| `core/__init__.py` | Modify | Add `ManualOperativoAgent` to agents import block + `__all__` |
| `docs/Architecture/sections/manual_operativo.md` | Create | As-built architecture doc |
| `CLAUDE.md` | Modify | Task 12 status `in-progress` → `done` |
| `.taskmaster/tasks/tasks.json` | Modify | Task 12 status → `done` |

No new core data model changes. No new persistence schema. No new dependencies beyond
what is already installed (Gradio, Anthropic SDK, core modules).

---

## Subtask breakdown

| Subtask | Title | Depends on |
|---------|-------|------------|
| 12.1 | `_build_manual_context` + `ManualOperativoAgent` + re-exports | — |
| 12.2 | Resumen tab (score, KPI bars, achievements, areas of opportunity) | 12.1 |
| 12.3 | Mi Restaurante tab + Recetas tab + Inventario tab | 12.1 |
| 12.4 | Gradio wiring: two-state UI, persistent agent sidebar, tab assembly, "Regenerar" button | 12.2, 12.3 |
| 12.5 | Unit tests for `_build_manual_context` and `ManualOperativoAgent` | 12.1 |
| 12.6 | Architecture doc + re-export updates + task closure | 12.4, 12.5 |

---

## Dependencies

- Task 11 done (InventoryItem enriched with two-unit model)
- `core/operations/readiness_kpis.py` — `compute_readiness_report()` (exists, tested)
- `core/operations/normalization.py` — `normalize_recipe_for_deduction` (exists)
- `core/agents/base_agent.py` — `BaseAgent` (exists)
- `core/agents/utils.py` — `create_agent()` (exists)
- `core/domain/serialization.py` — all `from_dict` functions (exist)
- `ANTHROPIC_API_KEY` in `.env`

---

## Out of scope (Task 12)

- Modifying any DataLake entity from the Manual Operativo section
- Export to PDF or print functionality
- Real-time stock deduction (tracking actual sales)
- Cost/price data (no purchase price field exists in the data model)
- Multi-session or multi-user manual comparison
- Tool-based agent (context injection is sufficient for Phase A data volume)
- LangGraph integration (single-agent, no fan-out needed)

---

## Test strategy

### Unit tests (offline, no API key)

| Test | Setup | Assertion |
|------|-------|-----------|
| `test_build_manual_context_returns_string` | DataLake with minimal restaurant + 1 recipe + 1 item | Returns non-empty string containing restaurant name |
| `test_build_manual_context_includes_recipe` | DataLake with 1 recipe named "Tacos" | Returned string contains "Tacos" |
| `test_build_manual_context_includes_inventory` | DataLake with 1 item named "Carne" | Returned string contains "Carne" |
| `test_build_manual_context_empty_session` | Empty DataLake | Returns string (no crash); does not raise |
| `test_build_resumen_md_all_na_kpis` | `compute_readiness_report()` with empty registries | Renders "0 / 100" score without crashing; areas of opportunity section is empty |
| `test_manual_operativo_agent_process_response` | Mock provider returning plain text | `_process_response` returns `{"reply": ..., "raw_response": ...}` |
| `test_manual_operativo_agent_output_schema` | `OUTPUT_SCHEMA` keys | `reply` and `raw_response` present |
| `test_manual_operativo_agent_input_schema` | `INPUT_SCHEMA` keys | `user_message` present |

### Live tests (require `ANTHROPIC_API_KEY`)

| Test | What it validates |
|------|------------------|
| `test_manual_operativo_agent_qa_live` | Agent answers a restaurant Q&A question in Spanish |
| `test_manual_operativo_agent_deduction_live` | Agent returns ingredient quantities for a deduction query |

---

## Risks and open questions

- **Context size:** A restaurant with 20+ recipes and 50+ items may produce a context
  string of 6,000–10,000 tokens. Well within Claude's window but worth measuring.
  Validate against `scripts/seed_data.py` output in subtask 12.1 before assuming
  context injection is sufficient. If it grows beyond ~15,000 tokens, switch to
  tool-based lookup per recipe/item.

- **Deduction accuracy:** The agent performs deduction by reasoning in natural language
  over the context. For MVP this is sufficient. For production, replace with a
  deterministic call to `normalize_recipe_for_deduction`.

- **KPI display in Gradio:** Progress bars will be rendered as `gr.Markdown` with
  Unicode block characters (████░░░) and color via HTML spans, since Gradio does not
  have a native progress bar component that works well in static display mode.
  If Gradio adds native support, upgrade accordingly.

- **"Regenerar Manual" button behavior:** Clicking "Regenerar Manual" re-calls
  `generate_fn` and updates all four tab `gr.Markdown` components in-place — no
  page reload. The generated state layout stays visible; only the content refreshes.
  This handles the case where the operator goes back to an earlier section and
  returns with updated data. Implement in subtask 12.4.

### [OPEN] — recipe_unit_conversion is SQLite-only
**Source:** Validation of task 12
**Problem:** `recipe_unit_conversion` is in `_SQLITE_ENTITY_TYPES` only (persistence.py). `_build_manual_context` loads it to build `RecipeUnitConversionRegistry` for `compute_readiness_report()`. If the backend is ever JSON, the registry will be empty and `normalization.deductionCoveragePct` will report 0% regardless of confirmed conversions.
**Impact:** Misleading deduction coverage KPI score in any JSON-backend deployment.
**Suggested action:** Document the SQLite dependency in `_build_manual_context` docstring. Add a backend guard or warning if this becomes relevant. Defer to Task 15 (tests).

---

## Deliverable checklist

`core/agents/manual_operativo_agent.py`:
- [ ] `ManualOperativoAgent` extends `BaseAgent` with `RESPONSE_MODEL = None`
- [ ] `INPUT_SCHEMA` has `user_message`; `OUTPUT_SCHEMA` has `reply` and `raw_response`
- [ ] `_generate_prompt()` injects full context string into system prompt
- [ ] `_process_response()` returns `{"reply": response, "raw_response": response}`

`core/agents/__init__.py`:
- [ ] `ManualOperativoAgent` imported and added to `__all__`

`core/__init__.py`:
- [ ] `ManualOperativoAgent` added to agents import block and `__all__`

`gradio_app/sections/manual_operativo.py`:
- [ ] `_build_manual_context(data_lake, session_id) -> str` uses `stable_entity_id`, reads all entities, calls `compute_readiness_report()`, returns plain-text string
- [ ] Empty session handled: returns minimal string without crashing
- [ ] State 1: single centered "Generar Manual Operativo" button
- [ ] State 2: `gr.Row` with `gr.Column(scale=7)` tabs + `gr.Column(scale=3)` persistent agent sidebar
- [ ] 4 tabs rendered: Resumen, Mi Restaurante, Recetas, Inventario
- [ ] Resumen: overall score + grade, per-dimension Unicode progress bars, logros checklist, áreas de oportunidad with specific entity names
- [ ] Unit mismatch case formatted in plain language: "receta usa X, inventario usa Y" — not the raw technical reason string
- [ ] `_build_resumen_md` receives loaded registries to resolve unit IDs to symbols for the mismatch display
- [ ] Mi Restaurante: restaurant name, type, operator, standardization level, entity counts
- [ ] Recetas: deduction-readiness badge per recipe, ingredient list with linked/unlinked status
- [ ] Inventario: grouped Perecederos / No Perecederos with purchase_unit → stock_unit, factor, family
- [ ] "Regenerar Manual" button updates tab Markdown components in-place (no page reload)
- [ ] Agent chat wired with `render_chat_panel()` and `create_agent(ManualOperativoAgent, ...)`

`tests/unit/test_manual_operativo.py`:
- [ ] `test_build_manual_context_returns_string`
- [ ] `test_build_manual_context_includes_recipe`
- [ ] `test_build_manual_context_includes_inventory`
- [ ] `test_build_manual_context_empty_session`
- [ ] `test_build_resumen_md_all_na_kpis`
- [ ] `test_manual_operativo_agent_process_response`
- [ ] `test_manual_operativo_agent_output_schema`
- [ ] `test_manual_operativo_agent_input_schema`
- [ ] `test_manual_operativo_agent_qa_live` (skipped without `ANTHROPIC_API_KEY`)
- [ ] `test_manual_operativo_agent_deduction_live` (skipped without `ANTHROPIC_API_KEY`)

`docs/Architecture/sections/manual_operativo.md`:
- [ ] As-built spec: two-state UI, tab layout, agent sidebar, KPI integration, `_build_manual_context` contract

`CLAUDE.md` + `.taskmaster/tasks/tasks.json`:
- [ ] Task 12 status updated to `done`
