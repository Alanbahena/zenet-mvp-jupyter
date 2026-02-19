# Implementation plan: Subtask 3.7 — Integration and unit tests

## Goal

Wire serialization (3.3) to storage (3.2, 3.5) and DataLake (3.6). Add **unit tests** for round-trip save/load per entity type on both JSON and SQLite, and for error cases (missing file, corrupt JSON, invalid DB). Document usage (e.g. in README or docs/Architecture) for DataLake and any convenience helpers. Export persistence and serialization from `core/__init__.py`.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| Tests in tests/unit/test_persistence.py (or similar); round-trip integrity; error paths | E2E or multi-user tests |
| Exports from core/__init__.py; short usage note in README or architecture doc | Performance/load testing |

---

## Dependencies

- **3.2** — JsonStorage.
- **3.3** — Entity to_dict/from_dict.
- **3.4** — Schema (used by 3.5).
- **3.5** — SqliteStorage.
- **3.6** — DataLake.

---

## Breakdown

### 1. Unit tests: JsonStorage

- **Round-trip:** Create JsonStorage with temp dir; save a dict for (entity_type, entity_id); load and assert equality.
- **Missing file:** load for non-existent id returns None.
- **Invalid JSON:** If test writes a corrupt file, load raises (or returns None per 3.2 contract); document and test.

### 2. Unit tests: SqliteStorage

- **Round-trip:** Create SqliteStorage with temp DB path; save dict, load, assert equality.
- **Missing entity:** load for unknown entity_id returns None.
- **Error:** Invalid path or locked DB (if feasible to simulate) raises; assert exception type or message.

### 3. Unit tests: serialization (3.3)

- For each entity type: create an entity instance (using data model); call to_dict; call from_dict on that dict; assert result is equivalent (same id, same key fields). Optionally compare with original entity.

### 4. Unit tests: DataLake

- **With JSON backend:** DataLake(backend="json", data_dir=…); save_entity / load_entity round-trip.
- **With SQLite backend:** DataLake(backend="sqlite", db_path=…); save_entity / load_entity round-trip.
- **Optional save_entity_obj / load_entity_obj:** Build entity, save_entity_obj; load_entity_obj; assert entity equality (by id and key fields).

### 5. Round-trip per entity type

- For at least Recipe, Ingredient, Restaurant, InventoryItem (and others as time allows): create entity → to_dict → save via DataLake (JSON and/or SQLite) → load → from_dict → assert equivalent to original. This validates 3.1 + 3.3 + 3.6 together.

### 6. Exports

- In `core/__init__.py`: export `JsonStorage`, `SqliteStorage`, `DataLake`, and the to_dict/from_dict functions (or serialization module) so callers can do `from core import DataLake, recipe_to_dict, recipe_from_dict`, etc.

### 7. Documentation

- **Usage note:** Short section in README or in `docs/Architecture` explaining: how to instantiate DataLake (JSON vs SQLite), how to save/load entities (dict or object API), and where persistence lives (core/persistence.py). No need for full API reference; enough for a developer to get started.

### 8. Deliverable

- **Tests:** `tests/unit/test_persistence.py` (and optionally `test_serialization.py` if split).
- **Exports:** `core/__init__.py` updated.
- **Docs:** README or architecture doc updated with usage.
