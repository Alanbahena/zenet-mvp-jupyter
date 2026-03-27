# Subtask 11.1 — Data model prerequisites

## Goal

Establish the updated data model foundation — two-unit `InventoryItem`, standard unit
chains, and removal of `InventoryUnitEquivalence` — that every subsequent subtask
(schema, serialization, agent, UI) depends on.

- **Prior:** nothing (11.1 is the entry point; Task 10 delivered base `InventoryItem`
  shells with `unit_id` still in place).
- **Next (11.2) needs:** updated `InventoryItem` dataclass, `InventoryUnitEquivalence`
  fully removed from `data_model.py`, and `seed_data.py` with correct unit chains so
  schema/serialization/normalization can be updated against the new shape.

---

## Files to modify

| File | Action | Summary |
|---|---|---|
| `core/domain/data_model.py` | Modify | Two-unit fields on `InventoryItem`; remove `InventoryUnitEquivalence` + `InventoryUnitEquivalenceRegistry`; update `add_ingredient`; annotate `_INVENTORY_UNIT_TEMPLATES` |
| `scripts/seed_data.py` | Modify | Add `base_unit_id` / `factor_to_base` chains to `INVENTORY_UNITS` |
| `tests/unit/test_data_model.py` | Modify | Delete equivalence tests; update `unit_id` assertions to `stock_unit_id` / `purchase_unit_id` |

---

## Key design decisions

| Decision | Rationale |
|---|---|
| Replace `unit_id` with `stock_unit_id`, `purchase_unit_id`, `purchase_to_stock_factor` | `unit_id` was ambiguous; deduction always reads `stock_unit_id` (always standard); purchase factor lives on the item, not a separate entity |
| Remove `InventoryUnitEquivalence` and `InventoryUnitEquivalenceRegistry` entirely | `purchase_to_stock_factor` replaces it; keeping both creates two competing representations |
| Standard unit chains hardcoded in `seed_data.py`, not in templates | Templates use `id=0`; chains require real IDs; seed data has explicit IDs so chains can be wired there |
| Templates annotated with comment only, not chain objects | Cannot wire `kg.base_unit_id = g.id` at template definition time — all template ids are `0` |
| `add_ingredient` shells use `stock_unit_id = purchase_unit_id` | Alineamiento creates thin shells; Estructura enriches them with purchase unit later |

---

## Implementation steps

### `core/domain/data_model.py`

1. Update `InventoryItem` dataclass (`line 406`): remove `unit_id: int`; add three
   fields after `category_id`:
   ```python
   stock_unit_id: int
   purchase_unit_id: int
   purchase_to_stock_factor: float = 1.0
   ```
   Keep `family_id` and `description` as optional fields after the new ones.

2. Verify `update_family_id` and `update_category_id` methods do not reference
   `self.unit_id` — they don't, no changes needed.

3. Update `InventoryItem.add_ingredient` (`line 469`):
   - Remove parameters `unit_requires_equivalence: bool`,
     `equivalence_base_unit_id: Optional[int]`,
     `equivalence_factor_to_base: Optional[float]`
   - Rename parameter `unit_id_for_inventory` → `stock_unit_id_for_inventory`
   - Remove all validation blocks referencing the three removed parameters
     (lines ~528–540)
   - Update the `InventoryItem(...)` construction inside the method:
     ```python
     InventoryItem(
         id=0,
         name=...,
         stock_unit_id=stock_unit_id_for_inventory,
         purchase_unit_id=stock_unit_id_for_inventory,
         purchase_to_stock_factor=1.0,
         category_id=...,
         family_id=...,
     )
     ```
     Shell defaults — Estructura fills in the purchase unit and factor later.

4. Remove `InventoryUnitEquivalence` dataclass (`line 732`) entirely.

5. Remove `InventoryUnitEquivalenceRegistry` class (`line 746`) entirely.

6. Keep `_inventory_unit_cycle` helper (`line 654`) — it is used by
   `InventoryUnitRegistry.add` for `base_unit_id` cycle detection, not by the
   equivalence classes.

7. Update the comment at `_INVENTORY_UNIT_TEMPLATES` (`line 288`): replace
   `"equivalences can be set when applying to registry"` with:
   ```
   # Standard unit chains (kg→g ×1000, L→ml ×1000) are wired in seed_data.py
   # where real IDs are known. Templates intentionally omit chains because all
   # template units use id=0 and base_unit_id cannot reference another id=0 unit.
   ```

8. Verify no remaining `InventoryUnitEquivalence` references anywhere in the file
   after steps 4–5.

