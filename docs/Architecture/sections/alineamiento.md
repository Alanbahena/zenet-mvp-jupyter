# Alineamiento Section Architecture

## 1. Overview

The Alineamiento section is the **4th tab** in the pipeline. It guides the operator through
capturing all their recipes and automatically proposes inventory item shells from the
ingredients in those recipes.

Layout: **two-column** — chat on the left, recipe preview on the right.

Data produced by this section:

| Entity | Entity type | Used by |
|--------|-------------|---------|
| Recipe (with ingredients) | `recipe` | Task 11 — Estructura |
| InventoryItem shells (name, category, family, best-effort unit) | `inventory_item` | Task 11 |
| Per-ingredient unit equivalences | `recipe_unit_conversion` | Task 11, normalization |

**Implementation files:**

| File | Role |
|------|------|
| `gradio_app/sections/alineamiento.py` | `render()`, `_chat_and_format`, `_handle_file_upload`, `_confirm_and_save`, `_load_alignment_context`, `_make_confirm_fn`, `_extract_file_text` |
| `core/agents/alignment_agent.py` | `AlignmentAgent` — recipe extraction, inventory proposals, entity creation tool |

---

## 2. AlignmentAgent

### Schemas

**INPUT_SCHEMA**

| Key | Type | Description |
|-----|------|-------------|
| `user_message` | `str` | Message from operator or extracted file content |
| `recipe_source` | `str` | `"conversation"` or `"file_content"` |
| `page_index` | `int` | 0-based index into multi-recipe file or session |

**OUTPUT_SCHEMA**

| Key | Type | Description |
|-----|------|-------------|
| `reply` | `str` | Conversational response in Spanish |
| `recipe_draft` | `dict` | Accumulated recipe fields for UI preview |
| `inventory_proposals` | `list` | Proposed inventory items |
| `raw_response` | `str` | Full LLM response string |
| `show_file_upload` | `bool` | True when operator indicates they have a file |

**RESPONSE_MODEL (`_AlignmentResponse`)**

| Field | Type | Description |
|-------|------|-------------|
| `reply` | `str` | Conversational reply |
| `recipe_name` | `str \| None` | Extracted recipe name |
| `recipe_category` | `str \| None` | Recipe category (from context list) |
| `recipe_description` | `str \| None` | Brief recipe description |
| `recipe_steps` | `list[str] \| None` | Preparation steps |
| `ingredients` | `list[_IngredientProposal] \| None` | Extracted ingredients |
| `inventory_proposals` | `list[_InventoryProposal] \| None` | Items to create in inventory |
| `show_file_upload` | `bool` | Reveal file upload widget |

**`_IngredientProposal` fields:** `name`, `quantity`, `unit_symbol`, `equivalent` (per-ingredient mass estimate, e.g. `"≈ 120 g"`), `inventory_link_status` (`"new"` / `"matched_existing"` / `"needs_resolution"`), `matched_item_name`.

**`_InventoryProposal` fields:** `name`, `category` (`"Perecedero"` / `"No perecedero"`), `family` (from context, or null), `status` (`"new"` / `"matched_existing"`).

### Context block

`_generate_prompt` injects 9 keys from the context dict into the system prompt:

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

The draft accumulated so far is also injected as a JSON block so the agent never repeats
questions about fields already captured.

### System prompt rules

- **No-hallucination:** extract only data present in the file or operator's words; never invent ingredients
- **Missing steps:** if no preparation steps are found, ask the operator once; if declined, save `recipe_steps=None`; do not repeat the question
- **Per-ingredient equivalents:** for non-standard units (taza, cda, cdta, oz, manojo, pizca, etc.), reason per-ingredient using culinary knowledge and propose an equivalent in g or ml; example: 1 taza de harina ≈ 120 g, 1 taza de arroz ≈ 185 g; never apply a universal volume-to-mass conversion
- **Standard unit rule:** only `{g, kg, ml, L, pza}` are standard — any other symbol requires an `equivalent` value in the ingredient proposal
- **Inventory unit fallback:** if a recipe unit has no direct inventory equivalent, use the nearest standard (g/kg for solids, ml/L for liquids, pza for countable items)
- **Category constraint:** `category` must be exactly `"Perecedero"` or `"No perecedero"`
- **Entity creation gate:** if the operator references a category, family, or recipe unit not in context, first propose mapping to an existing one; only call `create_entity` if the operator explicitly confirms; never create entities without confirmation

---

## 3. `create_entity` tool

