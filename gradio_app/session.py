import uuid
from core.storage.persistence import DataLake


def get_data_lake() -> DataLake:
    """Create a JSON DataLake instance for session storage.

    Storage root: data/sessions/ (created automatically on first call).
    """
    return DataLake(data_dir="data/sessions/")


def create_session(data_lake: DataLake) -> str:
    """Generate a unique session_id (UUID4) for a new operator session.

    The session_id is not persisted to disk — it lives in gr.State for
    the app lifetime. See Risk #4 in the Task 6 plan for resume behavior.

    Args:
        data_lake: The active DataLake instance (reserved for future use
                   when session persistence is added).

    Returns:
        A UUID4 string, e.g. "a3f8bc12-4491-9e00-f991-003211223344".
    """
    return str(uuid.uuid4())
