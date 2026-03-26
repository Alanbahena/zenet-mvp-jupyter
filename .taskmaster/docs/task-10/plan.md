# Task 10 — Alineamiento section: LangGraph multi-agent workflow and Gradio UI

## Goal

Walk the operator through capturing all their recipes and automatically proposing inventory
item shells from those recipes. Delivers a populated recipe registry and seed `InventoryItem`
records (name, category, family, best-effort unit) for Task 11 (Estructura) to complete with
unit assignments and equivalences.

**Builds on:** Task 9 (Configuración) — categories, families, recipe units, and inventory units
saved to DataLake. Task 17 — `restaurant_description` available in classification entity.
**Required by:** Task 11 (Estructura) — receives saved `Recipe` entities and `InventoryItem`
shells; adds equivalences, unit corrections, and structural validation.

---

## Dependencies

- Tasks 1–9 and Task 17 all `done`
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in `.env`
- `langgraph` installed (already present)
- File parsing libraries — must add via `uv add` before 10.2:
  - `pypdf` or `pdfplumber` (PDF)
  - `openpyxl` (Excel)
  - `pillow` (images/photos)

---

## Key design decisions

### Recipe-first approach
Start with recipes; inventory items are derived from recipe ingredients. Operators think in
recipes, not in inventory lists. This is consistent across Level 1–3 operators.

### Single AlignmentAgent
One agent handles extraction and inventory proposal in a single LLM call. No three-step
matching pipeline (exact → normalized → semantic). Simpler, fewer API calls, handles Spanish
variations and operator shorthand naturally.

### LLM-driven deduplication
Load all existing `InventoryItem` names from DataLake into agent context. LLM matches
ingredient names to existing items in one call. No rule-based deduplication pipeline.

### Inventory items saved with best-effort unit_id (Option A)
`InventoryItem.unit_id` is non-optional in the dataclass. Agent infers `unit_id` from recipe
ingredient unit (g → g, pza → pza). Task 11 reviews and corrects. The Task 10 UI does not
show `unit_id` to the operator.

### Inventory panel shows name + category + family + status only
All other `InventoryItem` fields (unit, equivalences) are Task 11's domain. The operator
confirms what is created, not how it is measured.

### Multi-recipe files: upload once, paginate
Agent paginates through detected recipes one by one using `page_index`. Operator does not
re-upload the same file for each recipe.

### Per-ingredient mass equivalents proposed by agent
Non-standard recipe units (taza, cda, cdta, etc.) require per-ingredient equivalents because
volume-to-mass conversion is ingredient-specific: 1 taza de harina ≈ 120 g, 1 taza de arroz
≈ 185 g. The agent uses culinary knowledge to reason per-ingredient and proposes the
equivalent: `"1 taza de harina ≈ 120 g, ¿te parece bien?"`. The operator confirms, corrects,
or says "no sé" (stored as `"agent_estimated"`). Confirmed equivalents are stored
per-ingredient in `RecipeUnitConversionRegistry` with `inventory_item_id` key and appropriate
`source` value (`"operator"` if corrected, `"agent_confirmed"` if accepted as-is,
`"agent_estimated"` if operator skipped).

### RecipeUnitConversion persistence (Task 9 open item)
`RecipeUnitConversionRegistry` currently has no persistence layer. Task 10 adds a
`recipe_unit_conversion` table so confirmed conversions survive session reload and carry
across recipes in the same session.

### equivalence_source tracking
`InventoryUnitEquivalence` (frozen dataclass) and `RecipeUnitConversionEntry` currently
have no `source` field. Task 10 adds:
- `equivalence_source: str` on `InventoryUnitEquivalence` — values: `"operator"` |
  `"agent_confirmed"` | `"agent_estimated"`
- `source: str` on `RecipeUnitConversionEntry` — same values
`InventoryUnitEquivalence` must be unfrozen to allow future updates by Task 11.

