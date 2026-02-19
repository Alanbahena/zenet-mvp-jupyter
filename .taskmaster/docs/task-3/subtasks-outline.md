# Task 3 — Subtasks: description and scope

This document outlines all subtasks of **Task 3: Implement data persistence layer**, with a short description and scope (in / out) for each. Full implementation details live in each subtask's plan under `task-3/<subtask-id>/plan.md`.

---

## 3.1 — Persistence scope and serialization contract

**Description:** Decide which entities from the data model (task 2) are persisted and define the JSON-serializable dict shape for each. Document how relationships are represented (by id). No implementation yet; this is the contract so 3.2, 3.3, and 3.4 stay aligned.

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| List of persisted entity types (Restaurant, Recipe, Ingredient, InventoryItem, RecipeUnit, InventoryUnit, CategoryRecipe, FamilyInventory, User; optionally InventoryUnitEquivalence, conversion table, or registry snapshots) | Actual serialization code (3.3) |
| Dict shape per type (field names, id references, handling of lists e.g. Recipe.ingredients) | Storage implementation (3.2, 3.5) |
| Document in code or short spec under `task-3/3.1/` | Schema migrations (deferred) |

**Plan:** [3.1/plan.md](3.1/plan.md)

---

## 3.2 — JSON storage (JsonStorage)

**Description:** Implement `core/persistence.py` with a `JsonStorage` class that saves and loads entity data as JSON files. One file per entity instance (e.g. `{entity_type}_{entity_id}.json`). Operate on plain dicts only; no entity objects in this class.

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| `JsonStorage`: `__init__(data_dir)`, `save(entity_type, entity_id, data_dict)`, `load(entity_type, entity_id) -> dict \| None` | Serialization of entity objects (3.3) |
| Optional: `delete(entity_type, entity_id)`, `list_ids(entity_type) -> list` | DataLake or unified API (3.6) |
| File layout and naming; `os.makedirs(data_dir, exist_ok=True)`; error handling (missing file, invalid JSON, IO) | SQLite (3.4, 3.5) |

**Plan:** [3.2/plan.md](3.2/plan.md)

---

## 3.3 — Entity ↔ dict serialization

**Description:** Implement functions (in `core/persistence.py` or a small `core/serialization.py`) to convert core entities (Recipe, Ingredient, Restaurant, InventoryItem, RecipeUnit, InventoryUnit, CategoryRecipe, FamilyInventory, User) to and from plain dicts. Used by both JSON and SQLite paths and by DataLake when saving/loading entity objects.

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| To-dict and from-dict per entity type; handle nested lists (e.g. Recipe.ingredients as list of dicts) | Persistence scope decisions (3.1) |
| Optional/enum fields (e.g. RestaurantType id); consistent id-based references | Storage backends (3.2, 3.5) |
| Single source of truth: use `core.data_model` types | Schema migrations |

**Plan:** [3.3/plan.md](3.3/plan.md)

---

## 3.4 — SQLite schema

**Description:** Design and implement the SQLite schema: tables for all persisted entity types, columns, and foreign keys (e.g. ingredient → recipe_id, unit_id). Implement `_create_tables()` with `CREATE TABLE` statements. Optional: schema version table for future migrations.

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| Tables: restaurant, recipe, ingredient, recipe_unit, inventory_unit, inventory_item, category_recipe, family_inventory, user; any for equivalences or conversion table if persisted | SqliteStorage save/load implementation (3.5) |
| FKs and indexing as needed; `_create_tables()` called from SqliteStorage constructor | Migration runner (deferred) |

**Plan:** [3.4/plan.md](3.4/plan.md)

---

## 3.5 — SQLite storage (SqliteStorage)

**Description:** Implement `SqliteStorage` in `core/persistence.py`: connect to DB, create tables (using 3.4 schema), save/load by entity_type and entity_id using parameterized queries. Optional delete/list_ids. Basic transaction handling and error handling (db locked, disk full).

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| `SqliteStorage`: `__init__(db_path)`, `_create_tables()`, `save(entity_type, entity_id, data_dict)`, `load(entity_type, entity_id) -> dict \| None` | Entity serialization (3.3) |
| Parameterized queries; optional `delete`, `list_ids`; error handling | DataLake (3.6) |

**Plan:** [3.5/plan.md](3.5/plan.md)

---

## 3.6 — DataLake unified interface

**Description:** Implement a `DataLake` (or equivalent) class in `core/persistence.py` that exposes a single API for saving and loading. Can wrap JsonStorage, SqliteStorage, or both (configurable). Optional convenience: `save_entity_obj` / `load_entity_obj` that serialize/deserialize (3.3) and delegate to the chosen backend.

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| DataLake: config (backend type, paths), `save_entity(entity_type, entity_id, data)` / `load_entity(...)` | New backends beyond JSON/SQLite |
| Optional: `save_entity_obj` / `load_entity_obj` using 3.3; single backend or simple strategy (e.g. "use SQLite if path set else JSON") | Sync/copy between JSON and SQLite (deferred) |

**Plan:** [3.6/plan.md](3.6/plan.md)

---

## 3.7 — Integration and unit tests

**Description:** Wire serialization (3.3) to storage (3.2, 3.5) and DataLake (3.6). Add unit tests: round-trip save/load per entity type for both JSON and SQLite; error cases (missing file, corrupt JSON, invalid DB). Document usage (e.g. in README or `docs/Architecture`) for DataLake and any convenience helpers.

**Scope:**

| In scope | Out of scope |
|----------|--------------|
| Tests in `tests/unit/test_persistence.py` (or similar); round-trip integrity; error paths | E2E or multi-user tests |
| Exports from `core/__init__.py`; short usage note in README or architecture doc | Performance/load testing |

**Plan:** [3.7/plan.md](3.7/plan.md)

---

## Dependency order

- **3.1** (no deps) → **3.2** (3.1) → **3.3** (3.1) → **3.4** (3.1) → **3.5** (3.4) → **3.6** (3.2, 3.3, 3.5) → **3.7** (3.6).
