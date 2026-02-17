# Implementation plan: Subtask 2.3 — Normalization rules in normalization.py

## Goal

Create `core/normalization.py` with unit conversion and normalization using **InventoryUnit.base_unit_id** and **factor_to_base** (from 2.2). Support converting quantities to/from a unit’s base and handle multi-step chains. Add **(1) base rule of normalization:** each inventory family has a designated base inventory unit so the system knows exactly what quantity and unit to deduct when a recipe is created; **(2) conversion table for unofficial recipe units** (scoop, cucharada, “al gusto”, etc.) so recipe lines can be normalized to a quantity and base unit for inventory deduction; and **(3) normalized recipe:** the list of (inventory_item_id, normalized_quantity, base_unit_id) for one recipe, used to discount inventory when a customer orders that recipe (consumo teórico por platillo). Conversion logic and table application in 2.3; LLM suggestion and UI for the table stay in later tasks.

**Reference:** `.taskmaster/docs/inventory-units-and-equivalences-plan.md` Part 2 and Part 5.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| core/normalization.py module | display_unit_id on InventoryItem (later) |
| to_base_quantity / from_base_quantity for InventoryUnit | Parsing free-text user input (e.g. "2 tazas") |
| Integration with InventoryUnitRegistry (lookup by unit_id) | Who creates/suggests conversion table rows (LLM) and UI for user confirmation (Alignment/Configuration/Structuring) |
| Error handling (missing unit, cycles, invalid quantity) | |
| **Base rule: family → base inventory unit** (see below) | |
| **Recipe-unit conversion table** (design + apply; see below) | |
| **Normalized recipe** (list per recipe for deduction on order; see below) | Actual order/deduction persistence (later) |
| Unit tests for conversions | |

---

## Base rule of normalization (family → base inventory unit)

- **Rule:** Each inventory family has a designated **base inventory unit** used for inventory deduction (e.g. Carnes → g, Verduras/Hierbas → g, Líquidos → ml, Insumos unitarios → pieza). When a recipe is normalized, every ingredient in that family is expressed in that base so the system knows exactly what quantity and inventory unit to deduct.
- **Data:** Add `base_unit_id: Optional[int] = None` to `FamilyInventory` (references InventoryUnit). Templates/Configuration set it per family (e.g. Carnes → g, Líquidos → ml, Insumos unitarios → pza). Implement in 2.2 (data model) or at start of 2.3.
- **In 2.3:** Provide a way to resolve “base unit for this family” (e.g. `get_family_base_unit_id(family_id, family_registry)` or use `FamilyInventory.base_unit_id`). When normalizing an ingredient for deduction, convert quantity to the family’s base unit using existing `to_base_quantity` / `from_base_quantity` and this rule.

---

## Conversion table for unofficial recipe units

- **Goal:** Support conversions from informal recipe units (scoop, cucharada, rodaja, “al gusto”) to a normalized quantity in a base unit (e.g. 1 scoop quinoa → 30 g, 1 cucharada mantequilla → 14 g). The LLM suggests rows; the user confirms; the system stores and applies them to produce the “normalized recipe” (what actually discounts inventory).
- **Required when recipe and inventory use different dimensions:** If the recipe states a unit in one dimension (e.g. "1 tortilla" in pza) but the inventory item is stored in another (e.g. tortillas in kg), the conversion table **must** have an entry (e.g. "1 pza = 0.05 kg" for that item) so that `normalize_recipe_for_deduction` can output a deduction line in kg. Without it, the ingredient is skipped.
- **In scope for 2.3:**
  - **Data shape:** A conversion table keyed by recipe unit and optionally by context (e.g. family_id or inventory_item_id): `(recipe_unit_id, optional family_id or inventory_item_id) → (quantity: float, base_unit_id: int)`. Allow simple entries (recipe_unit_id only) for universal conversions (e.g. 1 scoop = 30 g).
  - **Apply:** Functions in `normalization.py` that, given an ingredient (recipe_unit_id, optional family/item) and this table, return normalized quantity and base_unit_id. Combined with the family base rule, this yields the “normalized recipe” per ingredient.
- **Out of scope for 2.3:** Who creates or suggests table rows (LLM) and where the user confirms them (Alignment/Configuration/Structuring agents or notebooks); that stays in later tasks.

---

## Normalized recipe (for inventory deduction on order)