### LangGraph conditional branching
`build_sequential_graph` in `graph_utils.py` is linear-only. Task 10 adds
`build_conditional_graph` to support the file-path vs conversational-path branch after the
initial questions node.

### Missing recipe steps: ask once, skip if declined
If the agent extracts a recipe but no preparation steps are found (file without steps, or
operator only dictated ingredients), the agent asks once: "No encontré los pasos de
preparación para [recipe]. ¿Me los puedes dictar?". If the operator provides them, they are
included in the draft. If the operator skips or says "no los tengo", the recipe is saved with
`steps=None`. The agent does not repeat the question. Consistent with the classification
section pattern (one question, no insistence).

### No-hallucination rule on AlignmentAgent
The agent may only extract data present in the uploaded file or the operator's words. It must
never invent, assume, or infer ingredients not stated. If the source is sparse, the draft
stays short and accurate. Downstream agents receive only what the operator provided.

### Standard recipe unit rule (no schema change)
Only 5 recipe unit symbols are standard: `g`, `kg`, `ml`, `L`, `pza`. Any other symbol
(taza, cda, cdta, oz, manojo, pizca, shot, etc.) is non-standard and requires an equivalent
in ml or g. This is defined as a `frozenset` constant in `data_model.py` — no `is_standard`
column on `RecipeUnit`, no schema migration. The AlignmentAgent uses this rule to decide
which ingredients need the `equivalent` column filled.

### Entity creation via tool with operator confirmation
During recipe capture, the operator may reference a category, family, or recipe unit that
was not configured in Task 9. The AlignmentAgent handles this via a registered tool:

1. Agent first proposes mapping to an existing entity from context
2. If no match fits, agent asks: "use an existing one, or create a new one?"
3. Only if operator explicitly confirms → agent calls `create_entity` tool
4. Tool saves the new entity to DataLake, assigns next sequential ID, updates agent context
5. For new non-standard recipe units, agent asks for the approximate equivalent in g or ml

The agent must never create entities without explicit operator confirmation.

---

## Files to modify / create

| File | Action | Summary |
|------|--------|---------|
| `core/operations/normalization.py` | Modify | Add `source: str` field to `RecipeUnitConversionEntry` |
| `core/domain/data_model.py` | Modify | Unfreeze `InventoryUnitEquivalence`; add `equivalence_source: str` field |
| `core/storage/schema.py` | Modify | Add `recipe_unit_conversion` table |
| `core/storage/persistence.py` | Modify | Add `"recipe_unit_conversion"` to `_SQLITE_ENTITY_TYPES`; add save/load/delete/list handlers |
| `core/domain/serialization.py` | Modify | Add `recipe_unit_conversion_to_dict` / `recipe_unit_conversion_from_dict`; register in `_get_entity_registries()` |
| `core/domain/data_model_utils.py` | Modify | Add `load_inventory_item_registry()`; extend `ingredients_to_display()` with `equivalent` and `inventory_link_status` |
| `core/agents/alignment_agent.py` | Create | `AlignmentAgent` — extracts recipe, proposes inventory items, handles deduplication |
| `core/agents/graph_utils.py` | Modify | Add `build_conditional_graph()` for branching graphs |
| `core/agents/__init__.py` | Modify | Export `AlignmentAgent` |
| `core/__init__.py` | Modify | Re-export `AlignmentAgent` |
| `gradio_app/sections/alineamiento.py` | Modify | Replace 5-line stub with full two-column section |
| `tests/unit/test_alignment_agent.py` | Create | 21 mocked + 2 live tests |
| `docs/Architecture/sections/alineamiento.md` | Create | Full section architecture doc |
| `docs/Architecture/architecture-agent-framework.md` | Modify | Document `build_conditional_graph` and `AlignmentGraphState` |
| `docs/Architecture/architecture-data-model.md` | Modify | Document `recipe_unit_conversion` entity and `equivalence_source` addition |
| `docs/Architecture/architecture-persistence.md` | Modify | Document `recipe_unit_conversion` table (composite key, source field) |
| `CLAUDE.md` | Modify | Task 10 status → `done`; Task 11 noted as next |
| `.taskmaster/tasks/tasks.json` | Modify | Task 10 status → `done` |

