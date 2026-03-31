"""
SQLite schema for Task 3.4: tables and indexes for persisted entity types.

Creates all tables in dependency order; used by SqliteStorage on init.
Schema matches the 3.1 serialization contract.
"""

import sqlite3


def _create_tables(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes for the schema.

    Called from SqliteStorage.__init__() to initialize the database.
    Uses CREATE TABLE IF NOT EXISTS so it's safe to call multiple times.
    """
    cursor = conn.cursor()

    # Enable foreign key constraints (off by default in SQLite)
    cursor.execute("PRAGMA foreign_keys = ON")

    # 1. No FKs to other persisted entities
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipe_unit (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            description TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_recipe (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT
        )
    """)

    # 2. Self-referential FK
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_unit (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            description TEXT,
            base_unit_id INTEGER,
            factor_to_base REAL NOT NULL DEFAULT 1.0,
            is_standard INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (base_unit_id) REFERENCES inventory_unit(id)
        )
    """)

    # 3. References inventory_unit
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS family_inventory (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            base_unit_id INTEGER,
            FOREIGN KEY (base_unit_id) REFERENCES inventory_unit(id)
        )
    """)

    # 4. References inventory_unit and family_inventory
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_item (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            stock_unit_id INTEGER NOT NULL,
            purchase_unit_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            purchase_to_stock_factor REAL NOT NULL DEFAULT 1.0,
            family_id INTEGER,
            description TEXT,
            FOREIGN KEY (stock_unit_id) REFERENCES inventory_unit(id),
            FOREIGN KEY (purchase_unit_id) REFERENCES inventory_unit(id),
            FOREIGN KEY (family_id) REFERENCES family_inventory(id)
        )
    """)

    # 5. References category_recipe
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipe (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            description TEXT,
            steps TEXT,
            FOREIGN KEY (category_id) REFERENCES category_recipe(id)
        )
    """)

    # 6. References recipe and recipe_unit
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipe_ingredient (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit_id INTEGER NOT NULL,
            inventory_item_id INTEGER,
            FOREIGN KEY (recipe_id) REFERENCES recipe(id) ON DELETE CASCADE,
            FOREIGN KEY (unit_id) REFERENCES recipe_unit(id),
            FOREIGN KEY (inventory_item_id) REFERENCES inventory_item(id)
        )
    """)

    # 7. Recipe unit conversions (composite key: recipe_unit_id + family_id + inventory_item_id)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipe_unit_conversion (
            recipe_unit_id    INTEGER NOT NULL,
            family_id         INTEGER,
            inventory_item_id INTEGER,
            quantity          REAL NOT NULL,
            base_unit_id      INTEGER NOT NULL,
            source            TEXT NOT NULL DEFAULT 'agent_estimated',
            PRIMARY KEY (recipe_unit_id, family_id, inventory_item_id)
        )
    """)

    # 8. Schema version (for future migrations)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)

    # 9. Agent conversation state (text blob, keyed by agent-scoped session string)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_state (
            session_id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    """)

    # 10. Classification entity (JSON blob, keyed by integer session-derived id)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classification (
            id INTEGER PRIMARY KEY,
            data TEXT NOT NULL
        )
    """)

    # Indexes
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_recipe_category_id ON recipe(category_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_item_family_id ON inventory_item(family_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_item_stock_unit_id ON inventory_item(stock_unit_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_item_category_id ON inventory_item(category_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_recipe_ingredient_recipe_id ON recipe_ingredient(recipe_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_recipe_ingredient_unit_id ON recipe_ingredient(unit_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_recipe_ingredient_inventory_item_id ON recipe_ingredient(inventory_item_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_family_inventory_base_unit_id ON family_inventory(base_unit_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_unit_base_unit_id ON inventory_unit(base_unit_id)"
    )

    # Insert initial schema version if not present
    cursor.execute("SELECT COUNT(*) FROM schema_version WHERE version = 1")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (1, datetime('now'))"
        )

    conn.commit()
