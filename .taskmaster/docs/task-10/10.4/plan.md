# Subtask 10.4 — Gradio section: Alineamiento UI

## Goal

Replace the 5-line `alineamiento.py` stub with a full two-column Gradio section that
lets the operator capture recipes conversationally or via file upload, preview the
recipe draft and inventory proposals in real time, and persist everything on confirm.

**Builds on:** 10.2 delivered `AlignmentAgent` — handles extraction, inventory proposals,
`create_entity` tool, and draft accumulation across turns.
**Required by:** 10.5 — needs the section working end-to-end to write tests against it.

---

## Dependencies

- Subtask 10.1 done: `load_inventory_item_registry()`, `recipe_unit_conversion` persistence,
  `STANDARD_RECIPE_UNIT_SYMBOLS`, `recipe_unit_conversion_to_dict`
- Subtask 10.2 done: `AlignmentAgent` with `INPUT_SCHEMA`, `OUTPUT_SCHEMA`, `create_entity` tool
- Subtask 10.3 cancelled: no `AlignmentGraphState` or `build_conditional_graph` needed
- `create_agent()` factory — `core/agents/utils.py`
- `ClaudeProvider` — `core/ai/providers.py`
- `load_inventory_item_registry` — `core/domain/data_model_utils.py`
- `recipe_to_dict`, `inventory_item_to_dict` — `core/domain/serialization.py`
- `recipe_unit_conversion_to_dict` — `core/domain/serialization.py`
- File parsing libraries — **must install before any code changes:**
  ```bash
  uv add pypdf openpyxl pillow
  ```

---

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| No LangGraph — direct `agent.run()` in handler | No existing section uses LangGraph; single agent needs no orchestration |
| Single handler `_chat_and_format` wired to `send_btn.click` | Same pattern as `configuracion.py` — no `State.change()` dependency |
| Generator `_make_confirm_fn` yields loading state then result | Matches `configuracion.py`; operator sees feedback immediately |
| `gr.File(visible=False)` revealed conditionally | Shown only after operator indicates file-based recipe input |
| File reveal via `show_file_upload` flag in agent output | `AlignmentAgent` sets this flag when recipe source is file — no reply-text parsing |
| Image files handled via Claude vision API | `pillow` alone cannot OCR; passing image bytes to Claude as multimodal message requires no extra system dependencies |
| Agent draft reset between recipes via explicit `store()` calls | After confirm, `agent.store("recipe_draft", {})` and `agent.store("inventory_proposals", [])` clear state for recipe N+1; agent memory (conversation history) is also reset |
| `category_id` lookup by name from DataLake | On confirm, iterate `category_recipe` entities to find matching name; name uniqueness guaranteed by configuracion step |
| `equivalent` string parsed with regex on confirm | Pattern `r"[≈~]?\s*([\d.]+)\s*([a-zA-Z]+)"` extracts quantity + unit symbol; non-parseable or null → skip RecipeUnitConversion save |
| `entity_id = abs(hash(session_id)) % (2**31 - 1)` | Same stable session-to-entity-id mapping as all other sections |

---

## Files to modify / create

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/sections/alineamiento.py` | Modify | Replace stub with full `render()` |
| `pyproject.toml` / `.venv` | Modify | Install `pypdf`, `openpyxl`, `pillow` |

---

## Implementation steps

### Step 0 — Install file parsing libraries

```bash
uv add pypdf openpyxl pillow
```

Verify they appear in `pyproject.toml` before proceeding.

---

### Step 1 — Module-level imports and constants

```python
from __future__ import annotations

import re
import gradio as gr

