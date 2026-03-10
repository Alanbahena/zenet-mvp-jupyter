import os

from core.storage.persistence import DataLake


def get_data_lake() -> DataLake:
    """Create a SQLite DataLake instance for session storage.

    Database path: data/zenet.db (created automatically on first call).
    """
    os.makedirs("data", exist_ok=True)
    return DataLake(db_path="data/zenet.db")


def create_session(data_lake: DataLake) -> str:
    """Return the fixed session key for this MVP install.

    MVP design: one install = one restaurant = one session key.
    Data persists across app restarts. To wipe and start fresh,
    run reset_session.py from the project root.
    """
    return "primary_session"
