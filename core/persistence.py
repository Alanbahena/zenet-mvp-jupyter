"""
Persistence layer: JSON and (later) SQLite backends for entity data.

JsonStorage saves and loads plain dicts as JSON files (one file per entity).
SqliteStorage (3.4 schema, 3.5 save/load) persists dicts to SQLite.
Operates on dicts only; entity serialization is in 3.3 / DataLake in 3.6.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from core.schema import _create_tables


def _entity_id_to_str(entity_id: int | str) -> str:
    """Normalize entity_id for use in filenames (int or composite string)."""
    return str(entity_id)


def _file_path(data_dir: str, entity_type: str, entity_id: int | str) -> str:
    """Return path to JSON file for this entity."""
    eid = _entity_id_to_str(entity_id)
    return os.path.join(data_dir, f"{entity_type}_{eid}.json")


class JsonStorage:
    """
    File-based storage: one JSON file per entity instance.

    Operates on plain dicts only. entity_type and entity_id follow the
    serialization contract (3.1). No locking; assumes single-user/single-process.
    """

    def __init__(self, data_dir: str) -> None:
        self._data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

    def save(self, entity_type: str, entity_id: int | str, data_dict: dict[str, Any]) -> None:
        """
        Write data_dict to {data_dir}/{entity_type}_{entity_id}.json.

        Uses UTF-8 and indent=2. Raises OSError on IO failure.
        """
        path = _file_path(self._data_dir, entity_type, entity_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data_dict, f, indent=2, ensure_ascii=False)
        except OSError:
            raise

    def load(self, entity_type: str, entity_id: int | str) -> dict[str, Any] | None:
        """
        Read JSON from the entity file; return the dict.

        Returns None if the file does not exist. Raises json.JSONDecodeError
        if the file exists but is invalid JSON; OSError on other IO errors.
        """
        path = _file_path(self._data_dir, entity_type, entity_id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except OSError:
            raise

    def delete(self, entity_type: str, entity_id: int | str) -> None:
        """Remove the entity file if it exists; no-op if missing."""
        path = _file_path(self._data_dir, entity_type, entity_id)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError:
            raise

    def list_ids(self, entity_type: str) -> list[str]:
        """
        Return list of entity_id strings for this entity_type.

        For simple entities these are numeric strings; for composite keys
        (e.g. inventory_unit_equivalence) they are strings like "10_15".
        """
        prefix = f"{entity_type}_"
        suffix = ".json"
        result: list[str] = []
        try:
            for name in os.listdir(self._data_dir):
                if name.startswith(prefix) and name.endswith(suffix):
                    eid = name[len(prefix) : -len(suffix)]
                    result.append(eid)
        except OSError:
            raise
        return result


# Allowed entity types for SqliteStorage (must match schema table names / special cases)
_SQLITE_ENTITY_TYPES = frozenset({
    "restaurant",
    "user",
    "recipe_unit",
    "inventory_unit",
    "category_recipe",
    "family_inventory",
    "inventory_item",
    "recipe",
    "inventory_unit_equivalence",
})


class SqliteStorage:
    """
    SQLite-backed storage (Task 3.4 schema, 3.5 save/load).

    Saves and loads plain dicts by entity_type and entity_id. Uses parameterized
    queries; supports recipe (normalized ingredients) and composite key
    (inventory_unit_equivalence). Optional delete(), list_ids(), close().
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        _create_tables(self._conn)

    def close(self) -> None:
        """Close the database connection. No-op if already closed."""
        self._conn.close()

    def save(self, entity_type: str, entity_id: int | str, data_dict: dict[str, Any]) -> None:
        """Persist data_dict for the given entity. Upsert by entity_id (or composite key)."""
        if entity_type not in _SQLITE_ENTITY_TYPES:
            raise ValueError(f"Unknown entity_type: {entity_type}")
        try:
            cursor = self._conn.cursor()
            if entity_type == "restaurant":
                cursor.execute(
                    """
                    INSERT INTO restaurant (id, name, address, restaurant_type_id, notes)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        address = excluded.address,
                        restaurant_type_id = excluded.restaurant_type_id,
                        notes = excluded.notes
                    """,
                    (
                        data_dict["id"],
                        data_dict["name"],
                        data_dict.get("address"),
                        data_dict.get("restaurant_type_id"),
                        data_dict.get("notes"),
                    ),
                )
            elif entity_type == "user":
                cursor.execute(
                    """
                    INSERT INTO user (id, name, email, role)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        email = excluded.email,
                        role = excluded.role
                    """,
                    (
                        data_dict["id"],
                        data_dict["name"],
                        data_dict["email"],
                        data_dict["role"],
                    ),
                )
            elif entity_type == "recipe_unit":
                cursor.execute(
                    """
                    INSERT INTO recipe_unit (id, name, symbol, description)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        symbol = excluded.symbol,
                        description = excluded.description
                    """,
                    (
                        data_dict["id"],
                        data_dict["name"],
                        data_dict["symbol"],
                        data_dict.get("description"),
                    ),
                )
            elif entity_type == "inventory_unit":
                is_standard_int = 1 if data_dict.get("is_standard", True) else 0
                cursor.execute(
                    """
                    INSERT INTO inventory_unit (id, name, symbol, description, base_unit_id, factor_to_base, is_standard)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        symbol = excluded.symbol,
                        description = excluded.description,
                        base_unit_id = excluded.base_unit_id,
                        factor_to_base = excluded.factor_to_base,
                        is_standard = excluded.is_standard
                    """,
                    (
                        data_dict["id"],
                        data_dict["name"],
                        data_dict["symbol"],
                        data_dict.get("description"),
                        data_dict.get("base_unit_id"),
                        data_dict.get("factor_to_base", 1.0),
                        is_standard_int,
                    ),
                )
            elif entity_type == "category_recipe":
                cursor.execute(
                    """
                    INSERT INTO category_recipe (id, name, description)
                    VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        description = excluded.description
                    """,
                    (
                        data_dict["id"],
                        data_dict["name"],
                        data_dict.get("description"),
                    ),
                )
            elif entity_type == "family_inventory":
                cursor.execute(
                    """
                    INSERT INTO family_inventory (id, name, description, base_unit_id)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        description = excluded.description,
                        base_unit_id = excluded.base_unit_id
                    """,
                    (
                        data_dict["id"],
                        data_dict["name"],
                        data_dict.get("description"),
                        data_dict.get("base_unit_id"),
                    ),
                )
            elif entity_type == "inventory_item":
                cursor.execute(
                    """
                    INSERT INTO inventory_item (id, name, unit_id, category_id, family_id, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        unit_id = excluded.unit_id,
                        category_id = excluded.category_id,
                        family_id = excluded.family_id,
                        description = excluded.description
                    """,
                    (
                        data_dict["id"],
                        data_dict["name"],
                        data_dict["unit_id"],
                        data_dict["category_id"],
                        data_dict.get("family_id"),
                        data_dict.get("description"),
                    ),
                )
            elif entity_type == "recipe":
                steps_json = (
                    json.dumps(data_dict["steps"])
                    if data_dict.get("steps") is not None
                    else None
                )
                cursor.execute(
                    """
                    INSERT INTO recipe (id, name, category_id, description, steps)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        category_id = excluded.category_id,
                        description = excluded.description,
                        steps = excluded.steps
                    """,
                    (
                        data_dict["id"],
                        data_dict["name"],
                        data_dict["category_id"],
                        data_dict.get("description"),
                        steps_json,
                    ),
                )
                cursor.execute("DELETE FROM recipe_ingredient WHERE recipe_id = ?", (data_dict["id"],))
                for ing in data_dict.get("ingredients", []):
                    cursor.execute(
                        """
                        INSERT INTO recipe_ingredient (recipe_id, name, quantity, unit_id, inventory_item_id)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            data_dict["id"],
                            ing["name"],
                            ing["quantity"],
                            ing["unit_id"],
                            ing.get("inventory_item_id"),
                        ),
                    )
            elif entity_type == "inventory_unit_equivalence":
                unit_id, inventory_item_id = map(int, str(entity_id).split("_"))
                cursor.execute(
                    """
                    INSERT INTO inventory_unit_equivalence (unit_id, inventory_item_id, base_unit_id, factor_to_base)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(unit_id, inventory_item_id) DO UPDATE SET
                        base_unit_id = excluded.base_unit_id,
                        factor_to_base = excluded.factor_to_base
                    """,
                    (
                        unit_id,
                        inventory_item_id,
                        data_dict["base_unit_id"],
                        data_dict["factor_to_base"],
                    ),
                )
            self._conn.commit()
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Cannot save {entity_type} {entity_id}: {e}") from e
        except sqlite3.OperationalError as e:
            raise OSError(f"Database error saving {entity_type} {entity_id}: {e}") from e

    def load(self, entity_type: str, entity_id: int | str) -> dict[str, Any] | None:
        """Load entity dict for the given type and id. Returns None if not found."""
        if entity_type not in _SQLITE_ENTITY_TYPES:
            raise ValueError(f"Unknown entity_type: {entity_type}")
        try:
            cursor = self._conn.cursor()
            if entity_type == "restaurant":
                cursor.execute("SELECT * FROM restaurant WHERE id = ?", (entity_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            elif entity_type == "user":
                cursor.execute("SELECT * FROM user WHERE id = ?", (entity_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            elif entity_type == "recipe_unit":
                cursor.execute("SELECT * FROM recipe_unit WHERE id = ?", (entity_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            elif entity_type == "inventory_unit":
                cursor.execute("SELECT * FROM inventory_unit WHERE id = ?", (entity_id,))
                row = cursor.fetchone()
                if row is None:
                    return None
                d = dict(row)
                d["is_standard"] = bool(d["is_standard"])
                return d
            elif entity_type == "category_recipe":
                cursor.execute("SELECT * FROM category_recipe WHERE id = ?", (entity_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            elif entity_type == "family_inventory":
                cursor.execute("SELECT * FROM family_inventory WHERE id = ?", (entity_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            elif entity_type == "inventory_item":
                cursor.execute("SELECT * FROM inventory_item WHERE id = ?", (entity_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
            elif entity_type == "recipe":
                cursor.execute("SELECT * FROM recipe WHERE id = ?", (entity_id,))
                recipe_row = cursor.fetchone()
                if recipe_row is None:
                    return None
                recipe_dict = dict(recipe_row)
                recipe_dict["steps"] = (
                    json.loads(recipe_dict["steps"]) if recipe_dict["steps"] else None
                )
                cursor.execute(
                    """
                    SELECT name, quantity, unit_id, inventory_item_id
                    FROM recipe_ingredient WHERE recipe_id = ? ORDER BY id
                    """,
                    (entity_id,),
                )
                recipe_dict["ingredients"] = [
                    {
                        "name": ing["name"],
                        "quantity": ing["quantity"],
                        "unit_id": ing["unit_id"],
                        "inventory_item_id": ing["inventory_item_id"],
                    }
                    for ing in cursor.fetchall()
                ]
                return recipe_dict
            elif entity_type == "inventory_unit_equivalence":
                unit_id, inventory_item_id = map(int, str(entity_id).split("_"))
                cursor.execute(
                    """
                    SELECT unit_id, inventory_item_id, base_unit_id, factor_to_base
                    FROM inventory_unit_equivalence
                    WHERE unit_id = ? AND inventory_item_id = ?
                    """,
                    (unit_id, inventory_item_id),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
            return None
        except sqlite3.OperationalError as e:
            raise OSError(f"Database error loading {entity_type} {entity_id}: {e}") from e

    def delete(self, entity_type: str, entity_id: int | str) -> None:
        """Remove the entity if it exists. No-op if not found."""
        if entity_type not in _SQLITE_ENTITY_TYPES:
            raise ValueError(f"Unknown entity_type: {entity_type}")
        try:
            cursor = self._conn.cursor()
            if entity_type == "recipe":
                cursor.execute("DELETE FROM recipe WHERE id = ?", (entity_id,))
            elif entity_type == "inventory_unit_equivalence":
                unit_id, inventory_item_id = map(int, str(entity_id).split("_"))
                cursor.execute(
                    """
                    DELETE FROM inventory_unit_equivalence
                    WHERE unit_id = ? AND inventory_item_id = ?
                    """,
                    (unit_id, inventory_item_id),
                )
            else:
                table = entity_type
                cursor.execute("DELETE FROM " + table + " WHERE id = ?", (entity_id,))
            self._conn.commit()
        except sqlite3.OperationalError as e:
            raise OSError(f"Database error deleting {entity_type} {entity_id}: {e}") from e

    def list_ids(self, entity_type: str) -> list[str]:
        """Return list of entity_id strings for this entity_type."""
        if entity_type not in _SQLITE_ENTITY_TYPES:
            raise ValueError(f"Unknown entity_type: {entity_type}")
        try:
            cursor = self._conn.cursor()
            if entity_type == "inventory_unit_equivalence":
                cursor.execute("SELECT unit_id, inventory_item_id FROM inventory_unit_equivalence")
                return [f"{row[0]}_{row[1]}" for row in cursor.fetchall()]
            table = entity_type
            cursor.execute("SELECT id FROM " + table)
            return [str(row[0]) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            raise OSError(f"Database error listing {entity_type}: {e}") from e
