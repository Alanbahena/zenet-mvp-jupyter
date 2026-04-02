# Manual Operativo Section Architecture

## 1. Overview

The Manual Operativo section is the **6th and final tab** in the pipeline. It synthesizes all
data collected in the previous five sections into a read-only operational manual, and provides
a conversational AI assistant for Q&A and ingredient deduction.

Layout: **two-state** (empty → generated). After generation, the UI splits into a **two-column**
layout: a 4-tab content panel on the left (scale=7) and a persistent chat sidebar on the right
(scale=3).

Data **consumed** (read-only — no writes):

| Entity type | Produced by |
|-------------|-------------|
| `restaurant` | Bienvenida (Task 7) |
| `user` | Bienvenida (Task 7) |
| `classification` | Clasificación (Task 8) |
| `category_recipe` | Configuración (Task 9) |
| `family_inventory` | Configuración (Task 9) |
| `recipe_unit` | Configuración (Task 9) |
| `inventory_unit` | Configuración (Task 9) |
| `inventory_item` | Alineamiento (Task 10) + Estructura (Task 11) |
| `recipe` | Alineamiento (Task 10) |
| `recipe_unit_conversion` | Alineamiento (Task 10) — SQLite-only |

**Implementation files:**

| File | Role |
|------|------|
| `gradio_app/sections/manual_operativo.py` | `render()`, tab builders, `_make_content`, `_build_manual_context` |
| `core/agents/manual_operativo_agent.py` | `ManualOperativoAgent` — read-only Q&A and deduction agent |

---

## 2. Two-State UI

The section renders in two mutually exclusive columns managed by `gr.Column(visible=...)`.

```
State 1 (visible on load)
  gr.Column (state1_col)
    "Genera tu manual operativo..."
    generate_btn → triggers generate_fn

State 2 (hidden until generate_btn clicked)
  gr.Column (state2_col)
    regen_btn
    gr.Row
      gr.Column(scale=7)   ← 4-tab content panel
      gr.Column(scale=3)   ← persistent chat sidebar
```

**`generate_fn(sid)`** returns 8 values:

```python
gr.update(visible=False),   # state1_col hidden
gr.update(visible=True),    # state2_col shown
resumen,                    # str
mi_rest,                    # str
recetas,                    # str
inv_header,                 # str
perecederos,                # list[list]
no_perecederos,             # list[list]
```

**`regen_fn(sid)`** returns 6 values (skips column visibility toggles):

```python
resumen, mi_rest, recetas, inv_header, perecederos, no_perecederos
```

### Gradio wiring

| Event | Handler | Inputs | Outputs |
|-------|---------|--------|---------|
| `generate_btn.click` | `generate_fn` | `[session_id]` | `[state1_col, state2_col, resumen_md, mi_rest_md, recetas_md, inv_header_md, perecederos_tbl, no_perecederos_tbl]` |
| `regen_btn.click` | `regen_fn` | `[session_id]` | `[resumen_md, mi_rest_md, recetas_md, inv_header_md, perecederos_tbl, no_perecederos_tbl]` |
| chat send | `chat_fn` (via `render_chat_panel`) | `[message, history, session_id]` | `[history, textbox]` |

---

## 3. `_make_content` — Content Assembly

```python
def _make_content(data_lake, sid: str) -> tuple[str, str, str, str, list[list], list[list]]
```

Returns `(resumen_md, mi_rest_md, recetas_md, inv_header_md, perecederos_rows, no_perecederos_rows)`.

Returns `(placeholder, placeholder, placeholder, "", [], [])` when no `restaurant` entity exists for the session.

**Steps:**

1. Load `restaurant`, `user`, `classification` by `stable_entity_id(sid)`.
2. Load all entity lists: `recipe_unit`, `inventory_unit`, `category_recipe`, `family_inventory`, `recipe`, `inventory_item`, `recipe_unit_conversion`.
3. Build in-memory registries: `RecipeUnitRegistry`, `InventoryUnitRegistry`, `CategoryRecipeRegistry`, `FamilyInventoryRegistry`, `InventoryItemRegistry`, `RecipeUnitConversionRegistry`.
4. Call `compute_readiness_report(restaurant, recipes=..., ...)` to produce the KPI report.
5. Call each tab builder to produce output values.

