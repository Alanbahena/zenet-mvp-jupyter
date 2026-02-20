"""Unit tests for persistence layer (Task 3.2 JsonStorage, Task 3.4 schema, Task 3.5 SqliteStorage save/load)."""

import os
import tempfile
import unittest

from core.persistence import JsonStorage, SqliteStorage


class TestJsonStorage(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.storage = JsonStorage(self.tmpdir)

    def tearDown(self) -> None:
        try:
            for name in os.listdir(self.tmpdir):
                os.remove(os.path.join(self.tmpdir, name))
            os.rmdir(self.tmpdir)
        except OSError:
            pass

    def test_save_and_load_round_trip(self) -> None:
        """Minimal smoke test: save a dict, load it, assert equality."""
        data = {"id": 1, "name": "Test", "description": "Lácteos"}
        self.storage.save("recipe", 42, data)
        loaded = self.storage.load("recipe", 42)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded, data)

    def test_load_missing_returns_none(self) -> None:
        self.assertIsNone(self.storage.load("recipe", 999))

    def test_save_and_load_with_composite_entity_id(self) -> None:
        data = {"unit_id": 10, "inventory_item_id": 15, "base_unit_id": 1, "factor_to_base": 2.5}
        entity_id = "10_15"
        self.storage.save("inventory_unit_equivalence", entity_id, data)
        loaded = self.storage.load("inventory_unit_equivalence", entity_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded, data)

    def test_delete_removes_file(self) -> None:
        self.storage.save("recipe", 1, {"id": 1})
        self.assertIsNotNone(self.storage.load("recipe", 1))
        self.storage.delete("recipe", 1)
        self.assertIsNone(self.storage.load("recipe", 1))

    def test_delete_missing_is_no_op(self) -> None:
        self.storage.delete("recipe", 999)  # should not raise

    def test_list_ids_returns_saved_entity_ids(self) -> None:
        self.storage.save("recipe", 1, {"id": 1})
        self.storage.save("recipe", 2, {"id": 2})
        ids = self.storage.list_ids("recipe")
        self.assertEqual(set(ids), {"1", "2"})

    def test_list_ids_empty_for_type_with_no_files(self) -> None:
        self.assertEqual(self.storage.list_ids("user"), [])

    def test_list_ids_composite_returns_string_ids(self) -> None:
        self.storage.save("inventory_unit_equivalence", "10_15", {"unit_id": 10, "inventory_item_id": 15})
        ids = self.storage.list_ids("inventory_unit_equivalence")
        self.assertIn("10_15", ids)


