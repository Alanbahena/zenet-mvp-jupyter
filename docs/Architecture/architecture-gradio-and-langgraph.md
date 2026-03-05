# Gradio UI and LangGraph Integration Architecture

## 1. Overview

The Gradio + LangGraph layer sits between the agent framework (Tasks 4–5) and the section agents (Tasks 7–12):

```
Notebooks / Operator
        |
   gradio_app/          <-- this layer
        |
   core/agents/         <-- agent framework (BaseAgent, graph_utils)
        |
   core/ai/             <-- LLM providers, memory, prompts
        |
   core/domain|storage  <-- data model, persistence
```

This layer is responsible for:
- Launching the Gradio UI (`build_app()`)
- Creating and owning one `DataLake` instance per app launch
- Generating and propagating a `session_id` to all sections
- Providing the reusable chat panel component (`render_chat_panel()`)
- Defining LangGraph node and graph patterns that section agents follow

It does **not** own any section-specific logic. Each section (`bienvenida`, `clasificacion`, etc.) is a stub in Task 6 and is replaced by real implementations in Tasks 7–12.

---

## 2. Gradio Session Model

### Lifecycle

One `DataLake` instance is created when `build_app()` is called and lives for the entire lifetime of the process. There is no per-request or per-tab DataLake.

```python
# gradio_app/app.py
def build_app() -> gr.Blocks:
    data_lake = get_data_lake()           # created once at startup

    with gr.Blocks(title="Zenet MVP 0.1") as demo:
        session_id = gr.State(value="")   # one gr.State per browser session

        demo.load(
            fn=lambda: create_session(data_lake),
            outputs=[session_id]
        )
        ...
```

### `gr.State` and `session_id`

`gr.State` is a Gradio component that holds per-browser-tab state. When the page loads, `demo.load` fires `create_session(data_lake)`, which returns a UUID4 string. That string is stored in `session_id` and passed to every section's `render()` call.

```python
# gradio_app/session.py
def create_session(data_lake: DataLake) -> str:
    return str(uuid.uuid4())   # e.g. "a3f8bc12-4491-9e00-f991-003211223344"
```

### Session constraints

| Property | Behavior |
|----------|----------|
| `data_lake` | Single instance, shared across all tabs |
| `session_id` | UUID4, generated per browser tab on page load |
| Persistence | `session_id` is NOT saved to disk in MVP 0.1 |
| Resume | A page reload generates a new `session_id`; prior session data is not recovered |
| Multi-user | Not supported in MVP 0.1 — single process, single DataLake |

**Storage root:** `data/sessions/` (created automatically by `get_data_lake()` on first call).

---

## 3. Section Ownership Model

### `render()` contract

Every section module in `gradio_app/sections/` must expose exactly one function:

```python
def render(session_id: gr.State, data_lake: DataLake) -> None:
    ...
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | `gr.State` | The Gradio state component holding the active session UUID |
| `data_lake` | `DataLake` | The shared DataLake instance for this process |
| return | `None` | `render()` builds Gradio components as a side effect inside the active `gr.Tab` context |

`render()` is called inside a `with gr.Tab(...)` block in `build_app()`. It must not create its own `gr.Blocks` or call `.launch()`.

### Task 6 stubs vs real implementations

Task 6 delivers stub implementations for all six sections:

```python
# gradio_app/sections/bienvenida.py  (stub)
def render(session_id: gr.State, data_lake) -> None:
    """Stub — replaced by Task 7."""
    gr.Markdown("### Bienvenida\nPendiente — Task 7.")
```

Tasks 7–12 replace each stub with a full implementation. The `render()` signature must remain identical — `build_app()` calls it without any changes.

### Section-to-task mapping

| Section | Module | Implemented in |
|---------|--------|----------------|
| Bienvenida | `sections/bienvenida.py` | Task 7 |
| Clasificación | `sections/clasificacion.py` | Task 8 |
| Configuración | `sections/configuracion.py` | Task 9 |
| Alineamiento | `sections/alineamiento.py` | Task 10 |
| Estructura | `sections/estructura.py` | Task 11 |
| Manual operativo | `sections/manual_operativo.py` | Task 12 |

---

## 4. Chat Panel Component

### `render_chat_panel()` usage

`render_chat_panel()` renders a standard chat UI (Chatbot + Textbox + Send button) inside the calling section's column context. It is the canonical way to add LLM interaction to a section.

```python
# gradio_app/components.py
def render_chat_panel(
    chat_fn: Callable,
    session_id: gr.State,
    data_lake_ref: object,
) -> None:
    ...
