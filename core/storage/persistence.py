"""
Persistence layer: JSON and (later) SQLite backends for entity data.

JsonStorage saves and loads plain dicts as JSON files (one file per entity).
SqliteStorage (3.4 schema, 3.5 save/load) persists dicts to SQLite.
DataLake (3.6) exposes a unified API over either backend; optional obj-level save/load via 3.3.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from core.storage.schema import _create_tables


def _entity_id_to_str(entity_id: int | str) -> str:
    """Normalize entity_id for use in filenames (int or composite string)."""
    return str(entity_id)


def _file_path(data_dir: str, entity_type: str, entity_id: int | str) -> str:
    """Return path to JSON file for this entity."""
    eid = _entity_id_to_str(entity_id)
    return os.path.join(data_dir, f"{entity_type}_{eid}.json")


def _parse_ruc_id(entity_id: str) -> tuple[int, int | None, int | None]:
    """Parse composite recipe_unit_conversion id string to (recipe_unit_id, family_id, inventory_item_id)."""
    parts = str(entity_id).split("_")
    recipe_unit_id = int(parts[0])
    family_id = None if parts[1] == "None" else int(parts[1])
    inventory_item_id = None if parts[2] == "None" else int(parts[2])
    return recipe_unit_id, family_id, inventory_item_id


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
        if the file exists but contains invalid/corrupt JSON; OSError on other
        IO errors (permissions, disk full, etc.).
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
    "recipe_unit_conversion",
    "agent_state",
    "classification",
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
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
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
            elif entity_type == "recipe_unit_conversion":
                ruc_unit_id, ruc_family_id, ruc_item_id = _parse_ruc_id(entity_id)
                cursor.execute(
                    """
                    INSERT INTO recipe_unit_conversion
                        (recipe_unit_id, family_id, inventory_item_id, quantity, base_unit_id, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(recipe_unit_id, family_id, inventory_item_id) DO UPDATE SET
                        quantity = excluded.quantity,
                        base_unit_id = excluded.base_unit_id,
                        source = excluded.source
                    """,
                    (
                        ruc_unit_id,
                        ruc_family_id,
                        ruc_item_id,
                        data_dict["quantity"],
                        data_dict["base_unit_id"],
                        data_dict.get("source", "agent_estimated"),
                    ),
                )
            elif entity_type == "agent_state":
                cursor.execute(
                    """
                    INSERT INTO agent_state (session_id, data)
                    VALUES (?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        data = excluded.data
                    """,
                    (str(entity_id), json.dumps(data_dict)),
                )
            elif entity_type == "classification":
                cursor.execute(
                    "INSERT INTO classification (id, data) VALUES (?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
                    (int(entity_id), json.dumps(data_dict)),
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
            elif entity_type == "recipe_unit_conversion":
                ruc_unit_id, ruc_family_id, ruc_item_id = _parse_ruc_id(entity_id)
                cursor.execute(
                    """
                    SELECT recipe_unit_id, family_id, inventory_item_id, quantity, base_unit_id, source
                    FROM recipe_unit_conversion
                    WHERE recipe_unit_id = ? AND family_id IS ? AND inventory_item_id IS ?
                    """,
                    (ruc_unit_id, ruc_family_id, ruc_item_id),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
            elif entity_type == "agent_state":
                cursor.execute(
                    "SELECT data FROM agent_state WHERE session_id = ?", (str(entity_id),)
                )
                row = cursor.fetchone()
                return json.loads(row[0]) if row else None
            elif entity_type == "classification":
                cursor.execute(
                    "SELECT data FROM classification WHERE id = ?", (int(entity_id),)
                )
                row = cursor.fetchone()
                return json.loads(row[0]) if row else None
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
            elif entity_type == "recipe_unit_conversion":
                ruc_unit_id, ruc_family_id, ruc_item_id = _parse_ruc_id(entity_id)
                cursor.execute(
                    """
                    DELETE FROM recipe_unit_conversion
                    WHERE recipe_unit_id = ? AND family_id IS ? AND inventory_item_id IS ?
                    """,
                    (ruc_unit_id, ruc_family_id, ruc_item_id),
                )
            elif entity_type == "agent_state":
                cursor.execute(
                    "DELETE FROM agent_state WHERE session_id = ?", (str(entity_id),)
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
            elif entity_type == "recipe_unit_conversion":
                cursor.execute(
                    "SELECT recipe_unit_id, family_id, inventory_item_id FROM recipe_unit_conversion"
                )
                return [f"{row[0]}_{row[1]}_{row[2]}" for row in cursor.fetchall()]
            elif entity_type == "agent_state":
                cursor.execute("SELECT session_id FROM agent_state")
                return [row[0] for row in cursor.fetchall()]
            table = entity_type
            cursor.execute("SELECT id FROM " + table)
            return [str(row[0]) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            raise OSError(f"Database error listing {entity_type}: {e}") from e


# --- DataLake (Task 3.6) ---

# Lazy imports for entity types and serialization (avoid circular import)
def _get_entity_registries() -> tuple[dict[type, str], dict[str, Any], dict[str, Any]]:
    from core.domain import data_model as dm
    from core.domain import serialization as ser
    from core.operations import normalization as norm
    class_to_type: dict[type, str] = {
        dm.Restaurant: "restaurant",
        dm.User: "user",
        dm.RecipeUnit: "recipe_unit",
        dm.InventoryUnit: "inventory_unit",
        dm.CategoryRecipe: "category_recipe",
        dm.FamilyInventory: "family_inventory",
        dm.InventoryItem: "inventory_item",
        dm.Recipe: "recipe",
        dm.InventoryUnitEquivalence: "inventory_unit_equivalence",
        norm.RecipeUnitConversionEntry: "recipe_unit_conversion",
    }
    type_to_from_dict: dict[str, Any] = {
        "restaurant": ser.restaurant_from_dict,
        "user": ser.user_from_dict,
        "recipe_unit": ser.recipe_unit_from_dict,
        "inventory_unit": ser.inventory_unit_from_dict,
        "category_recipe": ser.category_recipe_from_dict,
        "family_inventory": ser.family_inventory_from_dict,
        "inventory_item": ser.inventory_item_from_dict,
        "recipe": ser.recipe_from_dict,
        "inventory_unit_equivalence": ser.inventory_unit_equivalence_from_dict,
        "recipe_unit_conversion": ser.recipe_unit_conversion_from_dict,
    }
    type_to_to_dict: dict[str, Any] = {
        "restaurant": ser.restaurant_to_dict,
        "user": ser.user_to_dict,
        "recipe_unit": ser.recipe_unit_to_dict,
        "inventory_unit": ser.inventory_unit_to_dict,
        "category_recipe": ser.category_recipe_to_dict,
        "family_inventory": ser.family_inventory_to_dict,
        "inventory_item": ser.inventory_item_to_dict,
        "recipe": ser.recipe_to_dict,
        "inventory_unit_equivalence": ser.inventory_unit_equivalence_to_dict,
        "recipe_unit_conversion": ser.recipe_unit_conversion_to_dict,
    }
    return class_to_type, type_to_from_dict, type_to_to_dict


def _datalake_entity_id(entity: Any, entity_type: str) -> str | int:
    """Extract entity_id from entity for save_entity_obj. Composite key for inventory_unit_equivalence."""
    if entity_type == "inventory_unit_equivalence":
        return f"{entity.unit_id}_{entity.inventory_item_id}"
    return entity.id


class DataLake:
    """
    Unified persistence API over JSON or SQLite backend (Task 3.6).

    One backend per instance: provide exactly one of data_dir (JSON) or db_path (SQLite).
    Dict-level: save_entity / load_entity / delete_entity / list_entity_ids.
    Optional object-level: save_entity_obj / load_entity_obj use 3.3 serialization.
    Resource cleanup: close() (no-op for JSON; closes DB for SQLite).
    Concurrency: inherits backend limitations (single-process for JSON; limited for SQLite).
    """

    def __init__(
        self,
        *,
        data_dir: str | None = None,
        db_path: str | None = None,
    ) -> None:
        if (data_dir is None) == (db_path is None):
            raise ValueError("Provide exactly one of data_dir or db_path")
        if db_path is not None:
            self._storage = SqliteStorage(db_path)
            self._backend_type = "sqlite"
        else:
            self._storage = JsonStorage(data_dir)
            self._backend_type = "json"

    def save_entity(self, entity_type: str, entity_id: str | int, data: dict[str, Any]) -> None:
        """Save a plain dict by entity_type and entity_id."""
        self._storage.save(entity_type, entity_id, data)

    def load_entity(self, entity_type: str, entity_id: str | int) -> dict[str, Any] | None:
        """Load entity dict; return None if missing."""
        return self._storage.load(entity_type, entity_id)

    def delete_entity(self, entity_type: str, entity_id: str | int) -> None:
        """Remove the entity from storage."""
        self._storage.delete(entity_type, entity_id)

    def list_entity_ids(self, entity_type: str) -> list[str]:
        """Return list of entity_id strings for this entity_type."""
        return self._storage.list_ids(entity_type)

    def close(self) -> None:
        """Close backend resources; no-op for JSON, closes DB for SQLite."""
        if hasattr(self._storage, "close"):
            self._storage.close()

    def __enter__(self) -> "DataLake":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
        return None

    def save_entity_obj(self, entity: Any) -> None:
        """Serialize entity with 3.3 to_dict and save via underlying storage. Raises ValueError if type unknown."""
        class_to_type, _type_to_from, type_to_to_dict = _get_entity_registries()
        entity_type = class_to_type.get(type(entity))
        if entity_type is None:
            raise ValueError(f"Unknown entity type for save_entity_obj: {type(entity).__name__}")
        to_dict_fn = type_to_to_dict[entity_type]
        entity_id = _datalake_entity_id(entity, entity_type)
        self.save_entity(entity_type, entity_id, to_dict_fn(entity))

    def load_entity_obj(self, entity_type: str, entity_id: str | int) -> Any | None:
        """Load entity dict and deserialize with 3.3 from_dict. Return None if missing."""
        _, type_to_from_dict, _ = _get_entity_registries()
        if entity_type not in type_to_from_dict:
            raise ValueError(f"Unknown entity_type for load_entity_obj: {entity_type}")
        data = self.load_entity(entity_type, entity_id)
        if data is None:
            return None
        return type_to_from_dict[entity_type](data)
