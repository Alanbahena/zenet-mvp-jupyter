# Implementation plan: Subtask 2.2 — Entity relationships and validation

## Goal

Extend the core entity classes (from 2.1) with **relationship methods**, **validation**, and **helpers**. Support the workflow where adding an ingredient to a recipe can create or link an **InventoryItem**. Add **unit registries** (add/remove recipe units and inventory units), **category/family registries** (add/remove CategoryRecipe and FamilyInventory), and **restaurant information** (add/update and clear optional fields). No new modules required for 2.2; extend `core/data_model.py` and add tests.

---

## 1. Scope

| In scope | Out of scope (later tasks) |
|----------|----------------------------|
| Recipe: add_ingredient, remove_ingredient, helpers | Full unit conversion (2.3 normalization) |
| Validation: quantity > 0; unit_id **required** in valid_unit_ids; category_id optional in allowed set | Taxonomy / semantic relations (2.4) |
| add_ingredient → create/link InventoryItem (workflow) | data_model_utils (2.5) |
| Simple helpers on Recipe/Ingredient/InventoryItem | Persistence (task 3) |
| **Unit registries:** add/remove RecipeUnit, add/remove InventoryUnit | |
| **Category/family registries:** add/remove CategoryRecipe, add/remove FamilyInventory | |
| **Restaurant:** add/update optional info (including restaurant_type_id), clear (delete) optional info | |
| **Restaurant types:** Fixed set provided by the software (user selects only; no add/remove) | |
| **User:** add, update, delete user; workflow: only admin can do these; business-profile creator gets admin automatically | |

---

## 2. Implementation order

1. **Validation** — Add validation helpers so relationship methods can use them.
2. **Unit registries** — Add/remove recipe units and inventory units (so valid_unit_ids has a clear source).
3. **Category and family registries** — Add/remove CategoryRecipe and FamilyInventory (so recipe category_id and inventory family_id reference valid ids).
4. **Restaurant info** — Add/update and clear optional restaurant information (address, restaurant_type_id, notes). Restaurant types: fixed set provided by software (user selects only).
5. **User management** — Add, update, delete user; enforce workflow (only admin; business-profile creator gets admin).
6. **Recipe relationship methods** — add_ingredient, remove_ingredient.
7. **add_ingredient and InventoryItem workflow** — Optional creation/linking of InventoryItem when adding an ingredient.
8. **Helper methods** — e.g. on Recipe: ingredient count, find by name.

---

## 3. Recipe: relationship methods

### 3.1 `add_ingredient(ingredient: Ingredient, valid_unit_ids: set[int], ...)`

- **Required:** Append `ingredient` to `self.ingredients`.
- **Validation before adding (all required):**
  - **`ingredient.name`** must be non-empty after stripping whitespace; raise `ValueError` otherwise.
  - `ingredient.quantity > 0` and **finite** (reject `math.inf`, `-math.inf`, `math.nan`); raise `ValueError` otherwise.
  - **`ingredient.unit_id`** must be in `valid_unit_ids` (the set of valid RecipeUnit ids). The caller must pass the set of allowed unit IDs; add_ingredient raises if `unit_id` is not in that set.
- **Workflow (InventoryItem):** When the ingredient is **new** (not already in inventory), create an InventoryItem and add it to inventory. **category_id** (perecedero / no perecedero) is **determined by the LLM**: the caller (e.g. Structuring agent or a service) asks the LLM to classify the ingredient as perishable or non-perishable, obtains the corresponding InventoryCategory id, then passes it when creating the InventoryItem. So:
  - Accept optional `category_id: int | None` (references InventoryCategory). The **caller** is responsible for having obtained this from the **LLM** when the ingredient is new (LLM classifies perecedero vs no perecedero).
  - **When creating a new InventoryItem**, the new item’s unit must be an **InventoryUnit** id. **Require** `unit_id_for_inventory: int` (from valid_inventory_unit_ids). The caller must pass it (e.g. same-unit match from ingredient’s recipe unit, user selection, or LLM/default). Validate `unit_id_for_inventory in valid_inventory_unit_ids`; if missing or invalid, raise `ValueError`. The new InventoryItem’s `unit_id` is this value, not `ingredient.unit_id` (which is a RecipeUnit id).
  - If the ingredient is new and `category_id` and `unit_id_for_inventory` are provided, **create** an `InventoryItem` (name from ingredient, unit_id=unit_id_for_inventory, category_id, optional family_id) and **return** it so the caller adds it to inventory and sets `ingredient.inventory_item_id`. If the ingredient already exists in inventory, link via existing `inventory_item_id` (no new InventoryItem).
  - **When `category_id` is provided**, **`valid_inventory_unit_ids` must also be passed** (required for validating unit_id_for_inventory). If category_id is provided but valid_inventory_unit_ids is None, raise `ValueError`.
  - **When `family_id` is not None**, validate `family_id in valid_family_inventory_ids` (caller must pass the set, e.g. from FamilyInventoryRegistry.valid_family_inventory_ids()); otherwise raise `ValueError`.
