# Estructura Section Architecture

## 1. Overview

The Estructura section is the **5th tab** in the pipeline. It guides the operator through
enriching the base `InventoryItem` shells produced by Alineamiento with purchase unit,
stock unit, conversion factor, family, and category — one category at a time.

Layout: **two-column** — chat on the left, proposal table and progress stepper on the right.

Data produced by this section:

| Entity | Entity type | Used by |
|--------|-------------|---------|
| Enriched `InventoryItem` records (all six fields populated) | `inventory_item` | Task 12 — Manual Operativo |
| New non-standard `InventoryUnit` records (if operator creates any) | `inventory_unit` | Task 12 — normalization |
| New `FamilyInventory` records (if operator creates any) | `family_inventory` | Task 12 |

**Implementation files:**

| File | Role |
|------|------|
| `gradio_app/sections/estructura.py` | `render()`, `_make_chat_fn`, `_make_confirm_fn`, `_confirm_and_save`, `_load_structuring_context`, `_phase_greeting`, `_progress_md`, `_proposals_to_rows` |
| `core/agents/structuring_agent.py` | `StructuringAgent` — batch inference, unit/family creation tools, proposal accumulation |

---

## 2. 4-Phase State Machine

The section drives the operator through four data-collection phases followed by a final
review and save step. Phase state is stored in `gr.State("enrich_perecederos")`.

```
enrich_perecederos → add_perecederos → enrich_no_perecederos → add_no_perecederos → final_review → done
```

| Phase key | Category | Mode | Description |
|-----------|----------|------|-------------|
| `enrich_perecederos` | Perecedero | enrich | Agent proposes all base perishable items from context in one batch |
| `add_perecederos` | Perecedero | add | Operator adds any additional perishable items not from recipes |
| `enrich_no_perecederos` | No perecedero | enrich | Agent proposes all base non-perishable items from context in one batch |
| `add_no_perecederos` | No perecedero | add | Operator adds any additional non-perishable items |
| `final_review` | — | — | Combined table with all items shown; single Confirm writes everything to DB |
| `done` | — | — | Terminal state; no further chat or saves |

**Phase mode semantics:**

- `"enrich"` — on any affirmative operator message ("listo", "sí", "adelante", etc.), the
  agent proposes ALL items in the context list in one LLM call. Confirm button enabled only
  when proposals exist and `gap_questions` is empty.
- `"add"` — operator describes additional items in conversation or uploads a file. Confirm
  button enabled as long as there are no pending `gap_questions` (even with 0 new items,
  so the operator can skip this phase).

**Phase skip rule (`enrich_no_perecederos`):**

On transition from `add_perecederos`, the section checks whether any items remain to enrich:

```python
has_cat2   = _count_items_by_category(data_lake, 2) > 0        # items with explicit category_id=2
has_unproc = _unprocessed_item_count(data_lake, already_names) > 0  # any item not yet accumulated
```

If both are `False`, `enrich_no_perecederos` is skipped and the phase advances directly to
`add_no_perecederos`.

**Deferred save pattern:**

No DB writes occur during phase transitions. Each Confirm click appends the current table
rows to `accumulated_state` (`gr.State([])`). The DB write happens only at `final_review`
confirm, writing all accumulated rows in one pass.

---

## 3. StructuringAgent

### Schemas

**INPUT_SCHEMA**

| Key | Type | Description |
|-----|------|-------------|
| `user_message` | `str` | Message from operator or extracted file content |
| `category` | `str` | `"Perecedero"` or `"No perecedero"` — current phase category |
| `recipe_source` | `str` | Optional — `"file_content"` triggers `[Contenido de archivo]` prefix |
| `phase` | `str` | Optional — `"enrich"` or `"add"`; injected into context block, not validated |

**OUTPUT_SCHEMA**

| Key | Type | Description |
|-----|------|-------------|
| `reply` | `str` | Conversational response in Spanish |
| `proposals` | `list` | List of proposal dicts for the dataframe |
| `gap_questions` | `list[str]` | Factor questions for `purchase ≠ stock` items |
| `needs_supplier_doc` | `bool \| None` | True when agent requests a supplier document |
| `raw_response` | `str` | Full LLM response string |

**RESPONSE_MODEL (`_StructuringResponse`)**

| Field | Type | Description |
|-------|------|-------------|
| `reply` | `str` | Conversational reply |
| `proposals` | `list[_StructuringItemProposal] \| None` | Batch proposals or null |
| `needs_supplier_doc` | `bool \| None` | True when agent requests a supplier document |
| `gap_questions` | `list[str] \| None` | Factor questions for purchase ≠ stock items |

