# Subtask 10.1 — Data model and persistence prerequisites

## Goal

Lay all data model, persistence, and utility foundations so subtasks 10.2–10.4 can build
the AlignmentAgent and Gradio UI without touching infrastructure.

**Builds on:** Tasks 1–9 and Task 17 all `done` — entities, registries, persistence layer,
and `restaurant_description` context threading are all in place.
**Required by:** Subtask 10.2 (AlignmentAgent) — needs `STANDARD_RECIPE_UNIT_SYMBOLS`,
`RecipeUnitConversionEntry.source`, `recipe_unit_conversion` persistence,
`load_inventory_item_registry()`, and extended `ingredients_to_display()` before the agent
can be written.

---

## Dependencies

- Tasks 1–9 and Task 17 all `done` (verified in tasks.json)
- No new packages required — no external API calls, no file parsing
- No env vars required

---

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| `STANDARD_RECIPE_UNIT_SYMBOLS` as frozenset constant, not `is_standard` column on `RecipeUnit` | No schema migration; pure logic constant usable in agent system prompt and code |
| Unfreeze `InventoryUnitEquivalence` + add `equivalence_source` | Task 11 needs to update equivalences; `frozen=True` prevents mutation. No current callers use instances as dict keys or set members (verified) |
| `source: str = "agent_estimated"` default on `RecipeUnitConversionEntry` | Agent-proposed values are estimates until operator explicitly confirms |
| `recipe_unit_conversion` composite key: `"{recipe_unit_id}_{family_id}_{inventory_item_id}"` | Matches the `inventory_unit_equivalence` pattern already in persistence.py |
| `load_inventory_item_registry()` returns empty registry when no items exist | Safe no-op for new sessions; 10.2 depends on this to load deduplication context |

---

## Files to modify

| File | Action | Summary |
|------|--------|---------|
| `core/operations/normalization.py` | Modify | Add `source: str = "agent_estimated"` to `RecipeUnitConversionEntry` |
| `core/domain/data_model.py` | Modify | Add `STANDARD_RECIPE_UNIT_SYMBOLS` + `is_standard_recipe_unit()`; unfreeze `InventoryUnitEquivalence`; add `equivalence_source` field |
| `core/storage/schema.py` | Modify | Add `recipe_unit_conversion` table after `inventory_unit_equivalence` |
| `core/storage/persistence.py` | Modify | Add `"recipe_unit_conversion"` to `_SQLITE_ENTITY_TYPES`; add save/load/delete/list handlers; update `_get_entity_registries()` |
| `core/domain/serialization.py` | Modify | Add `recipe_unit_conversion_to_dict` / `recipe_unit_conversion_from_dict` pair |
| `core/domain/data_model_utils.py` | Modify | Add `load_inventory_item_registry()`; extend `ingredients_to_display()` with `equivalent` and `inventory_link_status` |

---

## Implementation steps

### Step 1 — `core/operations/normalization.py` (line 270)

Add `source` field to `RecipeUnitConversionEntry`:

```python
@dataclass
class RecipeUnitConversionEntry:
    """One conversion: normalized quantity and base_unit_id."""

    quantity: float
    base_unit_id: int
    source: str = "agent_estimated"
```

Also update `RecipeUnitConversionRegistry.add()` (line 310) — it constructs the entry
directly. Add `source: str = "agent_estimated"` parameter and pass it through:

```python
self._entries[key] = RecipeUnitConversionEntry(
    quantity=quantity, base_unit_id=base_unit_id, source=source
)
```

---

### Step 2 — `core/domain/data_model.py`: constant + helper

Place after `_valid_inventory_category_ids()` (after line 84):

```python
STANDARD_RECIPE_UNIT_SYMBOLS: frozenset[str] = frozenset({"g", "kg", "ml", "L", "pza"})


def is_standard_recipe_unit(symbol: str) -> bool:
    """Return True if the symbol is a standard recipe unit (no equivalent needed)."""
    return symbol in STANDARD_RECIPE_UNIT_SYMBOLS
```

---

### Step 3 — `core/domain/data_model.py`: unfreeze `InventoryUnitEquivalence` (line 723)

Change decorator and add field:

```python
@dataclass          # was @dataclass(frozen=True)
class InventoryUnitEquivalence:
    """Per-inventory-item equivalence: for this unit and item, 1 unit = factor_to_base in base_unit_id."""

    unit_id: int
    inventory_item_id: int
    base_unit_id: int
    factor_to_base: float
    equivalence_source: str = "operator"
```

Before making this change: run `grep -r "InventoryUnitEquivalence" .` to confirm no caller
uses instances as dict keys or in sets (hashability check).

---

### Step 4 — `core/storage/schema.py`

Add after the `inventory_unit_equivalence` block (after line 134):

```python
    # 8a. Recipe unit conversions (composite key: recipe_unit_id + family_id + inventory_item_id)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipe_unit_conversion (
            recipe_unit_id    INTEGER NOT NULL,
            family_id         INTEGER,
            inventory_item_id INTEGER,
            quantity          REAL NOT NULL,
            base_unit_id      INTEGER NOT NULL,
            source            TEXT NOT NULL DEFAULT 'agent_estimated',
            PRIMARY KEY (recipe_unit_id, family_id, inventory_item_id)
        )
    """)
```