- **Recommendation:** Keep Recipe decoupled from persistence. Signature:  
  `add_ingredient(self, ingredient: Ingredient, valid_unit_ids: set[int], category_id: int | None = None, unit_id_for_inventory: int | None = None, family_id: int | None = None, valid_inventory_unit_ids: set[int] | None = None, valid_family_inventory_ids: set[int] | None = None) -> InventoryItem | None`  
  `valid_unit_ids` is **required**. When ingredient is **new** and category_id is provided, **unit_id_for_inventory** and **valid_inventory_unit_ids** are **required**; unit_id_for_inventory must be in valid_inventory_unit_ids. When family_id is provided, valid_family_inventory_ids must be passed and family_id must be in it. Method returns new InventoryItem for caller to add to inventory.
- **Error handling:** Raise `ValueError` if ingredient.name is empty (after strip); if quantity <= 0 or not finite; if `ingredient.unit_id not in valid_unit_ids`; if creating new InventoryItem and (valid_inventory_unit_ids is None or unit_id_for_inventory is None or unit_id_for_inventory not in valid_inventory_unit_ids); if family_id is provided and (valid_family_inventory_ids is None or family_id not in valid_family_inventory_ids).

### 3.2 `remove_ingredient(ingredient: Ingredient | int | str)`

- **By index:** If `int`, remove `self.ingredients[index]`. **Bounds check:** If index < 0 or index >= len(self.ingredients), raise `IndexError` (or `ValueError`) with a clear message.
- **By name:** If `str`, remove the first ingredient whose name matches (case-insensitive, e.g. `.casefold()`).
- **By ingredient:** If `Ingredient`, remove by identity (same object in list) or by matching name; document which (recommend: by name match so callers without a reference can remove).
- Return the removed `Ingredient` or `None` if not found.

### 3.3 Helpers on Recipe

- `ingredient_count() -> int` — len of ingredients.
- `has_ingredient(name: str) -> bool` — any ingredient with that name; use **case-insensitive** comparison (e.g. `.casefold()`) for consistency with remove_ingredient by name.
- Optional: `get_ingredient_by_name(name: str) -> Ingredient | None`.

---

## 3b. Recipe units and Inventory units: add / remove

**Yes, this belongs in 2.2.** The caller of `add_ingredient` needs a set of valid unit IDs; that set should come from a managed list of recipe units and inventory units.

### 3b.1 Recipe units

- **Container:** A registry or list that holds the restaurant’s `RecipeUnit` instances (e.g. from templates or Configuration).
- **Add:** `add_recipe_unit(unit: RecipeUnit)` — **Validation:** Reject duplicate `id` (raise `ValueError`). Reject duplicate `symbol` (exact or case-insensitive; document which; raise `ValueError`). Require `unit.name` and `unit.symbol` to be non-empty after stripping; raise `ValueError` otherwise. Then append to the list.
- **Remove:** `remove_recipe_unit(unit_id: int)` (or by instance); return the removed unit or `None`. **Guard:** If any Ingredient references this unit_id, **do not remove**; raise `ValueError` (see section 7).
- **For add_ingredient:** Expose `valid_recipe_unit_ids() -> set[int]` so the caller can pass this set into `Recipe.add_ingredient(..., valid_unit_ids=registry.valid_recipe_unit_ids())`.

**Implementation option:** Introduce a small class, e.g. `RecipeUnitRegistry`, that holds `units: list[RecipeUnit]` and provides `add(unit)`, `remove(unit_id: int) -> RecipeUnit | None`, `valid_ids() -> set[int]`, and optionally `get(unit_id: int) -> RecipeUnit | None`. Same idea for inventory units.

