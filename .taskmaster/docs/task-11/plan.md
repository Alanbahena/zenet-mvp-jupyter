# Task 11 — Estructura section plan

## Goal

Implement the Estructura section: enrich the base inventory from Alineamiento with
purchase unit, stock unit, conversion factor, family, and category via a batch-inference
agent and editable Gradio table, persisting fully structured `InventoryItem` records to
DataLake.

- **Prior step delivered:** base `InventoryItem` shells (name only, no units) saved to
  DataLake by AlignmentAgent confirm flow (Task 10).
- **Next section needs:** fully structured `InventoryItem` records with `stock_unit_id`,
  `purchase_unit_id`, `purchase_to_stock_factor` to enable deduction logic in Manual
  Operativo (Task 12).

---

## Key design decisions

### 1. Two-unit model on InventoryItem

Replace the single `unit_id` field with three explicit fields:

```python
stock_unit_id: int            # always standard: kg, L, pza, g, ml — used for deduction
purchase_unit_id: int         # how the operator buys it — can be non-standard (caja, bolsa)
purchase_to_stock_factor: float = 1.0   # 1 purchase_unit = X stock_units
```

**Rationale:** The old `unit_id` was ambiguous — it could be either the purchase unit or the
stock unit depending on context. Making both explicit removes the ambiguity. Deduction always
reads `stock_unit_id` (always standard). `purchase_to_stock_factor` replaces the separate
`InventoryUnitEquivalence` entity for this relationship.

### 2. InventoryUnitEquivalence removed entirely

`InventoryUnitEquivalence` and `InventoryUnitEquivalenceRegistry` are removed from:
- `core/domain/data_model.py`
- `core/domain/serialization.py`
- `core/storage/persistence.py`
- `core/storage/schema.py` (table dropped)
- `core/__init__.py`

**Rationale:** With `purchase_to_stock_factor` on `InventoryItem` directly, the separate
equivalence entity serves no purpose. Keeping both creates two competing ways to express
the same relationship. `normalization.py` is updated to read from `InventoryItem` fields
instead of an equivalence registry lookup.

### 3. Standard unit chains hardcoded

Standard inventory unit chains are hardcoded in templates and seed data — not collected
from the operator:

```
g   → root (base_unit_id=None, factor_to_base=1.0)
kg  → base_unit_id=g,  factor_to_base=1000.0
ml  → root (base_unit_id=None, factor_to_base=1.0)
L   → base_unit_id=ml, factor_to_base=1000.0
pza → root (base_unit_id=None, factor_to_base=1.0)
```

**Rationale:** These are universal physical facts. No operator input needed. Enables
`convert_quantity` and `to_base_quantity` to resolve cross-unit deductions automatically.

Note: template units use `id=0`. Standard unit chains cannot be wired at template
definition time — they must be applied when assigning real IDs to a registry.

### 4. Equivalence question only when purchase ≠ stock

The agent only asks the operator for a conversion factor when `purchase_unit ≠ stock_unit`.
The majority of items (bistec → kg/kg, limón → pza/pza) have matching units and generate
zero questions. Realistic load: 3–8 questions for a 50-item inventory.

`pza` is always standard — never requires an equivalence question regardless of context.

### 5. Category-by-category flow

Perecederos are processed first, then No Perecederos. Each category completes (agent
proposes → operator reviews table → operator confirms) before the next starts.

At the Perecederos → No Perecederos transition, the agent asks: "¿Hay algún artículo no
perecedero que quieras agregar que no venga de tus recetas?" to capture items outside the
base inventory (cleaning supplies, packaging, etc.).

### 6. Batch inference + table review (not per-item Q&A)

Agent processes all items in a single LLM call and returns a full structured proposal.
Operator reviews an editable `gr.Dataframe` — not a chat Q&A loop. Chat is used only for
exception handling (missing data, equivalence questions for non-standard units).

Confidence flags per row:
- `✅ alta` — standard unit, high-confidence inference
- `⚠️ estimado` — agent inference, operator should verify
- `❌ falta dato` — missing required field, agent will ask

### 7. Missing purchase unit resolution

When purchase unit is absent from the uploaded file, the agent asks once for the whole
group:

> "Encontré X artículos sin unidad de compra. Puedo:
> - Recibir un recibo o factura de tu proveedor y llenarlo con datos exactos
> - O proponer las unidades basándome en el nombre de cada artículo para que tú las confirmes
> ¿Cuál prefieres?"

