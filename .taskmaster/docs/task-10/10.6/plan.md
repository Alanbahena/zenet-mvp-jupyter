# Subtask 10.6 — Documentation and task closure

## Goal

Write all architecture documentation for Task 10, update Mermaid diagrams that became
stale during implementation, and mark Task 10 done in all trackers so Task 11 can start
with a clean, accurate reference.

**Builds on:** 10.5 delivered `AlignmentAgent` exports and 23 passing tests.
**Required by:** Task 11 (Estructura) — reads existing architecture docs as implementation
reference; the accuracy of what 10.6 writes directly informs the Task 11 plan.

---

## Dependencies

- Subtasks 10.1–10.5 all `done` (confirmed in `tasks.json`)
- No new packages or env vars required — documentation + status updates only

---

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| `alineamiento.md` mirrors `configuracion.md` structure | Consistent section doc format across all pipeline sections |
| Section 10 of `architecture-agent-framework.md` updated (not replaced) | Closes the LangGraph evaluation loop: evaluated at Task 10, not adopted; documents real future use cases |
| `build_conditional_graph` / `AlignmentGraphState` NOT documented | 10.3 was cancelled — these were never implemented; documenting them would be false |
| Mermaid source updated; companion PNGs noted as stale | Mermaid is the authoritative spec; PNGs are pre-rendered exports that require a manual export step |
| Task 10 data-model additions documented in a dedicated section 7 | Keeps existing sections intact; appends cleanly before "Related docs" |
| `recipe_unit_conversion` persistence documented as an addendum to the entity serialization section | Consistent with how `inventory_unit_equivalence` is documented in the same file |

---

## Files to modify / create

| File | Action | Summary |
|------|--------|---------|
| `docs/Architecture/sections/alineamiento.md` | Create | Full Alineamiento section architecture doc |
| `docs/Architecture/architecture-agent-framework.md` | Modify | Update section 1 flowchart (add `AlignmentAgent ✓`); update section 10 (LangGraph outcome) |
| `docs/Architecture/architecture-data-model.md` | Modify | Update class diagram (`InventoryUnitEquivalence` unfrozen, `equivalence_source` added); add section 7 (Task 10 additions) |
| `docs/Architecture/architecture-persistence.md` | Modify | Add `recipe_unit_conversion` entity doc + serialization pair |
| `CLAUDE.md` | Modify | Task 10 → `done`; Task 11 noted as next |
| `.taskmaster/tasks/tasks.json` | Modify | Task 10 status → `done`; subtask 10.6 → `done` |

---

## Implementation steps

### Step 1 — Create `docs/Architecture/sections/alineamiento.md`

Structure (mirrors `configuracion.md`):

