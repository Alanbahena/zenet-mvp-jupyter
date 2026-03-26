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
| `recipe_count` | `int \| None` | Total recipe count stated by operator |
| `ready_to_save` | `bool` | True when agent has resolved all fields and equivalents |
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
| `recipe_count` | `int \| None` | Total recipe count stated by operator; persisted once set |
| `ready_to_save` | `bool` | True when all fields and equivalents are resolved |
| `show_file_upload` | `bool` | Reveal file upload widget |

**`_IngredientProposal` fields:** `name`, `quantity`, `unit_symbol`, `equivalent` (per-ingredient mass estimate, e.g. `"≈ 120 g"`), `inventory_link_status` (`"new"` / `"matched_existing"` / `"needs_resolution"`), `matched_item_name`.

**`_InventoryProposal` fields:** `name`, `category` (`"Perecedero"` / `"No perecedero"`), `family` (from context, or null), `status` (`"new"` / `"matched_existing"`).

### Context block

`_generate_prompt` injects 10 keys from the context dict into the system prompt:

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
| `confirmed_equivalences` | `recipe_unit_conversion` entities — list of human-readable strings e.g. `"1 cucharada de mix ajo/shallot ≈ 8 g"` |

The draft accumulated so far is also injected as a JSON block so the agent never repeats
questions about fields already captured.

### System prompt rules

- **Opening flow (mandatory):** On operator confirmation of readiness, ask "¿Cuántas recetas tienes aproximadamente?" first; after reply ask the format question (level 1: explicit file-or-chat choice; level 2: proactive mention of both options); only start recipe capture after both answers. Exception: if operator starts dictating a recipe directly, adapt and capture it.
- **File content extraction:** When message begins with `[Contenido de archivo`, extract all available fields (`recipe_name`, `ingredients`, etc.) in the same turn before asking any follow-up questions. The file content is not re-sent in subsequent turns.
- **No-hallucination:** extract only data present in the file or operator's words; never invent ingredients or quantities
- **Missing steps:** if no preparation steps are found, ask the operator once; if declined, save `recipe_steps=None`; do not repeat the question
- **Per-ingredient equivalents:** for non-standard units, ask the operator per ingredient naming the ingredient explicitly (e.g. "¿Sabes cuántos gramos equivale 1 cucharada de mix ajo/shallot?"); only propose a culinary estimate if the operator doesn't know; never ask generically about the unit alone
- **Confirmed equivalences:** equivalents already in context under `confirmed_equivalences` are not asked again
- **Standard unit rule:** only `{g, kg, ml, L, pza}` are standard — any other symbol requires an `equivalent` value
- **Inventory unit fallback:** solids → g/kg, liquids → ml/L, countable → pza
- **Category constraint:** `category` must be exactly `"Perecedero"` or `"No perecedero"`
- **Entity creation gate:** propose mapping to existing first; only call `create_entity` after explicit operator confirmation
- **`ready_to_save`:** set to `true` only when recipe name is confirmed, all ingredients captured, all non-standard unit equivalents resolved, and no pending corrections
- **Draft is authoritative:** the injected draft block is the source of truth; do not ask the operator to re-confirm information already captured or re-upload files

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

`entity_id` for restaurant and classification lookup: `stable_entity_id(session_id)` (from `gradio_app.session`)

Returns a dict with 12 keys:

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
| `confirmed_equivalences` | `list[str]` | `[]` |
| `data_lake` | `DataLake` | (passed through) |
| `session_id` | `str` | (passed through) |

---

## 5. File upload flow

```python
gr.File(visible=False, file_types=[".pdf", ".xlsx", ".xls", ".jpg", ".jpeg", ".png", ".webp"])
```

Revealed via `gr.update(visible=True)` when the agent returns `show_file_upload=True`.

```python
def _extract_text_via_vision(image_bytes: bytes, media_type: str, client) -> str
def _extract_file_text(file_path: str, client=None) -> str
```

