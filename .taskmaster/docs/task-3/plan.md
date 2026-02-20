# Implementation plan: Task 3 — Data persistence layer

## Goal

Create data storage using JSON and SQLite to persist restaurant data and system state. Provide: (1) JsonStorage and SqliteStorage operating on dicts, (2) entity ↔ dict serialization aligned with the data model (task 2), (3) a unified DataLake-style interface, and (4) unit tests and basic documentation.

**Dependencies:** Task 2 (data model) done.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| core/persistence.py (and optional core/serialization.py) | Schema migrations; sync between JSON and SQLite |
| JsonStorage, SqliteStorage, DataLake; entity serialization for core entities | Agents, notebooks, or UI (later tasks) |
| Unit tests; exports from core | Full E2E or backup/restore flows |

---

## Breakdown into steps

### Step 3.1 — Persistence scope and serialization contract

- **Deliverable:** Document (in `task-3/3.1/plan.md` or a short spec) which entities are persisted and the dict shape for each.
- **Content:** List entity types; for each, field names, types, and how FKs are stored (id only). Decide whether registries are "rebuilt from loaded entities" or "persisted as snapshot." No code in core yet.

### Step 3.2 — Implement JsonStorage

- **Deliverable:** `core/persistence.py` with `JsonStorage(data_dir)`, `save(entity_type, entity_id, data_dict)`, `load(entity_type, entity_id) -> dict | None`.
- **File layout:** e.g. `data_dir/{entity_type}_{entity_id}.json`.
- **Error handling:** Missing file → None; invalid JSON / IO → raise or log and raise.

### Step 3.3 — Implement entity ↔ dict serialization

- **Deliverable:** Functions to convert each entity type to/from dict (e.g. `recipe_to_dict`, `recipe_from_dict`). Handle `Recipe.ingredients` as list of ingredient dicts; optional fields and enums as in 3.1.
- **Location:** In `core/persistence.py` or `core/serialization.py`; used by 3.6 and tests.

### Step 3.4 — SQLite schema

- **Deliverable:** Table definitions for all persisted types; `_create_tables()` SQL (called from SqliteStorage). FKs as agreed in 3.1.

### Step 3.5 — Implement SqliteStorage

- **Deliverable:** `SqliteStorage(db_path)` with `_create_tables()`, `save`, `load` (and optional delete/list_ids). Parameterized queries; basic transaction and error handling.

### Step 3.6 — DataLake unified interface

- **Deliverable:** `DataLake` with config (backend + paths), `save_entity` / `load_entity`. Optional `save_entity_obj` / `load_entity_obj` using 3.3.

### Step 3.7 — Integration and unit tests

- **Deliverable:** Unit tests for each storage and DataLake; round-trip per entity type; error cases. Exports from core; short usage note in README or architecture.

---

## Suggested order of execution

1. **3.1** — Persistence scope and serialization contract (no code).
2. **3.2** — JsonStorage (depends on 3.1 for entity_type naming).
3. **3.3** — Entity ↔ dict serialization (depends on 3.1 contract).
4. **3.4** — SQLite schema (depends on 3.1).
5. **3.5** — SqliteStorage (depends on 3.4).
6. **3.6** — DataLake (depends on 3.2, 3.3, 3.5).
7. **3.7** — Integration and unit tests (depends on 3.6).

---

## Files to create or modify

| Action | Path |
|--------|------|
| Create | `core/persistence.py` (JsonStorage, SqliteStorage, DataLake, optional serialization) |
| Create (optional) | `core/serialization.py` (if serialization is split out) |
| Create | `tests/unit/test_persistence.py` |
| Modify | `core/__init__.py` (exports) |
| Create | `task-3/3.1/` through `task-3/3.7/` plan and any spec docs |