```

### `chat_fn` signature contract

Every `chat_fn` passed to `render_chat_panel()` must have this signature:

```python
def chat_fn(message: str, history: list, session_id: str) -> tuple[list, str]:
    ...
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `message` | `str` | The user's latest message |
| `history` | `list` | Gradio 6.x messages format: `list[{"role": str, "content": str}]` |
| `session_id` | `str` | The active session UUID (resolved from `gr.State` by Gradio) |
| return[0] | `list` | Updated history with user + assistant turns appended |
| return[1] | `str` | Empty string `""` to clear the textbox after send |

**Minimal `chat_fn` example:**

```python
def my_chat_fn(message: str, history: list, session_id: str) -> tuple[list, str]:
    response = call_agent(message, session_id)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": response})
    return history, ""
```

### `data_lake_ref` note

`data_lake_ref` is accepted by `render_chat_panel()` but is **not** wired as a Gradio event input. Gradio only wires `[textbox, chatbot, session_id]` to `chat_fn`. `data_lake` must be accessed inside `chat_fn` via closure over the `data_lake` variable from the section's `render()` scope:

```python
def render(session_id: gr.State, data_lake: DataLake) -> None:
    def chat_fn(message: str, history: list, sid: str) -> tuple[list, str]:
        # data_lake is in scope via closure — do not pass it through Gradio
        result = my_agent.run({"message": message, "session_id": sid})
        ...
    render_chat_panel(chat_fn, session_id, data_lake)
```

### Layout convention

`render_chat_panel()` renders a single-column vertical layout (Chatbot → Textbox → Button). Sections that need a data/table row below the chat area should add a `gr.Row` after the two-column block in their own `render()` function, not inside `render_chat_panel()`.

---

## 5. LangGraph Node Pattern

### `BaseGraphState`

All section graph states must extend `BaseGraphState`:

```python
# core/agents/graph_utils.py
class BaseGraphState(TypedDict):
    session_id: str
    data_lake: DataLake
```

`session_id` and `data_lake` are the two mandatory fields every section graph receives. Sections add their own fields on top (see Section 6).

### `make_agent_node()`

`make_agent_node()` wraps a `BaseAgent` instance as a LangGraph node function:

```python
def make_agent_node(
    agent: BaseAgent,
    input_keys: list[str],
) -> Callable[[dict], dict]:
```

The returned node function:
1. Reads `input_keys` from the graph state
2. Always injects `session_id` from state automatically
3. Calls `agent.run(input_data=...)` with the extracted data
4. Merges the result back into state: `{**state, **result}`

```python
# Example: wrap an agent as a node
info_node = make_agent_node(agent=restaurant_info_agent, input_keys=["raw_input"])

# The node receives the full state dict and returns an updated state dict
# node(state) -> dict
```

### `build_sequential_graph()`

`build_sequential_graph()` builds and compiles a linear `StateGraph`:

```python
def build_sequential_graph(
    nodes: list[tuple[str, Callable]],
    state_schema: type,
) -> Any:
```

- `nodes`: ordered list of `(node_name, node_fn)` pairs
- `state_schema`: the `TypedDict` class defining the graph's state
- Returns a compiled LangGraph graph ready for `.invoke()`

The wiring is always: `START → node[0] → node[1] → ... → node[-1] → END`

```python
# Example: build a two-node sequential graph
compiled = build_sequential_graph(
    nodes=[
        ("collect_info", info_node),
        ("validate_info", validation_node),
    ],
    state_schema=MyGraphState,
)

result = compiled.invoke({"session_id": sid, "data_lake": lake, "raw_input": "..."})
```

**Raises `ValueError`** if `nodes` is empty.

---

## 6. State Schema Convention

### Extending `BaseGraphState`

Each section defines its own state schema as a `TypedDict` that extends `BaseGraphState`:

```python
from typing import TypedDict
from core.agents.graph_utils import BaseGraphState

class BienvenidaGraphState(BaseGraphState):
    restaurant_name: str
    restaurant_type: str
    validation_errors: list[str]
```

Rules:
- Always include `session_id: str` and `data_lake: DataLake` by inheriting from `BaseGraphState`
- Add section-specific fields for data passed between nodes
- All fields must have explicit type annotations
- Use `list[str]` or `dict` for accumulating outputs across nodes

### State flow through nodes

Each node receives the full state dict and returns a partial or full updated state dict. `make_agent_node()` merges via `{**state, **result}`, so nodes only need to return the keys they modify:

```python
# Node that adds "restaurant_name" to state
def extract_name_node(state: dict) -> dict:
    name = parse_name(state["raw_input"])
    return {"restaurant_name": name}   # other keys are preserved by merge
```

---

## 7. Non-Linear Graph Patterns

### When to use `build_sequential_graph()` vs native LangGraph

| Scenario | Approach |
|----------|----------|
| Simple pipeline: A → B → C | `build_sequential_graph()` |
| Conditional routing (branch on output) | Native LangGraph with `add_conditional_edges` |
| Validation loop (retry until valid) | Native LangGraph with conditional back-edge |
| Human-in-the-loop (pause for input) | Native LangGraph with interrupt/resume |
| Tool-equipped agent inside a node | `make_agent_node()` — `BaseAgent` handles tool loop internally |

