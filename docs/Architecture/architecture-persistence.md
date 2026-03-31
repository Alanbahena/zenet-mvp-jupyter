# Persistence Layer Architecture

## 1. Overview

The persistence layer provides save/load functionality for domain entities in the Zenet MVP. It consists of three main components:

- **JsonStorage**: File-based storage using JSON (one file per entity)
- **SqliteStorage**: Database storage using SQLite (tables with relationships)
- **DataLake**: Unified API over either backend with optional object-level operations

The persistence layer operates on plain dictionaries at its core, with optional entity object serialization provided by the `core.serialization` module (see [Serialization](#entity-serialization)).

### When to Use Each Backend

| Use Case | Recommended Backend |
|----------|-------------------|
| Local development | JSON (easy to inspect files) |
| Debugging, sample data | JSON (human-readable, version-controllable) |
| Prototypes, quick demos | JSON (simple, no schema setup) |
| Real application with relationships | SQLite (schema enforcement, foreign keys) |
| Queries like "all recipes in category X" | SQLite (SQL queries available) |
| Single-file deployment | SQLite (one `.db` file) |
| Production (small-medium scale) | SQLite (robust, transactions) |

---

## 2. Storage Backends

### JsonStorage

Stores each entity as a separate JSON file in a directory:

**File naming:** `{entity_type}_{entity_id}.json`

**Example:** Restaurant with id=1 → `restaurant_1.json`

```python
from core import JsonStorage

storage = JsonStorage(data_dir="data/json")

# Save entity dict
storage.save("restaurant", 1, {
    "id": 1,
    "name": "La Pizzeria",
    "address": "Calle Main 123",
    "restaurant_type_id": 1,
    "notes": None
})

# Load entity dict
data = storage.load("restaurant", 1)  # dict | None

# Delete entity
storage.delete("restaurant", 1)

# List all entity IDs for type
ids = storage.list_ids("restaurant")  # list[str]
```

**Characteristics:**
- Human-readable: Open files in any text editor
- No schema: Any dict structure accepted
- No queries: Load each file individually
- No relationships: No enforcement of foreign keys
- Concurrency: Single-process only (no file locking)

**Error handling:**
- Missing file → returns `None`
- Corrupt/invalid JSON → raises `json.JSONDecodeError`
- Permission errors, disk full → raises `OSError`

---

### SqliteStorage

Stores entities in a single SQLite database file with tables and relationships:

**Schema:** Defined in `core/schema.py` (10 entity tables + recipe_ingredient junction table)

```python
from core import SqliteStorage

storage = SqliteStorage(db_path="data/app.db")

# Save entity dict (validates foreign keys)
storage.save("restaurant", 1, {
    "id": 1,
    "name": "La Pizzeria",
    "address": "Calle Main 123",
    "restaurant_type_id": 1,
    "notes": None
})

# Load entity dict
data = storage.load("restaurant", 1)  # dict | None

# Delete entity (CASCADE for recipe ingredients)
storage.delete("restaurant", 1)

# List all entity IDs for type
ids = storage.list_ids("restaurant")  # list[str]

# Close connection when done
storage.close()
```

**Characteristics:**
- Structured: Schema enforced (columns, types, foreign keys)
- Single file: One `.db` file for all data
- Queryable: SQL available (though not exposed in MVP API)
- Relationships: Foreign key constraints enforced
- Transactions: ACID guarantees
- Concurrency: Limited (single writer; WAL mode not enabled in MVP)

**Special handling:**
- **Recipe:** Saved to `recipe` table; ingredients saved to `recipe_ingredient` junction table

**Error handling:**
- Missing entity → returns `None`
- Unknown entity_type → raises `ValueError`
- Foreign key violation → raises `ValueError` (wrapped from `sqlite3.IntegrityError`)
- DB locked, permission errors → raises `OSError` (wrapped from `sqlite3.OperationalError`)

---

## 3. DataLake Unified API

DataLake provides a single interface that works with either JSON or SQLite backend. Choose your backend once at instantiation; all subsequent operations use the same API regardless of backend.

### Instantiation

**Exactly one** of `data_dir` or `db_path` must be provided:

```python
from core import DataLake

# JSON backend
lake = DataLake(data_dir="data/json")

# SQLite backend
lake = DataLake(db_path="data/app.db")

# Both or neither → ValueError
```

**Context manager (recommended for SQLite):**

```python
with DataLake(db_path="data/app.db") as lake:
    lake.save_entity("restaurant", 1, data)
    # ... more operations
# Automatically calls lake.close() on exit
```

---

### Dict-Level API

Work with plain Python dictionaries (no entity classes required):

```python
# Save entity as dict
restaurant_data = {
    "id": 1,
    "name": "La Pizzeria",
    "address": "Calle Main 123",
    "restaurant_type_id": 1,
    "notes": None
}
lake.save_entity("restaurant", 1, restaurant_data)

# Load entity dict (returns None if missing)
data = lake.load_entity("restaurant", 1)  # dict | None

if data:
    print(data["name"])  # "La Pizzeria"

# Delete entity
lake.delete_entity("restaurant", 1)

# List all IDs for entity type
ids = lake.list_entity_ids("restaurant")  # ["1", "2", ...]

# Close resources (required for SQLite; no-op for JSON)
lake.close()
```

---

### Object-Level API

Work with domain objects; DataLake automatically converts using `to_dict`/`from_dict` from `core.serialization`:

```python
from core import DataLake, Restaurant

lake = DataLake(data_dir="data/json")

# Save domain object (auto-converts with restaurant_to_dict)
restaurant = Restaurant(
    id=1,
    name="La Pizzeria",
    address="Calle Main 123",
    restaurant_type_id=1,
    notes=None
)
lake.save_entity_obj(restaurant)

# Load as domain object (auto-converts with restaurant_from_dict)
loaded = lake.load_entity_obj("restaurant", 1)  # Restaurant | None

if loaded:
    print(loaded.name)  # "La Pizzeria"
    print(type(loaded))  # <class 'core.data_model.Restaurant'>
```

**Supported entity types (10 total):**
- `Restaurant`, `User`, `RecipeUnit`, `InventoryUnit`
- `CategoryRecipe`, `FamilyInventory`, `InventoryItem`
- `Recipe` (with embedded `Ingredient` list)
- `agent_state` — JSON blob only (dict-level API); schema: `session_id` (str key) + `data TEXT`
- `classification` — JSON blob only (dict-level API); schema: `{"standardization_level": 1|2|3}`

**Note:** `InventoryUnitEquivalence` was removed in Task 11. Purchase-to-stock conversion is
now stored directly on `InventoryItem` via `purchase_unit_id` and `purchase_to_stock_factor`.

**Note:** `agent_state` and `classification` do not have domain object classes or
`to_dict`/`from_dict` serializers. Use the dict-level API (`save_entity` / `load_entity`)
for these types — `save_entity_obj` / `load_entity_obj` will raise `KeyError`.

**Example with Recipe:**

```python
from core import DataLake, Recipe, Ingredient

lake = DataLake(db_path="data/app.db")

# Create recipe with ingredients
recipe = Recipe(
    id=1,
    name="Tacos",
    category_id=2,
    description="Tacos al pastor",
    steps=["Marinar carne", "Cortar", "Servir"],
    ingredients=[
        Ingredient(name="Carne", quantity=500.0, unit_id=1, inventory_item_id=5),
        Ingredient(name="Tortillas", quantity=12.0, unit_id=3, inventory_item_id=10),
    ]
)

# Save (converts to dict, saves to 'recipe' + 'recipe_ingredient' tables)
lake.save_entity_obj(recipe)

# Load (reads from DB, converts back to Recipe object)
loaded_recipe = lake.load_entity_obj("recipe", 1)  # Recipe | None
```

---

## 4. Error Handling

### JsonStorage Errors

```python
storage = JsonStorage("data/json")

# Missing file → None (expected)
data = storage.load("restaurant", 999)  # None

# Corrupt JSON → raises
try:
    data = storage.load("restaurant", 1)  # File contains "{invalid"
except json.JSONDecodeError as e:
    print(f"Corrupt JSON: {e}")

# Permission error → raises
try:
    storage.save("restaurant", 1, data)  # Directory is read-only
except OSError as e:
    print(f"IO error: {e}")
```

### SqliteStorage Errors

```python
storage = SqliteStorage("data/app.db")

# Missing entity → None (expected)
data = storage.load("restaurant", 999)  # None

# Unknown entity type → raises
try:
    storage.save("unknown_type", 1, {})
except ValueError as e:
    print(f"Unknown type: {e}")  # "Unknown entity_type: unknown_type"

# Foreign key violation → raises
try:
    storage.save("recipe", 1, {"id": 1, "name": "X", "category_id": 999, ...})
except ValueError as e:
    print(f"FK violation: {e}")  # Wrapped IntegrityError

# DB locked → raises
try:
    data = storage.load("restaurant", 1)  # DB file locked by another process
except OSError as e:
    print(f"DB error: {e}")  # Wrapped OperationalError
```

### DataLake Errors

DataLake inherits backend errors (no wrapper exceptions):

```python
lake = DataLake(data_dir="data/json")

# Constructor validation
try:
    lake = DataLake(data_dir="x", db_path="y")  # Both provided
except ValueError as e:
    print(e)  # "Provide exactly one of data_dir or db_path"

try:
    lake = DataLake()  # Neither provided
except ValueError as e:
    print(e)  # "Provide exactly one of data_dir or db_path"

# Unknown type in obj API
try:
    lake.save_entity_obj("not an entity")
except ValueError as e:
    print(e)  # "Unknown entity type for save_entity_obj: str"

try:
    lake.load_entity_obj("unknown_type", 1)
except ValueError as e:
    print(e)  # "Unknown entity_type for load_entity_obj: unknown_type"
```

---

## 5. Testing Patterns

### Temporary Directories for JSON

```python
import tempfile
import unittest

class TestMyFeature(unittest.TestCase):
    def test_save_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lake = DataLake(data_dir=tmpdir)
            lake.save_entity("restaurant", 1, {"id": 1, "name": "Test"})
            data = lake.load_entity("restaurant", 1)
            self.assertEqual(data["name"], "Test")
        # tmpdir auto-deleted on exit
```

### Temporary DB for SQLite

```python
import os
import tempfile
import unittest

class TestMyFeature(unittest.TestCase):
    def test_save_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            lake = DataLake(db_path=db_path)
            lake.save_entity("restaurant", 1, {"id": 1, "name": "Test", ...})
            data = lake.load_entity("restaurant", 1)
            self.assertEqual(data["name"], "Test")
            lake.close()
        # DB file auto-deleted with tmpdir
```

### In-Memory SQLite (faster tests)

```python
# Use ":memory:" for ephemeral DB (not persisted to disk)
storage = SqliteStorage(":memory:")
# All operations work; data is lost when connection closes
```

---

## 6. Implementation Files

| File | Contents |
|------|----------|
| `core/persistence.py` | JsonStorage, SqliteStorage, DataLake classes |
| `core/schema.py` | `_create_tables()` function with SQLite schema (DDL) |
| `core/serialization.py` | `to_dict`/`from_dict` functions for all 9 entity types |
| `core/data_model.py` | Domain entity dataclasses (Restaurant, Recipe, etc.) |
| `tests/unit/test_persistence.py` | Unit tests for storage and DataLake (46 tests) |
| `tests/unit/test_serialization.py` | Unit tests for to_dict/from_dict round-trips (15 tests) |

---

## 7. Design Decisions

### Single Backend Per Instance

Each `DataLake` instance uses **one** backend (JSON or SQLite). There is no automatic sync or dual-backend mode.

**Rationale:**
- Simplifies implementation and error handling
- Avoids ambiguity (which backend is "source of truth"?)
- Keeps API surface small and predictable

**Future:** Sync/migration tools can be added later as separate utilities.

---

### Dict-Level vs Object-Level APIs

**Dict-level (`save_entity`/`load_entity`):**
- Lower-level, more flexible
- No dependency on entity classes
- Useful for generic tools, migrations, admin interfaces

**Object-level (`save_entity_obj`/`load_entity_obj`):**
- Higher-level, more convenient
- Type-safe with IDE autocomplete
- Useful for application code

**Recommendation:** Use object-level API in application code; use dict-level for utilities.

---

### No Query Interface (Yet)

SqliteStorage has a DB with queryable tables, but no query API is exposed in the MVP.

**Rationale:**
- Keep persistence layer simple (save/load/delete/list only)
- Avoid exposing SQL directly (prevents SQL injection, keeps abstraction clean)
- Queries can be added as methods later (e.g., `find_recipes_by_category(category_id)`)

**Future:** Add query methods to DataLake or a separate "Repository" layer.

---

### Concurrency Limitations

**JsonStorage:**
- Single-process only
- No file locking
- Concurrent writes → data corruption

**SqliteStorage:**
- Single writer at a time (default SQLite behavior)
- Multiple readers OK
- WAL mode not enabled (could improve concurrency)

**Recommendation:** For multi-user production, migrate to PostgreSQL or enable SQLite WAL mode.

---

### Composite Keys

Only `InventoryUnitEquivalence` uses a composite key:

**Format:** `"{unit_id}_{inventory_item_id}"` (e.g., `"10_15"`)

**Rationale:**
- Matches the composite primary key in the schema
- Allows string-based entity_id for consistency with other types

**Implementation:** Save/load parse the composite string; storage handles normally.

---

## 8. Entity Serialization

The `core.serialization` module provides `to_dict`/`from_dict` functions for converting between domain objects and plain dicts. These are used internally by DataLake's object-level API.

**Available functions:**

```python
from core.serialization import (
    restaurant_to_dict, restaurant_from_dict,
    user_to_dict, user_from_dict,
    recipe_unit_to_dict, recipe_unit_from_dict,
    inventory_unit_to_dict, inventory_unit_from_dict,
    category_recipe_to_dict, category_recipe_from_dict,
    family_inventory_to_dict, family_inventory_from_dict,
    inventory_item_to_dict, inventory_item_from_dict,
    recipe_to_dict, recipe_from_dict,  # Includes ingredients
    inventory_unit_equivalence_to_dict, inventory_unit_equivalence_from_dict,
    recipe_unit_conversion_to_dict, recipe_unit_conversion_from_dict,
)
```

**Example:**

```python
from core import Restaurant, restaurant_to_dict, restaurant_from_dict

# Object → Dict
restaurant = Restaurant(id=1, name="La Pizzeria", address="Calle 1", restaurant_type_id=1, notes=None)
data = restaurant_to_dict(restaurant)
# data == {"id": 1, "name": "La Pizzeria", "address": "Calle 1", "restaurant_type_id": 1, "notes": None}

# Dict → Object
restored = restaurant_from_dict(data)
# restored == Restaurant(id=1, name="La Pizzeria", ...)
```

**See also:** [Data Model Architecture](architecture-data-model.md) for entity definitions.

---

### recipe_unit_conversion

Added in Task 10. Stores per-ingredient recipe unit → mass/volume equivalents confirmed
during the Alineamiento section.

**SQLite-only** — in `_SQLITE_ENTITY_TYPES`. JSON backend does not support it.

**Composite key:** entity id is a string `"{recipe_unit_id}_{family_id}_{inventory_item_id}"`.
`family_id` and `inventory_item_id` are nullable (stored as `None` in Python; `NULL` in SQLite).

**Schema (from `core/storage/schema.py`):**

```sql
CREATE TABLE IF NOT EXISTS recipe_unit_conversion (
    recipe_unit_id    INTEGER NOT NULL,
    family_id         INTEGER,
    inventory_item_id INTEGER,
    quantity          REAL NOT NULL,
    base_unit_id      INTEGER NOT NULL,
    source            TEXT NOT NULL DEFAULT 'agent_estimated',
    PRIMARY KEY (recipe_unit_id, family_id, inventory_item_id)
)
```

**Serialization:**

```python
from core.domain.serialization import (
    recipe_unit_conversion_to_dict,   # (entry, key) -> dict
    recipe_unit_conversion_from_dict, # dict -> (key, entry)
)
```

`recipe_unit_conversion_to_dict(entry, key)` returns:

```python
{
    "recipe_unit_id":    key.recipe_unit_id,
    "family_id":         key.family_id,        # None if item-specific only
    "inventory_item_id": key.inventory_item_id,
    "quantity":          entry.quantity,
    "base_unit_id":      entry.base_unit_id,
    "source":            entry.source,         # "operator" | "agent_confirmed" | "agent_estimated"
}
```

---

## Summary

The persistence layer provides flexible, backend-agnostic storage for Zenet MVP entities:

- **JsonStorage** for simple file-based storage (dev, demos, debugging)
- **SqliteStorage** for structured database storage (real app, relationships)
- **DataLake** for unified API over either backend (dict or object level)

Choose JSON for simplicity and readability; choose SQLite for structure and integrity. DataLake lets you switch backends with a single line of code.