`recipe_unit_conversion` is a SQLite-only entity type. On a JSON backend the conversion registry is always empty and `deductionCoveragePct` reports 0%.

---

## 4. Tab Builders

### 4.1 `_build_resumen_md`

```python
def _build_resumen_md(
    report: dict,
    recipe_unit_registry: RecipeUnitRegistry,
    inventory_unit_registry: InventoryUnitRegistry,
    item_registry: InventoryItemRegistry,
    *,
    recipes: list,
    items: list,
) -> str
```

Pure function. Returns HTML string. Always returns a non-empty string even when all KPIs are `na`.

Renders five blocks in order:

| Block | Content |
|-------|---------|
| Score hero card | Score (0–100) on the left, circular grade badge on the right. `grade_color` and `grade_bg` keyed by first letter of grade. |
| Dimension progress bars | Container card with one progress bar per dimension. Dimensions in `_SKIP_DIMENSIONS` (`taxonomy`) are omitted. |
| Deduction coverage highlight | Blue `#eff6ff` box — only shown when `normalization.deductionCoveragePct` status is not `na`. |
| Logros chips | Green rounded pills (`background:#dcfce7;color:#15803d;border-radius:999px`). Computed from registry sizes, recipe count, and item count. |
| Áreas de oportunidad cards | Up to 3 generic fail/warn KPI cards (bordered left, red or amber). Unit mismatch KPIs (`_UNIT_MISMATCH_REASON`) are segregated into a dedicated mismatch card. KPIs in `_HIDDEN_KPI_IDS` are suppressed. |

**Module-level constants:**

```python
_SKIP_DIMENSIONS  = {"taxonomy"}   # weight=0, always na
_HIDDEN_KPI_IDS   = {
    "recipes.stepsPresentPct",
    "recipes.ingredientsInventoryItemIdSetPct",
    "inventory.itemsWithFamilyPct",
    "inventory.itemsWithDescriptionPct",
}
_UNIT_MISMATCH_REASON = (
    "Missing conversion entry "
    "(ingredient unit family differs from inventory item unit family)"
)
```

**Unit mismatch resolution helpers:**

| Helper | Input | Output |
|--------|-------|--------|
| `_parse_ingredient_name_from_ref(ref)` | `"Recipe#N: 'ingredient_name'"` | ingredient name string |
| `_resolve_mismatch_units(ing_name, recipes, rur, ir, iur)` | ingredient name + registries | `(recipe_unit_symbol, inventory_unit_symbol)` or `(None, None)` |

### 4.2 `_build_mi_restaurante_md`

```python
def _build_mi_restaurante_md(
    restaurant,
    user_data: dict,
    classification_data: dict,
    *,
    recipe_units, inventory_units, categories, families, recipes, items,
) -> str
```

Pure function. Returns Markdown + HTML string.

Renders in order:
1. `## {restaurant.name}` heading.
2. Flex row of labeled fields (Tipo, Operador, Nivel de estandarización) via `_field()` helper.
3. Description callout (`background:#f0f9ff;border-left:3px solid #38bdf8`) — only when non-empty.
4. **Resumen de configuración** heading + 3-column CSS grid of stat cards via `_stat()` helper.

Stat card counts: Recetas, Artículos de inventario, Categorías de receta, Familias de inventario, Unidades de receta, Unidades de inventario.

Restaurant type resolved via `DEFAULT_RESTAURANT_TYPES` (`core.domain.data_model`).

### 4.3 `_build_recetas_md`

```python
def _build_recetas_md(
    recipes: list,
    recipe_unit_registry: RecipeUnitRegistry,
    item_registry: InventoryItemRegistry,
    category_registry: CategoryRecipeRegistry,
    inventory_unit_registry: InventoryUnitRegistry,
    conversion_table: RecipeUnitConversionRegistry,
    family_registry: FamilyInventoryRegistry,
) -> str
```

Pure function. Returns `"_(Sin recetas capturadas)_"` when `recipes` is empty.

Renders one dark-mode HTML card per recipe (`background:#1e293b;border:1px solid #334155`).

Per card structure:

