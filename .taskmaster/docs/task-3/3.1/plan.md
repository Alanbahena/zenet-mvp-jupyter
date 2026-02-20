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

- **Task 2** (data model) must be done: entities (Restaurant, Recipe, Ingredient, InventoryItem, RecipeUnit, InventoryUnit, CategoryRecipe, FamilyInventory, User, InventoryUnitEquivalence) and registries exist and are stable.

---

## Breakdown

### 1. List persisted entity types

- **Entities to persist:** Restaurant, Recipe, Ingredient, InventoryItem, RecipeUnit, InventoryUnit, CategoryRecipe, FamilyInventory, User, **InventoryUnitEquivalence**.
- **Optional (out of scope for MVP):** Conversion table (if distinct from equivalences), registry snapshots (decide and document).
- **Naming:** Use stable `entity_type` strings (e.g. `"restaurant"`, `"recipe"`, `"ingredient"`, `"inventory_unit_equivalence"`) for storage keys and file/table naming.

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

---

## Additional considerations for the contract

To prevent ambiguity and rework in later subtasks, the contract should also address:

### 1. ID generation strategy

- **ID type:** Are IDs integers (auto-increment) or UUIDs/strings?
- **Who assigns:** Does the persistence layer assign IDs (e.g. SQLite auto-increment), or does the application assign before save?
- **Temporary IDs:** What does `id=0` mean for new entities (as mentioned in Recipe docstring)? Document the convention.

**Recommendation:** "IDs are integers; new entities use id=0; persistence layer assigns real id on first save."

### 2. Optional vs required fields

For each entity, provide a complete table showing which fields are required vs optional:

| Field | Type | Required? | Notes |
|-------|------|-----------|-------|
| id | int | Yes | |
| name | str | Yes | |
| address | str | No | Nullable |
| restaurant_type_id | int | No | FK to RestaurantType; nullable |
| notes | str | No | Nullable |

This prevents confusion in 3.2 (JSON: omit key or write `null`?) and 3.3 (from_dict: what's the default?).

### 3. Recipe.ingredients storage

Clarify how `Recipe.ingredients` are stored:
- **Inline list:** `ingredients` is a list of inline dicts (name, quantity, unit_id, inventory_item_id); `Ingredient` is NOT persisted as a separate top-level entity.
- **Dict shape:** Each element has fields matching the `Ingredient` dataclass from the data model.

### 4. Enum and fixed-type representation

For fixed types like `RestaurantType` and `InventoryCategory`:
- **Do NOT persist** as separate entities; they are hardcoded in the data model.
- **Only store IDs** in referencing entities (e.g. `restaurant_type_id` in Restaurant dict).
- **Document:** "RestaurantType, InventoryCategory, etc. are NOT persisted; only their IDs are stored in the referencing entity."

### 5. Registry reconstruction strategy

Choose and document how registries are handled:

**Option A (simpler):**  
"Registries are NOT persisted. On load: load all entities of a type → rebuild the registry in memory (e.g. RecipeRegistry.add for each loaded Recipe)."

**Option B (if needed):**  
"Persist registry state as a separate entity_type (e.g. 'recipe_registry') with a list of IDs in order. On load: restore registry first, then load entities."

**Recommendation:** Option A for MVP simplicity.

### 6. List-of-strings fields

For fields like `Recipe.steps` (list[str]), explicitly document: **"steps: list[str]"** (not list of dicts).

### 7. InventoryUnitEquivalence (in scope)

**InventoryUnitEquivalence** is **in scope**: it is persisted like other entity types. Equivalences are required for non-standard units (caja, bolsa, etc.); without persistence they are lost on restart.
- **Entity type string:** e.g. `"inventory_unit_equivalence"`.
- **Dict shape:** Define in the contract (e.g. `unit_id`, `inventory_item_id`, `base_unit_id`, `factor_to_base`), matching the data model's `InventoryUnitEquivalence` structure.

### 8. JSON null convention

For optional fields, specify:
- **Option A:** Omit the key if the value is `None` (smaller files).
- **Option B:** Always write the key with `null` (explicit schema).

**Recommendation:** Option B for consistency and easier debugging.

### 9. Validation on load

Document validation policy:
- **Strict:** `from_dict` validates that FKs are valid (e.g. `recipe.category_id` exists in CategoryRecipe).
- **Lenient:** `from_dict` does NOT validate FK integrity; caller is responsible.

**Recommendation:** Lenient for MVP—validate at a higher level if needed.
