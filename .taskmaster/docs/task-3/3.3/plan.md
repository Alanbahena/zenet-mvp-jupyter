# Implementation plan: Subtask 3.3 — Entity ↔ dict serialization

## Goal

Implement functions to convert core entities (Recipe, Ingredient, Restaurant, InventoryItem, RecipeUnit, InventoryUnit, CategoryRecipe, FamilyInventory, User) **to** and **from** plain dicts. These dicts follow the contract from 3.1 and are used by JsonStorage (3.2), SqliteStorage (3.5), and DataLake (3.6) when saving or loading entity objects.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| To-dict and from-dict per entity type | Persistence scope decisions (3.1) |
| Nested lists (e.g. Recipe.ingredients as list of dicts); optional/enum fields | Storage backends (3.2, 3.5) |
| Single source of truth: use `core.data_model` types | Schema migrations |

---

## Dependencies

- **3.1** — Dict shape and field names are defined there; implement exactly that contract.
- **Task 2** — Data model types (Restaurant, Recipe, Ingredient, etc.) from `core.data_model`.

---

## Breakdown

### 1. Module location

- **Option A:** All in `core/persistence.py` (e.g. `recipe_to_dict`, `recipe_from_dict`, …).
- **Option B:** Separate `core/serialization.py` with to_dict/from_dict only; `persistence.py` imports and uses it.
- **Naming:** Prefer `entity_to_dict` / `entity_from_dict` (e.g. `recipe_to_dict`, `recipe_from_dict`) for clarity.

### 2. To-dict (entity → dict)

- For each entity type:
  - Map every persisted field to a key in the dict (names as in 3.1).
  - IDs: use entity’s `id` (or equivalent) for the root; references to other entities as `entity_id` or `recipe_id`, etc.
  - Nested lists: e.g. `Recipe.ingredients` → list of dicts, each element serialized with the same convention (id, quantity, unit_id, …).
  - Enums / optional: serialize enum as id or string; omit optional fields if None or document default.
- **No extra keys** beyond the 3.1 contract so storage stays consistent.

### 3. From-dict (dict → entity)

- For each entity type:
  - Read required fields from dict; construct entity instance (e.g. `Recipe(...)`, `Ingredient(...)`).
  - Nested lists: rebuild from list of dicts (e.g. list of Ingredient or equivalent from dicts).
  - References: resolve by id only; from_dict may receive a “lookup” or assume ids are valid (caller loads related entities if needed). Document whether from_dict does lazy resolution or expects pre-loaded registries.
  - Optional/enum: use default if key missing; parse enum from string/id.

### 4. Handle all persisted types

- **Restaurant, Recipe, Ingredient, InventoryItem, RecipeUnit, InventoryUnit, CategoryRecipe, FamilyInventory, User** — implement pair (to_dict, from_dict) for each.
- If 3.1 added equivalences or conversion table, add serialization for those too.

### 5. Round-trip consistency

- Ensure for each type: `entity_from_dict(entity_to_dict(entity))` reproduces an equivalent entity (same ids, same values). Unit tests in 3.7 will assert this.

### 6. Exports

- Export all to_dict/from_dict functions (and optional serialization module) from `core/__init__.py` in 3.7; used by DataLake and tests.
