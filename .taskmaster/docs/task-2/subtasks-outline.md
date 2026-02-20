# Task 2 — Subtasks: description and scope

This document outlines all subtasks of **Task 2: Design and implement data model and ontology**, with a short description and scope (in / out) for each. Full implementation details live in each subtask’s plan under `task-2/<subtask-id>/plan.md`.

---

## 2.1 — Core entity classes in `data_model.py`

**Description:** Implement in `core/data_model.py` the nine entity classes with attributes, type hints, docstrings, and the Recipe–Ingredient relationship. Use Python dataclasses; no validation or relationship methods yet (those are 2.2).

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| Single file `core/data_model.py` | Persistence or DB |
| Nine entities: RecipeUnit, InventoryUnit, CategoryRecipe, FamilyInventory, InventoryCategory, Restaurant, InventoryItem, Ingredient, Recipe | Validation logic |
| Type hints, docstrings, Recipe.ingredients / Ingredient.unit_id, inventory_item_id | add_ingredient / remove_ingredient |
| Exports from `core/__init__.py` | |

**Plan:** [2.1/plan.md](2.1/plan.md)

---

## 2.2 — Entity relationships and validation

**Description:** Extend the core entity classes with relationship methods, validation, and helpers. Support the workflow where adding an ingredient to a recipe can create or link an InventoryItem. Add unit registries (recipe + inventory), category/family registries, restaurant optional info (add/update/clear), fixed restaurant types, and user management (add/update/delete with admin-only workflow; business-profile creator gets admin). All in `core/data_model.py`; no new modules.

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| Recipe: add_ingredient, remove_ingredient, helpers (e.g. ingredient_count, has_ingredient) | Full unit conversion (2.3) |
| Validation: quantity > 0, unit_id in valid_unit_ids, category_id in allowed set | Taxonomy / semantic relations (2.4) |
| add_ingredient → create/link InventoryItem (workflow; LLM provides category_id when new) | data_model_utils (2.5) |
| Unit registries: add/remove RecipeUnit, add/remove InventoryUnit | Persistence (task 3) |
| Category/family registries: add/remove CategoryRecipe, add/remove FamilyInventory | |
| Restaurant: add/update/clear optional info (address, restaurant_type_id, notes) | |
| Restaurant types: fixed set (user selects only; no add/remove) | |
| User: add, update, delete; only admin; business-profile creator gets admin | |

**Plan:** [2.2/plan.md](2.2/plan.md)

---

## 2.3 — Normalization rules in `normalization.py`

**Description:** Create `core/normalization.py` with unit conversion and normalization using InventoryUnit.base_unit_id and factor_to_base. Implement: (1) base rule: per-item unit for deduction; optional family base for reporting; (2) recipe-unit conversion table for informal units (scoop, cucharada, etc.) so recipe lines normalize to quantity + base unit for deduction; (3) normalized recipe = list of (inventory_item_id, normalized_quantity, unit_id) for “consumo teórico por platillo.” Conversion logic and table application in 2.3; LLM/UI for populating the table stay in later tasks.

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| core/normalization.py; to_base_quantity / from_base_quantity for InventoryUnit | display_unit_id on InventoryItem |
| Integration with InventoryUnitRegistry; error handling (missing unit, cycles, invalid quantity) | Parsing free-text user input (e.g. "2 tazas") |
| Per-item unit for deduction; family base optional for reporting | Who creates/suggests conversion table rows (LLM) and UI |
| Recipe-unit conversion table (design + apply) | Actual order/deduction persistence |
| Normalized recipe (list per recipe); make_resolver, apply_deduction_lines | |
| Unit tests for conversions | |

**Plan:** [2.3/plan.md](2.3/plan.md)

---

## 2.4 — Semantic relations in `taxonomy.py`