Path A (supplier receipt): agent extracts from document, operator confirms.
Path B (agent proposes): agent infers, rows flagged as `⚠️ estimado`.

### 8. No LangGraph

Single-agent conversational flow. Same pattern as `configuracion.py` and `alineamiento.py`.

---

## UX sequence

### On load
Base inventory displayed split into Perecederos / No Perecederos columns. Units empty.

### Step 1 — Perecederos
Agent opens:
> "Aquí está tu inventario base. Vamos a estructurarlo en dos partes. Comenzaremos con
> los perecederos — tienes X artículos. ¿Tienes un archivo con tu inventario de
> perecederos, o prefieres hacerlo de forma conversacional?"

Three paths: file upload / conversational / both.

### Step 2 — Bulk inference
Agent processes file or conversation in one LLM call. Infers: `stock_unit`, `purchase_unit`,
`factor`, `family`, `category`, `description`. Detects new items not in base inventory.

### Step 3 — Missing purchase units (if any)
Agent asks once for the whole group (see decision §7 above). Skipped if no missing units.

### Step 4 — Operator reviews table
Full structured proposal as editable `gr.Dataframe`. Operator scans, edits flagged rows.

### Step 5 — Gap resolution via chat
Agent asks targeted questions only for `❌` rows. Equivalence only when `purchase ≠ stock`.

### Step 6 — Perecederos confirmed
Operator confirms. Perecedero `InventoryItem` records saved to DataLake.

### Step 7 — No Perecederos transition
Agent transitions:
> "Perfecto, perecederos listos. Ahora pasemos a los no perecederos — tienes X artículos
> en tu inventario base. Antes de continuar, ¿hay algún artículo no perecedero que quieras
> agregar que no venga de tus recetas?"

Steps 2–6 repeat for No Perecederos.

---

## Files to create / modify

| File | Action | Summary |
|---|---|---|
| `core/domain/data_model.py` | Modify | Two-unit fields on `InventoryItem`; standard unit chains in templates; remove `InventoryUnitEquivalence` and `InventoryUnitEquivalenceRegistry` |
| `core/storage/schema.py` | Modify | Update `inventory_item` table; drop `inventory_unit_equivalence` table |
| `core/domain/serialization.py` | Modify | Update `inventory_item_to_dict/from_dict`; remove equivalence functions |
| `core/storage/persistence.py` | Modify | Update SqliteStorage handlers for `inventory_item`; remove `inventory_unit_equivalence` handler; remove from `_SQLITE_ENTITY_TYPES` |
| `core/operations/normalization.py` | Modify | Update `to_base_quantity` / `from_base_quantity` to read from `InventoryItem` instead of equivalence registry |
| `core/domain/data_model_utils.py` | Modify | Audit and update any reference to `unit_id` or `InventoryUnitEquivalence` on `InventoryItem` |
| `scripts/seed_data.py` | Modify | Add `base_unit_id` + `factor_to_base` chains to `INVENTORY_UNITS` |
| `core/agents/structuring_agent.py` | Create | `StructuringAgent(BaseAgent)` with batch inference system prompt and structured output |
| `gradio_app/sections/estructura.py` | Modify | Replace stub with full `render()` |
| `gradio_app/sections/alineamiento.py` | Modify | Update `InventoryItem` construction to use `stock_unit_id` + `purchase_unit_id` |
| `core/agents/__init__.py` | Modify | Export `StructuringAgent` |
| `core/__init__.py` | Modify | Re-export `StructuringAgent`; remove `InventoryUnitEquivalence` exports |
| `scripts/seed_data.py` | Modify | Standard unit chains in `INVENTORY_UNITS` |
| `tests/unit/test_structuring_agent.py` | Create | Mocked + live tests |
| `docs/Architecture/sections/estructura.md` | Create | New section architecture doc |
| `docs/Architecture/architecture-data-model.md` | Modify | `InventoryItem` two-unit fields; remove `InventoryUnitEquivalence` section |
| `docs/Architecture/architecture-normalization.md` | Modify | Update deduction path; remove equivalence registry references |
| `docs/Architecture/architecture-persistence.md` | Modify | `inventory_item` table changes; `inventory_unit_equivalence` table dropped |
| `docs/Architecture/architecture-agent-framework.md` | Modify | Add `StructuringAgent` to agent inventory |
| `docs/Architecture/architecture-data-model-utils.md` | Modify | Update if any utils reference old `unit_id` or equivalence |

---

## Subtask breakdown

### 11.1 — Data model prerequisites
**Files:** `data_model.py`, `seed_data.py`