### Conditional routing

For branching on a node's output, use `add_conditional_edges` directly on a `StateGraph`:

```python
from langgraph.graph import StateGraph, END, START

graph = StateGraph(MyGraphState)
graph.add_node("classify", classify_node)
graph.add_node("route_a", route_a_node)
graph.add_node("route_b", route_b_node)

graph.add_edge(START, "classify")
graph.add_conditional_edges(
    "classify",
    lambda state: state["route"],   # routing function reads from state
    {"a": "route_a", "b": "route_b"},
)
graph.add_edge("route_a", END)
graph.add_edge("route_b", END)

compiled = graph.compile()
```

### Validation loop

For retrying a step until validation passes, add a conditional back-edge:

```python
graph.add_node("collect", collect_node)
graph.add_node("validate", validate_node)

graph.add_edge(START, "collect")
graph.add_edge("collect", "validate")
graph.add_conditional_edges(
    "validate",
    lambda state: "done" if not state["validation_errors"] else "retry",
    {"done": END, "retry": "collect"},
)
```

### Human-in-the-loop

LangGraph supports interrupting a graph execution to await user input via `interrupt_before` / `interrupt_after` on `.compile()`. In Zenet's context, "human-in-the-loop" means pausing a node to await the next chat message from the operator.

This requires a persistent checkpointer (see Section 8 for the limitation). It is deferred to post-MVP.

For MVP 0.1, the recommended pattern is stateless: each chat message triggers a full agent `.run()` call with the current history as context. The agent handles context continuity through its `ConversationMemory`, not through LangGraph checkpointing.

### Tool-equipped agents inside nodes

`BaseAgent` already implements a tool loop (see `core/agents/base_agent.py`). When a node needs tool-calling, wrap the agent directly with `make_agent_node()`. Do not implement a tool loop inside the node function itself.

```python
agent_with_tools = create_agent(
    MyAgent,
    provider=provider,
    name="my_agent",
)
# agent handles tool calls internally; node just invokes agent.run()
node_fn = make_agent_node(agent_with_tools, input_keys=["message"])
```

---

## 8. Known Limitations

### DataLake in graph state breaks LangGraph checkpointing

**Problem:** `BaseGraphState` includes `data_lake: DataLake`, which is a live Python object (open file handles or DB connection). LangGraph checkpointers (e.g., `SqliteSaver`, `MemorySaver`) serialize graph state to persist it between invocations. `DataLake` is not JSON-serializable and cannot be pickled safely, so enabling a checkpointer with the current state schema raises a serialization error.

**Current status:** In MVP 0.1, `build_sequential_graph()` calls `graph.compile()` with no checkpointer argument. Graphs are stateless between `.invoke()` calls. This is acceptable because all session data is read/written through `DataLake` explicitly by each node.

**Resolution path (post-MVP, Risk #3):**

1. Remove `data_lake` from `BaseGraphState`.
2. Inside each node function, reconstruct `DataLake` from `session_id`:
   ```python
   def my_node(state: dict) -> dict:
       lake = DataLake(data_dir=f"data/sessions/{state['session_id']}/")
       # use lake locally; do not store in state
       ...
   ```
3. Pass `data_lake` only via closure (from `render()` scope) or reconstruct per-node.
4. Once `data_lake` is removed from state, enable a checkpointer:
   ```python
   # Requires: uv add langgraph-checkpoint-sqlite
   from langgraph.checkpoint.sqlite import SqliteSaver
   checkpointer = SqliteSaver.from_conn_string("data/checkpoints.db")
   compiled = graph.compile(checkpointer=checkpointer)
   ```

This change enables true human-in-the-loop with `interrupt_before`, session resume after page reload, and multi-step workflow persistence.

---

## Implementation Files

| File | Contents |
|------|----------|
| `gradio_app/app.py` | `build_app()` — gr.Blocks with 6 tabs, DataLake creation, session_id wiring |
| `gradio_app/session.py` | `get_data_lake()`, `create_session()` |
| `gradio_app/components.py` | `render_chat_panel()` — reusable chat UI component |
| `gradio_app/sections/` | Six section stubs (`render()` contract, replaced by Tasks 7–12) |
| `core/agents/graph_utils.py` | `BaseGraphState`, `make_agent_node()`, `build_sequential_graph()` |
| `tests/unit/test_graph_utils.py` | Unit tests for graph_utils (6 tests) |

**See also:**
- [Agent Framework Architecture](architecture-agent-framework.md) — `BaseAgent`, tool loop, `ConversationMemory`
- [Persistence Layer Architecture](architecture-persistence.md) — `DataLake`, `JsonStorage`, `SqliteStorage`
