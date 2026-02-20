# Subtask 2.2 — Additional validation suggestions (breakdown)

Below are validations that are **not yet explicit** in the 2.2 plan. Each is grouped by area, with rationale and a recommendation (add to plan / optional / skip). No changes have been made to the plan file yet; use this to decide what to add.

---

## 1. Ingredient

| Suggestion | Rationale | Recommendation |
|------------|-----------|----------------|
| **Ingredient.name non-empty** | Empty or whitespace-only name would create useless ingredients and InventoryItems with empty names. | **Add:** Require `ingredient.name` to be non-empty after stripping whitespace; raise `ValueError` otherwise. |
| **Ingredient.quantity finite** | `quantity > 0` is already required; `math.inf`, `-math.inf`, and `math.nan` are not sensible. | **Optional:** Reject non-finite floats (e.g. `not math.isfinite(quantity)`); raise `ValueError`. Low cost, avoids subtle bugs. |

---

## 2. Recipe and add_ingredient

| Suggestion | Rationale | Recommendation |
|------------|-----------|----------------|
| **valid_inventory_unit_ids required when creating InventoryItem** | Plan says validate `unit_id_for_inventory in valid_inventory_unit_ids`, but if the caller passes `unit_id_for_inventory` and omits `valid_inventory_unit_ids`, we cannot validate. | **Add:** When `category_id` is provided (so we may create a new InventoryItem), require `valid_inventory_unit_ids` to be passed; if `unit_id_for_inventory` is provided and `valid_inventory_unit_ids` is `None`, raise `ValueError`. |
| **Recipe.category_id when set** | When a Recipe is created or `update_category_id(category_id)` is used, category_id should be in valid_category_recipe_ids. | **Add:** Document that any code that sets `Recipe.category_id` must validate against the CategoryRecipe registry’s `valid_category_recipe_ids()`; if a setter method is provided in 2.2, it must accept a `valid_ids: set[int]` or get it from context and raise if `category_id not in valid_ids`. |
| **remove_ingredient(int) index bounds** | Plan says “bounds check” but not whether to raise or return None. | **Add:** When argument is `int` and out of range (e.g. index < 0 or >= len(ingredients)), raise `IndexError` (or `ValueError`) with a clear message; document in 3.2. |

---

## 3. InventoryItem (when created from add_ingredient)

| Suggestion | Rationale | Recommendation |
|------------|-----------|----------------|
| **family_id when provided** | add_ingredient accepts optional `family_id`. If provided, it should reference a valid FamilyInventory id. | **Add:** When `family_id` is not None, validate `family_id in valid_family_inventory_ids` (caller must pass the set or we get it from registry); otherwise raise `ValueError`. If no set is available in the method, document “caller must ensure family_id is valid when provided.” |
| **category_id in valid set** | Plan says “validate against allowed ids if a set is provided.” We could require the caller to pass valid_category_ids when creating an InventoryItem. | **Optional:** Explicitly require a set of valid InventoryCategory ids (e.g. from a fixed list or small registry) and validate `category_id in valid_category_ids` when creating InventoryItem; raise if not. Plan already implies this; making “valid_category_ids required when category_id provided” explicit is enough. |

---

## 4. Registries (add)

| Suggestion | Rationale | Recommendation |
|------------|-----------|----------------|
| **Duplicate id on add** | Plan says “optionally reject duplicate id” for RecipeUnit. Without this, two units with same id can exist. | **Add:** All registries (RecipeUnit, InventoryUnit, CategoryRecipe, FamilyInventory): when adding, **reject duplicate `id`** (raise `ValueError`). Make it required, not optional. |
| **Duplicate symbol/name on add** | Duplicate symbol (e.g. two “g”) or duplicate category/family name can cause confusion. | **Add:** RecipeUnitRegistry and InventoryUnitRegistry: reject duplicate `symbol` (case-insensitive or exact, document which). CategoryRecipeRegistry and FamilyInventoryRegistry: reject duplicate `name` (case-insensitive or exact). Raise `ValueError` with a clear message. |
| **Unit/entity name/symbol non-empty** | Adding a RecipeUnit or InventoryUnit with empty name/symbol would create useless entries. | **Add:** When adding a unit or category/family, require `name` and `symbol` (for units) to be non-empty after stripping; raise `ValueError` otherwise. |

---

## 5. Registries (remove) — category and family

| Suggestion | Rationale | Recommendation |
|------------|-----------|----------------|
| **Remove category in use** | If we remove a CategoryRecipe that is still referenced by at least one Recipe, we leave dangling references. Same pattern as “remove unit in use.” | **Add:** When `remove_category_recipe(category_id)` is called, if any Recipe has `category_id == category_id`, **do not remove**; raise `ValueError` (“Category is in use by one or more recipes”). Document that the registry needs a way to check usage (e.g. caller passes a list of recipes, or a callback). |
| **Remove family in use** | Same for FamilyInventory: if any InventoryItem has that `family_id`, block removal. | **Add:** When `remove_family_inventory(family_id)` is called, if any InventoryItem has `family_id == family_id`, **do not remove**; raise `ValueError` (“Family is in use by one or more inventory items”). Same note: registry or caller must be able to check usage. |