**`_StructuringItemProposal` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Item name |
| `stock_unit_symbol` | `str` | Always one of `g`, `kg`, `ml`, `L`, `pza` |
| `purchase_unit_symbol` | `str` | How operator buys it — can be non-standard |
| `purchase_to_stock_factor` | `float \| None` | 1 purchase unit = X stock units; null when unknown |
| `family_name` | `str \| None` | From context family list, or null |
| `category_name` | `str` | Exactly `"Perecedero"` or `"No perecedero"` |
| `description` | `str \| None` | Optional item description |
| `confidence` | `str` | `"high"` / `"estimated"` / `"missing"` |
| `is_new_item` | `bool` | True for items not in the base inventory list |

### Context block

`_generate_prompt` injects these keys from the context dict into the system prompt:

| Key | Source |
|-----|--------|
| `restaurant_name` | `restaurant` entity |
| `restaurant_type` | `restaurant` entity |
| `restaurant_description` | `classification` entity |
| `category` | current phase category |
| `phase` | mode from `input_data` (`"enrich"` or `"add"`) |
| `inventory_items` | filtered `inventory_item` entities — list of names |
| `families` | `family_inventory` entities — list of names |
| `inventory_units` | `inventory_unit` entities — list of symbols |

Already-stored proposals are also injected under `## Propuestas ya generadas` so the agent
does not re-propose items already in the batch.

### System prompt rules (key excerpts)

**Enrich mode:**
- On any affirmative operator message, propose ALL items from the context list in one turn.
  Do not wait for subsequent messages.
- Opening reply must use this exact phrase: "Aquí está la propuesta para todos tus
  artículos perecederos definidos en la sección anterior. Revisa las unidades de compra
  sugeridas y familias sugeridas."
- Category filter rule: propose only items that belong to the current phase category
  (e.g. skip Aceite/Harina when in Perecedero phase — they will be proposed in the
  No Perecedero phase).

**Add mode:**
- Process all items described in one response turn (file or conversation).
- If operator says there are no more items ("no hay más", "listo", "nada más"), respond
  with `proposals: null` and `gap_questions: null`.

**Stock unit rule:** `stock_unit_symbol` is always one of `g`, `kg`, `ml`, `L`, `pza`.
Never use a non-standard symbol for stock.

**Factor rule:**
- `purchase_unit == stock_unit` → `purchase_to_stock_factor = 1.0`, `confidence: "high"`, no gap question.
- `purchase_unit != stock_unit` → `purchase_to_stock_factor = null`, `confidence: "missing"`, add gap question.
- `pza` is always standard — factor is always `1.0`.

**Unit creation gate:** If `purchase_unit_symbol` is not in the context unit list, ask
the operator for confirmation before calling `create_inventory_unit`. Non-standard unit
names requiring confirmation include: `caja`, `bolsa`, `costal`, `lata`, `garrafa`,
`orden`, `ord`, `ORD`, or any variant meaning "purchase order".

**Family creation gate:** If a new family is needed and not in the context family list,
ask for confirmation before calling `create_family_inventory`. For semantically similar
names (e.g. "proteínas" ≈ "Carnes y proteínas"), use the existing name directly without
asking.

**Supplier doc flag:** If purchase unit is completely unknown for a group of items, set
`needs_supplier_doc: true` and ask once for the whole group.

### Proposal preservation rule (`_process_response`)

To prevent factor-resolution turns from overwriting the full table with a partial list:

```python
if new_proposals:
    stored = self.retrieve("proposals", [])
    if len(new_proposals) >= len(stored):
        self.store("proposals", new_proposals)
proposals = self.retrieve("proposals", [])
```

A factor-resolution turn that re-proposes only the item being discussed (1 item) cannot
replace a stored full-batch list (e.g. 10 items). Replacement happens only when the new
batch is at least as large as what is stored.

---

## 4. Agent Tools

Both tools are registered in `StructuringAgent.__post_init__()` via `self.register_tool()`.

### `create_inventory_unit`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | yes | Display name (e.g. `"caja"`) |
| `symbol` | `str` | yes | Symbol string (e.g. `"caja"`) |

**Behavior:**
1. Check existing `inventory_unit` symbols in DataLake — dedup guard.
2. If symbol already exists, return informational message and ensure symbol is in context.
3. Otherwise: assign `id = max(existing_ids, default=0) + 1`; save `InventoryUnit` with `is_standard=False`, `factor_to_base=1.0`, `base_unit_id=None`.
4. Append symbol to `context["inventory_units"]` so subsequent LLM turns see it.

### `create_family_inventory`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | yes | Display name (e.g. `"Cítricos"`) |

**Behavior:**
1. Case-insensitive dedup check against existing `family_inventory` names.
2. If name already exists (case-insensitive), return canonical name and add to context.
3. Otherwise: assign `id = max(existing_ids, default=0) + 1`; save `FamilyInventory`.
4. Append name to `context["families"]`.

---