---

## Implementation steps

### Subtask 10.1 — Data model and persistence prerequisites

**Goal:** Add `recipe_unit_conversion` persistence, `equivalence_source` tracking, and
standard recipe unit constant. All subsequent subtasks depend on this.

1. `core/operations/normalization.py`
   - Add `source: str = "agent_estimated"` field to `RecipeUnitConversionEntry` dataclass.
   - No rename, no removal of existing fields.

2. `core/domain/data_model.py`
   - Add standard recipe unit constant and helper:
     ```python
     STANDARD_RECIPE_UNIT_SYMBOLS = frozenset({"g", "kg", "ml", "L", "pza"})

     def is_standard_recipe_unit(symbol: str) -> bool:
         """Return True if the symbol is a standard recipe unit (no equivalent needed)."""
         return symbol in STANDARD_RECIPE_UNIT_SYMBOLS
     ```
   - Place after `DEFAULT_INVENTORY_CATEGORIES` (near the other fixed-data constants).
   - Grep for any caller using `InventoryUnitEquivalence` as a dict key or set member before
     changing (hashability dependency).
   - Remove `frozen=True` from `@dataclass(frozen=True)` on `InventoryUnitEquivalence`.
   - Add `equivalence_source: str = "operator"` field.

3. `core/storage/schema.py`
   - Add after the `inventory_unit_equivalence` table block:
     ```sql
     CREATE TABLE IF NOT EXISTS recipe_unit_conversion (
         recipe_unit_id    INTEGER NOT NULL,
         family_id         INTEGER,
         inventory_item_id INTEGER,
         quantity          REAL NOT NULL,
         base_unit_id      INTEGER NOT NULL,
         source            TEXT NOT NULL DEFAULT 'agent_estimated',
         PRIMARY KEY (recipe_unit_id, family_id, inventory_item_id)
     )
     ```
   - `family_id` and `inventory_item_id` are nullable (match `RecipeUnitConversionKey` pattern).

4. `core/storage/persistence.py`
   - Add `"recipe_unit_conversion"` to `_SQLITE_ENTITY_TYPES`.
   - Add save handler: composite key `(recipe_unit_id, family_id, inventory_item_id)` using
     UPSERT pattern (same as `inventory_unit_equivalence`). Entity id passed as string
     `"{recipe_unit_id}_{family_id}_{inventory_item_id}"`.
   - Add load, delete, list handlers following the same composite-key pattern.

5. `core/domain/serialization.py`
   - Add `recipe_unit_conversion_to_dict(entry, key) -> dict` and
     `recipe_unit_conversion_from_dict(data) -> tuple[RecipeUnitConversionKey, RecipeUnitConversionEntry]`.
   - Follow the existing standalone function pair pattern (same as `inventory_unit_equivalence_to_dict` / `_from_dict`).

6. `core/domain/data_model_utils.py`
   - Add `load_inventory_item_registry(data_lake, session_id) -> InventoryItemRegistry`:
     - Call `data_lake.list_entity_ids("inventory_item")`
     - Deserialize each via `data_lake.load_entity("inventory_item", id)`
     - Add to a new `InventoryItemRegistry` and return it
     - Returns empty registry if no items exist (no-op for new sessions)
   - Extend `ingredients_to_display()` return dict with:
     - `equivalent: str | None` — per-ingredient mass equivalent for non-standard recipe
       units (e.g. `"≈ 120 g"` for 1 taza de harina, `"≈ 185 g"` for 1 taza de arroz);
       `None` for standard units (g, kg, ml, L, pza)
     - `inventory_link_status: str` — one of:
       `"standard"` | `"agent_estimated"` | `"operator_confirmed"` |
       `"needs_resolution"` | `"matched_existing"`

