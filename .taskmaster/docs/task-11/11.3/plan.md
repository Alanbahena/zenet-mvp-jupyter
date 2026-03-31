# Subtask 11.3 — StructuringAgent

## Goal

Create `StructuringAgent` — the batch-inference LLM agent that proposes `stock_unit`,
`purchase_unit`, `purchase_to_stock_factor`, `family`, `category`, and `description` for
all inventory items in a single LLM call, producing a structured proposal list that the
Estructura UI (11.4) renders as an editable dataframe.

- **Prior (11.2) delivered:** `InventoryItem` two-unit model fully propagated through
  schema / serialization / persistence / normalization. All existing tests green.
- **Next (11.4) needs:** `StructuringAgent` importable from `core.agents`, with
  `_generate_prompt` and `_process_response` implemented so `agent.run()` returns
  `proposals` (list of dicts) for the dataframe and `gap_questions` for the chat panel.
  All symbols in proposals are guaranteed to exist in DataLake by the time the operator
  hits Confirm (resolved during conversation via tools). Factors may be `None` (pending).

---

## Files to modify / create

| File | Action | Summary |
|---|---|---|
| `core/agents/structuring_agent.py` | Create | `StructuringAgent(BaseAgent)` with Pydantic response models, system prompt, tools, `_generate_prompt`, `_process_response` |
| `core/agents/__init__.py` | Modify | Add `StructuringAgent` import and `__all__` entry |

---

## Key design decisions

| Decision | Rationale |
|---|---|
| Single LLM call for all items (batch) | Realistic load is 3–50 items — one call is faster and more coherent than per-item Q&A |
| `pza` never needs a factor question | `pza` is always standard; `purchase = stock` always |
| Matching units get factor `1.0` automatically | No question needed when `purchase_unit == stock_unit` |
| Factor resolution is always operator-first | Agent never fills `purchase_to_stock_factor` unilaterally; operator is asked first, estimate offered only if declined, blank allowed if estimate also declined |
| `purchase_to_stock_factor: float \| None` | `None` means pending — operator chose to leave it blank; confirm fn saves it as-is; deduction will skip items with no factor |
| `confidence` field internal only — not shown in table | Drives `gap_questions` generation; the table is editable so operator corrects what looks wrong without needing a status label |
| Table columns: Artículo, Compra, Inventario, Factor, Familia, Categoría | No Estado/status column — chat handles missing data via `gap_questions`; `—` shown for `None` factors |
| `is_new_item: bool` in proposal | Distinguishes enrichment of existing base-inventory shells from new items detected in an uploaded file |
| `create_inventory_unit` tool | Non-standard purchase unit symbols not in DataLake require operator confirmation before creation |
| `create_family_inventory` tool | New families not in current configuration require operator confirmation |
| Stock units never created via tool | `stock_unit_symbol` is always one of the 5 standard units; system prompt rule prevents non-standard stock inference |
| Non-standard units created with `is_standard=False`, no chain | `factor_to_base=1.0`, `base_unit_id=None`; conversion lives on `InventoryItem.purchase_to_stock_factor` |

---

## Conversation flow

### Phase A — Batch inference + unit/family creation

1. Operator uploads file or describes items conversationally.
2. Agent runs batch inference on all items in one response:
   - Infers `stock_unit_symbol`, `purchase_unit_symbol`, `family_name`, `category_name`, `description`.
   - Sets `purchase_to_stock_factor = 1.0` and `confidence: "high"` when `purchase == stock`.
   - Sets `purchase_to_stock_factor = None` and `confidence: "missing"` when `purchase ≠ stock` (factor unknown until operator confirms).
   - Identifies any `purchase_unit_symbol` not in the context unit list.
3. If unknown units found: agent asks operator to confirm creation (one question for the group). Tools run after confirmation.
4. If unknown families requested: same pattern.

### Phase B — Factor resolution (one item at a time, only where purchase ≠ stock)

For each item where `purchase_unit ≠ stock_unit`, agent asks in sequence:

**Step 1 — Ask if operator knows:**
> "Para el **bistec**: ¿cuántos kg trae una caja aproximadamente?"

- Operator provides value → factor filled, move to next item.
- Operator doesn't know → go to Step 2.

