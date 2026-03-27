# Subtask 11.2 — Schema + serialization + persistence + normalization

## Goal

Propagate the `InventoryItem` two-unit model through every layer that still
references `unit_id` or `InventoryUnitEquivalence` so the full stack
(schema → serialization → persistence → normalization → utils → Alineamiento)
is consistent with the 11.1 data model before the agent is built in 11.3.

- **Prior (11.1) delivered:** updated `InventoryItem` dataclass, `InventoryUnitEquivalence`
  removed from `data_model.py`, `equivalence_registry` type annotations stubbed as
  `Optional[Any]` in `normalization.py` and `readiness_kpis.py`.
- **Next (11.3) needs:** `InventoryItem` fully loadable from/to SQLite with the new
  fields, `normalization.py` signatures cleaned up, `alineamiento.py` confirm flow
  not crashing at runtime.

---

## Files to modify

| File | Action | Summary |
|---|---|---|
| `core/storage/schema.py` | Modify | Replace `unit_id` column; drop `inventory_unit_equivalence` table + its index |
| `core/domain/serialization.py` | Modify | Update `inventory_item_to/from_dict` for 3 new fields |
| `core/storage/persistence.py` | Modify | Update SQLite save for `inventory_item`; remove all `inventory_unit_equivalence` references |
| `core/operations/normalization.py` | Modify | Remove `equivalence_registry` + `inventory_item_id` params; fix `make_resolver` |
| `core/domain/data_model_utils.py` | Modify | Fix `unit_id` → `stock_unit_id` in 2 functions; update `create_inventory_item_from_ingredient` |
| `gradio_app/sections/alineamiento.py` | Modify | Update `InventoryItem(...)` construction in confirm flow |
| `tests/unit/test_serialization.py` | Modify | Fix `unit_id` references (~18 hits) |
| `tests/unit/test_normalization.py` | Modify | Fix `equivalence_registry` param calls (~28 hits) |
| `tests/unit/test_persistence.py` | Modify | Fix `inventory_unit_equivalence` entity type + `unit_id` (~25 hits) |
| `tests/unit/test_data_model_utils.py` | Modify | Fix `unit_id` references (~7 hits) |
| `tests/unit/test_alignment_agent.py` | Modify | Fix `unit_id` references (~5 hits) |

---

## Key design decisions

| Decision | Rationale |
|---|---|
| `CREATE TABLE IF NOT EXISTS` — no ALTER | Existing DBs need `reset_session.py`; schema migration is outside MVP scope |
| `to_base_quantity` does NOT receive `InventoryItem` | Keeps the function generic (unit chain only); item-specific conversion lives on `InventoryItem.purchase_to_stock_factor` |
| `create_inventory_item_from_ingredient` gets full three-field signature | All callers need explicit unit fields; Alineamiento shells default to `stock=purchase` with factor 1.0 |

---

## Implementation steps

### `core/storage/schema.py`

1. Replace the `inventory_item` table DDL:
   - Remove: `unit_id INTEGER NOT NULL`
   - Add: `stock_unit_id INTEGER NOT NULL`, `purchase_unit_id INTEGER NOT NULL`,
     `purchase_to_stock_factor REAL NOT NULL DEFAULT 1.0`
   - Update FK: remove `FOREIGN KEY (unit_id) REFERENCES inventory_unit(id)`;
     add `FOREIGN KEY (stock_unit_id) REFERENCES inventory_unit(id)` and
     `FOREIGN KEY (purchase_unit_id) REFERENCES inventory_unit(id)`
   - Remove the `inventory_unit_equivalence` table DDL block entirely (table 7).
   - Remove `idx_equivalence_inventory_item_id` index.
   - Replace `idx_inventory_item_unit_id` with `idx_inventory_item_stock_unit_id`.

### `core/domain/serialization.py`

2. Update `inventory_item_to_dict` (line ~202): replace `"unit_id": item.unit_id`
   with:
   ```python
   "stock_unit_id": item.stock_unit_id,
   "purchase_unit_id": item.purchase_unit_id,
   "purchase_to_stock_factor": item.purchase_to_stock_factor,
   ```

3. Update `inventory_item_from_dict` (line ~214): replace
   `unit_id=int(_require(d, "unit_id", "inventory_item"))` with:
   ```python
   stock_unit_id=int(_require(d, "stock_unit_id", "inventory_item")),
   purchase_unit_id=int(_require(d, "purchase_unit_id", "inventory_item")),
   purchase_to_stock_factor=float(d.get("purchase_to_stock_factor", 1.0)),
   ```

### `core/storage/persistence.py`

4. Remove `"inventory_unit_equivalence"` from `_SQLITE_ENTITY_TYPES` frozenset.

