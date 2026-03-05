# Subtask 6.6 — Tests for Graph Utilities

## Context

**Parent task (6):** Gradio UI Foundation and LangGraph Integration Pattern.

**What this subtask achieves:** Creates `tests/unit/test_graph_utils.py` with 6 mocked
tests covering `make_agent_node()` and `build_sequential_graph()`. Gives the graph
utilities full automated coverage before the architecture doc closes Task 6.

**Prior subtask (6.5):** Delivered `core/agents/graph_utils.py` with `BaseGraphState`,
`make_agent_node()`, and `build_sequential_graph()` — all importable and verified.

**Next subtask (6.7):** Architecture documentation. Depends on all tests passing.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `tests/unit/test_graph_utils.py` (6 tests) | `tests/unit/test_gradio_session.py` (done in 6.2) |
| | Architecture doc (subtask 6.7) |
| | `test_build_sequential_graph_empty_nodes` (not in parent plan) |
| | Any live/API-calling tests |

---

## Files to Create

| File | Action | Summary |
|------|--------|---------|
| `tests/unit/test_graph_utils.py` | Create | 6 mocked tests for `make_agent_node` and `build_sequential_graph` |

`tests/unit/test_gradio_session.py` was listed as a 6.6 deliverable in the parent plan
but was already fully implemented in subtask 6.2. All 4 tests pass. No changes needed.

---

## Dependencies

- Subtask 6.2 done: `test_gradio_session.py` exists with all 4 tests passing
- Subtask 6.5 done: `core/agents/graph_utils.py` importable with all three exports
- No env vars required — all tests are mocked, no API calls

---

## Key Design Decisions

### Mock `agent.run()` with `MagicMock` — no real provider

**Choice:** `self.agent = MagicMock()` with `agent.run.return_value = {...}`.

**Rationale:** Tests validate node wiring logic (input extraction, state merging), not
agent behavior. No real provider or API key needed.

---

### Use real `build_sequential_graph()` with plain callable nodes

**Choice:** Node functions are plain lambdas (not `make_agent_node` wrappers) in the
`build_sequential_graph` tests.

**Rationale:** Validates the actual LangGraph compile/invoke path in isolation from agent
logic. Keeps the two concerns independently testable.

---

### Local `_TestState` TypedDict inside the test file

**Choice:** Define `_TestState(TypedDict)` with `session_id: str` and `value: int`
directly in the test file.

**Rationale:** `build_sequential_graph` requires a real TypedDict schema. No shared
fixture needed for a single test file.

---

## Implementation Steps

1. **Create `tests/unit/test_graph_utils.py`:**

```python
import unittest
from typing import TypedDict
from unittest.mock import MagicMock

from core.agents.graph_utils import make_agent_node, build_sequential_graph


class _TestState(TypedDict):
    session_id: str
    value: int


class TestMakeAgentNode(unittest.TestCase):

    def setUp(self):
        self.agent = MagicMock()

    def test_make_agent_node_calls_agent_run(self):
        self.agent.run.return_value = {"key": "val"}
        node = make_agent_node(self.agent, ["key"])
        node({"session_id": "s", "key": "input_val"})
        self.agent.run.assert_called_once()

    def test_make_agent_node_passes_correct_input_keys(self):
        self.agent.run.return_value = {}
        node = make_agent_node(self.agent, ["a", "b"])
        node({"session_id": "s", "a": 1, "b": 2, "c": 3})
        called_input = self.agent.run.call_args.kwargs["input_data"]
        self.assertEqual(set(called_input.keys()), {"a", "b", "session_id"})

    def test_make_agent_node_merges_result_into_state(self):
        self.agent.run.return_value = {"x": 1}
        node = make_agent_node(self.agent, [])
        result = node({"session_id": "s", "y": 2})
        self.assertIn("x", result)
        self.assertIn("y", result)

    def test_make_agent_node_missing_input_key_ignored(self):
        self.agent.run.return_value = {}
        node = make_agent_node(self.agent, ["missing"])
        node({"session_id": "s"})  # "missing" not in state — no error
        called_input = self.agent.run.call_args.kwargs["input_data"]
        self.assertEqual(set(called_input.keys()), {"session_id"})


class TestBuildSequentialGraph(unittest.TestCase):

    def test_build_sequential_graph_runs_end_to_end(self):
        node1 = lambda s: {**s, "value": s.get("value", 0) + 1}
        node2 = lambda s: {**s, "value": s.get("value", 0) + 10}
        graph = build_sequential_graph(
            nodes=[("n1", node1), ("n2", node2)],
            state_schema=_TestState,
        )
        result = graph.invoke({"session_id": "test", "value": 0})
        self.assertEqual(result["value"], 11)

    def test_build_sequential_graph_single_node(self):
        node = lambda s: {**s, "value": 42}
        graph = build_sequential_graph(
            nodes=[("only", node)],
            state_schema=_TestState,
        )
        result = graph.invoke({"session_id": "test", "value": 0})
        self.assertEqual(result["value"], 42)


if __name__ == "__main__":
    unittest.main()
```