| Element | Detail |
|---------|--------|
| Recipe name | `color:#f1f5f9;font-weight:700` |
| Status pill | Ready: `background:#14532d;color:#86efac`. Incomplete: `background:#78350f;color:#fcd34d`. Determined by `validate_recipe_for_deduction()`. |
| Category chip | `background:#1e3a5f;color:#93c5fd` |
| Description | `color:#94a3b8;font-style:italic` — omitted when empty |
| Ingredient table | 3 columns: INGREDIENTE, CANTIDAD, INVENTARIO. Row separator: `border-top:1px solid #334155`. |

Ingredient link status:
- `&#9679; vinculado` (`color:#86efac`) — when `ing.inventory_item_id` is set OR `item_registry.get_by_name(ing.name)` returns a result.
- `&#9679; sin vincular` (`color:#fcd34d`) — otherwise.

### 4.4 `_build_inventario_header` + `_build_inventario_rows`

```python
def _build_inventario_header(perecederos: list, no_perecederos: list) -> str
```

Returns a stat bar HTML string showing total / perecederos count / no perecederos count.
Returns `"_Sin artículos de inventario._"` when total is 0.

```python
def _build_inventario_rows(
    items: list,
    inventory_unit_registry: InventoryUnitRegistry,
    family_registry: FamilyInventoryRegistry,
) -> tuple[list[list], list[list]]
```

Returns `(perecederos_rows, no_perecederos_rows)`.

Row columns:

| Index | Field |
|-------|-------|
| 0 | Artículo (item name) |
| 1 | Familia (family name or `"—"`) |
| 2 | U. Compra (purchase unit symbol) |
| 3 | U. Stock (stock unit symbol) |
| 4 | Factor (purchase_to_stock_factor) |

Items with `category_id == 1` → perecederos. All others → no perecederos.

The Inventario tab renders two `gr.Dataframe` components (`interactive=False`) with section
headers as static `gr.Markdown` (green for Perecederos, blue for No Perecederos).

---

## 5. `_build_manual_context` — Agent Context Assembly

```python
def _build_manual_context(data_lake, session_id: str) -> str
```

Assembles all DataLake entities for a session into a structured plain-text block for injection
into `ManualOperativoAgent`'s system prompt.

Returns `"Sin datos de restaurante para esta sesión."` when no restaurant entity exists.

**Output sections (in order):**

```
PERFIL DEL RESTAURANTE
  Nombre: ...
  Tipo: ...
  Operador: ...
  Nivel de estandarización: ...
  Descripción: ...      (omitted when empty)

PUNTUACIÓN DE ESTANDARIZACIÓN
  Puntuación general: X / 100   Calificación: Y
  {dimension title}: X%  [status]
  ...

ÁREAS DE OPORTUNIDAD        (omitted when no fail/warn KPIs)
  [FAIL|WARN] {kpi title}
    - {evidence ref}
    ...

RECETAS (N total)
  Receta: {name}  Categoría: {category}
    - {ingredient}: {quantity} {unit_symbol}  [vinculado|sin vincular]
    ...

INVENTARIO (N artículos)
  {name}  compra: {pu_sym}  stock: {su_sym}  factor: {factor}  familia: {family}
  ...

INSTRUCCIONES PARA DEDUCCIÓN
  (deduction arithmetic rules for the agent)
```

**Registry construction is identical to `_make_content`** — both functions independently build
all registries and compute the readiness report. There is no shared cache between them.

---

## 6. ManualOperativoAgent

**File:** `core/agents/manual_operativo_agent.py`

```python
class ManualOperativoAgent(BaseAgent):
    RESPONSE_MODEL = None   # plain prose, no structured output
```

### Schemas

**INPUT_SCHEMA**

| Key | Type | Description |
|-----|------|-------------|
| `user_message` | `str` | Operator question or deduction request in natural language |

**OUTPUT_SCHEMA**

| Key | Type | Description |
|-----|------|-------------|
| `reply` | `str` | Agent response in Spanish |
| `raw_response` | `str` | Full LLM response string (identical to `reply` for plain-prose agents) |

### `_generate_prompt`

| Parameter | Source |
|-----------|--------|
| `manual_text` | `context["manual_context"]` |
| `user_message` | `input_data["user_message"]` |