Registered via `self.register_tool()` in `AlignmentAgent.__post_init__()`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity_type` | `str` | yes | `"category_recipe"` / `"family_inventory"` / `"recipe_unit"` |
| `name` | `str` | yes | Display name for the new entity |
| `symbol` | `str` | recipe_unit only | Symbol string (e.g. `"manojo"`) |

**Behavior:**
1. Load existing entity ids via `data_lake.list_entity_ids(entity_type)`
2. Assign `id = max(existing_ids, default=0) + 1`
3. Save entity to `data_lake`
4. Update agent's in-memory context dict (`categories` / `families` / `recipe_units` list)
5. Return a confirmation string for the LLM to continue
6. For new non-standard recipe units: the confirmation string instructs the LLM to ask the operator for an approximate equivalent in g or ml

---

## 4. `_load_alignment_context`

```python
def _load_alignment_context(data_lake, session_id) -> dict
```

`entity_id` for restaurant and classification lookup: `abs(hash(session_id)) % (2**31 - 1)`

Returns a dict with 11 keys:

| Key | Type | Default when missing |
|-----|------|----------------------|
| `restaurant_name` | `str` | `""` |
| `restaurant_type` | `str` | `""` |
| `restaurant_description` | `str` | `""` |
| `standardization_level` | `int` | `1` |
| `categories` | `list[str]` | `[]` |
| `families` | `list[str]` | `[]` |
| `recipe_units` | `list[str]` | `[]` |
| `inventory_units` | `list[str]` | `[]` |
| `existing_inventory_items` | `list[str]` | `[]` |
| `data_lake` | `DataLake` | (passed through) |
| `session_id` | `str` | (passed through) |

---

## 5. File upload flow

```python
gr.File(visible=False, file_types=[".pdf", ".xlsx", ".xls"])
```

Revealed via `gr.update(visible=True)` when the agent returns `show_file_upload=True`.

```python
def _extract_file_text(file_path: str) -> str
```

| File type | Library | Behavior |
|-----------|---------|---------|
| `.pdf` | `pypdf` (`PdfReader`) | Extracts text from all pages, joined with newlines |
| `.xlsx`, `.xls` | `openpyxl` (`load_workbook`) | Iterates all sheets and rows; joins cell values with tabs/newlines |
| Other (images, etc.) | — | Returns `""` — image OCR deferred to post-MVP |

When a file is uploaded, `_handle_file_upload` calls `_extract_file_text`, then runs the
agent with `recipe_source="file_content"` and the extracted text as `user_message`.

---

## 6. Draft accumulation

`_process_response()` merges fields across turns so the draft accumulates:

- **Scalar fields** (`recipe_name`, `recipe_category`, `recipe_description`, `recipe_steps`): merged if non-None — existing value preserved if new response returns None
- **`ingredients`**: overwrite if present in the response (last extraction wins)
- **`inventory_proposals`**: overwrite if present

Stored internally via `self.store("recipe_draft", merged_draft)` and retrieved via
`self.retrieve("recipe_draft", {})`. The draft is also injected into the system prompt
at the start of each turn so the agent never loses context.

---

## 7. Confirm flow (`_make_confirm_fn`)

```python
def _make_confirm_fn(data_lake) -> Callable
# Returns: confirm_fn(recipe_draft, inventory_proposals, session_id) -> Generator[(str, bool)]
```

Step sequence inside `confirm_fn`:

| Step | Action |
|------|--------|
| 1 | Yield `("Guardando receta...", False)` — loading state |
| 2 | Resolve `category_id` by matching `recipe_category` name against `category_recipe` entities |
| 3 | Build lookup maps: `ru_symbol_to_id`, `iu_symbol_to_id`, `existing_item_name_to_id`, `family_name_to_id` |
| 4 | Save new `InventoryItem` for each proposal with `status="new"`; skip if already exists |
| 5 | Build `proposal_name_to_id` map (new items + matched_existing items) |
| 6 | Build `Ingredient` list; set `inventory_item_id` from map |
| 7 | Parse `equivalent` strings (e.g. `"≈ 120 g"`) via regex → build `RecipeUnitConversion` saves |
| 8 | Save `Recipe` entity via `data_lake.save_entity("recipe", recipe_id, recipe_to_dict(recipe))` |
| 9 | Save `RecipeUnitConversion` entities with composite key `"{ru_id}_{family_id}_{item_id}"` |
| 10 | Yield `("**<name>** guardada correctamente.", True)` |

On exception: yield `(f"Error al guardar: {exc}", False)`.

---

## 8. Gradio wiring

| Event | Handler | Inputs | Outputs |
|-------|---------|--------|---------|
| `send_btn.click` | `_chat_and_format` | `textbox, chatbot, session_id, recipe_source_state, current_page_index_state` (5) | `chatbot, textbox, recipe_draft_state, inventory_proposals_state, file_upload, recipe_ready_state, confirm_btn, recipe_name_md, ingredients_tbl, proposals_tbl` (10) |
| `file_upload.upload` | `_handle_file_upload` | `file_upload, chatbot, session_id, current_page_index_state` (4) | same 10 outputs as send_btn |
| `confirm_btn.click` | `_confirm_and_save` | `recipe_draft_state, inventory_proposals_state, session_id, saved_recipes_state, current_page_index_state` (5) | `recipe_draft_state, confirm_btn, status_md, saved_md, saved_recipes_state, current_page_index_state, inventory_proposals_state` (7) |

**Key patterns:**
- No `State.change()` dependency — same single-handler pattern as `configuracion.py`
- `show_file_upload` field from agent output drives `file_upload` visibility update on each turn
- `_confirm_and_save` is a generator (`yield`) — `show_progress="hidden"` passed to Gradio
- Agent state is loaded, run, and saved within each handler call (load/run/save pattern)