1. Update `_INVENTORY_UNIT_TEMPLATES` for all 5 restaurant types with standard unit chains.
   Note: chains must be wired when assigning real IDs to a registry, not in template objects
   (all templates use `id=0`). Document this constraint clearly in the module docstring.
2. Update `InventoryItem` dataclass: remove `unit_id`; add `stock_unit_id: int`,
   `purchase_unit_id: int`, `purchase_to_stock_factor: float = 1.0`.
3. Remove `InventoryUnitEquivalence` dataclass and `InventoryUnitEquivalenceRegistry` class
   from `data_model.py`.
4. Update `InventoryItem.add_ingredient` and any dependent methods that reference `unit_id`,
   `equivalence_base_unit_id`, or `equivalence_factor_to_base`.
5. Update `seed_data.py` `INVENTORY_UNITS` with correct `base_unit_id` / `factor_to_base`
   for `g`, `kg`, `ml`, `L`.

### 11.2 — Schema + serialization + persistence + normalization
**Files:** `schema.py`, `serialization.py`, `persistence.py`, `normalization.py`,
`data_model_utils.py`, `alineamiento.py`

1. `schema.py`: update `inventory_item` table (replace `unit_id` with three new columns);
   remove `inventory_unit_equivalence` table creation; update indexes.
2. `serialization.py`: update `inventory_item_to_dict` / `inventory_item_from_dict`; remove
   `inventory_unit_equivalence_to_dict` / `inventory_unit_equivalence_from_dict`.
3. `persistence.py`: update SqliteStorage `save`/`load` for `inventory_item`; remove
   `inventory_unit_equivalence` handler; remove from `_SQLITE_ENTITY_TYPES`; update
   `_get_entity_registries` in DataLake (remove `dm.InventoryUnitEquivalence` from
   `class_to_type`, remove `"inventory_unit_equivalence"` from `type_to_from_dict` and
   `type_to_to_dict`); remove the `inventory_unit_equivalence` branch from
   `_datalake_entity_id`.
4. `normalization.py`: the deduction path change is surgical — do not pass `InventoryItem`
   to `to_base_quantity`. The actual changes are:
   - In `normalize_recipe_for_deduction`: replace every read of `item.unit_id` with
     `item.stock_unit_id` (stock unit is always standard; deduction uses it directly).
   - Remove the `equivalence_registry: Optional[InventoryUnitEquivalenceRegistry] = None`
     parameter from `to_base_quantity`, `from_base_quantity`, `to_base_quantity_by_id`,
     and `from_base_quantity_by_id`.
   - Remove the equivalence lookup branch (`if inventory_item_id is not None and
     equivalence_registry is not None`) inside each of those four functions.
   - Remove `inventory_item_id` parameter from the same four functions (no longer needed
     without equivalence registry).
   - The standard unit chain (`g→kg`, `ml→L`) on `InventoryUnit.base_unit_id` /
     `factor_to_base` still handles all standard conversions unchanged.
5. `data_model_utils.py`: three specific changes required:
   - `validate_recipe_for_deduction:162`: change `item.unit_id` → `item.stock_unit_id`.
   - `units_used_by_recipe:234`: change `inventory_ids.add(item.unit_id)` →
     `inventory_ids.add(item.stock_unit_id)`.
   - `create_inventory_item_from_ingredient`: update signature from
     `(ingredient, category_id, unit_id_for_inventory, family_id=None)` to
     `(ingredient, category_id, stock_unit_id, purchase_unit_id,
     purchase_to_stock_factor=1.0, family_id=None)` and update the `InventoryItem`
     construction inside accordingly. All callers of this function must be updated.
6. `alineamiento.py`: update `InventoryItem` construction in confirm flow to use
   `stock_unit_id` and `purchase_unit_id`.

### 11.3 — StructuringAgent
**File:** `core/agents/structuring_agent.py`

1. Define `_StructuringItemProposal(BaseModel)`: `name`, `stock_unit_symbol`,
   `purchase_unit_symbol`, `purchase_to_stock_factor`, `family_name`, `category_name`
   (`Perecedero` | `No perecedero`), `description`, `confidence`
   (`high` | `estimated` | `missing`), `is_new_item: bool`.
2. Define `_StructuringResponse(BaseModel)`: `reply: str`,
   `proposals: list[_StructuringItemProposal] | None`,
   `needs_supplier_doc: bool | None`, `gap_questions: list[str] | None`.
