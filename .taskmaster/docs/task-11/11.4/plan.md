# Subtask 11.4 — Estructura section UI

## Goal

Replace the `estructura.py` stub with the full Gradio section: wire `StructuringAgent` into a
two-column chat + editable table UI, handle file upload, and persist enriched `InventoryItem`
records to DataLake after operator review.

- **Prior subtask (11.3) delivered:** `StructuringAgent` with batch inference, structured
  proposals output (`name`, `stock_unit_symbol`, `purchase_unit_symbol`,
  `purchase_to_stock_factor`, `family_name`, `category_name`, `confidence`, `is_new_item`),
  and tools for creating missing units/families.
- **Next subtasks need:** 11.5 (exports) needs no changes here. 11.6 (tests) needs the
  `_make_confirm_fn` save path to be exercised in `test_confirm_fn_saves_inventory_items`.

---

## Files to Modify / Create

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/sections/estructura.py` | Modify | Replace 6-line stub with full section implementation |

---

## Dependencies

- Subtask 11.3 done — `StructuringAgent` importable from `core.agents`
- Subtask 11.2 done — `InventoryItem` two-unit model live in schema + serialization
- DataLake populated by prior sections: `inventory_unit`, `family_inventory`,
  `inventory_item` (shells from Alineamiento), `restaurant`, `classification`
- No new packages required beyond what `alineamiento.py` already uses

---

## Key design decisions

### 1. Same load/run/save_state pattern as `alineamiento.py`

`create_agent(StructuringAgent, ...)` + `agent.load_state(...)` + `agent.run(...)` +
`agent.save_state(...)` on every turn. No special framework, no LangGraph.

### 2. Editable `gr.Dataframe` for proposal review

Operator reviews all items at once in an editable table. Chat is used only for exception
handling (gap questions, unit/family creation). Not a per-item Q&A loop.

### 3. Table columns: Artículo, Compra, Inventario, Factor, Familia, Categoría

Six columns. No Estado column — `confidence` is internal to the agent and drives
`gap_questions` only; it is not shown in the UI.

### 4. Category-by-category flow

`gr.State(value="Perecedero")` tracks current phase. On successful Perecederos confirm,
state flips to `"No perecedero"` and a transition greeting is injected into chat.
On No Perecederos confirm, completion message is shown.

### 5. Confirm fn resolves symbol → ID from DataLake; creates missing units on the fly

`_make_confirm_fn` builds `iu_symbol_to_id` from DataLake `inventory_unit` records.
If a symbol returned by the agent is not found (e.g. "bolsa" not yet in DataLake),
a new non-standard `InventoryUnit` (`is_standard=False`) is created and saved before
constructing `InventoryItem`. This prevents confirm from crashing on unknown symbols.

### 6. UPDATE path for existing items (is_new_item=False)

For shells created by Alineamiento (`is_new_item=False`), confirm fn loads the existing
record, overwrites enrichment fields (`stock_unit_id`, `purchase_unit_id`,
`purchase_to_stock_factor`, `family_id`, `category_id`, `description`), and saves with
the same ID. `DataLake.save_entity` is a full overwrite — existing `name` and `id` must
be preserved.

### 7. Table rows from `gr.Dataframe` are positional

After operator edits, `gr.Dataframe` returns `list[list]`. Confirm fn indexes columns
positionally: `[0]=name, [1]=purchase_sym, [2]=stock_sym, [3]=factor, [4]=family_name,
[5]=category_name`.

### 8. Generator pattern in confirm fn

`yield "Guardando...", False` → do work → `yield "X artículos guardados.", True`.
Consistent with `alineamiento.py` confirm fn pattern.

---

## Implementation steps

### Step 1 — Module docstring + imports

Add module-level docstring. Imports:
```python
from __future__ import annotations
from typing import Any
import gradio as gr
from core.agents.structuring_agent import StructuringAgent
from core.agents.utils import create_agent
from core.ai.providers import ClaudeProvider
from gradio_app.session import stable_entity_id
from core.domain.data_model import DEFAULT_RESTAURANT_TYPES, InventoryItem
from core.domain.serialization import inventory_item_to_dict
```

### Step 2 — `_INVENTORY_CATEGORY_IDS` constant

```python
_INVENTORY_CATEGORY_IDS = {"Perecedero": 1, "No perecedero": 2}
```

### Step 3 — `_load_structuring_context(data_lake, session_id, category)`

Returns dict with: `restaurant_name`, `restaurant_type`, `restaurant_description`,
`inventory_items` (names, filtered by `category_id` matching `category`), `families`
(names from `family_inventory`), `inventory_units` (symbols from `inventory_unit`),
`category` (passed through), `data_lake`, `session_id`.

```python
def _load_structuring_context(
    data_lake: Any, session_id: str, category: str = "Perecedero"
) -> dict:
    entity_id = stable_entity_id(session_id)
    # load restaurant name + type
    # load classification description
    # load inventory_items filtered by category_id
    # load families
    # load inventory_unit symbols
    return { ... }
