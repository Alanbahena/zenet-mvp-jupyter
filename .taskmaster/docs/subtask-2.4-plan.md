# Implementation plan: Subtask 2.4 — Semantic relations in taxonomy.py

## Goal

Create `core/taxonomy.py` with a **Taxonomy** class and support for semantic relationships (e.g. is-a, part-of). Provide taxonomies for **ingredients**, **recipes**, and **inventory items**, with functions to query relationships and to find related items by taxonomic proximity. This supports categorization, semantic unification, and discovery of related entities (e.g. for alignment, substitution, or reporting).

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| core/taxonomy.py module | LLM or UI for populating taxonomies (later) |
| Taxonomy class (hierarchical relationships) | Persistence layer (DB); in-memory or simple file is enough for 2.4 |
| Typed relationships (is-a, part-of) and query API | Integration with agents/notebooks (later tasks) |
| Ingredient, recipe, and inventory-item taxonomies | Automatic inference of relationships from text (LLM) |
| find_related by proximity (depth/limit) | |
| Unit tests and exports from core | |

---

## Taxonomy class (core structure)

- **Purpose:** Represent hierarchical and typed semantic relationships between entities (nodes). Used by ingredient, recipe, and inventory taxonomies.
- **Data:** Nodes identifiable by id or name; directed edges with optional relationship type (e.g. `is_a`, `part_of`). Support single or multiple roots.
- **Operations:** Add node; add relationship (parent-child or typed); get children, get parents, get_related(node, relationship_type); optionally has_relationship(a, b, type). Document supported relationship types.
- **No domain logic:** Taxonomy class is generic; domain-specific taxonomies (ingredients, recipes, inventory) are built on top of it (subclasses or facades).

---

## Relationship types and query API

- **Relationship types:** At least **is-a** (subtype / classification) and **part-of** (meronymy). Others can be added (e.g. used_in, substitutes) as needed.
- **Query API:** Functions such as `get_children(node_id)`, `get_parents(node_id)`, `get_related(node_id, relationship_type)`, and optionally `has_relationship(a, b, type)`. Return lists of node ids or node references as documented.
- **Design:** Store edges as (source, target, type) or equivalent; support lookup by type so queries are efficient for the expected scale (hundreds to low thousands of nodes).
- **Edge direction:** For **is_a**, store (child, parent) so that e.g. (tomate, verdura) means “tomate is_a verdura” (source = child, target = parent). For **part_of**, define consistently (e.g. part = source, whole = target). Document in code so traversal and queries are unambiguous.

---

## Link to data model (core/data_model.py)

The taxonomy is a **separate semantic layer**; it does not replace Ingredient, Recipe, InventoryItem, or their registries. Node ids may match data model ids (e.g. Recipe.id, InventoryItem.id) or names (e.g. ingredient name); the chosen convention per taxonomy should be documented. The **caller** is responsible for populating the taxonomy and keeping it in sync with the data model; 2.4 does not implement persistence or automatic sync. Inventory items can be sourced from **InventoryItemRegistry** when populating InventoryTaxonomy.

---

## Ingredient taxonomy

- **Purpose:** Hierarchical and relational view of ingredients (e.g. “tomate” is-a “verdura”, “queso” part-of “tacos”).
- **Implementation:** IngredientTaxonomy or a dedicated Taxonomy instance for ingredients. Nodes keyed by ingredient id or name (decide and document). Methods to register ingredients and add is-a / part-of relationships; query API e.g. `get_ingredient_ancestors`, `get_ingredient_related(name_or_id, relationship_type)`.
- **Use:** Semantic unification (Alignment), substitution suggestions, reporting by category.

---

## Recipe taxonomy

- **Purpose:** Categorize and relate recipes (e.g. by category, cuisine, or semantic links).
- **Implementation:** RecipeTaxonomy or a dedicated Taxonomy instance for recipes. Nodes keyed by recipe id or name. Relationships can be category-style (is-a) or part-of (e.g. recipe X part of menu Y). Query API e.g. `get_recipe_categories`, `get_related_recipes(recipe_id, relationship_type)`.
- **Alignment:** Can align with CategoryRecipe (data model) where it makes sense; taxonomy can represent additional semantic hierarchy beyond category_id.

---

## Inventory item taxonomy