`family_id` and `inventory_item_id` are nullable — matches `RecipeUnitConversionKey` pattern.

---

### Step 5 — `core/storage/persistence.py`: `_SQLITE_ENTITY_TYPES`

Add `"recipe_unit_conversion"` to the frozenset (line 102).

---

### Step 6 — `core/storage/persistence.py`: handlers

Add a helper for parsing the composite ID string (define near the top of the module or
inline):

```python
def _parse_ruc_id(entity_id: str) -> tuple[int, int | None, int | None]:
    """Parse composite recipe_unit_conversion id string back to (recipe_unit_id, family_id, inventory_item_id)."""
    parts = str(entity_id).split("_")
    recipe_unit_id = int(parts[0])
    family_id = None if parts[1] == "None" else int(parts[1])
    inventory_item_id = None if parts[2] == "None" else int(parts[2])
    return recipe_unit_id, family_id, inventory_item_id
```

Add `elif entity_type == "recipe_unit_conversion":` blocks in `save()`, `load()`,
`delete()`, and `list_ids()` following the `inventory_unit_equivalence` pattern:

**save — UPSERT:**
```python
elif entity_type == "recipe_unit_conversion":
    recipe_unit_id, family_id, inventory_item_id = _parse_ruc_id(entity_id)
    cursor.execute(
        """
        INSERT INTO recipe_unit_conversion
            (recipe_unit_id, family_id, inventory_item_id, quantity, base_unit_id, source)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(recipe_unit_id, family_id, inventory_item_id) DO UPDATE SET
            quantity = excluded.quantity,
            base_unit_id = excluded.base_unit_id,
            source = excluded.source
        """,
        (
            recipe_unit_id,
            family_id,
            inventory_item_id,
            data_dict["quantity"],
            data_dict["base_unit_id"],
            data_dict.get("source", "agent_estimated"),
        ),
    )
```

**load — SELECT:**
```python
elif entity_type == "recipe_unit_conversion":
    recipe_unit_id, family_id, inventory_item_id = _parse_ruc_id(entity_id)
    cursor.execute(
        "SELECT * FROM recipe_unit_conversion WHERE recipe_unit_id=? AND family_id IS ? AND inventory_item_id IS ?",
        (recipe_unit_id, family_id, inventory_item_id),
    )
    row = cursor.fetchone()
    return dict(row) if row else None
```

**delete:**
```python
elif entity_type == "recipe_unit_conversion":
    recipe_unit_id, family_id, inventory_item_id = _parse_ruc_id(entity_id)
    cursor.execute(
        "DELETE FROM recipe_unit_conversion WHERE recipe_unit_id=? AND family_id IS ? AND inventory_item_id IS ?",
        (recipe_unit_id, family_id, inventory_item_id),
    )
```

**list_ids:**
```python
if entity_type == "recipe_unit_conversion":
    cursor.execute("SELECT recipe_unit_id, family_id, inventory_item_id FROM recipe_unit_conversion")
    return [f"{r[0]}_{r[1]}_{r[2]}" for r in cursor.fetchall()]
```

Note: use `IS ?` (not `= ?`) for nullable `family_id` and `inventory_item_id` so NULL
comparisons work correctly in SQLite.

---

### Step 7 — `core/storage/persistence.py`: `_get_entity_registries()`

Add to all three dicts (lines ~498–527):

```python
# class_to_type
norm.RecipeUnitConversionEntry: "recipe_unit_conversion",

# type_to_from_dict
"recipe_unit_conversion": ser.recipe_unit_conversion_from_dict,

# type_to_to_dict
"recipe_unit_conversion": ser.recipe_unit_conversion_to_dict,
```

Add `import core.operations.normalization as norm` at the top of `persistence.py` if not
already present.

---

### Step 8 — `core/domain/serialization.py`

Add after `inventory_unit_equivalence_from_dict`:

```python
def recipe_unit_conversion_to_dict(
    entry: RecipeUnitConversionEntry, key: RecipeUnitConversionKey
) -> dict:
    return {
        "recipe_unit_id": key.recipe_unit_id,
        "family_id": key.family_id,
        "inventory_item_id": key.inventory_item_id,
        "quantity": entry.quantity,
        "base_unit_id": entry.base_unit_id,
        "source": entry.source,
    }


def recipe_unit_conversion_from_dict(
    d: dict,
) -> tuple[RecipeUnitConversionKey, RecipeUnitConversionEntry]:
    key = RecipeUnitConversionKey(
        recipe_unit_id=d["recipe_unit_id"],
        family_id=d.get("family_id"),
        inventory_item_id=d.get("inventory_item_id"),
    )
    entry = RecipeUnitConversionEntry(
        quantity=d["quantity"],
        base_unit_id=d["base_unit_id"],
        source=d.get("source", "agent_estimated"),
    )
    return key, entry
```

Import `RecipeUnitConversionKey` and `RecipeUnitConversionEntry` from
`core.operations.normalization` at the top of `serialization.py` if not already present.