## 5. `_load_structuring_context`

```python
def _load_structuring_context(
    data_lake, session_id, category="Perecedero", already_names=None
) -> dict
```

`entity_id` for restaurant/classification: `stable_entity_id(session_id)`.

Returns:

| Key | Type | Default when missing |
|-----|------|----------------------|
| `restaurant_name` | `str` | `""` |
| `restaurant_type` | `str` | `""` |
| `restaurant_description` | `str` | `""` |
| `inventory_items` | `list[str]` | `[]` |
| `families` | `list[str]` | `[]` |
| `inventory_units` | `list[str]` | `[]` |
| `category` | `str` | (passed through) |
| `data_lake` | `DataLake` | (passed through) |
| `session_id` | `str` | (passed through) |

**Category filter with fallback:**

```python
# Primary: items matching the requested category_id
for eid in data_lake.list_entity_ids("inventory_item"):
    e = data_lake.load_entity("inventory_item", eid)
    if e and e.get("category_id") == category_id:
        if name not in exclude:
            inventory_items.append(name)

# Fallback: Alineamiento may have labelled all items as category_id=1.
# When the primary filter returns empty, load ALL items minus already_names.
if not inventory_items:
    for eid in data_lake.list_entity_ids("inventory_item"):
        e = data_lake.load_entity("inventory_item", eid)
        if e and e.get("name") and name not in exclude:
            inventory_items.append(name)
```

`already_names` is built from `accumulated_state` at call time:
```python
already_names = {str(r[0]).strip() for r in (accumulated or []) if r and r[0]}
```

This ensures that when transitioning to the No Perecedero phase, items already confirmed
in the Perecedero phase are excluded from the agent's context.

---

## 6. Phase Greeting and Progress Stepper

### `_phase_greeting(phase, data_lake, already_names=None) -> str`

| Phase | Greeting content |
|-------|-----------------|
| `enrich_perecederos` | Count of `category_id=1` items; asks operator to signal readiness |
| `add_perecederos` | Asks for additional perishable items; "listo" to skip |
| `enrich_no_perecederos` | Count: prefers `category_id=2`; falls back to `_unprocessed_item_count` when 0 |
| `add_no_perecederos` | Asks for additional non-perishable items; "listo" to skip |

For `enrich_no_perecederos`, the count is:
```python
count = _count_items_by_category(data_lake, 2)
if count == 0 and already_names is not None:
    count = _unprocessed_item_count(data_lake, already_names)
```

### `_progress_md(current_phase) -> str`

Renders a one-line Markdown stepper above the table using strikethrough for completed
phases, bold for the active phase, and plain text for pending phases.

```
**Progreso:** ~~Perecederos — Base~~ › ~~Perecederos — Adicionales~~ › **No Perecederos — Base** › No Perecederos — Adicionales
```

| Phase | Completed | Active | Pending |
|-------|-----------|--------|---------|
| Each of 4 data phases | `~~label~~` | `**label**` | `label` |
| `final_review` | all 4 as `~~...~~` | `**Revision final**` | — |
| `done` | all 5 as `~~...~~` | — | — |

---

## 7. Chat Handler (`chat_fn`)

```python
def chat_fn(message, history, session_id, recipe_source, phase, accumulated) -> tuple
```

Per-turn flow:

1. Guard: skip if `session_id` missing, message empty, or `phase` not in `_PHASE_SEQUENCE`.
2. Derive `category`, `mode`, `agent_key` from `phase`.
3. Build `already_names` from `accumulated`.
4. Create fresh `StructuringAgent` instance; load state from DataLake using `agent_key`.
5. If agent memory is empty, seed with phase greeting.
6. Load context via `_load_structuring_context(... category=category, already_names=already_names)`.
7. Call `agent.run(input_data={user_message, recipe_source, category, phase=mode}, context=ctx)`.
8. Determine confirm button readiness:
   - `enrich` mode: `ready = bool(proposals) and not gap_questions`
   - `add` mode: `ready = not gap_questions`
9. Save agent state to DataLake.
10. Return `(history, "", proposals, ready)`.

Each phase uses an isolated agent session key:
```python
agent_key = f"structuring_{phase}_{session_id}"
```