### 3b.1b. New unit when creating a recipe (auto-add missing recipe unit)

**Workflow:** When the user is creating a new recipe and uses a unit that **does not exist** in the RecipeUnit registry (e.g. they type "2 tazas de harina" and "taza" is not yet a recipe unit), then **once the recipe has been created/saved**, that unit is **automatically added** as a new RecipeUnit in the software.

- **Why it works:** Reduces friction — the user doesn’t have to leave the recipe flow to add a unit in Configuration. Units that weren’t in the template (e.g. "pizca", "taza", "cucharadita") are created on demand when the recipe is saved.
- **Flow:** (1) User creates a recipe and adds ingredients; for some ingredients they specify a unit by name/symbol that is not yet in the registry. (2) The UI or agent captures that unit (name + symbol) as a "pending" or new unit. (3) When the recipe is finalized/saved, for each ingredient whose unit is not in the registry, the system creates a new `RecipeUnit`, adds it to the RecipeUnitRegistry, and sets the ingredient’s `unit_id` to the new unit’s id. (4) The recipe is then stored with all `unit_id`s resolved.
- **Implementation notes:** Ingredients may be supplied with either an existing `unit_id` or a provisional (name, symbol) when the unit doesn’t exist yet. The "recipe save" or "finalize recipe" step (in the Structuring agent or recipe service) resolves new units: create RecipeUnit, add to registry, assign id to each such ingredient. Optionally: before creating a new unit, check for an existing one with the same or normalized name/symbol to avoid duplicates (e.g. "taza" vs "tazas").
- **Add to 2.2:** Yes — document this behavior in the plan and implement the "on recipe save, add any missing recipe units and resolve ingredient.unit_id" logic (in the registry or in the flow that saves the recipe).

### 3b.2 Inventory units

- **Container:** Same idea as recipe units: a list or registry of `InventoryUnit` instances.
- **Add:** `add_inventory_unit(unit: InventoryUnit)` — **Validation:** Reject duplicate `id` (raise `ValueError`). Reject duplicate `symbol` (exact or case-insensitive; document which; raise `ValueError`). Require `unit.name` and `unit.symbol` to be non-empty after stripping; raise `ValueError` otherwise. Then add.
- **Remove:** `remove_inventory_unit(unit_id: int)` (or by instance); return removed unit or `None`. **Guard:** If any InventoryItem references this unit_id, **do not remove**; raise `ValueError` (or document that caller must reassign or remove dependents first). See section 7.
- **Expose:** `valid_inventory_unit_ids() -> set[int]` for use when creating InventoryItems and when validating `unit_id_for_inventory` in add_ingredient.

### 3b.2b InventoryUnit equivalence fields (for custom units like “Caja = 10 kg”)

- **Data model (2.2):** Add to **InventoryUnit** (in data_model.py): `base_unit_id: Optional[int] = None`, `factor_to_base: float = 1.0`. If `base_unit_id is None`, the unit is its own base (factor 1.0). Example: Caja has base_unit_id = id(Kilogramos), factor_to_base = 10. See `.taskmaster/docs/inventory-units-and-equivalences-plan.md` Part 2 and 5.
- **Validation in registry:** When adding or updating an InventoryUnit with `base_unit_id` set: require `base_unit_id in valid_inventory_unit_ids()`, `factor_to_base > 0`, and **no cycles** (following base_unit_id chain must not lead back to the same unit). Raise `ValueError` if invalid.
- **Conversion logic** (to_base_quantity / from_base_quantity) belongs in 2.3 (normalization.py); 2.2 only adds the fields and registry validation.

### 3b.3 Where to put the registries

- **Option A:** Two classes in `data_model.py`: `RecipeUnitRegistry`, `InventoryUnitRegistry`. The Configuration agent or a “restaurant context” object holds instances of these.
- **Option B:** A single `RestaurantContext` (or extend `Restaurant`) with `recipe_units: list[RecipeUnit]`, `inventory_units: list[InventoryUnit]` and methods `add_recipe_unit`, `remove_recipe_unit`, `add_inventory_unit`, `remove_inventory_unit`, `valid_recipe_unit_ids()`, `valid_inventory_unit_ids()`.
- Recommendation: **Option A** keeps `Restaurant` as a simple entity and avoids loading it with collections; the app can still hold one registry of each type per restaurant/context.