**Description:** Create `core/taxonomy.py` with a Taxonomy class and support for semantic relationships (e.g. is-a, part-of). Provide taxonomies for ingredients, recipes, and inventory items, with functions to query relationships and to find related items by taxonomic proximity. Supports categorization, semantic unification, and discovery (alignment, substitution, reporting).

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| core/taxonomy.py; Taxonomy class (nodes + edges, optional relationship_type) | LLM or UI for populating taxonomies |
| Typed relationships (is-a, part-of) and query API (get_children, get_parents, get_related) | Persistence layer (DB); in-memory is enough |
| Ingredient, recipe, and inventory-item taxonomies | Integration with agents/notebooks |
| find_related by proximity (max_depth, limit) | Automatic inference of relationships from text (LLM) |
| Unit tests and exports from core | |

**Plan:** [2.4/plan.md](2.4/plan.md)

---

## 2.5 — Data model integration utilities

**Description:** Implement `core/data_model_utils.py` to integrate data_model, normalization, and (optionally) taxonomy. Provide: (1) conversion between normalized and display formats, (2) validation that combines entity and normalization rules, (3) helpers for common operations across entity types, (4) factory methods for related entities. No changes to existing core modules except exports from `core/__init__.py`.

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| New file core/data_model_utils.py | Changing data_model / normalization / taxonomy logic |
| Format (deduction line, ingredient, ingredients_to_display, parse_quantity_and_unit) | Persistence (task 3); agents/notebooks |
| Validation (validate_recipe_for_deduction, validate_ingredient_with_registries) | Full integration/E2E tests |
| Helpers (resolve_ingredient_to_inventory_item, make_resolver_from_item_registry, units_used_by_recipe) | Free-text parsing beyond simple "quantity unit" |
| Factory methods (create_inventory_item_from_ingredient, build_ingredient) | |
| Unit tests; exports from core/__init__.py | |

**Plan:** [2.5/plan.md](2.5/plan.md)

---

## 2.6 — Comprehensive documentation and examples

**Description:** Document the data model, normalization rules, and taxonomy with examples and usage patterns. Verify documentation accuracy and completeness so developers and AI assistants can understand and use the core layer confidently. Dependencies: 2.1–2.5 (all done).

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| Docstring audit and completion (core modules) | Sphinx/API reference (optional later) |
| Update/create architecture docs (data-model, normalization, taxonomy, data-model-utils, readiness-kpis) | Notebook examples (optional later) |
| README: data model section and accurate project structure | Spanish translation (optional later) |
| Runnable examples (e.g. quickstart, normalization, readiness) | |
| Diagram refresh/QA (Mermaid + .mmd/.png in docs/Architecture/images/) | |
| Verification checklist (see 2.6/verification.md) | |

**Plan:** [2.6/plan.md](2.6/plan.md) · **Verification:** [2.6/verification.md](2.6/verification.md)

---

## 2.7 — Readiness KPIs (onboarding completeness & standardization)

**Description:** Define a readiness-only KPI schema and compute a readiness report after onboarding so the operator sees how complete and standardized the restaurant setup is—without sales, purchases, or ongoing operations data. Phase A: serializable JSON schema, computation from in-memory model (registries + recipes + normalization + optional taxonomy), scoring (0–100 overall + per-dimension), drilldown (what’s missing and how to fix it). Not “performance KPIs” (no cost %, waste %, margin); those require persistence (task 3+).

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| Readiness-only KPI schema (JSON + optional dataclasses) | Performance KPIs (cost %, waste %, margin) |
| compute_readiness_report from registries, recipes, conversion table, optional taxonomy | Persistence or operational data |
| Dimensions: setup, recipes, inventory, normalization, taxonomy (optional; weight 0 in Phase A) | LLM or UI for populating taxonomies (separate) |
| Scoring model (0–100, per-dimension; ok/warn/fail; grade) | |
| Evidence and remediation (sample missing, next_actions) | |
| Unit tests for KPI computation; exports from core | |

**Plan:** [2.7/plan.md](2.7/plan.md)

---

## Dependency order

- **2.1** (no deps) → **2.2** (depends on 2.1) → **2.3** (2.1, 2.2) → **2.4** (2.1) → **2.5** (2.2, 2.3, 2.4) → **2.6** (2.1–2.5) → **2.7** (2.2–2.5).

All subtasks 2.1–2.7 are implemented and marked done in Task Master.