```
# Alineamiento Section Architecture

## 1. Overview
  - Pipeline position (4th tab)
  - Layout: two-column (chat left, recipe preview right)
  - Data produced table:
    | Entity | Entity type | Used by |
    | Recipe | recipe | Task 11 — Estructura |
    | InventoryItem shells | inventory_item | Task 11 |
    | RecipeUnitConversion | recipe_unit_conversion | Task 11, normalization |
  - Implementation files table

## 2. AlignmentAgent
  - INPUT_SCHEMA (user_message, recipe_source, page_index)
  - OUTPUT_SCHEMA (reply, recipe_draft, inventory_proposals, raw_response, show_file_upload)
  - RESPONSE_MODEL: _AlignmentResponse fields table
  - Context block — 9 keys and their sources:
    | Key | Source |
    | restaurant_name | restaurant entity |
    | restaurant_type | restaurant entity |
    | restaurant_description | classification entity |
    | standardization_level | classification entity |
    | categories | category_recipe entities |
    | families | family_inventory entities |
    | existing_inventory_items | inventory_item entities |
    | recipe_units | recipe_unit entities |
    | inventory_units | inventory_unit entities |
  - System prompt rules (bullet list):
    - No-hallucination: extract only from file or operator words
    - Missing steps: ask once; if declined, save steps=None
    - Per-ingredient equivalents: reason per-ingredient using culinary knowledge; propose ≈ g or ml
    - Standard unit rule: {g, kg, ml, L, pza} need no equivalent; all others do
    - Inventory unit fallback: solids → g/kg; liquids → ml/L; countable → pza
    - Entity creation gate: propose mapping first; only create with explicit operator confirmation

## 3. create_entity tool
  - Registered via register_tool() in __post_init__
  - entity_type: category_recipe | family_inventory | recipe_unit
  - Behavior: list existing → max id + 1 → save → update agent context → return confirmation string
  - For new non-standard recipe units: prompts operator for g/ml equivalent after creation

## 4. _load_alignment_context
  - Signature: _load_alignment_context(data_lake, session_id) -> dict
  - entity_id computed as: abs(hash(session_id)) % (2**31 - 1)
  - Returns all 11 keys (restaurant_name, restaurant_type, restaurant_description,
    standardization_level, categories, families, recipe_units, inventory_units,
    existing_inventory_items, data_lake, session_id)
  - Defaults: empty lists, standardization_level=1, empty strings for restaurant fields

## 5. File upload flow
  - gr.File(visible=False, file_types=[".pdf", ".xlsx", ".xls"])
  - Revealed via gr.update(visible=True) when agent returns show_file_upload=True
  - _extract_file_text(file_path) -> str:
    - PDF: pypdf PdfReader — extracts all pages
    - Excel: openpyxl load_workbook — iterates all sheets, all rows
    - Other (including images): returns "" — image OCR deferred to post-MVP

## 6. Draft accumulation
  - _process_response() merges non-None scalar fields into existing recipe_draft across turns
  - ingredients: overwrite if present (last extraction wins)
  - inventory_proposals: overwrite if present
  - Stored via self.store("recipe_draft", ...) / self.retrieve("recipe_draft", {})

## 7. Confirm flow (_make_confirm_fn)
  - Signature: confirm_fn(recipe_draft, inventory_proposals, session_id) -> Generator[(str, bool)]
  - Step sequence:
    1. Yield ("Guardando receta...", False)   ← loading state
    2. Resolve category_id from category_recipe entities
    3. Save new InventoryItem for each proposal with status="new"
    4. Build proposal_name_to_id map (new + matched_existing)
    5. Build Ingredient list; set inventory_item_id from map
    6. Parse equivalent strings ("≈ 120 g") → build RecipeUnitConversion saves
    7. Save Recipe entity
    8. Save RecipeUnitConversion entities (composite key)
    9. Yield ("**<name>** guardada correctamente.", True)
  - Error: yield (f"Error al guardar: {exc}", False)

## 8. Gradio wiring
  - send_btn.click → _make_chat_fn (load/run/save pattern; returns 6 outputs)
  - file_upload.upload → _handle_file_upload (extracts text, runs agent turn)
  - confirm_btn.click → _confirm_and_save generator (5 inputs, 7 outputs)
  - show_file_upload field drives file_upload visibility update on each turn
  - No State.change() dependency — same single-handler pattern as configuracion.py
```

---

### Step 2 — Modify `docs/Architecture/architecture-agent-framework.md`

**2a — Section 1 overview flowchart:** Update the `T712` node to include `AlignmentAgent ✓`:

Current:
```
T712["Tasks 7–12<br/>Notebook Agents<br/>WelcomeAgent ✓<br/>ClassificationAgent ✓<br/>ConfigurationAgent ✓<br/>ConsistencyCheckAgent ✓<br/>..."]
```

Replace with:
```
T712["Tasks 7–12<br/>Notebook Agents<br/>WelcomeAgent ✓<br/>ClassificationAgent ✓<br/>ConfigurationAgent ✓<br/>ConsistencyCheckAgent ✓<br/>AlignmentAgent ✓<br/>..."]
```

**2b — Section 10 ("Deferred — external framework integration"):** Replace the forward-reference text with the actual outcome. New content:

```markdown
## 10. Note on external framework integration (LangGraph)

**Evaluation outcome for Task 10 (Alineamiento):**

LangGraph was evaluated as part of Task 10 planning. A single conversational agent
(`AlignmentAgent`) handles recipe extraction, inventory proposals, and entity creation
in one LLM call. No multi-agent fan-out and no conditional branching between independent
agents were needed — the file-vs-conversation branch is a simple `if/else` in the
Gradio handler. LangGraph was not adopted for Task 10.

**When LangGraph would be appropriate in this project:**

| Use case | Why LangGraph fits |
|----------|--------------------|
| Multi-agent fan-out (e.g. parallel UnitResolver + PriceEstimator + NutritionAgent) | Independent subgraphs run in parallel; shared state merged after |
| Retry loops with quality gate (e.g. AlignmentAgent → ConsistencyCheckAgent → loop back) | Cyclic edges not possible with sequential helpers |
| Full pipeline API (all sections in sequence, no UI, API-only) | `StateGraph` over all section agents; no Gradio needed |

`BaseAgent`'s clean, composable interface (simple dataclass, `run()` returns a dict)
is easy to wrap with any framework without breaking changes.
```

---

### Step 3 — Modify `docs/Architecture/architecture-data-model.md`

**3a — Class diagram (section 2):** Update `InventoryUnitEquivalence` — remove `<<frozen dataclass>>` stereotype, add `equivalence_source` field, add `source` field note:

Current block:
```
class InventoryUnitEquivalence {
    <<frozen dataclass>>
    +int unit_id
    +int inventory_item_id
    +int base_unit_id
    +float factor_to_base
}
```

Replace with:
```
class InventoryUnitEquivalence {
    +int unit_id
    +int inventory_item_id
    +int base_unit_id
    +float factor_to_base
    +str equivalence_source
}
```

Note: The companion PNG `images/data-model-02-class-diagram.png` is now stale.
Add a comment line below the image reference:
```
<!-- NOTE: PNG is stale — class diagram Mermaid source updated for Task 10 (InventoryUnitEquivalence unfrozen, equivalence_source added). Regenerate from Mermaid source. -->
```

**3b — Add section 7 (Task 10 additions)** before "Related docs":

```markdown
## 7. Task 10 additions (Alineamiento)

### Standard recipe unit constant

```python
STANDARD_RECIPE_UNIT_SYMBOLS: frozenset[str] = frozenset({"g", "kg", "ml", "L", "pza"})

def is_standard_recipe_unit(symbol: str) -> bool:
    """Return True if the symbol is a standard recipe unit (no equivalent needed)."""
    return symbol in STANDARD_RECIPE_UNIT_SYMBOLS
```

Standard units need no per-ingredient mass equivalent. Any other symbol (taza, cda, cdta,
oz, manojo, pizca, etc.) is non-standard and requires an equivalent proposed per-ingredient
by `AlignmentAgent`.

### InventoryUnitEquivalence — unfrozen + equivalence_source

`InventoryUnitEquivalence` was `@dataclass(frozen=True)` prior to Task 10. Task 10
removed `frozen=True` to allow future updates by Task 11 and added:

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `equivalence_source` | `str` | `"operator"` | `"operator"` / `"agent_confirmed"` / `"agent_estimated"` |

### RecipeUnitConversionEntry.source

`RecipeUnitConversionEntry` (in `core/operations/normalization.py`) received a new field:

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `source` | `str` | `"agent_estimated"` | `"operator"` / `"agent_confirmed"` / `"agent_estimated"` |

Source values:
- `"operator"` — operator explicitly provided or corrected the equivalent
- `"agent_confirmed"` — operator accepted the agent's culinary estimate
- `"agent_estimated"` — operator skipped; agent estimate stored as-is
```

---

### Step 4 — Modify `docs/Architecture/architecture-persistence.md`

Append to the serialization function list (after `inventory_unit_equivalence_to_dict` /
`inventory_unit_equivalence_from_dict`):

```python
recipe_unit_conversion_to_dict, recipe_unit_conversion_from_dict,
```

Add a new subsection after the `inventory_unit_equivalence` serialization block (or at
the end before "Summary"):

