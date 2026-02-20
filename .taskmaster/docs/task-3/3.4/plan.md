# Implementation plan: Subtask 3.4 — SQLite schema

## Goal

Design and implement the SQLite schema: one table per persisted entity type, with columns and foreign keys aligned to the 3.1 dict shape. Implement `_create_tables()` that runs the `CREATE TABLE` statements. Optional: a schema version table for future migrations.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| Tables: restaurant, user, recipe_unit, inventory_unit, category_recipe, family_inventory, inventory_item, recipe, recipe_ingredient (normalized), inventory_unit_equivalence | SqliteStorage save/load implementation (3.5) |
| Complete DDL with all columns from 3.1 contract; FKs, indexes, composite keys; `_create_tables()` called from SqliteStorage constructor | Migration runner (deferred) |
| Schema version table (optional) for future migration support | Performance optimization (query plans, VACUUM, etc.) |

---

## Dependencies

- **3.1** — Table and column design must **exactly match** the persisted entity types and dict fields (ids, FKs, scalars) from the serialization contract.

---

## Breakdown

### 1. Table list and creation order

Create tables in this order to satisfy foreign key dependencies:

1. **No FKs to other persisted entities:**
   - `restaurant`
   - `user`
   - `recipe_unit`
   - `category_recipe`

2. **Self-referential FK:**
   - `inventory_unit` (has `base_unit_id` → `inventory_unit.id`)

3. **References inventory_unit:**
   - `family_inventory` (has `base_unit_id` → `inventory_unit.id`)

4. **References inventory_unit and family_inventory:**
   - `inventory_item` (has `unit_id` → `inventory_unit.id`, `family_id` → `family_inventory.id`)

5. **References category_recipe:**
   - `recipe` (has `category_id` → `category_recipe.id`)

6. **References recipe and recipe_unit:**
   - `recipe_ingredient` (normalized table for Recipe.ingredients list; has `recipe_id` → `recipe.id`, `unit_id` → `recipe_unit.id`)

7. **References inventory_unit and inventory_item:**
   - `inventory_unit_equivalence` (has `unit_id`, `inventory_item_id`, `base_unit_id` → `inventory_unit.id`)

8. **Optional (for migrations):**
   - `schema_version`

---

### 2. Complete table specifications

All column names, types, and constraints per the 3.1 contract. SQLite type mappings:

- `int` → `INTEGER`
- `float` → `REAL`
- `str` → `TEXT`
- `bool` → `INTEGER` (0 or 1)
- `list[str]` → `TEXT` (stored as JSON array)
- `list[dict]` → normalized table or `TEXT` (JSON array)

#### 2.1 restaurant

```sql
CREATE TABLE restaurant (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT,
    restaurant_type_id INTEGER,
    notes TEXT
);
```

**Fields from 3.1:** id, name, address (nullable), restaurant_type_id (nullable; FK to fixed constant), notes (nullable).

#### 2.2 user

```sql
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL
);
```

**Fields from 3.1:** id, name, email, role (all required). Role is one of: "admin", "mesero", "cocinero", "inventario".

#### 2.3 recipe_unit

```sql
CREATE TABLE recipe_unit (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    description TEXT
);
```

**Fields from 3.1:** id, name, symbol, description (nullable).

#### 2.4 inventory_unit

```sql
CREATE TABLE inventory_unit (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    description TEXT,
    base_unit_id INTEGER,
    factor_to_base REAL NOT NULL DEFAULT 1.0,
    is_standard INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (base_unit_id) REFERENCES inventory_unit(id)
);
```

**Fields from 3.1:** id, name, symbol, description (nullable), base_unit_id (nullable; self-referential FK for conversions), factor_to_base (default 1.0), is_standard (bool → INTEGER; default 1/true).

#### 2.5 category_recipe

```sql
CREATE TABLE category_recipe (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);
```

**Fields from 3.1:** id, name, description (nullable). No recipe_id; recipes reference categories, not vice versa.

#### 2.6 family_inventory

```sql
CREATE TABLE family_inventory (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    base_unit_id INTEGER,
    FOREIGN KEY (base_unit_id) REFERENCES inventory_unit(id)
);
```

**Fields from 3.1:** id, name, description (nullable), base_unit_id (nullable; FK to InventoryUnit). No restaurant_id.

#### 2.7 inventory_item

