# Implementation plan: Subtask 3.5 — SQLite storage (SqliteStorage)

## Goal

Implement **SqliteStorage** in `core/persistence.py`: connect to the SQLite database, create tables using the schema from 3.4, and provide `save(entity_type, entity_id, data_dict)` and `load(entity_type, entity_id) -> dict | None` using parameterized queries. Optional `delete` and `list_ids`. Basic transaction and error handling (db locked, disk full).

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| SqliteStorage: `__init__(db_path)`, `_create_tables()`, `save`, `load` | Entity serialization (3.3) |
| Parameterized queries; optional delete, list_ids; error handling | DataLake (3.6) |
| Type conversions (bool, JSON lists), composite keys, recipe normalization | Performance optimization (connection pooling, prepared statements) |

---

## Dependencies

- **3.4** — SQLite schema and `_create_tables()`; SqliteStorage calls it on init.
- **3.1** — Dict shapes define what fields to save/load per entity type.

---

## Breakdown

### 1. SqliteStorage class and __init__(db_path)

- **Location:** `core/persistence.py`.
- **Constructor:** Open or create SQLite DB at `db_path` (e.g. `sqlite3.connect(db_path)`); call `_create_tables(conn)` so schema exists before any save/load.
- **Connection lifecycle:** Keep `self._conn` open for the lifetime of the instance (better performance than open/close per operation). Add optional `close()` method for cleanup.
- **Row factory:** Use `sqlite3.Row` to simplify dict building:
  ```python
  self._conn.row_factory = sqlite3.Row
  ```

### 2. Entity type → table mapping

Each `entity_type` string maps to one or more tables:

| entity_type | Table(s) | Notes |
|-------------|----------|-------|
| `restaurant` | `restaurant` | Simple upsert |
| `user` | `user` | Simple upsert |
| `recipe_unit` | `recipe_unit` | Simple upsert |
| `inventory_unit` | `inventory_unit` | Simple upsert; has bool `is_standard` |
| `category_recipe` | `category_recipe` | Simple upsert |
| `family_inventory` | `family_inventory` | Simple upsert |
| `inventory_item` | `inventory_item` | Simple upsert |
| `recipe` | `recipe` + `recipe_ingredient` | **Normalized**: save/load handle two tables |
| `inventory_unit_equivalence` | `inventory_unit_equivalence` | **Composite key**: `entity_id = "unit_id_inventory_item_id"` |

### 3. save(entity_type, entity_id, data_dict) → None

**Behavior:** Persist `data_dict` for the given entity using **INSERT ... ON CONFLICT** (upsert).

#### 3.1 Simple entities (restaurant, user, etc.)

**Pattern:**
```python
def save(self, entity_type: str, entity_id: int | str, data_dict: dict[str, Any]) -> None:
    cursor = self._conn.cursor()
    
    if entity_type == "restaurant":
        cursor.execute("""
            INSERT INTO restaurant (id, name, address, restaurant_type_id, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                address = excluded.address,
                restaurant_type_id = excluded.restaurant_type_id,
                notes = excluded.notes
        """, (
            data_dict["id"],
            data_dict["name"],
            data_dict.get("address"),
            data_dict.get("restaurant_type_id"),
            data_dict.get("notes")
        ))
        self._conn.commit()
```

**Key points:**
- Use `INSERT ... ON CONFLICT(id) DO UPDATE SET ...` for true upsert (not `INSERT OR REPLACE` which deletes then inserts).
- All columns present even if NULL (matches 3.1 contract: "always write key with null").
- Use `data_dict.get(key)` for optional fields (returns None if missing).

#### 3.2 Type conversions

**bool → INTEGER (0/1):**
```python
# inventory_unit has is_standard (bool)
is_standard_int = 1 if data_dict["is_standard"] else 0
cursor.execute("INSERT INTO inventory_unit (..., is_standard) VALUES (..., ?)", (..., is_standard_int))
```

**list[str] → TEXT (JSON):**
```python
# recipe.steps is list[str] | None
steps_json = json.dumps(data_dict["steps"]) if data_dict.get("steps") is not None else None
cursor.execute("INSERT INTO recipe (..., steps) VALUES (..., ?)", (..., steps_json))
```

