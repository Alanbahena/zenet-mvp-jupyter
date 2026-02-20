"""
Persistence layer: JSON and (later) SQLite backends for entity data.

JsonStorage saves and loads plain dicts as JSON files (one file per entity).
Operates on dicts only; entity serialization is in 3.3 / DataLake in 3.6.
"""

import json
import os
from pathlib import Path
from typing import Any


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