from core.agents.alignment_agent import AlignmentAgent
from core.agents.utils import create_agent
from core.ai.providers import ClaudeProvider
from core.domain.data_model import DEFAULT_RESTAURANT_TYPES
from core.domain.data_model_utils import load_inventory_item_registry
from core.domain.serialization import (
    inventory_item_to_dict,
    recipe_to_dict,
    recipe_unit_conversion_to_dict,
)
from core.domain.data_model import InventoryItem, Recipe, Ingredient
from core.operations.normalization import RecipeUnitConversionEntry, RecipeUnitConversionKey
```

---

### Step 2 — `_load_alignment_context(data_lake, session_id) -> dict`

Pattern mirrors `_load_configuration_context` in `configuracion.py`.

```python
def _load_alignment_context(data_lake, session_id: str) -> dict:
    entity_id = abs(hash(session_id)) % (2**31 - 1)

    # Restaurant
    restaurant_name = ""
    restaurant_type = ""
    restaurant_data = data_lake.load_entity("restaurant", entity_id)
    if restaurant_data:
        restaurant_name = restaurant_data.get("name", "")
        type_id = restaurant_data.get("restaurant_type_id")
        if type_id is not None:
            type_map = {t.id: t.name for t in DEFAULT_RESTAURANT_TYPES}
            restaurant_type = type_map.get(type_id, "")

    # Classification
    standardization_level = 1
    restaurant_description = ""
    classification_data = data_lake.load_entity("classification", entity_id)
    if classification_data:
        standardization_level = classification_data.get("standardization_level", 1)
        restaurant_description = classification_data.get("restaurant_description", "")

    # Entity lists
    categories = []
    for eid in data_lake.list_entity_ids("category_recipe"):
        e = data_lake.load_entity("category_recipe", eid)
        if e:
            categories.append(e["name"])

    families = []
    for eid in data_lake.list_entity_ids("family_inventory"):
        e = data_lake.load_entity("family_inventory", eid)
        if e:
            families.append(e["name"])

    recipe_units = []
    for eid in data_lake.list_entity_ids("recipe_unit"):
        e = data_lake.load_entity("recipe_unit", eid)
        if e:
            recipe_units.append(e["symbol"])

    inventory_units = []
    for eid in data_lake.list_entity_ids("inventory_unit"):
        e = data_lake.load_entity("inventory_unit", eid)
        if e:
            inventory_units.append(e["symbol"])

    # Existing inventory items — via utility from 10.1
    item_registry = load_inventory_item_registry(data_lake, session_id)
    existing_inventory_items = [
        data_lake.load_entity("inventory_item", eid)["name"]
        for eid in data_lake.list_entity_ids("inventory_item")
        if data_lake.load_entity("inventory_item", eid)
    ]

    return {
        "restaurant_name":        restaurant_name,
        "restaurant_type":        restaurant_type,
        "restaurant_description": restaurant_description,
        "standardization_level":  standardization_level,
        "categories":             categories,
        "families":               families,
        "recipe_units":           recipe_units,
        "inventory_units":        inventory_units,
        "existing_inventory_items": existing_inventory_items,
        "data_lake":              data_lake,
        "session_id":             session_id,
    }
```

---

### Step 3 — `_extract_file_text(file_path: str) -> str`

```python
def _extract_file_text(file_path: str) -> str:
    """Extract plain text from PDF, Excel, or image files."""
    lower = file_path.lower()
    if lower.endswith(".pdf"):
        import pypdf
        reader = pypdf.PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if lower.endswith((".xlsx", ".xls")):
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True)
        lines = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                line = "  ".join(str(c) for c in row if c is not None)
                if line.strip():
                    lines.append(line)
        return "\n".join(lines)
    # Image files: pass raw bytes to Claude vision via the agent message
    # Return a sentinel so the chat handler knows to send the file path, not text
    return f"__image_file__:{file_path}"
```

Image handling note: when `_extract_file_text` returns `__image_file__:<path>`,
the chat handler reads the file bytes and passes them as multimodal content to the
agent. The `AlignmentAgent` (and `BaseAgent`) must support this — see **Risk #1**.

---

### Step 4 — `_make_chat_fn(provider, data_lake) -> Callable`

```python
def _make_chat_fn(provider, data_lake):
    def chat_fn(
        message, history, session_id,
        recipe_source, current_page_index,
    ):
        if not session_id:
            history = list(history)
            history.append({"role": "assistant", "content": "Sesión no iniciada. Recarga la página."})
            return history, "", {}, [], False, False

        if not (message or "").strip():
            return history, "", {}, [], False, False

        agent = create_agent(AlignmentAgent, provider=provider, name="alignment_agent")
        agent.load_state(data_lake, session_id=f"alignment_agent_{session_id}")

        ctx = _load_alignment_context(data_lake, session_id)

        try:
            result = agent.run(
                input_data={
                    "user_message":  message,
                    "recipe_source": recipe_source,
                    "page_index":    current_page_index,
                },
                context=ctx,
            )
            reply              = result["reply"]
            recipe_draft       = result["recipe_draft"]
            inventory_proposals = result["inventory_proposals"]
            show_file_upload   = bool(result.get("show_file_upload", False))
            recipe_ready       = bool(recipe_draft.get("recipe_name"))
        except Exception:
            reply               = "Hubo un problema al conectar con el asistente. Por favor, intenta de nuevo."
            recipe_draft        = {}
            inventory_proposals = []
            show_file_upload    = False
            recipe_ready        = False

        agent.save_state(data_lake, session_id=f"alignment_agent_{session_id}")

        history = list(history)
        history.append({"role": "user",      "content": message})
        history.append({"role": "assistant", "content": reply})

        return history, "", recipe_draft, inventory_proposals, show_file_upload, recipe_ready

    return chat_fn