---

### Subtask 10.2 — AlignmentAgent

**Goal:** Core agent that extracts recipes and proposes inventory items.

7. Create `core/agents/alignment_agent.py`:

   **Response model:**
   ```python
   class _IngredientProposal(BaseModel):
       name: str
       quantity: float
       unit_symbol: str
       equivalent: str | None = None          # per-ingredient mass equivalent, e.g. "≈ 120 g" for 1 taza de harina
       inventory_link_status: str             # matched_existing | new | needs_resolution
       matched_item_name: str | None = None   # canonical name if matched_existing

   class _InventoryProposal(BaseModel):
       name: str                              # canonical inventory item name
       category: str                          # "Perecedero" | "No perecedero"
       family: str | None = None              # FamilyInventory name from context
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

   **Schemas:**
   ```python
   INPUT_SCHEMA = {
       "user_message": "Message from operator or extracted file content.",
       "recipe_source": "'file_content' or 'conversation'",
       "page_index": "Which recipe in a multi-recipe file (0-based). 0 for single.",
   }
   OUTPUT_SCHEMA = {
       "reply": "Conversational response in Spanish.",
       "recipe_draft": "Dict with recipe fields for UI preview.",
       "inventory_proposals": "List of dicts for inventory panel.",
       "raw_response": "Full LLM response string.",
   }
   ```

   **Context injected into `_generate_prompt`:**
   | Key | Source |
   |-----|--------|
   | `restaurant_name` | `restaurant` entity |
   | `restaurant_type` | `restaurant` entity |
   | `restaurant_description` | `classification` entity |
   | `standardization_level` | `classification` entity |
   | `categories` | `category_recipe` entities — list of names |
   | `families` | `family_inventory` entities — list of names |
   | `existing_inventory_items` | `inventory_item` entities — list of canonical names |
   | `recipe_units` | `recipe_unit` entities — list of symbols |
   | `inventory_units` | `inventory_unit` entities — list of symbols |

   **Rules enforced in system prompt:**
   - No-hallucination: only extract data present in the file or operator's words
   - Missing steps: if no preparation steps found, ask the operator once. If declined,
     save with `steps=None`. Do not repeat the question.
   - Per-ingredient equivalents: for non-standard units (taza, cda, cdta, etc.), reason
     per-ingredient using culinary knowledge and propose a mass equivalent in g or ml.
     Example: "1 taza de harina ≈ 120 g", "1 taza de arroz ≈ 185 g". Ask operator to
     confirm, correct, or skip. Never apply a universal volume-to-mass conversion.
   - Standard recipe unit rule: only {g, kg, ml, L, pza} are standard — any other symbol
     requires an `equivalent` value proposed per-ingredient
   - Inventory unit fallback: if recipe unit has no direct inventory equivalent, use nearest
     standard (g for solids, ml for liquids, pza for countable items)
   - Category must be exactly `"Perecedero"` or `"No perecedero"` (fixed set)
   - Family must be chosen from the `families` context list; `null` if none fits
   - Entity creation rule: if a recipe uses a category, family, or recipe unit not in context,
     first propose mapping to an existing one. Only create a new entity if the operator
     explicitly requests it. Never create entities without confirmation.

   **Registered tool: `create_entity`**
   ```python
   def create_entity_tool(entity_type: str, name: str, symbol: str | None = None) -> str:
       """Create a new category_recipe, family_inventory, or recipe_unit.
       Only called after explicit operator confirmation.

       - entity_type: "category_recipe" | "family_inventory" | "recipe_unit"
       - name: display name for the entity
       - symbol: required only for recipe_unit (e.g. "manojo")

       Behavior:
       1. Loads existing entities for that type from DataLake
       2. Assigns ID = max existing ID + 1
       3. Saves new entity to DataLake
       4. Updates agent's in-memory context dict (categories/families/recipe_units list)
       5. For new non-standard recipe units (symbol not in {g, kg, ml, L, pza}),
          agent must ask operator for approximate equivalent in g or ml after creation
       6. Returns confirmation string for the LLM to continue
       """
   ```
   Registered via `self.register_tool()` in `AlignmentAgent.__post_init__()`.

   **`_process_response()`:**
   - Reads `_AlignmentResponse` fields
   - Stores `recipe_draft` and `inventory_proposals` via `self.store()`
   - Merges non-None fields across turns (draft accumulates)

---

### Subtask 10.3 — LangGraph graph

**Goal:** Build the conditional graph with file vs conversational branching.

8. `core/agents/graph_utils.py` — Add:
   ```python
   def build_conditional_graph(
       nodes: list[tuple[str, Callable]],
       conditional_edges: list[tuple[str, Callable, dict[str, str]]],
       state_schema: type,
   ) -> Any:
   ```
   Keep `build_sequential_graph` unchanged (backwards-compatible).

9. Define `AlignmentGraphState(BaseGraphState)` TypedDict with additional keys:
   `recipe_source`, `recipe_count`, `current_page_index`, `recipe_draft`,
   `inventory_proposals`, `user_message`.

10. Graph topology:
    ```
    initial_questions_node
        │
        ├── recipe_source == "file_content"  → file_extraction_node
        └── recipe_source == "conversation"  → conversational_node
                                                      │
                                                 review_node
    ```

---

### Subtask 10.4 — Gradio section

**Goal:** Replace stub with full two-column section UI.

11. `gradio_app/sections/alineamiento.py` — Replace stub with:

    **Right-column layout:**
    ```
    Progress: Receta X de ~N
    ──────────────────────────────────
    RECETA
      Nombre:      [name]
      Categoría:   [category]
      Descripción: [description]
      Pasos:       [expandable list]

    INGREDIENTES
      nombre | cantidad | unidad | equivalente | inventario
      ...

    ARTÍCULOS DE INVENTARIO A CREAR
      nombre | categoría | familia | estado
      ...
    ──────────────────────────────────
    [Guardar Receta + Artículos de Inventario]   ← disabled until confirmed

    RECETAS GUARDADAS
      Tacos de pollo ✓
      Caldo de res ✓
    ```

    **Key functions:**
    - `_load_alignment_context(data_lake, session_id) -> dict`
      Loads: restaurant entity, classification entity, all category_recipe entities,
      all family_inventory entities, all recipe_unit entities, all inventory_unit entities,
      all inventory_item entities (via `load_inventory_item_registry`).
      Returns dict with all keys needed by `AlignmentAgent._generate_prompt`.

    - `_make_chat_fn(provider, data_lake)` — load agent state / run agent / save agent state.
      Returns updated history + recipe_draft + inventory_proposals.

    - `_make_confirm_fn(data_lake)` — generator:
      1. yield "Guardando receta..." (loading state)
      2. Save `Recipe` via `data_lake.save_entity("recipe", id, recipe_dict)`
      3. For each new inventory proposal: save `InventoryItem` via
         `data_lake.save_entity("inventory_item", id, item_dict)`
      4. For matched inventory proposals: update `ingredient.inventory_item_id` in recipe dict
         before saving
      5. For each confirmed per-ingredient equivalent: save `RecipeUnitConversion` via
         `data_lake.save_entity("recipe_unit_conversion", composite_id, entry_dict)`
      6. yield final status + updated saved-recipes list

    - `_chat_and_format(...)` — single handler wired to `send_btn.click()`. Returns all
      outputs in one shot. No `State.change()` dependency (same pattern as configuracion).

    - File upload widget: `gr.File(visible=False)` by default. Revealed via `gr.update(visible=True)`
      after operator answers format question with a file-based option.

    - Progress indicator: `"Receta X de ~N"` — N is the recipe count the operator stated
      (optional/approximate). Shows `"Receta X de ?"` if operator skipped the count question.

    - When `create_entity` tool fires (agent creates new category/family/unit), the in-memory
      context updates immediately. The right-column dropdowns and context reflect the new entity
      for the current and all subsequent recipes in the session.

---

### Subtask 10.5 — Exports and tests

12. `core/agents/__init__.py` — Add `AlignmentAgent` following `WelcomeAgent`/`ClassificationAgent` pattern.
13. `core/__init__.py` — Re-export `AlignmentAgent`.
14. `tests/unit/test_alignment_agent.py` — see Test coverage section.

---

### Subtask 10.6 — Documentation and task closure

15. Create `docs/Architecture/sections/alineamiento.md` — full section doc:
    - Overview, layout, data produced
    - AlignmentAgent: schemas, context block, response model, rules
    - LangGraph graph: state, nodes, branching
    - `_load_alignment_context` return dict
    - Confirm flow (recipe + inventory items save sequence)
    - Gradio wiring (single-handler pattern, file upload reveal)
    - Error handling table
16. `docs/Architecture/architecture-agent-framework.md` — Add section on
    `build_conditional_graph` and `AlignmentGraphState`.
17. `docs/Architecture/architecture-data-model.md` — Add note on `recipe_unit_conversion`
    entity and `equivalence_source` field.
18. `docs/Architecture/architecture-persistence.md` — Add `recipe_unit_conversion` to
    entity type table; document composite key pattern and `source` field.
19. `CLAUDE.md` — Task 10 status → `done`; Task 11 noted as next.
20. `.taskmaster/tasks/tasks.json` — Task 10 status → `done`.

---

## Subtask execution order

```
10.1 (data model + persistence prerequisites)
  → 10.2 (AlignmentAgent)
  → 10.3 (LangGraph graph)
  → 10.4 (Gradio section)
  → 10.5 (exports + tests)
  → 10.6 (documentation + task closure)