9. Update `tests/unit/test_data_model.py`:
   - **DELETE** the 4 `add_ingredient` tests for `unit_requires_equivalence` behavior
     (lines ~368–435 — `test_add_ingredient_requires_equivalence_*`). The validation
     logic they test no longer exists.
   - **DELETE** `TestInventoryUnitEquivalence` class (line ~699) entirely.
   - **DELETE** `TestInventoryUnitEquivalenceRegistry` class (line ~713) entirely.
   - **UPDATE** assertions `new_item.unit_id == 1` at lines ~313, ~365, ~403:
     change to `new_item.stock_unit_id == 1` and add `new_item.purchase_unit_id == 1`.
   This keeps the test suite runnable before 11.2 starts.

### `scripts/seed_data.py`

10. Update `INVENTORY_UNITS` list (`line 85`) with correct chains:
    ```python
    INVENTORY_UNITS = [
        {"id": 1, "name": "gramo",     "symbol": "g",  "base_unit_id": None, "factor_to_base": 1.0},
        {"id": 2, "name": "kilogramo", "symbol": "kg", "base_unit_id": 1,    "factor_to_base": 1000.0},
        {"id": 3, "name": "mililitro", "symbol": "ml", "base_unit_id": None, "factor_to_base": 1.0},
        {"id": 4, "name": "litro",     "symbol": "L",  "base_unit_id": 3,    "factor_to_base": 1000.0},
        {"id": 5, "name": "pieza",     "symbol": "pza","base_unit_id": None, "factor_to_base": 1.0},
    ]
    ```

---

## Test coverage

- No new tests in this subtask — all agent/UI tests are in 11.6.
- **Fix existing tests**: `tests/unit/test_data_model.py` will break after step 1
  due to `InventoryItem(unit_id=...)` and `InventoryUnitEquivalence` references.
  Must be updated as the last step of 11.1 so the suite stays green.
- No live tests applicable.

---

## Out of scope

- `core/storage/schema.py` — 11.2
- `core/domain/serialization.py` — 11.2
- `core/storage/persistence.py` — 11.2
- `core/operations/normalization.py` — 11.2
- `core/domain/data_model_utils.py` — 11.2
- `gradio_app/sections/alineamiento.py` — 11.2
- `core/__init__.py` re-exports — 11.5
- Architecture docs — 11.7

---

## Risks and open questions

1. **Existing tests will break between 11.1 and 11.2**: `alineamiento.py` calls
   `add_ingredient` with the old signature. The app will not run cleanly until 11.2
   is complete. Do not run the Gradio app between 11.1 and 11.2.

2. **`_INVENTORY_UNIT_TEMPLATES` chain gap**: Sessions created via Configuración will
   have standard units with `base_unit_id=None` (no chains). Only seeded sessions
   (via `seed_data.py`) will have correct chains. Acceptable for MVP — Estructura
   uses seeded sessions. Note this in the template comment (step 7).

3. **`add_ingredient` callers**: any caller passing `unit_requires_equivalence=True`
   will break after step 3. Known location: `alineamiento.py`. Covered in 11.2 —
   do not fix here.

4. **Other test files will break after 11.1**: Five test files reference `unit_id`
   or `InventoryUnitEquivalence` and will fail after the data model changes:
   - `tests/unit/test_serialization.py` (~18 hits)
   - `tests/unit/test_normalization.py` (~28 hits)
   - `tests/unit/test_persistence.py` (~25 hits)
   - `tests/unit/test_alignment_agent.py` (~5 hits)
   - `tests/unit/test_data_model_utils.py` (~7 hits)
   These are fixed as part of their corresponding source file updates in 11.2.
   Do not attempt to fix them in 11.1.

---

## Deliverable checklist

`core/domain/data_model.py`
- [ ] `InventoryItem` has `stock_unit_id`, `purchase_unit_id`, `purchase_to_stock_factor`; `unit_id` removed
- [ ] `InventoryUnitEquivalence` dataclass removed
- [ ] `InventoryUnitEquivalenceRegistry` class removed
- [ ] `add_ingredient` has no `unit_requires_equivalence`, `equivalence_base_unit_id`, `equivalence_factor_to_base` parameters
- [ ] `add_ingredient` constructs `InventoryItem` with `stock_unit_id` + `purchase_unit_id` + `purchase_to_stock_factor=1.0`
- [ ] `_INVENTORY_UNIT_TEMPLATES` comment updated to reflect chain wiring constraint
- [ ] No remaining `InventoryUnitEquivalence` references in file
- [ ] `tests/unit/test_data_model.py` updated and passing

`scripts/seed_data.py`
- [ ] `g`: `base_unit_id=None, factor_to_base=1.0`
- [ ] `kg`: `base_unit_id=1, factor_to_base=1000.0`
- [ ] `ml`: `base_unit_id=None, factor_to_base=1.0`
- [ ] `L`: `base_unit_id=3, factor_to_base=1000.0`
- [ ] `pza`: `base_unit_id=None, factor_to_base=1.0`