```

**Note on `show_file_upload`:** `AlignmentAgent.OUTPUT_SCHEMA` does not currently
include this flag. Two options:
- (a) Add `show_file_upload: bool` to `_AlignmentResponse` and `OUTPUT_SCHEMA` in
  `alignment_agent.py` — preferred, keeps the signal structured.
- (b) Detect from `recipe_source` in gr.State after first agent turn.

Option (a) requires a minor edit to `alignment_agent.py`. See **Risk #1**.

---

### Step 5 — `_make_confirm_fn(data_lake) -> Callable` (generator)

```python
def _make_confirm_fn(data_lake):
    def confirm_fn(recipe_draft, inventory_proposals, session_id):
        if not session_id or not recipe_draft.get("recipe_name"):
            yield "No hay receta para guardar.", False
            return

        yield "Guardando receta...", False

        try:
            entity_id = abs(hash(session_id)) % (2**31 - 1)

            # --- Resolve category_id ---
            category_id = 1  # fallback
            cat_name = recipe_draft.get("recipe_category", "")
            for eid in data_lake.list_entity_ids("category_recipe"):
                e = data_lake.load_entity("category_recipe", eid)
                if e and e.get("name") == cat_name:
                    category_id = int(eid)
                    break

            # --- Assign recipe ID ---
            existing_recipe_ids = [int(i) for i in data_lake.list_entity_ids("recipe")]
            recipe_id = max(existing_recipe_ids, default=0) + 1

            # --- Save new inventory items; collect id map ---
            existing_item_ids = [int(i) for i in data_lake.list_entity_ids("inventory_item")]
            next_item_id = max(existing_item_ids, default=0) + 1

            # Build recipe_unit symbol → id map for conversion saves
            ru_symbol_to_id: dict[str, int] = {}
            for eid in data_lake.list_entity_ids("recipe_unit"):
                e = data_lake.load_entity("recipe_unit", eid)
                if e:
                    ru_symbol_to_id[e["symbol"]] = int(eid)

            # Build inventory_unit symbol → id map
            iu_symbol_to_id: dict[str, int] = {}
            for eid in data_lake.list_entity_ids("inventory_unit"):
                e = data_lake.load_entity("inventory_unit", eid)
                if e:
                    iu_symbol_to_id[e["symbol"]] = int(eid)

            # Build existing inventory item name → id map
            existing_item_name_to_id: dict[str, int] = {}
            for eid in data_lake.list_entity_ids("inventory_item"):
                e = data_lake.load_entity("inventory_item", eid)
                if e:
                    existing_item_name_to_id[e["name"]] = int(eid)

            # Resolve family name → id
            family_name_to_id: dict[str, int] = {}
            for eid in data_lake.list_entity_ids("family_inventory"):
                e = data_lake.load_entity("family_inventory", eid)
                if e:
                    family_name_to_id[e["name"]] = int(eid)

            # Save new inventory proposals
            proposal_name_to_id: dict[str, int] = {}
            for proposal in (inventory_proposals or []):
                name = proposal.get("name", "")
                if proposal.get("status") == "new" and name not in existing_item_name_to_id:
                    cat_str = proposal.get("category", "Perecedero")
                    cat_id = 1 if cat_str == "Perecedero" else 2  # standard IDs from Task 9
                    fam_name = proposal.get("family")
                    fam_id = family_name_to_id.get(fam_name) if fam_name else None
                    # Best-effort unit: fallback to g (id=1)
                    unit_id = iu_symbol_to_id.get("g", 1)
                    item = InventoryItem(
                        id=next_item_id, name=name,
                        unit_id=unit_id, category_id=cat_id, family_id=fam_id,
                    )
                    data_lake.save_entity("inventory_item", next_item_id, inventory_item_to_dict(item))
                    proposal_name_to_id[name] = next_item_id
                    next_item_id += 1
                elif name in existing_item_name_to_id:
                    proposal_name_to_id[name] = existing_item_name_to_id[name]

            # --- Build ingredients ---
            ingredients = []
            ruc_saves = []  # (key, entry) pairs to persist
            for ing_dict in (recipe_draft.get("ingredients") or []):
                ing_name    = ing_dict.get("name", "")
                ing_qty     = float(ing_dict.get("quantity", 1))
                unit_symbol = ing_dict.get("unit_symbol", "g")
                unit_id     = ru_symbol_to_id.get(unit_symbol, 1)
                inv_item_id = proposal_name_to_id.get(ing_name)

                ingredients.append(Ingredient(
                    name=ing_name,
                    quantity=ing_qty,
                    unit_id=unit_id,
                    inventory_item_id=inv_item_id,
                ))

                # Parse equivalent for RecipeUnitConversion
                equivalent = ing_dict.get("equivalent")
                if equivalent and inv_item_id:
                    match = re.search(r"[≈~]?\s*([\d.]+)\s*([a-zA-Z]+)", equivalent)
                    if match:
                        eq_qty    = float(match.group(1))
                        eq_symbol = match.group(2)
                        base_uid  = iu_symbol_to_id.get(eq_symbol)
                        ru_id     = ru_symbol_to_id.get(unit_symbol)
                        if base_uid and ru_id:
                            key   = RecipeUnitConversionKey(
                                recipe_unit_id=ru_id,
                                family_id=None,
                                inventory_item_id=inv_item_id,
                            )
                            entry = RecipeUnitConversionEntry(
                                quantity=eq_qty,
                                base_unit_id=base_uid,
                                source="agent_confirmed",
                            )
                            ruc_saves.append((key, entry))

            # --- Save Recipe ---
            recipe = Recipe(
                id=recipe_id,
                name=recipe_draft.get("recipe_name", ""),
                category_id=category_id,
                description=recipe_draft.get("recipe_description"),
                steps=recipe_draft.get("recipe_steps"),
                ingredients=ingredients,
            )
            data_lake.save_entity("recipe", recipe_id, recipe_to_dict(recipe))

            # --- Save RecipeUnitConversions ---
            for key, entry in ruc_saves:
                composite_id = f"{key.recipe_unit_id}_{key.family_id}_{key.inventory_item_id}"
                data_lake.save_entity(
                    "recipe_unit_conversion", composite_id,
                    recipe_unit_conversion_to_dict(entry, key),
                )

            saved_name = recipe_draft.get("recipe_name", "Receta")
            yield f"**{saved_name}** guardada correctamente.", True

        except Exception as exc:
            yield f"Error al guardar: {exc}", False

    return confirm_fn