**Step 2 — Offer agent estimate:**
> "¿Quieres que yo proponga un estimado y tú lo confirmas o corriges en la tabla?"

- Operator accepts → agent proposes value, flags as `confidence: "estimated"`, move to next item.
- Operator declines → go to Step 3.

**Step 3 — Leave blank:**
> "Entendido, queda pendiente. Podrás actualizarlo más adelante."

- Factor stays `None`. Item saved with `purchase_to_stock_factor=None`.

### Phase C — Table review + confirm

Agent presents full table after all factor questions resolved (or deferred).
Operator edits cells directly. Hits Confirm.

---

## Implementation steps

### `core/agents/structuring_agent.py` — Create

1. **Define `_StructuringItemProposal(BaseModel)`** with fields:
   - `name: str` — canonical inventory item name
   - `stock_unit_symbol: str` — always standard: `g`, `kg`, `ml`, `L`, `pza`
   - `purchase_unit_symbol: str` — how the operator buys it (may be non-standard)
   - `purchase_to_stock_factor: float | None` — `None` when unknown/pending; `1.0` when `purchase == stock`
   - `family_name: str | None` — from context families list; null if none fits
   - `category_name: str` — exactly `"Perecedero"` or `"No perecedero"`
   - `description: str | None` — brief item description; null if not inferrable
   - `confidence: str` — `"high"` (clear inference) | `"estimated"` (agent proposed, operator accepted) | `"missing"` (factor pending or required field absent)
   - `is_new_item: bool` — `True` if item was not in the base inventory passed in context

2. **Define `_StructuringResponse(BaseModel)`** with fields:
   - `reply: str` — conversational response in Spanish
   - `proposals: list[_StructuringItemProposal] | None` — full batch proposal; null if not yet ready
   - `needs_supplier_doc: bool | None` — `True` if agent requests supplier receipt for missing purchase units
   - `gap_questions: list[str] | None` — factor questions for `purchase ≠ stock` items, plus any other missing fields

3. **Define `_SYSTEM_PROMPT`** (module-level string constant):

   Core rules to encode:

   **Batch inference rules:**
   - Infer all fields for every item in the inventory list in a single response.
   - `stock_unit_symbol` must always be one of: `g`, `kg`, `ml`, `L`, `pza`. Never non-standard.
   - `purchase_unit_symbol` may be non-standard (caja, bolsa, costal, lata, etc.).
   - When `purchase_unit_symbol == stock_unit_symbol`: set `purchase_to_stock_factor = 1.0`,
     `confidence: "high"`. No factor question needed.
   - When `purchase_unit_symbol != stock_unit_symbol`: set `purchase_to_stock_factor = null`,
     `confidence: "missing"`. Add a factor question to `gap_questions`.
   - `pza` is always standard — `purchase_to_stock_factor` is always `1.0` for pza items.

   **Factor resolution rules (Phase B — after batch):**
   - Ask for each factor one at a time, in order.
   - Step 1: ask if operator knows the value.
   - Step 2 (if unknown): offer to propose an estimate.
   - Step 3 (if estimate declined): confirm it stays pending, set `purchase_to_stock_factor: null`.
   - When operator provides or accepts a value: update proposal, set `confidence: "estimated"` if
     agent proposed, `"high"` if operator provided.
   - Never fill a factor without asking the operator first.

   **Unit / family creation rules:**
   - If `purchase_unit_symbol` is not in the context unit list: ask operator to confirm creation
     before calling `create_inventory_unit`. Do not call the tool without explicit confirmation.
   - If a new family is requested: ask to confirm before calling `create_family_inventory`.
   - If no family fits from context, use `null` — do not invent family names.
   - Units and families loaded from DataLake at session start (via `_load_structuring_context`
     in 11.4) are already in the context lists — agent must never ask to create something
     that is already there.

   **Missing purchase unit rule:**
   - If purchase unit is entirely unknown for a group of items: set `needs_supplier_doc: true`,
     ask once for the whole group (supplier doc vs. agent estimates).

   **General rules:**
   - Items in the base inventory list are always `is_new_item: false`.
   - Items detected in the file not in the base list are `is_new_item: true`.
   - `category_name` must be exactly `"Perecedero"` or `"No perecedero"`.
   - No-hallucination: infer from item name + restaurant type context only.
   - File content arrives prefixed with `[Contenido de archivo...]` — extract all items
     in the same turn; do not wait for subsequent messages.
   - Language: always Spanish. Tone: direct, no jargon. Max 3–4 sentences in `reply`.
   - Response format: always JSON matching `_StructuringResponse`. No JSON inside `reply`.