This keeps memory and data_store separate across phases (e.g. Perecedero proposals do
not appear in the No Perecedero agent's stored state).

---

## 8. Confirm Flow (`_confirm_and_save`)

This is a generator function that yields twice per invocation.

### Phase transition (all phases except `final_review`)

1. Normalize `table_rows` (pandas DataFrame or list) → `current_rows`.
2. Append `current_rows` to `accumulated_state`: `new_accumulated = list(accumulated) + current_rows`.
3. Advance to next phase in `_PHASE_SEQUENCE`.
4. Apply skip rule for `enrich_no_perecederos` (see §2).
5. Emit phase greeting into chat history.
6. Pre-seed next phase agent memory (load → add greeting → save).
7. Clear table; update `phase_md` and `progress_md`.
8. Yield second state (no DB write).

### Final review trigger (last data phase `add_no_perecederos`)

1. Set `new_phase = "final_review"`.
2. Build summary message with perecedero/no-perecedero counts.
3. Set `new_table = gr.update(value=new_accumulated)` — full combined table.
4. Enable Confirm button (`new_confirm_interactive = True`).
5. Update `phase_md` to `"### Resumen completo"`.

### Final save (`final_review`)

1. Call `confirm_fn(table_rows, sid, "Perecedero")` — the inner save generator.
2. On success: set `new_phase = "done"`, update `phase_md` to `"### Inventario estructurado"`.
3. Emit completion message (see §10).
4. Update `progress_md` to `_progress_md("done")` — all phases strikethrough.

### Inner save logic (`_make_confirm_fn`)

```python
def confirm_fn(proposals_rows, session_id, current_category) -> Generator[(str, bool)]
```

| Step | Action |
|------|--------|
| 1 | Yield `("Guardando...", False)` — loading state |
| 2 | Build lookup maps: `iu_symbol_to_id`, `existing_item_name_to_id`, `family_name_to_id` |
| 3 | For each row: resolve `stock_unit_id` and `purchase_unit_id` via `_resolve_unit_id` |
| 4 | If item name exists in DataLake: **UPDATE** (enrich existing shell, preserve id + name) |
| 5 | If item name is new: **INSERT** new `InventoryItem` with next available id |
| 6 | Yield `("{N} artículo(s) guardado(s) correctamente.", True)` |

`_resolve_unit_id(symbol)`: returns existing unit id or creates a new `is_standard=False`
unit on the fly if the symbol is not found. This ensures the confirm flow never crashes
on non-standard units not previously created through the agent tool.

Row column order expected by `confirm_fn`:

| Index | Field |
|-------|-------|
| 0 | `name` |
| 1 | `purchase_unit_symbol` |
| 2 | `stock_unit_symbol` |
| 3 | `purchase_to_stock_factor` |
| 4 | `family_name` |
| 5 | `category_name` |

---

## 9. Gradio Wiring

| Event | Handler | Key inputs | Key outputs |
|-------|---------|------------|-------------|
| `send_btn.click` | `_chat_and_format` | `textbox, chatbot, session_id, recipe_source_state, phase_state, accumulated_state` (6) | `chatbot, textbox, proposals_state, table, confirm_btn` (5) |
| `textbox.submit` | `_chat_and_format` | same 6 | same 5 |
| `file_upload.upload` | `_handle_file_upload` | `file_upload, chatbot, session_id, phase_state, accumulated_state` (5) | same 5 |
| `confirm_btn.click` | `_confirm_and_save` | `table, session_id, phase_state, chatbot, accumulated_state` (5) | `confirm_btn, status_md, chatbot, phase_state, table, phase_md, accumulated_state, progress_md` (8) |

**State variables:**

| State | Initial value | Purpose |
|-------|--------------|---------|
| `phase_state` | `"enrich_perecederos"` | Drives agent session key, category, mode |
| `proposals_state` | `[]` | Last agent proposals (used for display only) |
| `accumulated_state` | `[]` | All confirmed rows across all phases (saved at final_review) |
| `recipe_source_state` | `"conversation"` | File vs conversation mode flag |

**Key patterns:**
- `confirm_btn.click` uses `show_progress="hidden"` and yields twice (loading → final state).
- `_chat_and_format` returns `gr.update(value=rows)` for the table and
  `gr.update(interactive=ready)` for the confirm button on every chat turn.
- `file_upload.upload` delegates to `_chat_and_format` with `recipe_source="file_content"`.
- No `State.change()` dependencies — same single-handler pattern as other sections.

---

## 10. Completion Message

When `final_review` confirm succeeds, the agent emits:

> "¡Felicidades, has completado la estructuración de tu inventario! Ahora cada artículo
> tiene definida su unidad de compra, unidad de inventario, factor de conversión y familia.
> Esta es la base que necesita tu restaurante para operar con mayor control: menos merma,
> compras más precisas y decisiones basadas en datos reales. Estás un paso más cerca de
> tener una operación completamente estandarizada y eficiente. Cuando estés listo, continúa
> al siguiente paso: Manual Operativo."

---

## 11. File Upload

Reuses `_extract_file_text` from `gradio_app.sections.alineamiento`. See
`docs/Architecture/sections/alineamiento.md §5` for file type handling details.

When a file is uploaded, `_handle_file_upload` calls `_extract_file_text`, then delegates
to `_chat_and_format` with `recipe_source="file_content"` and the extracted text as the
message body.
