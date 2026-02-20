# Implementation plan: Subtask 3.7 — Integration and unit tests

## Goal

Complete testing coverage for persistence layer (3.2, 3.5, 3.6) and serialization (3.3). Add comprehensive unit tests for all entity types, error cases, and full-stack integration. Create architecture documentation for persistence layer. Ensure all exports are in `core/__init__.py`.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| Tests in tests/unit/test_persistence.py and test_serialization.py; round-trip integrity for all 9 entity types; error paths | E2E or multi-user tests |
| Architecture documentation (docs/Architecture/architecture-persistence.md); README updates | Performance/load testing |
| Corrupt JSON handling; SQLite error cases | Migration tools or multi-backend sync |

---

## Dependencies

- **3.2** — JsonStorage.
- **3.3** — Entity to_dict/from_dict.
- **3.4** — Schema (used by 3.5).
- **3.5** — SqliteStorage.
- **3.6** — DataLake.

---

## Current Status (what's already done)

From subtasks 3.2-3.6, the following are **already complete**:

- ✅ **JsonStorage tests:** Round-trip, missing file, composite keys, delete, list_ids (TestJsonStorage - 8 tests)
- ✅ **SqliteStorage tests:** Round-trip, missing entity, schema creation, recipe with ingredients, composite keys (TestSqliteStorageSchema + TestSqliteStorageSaveLoad - 15 tests)
- ✅ **DataLake tests:** JSON/SQLite backends, dict-level API, obj-level API, context manager, error cases (TestDataLake - 18 tests)
- ✅ **Serialization tests (partial):** Recipe and Restaurant round-trip (4 tests)
- ✅ **Exports:** DataLake, JsonStorage, SqliteStorage, and all to_dict/from_dict functions in core/__init__.py

**Total existing:** 45 tests passing

---

## Breakdown (what remains for 3.7)

### 1. Enhanced JsonStorage tests

**Status:** Mostly complete; missing corrupt JSON handling

- ✅ Round-trip (existing)
- ✅ Missing file returns None (existing)
- ➕ **NEW: Corrupt JSON test:** Write invalid JSON to a file; verify that `load()` raises `json.JSONDecodeError`
- ➕ **NEW: Document behavior:** Update JsonStorage docstring to clarify that corrupt JSON raises (not returns None like missing file)

**Implementation:**
```python
def test_corrupt_json_raises(self) -> None:
    # Write invalid JSON
    path = os.path.join(self.tmpdir, "recipe_1.json")
    with open(path, "w") as f:
        f.write("{invalid json")
    # Verify it raises
    with self.assertRaises(json.JSONDecodeError):
        self.storage.load("recipe", 1)
```

### 2. Enhanced SqliteStorage tests

**Status:** Complete; optional error simulation

- ✅ Round-trip (existing)
- ✅ Missing entity returns None (existing)
- ✅ Unknown entity_type raises ValueError (existing)
- ⚪ **OPTIONAL: Error simulation:** Test for DB permission errors, locked DB, or invalid path (if feasible)

**Note:** Current tests cover the main error path (unknown entity_type). Additional SQLite errors are difficult to simulate reliably and offer limited value.

### 3. Complete serialization tests (all 9 entity types)

**Status:** 2 of 9 complete; need 7 more

**Existing (test_serialization.py):**
- ✅ Restaurant (full and with nulls)
- ✅ Recipe (minimal and with ingredients)

**Missing (add to test_serialization.py):**
- ➕ User
- ➕ RecipeUnit
- ➕ InventoryUnit (including is_standard bool)
- ➕ CategoryRecipe
- ➕ FamilyInventory
- ➕ InventoryItem
- ➕ InventoryUnitEquivalence (composite key)

**Implementation pattern for each:**
```python
def test_user_round_trip(self) -> None:
    user = User(id=1, name="Alice", role="admin", restaurant_id=1)
    data = user_to_dict(user)
    loaded = user_from_dict(data)
    self.assertEqual(loaded.id, user.id)
    self.assertEqual(loaded.name, user.name)
    self.assertEqual(loaded.role, user.role)
```

**Test class:** `TestSerializationRoundTrip` (7 new tests, one per missing entity type)

### 4. Enhanced DataLake integration tests

**Status:** Restaurant, Recipe, InventoryUnitEquivalence tested via obj API; others missing

**Existing obj-level tests:**
- ✅ Restaurant
- ✅ Recipe
- ✅ InventoryUnitEquivalence

**Optional additions (if time permits):**
- ⚪ User obj round-trip
- ⚪ InventoryItem obj round-trip

**Note:** The existing DataLake tests already validate the full stack (entity → to_dict → save → load → from_dict) for 3 representative types. Additional types offer diminishing returns since the infrastructure is the same.

### 5. Persistence architecture documentation

**Status:** Missing; high priority

**Create:** `docs/Architecture/architecture-persistence.md`

**Required sections:**

#### 1. Overview
- Purpose of persistence layer (save/load domain entities)
- Three components: JsonStorage, SqliteStorage, DataLake
- When to use each

#### 2. Storage Backends

**JsonStorage:**
- One JSON file per entity (`{entity_type}_{entity_id}.json`)
- Human-readable, great for debugging and demos
- Simple file operations; no schema enforcement
- Limitations: no queries, no relationships, single-process only
- Use for: prototypes, local dev, sample data, debugging

