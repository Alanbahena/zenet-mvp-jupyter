"""Unit tests for persistence layer (Task 3.2 JsonStorage, Task 3.4 SqliteStorage schema)."""

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