```

---

### Step 6 — `_reset_agent_draft(data_lake, session_id)`

Called after a successful confirm to clear AlignmentAgent's internal draft for the
next recipe. Uses `agent.store()` directly.

```python
def _reset_agent_draft(data_lake, session_id: str) -> None:
    agent = create_agent(
        AlignmentAgent, provider=ClaudeProvider(), name="alignment_agent"
    )
    agent.load_state(data_lake, session_id=f"alignment_agent_{session_id}")
    agent.store("recipe_draft", {})
    agent.store("inventory_proposals", [])
    agent.memory.clear()
    agent.save_state(data_lake, session_id=f"alignment_agent_{session_id}")
```

---

### Step 7 — `render(session_id, data_lake)` layout and wiring

```python
def render(session_id: gr.State, data_lake) -> None:
    provider = ClaudeProvider()

    # --- State ---
    recipe_draft_state        = gr.State({})
    inventory_proposals_state = gr.State([])
    recipe_source_state       = gr.State("conversation")
    current_page_index_state  = gr.State(0)
    saved_recipes_state       = gr.State([])
    recipe_ready_state        = gr.State(False)

    with gr.Row():
        # LEFT — chat
        with gr.Column(scale=1):
            gr.Markdown("## Asistente de alineamiento")
            chatbot  = gr.Chatbot(label="Asistente Zenet", height="60vh")
            textbox  = gr.Textbox(placeholder="Escribe tu mensaje...", show_label=False, lines=3, max_lines=3)
            send_btn = gr.Button("Enviar")
            file_upload = gr.File(
                label="Subir archivo de recetas",
                visible=False,
                file_types=[".pdf", ".xlsx", ".xls", ".png", ".jpg", ".jpeg"],
            )

        # RIGHT — preview
        with gr.Column(scale=1):
            progress_md     = gr.Markdown("Receta 1 de ?")
            recipe_name_md  = gr.Markdown("")
            ingredients_tbl = gr.Dataframe(
                headers=["Ingrediente", "Cantidad", "Unidad", "Equivalente", "Inventario"],
                interactive=False,
                label="Ingredientes",
            )
            proposals_tbl   = gr.Dataframe(
                headers=["Artículo", "Categoría", "Familia", "Estado"],
                interactive=False,
                label="Artículos de inventario a crear",
            )
            confirm_btn  = gr.Button("Guardar Receta + Artículos de Inventario", interactive=False)
            status_md    = gr.Markdown("")
            saved_md     = gr.Markdown("")

    # --- Handlers ---
    chat_fn    = _make_chat_fn(provider, data_lake)
    confirm_fn = _make_confirm_fn(data_lake)

    def _chat_and_format(message, history, sid, recipe_source, page_index):
        history, text, draft, proposals, show_file, ready = chat_fn(
            message, history, sid, recipe_source, page_index,
        )
        ing_rows  = _ingredients_to_rows(draft.get("ingredients") or [])
        prop_rows = _proposals_to_rows(proposals)
        name_md   = f"### {draft.get('recipe_name', '')}" if draft.get("recipe_name") else ""
        return (
            history, text,
            draft, proposals,
            gr.update(visible=show_file),
            ready,
            gr.update(interactive=ready),
            name_md, ing_rows, prop_rows,
        )

    def _confirm_and_save(draft, proposals, sid, saved_recipes, page_index):
        yield (
            gr.update(), gr.update(interactive=False), "Guardando...", gr.update(),
        )
        status = ""
        saved = list(saved_recipes)
        success = False
        for status, success in confirm_fn(draft, proposals, sid):
            pass
        if success:
            recipe_name = draft.get("recipe_name", "Receta")
            saved.append(f"{recipe_name} ✓")
            _reset_agent_draft(data_lake, sid)
            new_index = page_index + 1
        else:
            new_index = page_index
        saved_list_md = "\n".join(f"- {r}" for r in saved) if saved else ""
        yield (
            {},
            gr.update(interactive=False),
            status,
            saved_list_md,
        )

    send_btn.click(
        fn=_chat_and_format,
        inputs=[textbox, chatbot, session_id, recipe_source_state, current_page_index_state],
        outputs=[
            chatbot, textbox,
            recipe_draft_state, inventory_proposals_state,
            file_upload, recipe_ready_state,
            confirm_btn, recipe_name_md, ingredients_tbl, proposals_tbl,
        ],
    )

    confirm_btn.click(
        fn=_confirm_and_save,
        inputs=[recipe_draft_state, inventory_proposals_state, session_id,
                saved_recipes_state, current_page_index_state],
        outputs=[recipe_draft_state, confirm_btn, status_md, saved_md],
        show_progress="hidden",
    )