System prompt capabilities declared to the agent:
1. Answer questions about restaurant data (recipes, inventory, config, standardization score).
2. Perform ingredient deduction arithmetic: quantity × portions, purchase unit conversion via factor.
3. Explain how to improve the standardization score.

System prompt constraint: **never modifies data** — redirects change requests to the appropriate pipeline section.

### `_process_response`

Returns `{"reply": response, "raw_response": response}`. No parsing — raw LLM text is the reply.

### Agent instantiation

Created fresh per `render()` call at module load time (not per request):

```python
provider = ClaudeProvider()
agent = create_agent(ManualOperativoAgent, provider=provider, name="manual_operativo")
```

`ConversationMemory` is maintained within the agent instance across chat turns in a single
Gradio session. Memory resets when the app restarts.

---

## 7. Chat Sidebar

Rendered via `render_chat_panel(chat_fn, session_id, data_lake)` from `gradio_app.components`.

**`chat_fn(message, history, sid)`:**

1. Build `context = {"manual_context": _build_manual_context(data_lake, sid)}`.
2. Call `agent.run(input_data={"user_message": message}, context=context)`.
3. Append user + assistant turns to `history`.
4. Return `(history, "")` — clears the textbox.

The context is rebuilt on every turn from the current DataLake state. This means the agent
always sees the latest data if the operator regenerates or modifies data in another section.

---

## 8. KPI Integration

`compute_readiness_report` is called by both `_make_content` (for UI rendering) and
`_build_manual_context` (for agent context). The report schema:

| Top-level key | Type | Description |
|---------------|------|-------------|
| `overall` | `dict` | `score_0_100`, `grade` |
| `dimensions` | `list[dict]` | Per-dimension `dimension_id`, `title`, `score_0_100`, `status` |
| `kpis` | `list[dict]` | Per-KPI `kpi_id`, `title`, `status`, `severity`, `numerator`, `denominator`, `evidence` |

KPI `status` values: `"ok"`, `"warn"`, `"fail"`, `"na"`.

Grade letters: `A`, `B`, `C`, `D`, `F` — mapped to color/background pairs in `_build_resumen_md`.

---

## 9. Design Conventions

**Dark-mode card pattern (Recetas tab):**

All recipe cards use explicit `background:#1e293b` (dark slate) rather than relying on
Gradio's background inheritance. Text colors are light:

| Use | Color |
|-----|-------|
| Recipe name | `#f1f5f9` |
| Description | `#94a3b8` |
| Ingredient name | `#e2e8f0` |
| Ingredient quantity | `#cbd5e1` |
| Column headers | `#94a3b8` |
| Row separator | `#334155` |
| Linked status | `#86efac` |
| Unlinked status | `#fcd34d` |

**Light-mode card pattern (Resumen, Mi Restaurante tabs):**

Score hero and dimension cards use `background:#f8fafc` / `background:#fff` with `border:#e2e8f0`
for contrast against Gradio's default white panel background.

---

## 10. Test Coverage

**File:** `tests/unit/test_manual_operativo.py`

| Class | Tests | Scope |
|-------|-------|-------|
| `TestBuildManualContext` | 4 | `_build_manual_context`: restaurant name included, recipe included, inventory item included, empty session returns string |
| `TestBuildResumenMd` | 1 | All-NA KPIs renders `"0 / 100"` |
| `TestBuildRecetasMd` | 2 | Empty recipes returns placeholder; linked ingredient shows `"&#9679; vinculado"` |
| `TestBuildInventarioMd` | 1 | Groups items by category (Perecederos / No Perecederos) |
| `TestManualOperativoAgent` | 4 | Schema keys, `RESPONSE_MODEL` is None, mock run returns `reply` + `raw_response` |
| `TestManualOperativoAgentLive` | 2 | Live: responds in Spanish; deduction reply contains digits. Guarded by `ANTHROPIC_API_KEY`. |

**Known test file constraint:** The `TestBuildInventarioMd` test imports `_build_inventario_md`
(the pre-rename name). This import must be updated to `_build_inventario_rows` and the test
adapted to the tuple return type `(perecederos_rows, no_perecederos_rows)`.
The `TestBuildRecetasMd.test_linked_ingredient_shows_vinculado` assertion must match the HTML
entity `&#9679; vinculado` rather than a plain text literal.