4. **Define `StructuringAgent(BaseAgent)` as `@dataclass`**:
   ```python
   @dataclass
   class StructuringAgent(BaseAgent):
       INPUT_SCHEMA: ClassVar[dict[str, str]] = {
           "user_message": "Message from operator or extracted file content.",
           "category": "'Perecedero' or 'No perecedero' — current phase.",
       }
       OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
           "reply": "Conversational response in Spanish.",
           "proposals": "List of proposal dicts for the dataframe.",
           "gap_questions": "List of factor questions for purchase≠stock items.",
           "needs_supplier_doc": "True when agent requests a supplier document.",
           "raw_response": "Full LLM response string.",
       }
       RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = _StructuringResponse
   ```

5. **Implement `__post_init__`** — register two tools:

   **Tool 1: `create_inventory_unit`**
   - Description: "Create a new non-standard purchase unit (is_standard=False). Only call
     after the operator has explicitly confirmed they want to create it."
   - Parameters: `name: str`, `symbol: str`
   - Implementation (`_create_inventory_unit_tool`):
     - Get `data_lake` from `self._data_lake` (set in `_generate_prompt`)
     - **Dedup guard:** load all existing `inventory_unit` records from DataLake; collect
       their symbols. If `symbol` already exists, do NOT insert — return:
       `f"La unidad '{symbol}' ya existe en la configuración — no es necesario crearla."`
       and ensure symbol is in `self._context["inventory_units"]`.
     - Next id: `max(int(eid) for eid in data_lake.list_entity_ids("inventory_unit"), default=0) + 1`
     - Save: `{"id": next_id, "name": name, "symbol": symbol, "base_unit_id": None, "factor_to_base": 1.0, "is_standard": False}`
     - Append symbol to `self._context["inventory_units"]`
     - Return: `f"Unidad '{name}' ({symbol}) creada con id {next_id}."`

   **Tool 2: `create_family_inventory`**
   - Description: "Create a new inventory family. Only call after the operator has
     explicitly confirmed they want to create it."
   - Parameters: `name: str`
   - Implementation (`_create_family_inventory_tool`):
     - Get `data_lake` from `self._data_lake`
     - **Dedup guard:** load all existing `family_inventory` records from DataLake; collect
       their names. If `name` already exists (case-insensitive), do NOT insert — return:
       `f"La familia '{name}' ya existe en la configuración — no es necesario crearla."`
       and ensure name is in `self._context["families"]`.
     - Next id from `data_lake.list_entity_ids("family_inventory")`
     - Save: `{"id": next_id, "name": name, "base_unit_id": None}`
     - Append name to `self._context["families"]`
     - Return: `f"Familia '{name}' creada con id {next_id}."`

6. **Implement `_generate_prompt(input_data, context)`**:

   Store references for tool access:
   ```python
   self._data_lake = context.get("data_lake")
   self._context = context
   ```

   Build system prompt = `_SYSTEM_PROMPT` + context block as additional section.

   Context keys to inject (all optional — skip if absent):
   - `restaurant_name`, `restaurant_type`, `restaurant_description`
   - `category` (current phase: `"Perecedero"` or `"No perecedero"`)
   - `inventory_items`: list of item names for the current category (from base inventory)
   - `families`: list of `FamilyInventory` names available in this session
   - `inventory_units`: list of `InventoryUnit` symbols available (standard + any created so far)

   Inject accumulated proposals from `self.retrieve("proposals", [])` so the agent knows
   what was already proposed in prior turns.

   User message: `input_data["user_message"]`.
   If `input_data.get("recipe_source") == "file_content"`, prefix with `[Contenido de archivo]\n`.

   Return `(system, user_message)`.