```

---

### Step 8 — Display helper functions

```python
def _ingredients_to_rows(ingredients: list[dict]) -> list[list]:
    return [
        [
            ing.get("name", ""),
            ing.get("quantity", ""),
            ing.get("unit_symbol", ""),
            ing.get("equivalent") or "",
            ing.get("matched_item_name") or ing.get("inventory_link_status", ""),
        ]
        for ing in ingredients
    ]


def _proposals_to_rows(proposals: list[dict]) -> list[list]:
    return [
        [
            p.get("name", ""),
            p.get("category", ""),
            p.get("family") or "",
            p.get("status", ""),
        ]
        for p in proposals
    ]
```

---

## Out of scope

- `InventoryUnit` equivalences (`factor_to_base`, `base_unit_id`) — Task 11
- Readiness KPI recalculation
- `ConsistencyCheckAgent` — not used in this section
- `core/agents/__init__.py` and `core/__init__.py` exports — 10.5
- Architecture docs — 10.6
- Any changes to `AlignmentAgent` business logic — 10.2 is closed

---

## Risks and open questions

### [RISK] — `show_file_upload` flag missing from `AlignmentAgent` output
**Problem:** `AlignmentAgent.OUTPUT_SCHEMA` and `_AlignmentResponse` do not include a
`show_file_upload: bool` field. The chat handler needs this signal to reveal the
`gr.File` widget.
**Fix:** Before implementing step 4, add `show_file_upload: bool = False` to
`_AlignmentResponse` and `OUTPUT_SCHEMA` in `alignment_agent.py`, and add a rule to
the system prompt: "Set `show_file_upload: true` when the operator says they will
provide recipes via a file."

### [RISK] — Image file handling requires multimodal message support
**Problem:** `pillow` opens images but extracts no text. Image recipe photos require
Claude's vision API. `BaseAgent` and `AlignmentAgent` currently only pass string
`user_message` to the LLM.
**Fix options:**
- (a) For MVP: skip image support — accept PDF and Excel only; show a UI message for
  image files.
- (b) Post-MVP: extend `BaseAgent` to support multimodal messages.
**Recommended for MVP:** option (a) — simpler, no `BaseAgent` changes needed.

### [RISK] — `Perecedero`/`No perecedero` category IDs assumed to be 1 and 2
**Problem:** The confirm flow hardcodes `cat_id = 1 if cat_str == "Perecedero" else 2`.
These IDs are not guaranteed — they depend on what was saved in Task 9.
**Fix:** Look up IDs by name from DataLake at confirm time, same as `category_recipe`
lookup. Add a helper `_resolve_inventory_category_id(data_lake, name) -> int` that
iterates `inventory_category` entities (if that entity type exists) or falls back to 1/2.
Verify the entity type name used in Task 9 before implementing.

### [RISK] — `memory.clear()` method may not exist on `ConversationMemory`
**Problem:** `_reset_agent_draft` calls `agent.memory.clear()`. Verify this method
exists on `ConversationMemory` in `core/ai/memory.py` before implementing.

### [OPEN] — `_confirm_and_save` state updates incomplete
**Problem:** After confirm, `recipe_draft_state`, `inventory_proposals_state`,
`current_page_index_state`, `saved_recipes_state` all need updating. The generator
currently only yields 4 outputs. The full output list must be reconciled with the
Gradio `outputs=` list in `confirm_btn.click`.
**Suggested action:** Define the full outputs list before wiring — match exactly.

### [OPEN] — Image file types listed in gr.File but handler is unimplemented
**Source:** Validation of subtask 10.4
**Problem:** `gr.File(file_types=[..., ".png", ".jpg", ".jpeg"])` in Step 7, but
`_extract_file_text` returns an `"__image_file__:<path>"` sentinel and `_make_chat_fn`
has no code path to handle it — the sentinel gets passed directly as `user_message`.
**Impact:** Operator uploads a photo; agent receives the sentinel string and produces
garbage output or an unintelligible error.
**Suggested action:** For MVP, remove image types from `file_types` in `render()`.
Add comment: `# image support via Claude vision deferred to post-MVP`.