#### 3.3 Recipe (normalized: recipe + recipe_ingredient)

**Pattern:**
```python
if entity_type == "recipe":
    # 1. Upsert recipe table (without ingredients)
    steps_json = json.dumps(data_dict["steps"]) if data_dict.get("steps") else None
    cursor.execute("""
        INSERT INTO recipe (id, name, category_id, description, steps)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            category_id = excluded.category_id,
            description = excluded.description,
            steps = excluded.steps
    """, (
        data_dict["id"],
        data_dict["name"],
        data_dict["category_id"],
        data_dict.get("description"),
        steps_json
    ))
    
    # 2. Clear existing ingredients (CASCADE or explicit DELETE)
    cursor.execute("DELETE FROM recipe_ingredient WHERE recipe_id = ?", (data_dict["id"],))
    
    # 3. Insert new ingredients
    for ing_dict in data_dict.get("ingredients", []):
        cursor.execute("""
            INSERT INTO recipe_ingredient (recipe_id, name, quantity, unit_id, inventory_item_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data_dict["id"],
            ing_dict["name"],
            ing_dict["quantity"],
            ing_dict["unit_id"],
            ing_dict.get("inventory_item_id")
        ))
    
    self._conn.commit()
```

**Order:** Recipe first (parent), then ingredients (children). All in one transaction (one commit at end).

#### 3.4 Composite key (inventory_unit_equivalence)

**entity_id format:** `"unit_id_inventory_item_id"` (e.g., `"10_15"`)

**Pattern:**
```python
if entity_type == "inventory_unit_equivalence":
    # Parse composite entity_id
    unit_id, inventory_item_id = map(int, str(entity_id).split("_"))
    
    cursor.execute("""
        INSERT INTO inventory_unit_equivalence (unit_id, inventory_item_id, base_unit_id, factor_to_base)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(unit_id, inventory_item_id) DO UPDATE SET
            base_unit_id = excluded.base_unit_id,
            factor_to_base = excluded.factor_to_base
    """, (
        unit_id,
        inventory_item_id,
        data_dict["base_unit_id"],
        data_dict["factor_to_base"]
    ))
    self._conn.commit()
```

### 4. load(entity_type, entity_id) → dict[str, Any] | None

**Behavior:** Read row(s) for the given entity; reconstruct dict matching 3.1 shape. Return None if not found.

#### 4.1 Simple entities

**Pattern:**
```python
def load(self, entity_type: str, entity_id: int | str) -> dict[str, Any] | None:
    cursor = self._conn.cursor()
    
    if entity_type == "restaurant":
        cursor.execute("SELECT * FROM restaurant WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)  # sqlite3.Row converts to dict with column names as keys
```

**With sqlite3.Row factory:** `dict(row)` gives `{"id": 1, "name": "...", "address": None, ...}`.

#### 4.2 Type conversions

**INTEGER → bool:**
```python
# inventory_unit
row_dict = dict(row)
row_dict["is_standard"] = bool(row_dict["is_standard"])
return row_dict
```

**TEXT (JSON) → list[str]:**
```python
# recipe.steps
row_dict = dict(row)
row_dict["steps"] = json.loads(row_dict["steps"]) if row_dict["steps"] else None
return row_dict
```

#### 4.3 Recipe (join/two queries to rebuild ingredients list)

**Pattern (two SELECTs):**
```python
if entity_type == "recipe":
    # 1. Load recipe row
    cursor.execute("SELECT * FROM recipe WHERE id = ?", (entity_id,))
    recipe_row = cursor.fetchone()
    if recipe_row is None:
        return None
    
    recipe_dict = dict(recipe_row)
    
    # 2. Load ingredients
    cursor.execute("""
        SELECT name, quantity, unit_id, inventory_item_id
        FROM recipe_ingredient
        WHERE recipe_id = ?
        ORDER BY id
    """, (entity_id,))
    ing_rows = cursor.fetchall()
    
    # 3. Build ingredients list
    recipe_dict["ingredients"] = [
        {
            "name": ing["name"],
            "quantity": ing["quantity"],
            "unit_id": ing["unit_id"],
            "inventory_item_id": ing["inventory_item_id"]
        }
        for ing in ing_rows
    ]
    
    # 4. Convert steps (JSON) if not NULL
    recipe_dict["steps"] = json.loads(recipe_dict["steps"]) if recipe_dict["steps"] else None
    
    return recipe_dict
```