5. Update `inventory_item` `save` branch (~line 262): change column list and
   bound params to use `stock_unit_id`, `purchase_unit_id`, `purchase_to_stock_factor`.
   The `load` branch needs no change — `SELECT *` + `dict(row)` reads all columns
   automatically once the schema is updated.

6. Remove `elif entity_type == "inventory_unit_equivalence":` blocks in `save`,
   `load`, `delete`, and `list_ids`.

7. In `_get_entity_registries` (~line 549):
   - Remove `dm.InventoryUnitEquivalence: "inventory_unit_equivalence"` from
     `class_to_type`.
   - Remove `"inventory_unit_equivalence": ser.inventory_unit_equivalence_from_dict`
     from `type_to_from_dict`.
   - Remove `"inventory_unit_equivalence": ser.inventory_unit_equivalence_to_dict`
     from `type_to_to_dict`.

8. Remove the `if entity_type == "inventory_unit_equivalence":` branch in
   `_datalake_entity_id` (~line 592).

### `core/operations/normalization.py`

9. Remove `inventory_item_id: Optional[int] = None` parameter from
   `to_base_quantity`, `from_base_quantity`, `to_base_quantity_by_id`,
   `from_base_quantity_by_id`.

10. Remove `equivalence_registry: Optional[Any] = None` parameter from the
    same four functions (currently typed as `Any` from the 11.1 stub).

11. Remove the equivalence lookup branch from each of those four function bodies:
    ```python
    if inventory_item_id is not None and equivalence_registry is not None:
        ...
    ```

12. In `make_resolver` (~line 462): change
    `return (item.id, item.family_id, item.unit_id)` →
    `return (item.id, item.family_id, item.stock_unit_id)`

13. In `normalize_recipe_for_deduction` (~line 369):
    - Remove `equivalence_registry: Optional[Any] = None` from the signature.
    - Remove `inventory_item_id=inventory_item_id` and
      `equivalence_registry=equivalence_registry` kwargs from the
      `to_base_quantity_by_id(...)` call in the fallback path (~line 431–437).

### `core/domain/data_model_utils.py`

14. `validate_recipe_for_deduction` (~line 162): change both occurrences of
    `item.unit_id` → `item.stock_unit_id`.

15. `units_used_by_recipe` (~line 234): change
    `inventory_ids.add(item.unit_id)` → `inventory_ids.add(item.stock_unit_id)`.

16. `create_inventory_item_from_ingredient` (~line 238): update signature from
    `(ingredient, category_id, unit_id_for_inventory, family_id=None)` to
    `(ingredient, category_id, stock_unit_id, purchase_unit_id,
    purchase_to_stock_factor=1.0, family_id=None)`.
    Update the `InventoryItem(...)` construction inside:
    ```python
    return InventoryItem(
        id=0,
        name=ingredient.name.strip(),
        stock_unit_id=stock_unit_id,
        purchase_unit_id=purchase_unit_id,
        purchase_to_stock_factor=purchase_to_stock_factor,
        category_id=category_id,
        family_id=family_id,
    )
    ```

### `gradio_app/sections/alineamiento.py`

17. Update `InventoryItem(...)` construction (~line 441): change
    `unit_id=unit_id` →
    `stock_unit_id=unit_id, purchase_unit_id=unit_id, purchase_to_stock_factor=1.0`
    (Alineamiento creates shells; Estructura enriches the purchase unit later).

### Test files (fix broken tests — do not add new tests)

18. `tests/unit/test_serialization.py`: update `InventoryItem(...)` constructions
    and `inventory_item_to/from_dict` assertions to use `stock_unit_id`,
    `purchase_unit_id`, `purchase_to_stock_factor`. Remove any test constructing
    or asserting on `inventory_unit_equivalence` round-trips.

19. `tests/unit/test_normalization.py`: remove `equivalence_registry` and
    `inventory_item_id` kwargs from any call to `to_base_quantity`,
    `from_base_quantity`, `to_base_quantity_by_id`, `from_base_quantity_by_id`.
    Update `make_resolver` tests if they check the returned `unit_id` field.

20. `tests/unit/test_persistence.py`: update `inventory_item` fixtures to use
    the three new fields. Remove all `inventory_unit_equivalence` entity type
    tests (save/load/delete/list_ids).

21. `tests/unit/test_data_model_utils.py`: update `InventoryItem(...)` constructions
    and assertions on `unit_id` to `stock_unit_id`. Update any call to
    `create_inventory_item_from_ingredient` with the new signature.

22. `tests/unit/test_alignment_agent.py`: update `InventoryItem(...)` constructions
    to use `stock_unit_id` + `purchase_unit_id`.

---

## Post-implementation

Run `reset_session.py` before running any live tests or the Gradio app:
```bash
uv run python scripts/reset_session.py && uv run python scripts/seed_data.py
```
This is required because `CREATE TABLE IF NOT EXISTS` will not alter existing
SQLite sessions — the stale `unit_id` column would cause runtime errors.