---

## 3c. Restaurant: add / update / delete (clear) information

**Yes, this belongs in 2.2.** Restaurant is the top-level entity; operators need to add or change optional info and clear fields when they no longer apply.

### 3c.1 Add or update restaurant information

- **Fields:** `address`, `restaurant_type_id` (references RestaurantType), `notes` are optional and mutable.
- **Methods:** Either keep the dataclass mutable (direct assignment) or add:
  - `update_info(self, address: str | None = None, restaurant_type_id: int | None = None, notes: str | None = None)` — set only the provided keys.
  - Simpler: `update_address(self, value: str | None)`, `update_restaurant_type_id(self, value: int | None)`, `update_notes(self, value: str | None)` so “add/update” = set value (including None to clear).
- **Validation:** When setting `restaurant_type_id`, validate against the **fixed set of restaurant types provided by the software** (e.g. a constant list or module: Casual, Rápida, Gourmet, Cafeterías, Cafés). The user cannot create new types; they only select from these options.

### 3c.2 Delete (clear) restaurant information

- **Meaning:** For optional fields, “delete” = set to `None`.
- **Methods:** `clear_address()`, `clear_restaurant_type_id()`, `clear_notes()` — each sets the corresponding attribute to `None`. Alternatively a single `clear_optional_info()` that sets all three to `None`.
- **Id and name:** Do not provide “delete restaurant” in 2.2 (that would be persistence/lifecycle); only clear optional fields.

---

## 3d. Category recipes and Family inventory: add / remove

**Yes, this belongs in 2.2.** Recipes have a **single** `category_id` (CategoryRecipe); InventoryItems have a **single** `family_id` (FamilyInventory). There are no lists of categories or families per entity. Operators need to add or remove recipe categories and inventory families from the restaurant’s **registries**. When setting **Recipe.category_id** (e.g. on creation or via `Recipe.update_category_id(category_id)`), validate `category_id in valid_category_recipe_ids()` (from CategoryRecipeRegistry); raise `ValueError` if not. When setting **InventoryItem.family_id**, validate against `valid_family_inventory_ids()` when provided. Optional convenience: `Recipe.update_category_id(category_id: int, valid_ids: set[int] | None = None)` and `InventoryItem.update_family_id(family_id: int | None, valid_ids: set[int] | None = None)` that validate and set the single field. Do not add “add_category”/“get_categories” as a list API.

### 3d.1 Category recipe (recipe categories)

- **Container:** A registry or list that holds the restaurant’s `CategoryRecipe` instances (e.g. from templates or Configuration).
- **Add:** `add_category_recipe(category: CategoryRecipe)` — **Validation:** Reject duplicate `id` (raise `ValueError`). Reject duplicate `name` (exact or case-insensitive; document which; raise `ValueError`). Require `category.name` non-empty after stripping; raise `ValueError` otherwise. Then add.
- **Remove:** `remove_category_recipe(category_id: int)` (or by instance) — remove by id; return the removed category or `None`. **Guard:** If any Recipe references this category (i.e. recipe.category_id equals the id being removed), **do not remove**; raise `ValueError` (“Category is in use”). The registry or caller must be able to check usage (e.g. caller passes list of recipes, or registry is part of a context that holds recipes). Document the chosen approach.
- **Expose:** `valid_category_recipe_ids() -> set[int]` so callers can validate `Recipe.category_id` or offer a list of valid categories when creating/editing recipes.

**Implementation option:** `CategoryRecipeRegistry` with `categories: list[CategoryRecipe]`, `add(category)`, `remove(category_id: int) -> CategoryRecipe | None`, `valid_ids() -> set[int]`, and optionally `get(category_id: int) -> CategoryRecipe | None`.

### 3d.2 Family inventory (inventory families)

- **Container:** A registry or list that holds the restaurant’s `FamilyInventory` instances.
- **Add:** `add_family_inventory(family: FamilyInventory)` — **Validation:** Reject duplicate `id` (raise `ValueError`). Reject duplicate `name` (exact or case-insensitive; document which; raise `ValueError`). Require `family.name` non-empty after stripping; raise `ValueError` otherwise. Then add.
- **Remove:** `remove_family_inventory(family_id: int)` (or by instance); return removed family or `None`. **Guard:** If any InventoryItem references this family (i.e. item.family_id equals the id being removed), **do not remove**; raise `ValueError` (“Family is in use”). The registry or caller must be able to check usage; document the chosen approach.
- **Expose:** `valid_family_inventory_ids() -> set[int]` for validating `InventoryItem.family_id` and when creating/editing inventory items.