3. Implement `StructuringAgent(BaseAgent)`:
   - System prompt: batch inference mode; infer all fields from item name + restaurant type;
     flag missing purchase units as a group; only ask equivalence when `purchase ≠ stock`;
     `pza` always standard; no hallucination rule.
   - `_generate_prompt(input_data, context)`: inject base inventory items (by category),
     restaurant type, families, standard unit symbols.
   - `_process_response(response)`: merge proposals into `_data_store`; accumulate gap items.

### 11.4 — Estructura section UI
**File:** `gradio_app/sections/estructura.py`

1. `_load_structuring_context(data_lake, session_id)`: load `restaurant`, `classification`,
   `inventory_unit`, `family_inventory`, `inventory_item` entities.
2. `_initial_greeting()`: opens with Perecederos count and data collection question.
3. `_make_chat_fn(agent, context)`: same load/run/save_state pattern as `alineamiento.py`;
   updates `gr.State` for table proposals; handles file upload via
   `[Contenido de archivo...]` prefix.
4. `_make_confirm_fn(data_lake, session_id)`: generator pattern; resolves `stock_unit_id`
   and `purchase_unit_id` from symbol → DataLake `inventory_unit` records; saves enriched
   `InventoryItem` records; yields loading → result.
5. `render(session_id, data_lake)`: two-column layout:
   - Left: `gr.Chatbot` + `gr.Textbox` + `gr.UploadButton`
   - Right: editable `gr.Dataframe` (columns: Artículo, Compra, Inventario, Factor, Familia,
     Categoría, Estado) + Confirm button
   - Category transition logic: Perecederos confirm → trigger No Perecederos flow.

### 11.5 — Exports
**Files:** `core/agents/__init__.py`, `core/__init__.py`

1. `core/agents/__init__.py`: add `StructuringAgent` import and `__all__` entry.
2. `core/__init__.py`: add `StructuringAgent`; remove `InventoryUnitEquivalence`,
   `InventoryUnitEquivalenceRegistry`, `inventory_unit_equivalence_to_dict`,
   `inventory_unit_equivalence_from_dict` from imports and `__all__`.

### 11.6 — Tests
**File:** `tests/unit/test_structuring_agent.py`

Mocked tests (12):
- `test_create_via_factory`
- `test_response_model_fields`
- `test_bulk_inference_standard_units`
- `test_bulk_inference_non_standard_unit`
- `test_missing_purchase_unit_flag`
- `test_no_equivalence_for_pza`
- `test_new_item_detection`
- `test_data_store_accumulation`
- `test_perecedero_category_inference`
- `test_no_perecedero_category_inference`
- `test_context_injection`
- `test_confirm_fn_saves_inventory_items`

Live tests (2, guarded by `ANTHROPIC_API_KEY`):
- `test_live_bulk_inference_taqueria`
- `test_live_gap_question_non_standard_unit`

### 11.7 — Documentation and closure
**Files:** all architecture docs listed below + `CLAUDE.md` + `tasks.json`

1. Create `docs/Architecture/sections/estructura.md`: section overview, agent, context
   loader, UI layout, confirm flow, category-by-category flow, missing unit resolution,
   equivalence rule, Gradio wiring.
2. Update `docs/Architecture/architecture-data-model.md`: `InventoryItem` two-unit fields;
   standard unit chains; remove `InventoryUnitEquivalence` section.
3. Update `docs/Architecture/architecture-normalization.md`: updated deduction path reading
   from `InventoryItem` directly; remove equivalence registry references.
4. Update `docs/Architecture/architecture-persistence.md`: `inventory_item` table changes;
   `inventory_unit_equivalence` table removed; `_SQLITE_ENTITY_TYPES` updated.
5. Update `docs/Architecture/architecture-agent-framework.md`: add `StructuringAgent` to
   agent inventory table.
6. Update `docs/Architecture/architecture-data-model-utils.md`: update if any utils
   referenced `unit_id` or `InventoryUnitEquivalence`.
7. Update `CLAUDE.md`: Task 11 → done, Task 12 → next.
8. Update `tasks.json`: Task 11 status → done.

---

## Subtask execution order

```
11.1 → 11.2 → 11.3 → 11.4 → 11.5 → 11.6 → 11.7
```

All sequential. 11.2 depends on 11.1 (dataclass must exist before schema/serialization).
11.3 depends on 11.2 (agent uses updated InventoryItem). 11.4 depends on 11.3.

---

## Risks and open questions

