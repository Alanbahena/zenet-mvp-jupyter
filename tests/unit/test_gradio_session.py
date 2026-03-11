import unittest
from unittest.mock import MagicMock
from core.storage.persistence import DataLake
from gradio_app.session import get_data_lake, create_session


class TestCreateSession(unittest.TestCase):

    def setUp(self):
        self.mock_data_lake = MagicMock(spec=DataLake)

    def test_create_session_returns_string(self):
        result = create_session(self.mock_data_lake)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_create_session_returns_primary_session(self):
        result = create_session(self.mock_data_lake)
        self.assertEqual(result, "primary_session")

    def test_create_session_is_deterministic(self):
        result_a = create_session(self.mock_data_lake)
        result_b = create_session(self.mock_data_lake)
        self.assertEqual(result_a, result_b)


class TestGetDataLake(unittest.TestCase):

    def test_get_data_lake_returns_data_lake_instance(self):
        result = get_data_lake()
        self.assertIsInstance(result, DataLake)


if __name__ == "__main__":
    unittest.main()