**Implementation option:** `FamilyInventoryRegistry` with `families: list[FamilyInventory]`, `add(family)`, `remove(family_id: int) -> FamilyInventory | None`, `valid_ids() -> set[int]`, and optionally `get(family_id: int) -> FamilyInventory | None`.

### 3d.3 Where to put the registries

- Same pattern as unit registries: separate classes `CategoryRecipeRegistry` and `FamilyInventoryRegistry` in `data_model.py`. The Configuration agent or restaurant context holds one instance of each; templates can seed them with default categories and families.

---

## 3e. Restaurant types: fixed options (no registry)

**Restaurant types are provided by the software; the user only selects one.** There is **no add/remove** — the user cannot create new restaurant types.

- **Fixed set:** Casual, Rápida, Gourmet, Cafeterías, Cafés. Expose these as a constant list or module-level sequence of `RestaurantType` instances (e.g. `DEFAULT_RESTAURANT_TYPES` or `RESTAURANT_TYPES` in `data_model.py` or a config/templates module).
- **Restaurant.restaurant_type_id:** References one of these types. When updating restaurant info, validate `restaurant_type_id in valid_restaurant_type_ids` where `valid_restaurant_type_ids` is derived from the **fixed** list (e.g. `{t.id for t in DEFAULT_RESTAURANT_TYPES}`), not a user-editable registry.
- **Classification/Configuration:** The UI or agent presents the fixed options; the user selects one. No "add restaurant type" or "remove restaurant type" in 2.2 or in the product.

---

## 3f. User: add, update, delete (workflow: only admin; business-profile creator gets admin)

**Yes, this belongs in 2.2.** User entity exists in the data model (id, name, email, role). Implement add user, update user, and delete user with the following **workflow rules**:

### 3f.1 Workflow rule 1: Only admin can create, update, or delete users

- **Create user:** Allowed only if the **current user** (the one performing the action) has `role == "admin"`. Otherwise raise a permission error (e.g. `PermissionError` or a custom `ForbiddenError`).
- **Update user:** Same: only an **admin** can update any user (e.g. change name, email, or role of another user).
- **Delete user:** Same: only an **admin** can delete a user.
- **Implementation:** The add/update/delete functions or methods accept a **current_user: User** (or current_user_id). Before performing the operation, check `current_user.role == "admin"`; if not, do not perform the operation and raise an error. Optionally: prevent an admin from deleting themselves or the last admin (document behavior).

### 3f.2 Workflow rule 2: The user who created the business profile gets admin rights automatically

- When a user **creates the business profile** (i.e. creates the Restaurant / completes the initial business setup), that user is automatically assigned the role **"admin"**.
- **Implementation:** In the flow that creates the restaurant (e.g. Welcome or Configuration agent, or first-time setup), after creating or linking the Restaurant, set the creating user’s `role` to `"admin"` (or create the user with `role="admin"` if they are created at that moment). No separate “grant admin” action by another admin is required for the business-profile creator.
- This ensures there is always at least one admin per business (the one who created the profile).

### 3f.3 Add, update, delete user (signature / behavior)

- **Add user:** `add_user(user: User, current_user: User) -> None` or add to a `UserRegistry` with `add(user, current_user)`. **Validation:** Enforce `current_user.role == "admin"`. Require `user.name` and `user.email` non-empty after stripping; raise `ValueError` otherwise. Validate **email format** (e.g. basic regex or email-validator); raise `ValueError` if invalid. Validate **role** is in the allowed set (e.g. `{"admin", "user"}` — document allowed roles in the plan); raise `ValueError` otherwise. Email uniqueness is the caller’s or registry’s responsibility (document).
- **Update user:** `update_user(user_id: int, updates: dict, current_user: User)` or registry method. Enforce: `current_user.role == "admin"`. Allowed updates: name, email, role. When updating name or email, require non-empty after stripping. When updating email, validate format. When updating role, validate role in allowed set. Document whether an admin can demote themselves.
- **Delete user:** `delete_user(user_id: int, current_user: User)` or registry method. Enforce: `current_user.role == "admin"`.

