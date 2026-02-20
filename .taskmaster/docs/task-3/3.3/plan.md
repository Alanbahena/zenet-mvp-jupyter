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
- **Recommendation:** Option B (separate `serialization.py`) for clearer separation: serialization converts objects; persistence stores dicts. Option A is fine for small MVP.

### 2. To-dict (entity → dict)

- For each entity type:
  - Map every persisted field to a key in the dict (names as in 3.1).
  - IDs: use entity’s `id` (or equivalent) for the root; references to other entities as `entity_id` or `recipe_id`, etc.
  - Nested lists: e.g. `Recipe.ingredients` → list of dicts: `[ingredient_to_dict(ing) for ing in recipe.ingredients]`. See Implementation details for pattern.
  - Enums / optional: serialize enum as id (int); **always write optional fields** as `key: None` (JSON `null`), never omit keys.
- **Type hints:** Add for all to_dict functions: `def entity_to_dict(entity: EntityType) -> dict[str, Any]: ...`
- **Key order:** Order doesn't matter for correctness; can match contract examples for readability.
- **No extra keys** beyond the 3.1 contract so storage stays consistent.

### 3. From-dict (dict → entity)

- For each entity type:
  - Read required fields from dict; construct entity instance (e.g. `Recipe(...)`, `Ingredient(...)`).
  - Nested lists: rebuild from list of dicts (e.g. list of Ingredient or equivalent from dicts).
  - References: resolve by id only; from_dict may receive a “lookup” or assume ids are valid (caller loads related entities if needed). Document whether from_dict does lazy resolution or expects pre-loaded registries.
  - **Missing keys:** Use `.get(key, None)` for lenient parsing (missing or null → `None`). For **required** fields, raise `ValueError` if key is missing.
  - Optional fields (`None` vs empty): `steps: list[str] | None` → `null` or missing → `steps=None` (not `[]`); `description` → `null` → `None` (not `""`).
  - Enums: read id (int) from dict; assume valid (no lookup or validation).
- **Type hints:** Add for all from_dict functions: `def entity_from_dict(d: dict[str, Any]) -> EntityType: ...`
- **See Implementation details section below** for concrete patterns and examples.

### 4. Handle all persisted types

- **Restaurant, Recipe, Ingredient, InventoryItem, RecipeUnit, InventoryUnit, CategoryRecipe, FamilyInventory, User, InventoryUnitEquivalence** — implement pair (to_dict, from_dict) for each.
- **Ingredient:** Even though not a top-level entity, implement `ingredient_to_dict` and `ingredient_from_dict` (used by Recipe serialization for the ingredients list).
- **InventoryUnitEquivalence:** No `id` field in dict (composite key is external); from_dict builds object from four fields: `unit_id`, `inventory_item_id`, `base_unit_id`, `factor_to_base`.

### 5. Round-trip consistency

- Ensure for each type: `entity_from_dict(entity_to_dict(entity))` reproduces an equivalent entity (same ids, same values). Unit tests in 3.7 will assert this.

### 6. Exports

- Export all to_dict/from_dict functions (and optional serialization module) from `core/__init__.py` in 3.7; used by DataLake and tests.

---

## Implementation details

### Handling None vs missing keys

- **from_dict strategy (lenient):** Use `d.get("field_name", None)` so both missing keys and `null` values → `None`.
- **Required fields:** Raise `ValueError` if a required field (e.g. `name`) is missing: `if "name" not in d: raise ValueError("Required field 'name' missing")`.
- **Optional fields:** Missing or `null` → `None`; for `steps`, `null` → `None` (not `[]`).

### Recipe.ingredients serialization pattern

**to_dict:**

```python
def recipe_to_dict(recipe: Recipe) -> dict[str, Any]:
    return {
        "id": recipe.id,
        "name": recipe.name,
        "description": recipe.description,
        "steps": recipe.steps,
        "category_id": recipe.category_id,
        "ingredients": [ingredient_to_dict(ing) for ing in recipe.ingredients]
    }
```

**from_dict:**

```python
def recipe_from_dict(d: dict[str, Any]) -> Recipe:
    return Recipe(
        id=d["id"],
        name=d["name"],
        category_id=d["category_id"],
        description=d.get("description"),
        steps=d.get("steps"),
        ingredients=[ingredient_from_dict(ing_d) for ing_d in d.get("ingredients", [])]
    )
```

### Type hints

- Add for all functions: `def entity_to_dict(entity: EntityType) -> dict[str, Any]: ...`
- Add for all functions: `def entity_from_dict(d: dict[str, Any]) -> EntityType: ...`

### InventoryUnitEquivalence (no id field)

**to_dict:**

```python
def inventory_unit_equivalence_to_dict(eq: InventoryUnitEquivalence) -> dict[str, Any]:
    return {
        "unit_id": eq.unit_id,
        "inventory_item_id": eq.inventory_item_id,
        "base_unit_id": eq.base_unit_id,
        "factor_to_base": eq.factor_to_base
    }
```

**from_dict:**

```python
def inventory_unit_equivalence_from_dict(d: dict[str, Any]) -> InventoryUnitEquivalence:
    return InventoryUnitEquivalence(
        unit_id=d["unit_id"],
        inventory_item_id=d["inventory_item_id"],
        base_unit_id=d["base_unit_id"],
        factor_to_base=d["factor_to_base"]
    )
```

No `id` field; composite key `(unit_id, inventory_item_id)` is used by storage layer (3.2/3.5) for filenames/table keys.

### Test coverage in 3.3

- **Minimal:** Add at least round-trip tests for **Recipe** and **Restaurant** in `tests/unit/test_persistence.py` or new `test_serialization.py` to verify conversion logic.
- **Full coverage (3.7):** Round-trip for all entity types, error cases (missing required field, invalid data), nested lists, optional fields.