| File type | Library | Behavior |
|-----------|---------|---------|
| `.jpg`, `.jpeg` | Claude vision API | Base64-encoded, sent to `claude-sonnet-4-6` via `client.messages.create`; returns extracted text |
| `.png`, `.webp` | Claude vision API | Same as above with appropriate `media_type` |
| `.pdf` (text-based) | `pypdf` (`PdfReader`) | Extracts text from all pages; returns joined string |
| `.pdf` (image-based) | `pymupdf` (`fitz`) + Claude vision | Renders each page at 2x resolution via `page.get_pixmap(matrix=fitz.Matrix(2,2))`; sends each page image to Claude vision; joins results |
| `.xlsx`, `.xls` | `openpyxl` (`load_workbook`) | Iterates all sheets and rows; joins non-empty cell values |

`_extract_file_text` requires `client` (an `anthropic.Anthropic` instance) for image and image-based PDF extraction. `provider.client` is passed from the `render()` scope.

When a file is uploaded, `_handle_file_upload` calls `_extract_file_text`, then delegates to `_chat_and_format` with `recipe_source="file_content"`.

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
| `send_btn.click` | `_chat_and_format` | `textbox, chatbot, session_id, recipe_source_state, current_page_index_state, recipe_count_state` (6) | `chatbot, textbox, recipe_draft_state, inventory_proposals_state, file_upload, recipe_ready_state, recipe_count_state, confirm_btn, recipe_name_md, ingredients_tbl, proposals_tbl, progress_md` (12) |
| `file_upload.upload` | `_handle_file_upload` | `file_upload, chatbot, session_id, current_page_index_state, recipe_count_state` (5) | same 12 outputs as send_btn |
| `confirm_btn.click` | `_confirm_and_save` | `recipe_draft_state, inventory_proposals_state, session_id, saved_recipes_state, current_page_index_state, chatbot, recipe_count_state` (7) | `recipe_draft_state, confirm_btn, status_md, saved_md, saved_recipes_state, current_page_index_state, inventory_proposals_state, chatbot, progress_md` (9) |

**Key patterns:**
- No `State.change()` dependency — same single-handler pattern as `configuracion.py`
- `show_file_upload` field from agent output drives `file_upload` visibility update on each turn
- `ready_to_save` field from agent output drives `confirm_btn` interactivity — button is disabled until agent explicitly signals all fields and equivalents are resolved
- `recipe_count_state` persists the operator-stated total across turns; drives `progress_md` ("Receta X de N")
- `_confirm_and_save` appends a post-save chat message to `chatbot`; if `new_index >= recipe_count`, shows a section-completion message directing to step 5 (Estructura)
- `_confirm_and_save` is a generator (`yield`) — `show_progress="hidden"` passed to Gradio
- Agent state is loaded, run, and saved within each handler call (load/run/save pattern)

---

## 9. Additional UI helpers

### `_initial_greeting()`

```python
def _initial_greeting(_level: int = 1) -> list[dict]
```

Returns the static opening message shown in `gr.Chatbot(value=...)` when the section loads. The greeting is level-agnostic (same text for all operators). It is also injected into `AlignmentAgent` memory on the first turn via `agent.memory.add_assistant(greeting_text)` so the agent knows what was already said.

### Status translation

Display helpers translate agent status strings to Spanish before showing in the UI:

| English | Spanish | Column |
|---------|---------|--------|
| `new` | `nuevo` | Inventario / Estado |
| `matched_existing` | `existente` | Inventario / Estado |
| `needs_resolution` | `por resolver` | Inventario |

### `stable_entity_id`

All sections use `stable_entity_id(session_id)` from `gradio_app.session` to compute the integer entity ID used for loading `restaurant` and `classification` entities. This replaces the previous `abs(hash(session_id)) % (2**31 - 1)` which was non-deterministic across Python restarts (PYTHONHASHSEED randomization). `stable_entity_id` uses MD5 for a consistent result across runs.
