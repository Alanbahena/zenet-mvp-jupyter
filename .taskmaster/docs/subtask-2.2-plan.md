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

---

## 2. Implementation order

1. **Validation** — Add validation helpers so relationship methods can use them.
2. **Unit registries** — Add/remove recipe units and inventory units (so valid_unit_ids has a clear source).
3. **Category and family registries** — Add/remove CategoryRecipe and FamilyInventory (so recipe category_id and inventory family_id reference valid ids).
4. **Restaurant info** — Add/update and clear optional restaurant information (address, restaurant_type_id, notes). Restaurant types: fixed set provided by software (user selects only).
5. **Recipe relationship methods** — add_ingredient, remove_ingredient.
6. **add_ingredient and InventoryItem workflow** — Optional creation/linking of InventoryItem when adding an ingredient.
7. **Helper methods** — e.g. on Recipe: ingredient count, find by name.

---

## 3. Recipe: relationship methods

### 3.1 `add_ingredient(ingredient: Ingredient, valid_unit_ids: set[int], ...)`

- **Required:** Append `ingredient` to `self.ingredients`.
- **Validation before adding (all required):**
  - `ingredient.quantity > 0`
  - **`ingredient.unit_id` must be in `valid_unit_ids`** (the set of valid RecipeUnit ids). The caller must pass the set of allowed unit IDs; add_ingredient raises if `unit_id` is not in that set.
- **Workflow (InventoryItem):** When the ingredient is **new** (not already in inventory), create an InventoryItem and add it to inventory. **category_id** (perecedero / no perecedero) is **determined by the LLM**: the caller (e.g. Structuring agent or a service) asks the LLM to classify the ingredient as perishable or non-perishable, obtains the corresponding InventoryCategory id, then passes it when creating the InventoryItem. So:
  - Accept optional `category_id: int | None` (references InventoryCategory). The **caller** is responsible for having obtained this from the **LLM** when the ingredient is new (LLM classifies perecedero vs no perecedero).
  - If the ingredient is new and `category_id` is provided, **create** an `InventoryItem` (name from ingredient, unit_id from ingredient, category_id, optional family_id) and **return** it so the caller adds it to inventory and sets `ingredient.inventory_item_id`. If the ingredient already exists in inventory, link via existing `inventory_item_id` (no new InventoryItem).
- **Recommendation:** Keep Recipe decoupled from persistence. Signature:  
  `add_ingredient(self, ingredient: Ingredient, valid_unit_ids: set[int], category_id: int | None = None, unit_id_for_inventory: int | None = None, family_id: int | None = None) -> InventoryItem | None`  
  `valid_unit_ids` is **required**. When ingredient is **new**, caller gets `category_id` from **LLM** (perecedero/no perecedero), then calls add_ingredient with that category_id; method returns new InventoryItem for caller to add to inventory.
- **Error handling:** Raise `ValueError` if quantity <= 0, or if `ingredient.unit_id not in valid_unit_ids`.

### 3.2 `remove_ingredient(ingredient: Ingredient | int)`

- **By ingredient:** Remove by object identity or by matching name (document which).
- **By index:** If `int`, remove `self.ingredients[index]` (with bounds check).
- Return the removed `Ingredient` or `None` if not found.

### 3.3 Helpers on Recipe

- `ingredient_count() -> int` — len of ingredients.
- `has_ingredient(name: str) -> bool` — any ingredient with that name (case-sensitive or -insensitive, document).
- Optional: `get_ingredient_by_name(name: str) -> Ingredient | None`.

---

## 3b. Recipe units and Inventory units: add / remove

**Yes, this belongs in 2.2.** The caller of `add_ingredient` needs a set of valid unit IDs; that set should come from a managed list of recipe units and inventory units.

### 3b.1 Recipe units

- **Container:** A registry or list that holds the restaurant’s `RecipeUnit` instances (e.g. from templates or Configuration).
- **Add:** `add_recipe_unit(unit: RecipeUnit)` — append to the list; optionally reject duplicate `id` or duplicate `symbol`.
- **Remove:** `remove_recipe_unit(unit_id: int) | remove_recipe_unit(unit: RecipeUnit)` — remove by id or by instance; return the removed unit or `None`.
- **For add_ingredient:** Expose `valid_recipe_unit_ids() -> set[int]` so the caller can pass this set into `Recipe.add_ingredient(..., valid_unit_ids=registry.valid_recipe_unit_ids())`.

**Implementation option:** Introduce a small class, e.g. `RecipeUnitRegistry`, that holds `units: list[RecipeUnit]` and provides `add(unit)`, `remove(unit_id: int) -> RecipeUnit | None`, `valid_ids() -> set[int]`, and optionally `get(unit_id: int) -> RecipeUnit | None`. Same idea for inventory units.

