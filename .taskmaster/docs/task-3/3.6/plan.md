# Implementation plan: Subtask 3.6 — DataLake unified interface

## Goal

Implement a **DataLake** (or equivalent) class in `core/persistence.py` that exposes a **single API** for saving and loading data. It can wrap JsonStorage, SqliteStorage, or both (configurable). Optionally provide `save_entity_obj` / `load_entity_obj` that use serialization (3.3) and delegate to the chosen backend.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| DataLake: config (backend type, paths), save_entity / load_entity | New backends beyond JSON/SQLite |
| Optional: save_entity_obj / load_entity_obj using 3.3 | Sync/copy between JSON and SQLite (deferred) |

---

## Dependencies

- **3.2** — JsonStorage (dict-level save/load).
- **3.3** — Entity ↔ dict serialization (to_dict, from_dict).
- **3.5** — SqliteStorage (dict-level save/load).

---

## Breakdown

### 1. DataLake class and configuration

- **Constructor:** Accept configuration for backend and paths, e.g.:
  - `backend: Literal["json", "sqlite"]` (or enum).
  - `data_dir: str` for JSON; `db_path: str` for SQLite.
- **Behavior:** Instantiate one of JsonStorage or SqliteStorage internally based on config; do not expose storage instance in the public API (or expose only if needed for advanced use).

### 2. save_entity(entity_type, entity_id, data) and load_entity(entity_type, entity_id)

- **save_entity:** Accept `data` as a plain dict; call underlying storage’s `save(entity_type, entity_id, data)`.
- **load_entity:** Call storage’s `load(entity_type, entity_id)`; return `dict | None`.
- **Signature:** e.g. `save_entity(self, entity_type: str, entity_id: str, data: dict) -> None`; `load_entity(self, entity_type: str, entity_id: str) -> dict | None`.

### 3. Optional: save_entity_obj / load_entity_obj

- **save_entity_obj(entity):** Infer entity_type and entity_id from the object (e.g. from type and entity.id); call 3.3 to_dict for that type; then save_entity(entity_type, entity_id, dict).
- **load_entity_obj(entity_type, entity_id):** load_entity(entity_type, entity_id); if None return None; else call 3.3 from_dict for that type and return the entity object.
- **Entity type dispatch:** Map type(entity) or explicit entity_type string to the right to_dict/from_dict function (e.g. registry or if/elif).

### 4. Single backend or strategy

- **MVP:** One backend per DataLake instance (either JSON or SQLite). No automatic sync or copy between them.
- **Optional:** Simple strategy, e.g. “use SQLite if db_path is set, else use JSON”; document in docstring.

### 5. Error handling and exports

- Propagate errors from underlying storage (IO, DB errors); optional wrapper exception `PersistenceError` for callers.
- Export `DataLake` from `core/__init__.py` in 3.7.