**Alternative (JOIN):** Can use LEFT JOIN to get recipe + ingredients in one query, then group by recipe.id. Two SELECTs is simpler and clearer.

#### 4.4 Composite key (inventory_unit_equivalence)

**Pattern:**
```python
if entity_type == "inventory_unit_equivalence":
    # Parse composite entity_id
    unit_id, inventory_item_id = map(int, str(entity_id).split("_"))
    
    cursor.execute("""
        SELECT unit_id, inventory_item_id, base_unit_id, factor_to_base
        FROM inventory_unit_equivalence
        WHERE unit_id = ? AND inventory_item_id = ?
    """, (unit_id, inventory_item_id))
    
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(row)
```

### 5. Optional: delete(entity_type, entity_id) → None

**Pattern:**
```python
def delete(self, entity_type: str, entity_id: int | str) -> None:
    cursor = self._conn.cursor()
    
    if entity_type == "recipe":
        # ON DELETE CASCADE on recipe_ingredient FK auto-deletes ingredients
        cursor.execute("DELETE FROM recipe WHERE id = ?", (entity_id,))
    elif entity_type == "inventory_unit_equivalence":
        unit_id, inventory_item_id = map(int, str(entity_id).split("_"))
        cursor.execute("""
            DELETE FROM inventory_unit_equivalence
            WHERE unit_id = ? AND inventory_item_id = ?
        """, (unit_id, inventory_item_id))
    else:
        # Simple entity: entity_type maps to table name
        table = entity_type  # e.g. "restaurant" → restaurant table
        cursor.execute(f"DELETE FROM {table} WHERE id = ?", (entity_id,))
    
    self._conn.commit()
```

**Note on table name:** For simple entities, `entity_type` string matches table name (per 3.1 naming convention). For recipe, CASCADE handles ingredients; for composite key, use composite WHERE.

### 6. Optional: list_ids(entity_type) → list[str]

**Pattern:**
```python
def list_ids(self, entity_type: str) -> list[str]:
    cursor = self._conn.cursor()
    
    if entity_type == "inventory_unit_equivalence":
        # Composite key: return "unit_id_inventory_item_id"
        cursor.execute("SELECT unit_id, inventory_item_id FROM inventory_unit_equivalence")
        return [f"{row[0]}_{row[1]}" for row in cursor.fetchall()]
    else:
        # Simple entity: return id column as strings
        table = entity_type  # maps to table name
        cursor.execute(f"SELECT id FROM {table}")
        return [str(row[0]) for row in cursor.fetchall()]
```

### 7. Transaction and error handling

#### 7.1 Transactions

- **Pattern:** Each save/delete ends with `self._conn.commit()`.
- **Recipe:** All statements (recipe + delete + insert ingredients) in one transaction; one commit at end.
- **Rollback:** If exception during save, transaction auto-rolls back (SQLite default); no explicit rollback needed unless using manual BEGIN.

#### 7.2 Error handling

**Catch and wrap exceptions:**
```python
import sqlite3

def save(self, entity_type: str, entity_id: int | str, data_dict: dict[str, Any]) -> None:
    try:
        cursor = self._conn.cursor()
        # ... save logic ...
        self._conn.commit()
    except sqlite3.IntegrityError as e:
        # FK violation, unique constraint, NOT NULL, etc.
        raise ValueError(f"Cannot save {entity_type} {entity_id}: {e}") from e
    except sqlite3.OperationalError as e:
        # Database locked, disk full, permission denied
        raise IOError(f"Database error saving {entity_type} {entity_id}: {e}") from e
```

**Don't swallow errors:** Always re-raise (or wrap and raise); never silently catch and return None.

### 8. Implementation checklist