- **Concept:** The **normalized recipe** for a given recipe is the list of deduction lines: for each ingredient, (inventory_item_id, normalized_quantity, unit_id). Quantity is expressed in **that inventory item’s unit** (InventoryItem.unit_id), not a family-wide base. This allows items in the same family to use different units (e.g. kg for meat, pza for eggs). “Consumo teórico por platillo.”
- **Implementation:** `normalize_recipe_for_deduction` takes a resolver that returns (inventory_item_id, family_id, item_unit_id). It uses the conversion table (recipe unit → quantity, base_unit_id) then converts to item_unit_id when needed, or falls back to converting the ingredient quantity to item_unit_id via the unit chain and optional equivalence_registry. When recipe unit and item unit are in **different dimensions** (e.g. 1 tortilla / pza vs kg), only the conversion table can bridge them; without an entry, the ingredient is skipped. `get_family_base_unit_id` is not used for deduction; it remains available for reporting/aggregation if desired.
- **Out of scope for 2.3:** Persisting orders, applying deductions to inventory, or any UI for “customer ordered X”; 2.3 only produces the normalized recipe list. Those belong in persistence or a later task.

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

### Step 2.3.6 — Family base unit (base rule of normalization)

- **Data (if not in 2.2):** Add `base_unit_id: Optional[int] = None` to `FamilyInventory`; ensure FamilyInventoryRegistry can resolve family by id. Templates set base_unit_id per family (Carnes → g, Líquidos → ml, Insumos unitarios → pza, etc.).
- **Function:** `get_family_base_unit_id(family_id: int, family_registry: FamilyInventoryRegistry, unit_registry: InventoryUnitRegistry) -> Optional[int]`. Return the base_unit_id for the family, or None if not set. Validate that the id is in unit_registry.
- **Usage:** When normalizing an ingredient for deduction, resolve the ingredient’s family (e.g. from InventoryItem.family_id), get family base_unit_id, then use to_base_quantity / from_base_quantity to express quantity in that base.
- **Tests:** Family with base_unit_id set returns that id; family with None returns None; invalid base_unit_id (not in registry) raises or returns None as documented.

### Step 2.3.7 — Recipe-unit conversion table (design + apply)

- **Data shape:** Define a conversion table structure: entries keyed by `(recipe_unit_id, optional family_id, optional inventory_item_id)` mapping to `(quantity: float, base_unit_id: int)`. Allow key with only recipe_unit_id for universal conversions (e.g. 1 scoop = 30 g). Implement as a registry or module-level structure (e.g. `RecipeUnitConversionRegistry` or dict-like) that can be populated by Configuration/Structuring later.
- **Function:** `normalize_recipe_unit_quantity(quantity: float, recipe_unit_id: int, family_id: Optional[int], inventory_item_id: Optional[int], conversion_table, unit_registry: InventoryUnitRegistry) -> tuple[float, int]`. Look up best match (exact context first, then recipe_unit only); return (normalized_quantity, base_unit_id). If no match, raise ValueError or return None as documented.
- **Integration:** Combined with family base rule, support a higher-level “normalize ingredient for deduction” that returns (quantity, base_unit_id) for inventory discount.
- **Tests:** Lookup by recipe_unit_id only; lookup by recipe_unit_id + family_id; missing entry raises or returns None; invalid base_unit_id in table raises.

### Step 2.3.8 — Normalized recipe (list per recipe for deduction on order)

- **Function:** `normalize_recipe_for_deduction(recipe: Recipe, ..., family_registry, unit_registry, conversion_table, resolve_ingredient_to_inventory: Callable or similar) -> list[tuple[int, float, int]]` (or list of a small NamedTuple/dataclass with inventory_item_id, normalized_quantity, base_unit_id). Caller must supply a way to resolve each ingredient to its inventory_item_id and family_id (e.g. from Recipe + restaurant inventory or from Ingredient.inventory_item_id and item.family_id). For each ingredient, use the per-ingredient normalizer (normalize_recipe_unit_quantity + family base) to get (quantity, base_unit_id); append (inventory_item_id, quantity, base_unit_id) to the result list. Document behavior when an ingredient cannot be normalized (skip, raise, or partial result).
- **Output:** The normalized recipe = “consumo teórico por platillo” — exactly what to deduct from inventory when one order of that recipe is placed.
- **Tests:** Recipe with one or more ingredients yields correct list; ingredient without conversion or missing family/base is handled as documented; empty recipe yields empty list.

### Step 2.3.9 — Exports and unit tests

- Export from `core/__init__.py`: `to_base_quantity`, `from_base_quantity`, `to_base_quantity_by_id`, `from_base_quantity_by_id`, `convert_quantity`, `get_family_base_unit_id`, `normalize_recipe_unit_quantity`, `normalize_recipe_for_deduction` (and conversion table type/registry if public).
- **Test file:** `tests/unit/test_normalization.py` with tests for all steps above (known values, round-trip, by_id, errors, convert_quantity, family base, recipe-unit conversion table, normalized recipe).