**SqliteStorage:**
- One SQLite DB file with tables and relationships
- Schema enforcement via foreign keys
- Queryable (though not exposed in MVP)
- Transactions and data integrity
- Limitations: limited concurrency without WAL mode
- Use for: real apps, when you need relationships, structured data

#### 3. DataLake Unified API

**Instantiation:**
```python
# JSON backend
from core import DataLake
lake = DataLake(data_dir="data/json")

# SQLite backend
lake = DataLake(db_path="data/app.db")

# Context manager (recommended for SQLite)
with DataLake(db_path="data/app.db") as lake:
    # ... use lake
```

**Dict-level API:**
```python
# Save entity as dict
restaurant_data = {
    "id": 1,
    "name": "La Pizzeria",
    "address": "Calle 1",
    "restaurant_type_id": 1,
    "notes": None
}
lake.save_entity("restaurant", 1, restaurant_data)

# Load entity dict
data = lake.load_entity("restaurant", 1)  # dict | None

# Delete entity
lake.delete_entity("restaurant", 1)

# List all IDs for type
ids = lake.list_entity_ids("restaurant")  # list[str]
```

**Object-level API:**
```python
from core import DataLake, Restaurant, restaurant_to_dict, restaurant_from_dict

# Save domain object (auto-converts with to_dict)
restaurant = Restaurant(id=1, name="La Pizzeria", address="Calle 1", restaurant_type_id=1, notes=None)
lake.save_entity_obj(restaurant)

# Load as domain object (auto-converts with from_dict)
loaded = lake.load_entity_obj("restaurant", 1)  # Restaurant | None
```

#### 4. Error Handling

**JsonStorage:**
- `FileNotFoundError` → returns `None` (expected for missing)
- `json.JSONDecodeError` → raises (corrupt JSON file)
- `OSError` → raises (permission, disk full, etc.)

**SqliteStorage:**
- Missing entity → returns `None`
- Unknown entity_type → raises `ValueError`
- `sqlite3.IntegrityError` (FK violation, etc.) → raises `ValueError`
- `sqlite3.OperationalError` (DB locked, etc.) → raises `OSError`

**DataLake:**
- Inherits backend errors (no wrapper)
- Unknown type in obj API → raises `ValueError`

#### 5. Testing Patterns

**Temporary directories for JSON:**
```python
import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    lake = DataLake(data_dir=tmpdir)
    # ... test
```

**Temporary DB for SQLite:**
```python
import tempfile, os
with tempfile.TemporaryDirectory() as tmpdir:
    db_path = os.path.join(tmpdir, "test.db")
    lake = DataLake(db_path=db_path)
    # ... test
    lake.close()
```

#### 6. Implementation Files

- **core/persistence.py:** JsonStorage, SqliteStorage, DataLake
- **core/schema.py:** SQLite schema (tables, FKs)
- **core/serialization.py:** to_dict/from_dict for all entity types
- **tests/unit/test_persistence.py:** Storage and DataLake tests
- **tests/unit/test_serialization.py:** Round-trip serialization tests

#### 7. Design Decisions

- **Single backend per DataLake instance:** No automatic sync between JSON and SQLite (deferred)
- **Dict-level vs obj-level:** Dict API for flexibility; obj API for convenience
- **No migration tools yet:** Switching backends requires manual data export/import
- **Concurrency:** Limited by backend (single-process JSON; limited SQLite concurrency)

### 6. Update project README

**File:** `README.md` (project root)

**Add section:** "Architecture Documentation"
```markdown
## Architecture Documentation

See `docs/Architecture/` for detailed documentation:
- [Data Model](docs/Architecture/architecture-data-model.md) - Core entities
- [Normalization](docs/Architecture/architecture-normalization.md) - Unit conversions
- [Taxonomy](docs/Architecture/architecture-taxonomy.md) - Relationships
- [Persistence](docs/Architecture/architecture-persistence.md) - Storage layer (NEW)
- [Readiness KPIs](docs/Architecture/architecture-readiness-kpis.md) - Metrics
```

### 7. Verify exports

**Status:** Complete; verify only

- ✅ DataLake, JsonStorage, SqliteStorage in core/__init__.py
- ✅ All to_dict/from_dict functions in core/__init__.py

**Action:** Quick verification (no changes needed)

---

## Test Summary (after 3.7)

**Before 3.7:** 45 tests
**Added in 3.7:**
- JsonStorage corrupt JSON: +1 test
- Serialization round-trip (7 types): +7 tests

**After 3.7:** 53 tests (minimum)

---

## Deliverable Checklist

- [ ] Add corrupt JSON test to TestJsonStorage
- [ ] Update JsonStorage docstring to document corrupt JSON behavior
- [ ] Add 7 serialization round-trip tests (User, RecipeUnit, InventoryUnit, CategoryRecipe, FamilyInventory, InventoryItem, InventoryUnitEquivalence)
- [ ] Create `docs/Architecture/architecture-persistence.md` with all 7 sections
- [ ] Update `README.md` with link to persistence doc
- [ ] Verify all exports in core/__init__.py (no changes needed)
- [ ] Run full test suite: `python -m pytest tests/unit/test_persistence.py tests/unit/test_serialization.py -v`
- [ ] Verify 53+ tests passing, no linter errors

---

## Notes

- **Priority:** Documentation first (high value, zero current coverage), then serialization tests (validates 3.3 completeness), then corrupt JSON test
- **Optional:** Additional SQLite error tests, additional DataLake obj tests for remaining types
- **Out of scope:** Performance testing, migration tools, multi-backend sync (deferred to future tasks)