- [ ] Add `sqlite3.Row` factory in `__init__`
- [ ] Implement `save()` for all entity types (9 types + 1 composite)
- [ ] Add type conversions: bool → INTEGER, list[str] → JSON TEXT
- [ ] Implement Recipe save: upsert recipe + delete + insert ingredients
- [ ] Implement composite key save/load: parse `"unit_id_inventory_item_id"`
- [ ] Implement `load()` for all entity types
- [ ] Add type conversions: INTEGER → bool, JSON TEXT → list[str]
- [ ] Implement Recipe load: two SELECTs + build ingredients list
- [ ] Add error handling: catch `IntegrityError` and `OperationalError`
- [ ] Optional: implement `delete()` (handle CASCADE for recipe, composite key)
- [ ] Optional: implement `list_ids()` (handle composite key formatting)
- [ ] Add unit tests in 3.7: round-trip save/load, None on missing, error cases

### 9. Complete entity type implementations

For reference, all entity types and their special handling:

| entity_type | save notes | load notes |
|-------------|------------|------------|
| `restaurant` | Simple upsert | dict(row) |
| `user` | Simple upsert | dict(row) |
| `recipe_unit` | Simple upsert | dict(row) |
| `inventory_unit` | Convert `is_standard` bool → int | Convert `is_standard` int → bool |
| `category_recipe` | Simple upsert | dict(row) |
| `family_inventory` | Simple upsert | dict(row) |
| `inventory_item` | Simple upsert | dict(row) |
| `recipe` | Upsert recipe + delete/insert ingredients; convert `steps` → JSON | Two SELECTs + build ingredients list; convert JSON → `steps` |
| `inventory_unit_equivalence` | Parse composite entity_id; upsert by (unit_id, inventory_item_id) | Parse composite entity_id; SELECT by composite key |

### 10. Example: Complete save() implementation structure

```python
def save(self, entity_type: str, entity_id: int | str, data_dict: dict[str, Any]) -> None:
    try:
        cursor = self._conn.cursor()
        
        if entity_type == "restaurant":
            # ... (see section 3.1)
        elif entity_type == "user":
            # ... (similar to restaurant)
        elif entity_type == "recipe_unit":
            # ... (similar to restaurant)
        elif entity_type == "inventory_unit":
            # ... (with bool → int conversion, see section 3.2)
        elif entity_type == "category_recipe":
            # ...
        elif entity_type == "family_inventory":
            # ...
        elif entity_type == "inventory_item":
            # ...
        elif entity_type == "recipe":
            # ... (see section 3.3)
        elif entity_type == "inventory_unit_equivalence":
            # ... (see section 3.4)
        else:
            raise ValueError(f"Unknown entity_type: {entity_type}")
        
        self._conn.commit()
    
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Cannot save {entity_type} {entity_id}: {e}") from e
    except sqlite3.OperationalError as e:
        raise IOError(f"Database error saving {entity_type} {entity_id}: {e}") from e
```

### 11. Example: Complete load() implementation structure

```python
def load(self, entity_type: str, entity_id: int | str) -> dict[str, Any] | None:
    try:
        cursor = self._conn.cursor()
        
        if entity_type == "restaurant":
            # ... (see section 4.1)
        elif entity_type == "user":
            # ...
        elif entity_type == "recipe_unit":
            # ...
        elif entity_type == "inventory_unit":
            # ... (with int → bool conversion, see section 4.2)
        elif entity_type == "category_recipe":
            # ...
        elif entity_type == "family_inventory":
            # ...
        elif entity_type == "inventory_item":
            # ...
        elif entity_type == "recipe":
            # ... (see section 4.3)
        elif entity_type == "inventory_unit_equivalence":
            # ... (see section 4.4)
        else:
            raise ValueError(f"Unknown entity_type: {entity_type}")
    
    except sqlite3.OperationalError as e:
        raise IOError(f"Database error loading {entity_type} {entity_id}: {e}") from e
```

---

## Deliverable

- **Code:** `save()`, `load()` (and optionally `delete()`, `list_ids()`) methods in `SqliteStorage` class in `core/persistence.py`.
- **Handles:** All 9 entity types (8 simple + recipe normalized + inventory_unit_equivalence composite).
- **Type conversions:** bool ↔ INTEGER, list[str] ↔ JSON TEXT.
- **Error handling:** Catches `IntegrityError` and `OperationalError`; wraps and re-raises.
- **Tests:** Unit tests in 3.7 for round-trip save/load, missing entity (None), error cases.
- **No save/load for entity objects yet:** Still works on dicts only; entity serialization (3.3) is used by caller or DataLake (3.6).