---

### Step 9 — `core/domain/data_model_utils.py`: `load_inventory_item_registry()`

Add after the existing imports/helpers:

```python
def load_inventory_item_registry(data_lake, session_id: str) -> InventoryItemRegistry:
    """Load all InventoryItem entities from DataLake into a new registry.

    Returns an empty registry if no items exist (safe no-op for new sessions).
    """
    registry = InventoryItemRegistry()
    for item_id in data_lake.list_entity_ids("inventory_item"):
        data = data_lake.load_entity("inventory_item", item_id)
        if data:
            registry.add(inventory_item_from_dict(data))
    return registry
```

---

### Step 10 — `core/domain/data_model_utils.py`: extend `ingredients_to_display()`

Add two keys to the `row` dict (after `unit_id`, before the inventory_item_registry block):

```python
row["equivalent"] = None                    # per-ingredient mass equivalent; set by AlignmentAgent
row["inventory_link_status"] = "needs_resolution"  # default; caller overrides
```

Signature stays unchanged. The keys must be present so the UI can render columns
consistently regardless of whether the agent has filled them.

---

## Test coverage

Tests live in `tests/unit/test_alignment_agent.py` (created in subtask 10.5).
The following tests from the parent plan are directly exercised by 10.1 code:

| Test | Validates |
|------|-----------|
| `test_recipe_unit_conversion_roundtrip` | save → reload from SQLite returns same entry including `source` field |
| `test_ingredients_to_display_equivalent_and_status_columns` | `equivalent` and `inventory_link_status` keys present in output |
| `test_is_standard_recipe_unit_true_for_standard` | `is_standard_recipe_unit("g")` returns `True` |
| `test_is_standard_recipe_unit_false_for_nonstandard` | `is_standard_recipe_unit("taza")` returns `False` |
| `test_load_alignment_context_all_keys_present` | returns registry with items when DataLake has inventory_item entities |
| `test_load_alignment_context_defaults_on_empty_datalake` | returns empty registry when no entities |

**Live tests:** None — no LLM calls in 10.1.

---

## Out of scope

- `AlignmentAgent` — 10.2
- LangGraph graph — 10.3
- Gradio UI — 10.4
- Agent exports (`__init__.py`) — 10.5
- Architecture docs — 10.6
- `InventoryUnit` equivalences (`factor_to_base`, `base_unit_id`) — Task 11
- File parsing libraries (`pypdf`, `openpyxl`, `pillow`) — added at start of 10.2

---

## Risks and open questions

### [RISK] — `RecipeUnitConversionRegistry.add()` constructs entry directly
**Problem:** Line 310 in `normalization.py` constructs `RecipeUnitConversionEntry(quantity=quantity, base_unit_id=base_unit_id)` without a `source` parameter. After adding the field, `source` will always default to `"agent_estimated"` regardless of caller intent.
**Fix:** Add `source: str = "agent_estimated"` parameter to `add()` and pass it through to the constructor.

### [RISK] — Composite key with `None` values in string ID
**Problem:** `"{recipe_unit_id}_{family_id}_{inventory_item_id}"` produces strings like `"5_None_12"` when fields are `None`. Round-trip parsing must handle the literal string `"None"` → Python `None`.
**Fix:** Use the `_parse_ruc_id()` helper defined in step 6 above.

### [RISK] — SQLite NULL comparison in load/delete
**Problem:** `WHERE family_id = ?` with `None` does not match NULL rows in SQLite — must use `IS ?`.
**Fix:** Use `IS ?` for nullable columns in all SELECT/DELETE queries (shown in step 6).

### [RISK] — `equivalence_source` missing in existing SQLite rows
**Problem:** Existing `inventory_unit_equivalence` rows have no `equivalence_source` column. The deserializer `inventory_unit_equivalence_from_dict` will raise `KeyError` unless it uses `.get()`.
**Fix:** In `serialization.py`, update `inventory_unit_equivalence_from_dict` to read `equivalence_source` with fallback: `d.get("equivalence_source", "operator")`.

### [RISK] — `normalization` import in `persistence.py`
**Problem:** `persistence.py` does not currently import `core.operations.normalization`. Adding `norm.RecipeUnitConversionEntry` to `_get_entity_registries()` requires this import.
**Fix:** Add `from core.operations import normalization as norm` (or equivalent) at the top of `persistence.py`. Check for circular imports before adding.

---

## Deliverable checklist

### `core/operations/normalization.py`
- [ ] `RecipeUnitConversionEntry.source` field added
- [ ] `RecipeUnitConversionRegistry.add()` updated to accept and pass through `source`

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
- [ ] `_get_entity_registries()` updated with `recipe_unit_conversion` entry
- [ ] `inventory_unit_equivalence_from_dict` uses `.get("equivalence_source", "operator")` fallback

### `core/domain/serialization.py`
- [ ] `recipe_unit_conversion_to_dict` / `recipe_unit_conversion_from_dict` added (standalone pair pattern)

### `core/domain/data_model_utils.py`
- [ ] `load_inventory_item_registry()` added
- [ ] `ingredients_to_display()` extended with `equivalent` and `inventory_link_status`
