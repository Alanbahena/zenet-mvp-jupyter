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

- **Convention:** One file per entity: `{entity_type}_{entity_id}.json` (e.g. `recipe_abc123.json`). Use a safe filename if `entity_id` contains path characters (e.g. sanitize or use base64); document in code.
- **Encoding:** UTF-8; `json.dumps(..., ensure_ascii=False)` for readability if needed.

### 3. save(entity_type, entity_id, data_dict)

- **Behavior:** Write `data_dict` to `{data_dir}/{entity_type}_{entity_id}.json`.
- **Implementation:** Open file in write mode, `json.dump(data_dict, f, indent=2)` (or no indent for smaller files); handle IOError and re-raise or log.

### 4. load(entity_type, entity_id) -> dict | None

- **Behavior:** Read JSON from the corresponding file; return the dict. If file is missing, return `None`. If file exists but JSON is invalid, raise (or log and raise).
- **Implementation:** Check `os.path.exists` or use try/except on open; `json.load(f)`; return None only for missing file.

### 5. Optional: delete and list_ids

- **delete(entity_type, entity_id):** Remove the file if it exists; no-op if missing.
- **list_ids(entity_type):** Glob or listdir for `{entity_type}_*.json`, extract entity_id from each filename, return list of ids.

### 6. Error handling

- **Missing file:** Return None from `load`.
- **Invalid JSON / corrupt file:** Raise `ValueError` or `json.JSONDecodeError` with clear message.
- **IO (permission, disk full):** Let `IOError` propagate or wrap in a small persistence-specific exception.

### 7. Exports and tests

- **Exports:** Add `JsonStorage` to `core/__init__.py` when done (can be in 3.7).
- **Unit tests:** In 3.7; for 3.2, a minimal test can create JsonStorage, save a dict, load it, assert equality.