```sql
CREATE TABLE inventory_item (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    unit_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    family_id INTEGER,
    description TEXT,
    FOREIGN KEY (unit_id) REFERENCES inventory_unit(id),
    FOREIGN KEY (family_id) REFERENCES family_inventory(id)
);
```

**Fields from 3.1:** id, name, unit_id (FK to InventoryUnit), category_id (FK to fixed InventoryCategory constant; not persisted as table), family_id (nullable; FK to FamilyInventory), description (nullable). No quantity field.

**Note:** category_id references a fixed constant (perecedero/no perecedero) not a persisted table; no FK constraint for it.

#### 2.8 recipe

```sql
CREATE TABLE recipe (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    description TEXT,
    steps TEXT,
    FOREIGN KEY (category_id) REFERENCES category_recipe(id)
);
```

**Fields from 3.1:** id, name, category_id (FK to CategoryRecipe), description (nullable), steps (nullable; stored as JSON array of strings or NULL). **No ingredients column**; ingredients are in separate `recipe_ingredient` table (normalized approach). No restaurant_id.

**Note on steps:** Store as JSON TEXT when not NULL, e.g. `'["Marinar", "Cortar", "Servir"]'`.

#### 2.9 recipe_ingredient (normalized table for Recipe.ingredients)

```sql
CREATE TABLE recipe_ingredient (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit_id INTEGER NOT NULL,
    inventory_item_id INTEGER,
    FOREIGN KEY (recipe_id) REFERENCES recipe(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES recipe_unit(id),
    FOREIGN KEY (inventory_item_id) REFERENCES inventory_item(id)
);
```

**Fields from 3.1 embedded ingredient shape:** recipe_id (parent recipe), name, quantity, unit_id (FK to RecipeUnit), inventory_item_id (nullable; FK to InventoryItem).