**Note:** For “remove category/family in use,” the registry typically does not hold all Recipe or InventoryItem instances. So either: (a) the remove method accepts an optional “in-use” checker (e.g. `recipes: list[Recipe]` or `is_category_in_use(category_id) -> bool`), or (b) the caller is responsible for checking before calling remove, and the plan documents that. Option (a) keeps validation in one place; option (b) is simpler. Recommend **document** in plan: “When removing a category (or family), caller must ensure no Recipe (or InventoryItem) references it; otherwise data integrity is the caller’s responsibility.” Or implement a check if the registry has access to recipes/items (e.g. passed in or from a context). So: **Add** the rule (do not remove if in use); **document** how the check is done (caller passes dependent collections, or registry holds refs).

---

## 6. User

| Suggestion | Rationale | Recommendation |
|------------|-----------|----------------|
| **User.role in allowed set** | Plan uses `role == "admin"` but doesn’t restrict role values. Arbitrary strings could break assumptions later. | **Add:** Define allowed roles (e.g. `{"admin", "user"}` or product list). On `add_user` and `update_user` (when role is updated), validate `role in allowed_roles`; raise `ValueError` otherwise. Document allowed roles in the plan. |
| **User email format** | Plan says “Validate email format and uniqueness if required.” | **Add:** Validate email format (e.g. basic regex or `email-validator`); raise `ValueError` if invalid. Uniqueness: document that it is the caller’s or registry’s responsibility (e.g. UserRegistry checks before add). |
| **User name and email non-empty** | Empty name or email is not useful and can break UI or downstream logic. | **Add:** On add_user (and update_user when name/email are updated), require non-empty name and email after stripping; raise `ValueError` otherwise. |

---

## 7. Restaurant

| Suggestion | Rationale | Recommendation |
|------------|-----------|----------------|
| **Restaurant.name non-empty** | Plan doesn’t update name in 2.2 (only address, restaurant_type_id, notes). If a future method or constructor validates name, good to document. | **Optional:** If 2.2 adds any way to set Restaurant.name, require non-empty. Otherwise leave to 2.1/persistence; no change needed. |
| **Restaurant id > 0 or id valid** | Not typically validated for in-memory entities; id can be 0 for “unsaved.” | **Skip.** |

---

## 8. Recipe and InventoryItem (entity-level)

| Suggestion | Rationale | Recommendation |
|------------|-----------|----------------|
| **Recipe.name / description / steps** | Empty name might be invalid; empty steps list might be allowed for “draft.” | **Optional:** If 2.2 adds Recipe creation or update methods, require `name` non-empty; allow `description` and `steps` empty. Otherwise defer. |
| **InventoryItem.name when created** | Comes from ingredient.name; validating ingredient.name covers this. | **Covered** by Ingredient.name validation above. |

---

## 9. Summary table (what to add to the plan)

| # | Validation | Section to add / update | Priority |
|---|-------------|--------------------------|----------|
| 1 | Ingredient.name non-empty (after strip) | 4.1 Ingredient | High |
| 2 | Ingredient.quantity finite (optional) | 4.1 | Low |
| 3 | valid_inventory_unit_ids required when category_id provided | 3.1, 4.2, 7 | High |
| 4 | Recipe.category_id validated when set (valid_category_recipe_ids) | 3d, 4 | High |
| 5 | remove_ingredient(int) index out of range → IndexError/ValueError | 3.2, 7 | High |
| 6 | family_id when provided must be in valid_family_inventory_ids | 3.1, 4.2, 5 | High |
| 7 | Registries: reject duplicate id on add | 3b.1, 3b.2, 3d.1, 3d.2 | High |
| 8 | Registries: reject duplicate symbol (units) / name (category, family) on add | 3b.1, 3b.2, 3d.1, 3d.2 | High |
| 9 | Unit/category/family: name and symbol non-empty on add | 3b, 3d | Medium |
| 10 | remove_category_recipe / remove_family_inventory: block if in use | 3d, 7, 8 | High |
| 11 | User: role in allowed set; name and email non-empty; email format | 3f, 4, 7 | High |

---

## 10. Implementation note: “in use” for category and family

For **remove_category_recipe** and **remove_family_inventory**, the registry usually doesn’t hold all Recipe or InventoryItem instances. Options:

- **A)** Registry methods take an optional “checker”: e.g. `remove_category_recipe(category_id, recipes: list[Recipe] | None = None)`; if `recipes` is provided, check that no recipe has that category_id before removing.
- **B)** A higher-level “context” or “restaurant state” object that holds registries and all recipes/items; it implements remove_category_recipe by first checking recipes, then calling registry remove.
- **C)** Document that the **caller** must ensure no Recipe (or InventoryItem) uses that category (or family) before calling remove; the registry does not check. Simpler but shifts responsibility.

Recommend **documenting** in the plan which approach is chosen (e.g. “Caller must not remove a category/family that is still in use; the registry does not perform this check unless usage data is provided.” or “Registry remove methods accept an optional list of dependent entities for validation.”). If the app has a single “context” that holds recipes and items, option B is clean.

---

No changes have been made to `subtask-2.2-plan.md` yet. After you decide which of these to adopt, the plan can be updated accordingly.
