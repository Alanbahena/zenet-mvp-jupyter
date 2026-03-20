# Subtask 17.1 — Verify Restaurant Entity Storage Path

## Goal

Determine how the restaurant entity is stored (typed columns vs JSON blob) to decide
whether `restaurant_description` should be saved on the restaurant entity or the
classification entity. This decision affects every subsequent subtask in Task 17.

---

## Findings (verified 2026-03-19)

### How bienvenida.py saves the restaurant entity

```python
# gradio_app/sections/bienvenida.py, line 60
data_lake.save_entity("restaurant", entity_id, restaurant_to_dict(restaurant))
```

`restaurant_to_dict` (`core/domain/serialization.py`, line 58) produces:
```python
{"id": int, "name": str, "address": str|None, "restaurant_type_id": int|None, "notes": str|None}
```

No `description` field exists.

### How SqliteStorage handles the `restaurant` entity

**Typed columns** (`core/storage/persistence.py`, lines 142–160):

```sql
INSERT INTO restaurant (id, name, address, restaurant_type_id, notes)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    name = excluded.name, address = excluded.address,
    restaurant_type_id = excluded.restaurant_type_id, notes = excluded.notes
```

A `description` field in the dict would be **silently dropped** — only the five named
columns are persisted and loaded.

### SQLite schema for `restaurant`

`core/storage/schema.py`, lines 24–30:

```sql
CREATE TABLE IF NOT EXISTS restaurant (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT,
    restaurant_type_id INTEGER,
    notes TEXT
)
```

No `description` column.

### How SqliteStorage handles the `classification` entity

**Generic JSON blob** (`core/storage/persistence.py`, lines 338–343):

```sql
INSERT INTO classification (id, data) VALUES (?, ?)
ON CONFLICT(id) DO UPDATE SET data = excluded.data
```

The entire dict is serialized with `json.dumps()`. Any extra keys are preserved —
adding `restaurant_description` to the dict just works with zero schema changes.

### How clasificacion.py saves the classification entity

`gradio_app/sections/clasificacion.py`, line 70:

```python
data_lake.save_entity("classification", entity_id, {"standardization_level": level})
```

Only `standardization_level` is saved today. Adding `restaurant_description` to this
dict is a one-line change.

### How _load_configuration_context reads both entities

`gradio_app/sections/configuracion.py`, lines 117–146:

- Loads `restaurant` entity (line 125) → reads `name`, `restaurant_type_id`
- Loads `classification` entity (line 135) → reads `standardization_level`
- Returns a context dict consumed by ConfigurationAgent and ConsistencyCheckAgent

Adding `restaurant_description` from the classification entity requires one line:
```python
"restaurant_description": classification_data.get("restaurant_description", "")
```

---

## Decision

**Store `restaurant_description` in the classification entity** alongside
`standardization_level`.

### Why not the restaurant entity?

Storing on the restaurant entity would require three changes:
1. `ALTER TABLE restaurant ADD COLUMN description TEXT` in `schema.py`
2. Update `SqliteStorage.save` restaurant branch to include description
3. Update `SqliteStorage.load` restaurant branch to return description

Plus updating `restaurant_to_dict` / `restaurant_from_dict` in `serialization.py` and
the `Restaurant` dataclass in `data_model.py`.

### Why the classification entity?

- Zero schema changes — `classification` uses a JSON blob
- Zero persistence.py changes
- `clasificacion.py` already saves and loads the classification entity
- `_load_configuration_context` already loads the classification entity
- One-line change in each of: save, load, and context dict

### Semantic trade-off

`restaurant_description` on the `classification` entity is semantically imprecise —
it describes the restaurant, not the classification. But for MVP this is the pragmatic
choice. If a future task adds a `description` column to the `restaurant` table, the
field should be migrated at that point.

---

## Impact on subsequent subtasks

| Subtask | What this decision means |
|---------|------------------------|
| 17.2 | ClassificationAgent stores `restaurant_description` in `_data_store` — no change needed, this is agent-internal |
| 17.3 | `confirm_fn` saves `restaurant_description` to the **classification** entity dict, not the restaurant entity |
| 17.4 | `_load_configuration_context` reads `restaurant_description` from `classification_data`, not `restaurant_data` |
| 17.5–17.7 | No impact — they consume the context dict regardless of source |