### 3f.4 Where to put this

- **Option A:** `UserRegistry` in `data_model.py` with `add(user, current_user)`, `update(user_id, updates, current_user)`, `delete(user_id, current_user)`, each checking `current_user.role == "admin"` and raising if not.
- **Option B:** Standalone functions or a small `user_service` module that takes a user list/registry and performs add/update/delete with the same authorization check.
- The **business-profile creator gets admin** logic lives in the flow that creates the Restaurant (e.g. in the agent or setup code that creates the first Restaurant and the creating user), not necessarily in the UserRegistry itself.

---

## 4. Validation

### 4.1 Ingredient

- **name:** Must be non-empty after stripping whitespace. Raise `ValueError` otherwise (avoids empty ingredients and empty InventoryItem names when created from add_ingredient).
- **Quantity:** Must be > 0 and **finite** (reject `math.inf`, `-math.inf`, `math.nan`). Raise `ValueError` with a clear message if not.
- **unit_id:** Must be a valid unit ID. When adding an ingredient, the caller passes `valid_unit_ids: set[int]` (e.g. from the restaurant’s RecipeUnit registry); **validation is required**: `ingredient.unit_id in valid_unit_ids`, otherwise raise `ValueError`. It is not optional.

### 4.2 InventoryItem (when created from add_ingredient)

- **category_id:** Must reference a valid InventoryCategory. If the caller passes a set of valid category ids (e.g. {1, 2} for perecedero / no perecedero), validate; otherwise require category_id to be an int (no magic values).
- **unit_id:** **Required** when creating a new InventoryItem: must be `unit_id_for_inventory` from the set **valid_inventory_unit_ids** (InventoryUnit registry). When `category_id` is provided, **valid_inventory_unit_ids must be passed**; if it is None, raise `ValueError`. Validate `unit_id_for_inventory in valid_inventory_unit_ids`; do not use ingredient.unit_id (that is a RecipeUnit id).
- **family_id:** When `family_id` is not None, **valid_family_inventory_ids** must be passed and `family_id in valid_family_inventory_ids`; otherwise raise `ValueError`.

### 4.3 Where to put validation

- **Option A:** Instance method `Ingredient.validate(valid_unit_ids: set[int])` — `valid_unit_ids` is **required**; raise if quantity <= 0 or `unit_id not in valid_unit_ids`. Similarly `InventoryItem.validate(valid_category_ids: set[int] | None = None)` for category when creating from add_ingredient.
- **Option B:** Standalone functions in `core/data_model.py`: `validate_ingredient(ingredient, valid_unit_ids: set[int])`, etc.
- Prefer **Option A** for clarity; call from `Recipe.add_ingredient(ingredient, valid_unit_ids, ...)` before appending. The caller must always pass the set of valid RecipeUnit ids.

---

## 5. InventoryItem creation from add_ingredient (workflow)

**Rule:** When an ingredient added to a recipe is **new** (not already in inventory), it is added to the inventory as an InventoryItem. The **category_id** (perecedero / no perecedero) is **defined by the LLM model**.

- **When ingredient is new:** The caller (e.g. Structuring agent) (1) calls the **LLM** to classify the ingredient as perecedero or no perecedero and gets the corresponding InventoryCategory id, (2) calls `add_ingredient(ingredient, valid_unit_ids, category_id=<from LLM>, ...)`, (3) receives the new InventoryItem, adds it to the restaurant’s inventory, and sets `ingredient.inventory_item_id`. If the ingredient already exists in inventory, link to the existing InventoryItem (no LLM call, no new InventoryItem).
- **Inputs:** ingredient (name non-empty, quantity finite and > 0, unit_id), **category_id** (obtained from LLM when ingredient is new), **unit_id_for_inventory** (required: from valid_inventory_unit_ids), **valid_inventory_unit_ids** (required when category_id provided), optional family_id (if provided, **valid_family_inventory_ids** required and family_id must be in it). Unit of the new InventoryItem is **unit_id_for_inventory**, not ingredient.unit_id.
- **Output:** When new and category_id and unit_id_for_inventory provided, new `InventoryItem(id=0, name=ingredient.name, unit_id=unit_id_for_inventory, category_id=..., family_id=...)`. Caller assigns a real id, appends to inventory, sets `ingredient.inventory_item_id`.
- **No “restaurant” inside Recipe:** Recipe does not hold a reference to Restaurant or to an inventory list; the caller is responsible for storing the returned InventoryItem and linking it.

