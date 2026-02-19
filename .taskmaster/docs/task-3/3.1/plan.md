# Implementation plan: Subtask 3.1 — Persistence scope and serialization contract

## Goal

Define which entities from the data model (task 2) are persisted and the exact JSON-serializable dict shape for each. Document how relationships are represented (by id). This is the contract so 3.2 (JsonStorage), 3.3 (serialization), and 3.4 (SQLite schema) stay aligned. No implementation code in core yet.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| List of persisted entity types | Actual serialization code (3.3) |
| Dict shape per type: field names, types, id references | Storage implementation (3.2, 3.5) |
| Handling of lists (e.g. Recipe.ingredients) and optional/enum fields | Schema migrations (deferred) |
| Document in code or short spec under `task-3/3.1/` | |

---

## Dependencies

- **Task 2** (data model) must be done: entities (Restaurant, Recipe, Ingredient, InventoryItem, RecipeUnit, InventoryUnit, CategoryRecipe, FamilyInventory, User) and registries exist and are stable.

---

## Breakdown

### 1. List persisted entity types

- **Entities to persist:** Restaurant, Recipe, Ingredient, InventoryItem, RecipeUnit, InventoryUnit, CategoryRecipe, FamilyInventory, User.
- **Optional:** InventoryUnitEquivalence, conversion table, or registry snapshots (decide and document).
- **Naming:** Use stable `entity_type` strings (e.g. `"restaurant"`, `"recipe"`, `"ingredient"`) for storage keys and file/table naming.

### 2. Dict shape per entity

- For each type, define:
  - **Fields:** Name, type (str, int, float, bool, list, dict), and whether optional.
  - **References:** Store FKs as id only (e.g. `recipe_id`, `unit_id`); no nested full objects in the canonical dict.
  - **Lists:** e.g. Recipe.ingredients → list of dicts (each with id/name, quantity, unit_id, etc. as per data model).
  - **Enums / optional:** e.g. RestaurantType → store as id or string; document default for optional fields.

### 3. Relationship representation

- Document: parent-child and many-to-one links are stored by id (e.g. ingredient.recipe_id, inventory_item.family_id).
- Document: how to reconstruct registries (e.g. load all recipes then build RecipeRegistry) vs persisting registry snapshots (if any).

### 4. Deliverable

- **Artifact:** Short spec (markdown or comment block) under `.taskmaster/docs/task-3/3.1/` or in this plan, so 3.2, 3.3, 3.4 can implement against it.
- **No code** in `core/` for 3.1.