```markdown
### recipe_unit_conversion

Added in Task 10. Stores per-ingredient recipe unit → mass/volume equivalents confirmed
during the Alineamiento section.

**SQLite-only** — in `_SQLITE_ENTITY_TYPES`. JSON backend does not support it.

**Composite key:** entity id is a string `"{recipe_unit_id}_{family_id}_{inventory_item_id}"`.
`family_id` and `inventory_item_id` are nullable (stored as `None` in Python; `NULL` in SQLite).

**Schema (from `core/storage/schema.py`):**

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

**Serialization:**

```python
from core.domain.serialization import (
    recipe_unit_conversion_to_dict,   # (entry, key) -> dict
    recipe_unit_conversion_from_dict, # dict -> (key, entry)
)
```

`recipe_unit_conversion_to_dict(entry, key)` returns:
```python
{
    "recipe_unit_id":    key.recipe_unit_id,
    "family_id":         key.family_id,       # None if item-specific only
    "inventory_item_id": key.inventory_item_id,
    "quantity":          entry.quantity,
    "base_unit_id":      entry.base_unit_id,
    "source":            entry.source,        # "operator" | "agent_confirmed" | "agent_estimated"
}
```
```

---

### Step 5 — Modify `CLAUDE.md`

- Change Task 10 row from `pending` to `done`
- Change the "**Task 10** (Alineamiento) is next." line to "**Task 11** (Estructura) is next."

---

### Step 6 — Modify `.taskmaster/tasks/tasks.json`

Use Python script (avoid Unicode Edit tool pitfalls):
- Task 10 `status` → `"done"`
- Subtask 10.6 `status` → `"done"`

---

## Out of scope

- Any changes to agent code, Gradio section code, or test files
- `build_conditional_graph` / `AlignmentGraphState` documentation (10.3 cancelled, never implemented)
- Architecture docs for Task 11 (Estructura) — separate task
- `sections/bienvenida.md` or `sections/clasificacion.md` updates
- Regenerating companion PNG images — Mermaid source is the authoritative spec; PNG regeneration requires a manual export step

---

## Risks and open questions

### [RISK] — Parent plan step 16 references `build_conditional_graph` and `AlignmentGraphState`
These were never implemented (10.3 cancelled). This step is modified: instead document
the LangGraph evaluation outcome and `AlignmentAgent` addition. Already accounted for above.

### [RISK] — Static PNG images become stale
`images/data-model-02-class-diagram.png` references the old `InventoryUnitEquivalence`
class. `architecture-agent-framework.md` may have a companion image (not confirmed —
no image reference seen in the first 40 lines). Add a HTML comment stale note next to
the PNG references in the affected files; do not delete the image files.

### [OPEN] — architecture-agent-framework.md companion images
The framework doc has a Mermaid flowchart but no PNG reference was observed in the
first 40 lines read. Verify the full file has no `![...]` image reference for section 1
before skipping the stale-image note.

---

## Deliverable checklist

### `docs/Architecture/sections/alineamiento.md`
- [ ] Created with 8-section structure (Overview, AlignmentAgent, create_entity tool, _load_alignment_context, File upload flow, Draft accumulation, Confirm flow, Gradio wiring)
- [ ] Data produced table includes Recipe, InventoryItem, RecipeUnitConversion
- [ ] All 9 context keys documented with their sources
- [ ] Confirm flow step sequence matches actual `_make_confirm_fn` implementation

### `docs/Architecture/architecture-agent-framework.md`
- [ ] Section 1 flowchart T712 node updated: `AlignmentAgent ✓` added
- [ ] Section 10 text replaced with LangGraph evaluation outcome + future use cases table

### `docs/Architecture/architecture-data-model.md`
- [ ] Class diagram: `InventoryUnitEquivalence` `<<frozen dataclass>>` stereotype removed
- [ ] Class diagram: `equivalence_source: str` field added to `InventoryUnitEquivalence`
- [ ] PNG stale comment added below `images/data-model-02-class-diagram.png` reference
- [ ] Section 7 added: `STANDARD_RECIPE_UNIT_SYMBOLS`, `is_standard_recipe_unit()`, unfrozen equivalence, `RecipeUnitConversionEntry.source`

### `docs/Architecture/architecture-persistence.md`
- [ ] `recipe_unit_conversion_to_dict` / `recipe_unit_conversion_from_dict` added to serialization list
- [ ] `recipe_unit_conversion` subsection added: SQLite-only note, composite key, schema, serialization example

### `CLAUDE.md`
- [ ] Task 10 status → `done`
- [ ] "Task 11 (Estructura) is next." line updated

### `.taskmaster/tasks/tasks.json`
- [ ] Task 10 status → `done`
- [ ] Subtask 10.6 status → `done`