class TestSqliteStorageSchema(unittest.TestCase):
    """Smoke tests for SQLite schema (Task 3.4): tables and schema_version exist."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_schema.db")

    def tearDown(self) -> None:
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            os.rmdir(self.tmpdir)
        except OSError:
            pass

    def test_create_tables_creates_all_expected_tables(self) -> None:
        """SqliteStorage init runs _create_tables(); all 11 tables exist."""
        storage = SqliteStorage(self.db_path)
        cursor = storage._conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        expected = {
            "restaurant",
            "user",
            "recipe_unit",
            "inventory_unit",
            "category_recipe",
            "family_inventory",
            "inventory_item",
            "recipe",
            "recipe_ingredient",
            "inventory_unit_equivalence",
            "schema_version",
        }
        # sqlite_sequence is auto-created by SQLite for AUTOINCREMENT; allow it
        self.assertTrue(
            expected.issubset(tables),
            f"Missing tables: {expected - tables}. Got: {tables}",
        )

    def test_schema_version_initialized_to_one(self) -> None:
        """schema_version table has a single row with version = 1."""
        storage = SqliteStorage(self.db_path)
        cursor = storage._conn.cursor()
        cursor.execute("SELECT version, applied_at FROM schema_version WHERE version = 1")
        row = cursor.fetchone()
        self.assertIsNotNone(row, "schema_version should have version 1")
        self.assertEqual(row[0], 1)
        self.assertIsNotNone(row[1], "applied_at should be set")

    def test_create_tables_idempotent(self) -> None:
        """Calling _create_tables twice (second init) does not fail."""
        storage1 = SqliteStorage(self.db_path)
        storage1._conn.close()
        storage2 = SqliteStorage(self.db_path)
        cursor = storage2._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM schema_version")
        self.assertEqual(cursor.fetchone()[0], 1, "Still exactly one schema version row")


class TestSqliteStorageSaveLoad(unittest.TestCase):
    """Save/load round-trip and behavior for SqliteStorage (Task 3.5)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_save_load.db")
        self.storage = SqliteStorage(self.db_path)

    def tearDown(self) -> None:
        try:
            self.storage.close()
        except Exception:
            pass
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            os.rmdir(self.tmpdir)
        except OSError:
            pass

    def test_restaurant_save_and_load_round_trip(self) -> None:
        data = {
            "id": 1,
            "name": "La Cocina",
            "address": "Calle Principal 123",
            "restaurant_type_id": 1,
            "notes": "Principal",
        }
        self.storage.save("restaurant", 1, data)
        loaded = self.storage.load("restaurant", 1)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["id"], data["id"])
        self.assertEqual(loaded["name"], data["name"])
        self.assertEqual(loaded["address"], data["address"])
        self.assertEqual(loaded["restaurant_type_id"], data["restaurant_type_id"])
        self.assertEqual(loaded["notes"], data["notes"])

    def test_restaurant_with_nulls_round_trip(self) -> None:
        data = {"id": 2, "name": "El Café", "address": None, "restaurant_type_id": None, "notes": None}
        self.storage.save("restaurant", 2, data)
        loaded = self.storage.load("restaurant", 2)
        self.assertIsNotNone(loaded)
        self.assertIsNone(loaded["address"])
        self.assertIsNone(loaded["restaurant_type_id"])
        self.assertIsNone(loaded["notes"])

    def test_recipe_save_and_load_round_trip(self) -> None:
        # Prerequisites: category_recipe and recipe_unit for FK
        self.storage.save("category_recipe", 1, {"id": 1, "name": "Cat", "description": None})
        self.storage.save("recipe_unit", 1, {"id": 1, "name": "g", "symbol": "g", "description": None})
        data = {
            "id": 1,
            "name": "Tacos",
            "category_id": 1,
            "description": "Tacos tradicionales",
            "steps": ["Marinar", "Cortar", "Servir"],
            "ingredients": [
                {"name": "Carne", "quantity": 500.0, "unit_id": 1, "inventory_item_id": None},
                {"name": "Cilantro", "quantity": 50.0, "unit_id": 1, "inventory_item_id": None},
            ],
        }
        self.storage.save("recipe", 1, data)
        loaded = self.storage.load("recipe", 1)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["id"], 1)
        self.assertEqual(loaded["name"], "Tacos")
        self.assertEqual(loaded["category_id"], 1)
        self.assertEqual(loaded["description"], "Tacos tradicionales")
        self.assertEqual(loaded["steps"], ["Marinar", "Cortar", "Servir"])
        self.assertEqual(len(loaded["ingredients"]), 2)
        self.assertEqual(loaded["ingredients"][0]["name"], "Carne")
        self.assertEqual(loaded["ingredients"][0]["quantity"], 500.0)
        self.assertIsNone(loaded["ingredients"][0]["inventory_item_id"])
        self.assertIsNone(loaded["ingredients"][1]["inventory_item_id"])

    def test_recipe_minimal_round_trip(self) -> None:
        self.storage.save("category_recipe", 1, {"id": 1, "name": "Cat", "description": None})
        data = {"id": 2, "name": "Enchiladas", "category_id": 1, "description": None, "steps": None, "ingredients": []}
        self.storage.save("recipe", 2, data)
        loaded = self.storage.load("recipe", 2)
        self.assertIsNotNone(loaded)
        self.assertIsNone(loaded["description"])
        self.assertIsNone(loaded["steps"])
        self.assertEqual(loaded["ingredients"], [])

    def test_inventory_unit_is_standard_round_trip(self) -> None:
        # Insert base unit first (self-referential FK can be null)
        self.storage.save("inventory_unit", 1, {"id": 1, "name": "kg", "symbol": "kg", "description": None, "base_unit_id": None, "factor_to_base": 1.0, "is_standard": True})
        data = {
            "id": 1,
            "name": "caja",
            "symbol": "caja",
            "description": "Caja",
            "base_unit_id": 1,
            "factor_to_base": 10.0,
            "is_standard": False,
        }
        self.storage.save("inventory_unit", 1, data)
        loaded = self.storage.load("inventory_unit", 1)
        self.assertIsNotNone(loaded)
        self.assertFalse(loaded["is_standard"])

    def test_inventory_unit_equivalence_save_and_load_round_trip(self) -> None:
        # Prerequisites: inventory_unit 1 and 10, inventory_item 15 (FKs)
        self.storage.save("inventory_unit", 1, {"id": 1, "name": "kg", "symbol": "kg", "description": None, "base_unit_id": None, "factor_to_base": 1.0, "is_standard": True})
        self.storage.save("inventory_unit", 10, {"id": 10, "name": "caja", "symbol": "caja", "description": None, "base_unit_id": 1, "factor_to_base": 10.0, "is_standard": False})
        self.storage.save("family_inventory", 1, {"id": 1, "name": "Fam", "description": None, "base_unit_id": 1})
        self.storage.save("inventory_item", 15, {"id": 15, "name": "Item", "unit_id": 10, "category_id": 1, "family_id": 1, "description": None})
        data = {"unit_id": 10, "inventory_item_id": 15, "base_unit_id": 1, "factor_to_base": 2.5}
        entity_id = "10_15"
        self.storage.save("inventory_unit_equivalence", entity_id, data)
        loaded = self.storage.load("inventory_unit_equivalence", entity_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["unit_id"], 10)
        self.assertEqual(loaded["inventory_item_id"], 15)
        self.assertEqual(loaded["base_unit_id"], 1)
        self.assertEqual(loaded["factor_to_base"], 2.5)

    def test_load_missing_returns_none(self) -> None:
        self.assertIsNone(self.storage.load("restaurant", 999))
        self.assertIsNone(self.storage.load("recipe", 999))
        self.assertIsNone(self.storage.load("inventory_unit_equivalence", "99_99"))

    def test_delete_removes_entity(self) -> None:
        self.storage.save("restaurant", 1, {"id": 1, "name": "Test", "address": None, "restaurant_type_id": None, "notes": None})
        self.assertIsNotNone(self.storage.load("restaurant", 1))
        self.storage.delete("restaurant", 1)
        self.assertIsNone(self.storage.load("restaurant", 1))

    def test_delete_recipe_cascades_ingredients(self) -> None:
        self.storage.save("category_recipe", 1, {"id": 1, "name": "Cat", "description": None})
        self.storage.save("recipe_unit", 1, {"id": 1, "name": "g", "symbol": "g", "description": None})
        self.storage.save("recipe", 1, {"id": 1, "name": "R", "category_id": 1, "description": None, "steps": None, "ingredients": [{"name": "X", "quantity": 1.0, "unit_id": 1, "inventory_item_id": None}]})
        self.storage.delete("recipe", 1)
        self.assertIsNone(self.storage.load("recipe", 1))

    def test_list_ids_returns_saved_ids(self) -> None:
        self.storage.save("restaurant", 1, {"id": 1, "name": "A", "address": None, "restaurant_type_id": None, "notes": None})
        self.storage.save("restaurant", 2, {"id": 2, "name": "B", "address": None, "restaurant_type_id": None, "notes": None})
        ids = self.storage.list_ids("restaurant")
        self.assertEqual(set(ids), {"1", "2"})

    def test_list_ids_composite_returns_formatted_ids(self) -> None:
        self.storage.save("inventory_unit", 1, {"id": 1, "name": "kg", "symbol": "kg", "description": None, "base_unit_id": None, "factor_to_base": 1.0, "is_standard": True})
        self.storage.save("inventory_unit", 10, {"id": 10, "name": "caja", "symbol": "caja", "description": None, "base_unit_id": 1, "factor_to_base": 10.0, "is_standard": False})
        self.storage.save("family_inventory", 1, {"id": 1, "name": "Fam", "description": None, "base_unit_id": 1})
        self.storage.save("inventory_item", 15, {"id": 15, "name": "Item", "unit_id": 10, "category_id": 1, "family_id": 1, "description": None})
        self.storage.save("inventory_unit_equivalence", "10_15", {"unit_id": 10, "inventory_item_id": 15, "base_unit_id": 1, "factor_to_base": 2.5})
        ids = self.storage.list_ids("inventory_unit_equivalence")
        self.assertIn("10_15", ids)

    def test_unknown_entity_type_save_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.storage.save("unknown_type", 1, {"id": 1})
        self.assertIn("Unknown entity_type", str(ctx.exception))

    def test_unknown_entity_type_load_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.storage.load("unknown_type", 1)
        self.assertIn("Unknown entity_type", str(ctx.exception))
