# Implementation plan: Subtask 3.4 — SQLite schema

## Goal

Design and implement the SQLite schema: one table per persisted entity type, with columns and foreign keys aligned to the 3.1 dict shape. Implement `_create_tables()` that runs the `CREATE TABLE` statements. Optional: a schema version table for future migrations.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| Tables: restaurant, recipe, ingredient, recipe_unit, inventory_unit, inventory_item, category_recipe, family_inventory, user; plus any for equivalences/conversion if persisted | SqliteStorage save/load implementation (3.5) |
| FKs and indexing as needed; `_create_tables()` called from SqliteStorage constructor | Migration runner (deferred) |

---

## Dependencies

- **3.1** — Table and column design must match the persisted entity types and dict fields (ids, FKs, scalars).

---

## Breakdown

### 1. Table list

- **Core entities:** restaurant, recipe, ingredient, recipe_unit, inventory_unit, inventory_item, category_recipe, family_inventory, user.
- **Optional:** inventory_unit_equivalence, conversion_table, or similar if in 3.1 scope.
- **Naming:** Use snake_case table names; primary key `id` (TEXT or INTEGER as per data model).

### 2. Column design per table

- **restaurant:** id, name, type (or type_id), and any other persisted Restaurant fields; types TEXT/INTEGER/REAL as appropriate.
- **recipe:** id, name, restaurant_id (FK), and other Recipe fields; optional JSON column for ingredients list if stored as blob, or normalized in ingredient table.
- **ingredient:** id, recipe_id (FK), name, quantity, unit_id (FK), and other fields.
- **recipe_unit, inventory_unit:** id, name, symbol, and any unit-specific fields.
- **inventory_item:** id, family_id (FK), name, unit_id (FK), quantity, and other fields.
- **category_recipe:** id, name, recipe_id (FK) or equivalent; category hierarchy if needed.
- **family_inventory:** id, name, restaurant_id or equivalent (FK).
- **user:** id, name, email, and other User fields.
- **Foreign keys:** Declare FKs in CREATE TABLE or with ALTER; ensure referenced tables exist (order of CREATE TABLE matters).

### 3. Indexes

- Add indexes on FK columns and frequently queried columns (e.g. recipe_id, family_id, unit_id) to keep lookups fast.

### 4. _create_tables()

- **Implementation:** One function (or method) that runs all `CREATE TABLE IF NOT EXISTS` and optional `CREATE INDEX` statements.
- **Location:** In `core/persistence.py` next to SqliteStorage, or in a schema module; SqliteStorage will call it in `__init__`.
- **Optional:** `schema_version` table with a single row (version integer); write initial version after creating tables (for future migrations).

### 5. Deliverable

- **Code:** SQL strings or executed statements in `core/persistence.py` (or dedicated schema file); `_create_tables(conn)` or `_create_tables(cursor)`.
- **No** save/load logic in 3.4; that is 3.5.
