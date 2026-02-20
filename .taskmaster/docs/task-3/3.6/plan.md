# Implementation plan: Subtask 3.6 — DataLake unified interface

## Goal

Implement a **DataLake** (or equivalent) class in `core/persistence.py` that exposes a **single API** for saving and loading data. It can wrap JsonStorage, SqliteStorage, or both (configurable). Optionally provide `save_entity_obj` / `load_entity_obj` that use serialization (3.3) and delegate to the chosen backend.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| DataLake: config (backend type, paths), save_entity / load_entity / delete_entity / list_entity_ids | New backends beyond JSON/SQLite |
| Optional: save_entity_obj / load_entity_obj using 3.3 | Sync/copy between JSON and SQLite (deferred) |
| Resource cleanup (close method, optional context manager) | Thread safety / concurrent access beyond backend limitations |

---

## Dependencies

- **3.2** — JsonStorage (dict-level save/load/delete/list_ids).
- **3.3** — Entity ↔ dict serialization (to_dict, from_dict).
- **3.5** — SqliteStorage (dict-level save/load/delete/list_ids).

---

## Breakdown

### 1. DataLake class and configuration

- **Constructor:** Accept configuration for backend and paths:
  - `backend: Literal["json", "sqlite"]` (or enum).
  - `data_dir: str` for JSON; `db_path: str` for SQLite.
  - **Validation:** Exactly one of `data_dir` or `db_path` must be provided; raise `ValueError` if both or neither.
  - **Behavior:** Instantiate one of JsonStorage or SqliteStorage internally based on which path is set.
- **Storage instance:** Store as private `_storage` attribute; do not expose in public API (or expose only if needed for advanced use).
- **Backend type:** Optionally store `_backend_type` for introspection (e.g., `"json"` or `"sqlite"`).

### 2. Core dict-level methods

#### save_entity / load_entity

- **save_entity:** Accept `data` as a plain dict; call underlying storage's `save(entity_type, entity_id, data)`.
- **load_entity:** Call storage's `load(entity_type, entity_id)`; return `dict | None`.
- **Signature:** `save_entity(self, entity_type: str, entity_id: str | int, data: dict) -> None`; `load_entity(self, entity_type: str, entity_id: str | int) -> dict | None`.

#### delete_entity / list_entity_ids

- **delete_entity:** Delegate to `storage.delete(entity_type, entity_id)`; remove the entity from storage.
- **list_entity_ids:** Delegate to `storage.list_ids(entity_type)`; return `list[str]` of all entity IDs for that type.
- **Signature:** `delete_entity(self, entity_type: str, entity_id: str | int) -> None`; `list_entity_ids(self, entity_type: str) -> list[str]`.

#### close() for resource cleanup

- **close():** If backend is SqliteStorage, call `storage.close()` to close DB connection; no-op for JsonStorage (check with `hasattr(self._storage, 'close')`).
- **Optional enhancement:** Implement `__enter__` / `__exit__` for context manager pattern (`with DataLake(...) as lake: ...`).

### 3. Optional: save_entity_obj / load_entity_obj

#### save_entity_obj

- **save_entity_obj(entity):** Accept a domain object (Restaurant, Recipe, etc.); infer `entity_type` and `entity_id` from the object; call 3.3 `to_dict` for that type; then call `save_entity(entity_type, entity_id, dict)`.
- **Entity type mapping:** Use a dict/registry mapping class type → string:
  - `Restaurant` → `"restaurant"`
  - `Recipe` → `"recipe"`
  - `InventoryUnitEquivalence` → `"inventory_unit_equivalence"`
  - etc. (9 entity types total: restaurant, user, recipe_unit, inventory_unit, category_recipe, family_inventory, inventory_item, recipe, inventory_unit_equivalence)
- **Entity ID extraction:**
  - Simple entities: use `entity.id`
  - `InventoryUnitEquivalence`: construct `f"{entity.unit_id}_{entity.inventory_item_id}"` (composite key)
- **to_dict dispatch:** Use same mapping to call the right serialization function (e.g., `restaurant_to_dict`, `recipe_to_dict`, etc.).
- **Signature:** `save_entity_obj(self, entity: Restaurant | Recipe | User | ...) -> None`.

#### load_entity_obj

- **load_entity_obj(entity_type, entity_id):** Call `load_entity(entity_type, entity_id)`; if `None` return `None`; else call 3.3 `from_dict` for that type and return the entity object.
- **from_dict dispatch:** Use same mapping (entity_type string → from_dict function) to call the right deserialization function.
- **Signature:** `load_entity_obj(self, entity_type: str, entity_id: str | int) -> Restaurant | Recipe | User | ... | None`.

#### Implementation notes

- **Type mapping registry:** Create `_ENTITY_TYPE_TO_CLASS` dict mapping strings to classes and `_CLASS_TO_ENTITY_TYPE` mapping classes to strings.
- **Serialization function registry:** Create dicts mapping entity_type → to_dict/from_dict functions (or use dynamic lookup like `globals()[f"{entity_type}_to_dict"]`).
- **Error handling:** Raise `ValueError` if entity type is unknown or unsupported.

### 4. Single backend strategy

- **MVP:** One backend per DataLake instance (either JSON or SQLite). No automatic sync or copy between them.
- **Strategy:** Use `db_path` if set → SqliteStorage; else use `data_dir` → JsonStorage. Document in docstring.
- **No dual backends:** Do not support reading from one and writing to another in 3.6.

### 5. Error handling

- **Storage errors:** Let underlying storage exceptions bubble up (OSError for JSON, sqlite3 errors for SQLite).
- **Optional wrapper:** Define `PersistenceError` exception class if unified error handling is desired; catch storage errors and re-raise as `PersistenceError` with original as `__cause__`.
- **Serialization errors:** Let 3.3 serialization exceptions bubble up (e.g., `ValueError` for invalid data).
- **For MVP:** Simple approach = let all exceptions bubble; no wrapper.

### 6. Test requirements

- **DataLake with JSON backend:**
  - save_entity / load_entity round-trip (restaurant)
  - delete_entity removes entity
  - list_entity_ids returns saved IDs
  - load missing returns None
- **DataLake with SQLite backend:**
  - save_entity / load_entity round-trip (restaurant, recipe with ingredients)
  - delete_entity removes entity
  - list_entity_ids returns saved IDs
  - close() cleanup
- **Optional save_entity_obj / load_entity_obj:**
  - Round-trip for Restaurant object
  - Round-trip for Recipe object (with ingredients)
  - Round-trip for InventoryUnitEquivalence (composite key)
- **Error cases:**
  - Constructor with both data_dir and db_path raises ValueError
  - Constructor with neither data_dir nor db_path raises ValueError
  - Unknown entity_type in save_entity_obj/load_entity_obj raises ValueError

### 7. Exports

- Export `DataLake` from `core/__init__.py` in 3.7.
- Optionally export `PersistenceError` if implemented.

---

## Notes

- **Concurrency:** DataLake inherits the concurrency limitations of its backend (single-process for JSON, limited for SQLite without WAL mode). Document this limitation.
- **Context manager:** Optional but recommended for clean resource management with SQLite backend.
- **Flexibility:** Design allows future enhancements (dual backends, sync/copy, migration tools) without breaking API.
