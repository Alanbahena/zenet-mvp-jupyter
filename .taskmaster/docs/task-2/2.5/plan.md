# Implementation plan: Subtask 2.5 — Data model integration utilities

## Goal

Implement **core/data_model_utils.py** to integrate `core/data_model.py`, `core/normalization.py`, and `core/taxonomy.py`. Provide: (1) conversion between normalized and display formats, (2) validation that combines entity and normalization rules, (3) helpers for common operations across entity types, (4) factory methods for related entities. No changes to existing core modules except exporting the new utilities from `core/__init__.py`.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| New file `core/data_model_utils.py` | Changing `data_model.py`, `normalization.py`, or `taxonomy.py` logic |
| Functions that take registries and return values or raise | Persistence (task 3); agents/notebooks (later tasks) |
| Unit tests in `tests/unit/test_data_model_utils.py` | Full integration/E2E tests |
| Exports from `core/__init__.py` | Parsing free-text user input (e.g. "2 tazas") beyond simple numeric+unit |

---

## Dependencies

Subtask 2.5 depends on 2.2 (entity relationships and registries), 2.3 (normalization), and 2.4 (taxonomy). All are implemented; no dependency block.

---

## Link to taxonomy (core/taxonomy.py)

The goal mentions integrating **data_model**, **normalization**, and **taxonomy**. The current 2.5 implementation integrates data_model and normalization only; it does not import or use taxonomy. Taxonomy remains a separate semantic layer that callers populate and keep in sync with registries (see subtask-2.4-plan.md). This is intentional: format, validation, and resolver helpers do not require taxonomy. Optional future addition: helpers that accept a taxonomy (e.g. `get_related_inventory_items_for_display(item_id, inventory_taxonomy, item_registry)`) for UI or agents.

---

## Step 2.5.1 — Module skeleton and format: normalized → display

- **Deliverable:** Create `core/data_model_utils.py` with minimal imports from `data_model` and `normalization`.
- **Functions:**
  - **`format_deduction_line_for_display(line, unit_registry, item_registry) -> str`** — Given a `(inventory_item_id, quantity, unit_id)`, resolve item name and unit symbol; return a string like `"0.5 kg Leche"`. If item or unit is missing, return a fallback string with raw id/quantity/unit_id.
  - **`format_ingredient_for_display(ingredient, recipe_unit_registry) -> str`** — Return `"{quantity} {unit_symbol} {ingredient.name}"` (e.g. `"250 g Harina"`). Look up symbol via `recipe_unit_registry.get(ingredient.unit_id)`; if unit missing, use unit_id as fallback.
- **Tests:** Valid line/item/unit; missing unit or item (fallback).

---

## Step 2.5.2 — Format: recipe ingredients to display structures (optional display → normalized)

- **Functions:**
  - **`ingredients_to_display(recipe, recipe_unit_registry, inventory_item_registry=None) -> list[dict]`** — Return a list of dicts suitable for UI: `name`, `quantity`, `unit_symbol`, `unit_id`, and optionally `inventory_item_name` when registry is given. Resolve unit symbol from recipe_unit_registry; optionally resolve inventory item name from `inventory_item_registry.get(ing.inventory_item_id)` or `get_by_name(ing.name)`.
  - **`parse_quantity_and_unit(quantity_str, unit_registry) -> tuple[float, int]`** — Parse strings like `"250 g"` to `(quantity, unit_id)` using registry symbol lookup. Single token unit only; raise if unit missing or symbol not found. Document limitations.
- **Tests:** Recipe with one/multiple ingredients; missing unit; with/without inventory registry. Parse valid "250 g", single number raises, unknown symbol raises.

---

## Step 2.5.3 — Validation combining entity and normalization rules

- **Functions:**
  - **`validate_recipe_for_deduction(recipe, item_registry, unit_registry, conversion_table, family_registry) -> list[str]`** — For each ingredient, resolve to inventory item (by `inventory_item_id` or `get_by_name`); check unit exists in registry. Return a list of human-readable issues (e.g. `"Ingredient 'X' has no inventory item"`, `"Unit id 99 not in registry"`). Empty list means valid.
  - **`validate_ingredient_with_registries(ingredient, valid_recipe_unit_ids) -> list[str]`** — Entity-level checks only: name non-empty, quantity > 0 and finite, `unit_id in valid_recipe_unit_ids`. Return list of error messages; empty if valid.
- **Tests:** Recipe with all valid ingredients → empty list; recipe with unresolved ingredient → non-empty list. Ingredient valid/invalid cases (empty name, bad quantity, invalid unit_id).

---

## Step 2.5.4 — Helpers across entity types

- **Functions:**
  - **`resolve_ingredient_to_inventory_item(ingredient, item_registry) -> Optional[InventoryItem]`** — Return `item_registry.get(ingredient.inventory_item_id)` if set and found; else `item_registry.get_by_name(ingredient.name)`. Return `None` if not found.
  - **`make_resolver_from_item_registry(item_registry)`** — Return the result of `make_resolver(lambda ing: resolve_ingredient_to_inventory_item(ing, item_registry))` so that `normalize_recipe_for_deduction(..., resolve_ingredient_to_inventory=make_resolver_from_item_registry(reg))` works without the caller building the lambda.
  - **`units_used_by_recipe(recipe, recipe_unit_registry, item_registry, inventory_unit_registry) -> tuple[set[int], set[int]]`** — Return `(recipe_unit_ids, inventory_unit_ids)` where recipe_unit_ids are from `ing.unit_id` and inventory_unit_ids are from resolved inventory items’ `unit_id`.