### 3b.2 Inventory units

- **Container:** Same idea as recipe units: a list or registry of `InventoryUnit` instances.
- **Add:** `add_inventory_unit(unit: InventoryUnit)`.
- **Remove:** `remove_inventory_unit(unit_id: int)` (or by instance); return removed unit or `None`.
- **Expose:** `valid_inventory_unit_ids() -> set[int]` for use when creating InventoryItems (e.g. in Structuring or when validating inventory unit_id).

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

**Yes, this belongs in 2.2.** Recipes reference `category_id` (CategoryRecipe); InventoryItems can reference `family_id` (FamilyInventory). Operators need to add or remove recipe categories (e.g. desayuno, comida, cena, bebidas) and inventory families (e.g. Lácteos, Granos) from the restaurant’s configured sets.

### 3d.1 Category recipe (recipe categories)

- **Container:** A registry or list that holds the restaurant’s `CategoryRecipe` instances (e.g. from templates or Configuration).
- **Add:** `add_category_recipe(category: CategoryRecipe)` — add a recipe category to the registry; optionally reject duplicate `id` or duplicate `name`.
- **Remove:** `remove_category_recipe(category_id: int)` (or by instance) — remove by id; return the removed category or `None`.
- **Expose:** `valid_category_recipe_ids() -> set[int]` so callers can validate `Recipe.category_id` or offer a list of valid categories when creating/editing recipes.

**Implementation option:** `CategoryRecipeRegistry` with `categories: list[CategoryRecipe]`, `add(category)`, `remove(category_id: int) -> CategoryRecipe | None`, `valid_ids() -> set[int]`, and optionally `get(category_id: int) -> CategoryRecipe | None`.

### 3d.2 Family inventory (inventory families)

- **Container:** A registry or list that holds the restaurant’s `FamilyInventory` instances.
- **Add:** `add_family_inventory(family: FamilyInventory)`.
- **Remove:** `remove_family_inventory(family_id: int)` (or by instance); return removed family or `None`.
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

## 4. Validation

### 4.1 Ingredient

- **Quantity:** Must be > 0. Raise `ValueError` with a clear message if not.
- **unit_id:** Must be a valid unit ID. When adding an ingredient, the caller passes `valid_unit_ids: set[int]` (e.g. from the restaurant’s RecipeUnit registry); **validation is required**: `ingredient.unit_id in valid_unit_ids`, otherwise raise `ValueError`. It is not optional.

### 4.2 InventoryItem (when created from add_ingredient)

- **category_id:** Must reference a valid InventoryCategory. If the caller passes a set of valid category ids (e.g. {1, 2} for perecedero / no perecedero), validate; otherwise require category_id to be an int (no magic values).
- **unit_id:** Use the ingredient’s unit_id (already validated against valid_unit_ids), or optional override for inventory-specific unit.

### 4.3 Where to put validation

- **Option A:** Instance method `Ingredient.validate(valid_unit_ids: set[int])` — `valid_unit_ids` is **required**; raise if quantity <= 0 or `unit_id not in valid_unit_ids`. Similarly `InventoryItem.validate(valid_category_ids: set[int] | None = None)` for category when creating from add_ingredient.
- **Option B:** Standalone functions in `core/data_model.py`: `validate_ingredient(ingredient, valid_unit_ids: set[int])`, etc.
- Prefer **Option A** for clarity; call from `Recipe.add_ingredient(ingredient, valid_unit_ids, ...)` before appending. The caller must always pass the set of valid RecipeUnit ids.

---

## 5. InventoryItem creation from add_ingredient (workflow)

**Rule:** When an ingredient added to a recipe is **new** (not already in inventory), it is added to the inventory as an InventoryItem. The **category_id** (perecedero / no perecedero) is **defined by the LLM model**.

- **When ingredient is new:** The caller (e.g. Structuring agent) (1) calls the **LLM** to classify the ingredient as perecedero or no perecedero and gets the corresponding InventoryCategory id, (2) calls `add_ingredient(ingredient, valid_unit_ids, category_id=<from LLM>, ...)`, (3) receives the new InventoryItem, adds it to the restaurant’s inventory, and sets `ingredient.inventory_item_id`. If the ingredient already exists in inventory, link to the existing InventoryItem (no LLM call, no new InventoryItem).
- **Inputs:** ingredient (name, quantity, unit_id), **category_id** (obtained from LLM when ingredient is new), optional family_id. Unit of the new InventoryItem: ingredient.unit_id (or optional override `unit_id_for_inventory`).
- **Output:** When new and category_id provided, new `InventoryItem(id=0, name=ingredient.name, unit_id=..., category_id=..., family_id=...)`. Caller assigns a real id, appends to inventory, sets `ingredient.inventory_item_id`.
- **No “restaurant” inside Recipe:** Recipe does not hold a reference to Restaurant or to an inventory list; the caller is responsible for storing the returned InventoryItem and linking it.