Constraints:
- `call_args.kwargs["input_data"]` — requires Python 3.8+; project is on 3.13.5. No issue.
- `_TestState` must be a real `TypedDict`, not a plain dict — LangGraph's `StateGraph`
  inspects the schema at compile time.
- `build_sequential_graph` tests exercise real LangGraph compile/invoke — not purely unit.
  Acceptable for MVP.

2. **Run the suite:**

```bash
uv run python -m pytest tests/unit/test_graph_utils.py -v
```

3. **Run full suite to confirm no regressions:**

```bash
uv run python -m pytest tests/ -q
```

---

## Test Coverage

All 6 tests are mocked (no API calls):

| Test | Validates |
|------|-----------|
| `test_make_agent_node_calls_agent_run` | `agent.run()` called exactly once |
| `test_make_agent_node_passes_correct_input_keys` | `input_data` has listed keys + `session_id`; excludes unlisted keys |
| `test_make_agent_node_merges_result_into_state` | Agent output merged with original state — both keys present |
| `test_make_agent_node_missing_input_key_ignored` | Absent key in `input_keys` → no `KeyError`; `input_data` has only `session_id` |
| `test_build_sequential_graph_runs_end_to_end` | 2-node graph compiles; `.invoke()` applies both nodes in order |
| `test_build_sequential_graph_single_node` | 1-node graph compiles; `.invoke()` returns node output |

---

## Risks and Open Questions

1. **`test_gradio_session.py` listed as a 6.6 deliverable in parent plan but already
   exists from 6.2.** No action needed — all 4 tests pass. The parent plan's "two new
   test files" description is inaccurate for 6.6; only one file is new here.

2. **`build_sequential_graph` tests exercise real LangGraph.** If LangGraph's internal
   behavior changes (e.g. how `StateGraph` handles TypedDict schemas), these tests may
   need updating. Not a current concern on 1.0.10.

3. **`test_build_sequential_graph_empty_nodes` not included.** The `ValueError` guard
   in `build_sequential_graph` has no corresponding test per the parent plan. If coverage
   becomes a requirement, add it as a follow-up.

---

## Deliverable Checklist

### `tests/unit/test_gradio_session.py` *(already done in 6.2)*
- [x] `test_create_session_returns_string`
- [x] `test_create_session_returns_valid_uuid`
- [x] `test_create_session_is_unique`
- [x] `test_get_data_lake_returns_data_lake_instance`

### `tests/unit/test_graph_utils.py`
- [x] `test_make_agent_node_calls_agent_run`
- [x] `test_make_agent_node_passes_correct_input_keys`
- [x] `test_make_agent_node_merges_result_into_state`
- [x] `test_make_agent_node_missing_input_key_ignored`
- [x] `test_build_sequential_graph_runs_end_to_end`
- [x] `test_build_sequential_graph_single_node`
