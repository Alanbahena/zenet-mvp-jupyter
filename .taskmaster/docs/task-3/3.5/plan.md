# Implementation plan: Subtask 3.5 — SQLite storage (SqliteStorage)

## Goal

Implement **SqliteStorage** in `core/persistence.py`: connect to the SQLite database, create tables using the schema from 3.4, and provide `save(entity_type, entity_id, data_dict)` and `load(entity_type, entity_id) -> dict | None` using parameterized queries. Optional `delete` and `list_ids`. Basic transaction and error handling (db locked, disk full).

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| SqliteStorage: `__init__(db_path)`, `_create_tables()`, `save`, `load` | Entity serialization (3.3) |
| Parameterized queries; optional delete, list_ids; error handling | DataLake (3.6) |

---

## Dependencies

- **3.4** — SQLite schema and `_create_tables()`; SqliteStorage calls it on init.

---

## Breakdown

### 1. SqliteStorage class and __init__(db_path)

- **Location:** `core/persistence.py`.
- **Constructor:** Open or create SQLite DB at `db_path` (e.g. `sqlite3.connect(db_path)`); call `_create_tables(conn)` so schema exists before any save/load.
- **Connection:** Keep connection open for the lifetime of the instance, or open per operation (simpler for concurrency); document choice.

### 2. save(entity_type, entity_id, data_dict)

- **Behavior:** Persist `data_dict` for the given entity. Implementation depends on schema:
  - **Option A:** One table per entity_type; column names match dict keys; INSERT OR REPLACE (upsert) by entity_id.
  - **Option B:** Single key-value table (entity_type, entity_id, data_json); store dict as JSON string.
- Use **parameterized queries** (e.g. `?` or `:key`) to avoid SQL injection; never concatenate entity_id or dict values into SQL.
- **Nested structures:** If schema stores ingredients etc. as JSON blob, serialize that part with `json.dumps`; if normalized, insert into related tables and link by FK.

### 3. load(entity_type, entity_id) -> dict | None

- **Behavior:** Read row(s) for the given entity; reconstruct dict and return. If not found, return None.
- **Implementation:** SELECT by entity_type and entity_id; build dict from row(s); if schema uses JSON column, `json.loads` that part.
- Use parameterized query for entity_id.

### 4. Optional: delete(entity_type, entity_id) and list_ids(entity_type)

- **delete:** DELETE FROM … WHERE entity_type = ? AND entity_id = ? (or equivalent per schema).
- **list_ids:** SELECT entity_id FROM … WHERE entity_type = ?; return list of ids.

### 5. Transaction and error handling

- **Transactions:** Use `conn.commit()` after save/delete; optional explicit `BEGIN`/`COMMIT` for multi-row writes.
- **Errors:** Catch `sqlite3.OperationalError` (e.g. disk full, db locked); re-raise with clear message or wrap in persistence exception. Do not swallow errors.

### 6. Exports and tests

- Export `SqliteStorage` from `core/__init__.py` (in 3.7). Unit tests in 3.7: round-trip save/load, missing entity returns None, invalid path or locked DB raises.