---

## Test coverage

- No new tests in this subtask — all new agent/UI tests are in 11.6.
- **Fix existing tests**: the 5 test files listed above broke after 11.1. Must
  be updated as the last step of 11.2 so the full suite stays green.
- No live tests applicable.

---

## Out of scope

- `core/agents/structuring_agent.py` — 11.3
- `gradio_app/sections/estructura.py` — 11.4
- `core/agents/__init__.py` / `core/__init__.py` exports — 11.5
- `tests/unit/test_structuring_agent.py` — 11.6
- Architecture docs — 11.7
- SQLite migration helper for existing sessions — out of scope for MVP

---

## Risks and open questions

1. **Runtime blocker already present:** `persistence.py` `_get_entity_registries()`
   still references `dm.InventoryUnitEquivalence` and the deleted serialization
   functions. These are lazy-evaluated (pass import, crash at runtime). Any call
   to `save_entity_obj` / `load_entity_obj` will fail until step 7 is done.

2. **`normalize_recipe_for_deduction` fallback path:** The fallback branch
   (~lines 431–437) calls `to_base_quantity_by_id(..., inventory_item_id=...,
   equivalence_registry=...)`. After step 9–10 remove those params, the kwargs
   in the call site must also be removed — otherwise a `TypeError` is raised.
   Verify both the signature AND every call site inside that function.

3. **`create_inventory_item_from_ingredient` callers:** Before implementing step 16,
   grep for all callers of this function. Known: `alineamiento.py` (step 17).
   Unknown callers will break silently if missed.

4. **`purchase_to_stock_factor` schema:** No FK needed (it is a float). Verify
   no FK constraint is accidentally added to that column.

### [OPEN] — readiness_kpis test file may also break
**Source:** Validation of subtask 11.2
**Problem:** `tests/unit/test_readiness_kpis.py` (if it exists) likely passes `equivalence_registry` to `compute_readiness_report` or constructs `InventoryItem` with `unit_id`. Not listed in the plan's test files to fix.
**Impact:** Test suite will not be fully green if this file is missed.
**Suggested action:** Grep for `equivalence_registry` and `unit_id` in `tests/unit/test_readiness_kpis.py` during implementation. If hits are found, add it to the test fix list.

---

## Deliverable checklist

`core/storage/schema.py`
- [ ] `inventory_item` table has `stock_unit_id`, `purchase_unit_id`, `purchase_to_stock_factor`; `unit_id` removed
- [ ] `inventory_unit_equivalence` table removed
- [ ] `idx_equivalence_inventory_item_id` index removed
- [ ] `idx_inventory_item_stock_unit_id` index present (renamed from `unit_id`)

`core/domain/serialization.py`
- [ ] `inventory_item_to_dict` emits `stock_unit_id`, `purchase_unit_id`, `purchase_to_stock_factor`
- [ ] `inventory_item_from_dict` reads `stock_unit_id`, `purchase_unit_id`, `purchase_to_stock_factor`

`core/storage/persistence.py`
- [ ] `"inventory_unit_equivalence"` removed from `_SQLITE_ENTITY_TYPES`
- [ ] `inventory_item` save branch uses three new columns
- [ ] `inventory_unit_equivalence` blocks removed from save/load/delete/list_ids
- [ ] `_get_entity_registries` has no `InventoryUnitEquivalence` or equivalence serialization references
- [ ] `_datalake_entity_id` has no `inventory_unit_equivalence` branch

`core/operations/normalization.py`
- [ ] `to_base_quantity`, `from_base_quantity`, `to_base_quantity_by_id`, `from_base_quantity_by_id`: no `equivalence_registry` or `inventory_item_id` params
- [ ] Equivalence lookup branch removed from all four functions
- [ ] `make_resolver` returns `item.stock_unit_id`
- [ ] `normalize_recipe_for_deduction` has no `equivalence_registry` param or kwargs

`core/domain/data_model_utils.py`
- [ ] `validate_recipe_for_deduction` reads `item.stock_unit_id`
- [ ] `units_used_by_recipe` reads `item.stock_unit_id`
- [ ] `create_inventory_item_from_ingredient` signature: `stock_unit_id`, `purchase_unit_id`, `purchase_to_stock_factor`

`gradio_app/sections/alineamiento.py`
- [ ] `InventoryItem(...)` construction uses `stock_unit_id` + `purchase_unit_id` + `purchase_to_stock_factor=1.0`

`tests/`
- [ ] `test_serialization.py` passing
- [ ] `test_normalization.py` passing
- [ ] `test_persistence.py` passing
- [ ] `test_data_model_utils.py` passing
- [ ] `test_alignment_agent.py` passing
- [ ] Full suite green: `uv run python -m pytest tests/`