---

## 6. Unit conversion (2.2 scope)

- Task says “convert between different units where appropriate.” For 2.2, keep it minimal:
  - **Option 1:** Only “same unit” checks (e.g. both in grams) or a stub that defers to 2.3.
  - **Option 2:** One or two simple conversion factors in data_model (e.g. kg ↔ g) as a placeholder; full registry in 2.3.
- Recommendation: **Stub or very minimal** in 2.2; full normalization in 2.3.

---

## 7. Error handling

- Use **ValueError** for invalid data (e.g. ingredient name empty; quantity <= 0 or not finite; invalid category_id; invalid or missing unit_id_for_inventory or valid_inventory_unit_ids when creating InventoryItem; family_id provided but not in valid_family_inventory_ids; invalid base_unit_id or cycle in InventoryUnit equivalence; duplicate id/symbol/name on registry add; empty name/symbol on unit or category/family add; User name/email empty or invalid email format or role not in allowed set).
- **Index out of range:** When `remove_ingredient(int)` is called with an index < 0 or >= len(ingredients), raise **IndexError** (or ValueError) with a clear message.
- **Remove unit in use:** When `remove_recipe_unit(unit_id)` or `remove_inventory_unit(unit_id)` is called, if any Ingredient (for recipe unit) or InventoryItem (for inventory unit) still references that unit_id, **raise ValueError** and do not remove. Document: “Unit is in use; reassign or remove dependent entities first.”
- **Remove category/family in use:** When `remove_category_recipe(category_id)` or `remove_family_inventory(family_id)` is called, if any Recipe (for category) or InventoryItem (for family) still references it, **raise ValueError** and do not remove. Document how the check is done (caller passes dependent list, or context provides it).
- Optionally define `core.data_model.ValidationError` subclass of ValueError for clearer catching.
- Document in docstrings which methods raise and when.

---

## 8. Tests (test strategy from task)

- **Relationship methods:** Add ingredient → list grows; remove by index (including index out of range → IndexError/ValueError), by name, and by ingredient; remove missing → return None.
- **Validation:** ingredient name empty → ValueError; quantity <= 0 or not finite → ValueError; **ingredient.unit_id not in valid_unit_ids → ValueError** (required); invalid category_id (when provided) → ValueError; valid_inventory_unit_ids missing when creating InventoryItem → ValueError; family_id provided but not in valid_family_inventory_ids → ValueError.
- **Workflow:** add_ingredient with category_id returns an InventoryItem with correct name, unit_id, category_id; ingredient.inventory_item_id remains unset until caller assigns it.
- **Unit registries:** add_recipe_unit / remove_recipe_unit (by id); valid_recipe_unit_ids() returns correct set; same for inventory units. **Recipe units:** When a recipe is saved with an ingredient whose unit (name/symbol) is not in the registry, that unit is auto-added and ingredient.unit_id resolved.
- **Category/family registries:** add_category_recipe / remove_category_recipe (reject duplicate id/name, non-empty name; block remove if category/family in use); valid_category_recipe_ids(); add_family_inventory / remove_family_inventory (same validations); valid_family_inventory_ids(). Recipe.category_id and InventoryItem.family_id validated when set.
- **Restaurant types:** Fixed set (Casual, Rápida, Gourmet, Cafeterías, Cafés); no registry; validation that restaurant_type_id is in the fixed set when setting.
- **Restaurant:** update_info or update_* sets optional fields (including restaurant_type_id); clear_address / clear_restaurant_type_id / clear_notes etc. set to None; name and id unchanged.
- **User:** add_user / update_user / delete_user only succeed when current_user.role == "admin"; otherwise raise permission error. Validate user name and email non-empty, email format, role in allowed set (e.g. {"admin", "user"}). When a user creates the business profile (Restaurant), that user is assigned role "admin" automatically. Tests: admin can add/update/delete; non-admin cannot; invalid email/role/empty name → ValueError.
- **Edge cases:** Empty ingredients list; remove from empty list; duplicate ingredient names allowed or not; remove unit that is in use → raise ValueError (see section 7); last admin or self-delete (document behavior).

