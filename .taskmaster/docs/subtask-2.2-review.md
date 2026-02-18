# Review: Subtask 2.2 — Entity relationships and validation

## Summary

The subtask 2.2 plan (`.taskmaster/docs/subtask-2.2-plan.md`) and the Task Master task details are largely aligned. Below are **gaps**, **ambiguities**, and **recommended changes** so implementation stays consistent with the data model and the inventory-units/equivalences design.

---

## 1. Require `unit_id_for_inventory` when creating a new InventoryItem

**Current state:** Plan section 3.1 and 5 say the new InventoryItem’s unit comes from “ingredient.unit_id (or optional override `unit_id_for_inventory`).”

**Issue:** Ingredient.unit_id is a **RecipeUnit** id; InventoryItem.unit_id must be an **InventoryUnit** id. They are different registries. So we cannot use ingredient.unit_id as InventoryItem.unit_id unless we resolve it (e.g. same symbol in inventory registry). The inventory-units plan says: **require** `unit_id_for_inventory` from `valid_inventory_unit_ids` when creating the new item.

**Recommendation:** In 2.2 plan:
- When add_ingredient creates a **new** InventoryItem, **require** `unit_id_for_inventory: int` (from valid_inventory_unit_ids). Validate it; raise ValueError if missing or invalid.
- Document that the caller (Structuring agent / UI) is responsible for providing this (e.g. same-unit match, user choice, or LLM/default).
- Update section 4.2 and 5 so the new InventoryItem’s unit_id is **always** from `unit_id_for_inventory`, not from ingredient.unit_id.

---

## 2. InventoryUnit equivalence fields (base_unit_id, factor_to_base)

**Current state:** The 2.2 plan does not mention adding equivalence fields to InventoryUnit. The inventory-units-and-equivalences plan and Task Master say: add optional `base_unit_id` and `factor_to_base` in 2.2; use them for conversion in 2.3.

**Recommendation:** Add a short subsection under 3b.2 (Inventory units):
- **InventoryUnit** gets optional `base_unit_id: Optional[int] = None` and `factor_to_base: float = 1.0`.
- **InventoryUnitRegistry** (or add_inventory_unit): when a unit has base_unit_id set, validate: base_unit_id in valid_inventory_unit_ids(), factor_to_base > 0, and **no cycles** (unit A → base B → … → A). Raise ValueError if invalid.
- Conversion logic (to_base_quantity / from_base_quantity) stays in 2.3 (normalization). Reference `.taskmaster/docs/inventory-units-and-equivalences-plan.md` Part 2 and 5.

---

## 3. Recipe “category” and InventoryItem “family” API

**Current state:** Task details mention “add_category(category_id)”, “remove_category(category_id)”, “get_categories()” on Recipe, and “add_family(family_id)”, “remove_family(family_id)”, “get_families()” on InventoryItem. The data model has **single** category_id on Recipe and **single** family_id on InventoryItem (no lists).

**Issue:** “get_categories()” / “get_families()” suggest multiple categories/families per entity. That would conflict with the current model.

**Recommendation:** In the plan, clarify:
- **Recipe** has one `category_id`. No list. Provide validation that category_id is in valid_category_recipe_ids when setting (e.g. in add_ingredient or a dedicated setter). Optional helpers: `update_category_id(category_id: int)` and `clear_category_id()` (set to None if allowed by product rules, or omit clear if category is required).
- **InventoryItem** has one `family_id`. Same idea: validate against valid_family_inventory_ids; optional `update_family_id(family_id: int | None)` and `clear_family_id()`. Do **not** add “add_category”/“get_categories” as a list API unless the model is changed to support multiple categories per recipe.

---

## 4. remove_ingredient: by identity vs by name

**Current state:** Plan 3.2 says “Remove by object identity or by matching name (document which).”

**Recommendation:** Pick one and document it. Options:
- **By identity:** Remove the exact Ingredient instance in the list (if the same object is in self.ingredients). No name matching.
- **By name:** Remove the first ingredient whose name matches (case-sensitive or not). Simpler for callers who don’t hold a reference.

Recommend **by index (int) or by name (str)** for remove_ingredient(ingredient: Ingredient | int | str): if int, treat as index; if str, remove first ingredient with matching name; if Ingredient, remove by identity or by name (document which). That keeps the signature simple and avoids “by identity only” which is rarely what the UI has.

---

## 5. “Remove unit that is in use” (edge case)

**Current state:** Section 8 (Tests) lists “remove unit that is in use” as an edge case but does not define behavior.

**Recommendation:** In section 7 (Error handling) or 3b:
- When **remove_recipe_unit(unit_id)** or **remove_inventory_unit(unit_id)** is called, either:
  - **Option A:** Check that no Ingredient (recipe unit) or InventoryItem (inventory unit) references this unit_id; if any do, **raise ValueError** (or a dedicated error) and do not remove. Document: “Removing a unit in use is not allowed; reassign or remove dependent entities first.”
  - **Option B:** Allow removal and leave existing references as “dangling” (not recommended for data integrity).

Recommend **Option A** and add a test: removing a unit that is still referenced raises.

---

## 6. Checklist and validation summary

**Recommendation:** Add to the section 9 checklist:
- [ ] When add_ingredient creates a new InventoryItem, **unit_id_for_inventory** is required and validated against valid_inventory_unit_ids(); otherwise ValueError.
- [ ] **InventoryUnit** has optional `base_unit_id` and `factor_to_base`. **InventoryUnitRegistry** (or add/update logic) validates base_unit_id in valid ids, factor_to_base > 0, and no cycles.
- [ ] Removing a recipe or inventory unit that is still referenced by any Ingredient or InventoryItem raises an error (or document that it is blocked).

---

## 7. Optional: has_ingredient(name) case sensitivity

**Current state:** Plan 3.3 says “case-sensitive or -insensitive, document.”

**Recommendation:** Choose one in the plan. For recipes (e.g. “Huevo” vs “huevo”), **case-insensitive** is usually friendlier; document: `has_ingredient(name: str) -> bool` compares names case-insensitively (e.g. .lower() or .casefold()).

---

## 8. What is already in good shape

- **Scope** (in/out of 2.2) is clear.
- **Implementation order** is sensible (validation → registries → Restaurant → User → Recipe methods → workflow → helpers).
- **add_ingredient** signature and validation (quantity, valid_unit_ids) are clear.
- **Registries** (RecipeUnit, InventoryUnit, CategoryRecipe, FamilyInventory) and Option A (separate classes in data_model.py) are well specified.
- **Restaurant types** fixed set and **User** admin workflow are clearly defined.
- **Auto-add missing recipe unit on recipe save** (3b.1b) is well described.
- **Tests** and **checklist** cover the main behaviors; the additions above close the remaining gaps.

---

## Next step

Apply the recommended changes to `.taskmaster/docs/subtask-2.2-plan.md` (sections 3.1, 3.2, 3b.2, 4.2, 5, 7, 8, 9) and optionally sync the Task Master subtask 2.2 details so they reference “required unit_id_for_inventory” and “InventoryUnit equivalence fields” explicitly.