**Design decision:** Ingredients are embedded in Recipe.ingredients list per 3.1, NOT a top-level entity. Normalized storage: one row per ingredient; recipe_id links to parent. `ON DELETE CASCADE` ensures ingredients are deleted when recipe is deleted. `id` is an auto-increment surrogate key (ingredients don't have IDs in the data model).

**Alternative (not chosen):** Store ingredients as JSON TEXT column in recipe table. This approach (normalized) allows easier querying and FK validation.

#### 2.10 inventory_unit_equivalence

```sql
CREATE TABLE inventory_unit_equivalence (
    unit_id INTEGER NOT NULL,
    inventory_item_id INTEGER NOT NULL,
    base_unit_id INTEGER NOT NULL,
    factor_to_base REAL NOT NULL,
    PRIMARY KEY (unit_id, inventory_item_id),
    FOREIGN KEY (unit_id) REFERENCES inventory_unit(id),
    FOREIGN KEY (inventory_item_id) REFERENCES inventory_item(id),
    FOREIGN KEY (base_unit_id) REFERENCES inventory_unit(id)
);
```

**Fields from 3.1:** unit_id, inventory_item_id, base_unit_id, factor_to_base. **No single id field**; composite primary key on (unit_id, inventory_item_id).

#### 2.11 schema_version (optional)

```sql
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
```

**Purpose:** Track current schema version for future migrations. After creating all tables, insert initial version:

```sql
INSERT INTO schema_version (version, applied_at) 
VALUES (1, datetime('now'));
```

---

### 3. Indexes

Add indexes on foreign key columns and frequently queried fields for fast lookups:

```sql
-- Recipe queries by category
CREATE INDEX idx_recipe_category_id ON recipe(category_id);

-- Inventory item lookups
CREATE INDEX idx_inventory_item_family_id ON inventory_item(family_id);
CREATE INDEX idx_inventory_item_unit_id ON inventory_item(unit_id);
CREATE INDEX idx_inventory_item_category_id ON inventory_item(category_id);

-- Recipe ingredient queries by recipe
CREATE INDEX idx_recipe_ingredient_recipe_id ON recipe_ingredient(recipe_id);
CREATE INDEX idx_recipe_ingredient_unit_id ON recipe_ingredient(unit_id);
CREATE INDEX idx_recipe_ingredient_inventory_item_id ON recipe_ingredient(inventory_item_id);

-- Equivalence lookups by item
CREATE INDEX idx_equivalence_inventory_item_id ON inventory_unit_equivalence(inventory_item_id);

-- Family inventory queries by base unit
CREATE INDEX idx_family_inventory_base_unit_id ON family_inventory(base_unit_id);

-- Inventory unit queries by base unit (for conversion chains)
CREATE INDEX idx_inventory_unit_base_unit_id ON inventory_unit(base_unit_id);
```

---

### 4. _create_tables() implementation

#### 4.1 Function signature and location

```python
def _create_tables(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes for the schema.
    
    Called from SqliteStorage.__init__() to initialize the database.
    Uses CREATE TABLE IF NOT EXISTS so it's safe to call multiple times.
    """
```

**Location:** In `core/persistence.py` next to SqliteStorage class, or in a separate `core/schema.py` module (if schema logic becomes large).

#### 4.2 Implementation pattern

```python
import sqlite3

def _create_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    
    # Enable foreign key constraints (off by default in SQLite)
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Create tables in dependency order
    # 1. No FKs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurant (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT,
            restaurant_type_id INTEGER,
            notes TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)
    
    # ... (all other CREATE TABLE statements in order) ...
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recipe_category_id ON recipe(category_id)")
    # ... (all other CREATE INDEX statements) ...
    
    # Optional: Initialize schema version
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)
    
    # Insert version 1 if not exists
    cursor.execute("SELECT COUNT(*) FROM schema_version WHERE version = 1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO schema_version (version, applied_at) VALUES (1, datetime('now'))")
    
    conn.commit()
```

#### 4.3 SqliteStorage integration

```python
class SqliteStorage:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        _create_tables(self._conn)  # Initialize schema
```

---

### 5. Type mapping reference

| Python type (3.1 contract) | SQLite type | Notes |
|---------------------------|-------------|-------|
| int | INTEGER | |
| float | REAL | |
| str | TEXT | |
| bool | INTEGER | Store as 0 (false) or 1 (true) |
| list[str] | TEXT | Store as JSON array, e.g. `'["a","b"]'` or NULL |
| list[dict] | Normalized table | For Recipe.ingredients → recipe_ingredient table |
| None (nullable) | NULL | Use `column_name TEXT` (no NOT NULL) |

---

### 6. Implementation checklist

- [ ] Create `_create_tables()` function with all CREATE TABLE statements in correct order
- [ ] Add all CREATE INDEX statements
- [ ] Enable `PRAGMA foreign_keys = ON` at start of function
- [ ] Optional: Add schema_version table and initial insert
- [ ] Call `_create_tables(conn)` from SqliteStorage.__init__()
- [ ] Add minimal smoke test: create DB, verify tables exist via `SELECT name FROM sqlite_master WHERE type='table'`

---

### 7. Notes and decisions

#### 7.1 Why normalized recipe_ingredient table?

**Alternative:** Store ingredients as JSON TEXT in recipe.ingredients column.

**Chosen approach (normalized):**
- Easier FK validation (unit_id, inventory_item_id)
- Enables queries like "find all recipes using ingredient X"
- Cleaner alignment with 3.5 save/load (can query by recipe_id)

**Trade-off:** Requires JOIN when loading a recipe with ingredients; 3.5 will use `SELECT * FROM recipe_ingredient WHERE recipe_id = ?` to rebuild the ingredients list.

#### 7.2 No table for InventoryCategory or RestaurantType

Per 3.1, these are **fixed constants in code** (`DEFAULT_INVENTORY_CATEGORIES`, `DEFAULT_RESTAURANT_TYPES`). Only their IDs are stored in inventory_item.category_id and restaurant.restaurant_type_id. No FK constraints for these fields.

#### 7.3 Composite primary key for inventory_unit_equivalence

Per 3.1, this entity has no single `id` field. Use `PRIMARY KEY (unit_id, inventory_item_id)` to enforce uniqueness on the pair.

---

### 8. Deliverable

- **Code:** `_create_tables(conn)` function in `core/persistence.py` (or `core/schema.py`)
- **Tables:** 10 tables (restaurant, user, recipe_unit, inventory_unit, category_recipe, family_inventory, inventory_item, recipe, recipe_ingredient, inventory_unit_equivalence) + optional schema_version
- **Indexes:** 11 indexes on FK and frequently queried columns
- **No save/load logic** in 3.4; that is 3.5
- **Test:** Minimal smoke test that DB is created and tables exist (in 3.7 or as part of 3.4 delivery)