7. **Implement `_process_response(response)`**:
   ```python
   def _process_response(self, response: str) -> dict[str, Any]:
       data = self._parse_response(response)
       proposals = list(data.get("proposals") or [])
       self.store("proposals", proposals)
       gap_questions = list(data.get("gap_questions") or [])
       self.store("gap_questions", gap_questions)
       return {
           "reply": data.get("reply", ""),
           "proposals": proposals,
           "gap_questions": gap_questions,
           "needs_supplier_doc": data.get("needs_supplier_doc"),
           "raw_response": response,
       }
   ```

### `core/agents/__init__.py` — Modify

8. Add import: `from core.agents.structuring_agent import StructuringAgent`
9. Add `"StructuringAgent"` to `__all__` — alphabetical order: after `"RestaurantInfoAgent"`,
   before `"WelcomeAgent"`.

---

## Data contract between sections

```
Configuración (3)  →  DataLake: inventory_unit, family_inventory, category_recipe, recipe_unit
                              ↓  loaded at Estructura start via _load_structuring_context (11.4)
Alineamiento (4)   →  DataLake: inventory_item shells
                       (name, stock_unit_id=g, purchase_unit_id=g, category_id)
                              ↓  loaded as base inventory list
Estructura (5)     →  For each proposal:
                         is_new_item=False  →  UPDATE existing DataLake record (same id)
                         is_new_item=True   →  INSERT new record (new id)
                       Tools guard against duplicate unit/family creation via dedup check.
                       Confirm fn guards against duplicate inventory_item via name lookup.
```

**Dedup rules by entity type:**

| Entity | Dedup key | Owner | Guard location |
|---|---|---|---|
| `inventory_unit` | `symbol` (exact) | Configuración creates; Estructura may add | Tool dedup check |
| `family_inventory` | `name` (case-insensitive) | Configuración creates; Estructura may add | Tool dedup check |
| `inventory_item` | `name` (exact) | Alineamiento creates shells; Estructura enriches | Confirm fn: update vs. insert by name lookup |

---

## Full conversation example (taquería, 5 perecederos)

**Base inventory:** bistec, cebolla, aguacate, limón, crema

**Turn 1 — Operator uploads invoice**

Agent batch inference:
- `caja`, `costal` not in unit list → ask to create
- `bistec (caja→kg)`, `limón (costal→kg)` → `purchase_to_stock_factor: null`, `confidence: "missing"`
- `cebolla (kg→kg)`, `aguacate (pza→pza)`, `crema (L→L)` → factor `1.0`, `confidence: "high"`

> **Zeni:** "Encontré tus 5 artículos. Dos unidades no están en tu configuración: 'caja' y 'costal'. ¿Las creamos?"

> **Operator:** "Sí"

Tools run → units created. Table shown with `—` for bistec and limón factors.

**Turn 2 — Factor resolution, bistec**

> **Zeni:** "Para el **bistec**: ¿cuántos kg trae una caja aproximadamente?"

> **Operator:** "Como 8 kg"

Bistec factor → `8.0`, `confidence: "high"`.

**Turn 3 — Factor resolution, limón**

> **Zeni:** "¿Y para el **limón**: cuántos kg trae un costal?"

> **Operator:** "No sé"

> **Zeni:** "¿Quieres que yo proponga un estimado y tú lo confirmas en la tabla?"

> **Operator:** "No, déjalo pendiente"

> **Zeni:** "Entendido, queda pendiente. Aquí está la tabla completa — edita lo que necesites y confirma cuando estés listo."

**Final table:**

| Artículo | Compra | Inventario | Factor | Familia | Categoría |
|---|---|---|---|---|---|
| bistec | caja | kg | 8 | Carnes | Perecedero |
| cebolla | kg | kg | 1 | Verduras | Perecedero |
| aguacate | pza | pza | 1 | Frutas | Perecedero |
| limón | costal | kg | — | Frutas | Perecedero |
| crema | L | L | 1 | Lácteos | Perecedero |

**Confirm fn:** saves all 5 records. `limón.purchase_to_stock_factor = None`.

---

## Out of scope