---

## 9. Checklist before marking 2.2 done

- [ ] Recipe has `add_ingredient(..., valid_inventory_unit_ids=None, valid_family_inventory_ids=None)` and `remove_ingredient(ingredient | index | str)`; remove_ingredient(index) raises IndexError/ValueError when index out of range.
- [ ] add_ingredient validates ingredient.name non-empty, quantity > 0 and finite, `ingredient.unit_id in valid_unit_ids`; when creating new InventoryItem, **requires** `valid_inventory_unit_ids` and `unit_id_for_inventory` in it; when family_id provided, **requires** `valid_family_inventory_ids` and family_id in it; raises ValueError on failure.
- [ ] When category_id and unit_id_for_inventory are provided (ingredient new), add_ingredient returns an InventoryItem (with unit_id=unit_id_for_inventory) for the caller to add to inventory.
- [ ] Recipe helpers: at least ingredient_count(); optional has_ingredient / get_ingredient_by_name.
- [ ] **Recipe units:** Registry with add_recipe_unit(unit) — reject duplicate id/symbol, non-empty name/symbol; remove_recipe_unit(unit_id) — block if unit in use; valid_recipe_unit_ids() -> set[int]. **On recipe save:** if an ingredient uses a unit not in the registry, auto-add that unit as a new RecipeUnit and resolve ingredient.unit_id.
- [ ] **Inventory units:** Registry with add_inventory_unit(unit) — reject duplicate id/symbol, non-empty name/symbol; remove_inventory_unit(unit_id) — block if in use; valid_inventory_unit_ids() -> set[int]. **InventoryUnit** has optional `base_unit_id` and `factor_to_base`; registry validates no cycles and factor_to_base > 0.
- [ ] **Category recipes:** Registry with add_category_recipe(category) — reject duplicate id/name, non-empty name; remove_category_recipe(category_id) — block if category in use; valid_category_recipe_ids() -> set[int]. Recipe.category_id validated when set.
- [ ] **Family inventory:** Registry with add_family_inventory(family) — reject duplicate id/name, non-empty name; remove_family_inventory(family_id) — block if family in use; valid_family_inventory_ids() -> set[int].
- [ ] **Restaurant types:** Fixed set provided by software (Casual, Rápida, Gourmet, Cafeterías, Cafés); user selects only; no add/remove. Validate restaurant_type_id against this set when updating Restaurant.
- [ ] **Restaurant:** Add/update optional info (address, restaurant_type_id, notes); clear_* methods to set optional fields to None.
- [ ] **User:** Add, update, delete user. **Workflow:** (1) Only users with role "admin" can create, update, or delete users; otherwise raise permission error. (2) The user who creates the business profile (Restaurant) is automatically assigned the admin role. **Validation:** name and email non-empty; email format valid; role in allowed set (e.g. {"admin", "user"}).
- [ ] Unit tests for add/remove ingredient, validation, InventoryItem workflow, unit registries, category/family registries, restaurant info, and user add/update/delete with admin check.
- [ ] Docstrings and type hints on new methods.

---

## 10. Alignment with 2.1 and design docs

- **2.1 plan (section 5b):** When an ingredient added to a recipe is **new**, it is added to inventory as an InventoryItem; **category_id** (perecedero / no perecedero) is **determined by the LLM**. 2.2 implements add_ingredient; the caller (e.g. Structuring agent) calls the LLM to get category_id when the ingredient is new, then creates/links the InventoryItem.
- **InventoryCategory:** Use `category_id: int` (reference to InventoryCategory.id); validate against allowed ids if a set is provided. No string "perecedero"/"no perecedero" in the API; those are the names of InventoryCategory instances.
- **RestaurantType:** Restaurant uses `restaurant_type_id: Optional[int]` (reference to RestaurantType.id). Types are a **fixed set provided by the software** (Casual, Rápida, Gourmet, Cafeterías, Cafés). The user **selects** one option only; there is no registry and the user cannot create or remove restaurant types.
- **User:** Add, update, delete user are in 2.2. **Workflow:** (1) Only **admin** users can create, update, or delete users; enforce by passing current_user and checking role before performing the operation. (2) The **user who created the business profile** (Restaurant) gets **admin** rights automatically when the profile is created.
