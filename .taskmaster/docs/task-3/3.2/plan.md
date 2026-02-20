# Implementation plan: Subtask 3.2 — JSON storage (JsonStorage)

## Goal

Implement `core/persistence.py` with a **JsonStorage** class that saves and loads entity data as JSON files. One file per entity instance (e.g. `{entity_type}_{entity_id}.json`). The class operates on **plain dicts only**; no entity objects. This provides a simple, file-based backend for the persistence layer.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| JsonStorage: `__init__(data_dir)`, `save(entity_type, entity_id, data_dict)`, `load(entity_type, entity_id) -> dict \| None` | Serialization of entity objects (3.3) |
| Optional: `delete(entity_type, entity_id)`, `list_ids(entity_type) -> list` | DataLake or unified API (3.6) |
| File layout and naming; `os.makedirs(data_dir, exist_ok=True)`; error handling (missing file, invalid JSON, IO) | SQLite (3.4, 3.5) |

---

## Dependencies

- **3.1** — Persistence scope and serialization contract: use agreed `entity_type` and `entity_id` semantics; dict shape is defined there (this class just stores/retrieves dicts).

---

## Breakdown

### 1. Create core/persistence.py and JsonStorage class

- **Location:** `core/persistence.py`.
- **Constructor:** `__init__(self, data_dir: str)` — store `data_dir`; ensure directory exists with `os.makedirs(data_dir, exist_ok=True)`.

### 2. File layout and naming

- **Convention:** One file per entity: `{entity_type}_{entity_id}.json` (e.g. `recipe_42.json`, `inventory_unit_equivalence_10_15.json`).
- **Entity ID format:**
  - **Simple entities** (Restaurant, Recipe, InventoryItem, etc.): `entity_id` is an integer; convert to string for filename.
  - **Composite keys** (InventoryUnitEquivalence): `entity_id` is a string like `"10_15"` (format: `"{unit_id}_{inventory_item_id}"`); use directly in filename.
  - **No sanitization needed:** entity_id is always integer or safe composite string (no path separators or special chars).
- **Encoding:** UTF-8 with `ensure_ascii=False` for readability (so accented characters like "Lácteos" appear as-is in JSON).

### 3. save(entity_type, entity_id, data_dict)

- **Behavior:** Write `data_dict` to `{data_dir}/{entity_type}_{entity_id}.json`.
- **Implementation:**
  - Open file in write mode: `open(path, "w", encoding="utf-8")`.
  - Write JSON with `json.dump(data_dict, f, indent=2, ensure_ascii=False)`.
  - **Indent:** Always use `indent=2` for human readability, version control diffs, and debugging (MVP priority).
  - Handle `IOError` and re-raise or wrap in persistence exception.

### 4. load(entity_type, entity_id) -> dict | None

- **Behavior:** Read JSON from the corresponding file; return the dict. If file is missing, return `None`. If file exists but JSON is invalid, raise (or log and raise).
- **Implementation:**
  - Open file in read mode: `open(path, "r", encoding="utf-8")`.
  - Use try/except on open to catch `FileNotFoundError` → return `None`.
  - Use `json.load(f)` to parse; if invalid JSON, let `json.JSONDecodeError` propagate or wrap with context.

### 5. Optional: delete and list_ids

- **delete(entity_type, entity_id):** Remove the file if it exists; no-op if missing (`os.remove` or `os.unlink` with try/except).
- **list_ids(entity_type):** Glob or listdir for `{entity_type}_*.json`, extract entity_id from each filename, return list of ids (as strings).
  - **For composite keys** (e.g. InventoryUnitEquivalence): returns strings like `"10_15"`, matching the format used in `save`/`load` calls.

### 6. Error handling

- **Missing file:** Return `None` from `load`.
- **Invalid JSON / corrupt file:** Raise `ValueError` or `json.JSONDecodeError` with clear message.
- **IO errors (permission, disk full):** Let `IOError` propagate or wrap in a small persistence-specific exception.
- **Concurrent access:** JsonStorage does **not** handle concurrent writes (no locking). For MVP, assume single-user/single-process; last write wins if multiple processes save the same entity. File locking is deferred.
- **Atomic writes:** Direct write (no temp-file-then-rename); if system crashes mid-save, file may be corrupt. Out of scope for 3.2; can be added later if needed.

### 7. Exports and tests

- **Exports:** Add `JsonStorage` to `core/__init__.py` when done (can be in 3.7).
- **Minimal smoke test (in 3.2):** Create `tests/unit/test_persistence.py` with a simple test: instantiate JsonStorage with temp dir, save a dict, load it, assert equality. Verifies basic save/load works.
- **Full test coverage (in 3.7):** Round-trip for all entity types, error cases (missing file, corrupt JSON, invalid path), `delete`, `list_ids`.

---

## Implementation details

### Composite key handling (InventoryUnitEquivalence)

- **entity_id format:** `"{unit_id}_{inventory_item_id}"` (e.g. `"10_15"`).
- **Filename:** `inventory_unit_equivalence_10_15.json`.
- **list_ids:** Returns strings like `["10_15", "10_16", ...]`.

### UTF-8 encoding

- **save:** `open(path, "w", encoding="utf-8")` + `json.dump(data_dict, f, indent=2, ensure_ascii=False)`.
- **load:** `open(path, "r", encoding="utf-8")` + `json.load(f)`.

### JSON formatting

- **indent=2:** Always indent for readability, version control, and debugging. Compact JSON is out of scope for 3.2.

### Concurrency and atomicity (deferred)

- **No locking:** Assumes single-user/single-process for MVP.
- **No atomic writes:** Direct write; file may be corrupt if crash mid-save. Can be improved later (write to temp file + rename).