### [OPEN] — Configuración-created sessions lack standard unit chains
**Source:** Validation of subtask 11.1
**Problem:** `_INVENTORY_UNIT_TEMPLATES` uses `id=0` for all units; `kg.base_unit_id = g.id` cannot be wired at template definition time. Sessions created via the Configuración flow will have `base_unit_id=None` for all standard units. Only seeded sessions (seed_data.py) will have correct chains.
**Impact:** `convert_quantity` and `to_base_quantity` will fail for cross-unit deductions (e.g. kg→g) in non-seeded sessions. This does not affect Task 11 (no deduction runs in Estructura) but will break Task 12 (Manual Operativo) for real operator sessions.
**Suggested action:** Before starting Task 12, add `apply_standard_unit_chains(units)` helper to `data_model.py` (wires chains by symbol after real IDs assigned) and call it in `configuracion.py` after units get their real IDs. Defer to Task 12 planning.

### [OPEN] — Conversational path (no file) not specified
**Source:** Validation of Task 11
**Problem:** 11.3 system prompt and 11.4 chat fn mention "conversational path" as a valid option but give no detail on how the agent handles it differently from the file path. No turn-by-turn flow is defined.
**Impact:** Implementer will invent the conversational flow during 11.3/11.4, risking inconsistency with the batch inference design.
**Suggested action:** Add a "Conversational path" subsection to the UX sequence before starting 11.3.

### [OPEN] — Deduplication between uploaded file and base inventory not specified
**Source:** Validation of Task 11
**Problem:** An uploaded file may contain items already in the base inventory (from Alineamiento). No dedup rule is defined in the agent prompt spec or confirm flow.
**Impact:** Duplicate InventoryItem records in DataLake; InventoryItemRegistry will raise "duplicate name" ValueError on confirm.
**Suggested action:** Add dedup rule to 11.3 step 3 (_process_response): if proposal name matches existing base inventory item, treat as enrichment (update), not new item creation.

### [OPEN] — Symbol-to-unit_id resolution fallback not specified
**Source:** Validation of Task 11
**Problem:** `_make_confirm_fn` resolves `stock_unit_id` / `purchase_unit_id` from symbol → DataLake `inventory_unit` records. No fallback defined when a symbol (e.g. "bolsa") doesn't exist in DataLake (wasn't created in Configuración).
**Impact:** Confirm will crash for restaurants using units not in their Configuración inventory_unit list.
**Suggested action:** Add rule to 11.4 step 4: if symbol not found in DataLake, create new `InventoryUnit` record (`is_standard=False`) and save it before constructing `InventoryItem`.

1. **Standard unit chain wiring in templates**: template units use `id=0`, so
   `kg.base_unit_id = g.id` cannot be set at template definition time. Chains must be
   applied when assigning real IDs to a registry. Implementation must document this clearly
   and update the apply-template flow accordingly.

2. **normalization.py signature changes**: removing `equivalence_registry` parameters from
   `to_base_quantity` / `from_base_quantity` is a breaking change for any caller passing
   that argument. Audit all call sites before removing.

3. **Schema migration**: `_create_tables` uses `CREATE TABLE IF NOT EXISTS` — will not alter
   existing tables. Existing SQLite sessions will have stale `unit_id` column.
   `reset_session.py` must be run after 11.2 to pick up schema changes. Document this.

4. **`gr.Dataframe` inline editing**: confirm installed Gradio version supports editable
   cells. If not, the review UX needs a fallback (e.g. editable per-row modal or chat-based
   correction).

5. **Alineamiento confirm flow**: `alineamiento.py` constructs `InventoryItem` with `unit_id`.
   Must be updated in 11.2 before running any live tests. Failure to update will cause
   runtime errors on the Alineamiento confirm button.

6. **`InventoryItem.add_ingredient` callers**: this method references `equivalence_base_unit_id`
   and `equivalence_factor_to_base`. All callers must be identified and updated in 11.1.

---

## MVP ceiling

- Max ~50 inventory items — table review is manageable at this scale
- Operator is the only data source — no supplier catalog integrations
- Setup is one session — iterative enrichment across sessions is post-MVP
- Agent inferences are always visible — nothing auto-confirmed without operator seeing table

---

## Post-MVP notes (do not implement now)

- Supplier catalog integration: `purchase_unit` + `purchase_to_stock_factor` model makes
  this straightforward to add later
- Network effects: operator corrections feed shared templates for similar restaurant types
- Progressive enrichment: inventory starts rough and improves through daily use
- At 200+ items, trust becomes the bottleneck — not speed. Batch review by supplier or
  family grouping is the right production pattern, not a smarter chatbot