```

### Step 4 — `_initial_greeting(perecedero_count)`

```python
def _initial_greeting(perecedero_count: int) -> list[dict]:
    content = (
        f"Vamos a estructurar tu inventario. Comenzaremos con los perecederos "
        f"— tienes {perecedero_count} artículos. "
        "¿Tienes un archivo con tu inventario de perecederos, "
        "o prefieres hacerlo de forma conversacional?"
    )
    return [{"role": "assistant", "content": content}]
```

### Step 5 — `_proposals_to_rows(proposals)`

Maps `list[dict]` → `list[list]` for `gr.Dataframe`:
```python
def _proposals_to_rows(proposals: list[dict]) -> list[list]:
    return [
        [
            p.get("name", ""),
            p.get("purchase_unit_symbol", ""),
            p.get("stock_unit_symbol", ""),
            p.get("purchase_to_stock_factor", 1.0),
            p.get("family_name") or "",
            p.get("category_name", ""),
        ]
        for p in (proposals or [])
    ]
```

### Step 6 — `_make_chat_fn(provider, data_lake, initial_greeting_text)`

Inner `chat_fn(message, history, session_id, recipe_source, current_category)`:
1. Guard: empty message or no session → return unchanged state.
2. `agent = create_agent(StructuringAgent, provider=provider, name="structuring_agent")`
3. `agent.load_state(data_lake, session_id=f"structuring_agent_{session_id}")`
4. First turn (empty memory): `agent.memory.add_assistant(initial_greeting_text)`
5. `ctx = _load_structuring_context(data_lake, session_id, category=current_category)`
6. `result = agent.run(input_data={"user_message": message, "recipe_source": recipe_source, "category": current_category}, context=ctx)`
7. `agent.save_state(data_lake, session_id=f"structuring_agent_{session_id}")`
8. Append user + assistant messages to history.
9. Return: `history, "", proposals, gap_questions, show_file_upload, ready_to_confirm`

`ready_to_confirm`: `True` when `result["proposals"]` is non-empty and
`result.get("gap_questions")` is empty.

### Step 7 — `_make_confirm_fn(data_lake)`

Generator `confirm_fn(proposals_rows, session_id, current_category)`:

1. `yield "Guardando...", False, current_category`
2. Build maps from DataLake:
   - `iu_symbol_to_id: dict[str, int]` from `inventory_unit`
   - `existing_item_name_to_id: dict[str, int]` from `inventory_item`
   - `family_name_to_id: dict[str, int]` from `family_inventory`
3. For each row `[name, purchase_sym, stock_sym, factor, family_name, cat_name]`:
   - Skip if `name` is empty.
   - Resolve `stock_unit_id`:
     - If `stock_sym` in `iu_symbol_to_id` → use it.
     - Else: create new `InventoryUnit(is_standard=False)`, save to DataLake, add to map.
   - Resolve `purchase_unit_id` same way.
   - `family_id = family_name_to_id.get(family_name) if family_name else None`
   - `category_id = _INVENTORY_CATEGORY_IDS.get(cat_name, 1)`
   - If `name` in `existing_item_name_to_id` (UPDATE path):
     - Load existing record, update enrichment fields, save with same ID.
   - Else (INSERT path):
     - `next_id = max(existing_ids, default=0) + 1`
     - Build `InventoryItem(...)`, save via `inventory_item_to_dict`.
4. `yield f"{count} artículos guardados correctamente.", True, current_category`

### Step 8 — `render(session_id, data_lake)`

```python
def render(session_id: gr.State, data_lake: Any) -> None:
    provider = ClaudeProvider()

    # State
    proposals_state     = gr.State([])
    category_state      = gr.State("Perecedero")
    recipe_source_state = gr.State("conversation")

    # Count Perecedero items for initial greeting
    perecedero_count = ...  # len of inventory_item entities with category_id=1

    greeting_messages = _initial_greeting(perecedero_count)
    greeting_text     = greeting_messages[0]["content"]

    with gr.Row():
        # LEFT — chat
        with gr.Column(scale=1):
            gr.Markdown("## Asistente de estructuración")
            chatbot = gr.Chatbot(label="Asistente Zenet", height="60vh", value=greeting_messages)
            textbox = gr.Textbox(placeholder="Escribe tu mensaje...", show_label=False, lines=3, max_lines=3)
            send_btn = gr.Button("Enviar")
            file_upload = gr.File(
                label="Subir archivo de inventario",
                visible=False,
                file_types=[".pdf", ".xlsx", ".xls", ".jpg", ".jpeg", ".png", ".webp"],
            )

        # RIGHT — table
        with gr.Column(scale=1):
            phase_md  = gr.Markdown("### Perecederos")
            table     = gr.Dataframe(
                headers=["Artículo", "Compra", "Inventario", "Factor", "Familia", "Categoría"],
                interactive=True,
                label="Propuesta de inventario",
            )
            confirm_btn = gr.Button("Confirmar y guardar", interactive=False)
            status_md   = gr.Markdown("")