- **Purpose:** Semantic grouping and relations for inventory items (e.g. by product type, family-like hierarchy).
- **Implementation:** InventoryTaxonomy or a dedicated Taxonomy instance for inventory items. Nodes keyed by inventory_item_id or name. Support is-a and part-of; optionally reflect FamilyInventory as a taxonomic level. Query API e.g. `get_inventory_ancestors`, `get_related_inventory_items(item_id, relationship_type)`.
- **Note:** FamilyInventory (data model) remains the source of truth for “family” grouping; taxonomy can mirror or extend it for semantic queries.

---

## Find related by proximity

- **Purpose:** Find items related to a given entity within a distance limit (e.g. same branch, N hops).
- **API:** e.g. `find_related_items(entity_id, taxonomy_type, max_depth=None, limit=None)` returning a list of (node_id, distance or relationship_path). taxonomy_type can be "ingredient" | "recipe" | "inventory" or an enum.
- **Behavior:** Traverse from the given node along relationship edges up to max_depth; optionally cap number of results with limit. Document tie-breaking and ordering (e.g. by distance, then by id).

---

## Breakdown (implementation order)

### Step 2.4.1 — Create core/taxonomy.py and Taxonomy class

- **Deliverable:** New file `core/taxonomy.py`.
- **Class:** `Taxonomy` with: (1) storage for nodes (by id or name); (2) storage for edges (source, target, optional relationship_type); (3) methods: add_node(id, name=None), add_relationship(source, target, relationship_type=None), get_children(node_id), get_parents(node_id). Support multiple roots (no single root required).
- **Tests:** Add nodes and parent-child links; query children/parents; multiple roots.

### Step 2.4.2 — Relationship types and query API

- **Extend:** Edges store relationship_type (e.g. "is_a", "part_of"). Add get_related(node_id, relationship_type), and optionally has_relationship(a, b, type).
- **Document:** Supported relationship types and their meaning (is-a, part-of).
- **Tests:** Add typed relationships; query by type; missing node or type returns empty or raises as documented.

### Step 2.4.3 — Ingredient taxonomy

- **Implement:** IngredientTaxonomy (or Taxonomy instance) for ingredients. Register ingredient nodes (by name or id); add is-a / part-of. Expose get_ingredient_ancestors, get_ingredient_related (or equivalent).
- **Tests:** Build small ingredient hierarchy; query ancestors and related by type.

### Step 2.4.4 — Recipe taxonomy

- **Implement:** RecipeTaxonomy (or Taxonomy instance) for recipes. Register recipe nodes; add category-style and part-of relationships. Expose get_recipe_categories, get_related_recipes (or equivalent).
- **Tests:** Build small recipe taxonomy; query categories and related recipes.

### Step 2.4.5 — Inventory item taxonomy

- **Implement:** InventoryTaxonomy (or Taxonomy instance) for inventory items. Register inventory item nodes; add is-a / part-of. Expose get_inventory_ancestors, get_related_inventory_items (or equivalent).
- **Tests:** Build small inventory taxonomy; query ancestors and related items.

### Step 2.4.6 — Find related by proximity, exports, and tests

- **Implement:** find_related_items(entity_id, taxonomy_type, max_depth=None, limit=None) (or equivalent API) traversing the taxonomy and returning related nodes with distance/path.
- **Exports:** From core/__init__.py export Taxonomy and public taxonomy classes/functions.
- **Tests:** tests/unit/test_taxonomy.py — Taxonomy basics, typed relationships, ingredient/recipe/inventory taxonomies, find_related by proximity.

---

## Checklist before marking 2.4 done

- [x] core/taxonomy.py exists with Taxonomy class (nodes + edges, optional relationship_type).
- [x] get_children, get_parents, get_related(node, type) (and optionally has_relationship) implemented and tested.
- [x] Ingredient taxonomy implemented with query API; tests pass.
- [x] Recipe taxonomy implemented with query API; tests pass.
- [x] Inventory item taxonomy implemented with query API; tests pass.
- [x] find_related_items (or equivalent) by proximity implemented; tests pass.
- [x] Exports added in core/__init__.py; tests/unit/test_taxonomy.py has good coverage.

---

## Optional (later)

- Persistence: save/load taxonomy from DB or file.
- LLM or UI to populate and edit taxonomies (Alignment/Configuration/Structuring).
- Additional relationship types (e.g. substitutes, used_in).
