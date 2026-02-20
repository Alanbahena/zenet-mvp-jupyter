"""Unit tests for persistence layer (Task 3.2 — JsonStorage)."""

import os
import tempfile
import unittest

from core.persistence import JsonStorage


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