```

Wire `send_btn.click` and `file_upload.upload` to `_chat_and_format` wrapper.
Wire `confirm_btn.click` to `_confirm_and_save` wrapper.

`_confirm_and_save` wrapper logic:
- Calls `confirm_fn(table_rows, session_id, current_category)`.
- On success + `current_category == "Perecedero"`:
  - Set `category_state` → `"No perecedero"`.
  - Inject No Perecederos transition greeting into chat.
  - Update `phase_md` to `"### No Perecederos"`.
- On success + `current_category == "No perecedero"`:
  - Show completion message in chat and `status_md`.

`_handle_file_upload` wrapper: same pattern as `alineamiento.py` — extract text,
prepend `[Contenido de archivo]\n`, call `_chat_and_format` with `recipe_source="file_content"`.

---

## Test coverage

Tests are in subtask 11.6 (`tests/unit/test_structuring_agent.py`).
Relevant test for this subtask: `test_confirm_fn_saves_inventory_items`.

No UI wiring tests are planned (Gradio event wiring is not unit-testable without a browser).

---

## Out of scope

- `core/agents/__init__.py` and `core/__init__.py` exports — subtask 11.5
- Unit and integration tests — subtask 11.6
- Architecture docs, `CLAUDE.md`, `tasks.json` updates — subtask 11.7
- File text extraction helpers (`_extract_file_text`, `_extract_text_via_vision`) — reuse
  from `alineamiento.py` if needed, or call directly; do not duplicate the logic

---

## Risks and open questions

### [OPEN] — File extraction helpers reuse vs. duplication
**Problem:** `alineamiento.py` has `_extract_file_text` and `_extract_text_via_vision`.
`estructura.py` needs the same capability. No shared module exists.
**Impact:** Duplicated code if copied; import coupling if imported from `alineamiento`.
**Suggested action:** For MVP, import directly from `alineamiento.py`
(`from gradio_app.sections.alineamiento import _extract_file_text`). Refactor to
`gradio_app/components.py` in a later cleanup pass.

### [OPEN] — Category transition greeting not scripted
**Problem:** No text is specified for the No Perecederos transition message.
**Impact:** Implementer invents the message; may be inconsistent with UX spec.
**Suggested action:** Use the text from parent plan section UX sequence step 7:
> "Perfecto, perecederos listos. Ahora pasemos a los no perecederos — tienes X artículos
> en tu inventario base. Antes de continuar, ¿hay algún artículo no perecedero que quieras
> agregar que no venga de tus recetas?"

### [OPEN] — ready_to_confirm trigger not fully specified
**Problem:** Plan says "Confirm button enabled when proposals non-empty and gap_questions
empty" but the agent may return proposals + gap_questions simultaneously (phase A+B overlap).
**Impact:** Button may never enable if gap_questions drains slowly across turns.
**Suggested action:** Enable confirm when `proposals` is non-empty regardless of
`gap_questions`. Let operator confirm even with pending gaps; factor=None items are saved
with `purchase_to_stock_factor=None`.

---

## Deliverable checklist

### `gradio_app/sections/estructura.py`

- [ ] Module docstring present
- [ ] `_INVENTORY_CATEGORY_IDS` constant defined
- [ ] `_load_structuring_context(data_lake, session_id, category)` loads all 5 entity types
- [ ] `_initial_greeting(perecedero_count)` returns correct opening message
- [ ] `_proposals_to_rows(proposals)` maps 6 fields in correct column order
- [ ] `_make_chat_fn` follows load/run/save_state pattern
- [ ] First-turn memory injection with greeting text
- [ ] File upload handled via `[Contenido de archivo...]` prefix + `recipe_source="file_content"`
- [ ] `_make_confirm_fn` resolves `stock_unit_id` and `purchase_unit_id` from symbol
- [ ] Missing symbol creates new non-standard `InventoryUnit` before saving
- [ ] UPDATE path: existing items enriched (fields overwritten, id+name preserved)
- [ ] INSERT path: new items created with next available ID
- [ ] Generator yields loading message, then final status
- [ ] `render()` left column: Chatbot + Textbox + Send button + File upload (hidden initially)
- [ ] `render()` right column: Phase indicator + editable Dataframe (6 cols) + Confirm button + status
- [ ] Confirm button disabled by default; enabled when proposals non-empty
- [ ] Perecederos confirm → category_state flips to "No perecedero" + transition greeting injected
- [ ] No Perecederos confirm → completion message shown
- [ ] Phase indicator (`phase_md`) updates on category transition
