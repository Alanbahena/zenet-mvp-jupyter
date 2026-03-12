# Subtask 8.2 — Classification Persistence

## Context

Adds the `classification` entity to the SQLite schema and persistence layer.
`confirm_fn` (8.4) calls `data_lake.save_entity("classification", entity_id, dict)` —
without this subtask that call raises `ValueError: Unknown entity_type`.
Tasks 9–12 read this entity to decide which sections show base templates vs. existing data.

**Prior:** 8.1 delivered `ClassificationAgent`; draft lives in `_data_store` (memory only).

**Next:** 8.3 and 8.4 write the confirmed classification dict to DataLake via
`data_lake.save_entity("classification", entity_id, classification_dict)`.

---

## Files to Modify

| File | Action | Summary |
|------|--------|---------|
| `core/storage/schema.py` | Modify | Add `classification` table after `agent_state` |
| `core/storage/persistence.py` | Modify | Add `"classification"` to `_SQLITE_ENTITY_TYPES` + `save`/`load` handlers |

---

## Dependencies

- `core/storage/schema.py` and `core/storage/persistence.py` exist and pass current tests
- No new packages — `sqlite3` and `json` are already imported
- 8.1 complete (not a hard dependency, but classification entity is meaningless without the agent)

---

## Design Decisions

### Decision 1: JSON blob storage

`classification` table uses `id INTEGER PRIMARY KEY, data TEXT NOT NULL`.
No relational queries are needed on classification data — JSON blob is simpler and
consistent with the `agent_state` pattern already in the codebase.

### Decision 2: Integer PK derived from session_id

`entity_id = abs(hash(session_id)) % (2**31 - 1)` — computed by the caller in 8.4,
not by the persistence layer. Same session always maps to the same row, making the
upsert-safe.

### Decision 3: No explicit delete/list_ids branch needed

The generic `else` branch in `SqliteStorage.delete()` (`DELETE FROM {table} WHERE id = ?`)
and `list_ids()` (`SELECT id FROM {table}`) already handle tables with `id INTEGER PRIMARY KEY`.
Only `save` and `load` require explicit `elif` branches due to JSON serialization.

### Decision 4: No dataclass or serialization layer

`classification` is a plain dict throughout (agent draft → confirm → DataLake).
No `save_entity_obj` / `load_entity_obj` support — there is no corresponding dataclass.

---

## Implementation Steps

### 1. `core/storage/schema.py` — Add `classification` table

Add after the `agent_state` block (before the Indexes section):

```python
# 10. Classification entity (JSON blob, keyed by integer session-derived id)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS classification (
        id INTEGER PRIMARY KEY,
        data TEXT NOT NULL
    )
""")
```

### 2. `core/storage/persistence.py` — `_SQLITE_ENTITY_TYPES`

Add `"classification"` to the frozenset:

```python
_SQLITE_ENTITY_TYPES = frozenset({
    ...
    "agent_state",
    "classification",
})
```

### 3. `core/storage/persistence.py` — `save()` handler

Add after the `agent_state` branch:

```python
elif entity_type == "classification":
    cursor.execute(
        "INSERT INTO classification (id, data) VALUES (?, ?) "
        "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
        (int(entity_id), json.dumps(data_dict)),
    )
```

Note: `int(entity_id)` cast handles callers passing a string-encoded integer.
Uses `ON CONFLICT DO UPDATE` consistent with all other upsert handlers in the file.

### 4. `core/storage/persistence.py` — `load()` handler

Add after the `agent_state` branch:

```python
elif entity_type == "classification":
    cursor.execute("SELECT data FROM classification WHERE id = ?", (int(entity_id),))
    row = cursor.fetchone()
    return json.loads(row[0]) if row else None
```

---

## Plan Completeness

| Category | Status |
|----------|--------|
| Unit tests (mocked) | Covered in 8.6 (`test_confirm_fn_persists_classification`) |
| Direct persistence round-trip test | Not in 8.6 test table — see Risks |
| Live/integration tests | Not applicable (no external API) |
| Error handling | Existing `sqlite3.IntegrityError` / `OperationalError` handlers in `save`/`load` cover this |
| Re-exports | Not applicable — no new public classes |
| Status updates | Covered in 8.7 |
| Architecture doc | Covered in 8.7 (`architecture-persistence.md` update) |

---

## Out of Scope

- No changes to `JsonStorage` (handles any entity type generically via file-based path)
- No dataclass or serialization layer for `classification` — plain dict throughout
- No `save_entity_obj` / `load_entity_obj` support (no corresponding dataclass)
- No `schema_version` bump — no migration strategy is defined in this task
- No changes to `DataLake` class

---

## Risks and Open Questions

### [OPEN] — Entity type count mismatch in architecture doc
**Problem:** Parent plan says "9 entity tables → 10" for the `architecture-persistence.md`
update (8.7). Current `_SQLITE_ENTITY_TYPES` already has 10 entries. Adding `classification`
makes it 11.
**Impact:** Architecture doc will be wrong on the first read if the count isn't corrected.
**Suggested action:** In 8.7, update `architecture-persistence.md` to say "10 → 11", not "9 → 10".

### [OPEN] — No direct SqliteStorage round-trip test for classification
**Problem:** 8.6 test table covers `confirm_fn_persists_classification` (exercises DataLake
indirectly) but not a direct `SqliteStorage.save/load` round-trip for `classification`.
**Impact:** A typo in the SQL or a wrong cast in save/load would only surface at UI test time.
**Suggested action:** Add `test_classification_save_load_round_trip` to 8.6 test plan:
`storage.save("classification", 1, dict) → storage.load("classification", 1) == dict`.

---

## Deliverable Checklist

### `core/storage/schema.py`
- [ ] `classification` table added (`id INTEGER PRIMARY KEY, data TEXT NOT NULL`)

### `core/storage/persistence.py`
- [ ] `"classification"` added to `_SQLITE_ENTITY_TYPES`
- [ ] `save()` handler for `classification` (JSON blob, `ON CONFLICT(id) DO UPDATE SET`)
- [ ] `load()` handler for `classification` (`SELECT data → json.loads`)
- [ ] `delete()` and `list_ids()` — verified generic branch handles `classification` (no new branch needed)
