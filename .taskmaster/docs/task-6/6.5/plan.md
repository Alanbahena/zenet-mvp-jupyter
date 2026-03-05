# Subtask 6.5 — LangGraph Integration Utilities (`core/agents/graph_utils.py`)

## Context

**Parent task (6):** Gradio UI Foundation and LangGraph Integration Pattern.

**What this subtask achieves:** Creates `core/agents/graph_utils.py` with the three
LangGraph integration utilities — `BaseGraphState`, `make_agent_node()`, and
`build_sequential_graph()` — plus `examples/graph_example.py` as the manual wiring
validation script. This establishes the pattern all section agents (Tasks 7–12) will
follow when wrapping `BaseAgent` instances as LangGraph nodes.

**Prior subtask (6.4):** Delivered `gradio_app/app.py` with 6 tabs and section stubs.
All of `gradio_app/` is importable and `build_app()` constructs without errors.

**Next subtasks (6.6, 6.7):** 6.6 (tests) depends on `graph_utils.py` being importable.
6.7 (docs) depends on both 6.5 and 6.6 being done.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `core/agents/graph_utils.py` | `tests/unit/test_graph_utils.py` (subtask 6.6) |
| `examples/graph_example.py` | Architecture doc (subtask 6.7) |
| Import verification (headless) | Non-linear graph helpers |
| | Conditional edge wrappers |
| | LangGraph checkpointing / DataLake serialization (Risk #3) |
| | Human-in-the-loop interrupt/resume |

---

## Files to Create

| File | Action | Summary |
|------|--------|---------|
| `core/agents/graph_utils.py` | Create | `BaseGraphState`, `make_agent_node()`, `build_sequential_graph()` |
| `examples/graph_example.py` | Create | Manual wiring validation script — not run in CI |

No other files change in this subtask.

---

## Dependencies

- Subtask 6.1 done: `langgraph` 1.0.10 installed (`uv sync`)
- `core/agents/base_agent.py` exists: `BaseAgent.run(self, *, input_data: dict, context: dict | None = None) -> dict` — keyword-only args
- `core/agents/simple_agent.py` exists: `RestaurantInfoAgent(provider, name)` — used in example only
- `core/agents/utils.py` exists: `create_agent(agent_class, *, provider, **kwargs)` — canonical factory
- `core/ai/providers.py` exists: `ClaudeProvider(model_name="claude-sonnet-4-6")` — no required args
- `gradio_app.session` importable: `get_data_lake()`, `create_session(data_lake)` (subtask 6.2 done)
- `ANTHROPIC_API_KEY` in `.env` — required at runtime for `graph_example.py` only; not needed for import verification

---

## Key Design Decisions

### `BaseGraphState` carries `session_id` and `data_lake`

**Choice:** `BaseGraphState` is a `TypedDict` with exactly `session_id: str` and
`data_lake: DataLake`. All section state schemas extend this.

**Rationale:** Ensures session context is always available in every node without
callers having to redeclare it. TypedDict fields are annotations only — `DataLake`
objects pass through at runtime with no issue.

---

### `make_agent_node()` injects `session_id` automatically

**Choice:** The node function always extracts `session_id` from state and includes it
in `input_data`, even if it is not listed in `input_keys`.

**Rationale:** Agents universally need `session_id` for storage. Requiring callers to
list it in `input_keys` every time would be repetitive and error-prone.

---

### Missing `input_keys` are silently ignored

**Choice:** `{k: state[k] for k in input_keys if k in state}` — absent keys are
skipped, not raised.

**Rationale:** Avoids `KeyError` when a key is declared in the node but not yet
populated by a prior node. Graph wiring bugs surface via missing output values, not
crashes.

---

### `build_sequential_graph()` raises `ValueError` on empty `nodes`

**Choice:** Single guard: `if not nodes: raise ValueError(...)`. No other validation.

**Rationale:** Empty nodes is the only failure mode that is undetectable at `.invoke()`
time. All other errors (wrong state schema, bad node function) surface naturally at
compile or invoke time.

---

### `graph_example.py` uses `create_agent()`, not direct instantiation

**Choice:** `create_agent(RestaurantInfoAgent, provider=provider, name="extractor")`
instead of `RestaurantInfoAgent(name="extractor", provider=ClaudeProvider(...))`.

**Rationale:** `create_agent()` is the canonical factory exported from `core.agents`.
It validates the agent class is a proper `BaseAgent` subclass before constructing it.
The example demonstrates the full framework usage pattern, not just graph wiring.

---

### `graph_example.py` kept separate from `graph_utils.py`

**Choice:** Example lives in `examples/`, not imported into the utility module.

**Rationale:** Keeps `graph_utils.py` free of concrete agent dependencies
(`RestaurantInfoAgent`, `ClaudeProvider`). The example is for manual validation only
and must not be imported by the test suite.

---

## Implementation Steps

1. **Create `core/agents/graph_utils.py`:**

```python
from typing import TypedDict, Callable, Any
from langgraph.graph import StateGraph, END, START
from core.agents.base_agent import BaseAgent
from core.storage.persistence import DataLake


class BaseGraphState(TypedDict):
    session_id: str
    data_lake: DataLake


def make_agent_node(
    agent: BaseAgent,
    input_keys: list[str],
) -> Callable[[dict], dict]:
    """
    Wrap a BaseAgent as a LangGraph node function.

    The node reads input_keys from the graph state, calls agent.run(),
    and merges the result back into the state.

    Args:
        agent:      A BaseAgent instance.
        input_keys: Keys to extract from state and pass as input_data to agent.run().
                    session_id is always injected automatically from state.

    Returns:
        A node function: (state: dict) -> dict
    """
    def node(state: dict) -> dict:
        input_data = {k: state[k] for k in input_keys if k in state}
        input_data["session_id"] = state.get("session_id", "")
        result = agent.run(input_data=input_data)
        return {**state, **result}
    return node


def build_sequential_graph(
    nodes: list[tuple[str, Callable]],
    state_schema: type,
) -> Any:
    """
    Build and compile a simple linear LangGraph StateGraph.

    Args:
        nodes:        List of (node_name, node_fn) in execution order.
        state_schema: TypedDict class defining the graph state.

    Returns:
        Compiled LangGraph graph ready for .invoke().

    Raises:
        ValueError: If nodes is empty.
    """
    if not nodes:
        raise ValueError("nodes list must not be empty")
    graph = StateGraph(state_schema)
    for name, fn in nodes:
        graph.add_node(name, fn)
    graph.add_edge(START, nodes[0][0])
    for i in range(len(nodes) - 1):
        graph.add_edge(nodes[i][0], nodes[i + 1][0])
    graph.add_edge(nodes[-1][0], END)
    return graph.compile()
```

Constraints:
- `agent.run(input_data=input_data)` — must use keyword argument; `BaseAgent.run()` uses `*` separator (keyword-only)
- `{**state, **result}` — merges agent output into state without losing existing keys
- `graph.add_edge(START, nodes[0][0])` — `set_entry_point()` is deprecated in LangGraph 1.0.10

2. **Create `examples/graph_example.py`:**

```python
"""
Manual wiring validation for LangGraph integration pattern.

Demonstrates the full pipeline:
    create_agent() -> make_agent_node() -> build_sequential_graph() -> graph.invoke()

Requires ANTHROPIC_API_KEY in .env. Not run in the unit test suite.
Run manually:
    uv run python examples/graph_example.py
"""
from gradio_app.session import get_data_lake, create_session
from core.agents import create_agent, RestaurantInfoAgent
from core.agents.graph_utils import BaseGraphState, make_agent_node, build_sequential_graph
from core.ai.providers import ClaudeProvider
from typing import Optional


class ExampleState(BaseGraphState):
    user_message: str
    restaurant_name: Optional[str]
    restaurant_type: Optional[str]


provider = ClaudeProvider()  # defaults to claude-sonnet-4-6; reads ANTHROPIC_API_KEY from .env

agent_a = create_agent(RestaurantInfoAgent, provider=provider, name="extractor")
agent_b = create_agent(RestaurantInfoAgent, provider=provider, name="confirmer")

graph = build_sequential_graph(
    nodes=[
        ("extract", make_agent_node(agent_a, input_keys=["user_message"])),
        ("confirm", make_agent_node(agent_b, input_keys=["restaurant_name"])),
    ],
    state_schema=ExampleState,
)

data_lake = get_data_lake()
session_id = create_session(data_lake)

result = graph.invoke({
    "session_id": session_id,
    "data_lake": data_lake,
    "user_message": "Mi restaurante se llama El Rincón y es de tipo fast-casual.",
    "restaurant_name": None,
    "restaurant_type": None,
})
print(result)
```

Constraints:
- `Optional[str]` used instead of `str | None` for TypedDict fields — avoids potential
  runtime issues with LangGraph's state schema introspection on Python 3.13
- `ClaudeProvider()` uses default model (`claude-sonnet-4-6`) and reads API key from `.env`
- Both agents share the same provider instance — acceptable for MVP

3. **Verify import:**

```bash
uv run python -c "from core.agents.graph_utils import BaseGraphState, make_agent_node, build_sequential_graph; print('graph_utils OK')"
```

This confirms the module imports, all dependencies resolve, and the three exports are
available — without making any API calls.

---

## Test Coverage

No unit tests in this subtask. Tests live in subtask 6.6 (`tests/unit/test_graph_utils.py`).

Listed here for forward reference:

| Test | Validates |
|------|-----------|
| `test_make_agent_node_calls_agent_run` | `agent.run()` called exactly once |
| `test_make_agent_node_passes_correct_input_keys` | `input_data` keys = listed keys + `session_id` |
| `test_make_agent_node_merges_result_into_state` | Output state has both original and agent-returned keys |
| `test_make_agent_node_missing_input_key_ignored` | No `KeyError` when `input_keys` has absent key |
| `test_build_sequential_graph_runs_end_to_end` | 2 mock nodes; compiled graph `.invoke()` returns merged state |
| `test_build_sequential_graph_single_node` | 1 node; compiles and invokes correctly |

---

## Risks and Open Questions

1. **`DataLake` in TypedDict breaks LangGraph checkpointing.** `DataLake` is a Python
   object — not JSON-serializable. If LangGraph checkpointing is enabled (Tasks 10–11
   human-in-the-loop), the state cannot be persisted. Resolution path documented in
   parent plan Risk #3: reconstruct `DataLake` from `session_id` inside nodes, remove it
   from state before enabling checkpointing.

2. **`graph_example.py` uses `Optional[str]` for TypedDict fields.** LangGraph's state
   schema introspection on Python 3.13 may not handle `str | None` in TypedDict fields
   correctly. `Optional[str]` (from `typing`) is safer and equivalent. Verify during
   execution; switch back to `str | None` if no issue is found.

3. **`graph_utils.py` not added to `core/agents/__init__.py` exports.** Intentional —
   `graph_utils` is a standalone utility, not a framework base class. Import directly
   via `from core.agents.graph_utils import ...`.

---

## Deliverable Checklist

### `core/agents/graph_utils.py`
- [x] `BaseGraphState` is a `TypedDict` with `session_id: str` and `data_lake: DataLake`
- [x] `make_agent_node(agent, input_keys)` returns a callable node function
- [x] Node function injects `session_id` from state automatically
- [x] Node function silently ignores missing `input_keys`
- [x] Node function merges agent result into state with `{**state, **result}`
- [x] Node function calls `agent.run(input_data=input_data)` using keyword argument
- [x] `build_sequential_graph(nodes, state_schema)` raises `ValueError` on empty nodes
- [x] `build_sequential_graph` uses `add_edge(START, nodes[0][0])` (not `set_entry_point`)
- [x] Import check passes: `from core.agents.graph_utils import BaseGraphState, make_agent_node, build_sequential_graph`

### `examples/graph_example.py`
- [x] Uses `create_agent()` factory, not direct `RestaurantInfoAgent(...)` instantiation
- [x] `ExampleState` extends `BaseGraphState` with `user_message`, `restaurant_name`, `restaurant_type`
- [x] Single shared `ClaudeProvider()` instance for both agents
- [x] 2-node graph constructed with `build_sequential_graph`
- [x] `graph.invoke()` call includes `session_id`, `data_lake`, `user_message` in initial state