- **Tests:** resolve by id, by name, missing → None. make_resolver_from_item_registry used with normalize_recipe_for_deduction. units_used_by_recipe with one ingredient and with unresolved ingredient.

---

## Step 2.5.5 — Factory methods for related entities

- **Functions:**
  - **`create_inventory_item_from_ingredient(ingredient, category_id, unit_id_for_inventory, family_id=None) -> InventoryItem`** — Return `InventoryItem(id=0, name=ingredient.name.strip(), unit_id=unit_id_for_inventory, category_id=category_id, family_id=family_id)`. No registry or validation inside; callers validate `category_id` and `unit_id_for_inventory`.
  - **`build_ingredient(name, quantity, unit_id, inventory_item_id=None) -> Ingredient`** — Convenience wrapper returning `Ingredient(...)` with the given fields.
- **Tests:** create_inventory_item_from_ingredient returns item with correct fields. build_ingredient returns correct Ingredient; default inventory_item_id None.

---

## Step 2.5.6 — Exports and tests

- **Exports:** In `core/__init__.py`, add imports from `core.data_model_utils` for all public functions and add them to `__all__`: `format_deduction_line_for_display`, `format_ingredient_for_display`, `ingredients_to_display`, `parse_quantity_and_unit`, `validate_recipe_for_deduction`, `validate_ingredient_with_registries`, `resolve_ingredient_to_inventory_item`, `make_resolver_from_item_registry`, `units_used_by_recipe`, `create_inventory_item_from_ingredient`, `build_ingredient`.
- **Test file:** `tests/unit/test_data_model_utils.py` with tests for each function: happy path, missing registry entries, empty recipe, and edge cases as described per step.

---

## Implementation order

1. Step 2.5.1 — Skeleton + format deduction line + format ingredient.
2. Step 2.5.2 — ingredients_to_display + parse_quantity_and_unit.
3. Step 2.5.3 — validate_recipe_for_deduction + validate_ingredient_with_registries.
4. Step 2.5.4 — resolve_ingredient_to_inventory_item, make_resolver_from_item_registry, units_used_by_recipe.
5. Step 2.5.5 — create_inventory_item_from_ingredient + build_ingredient.
6. Step 2.5.6 — Exports and test file; run full unit suite.

---

## Checklist before marking 2.5 done

- [x] `core/data_model_utils.py` exists with no syntax/lint errors.
- [x] Format: normalized → display (deduction line, ingredient) implemented and tested.
- [x] ingredients_to_display and parse_quantity_and_unit implemented and tested.
- [x] Validation: validate_recipe_for_deduction and validate_ingredient_with_registries implemented and tested.
- [x] Helpers: resolve_ingredient_to_inventory_item, make_resolver_from_item_registry, units_used_by_recipe implemented and tested.
- [x] Factory: create_inventory_item_from_ingredient and build_ingredient implemented and tested.
- [x] Exports added in `core/__init__.py`; `tests/unit/test_data_model_utils.py` has coverage for all public functions.
- [x] Full unit test suite passes.

---

## When to use data_model_utils

- **Display:** Use `format_deduction_line_for_display`, `format_ingredient_for_display`, and `ingredients_to_display` when showing deduction lines or recipe ingredients in UI or reports.
- **Validation:** Use `validate_ingredient_with_registries` before adding an ingredient (e.g. in forms); use `validate_recipe_for_deduction` before running deduction or to show issues to the user.
- **Resolvers:** Use `resolve_ingredient_to_inventory_item` and `make_resolver_from_item_registry` when calling `normalize_recipe_for_deduction` with an `InventoryItemRegistry`.
- **Factories:** Use `create_inventory_item_from_ingredient` when creating a new inventory item from an ingredient outside `Recipe.add_ingredient`; use `build_ingredient` for consistent Ingredient construction.

Consider updating `docs/Architecture/architecture-data-model.md` to reference `core.data_model_utils` and these use cases.

---

## Optional (later)

- **Deeper validation** in `validate_recipe_for_deduction`: check that normalization would succeed (e.g. conversion table or same-dimension path) and report which ingredients would be skipped.
- **Parsing** richer input (e.g. "2 tazas de harina") with unit and ingredient resolution; currently limited to "quantity unit_symbol" with one token.
- **`validate_inventory_item_with_registries(item, valid_category_ids, valid_unit_ids, valid_family_ids=None) -> list[str]`** — Entity-level validation for an InventoryItem (name non-empty, category_id and unit_id in valid sets, optional family_id). Useful when creating items from the inventory section before calling `item_registry.add()`.
- **`format_deduction_lines_for_display(lines, unit_registry, item_registry) -> list[str]`** — Batch version: map each DeductionLine to a display string (convenience for "consumo teórico" report or UI).
- **Taxonomy helpers** — e.g. get related inventory items for an ingredient or item for display (requires passing InventoryTaxonomy or IngredientTaxonomy into data_model_utils).