### [OPEN] — `_reset_agent_draft` instantiates ClaudeProvider unnecessarily
**Source:** Validation of subtask 10.4
**Problem:** `_reset_agent_draft` calls `create_agent(AlignmentAgent, provider=ClaudeProvider(), ...)`
just to invoke `store()` and `memory.clear()` — no LLM call is made. `ClaudeProvider()`
reads `ANTHROPIC_API_KEY` at construction time.
**Impact:** Crashes if `ANTHROPIC_API_KEY` is absent even though no LLM call is intended.
**Suggested action:** Accept `provider` as a parameter passed from `render()`, or verify
that `ClaudeProvider()` construction is safe when no API key is set.

---

## Deliverable checklist

### `gradio_app/sections/alineamiento.py`
- [ ] `uv add pypdf openpyxl pillow` run and verified in `pyproject.toml`
- [ ] Stub replaced with full `render()`
- [ ] `_load_alignment_context()` loads all 7 entity sources + `data_lake` + `session_id`
- [ ] `_extract_file_text()` handles PDF and Excel; image files show clear error or skip message
- [ ] `_make_chat_fn()` follows load/run/save pattern
- [ ] `_make_confirm_fn()` saves Recipe + InventoryItems + RecipeUnitConversions; links matched items
- [ ] `_reset_agent_draft()` clears draft and memory after confirm
- [ ] Single-handler pattern (`_chat_and_format`) — no `State.change()`
- [ ] `gr.File` widget revealed conditionally after format answer
- [ ] Ingredients table shows: nombre | cantidad | unidad | equivalente | inventario
- [ ] Proposals table shows: artículo | categoría | familia | estado
- [ ] Saved-recipes list accumulates below confirm button
- [ ] Progress indicator shown (`"Receta X de ~N"` or `"Receta X de ?"`)
- [ ] Confirm button disabled until `recipe_ready` is True