```

---

## Test coverage

### Mocked tests (`tests/unit/test_alignment_agent.py`)

| Test name | Validates |
|-----------|-----------|
| `test_extracts_recipe_from_plain_text` | name, category, ingredients parsed from Spanish recipe text |
| `test_matches_existing_inventory_item` | ingredient matched to existing item; status = `"matched_existing"` |
| `test_proposes_new_inventory_item_with_category_and_family` | new item gets correct category/family from context |
| `test_nonstandard_unit_per_ingredient_equivalent` | taza de harina → `"≈ 120 g"` in equivalent column (per-ingredient) |
| `test_per_ingredient_equivalent_differs_by_ingredient` | same unit (taza) produces different equivalents for harina vs arroz |
| `test_no_hallucination_on_sparse_input` | agent does not add ingredients not present in source |
| `test_draft_accumulates_across_turns` | `_data_store` retains recipe_draft across multiple messages |
| `test_load_alignment_context_all_keys_present` | all context keys returned when Task 9 entities exist |
| `test_load_alignment_context_defaults_on_empty_datalake` | returns empty lists/defaults when no entities |
| `test_confirm_saves_recipe_to_datalake` | `Recipe` entity written with correct fields |
| `test_confirm_saves_new_inventory_items` | new `InventoryItem` entities written for each proposal |
| `test_confirm_links_ingredient_to_existing_item` | `inventory_item_id` set on matched ingredient before saving |
| `test_recipe_unit_conversion_roundtrip` | save → reload from SQLite returns same entry with source field |
| `test_ingredients_to_display_equivalent_and_status_columns` | extended columns present in output dict |
| `test_is_standard_recipe_unit_true_for_standard` | `is_standard_recipe_unit("g")` returns True |
| `test_is_standard_recipe_unit_false_for_nonstandard` | `is_standard_recipe_unit("taza")` returns False |
| `test_create_entity_tool_creates_category` | new category saved to DataLake with correct next ID |
| `test_create_entity_tool_creates_recipe_unit` | new recipe unit saved with name and symbol |
| `test_create_entity_tool_updates_agent_context` | agent context dict includes new entity after creation |
| `test_agent_does_not_create_without_confirmation` | agent proposes mapping first, does not call tool unprompted |
| `test_missing_steps_asks_once_then_saves_none` | when no steps found, agent asks once; on skip, recipe saved with `steps=None` |

### Live tests (skip unless `ANTHROPIC_API_KEY` set)

| Test name | Validates |
|-----------|-----------|
| `test_live_alignment_agent_spanish_recipe_text` | full LLM round-trip; extracts real recipe with ≥1 ingredient |
| `test_live_alignment_agent_multi_recipe_pagination` | two recipe extractions from same content via `page_index` |

---

## Out of scope

- `InventoryUnit` equivalences (`factor_to_base`, `base_unit_id`) — Task 11
- Full inventory structuring review UI — Task 11
- Exact density tables — agent uses culinary knowledge for per-ingredient estimates, not
  a lookup table. Operator confirms or corrects.
- PDF/image OCR quality and library selection details — implementation choice at 10.2
- Tasks 11–12 agent prompts and docs
- Readiness KPI recalculation
- `sections/bienvenida.md` or `sections/clasificacion.md` updates

---

## Risks and open questions

### [OPEN] — File parsing library selection
**Source:** Session discussion, pre-implementation
**Problem:** `pypdf`/`pdfplumber`, `openpyxl`, `pillow` not confirmed in `pyproject.toml`.
**Impact:** File-path branch of the graph cannot be implemented until libraries are added.
**Suggested action:** Run `uv add pypdf openpyxl pillow` at the start of 10.2 and verify.

### [OPEN] — InventoryUnitEquivalence hashability
**Source:** Codebase review of `data_model.py`
**Problem:** Removing `frozen=True` breaks hashability. No current callers use instances as
dict keys or in sets (verified in session codebase review), but must grep before changing.
**Impact:** Silent runtime error if any caller depends on hashability.
**Suggested action:** Run `grep -r "InventoryUnitEquivalence" .` before 10.1 step 2 to confirm.

### [OPEN] — build_conditional_graph placement
**Source:** Session discussion
**Problem:** If branching logic in the alignment graph is simple (one conditional edge),
adding a generic helper to `graph_utils.py` may be premature abstraction.
**Impact:** Unnecessary complexity in `graph_utils.py`.
**Suggested action:** Evaluate at 10.3 implementation time; define graph inline in
`alineamiento.py` if the conditional logic is section-specific.

### [OPEN] — Inventory item unit_id fallback rule
**Source:** Session discussion
**Problem:** If recipe unit has no direct inventory equivalent (e.g., `cdas` not in
inventory units), the exact fallback rule for `unit_id` inference is unspecified.
**Impact:** Agent may assign inconsistent units across recipes; Task 11 review surface
may show many corrections needed.
**Suggested action:** Define explicit fallback in AlignmentAgent system prompt at 10.2:
solids → `g` or `kg`; liquids → `ml` or `L`; countable → `pza`. Document in 10.6.

### [OPEN] — Per-ingredient equivalent confirmation timing
**Source:** Validation of task 10
**Problem:** The plan says the agent proposes per-ingredient equivalents (e.g. "1 taza de
harina ≈ 120 g, ¿te parece bien?") but does not specify whether this happens
ingredient-by-ingredient during extraction or as a batch after the full recipe draft is shown.
**Impact:** Implementer at 10.2 must decide the UX flow; inconsistent choice could make the
confirmation feel disjointed.
**Suggested action:** Decide at 10.2 planning time. Recommend batch: show all equivalents in
the preview table, operator confirms or corrects inline before saving.

### [OPEN] — CLAUDE.md Task 17 status still says "pending"
**Source:** Validation of task 10
**Problem:** CLAUDE.md task status table shows Task 17 as `pending`, but tasks.json correctly
shows `done`. Subtask 17.8 was supposed to update CLAUDE.md.
**Impact:** Misleading for future implementers reading CLAUDE.md. Not blocking for Task 10
since tasks.json is authoritative.
**Suggested action:** Update CLAUDE.md Task 17 row to `done` before starting 10.1.

---

## Deliverable checklist

### `core/operations/normalization.py`
- [ ] `RecipeUnitConversionEntry.source` field added

### `core/domain/data_model.py`
- [ ] `STANDARD_RECIPE_UNIT_SYMBOLS` frozenset added
- [ ] `is_standard_recipe_unit()` helper added
- [ ] `InventoryUnitEquivalence` unfrozen
- [ ] `InventoryUnitEquivalence.equivalence_source` field added

### `core/storage/schema.py`
- [ ] `recipe_unit_conversion` table added

### `core/storage/persistence.py`
- [ ] `"recipe_unit_conversion"` in `_SQLITE_ENTITY_TYPES`
- [ ] save/load/delete/list handlers for `recipe_unit_conversion`

### `core/domain/serialization.py`
- [ ] `recipe_unit_conversion_to_dict` / `recipe_unit_conversion_from_dict` added (standalone pair pattern)

### `core/domain/data_model_utils.py`
- [ ] `load_inventory_item_registry()` added
- [ ] `ingredients_to_display()` extended with `equivalent` and `inventory_link_status`

### `core/agents/alignment_agent.py`
- [ ] `_IngredientProposal`, `_InventoryProposal`, `_AlignmentResponse` models defined
- [ ] `AlignmentAgent` with `INPUT_SCHEMA`, `OUTPUT_SCHEMA`, `RESPONSE_MODEL`
- [ ] `_generate_prompt()` injects all 9 context keys
- [ ] No-hallucination rule in system prompt
- [ ] Per-ingredient equivalent reasoning rule in system prompt
- [ ] Standard recipe unit rule in system prompt
- [ ] Entity creation rule in system prompt (no create without confirmation)
- [ ] `create_entity` tool registered via `register_tool()`
- [ ] `_process_response()` merges non-None fields across turns

### `core/agents/graph_utils.py`
- [ ] `build_conditional_graph()` added
- [ ] `build_sequential_graph()` unchanged

### `core/agents/__init__.py` + `core/__init__.py`
- [ ] `AlignmentAgent` exported

### `gradio_app/sections/alineamiento.py`
- [ ] Stub replaced with full `render()`
- [ ] `_load_alignment_context()` loads all 5 entity sources
- [ ] `_make_chat_fn()` follows load/run/save pattern
- [ ] `_make_confirm_fn()` saves recipe + inventory items + recipe unit conversions; links matched items
- [ ] Single-handler pattern (`_chat_and_format`) — no `State.change()`
- [ ] File upload widget revealed conditionally after format answer
- [ ] Saved-recipes list accumulates below confirm button
- [ ] Progress indicator shown

### `tests/unit/test_alignment_agent.py`
- [ ] 21 mocked tests passing
- [ ] 2 live tests skipped without API key, passing with key

### `docs/Architecture/sections/alineamiento.md`
- [ ] Created with full section doc

### `docs/Architecture/architecture-agent-framework.md`
- [ ] `build_conditional_graph` and `AlignmentGraphState` documented

### `docs/Architecture/architecture-data-model.md`
- [ ] `recipe_unit_conversion` entity and `equivalence_source` documented

### `docs/Architecture/architecture-persistence.md`
- [ ] `recipe_unit_conversion` table documented

### `CLAUDE.md`
- [ ] Task 10 status → `done`

### `.taskmaster/tasks/tasks.json`
- [ ] Task 10 status → `done`