---

## Checklist before marking 2.3 done

- [ ] core/normalization.py exists and has no syntax/lint errors.
- [ ] to_base_quantity(quantity, unit, registry) works for unit as base and for one- and two-step chains.
- [ ] from_base_quantity(base_quantity, unit, registry) is inverse of to_base; round-trip tests pass.
- [ ] to_base_quantity_by_id and from_base_quantity_by_id work; invalid unit_id raises.
- [ ] Broken chain and cycle raise clear errors.
- [ ] convert_quantity(from_unit_id, to_unit_id, registry) works for same-family units; incompatible units raise.
- [ ] FamilyInventory has base_unit_id (2.2 or 2.3); get_family_base_unit_id(family_id, family_registry, unit_registry) works.
- [ ] Recipe-unit conversion table structure and normalize_recipe_unit_quantity implemented; tests for lookups and missing/invalid data.
- [ ] normalize_recipe_for_deduction(recipe, ...) implemented; returns list of (inventory_item_id, normalized_quantity, base_unit_id) for deduction on order; tests for single/multiple ingredients and edge cases.
- [ ] Exports added in core/__init__.py.
- [ ] tests/unit/test_normalization.py added with good coverage.
- [ ] Item-specific inventory unit equivalence (see below) implemented and tested.

---

## Item-specific inventory unit equivalence

**Goal:** The same unit label (e.g. “Caja”) can have different conversion factors depending on the **inventory item** (e.g. 1 box strawberries = 2 kg, 1 box oranges = 10 kg).

**Data model (`core/data_model.py`):**
- **`InventoryUnitEquivalence`** (frozen dataclass): `unit_id`, `inventory_item_id`, `base_unit_id`, `factor_to_base`. One row per (unit, item) override.
- **`InventoryUnitEquivalenceRegistry`**: `add(equivalence, unit_registry)`, `get(unit_id, inventory_item_id)`, `remove(unit_id, inventory_item_id)`. Validates unit_id and base_unit_id exist in unit_registry; factor_to_base > 0; no duplicate (unit_id, inventory_item_id).

**Normalization (`core/normalization.py`):**
- **`to_base_quantity`** / **`from_base_quantity`** (and **`to_base_quantity_by_id`** / **`from_base_quantity_by_id`**): Optional kwargs `inventory_item_id` and `equivalence_registry`. When both are provided and an equivalence exists for (unit.id, inventory_item_id), use that row for the first conversion step; otherwise use the unit’s built-in `base_unit_id` / `factor_to_base` chain.
- **`normalize_recipe_for_deduction`**: Optional parameter **`equivalence_registry`**. In the fallback path (inventory unit → family base), pass `inventory_item_id` and `equivalence_registry` into `to_base_quantity_by_id` so that “1 box strawberries” and “1 box oranges” yield different normalized quantities when equivalences are registered.

**Design choice:** `InventoryUnit` and `InventoryUnitRegistry` are unchanged. Global default (e.g. 1 Caja = 10 kg) remains on the unit; item-specific overrides live in `InventoryUnitEquivalenceRegistry`. Lookup order: item-specific first, then unit’s chain.

**Caller responsibility when creating items with non-standard units:** When creating a new inventory item whose unit is non-standard (e.g. via `Recipe.add_ingredient(..., unit_requires_equivalence=True, equivalence_base_unit_id=..., equivalence_factor_to_base=...)` or a direct “Add inventory item” flow), the model only validates the equivalence parameters. The caller must: (1) persist the new `InventoryItem` and obtain its assigned id; (2) call `InventoryUnitEquivalenceRegistry.add(InventoryUnitEquivalence(unit_id=..., inventory_item_id=<new_item_id>, base_unit_id=..., factor_to_base=...), unit_registry)` so that normalization can use the item-specific conversion. This is also documented in `Recipe.add_ingredient`’s docstring.

**Tests:** `tests/unit/test_data_model.py` — InventoryUnitEquivalence instantiation; InventoryUnitEquivalenceRegistry add/get/remove, duplicate and invalid unit_id/base_unit_id. `tests/unit/test_normalization.py` — to_base_quantity with inventory_item_id and equivalence_registry (same unit, different items, different factors); normalize_recipe_for_deduction with equivalence_registry (two ingredients, same unit, different item-specific factors).

---

## Optional (later)

- **Applying deductions:** When a customer order is recorded, use the normalized recipe (output of normalize_recipe_for_deduction) to actually subtract quantities from inventory; persistence and order management are out of 2.3.
- **LLM and UI for conversion table:** Populating and editing the recipe-unit conversion table via Alignment/Configuration/Structuring agents and notebooks.
