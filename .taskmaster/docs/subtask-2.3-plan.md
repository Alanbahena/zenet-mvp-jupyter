# Implementation plan: Subtask 2.3 — Normalization rules in normalization.py

## Goal

Create `core/normalization.py` with unit conversion and normalization using **InventoryUnit.base_unit_id** and **factor_to_base** (from 2.2). Support converting quantities to/from a unit’s base and handle multi-step chains. No new entities; conversion logic only.

**Reference:** `.taskmaster/docs/inventory-units-and-equivalences-plan.md` Part 2 and Part 5.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| core/normalization.py module | RecipeUnit equivalences (defer unless RecipeUnit gets base_unit_id) |
| to_base_quantity / from_base_quantity for InventoryUnit | Cross recipe ↔ inventory conversion (later) |
| Integration with InventoryUnitRegistry (lookup by unit_id) | display_unit_id on InventoryItem (later) |
| Error handling (missing unit, cycles, invalid quantity) | Parsing free-text user input (e.g. "2 tazas") |
| Unit tests for conversions | |

---

## Breakdown (implementation order)

### Step 2.3.1 — Create core/normalization.py and to_base_quantity

- **Deliverable:** New file `core/normalization.py`.
- **Function:** `to_base_quantity(quantity: float, unit: InventoryUnit, registry: InventoryUnitRegistry) -> float`.
  - If `unit.base_unit_id is None`: return `quantity * unit.factor_to_base` (unit is its own base; factor is 1.0 for standard bases).
  - Else: get base unit from registry; recursively convert: `quantity * unit.factor_to_base` is in base unit’s terms; if base unit has its own base, recurse with that unit and the registry.
  - Effect: walk the chain from `unit` toward the root (base_unit_id is None), multiplying factors; return `quantity * product(factor_to_base along chain)`.
- **Dependencies:** `InventoryUnit`, `InventoryUnitRegistry` from `core.data_model`.
- **Tests:** Unit with no base (factor 1.0) returns quantity; unit with base (e.g. kg, factor 1000, base = g) returns quantity * 1000.

### Step 2.3.2 — Implement from_base_quantity

- **Function:** `from_base_quantity(base_quantity: float, unit: InventoryUnit, registry: InventoryUnitRegistry) -> float`.
  - Convert a quantity expressed in the **base** of the unit’s family into the given unit.
  - Inverse of to_base: divide by the product of factor_to_base along the chain from base to unit (or multiply by 1 / product).
  - Example: base_quantity 500 (grams), unit = kg (factor_to_base 1000, base = g) → 500 / 1000 = 0.5 kg.
- **Tests:** Round-trip: from_base_quantity(to_base_quantity(q, u, reg), u, reg) == q (within float tolerance). Test with chained units (e.g. caja → kg → g).

### Step 2.3.3 — Overloads by unit_id and registry

- **Convenience:** `to_base_quantity_by_id(quantity: float, unit_id: int, registry: InventoryUnitRegistry) -> float`.
  - Look up unit by `registry.get(unit_id)`; if None, raise ValueError("unit_id not found").
  - Call `to_base_quantity(quantity, unit, registry)`.
- **Same for:** `from_base_quantity_by_id(base_quantity: float, unit_id: int, registry: InventoryUnitRegistry) -> float`.
- **Tests:** Pass valid unit_id; pass invalid unit_id and expect ValueError.

### Step 2.3.4 — Error handling and edge cases

- **Missing unit in chain:** If `registry.get(unit.base_unit_id)` is None mid-chain, raise ValueError (broken chain).
- **Cycle:** 2.2 already prevents cycles on add; normalization can defensively detect cycle (e.g. set of visited ids) and raise ValueError.
- **Invalid quantity:** Reject inf/nan if desired (optional); document behavior for negative quantity (either reject or allow for deductions).
- **Tests:** Broken chain (mock registry returning None); cycle (if testable with a temporary registry); negative/zero quantity as documented.

### Step 2.3.5 — Convert between two arbitrary units (same family)

- **Function:** `convert_quantity(quantity: float, from_unit_id: int, to_unit_id: int, registry: InventoryUnitRegistry) -> float`.
  - Convert quantity from from_unit to to_unit when both units share the same base (same “family”). Algorithm: to_base_quantity(quantity, from_unit, registry) → base_qty; then from_base_quantity(base_qty, to_unit, registry). If the two units have different bases (different families), raise ValueError (incompatible units).
  - **Same family:** The root base (unit with base_unit_id None) reached from from_unit must be the same as the root base reached from to_unit.
- **Tests:** 0.5 kg → g = 500; 1 caja (10 kg) → g = 10000; incompatible units (e.g. kg vs L) raise.

### Step 2.3.6 — Exports and unit tests

- Export from `core/__init__.py`: `to_base_quantity`, `from_base_quantity`, `to_base_quantity_by_id`, `from_base_quantity_by_id`, `convert_quantity` (or a single normalization namespace).
- **Test file:** `tests/unit/test_normalization.py` with tests for all steps above (known values, round-trip, by_id, errors, convert_quantity).

---

## Checklist before marking 2.3 done

- [ ] core/normalization.py exists and has no syntax/lint errors.
- [ ] to_base_quantity(quantity, unit, registry) works for unit as base and for one- and two-step chains.
- [ ] from_base_quantity(base_quantity, unit, registry) is inverse of to_base; round-trip tests pass.
- [ ] to_base_quantity_by_id and from_base_quantity_by_id work; invalid unit_id raises.
- [ ] Broken chain and cycle raise clear errors.
- [ ] convert_quantity(from_unit_id, to_unit_id, registry) works for same-family units; incompatible units raise.
- [ ] Exports added in core/__init__.py.
- [ ] tests/unit/test_normalization.py added with good coverage.

---

## Optional (later)

- **RecipeUnit equivalences:** If RecipeUnit gets base_unit_id and factor_to_base, add similar functions for RecipeUnitRegistry in normalization.py or a separate section.
- **Cross recipe ↔ inventory:** Convert ingredient (recipe unit) quantity to inventory unit for matching; can use convert_quantity if both registries share a common base or a bridge is defined later.