---

## 6. Unit conversion (2.2 scope)

- Task says “convert between different units where appropriate.” For 2.2, keep it minimal:
  - **Option 1:** Only “same unit” checks (e.g. both in grams) or a stub that defers to 2.3.
  - **Option 2:** One or two simple conversion factors in data_model (e.g. kg ↔ g) as a placeholder; full registry in 2.3.
- Recommendation: **Stub or very minimal** in 2.2; full normalization in 2.3.

---

## 7. Error handling

- Use **ValueError** for invalid data (e.g. quantity <= 0, invalid category_id).
- Optionally define `core.data_model.ValidationError` subclass of ValueError for clearer catching.
- Document in docstrings which methods raise and when.

---

## 8. Tests (test strategy from task)

- **Relationship methods:** Add ingredient → list grows; remove by index and by ingredient; remove missing → no error or return None.
- **Validation:** quantity <= 0 → ValueError; **ingredient.unit_id not in valid_unit_ids → ValueError** (required); invalid category_id (when provided) → ValueError.
- **Workflow:** add_ingredient with category_id returns an InventoryItem with correct name, unit_id, category_id; ingredient.inventory_item_id remains unset until caller assigns it.
- **Unit registries:** add_recipe_unit / remove_recipe_unit (by id); valid_recipe_unit_ids() returns correct set; same for inventory units.
- **Category/family registries:** add_category_recipe / remove_category_recipe; valid_category_recipe_ids(); add_family_inventory / remove_family_inventory; valid_family_inventory_ids().
- **Restaurant types:** Fixed set (Casual, Rápida, Gourmet, Cafeterías, Cafés); no registry; validation that restaurant_type_id is in the fixed set when setting.
- **Restaurant:** update_info or update_* sets optional fields (including restaurant_type_id); clear_address / clear_restaurant_type_id / clear_notes etc. set to None; name and id unchanged.
- **Edge cases:** Empty ingredients list; remove from empty list; duplicate ingredient names allowed or not; remove unit that is in use (document behavior).

---

## 9. Checklist before marking 2.2 done

- [ ] Recipe has `add_ingredient(ingredient, valid_unit_ids: set[int], category_id=None, ...)` and `remove_ingredient(ingredient | index)`.
- [ ] add_ingredient **requires** `valid_unit_ids`; validates quantity > 0 and `ingredient.unit_id in valid_unit_ids`; raises on failure.
- [ ] When category_id is provided, add_ingredient returns an InventoryItem for the caller to add to inventory.
- [ ] Recipe helpers: at least ingredient_count(); optional has_ingredient / get_ingredient_by_name.
- [ ] **Recipe units:** Registry with add_recipe_unit(unit), remove_recipe_unit(unit_id), valid_recipe_unit_ids() -> set[int].
- [ ] **Inventory units:** Registry with add_inventory_unit(unit), remove_inventory_unit(unit_id), valid_inventory_unit_ids() -> set[int].
- [ ] **Category recipes:** Registry with add_category_recipe(category), remove_category_recipe(category_id), valid_category_recipe_ids() -> set[int].
- [ ] **Family inventory:** Registry with add_family_inventory(family), remove_family_inventory(family_id), valid_family_inventory_ids() -> set[int].
- [ ] **Restaurant types:** Fixed set provided by software (Casual, Rápida, Gourmet, Cafeterías, Cafés); user selects only; no add/remove. Validate restaurant_type_id against this set when updating Restaurant.
- [ ] **Restaurant:** Add/update optional info (address, restaurant_type_id, notes); clear_* methods to set optional fields to None.
- [ ] Unit tests for add/remove ingredient, validation, InventoryItem workflow, unit registries, category/family registries, and restaurant info.
- [ ] Docstrings and type hints on new methods.

---

## 10. Alignment with 2.1 and design docs

- **2.1 plan (section 5b):** When an ingredient added to a recipe is **new**, it is added to inventory as an InventoryItem; **category_id** (perecedero / no perecedero) is **determined by the LLM**. 2.2 implements add_ingredient; the caller (e.g. Structuring agent) calls the LLM to get category_id when the ingredient is new, then creates/links the InventoryItem.
- **InventoryCategory:** Use `category_id: int` (reference to InventoryCategory.id); validate against allowed ids if a set is provided. No string "perecedero"/"no perecedero" in the API; those are the names of InventoryCategory instances.
- **RestaurantType:** Restaurant uses `restaurant_type_id: Optional[int]` (reference to RestaurantType.id). Types are a **fixed set provided by the software** (Casual, Rápida, Gourmet, Cafeterías, Cafés). The user **selects** one option only; there is no registry and the user cannot create or remove restaurant types.