- `gradio_app/sections/estructura.py` — 11.4
- `core/__init__.py` re-export of `StructuringAgent` — 11.5
- `tests/unit/test_structuring_agent.py` — 11.6
- Architecture docs, CLAUDE.md, tasks.json updates — 11.7
- Update-vs-insert logic for existing DataLake records — 11.4 confirm fn (dedup by item name)
- `_load_structuring_context` that populates unit/family/item lists from DataLake — 11.4
- Deduction behavior for items with `purchase_to_stock_factor=None` — Task 12

---

## Risks and open questions

### [OPEN] — Conversational path (no file) undefined
**Source:** Validation of subtask 11.3
**Problem:** No turn-by-turn flow defined for when operator describes items in natural
language instead of uploading a file.
**Impact:** Inconsistent behavior between file-upload and conversational paths.
**Suggested action:** Treat both paths identically — any operator message triggers batch
inference. `[Contenido de archivo]` prefix is the only difference. Document in system prompt.

### [OPEN] — Alineamiento shells have stock_unit_id=1 (g) — resolved in 11.4
**Source:** Validation of subtask 11.3
**Problem:** Shells created by Alineamiento default to `stock_unit_id = purchase_unit_id = 1` (g).
11.4 confirm fn must UPDATE existing DataLake records (not insert) for `is_new_item=False` items.
The dedup key is item `name` — confirm fn does a name lookup against existing DataLake records
to decide update vs. insert.
**Impact:** DataLake will have stale g/g records unless 11.4 confirm fn issues an update.
**Suggested action:** 11.4 confirm fn: for each proposal, look up existing `inventory_item` by
name; if found → update that record's id; if not found → insert with new id.

### [OPEN] — recipe_source is an undocumented optional input
**Source:** Validation of subtask 11.3
**Problem:** `_generate_prompt` references `input_data.get("recipe_source")` to decide
whether to prefix with `[Contenido de archivo]`, but `"recipe_source"` is not listed
in `INPUT_SCHEMA` or documented anywhere in the plan as an optional input key.
**Impact:** Callers in 11.4 may omit it and get wrong prompt framing; test writers
won't know it exists.
**Suggested action:** Add a note to step 6 that `"recipe_source"` is an optional input
key (not in `INPUT_SCHEMA`) accepted by `_generate_prompt`. Valid values: `"file_content"` | `None`.

### [OPEN] — Factor question order not fully specified
**Source:** Validation of subtask 11.3
**Problem:** Phase B asks factors one item at a time, but the order is not defined when
multiple items have `purchase ≠ stock`.
**Impact:** Minor — any consistent order works. Suggest: order of appearance in the base
inventory list.
**Suggested action:** Document order rule in system prompt: ask in the same order items
appear in the base inventory list passed in context.

---

## Deliverable checklist

`core/agents/structuring_agent.py`
- [ ] `_StructuringItemProposal(BaseModel)` defined with all 9 fields; `purchase_to_stock_factor: float | None`
- [ ] `_StructuringResponse(BaseModel)` defined with all 4 fields
- [ ] `_SYSTEM_PROMPT` defined as module-level constant with all rules from this plan
- [ ] `StructuringAgent(BaseAgent)` implemented as `@dataclass`
- [ ] `INPUT_SCHEMA`, `OUTPUT_SCHEMA`, `RESPONSE_MODEL` set as `ClassVar`
- [ ] `__post_init__` registers `create_inventory_unit` and `create_family_inventory` tools
- [ ] `_create_inventory_unit_tool` dedup guard: checks existing symbols before inserting; saves `is_standard=False` unit; appends symbol to context unit list
- [ ] `_create_family_inventory_tool` dedup guard: checks existing names (case-insensitive) before inserting; saves family; appends name to context families list
- [ ] `_generate_prompt` stores `self._data_lake` and `self._context`; injects all context keys; injects accumulated proposals
- [ ] `_process_response` stores proposals and gap_questions in `_data_store`; returns all 5 output keys
- [ ] Factor `None` allowed in proposals — not coerced to a default value
- [ ] `confidence` field internal only — not surfaced to table as a column

`core/agents/__init__.py`
- [ ] `StructuringAgent` imported
- [ ] `"StructuringAgent"` added to `__all__` in alphabetical order
