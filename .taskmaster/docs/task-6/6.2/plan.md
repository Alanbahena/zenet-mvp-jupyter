# Subtask 6.2 — Session Management Module (`gradio_app/session.py`)

## Context

**Parent task (6):** Gradio UI Foundation and LangGraph Integration Pattern.

**What this subtask achieves:** Creates the two factory functions that wire the Gradio app
to the DataLake persistence layer — `get_data_lake()` and `create_session()`. Every section
and the app shell depend on these two functions.

**Prior subtask (6.1):** Delivered `gradio` 6.8.0 and `langgraph` 1.0.10 installed.
`gradio_app/` directory exists with only `README.md`. No `__init__.py` yet.

**Next subtask (6.3):** Requires `from gradio_app.session import get_data_lake, create_session`
to resolve. Cannot import until `gradio_app/__init__.py` exists.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `gradio_app/__init__.py` (empty package marker) | `gradio_app/components.py` (subtask 6.3) |
| `gradio_app/session.py` with `get_data_lake()` and `create_session()` | `gradio_app/app.py` (subtask 6.4) |
| `tests/unit/test_gradio_session.py` (4 unit tests) | Any section stub files |
| `data/sessions/` directory created on first call | Writing `session_id` to disk (deferred — Risk #4 in parent plan) |

---

## Files to Create

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/__init__.py` | Create | Empty — marks `gradio_app` as a Python package |
| `gradio_app/session.py` | Create | `get_data_lake()` and `create_session(data_lake)` |
| `tests/unit/test_gradio_session.py` | Create | 4 unit tests for both functions |

No other files change in this subtask.

---

## Dependencies

- Subtask 6.1 done: `gradio` and `langgraph` installed, `gradio_app/` directory exists
- `DataLake` importable from `core.storage.persistence` — confirmed in codebase
- `data/sessions/` need not be pre-created — `JsonStorage.__init__` calls
  `os.makedirs(data_dir, exist_ok=True)` automatically on first `DataLake` instantiation

---

## Key Design Decisions

### Use JSON backend pointed at `data/sessions/`

**Choice:** `get_data_lake()` returns `DataLake(data_dir="data/sessions/")`.

**Rationale:** Session data is ephemeral and file-based — JSON is simpler than SQLite for
this use case and consistent with the DataLake conventions from Task 3. The `data/` directory
already exists in the project.

---

### `session_id` is not persisted to disk

**Choice:** `create_session(data_lake)` generates `str(uuid.uuid4())` and returns it.
Nothing is written to disk. The ID lives only in `gr.State` for the app lifetime.

**Rationale:** For MVP, one operator uses the app in one sitting. A fresh session per launch
is sufficient. Resume behavior is deferred (see Risk #1 below).

---

### `data_lake` parameter is accepted but not used inside `create_session`

**Choice:** The function signature is `create_session(data_lake: DataLake) -> str` even
though the current implementation ignores `data_lake`.

**Rationale:** The signature matches how `app.py` will call it:
`demo.load(fn=lambda: create_session(data_lake), outputs=[session_id])`. When resume
behavior is added (Risk #1), `data_lake` will be used to read/write the last session ID —
the signature does not need to change.

---

## Implementation Steps

1. **Create `gradio_app/__init__.py`** — empty file.

2. **Create `gradio_app/session.py`:**

```python
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
```

   Constraints:
   - `DataLake` constructor takes `data_dir` as a **keyword-only** argument
   - Return type is `str`, not `uuid.UUID`
   - No writes to disk in this subtask

3. **Create `tests/unit/test_gradio_session.py`:**

```python
import uuid
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

    def test_create_session_returns_valid_uuid(self):
        result = create_session(self.mock_data_lake)
        # Should not raise
        uuid.UUID(result)

    def test_create_session_is_unique(self):
        result_a = create_session(self.mock_data_lake)
        result_b = create_session(self.mock_data_lake)
        self.assertNotEqual(result_a, result_b)


class TestGetDataLake(unittest.TestCase):

    def test_get_data_lake_returns_data_lake_instance(self):
        result = get_data_lake()
        self.assertIsInstance(result, DataLake)


if __name__ == "__main__":
    unittest.main()
```

---

## Test Coverage

**Mocked tests** (no API calls, no Gradio launch):

| Test | Assertion |
|------|-----------|
| `test_create_session_returns_string` | Result is a non-empty `str` |
| `test_create_session_returns_valid_uuid` | `uuid.UUID(result)` does not raise |
| `test_create_session_is_unique` | Two consecutive calls return different strings |
| `test_get_data_lake_returns_data_lake_instance` | `isinstance(result, DataLake)` is True |

Live tests: None.

Note: `test_get_data_lake_returns_data_lake_instance` will create `data/sessions/` on disk
during the test run. This is acceptable — `data/sessions/` is gitignored (added to `.gitignore`
during 6.2 validation).

---

## Risks and Open Questions

1. **Session resume not yet implemented (deferred).** `session_id` lives only in `gr.State`.
   When the app restarts, the operator cannot resume a previous session. Resolution: add
   `load_or_create_session()` to this file that reads/writes `data/sessions/.last_session`.
   Full details in Risk #4 of the parent plan.

2. **`data/sessions/` path is relative.** `DataLake(data_dir="data/sessions/")` resolves
   relative to the working directory at runtime. If the app is launched from a directory
   other than the project root, files will be written to the wrong location. For MVP
   (always launched from root via `uv run python` or `python -m gradio_app.app`), this
   is acceptable.

---

## Deliverable Checklist

- [x] `gradio_app/__init__.py` exists (empty)
- [x] `get_data_lake()` returns a `DataLake` instance pointed at `data/sessions/`
- [x] `create_session(data_lake)` returns a unique UUID4 string
- [x] `test_create_session_returns_string` passes
- [x] `test_create_session_returns_valid_uuid` passes
- [x] `test_create_session_is_unique` passes
- [x] `test_get_data_lake_returns_data_lake_instance` passes
- [x] Full suite passes: 449 passed, 17 deselected (live tests)
