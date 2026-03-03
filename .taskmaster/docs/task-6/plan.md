# Task 6 — Gradio UI Foundation and LangGraph Integration Pattern

## Context

Task 6 builds two things that every subsequent task depends on:

1. **Gradio UI foundation** — the multi-section shell with navigation, session management,
   and reusable form+chat layout. Tasks 7–12 plug their agents and form fields into this
   shell. Without it, no section can be built.

2. **LangGraph integration pattern** — a reusable pattern showing how `BaseAgent.run()`
   maps to a LangGraph node, with a shared state schema. Tasks 10 (Alineamiento) and 11
   (Estructura) use LangGraph. Establishing the pattern here prevents each of those tasks
   from inventing their own approach.

**Prior task (5):** Delivered `BaseAgent`, `AgentRegistry`, `create_agent()`,
`ConversationMemory`, `ToolRegistry`, `DataLake`. All are inputs to Task 6.

**Next tasks (7–12):** Each section task receives a stub screen in the Gradio shell and
plugs in its agent and form fields. Complex sections (10, 11) also receive the LangGraph
pattern to build their graphs on.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| Gradio app shell with 6 tab stubs | Any section-specific form fields or agents (Tasks 7–12) |
| Reusable two-column form+chat layout component | Full agent implementations |
| Session management (`session_id` + DataLake wired to `gr.State`) | LangGraph graphs for specific sections |
| LangGraph + BaseAgent node wrapper pattern | Multi-agent graph design for Alineamiento or Estructura |
| Minimal working 2-node example graph | File upload UI (Task 10) |
| `uv add langgraph` dependency | OpenAI live costs — example graph uses mocked agents in tests |
| Architecture doc update (`docs/Architecture/`) | Gradio theming or styling polish |

---

## Architectural Decisions

### Decision 1: `gr.Blocks` with tabs — not multi-page routing

**Choice:** Single `gr.Blocks` app with 6 `gr.Tab` components for the 6 sections.

**Rationale:** Multi-page routing in Gradio requires more boilerplate and a server setup.
Tabs keep everything in one Python file, are simpler to implement for MVP, and are
sufficient for a linear pipeline where the operator moves left to right. Can be refactored
later if needed.

---

### Decision 2: Session created at app start, one session per app instance

**Choice:** `session_id` is a UUID4 generated when the Gradio app launches. It lives in a
`gr.State` component and is passed to every section's event handlers.

**Rationale:** For MVP, one operator uses the app at a time. A single session per launch is
the simplest model. Multi-user sessions (one `session_id` per user) can be added later by
moving `session_id` generation to a per-request scope.

---

### Decision 3: DataLake (JSON backend) as shared state between sections

**Choice:** Each section reads and writes to the same `DataLake` instance using the shared
`session_id`. Sections do not pass data to each other directly.

**Rationale:** Already established in the architectural discussion. DataLake is the source
of truth. The Gradio tab navigation is the pipeline — no orchestrator needed.

---

### Decision 4: BaseAgent node wrapper is a factory function, not a subclass

**Choice:** `make_agent_node(agent, input_keys)` returns a LangGraph-compatible node
function. `BaseAgent` is not modified.

**Rationale:** Keeps `BaseAgent` clean and framework-agnostic. A factory function is
simpler than a mixin or adapter class and can be added without touching any existing code.

---

### Decision 5: LangGraph state is a `TypedDict` with a fixed base + section-specific fields

**Choice:** Every LangGraph graph in this project uses a `TypedDict` state that always
includes `session_id: str` and `data_lake: DataLake`. Each section extends this base with
its own fields.

**Rationale:** Makes the DataLake accessible inside every node without passing it as an
argument. Section-specific fields are typed explicitly — no untyped dicts.

---

## Files to Create

| File | Action | Summary |
|------|--------|---------|
| `gradio/session.py` | Create | `create_session()` and `get_data_lake()` — session and DataLake factory |
| `gradio/layout.py` | Create | `create_section_layout()` — reusable two-column form+chat Gradio layout |
| `gradio/app.py` | Create | Main Gradio app — `gr.Blocks` with 6 `gr.Tab` stubs; session state wired |
| `core/agents/graph_utils.py` | Create | `make_agent_node()`, `BaseGraphState`, `build_sequential_graph()`, minimal example |
| `docs/Architecture/architecture-gradio-and-langgraph.md` | Create | Architecture doc covering Gradio session model and LangGraph node pattern |
| `README.md` | Modify | Add architecture table row; update `gradio/` block in project structure |

---

## Subtask Breakdown

### 6.1 — Install dependencies

- Verify `gradio` is importable: `python -c "import gradio as gr; print(gr.__version__)"`
- Install LangGraph: `uv add langgraph`
- Verify: `python -c "from langgraph.graph import StateGraph; print('ok')"`
- Pin versions in `pyproject.toml` via `uv add`

---

### 6.2 — Session management (`gradio/session.py`)

```python
import uuid
from core.storage.persistence import DataLake

def get_data_lake() -> DataLake:
    """Create a JSON DataLake instance for session storage."""

def create_session(data_lake: DataLake) -> str:
    """Generate a unique session_id (UUID4) for a new operator session."""
```

- `get_data_lake()` — creates a `DataLake` (JSON backend) pointed at `data/sessions/`
- `create_session(data_lake)` — generates `str(uuid.uuid4())`, returns it
- Session directory `data/sessions/` must be created if it does not exist
- No persistence of `session_id` itself — it lives in `gr.State` for the app lifetime

---

### 6.3 — Reusable layout (`gradio/layout.py`)

```python
import gradio as gr
from typing import Callable

def create_section_layout(
    title: str,
    form_fn: Callable,
    chat_fn: Callable,
) -> None:
    """
    Render a two-column section layout inside an active gr.Blocks context.

    Left column:  title + form area (rendered by form_fn)
    Right column: gr.Chatbot + gr.Textbox + Send button

    chat_fn signature: (message: str, history: list, session_id: str, data_lake: DataLake)
                       -> tuple[list, str]
    """
```

- Left column: section title + form area rendered by `form_fn()`
- Right column: `gr.Chatbot`, `gr.Textbox` for user input, Send `gr.Button`
- Send button click calls `chat_fn(message, history, session_id, data_lake)` and updates chatbot
- `session_id` and `data_lake` are passed in from the app-level `gr.State` components
- Tasks 7–12 pass their own `form_fn` and `chat_fn` — stubs for now

---

### 6.4 — Gradio shell (`gradio/app.py`)

```python
import gradio as gr
from gradio.session import create_session, get_data_lake
from gradio.layout import create_section_layout

def build_app() -> gr.Blocks:
    data_lake = get_data_lake()

    with gr.Blocks(title="Zenet MVP 0.1") as demo:
        session_id = gr.State(value="")

        demo.load(fn=lambda: create_session(data_lake), outputs=[session_id])

        with gr.Tabs():
            with gr.Tab("Bienvenida"):
                create_section_layout("Bienvenida", form_fn=_stub_form, chat_fn=_stub_chat)
            with gr.Tab("Clasificación"):
                create_section_layout("Clasificación", form_fn=_stub_form, chat_fn=_stub_chat)
            with gr.Tab("Configuración"):
                create_section_layout("Configuración", form_fn=_stub_form, chat_fn=_stub_chat)
            with gr.Tab("Alineamiento"):
                create_section_layout("Alineamiento", form_fn=_stub_form, chat_fn=_stub_chat)
            with gr.Tab("Estructura"):
                create_section_layout("Estructura", form_fn=_stub_form, chat_fn=_stub_chat)
            with gr.Tab("Manual operativo"):
                create_section_layout("Manual operativo", form_fn=_stub_form, chat_fn=_stub_chat)

    return demo

if __name__ == "__main__":
    build_app().launch()
```

- `_stub_form()` renders a placeholder `gr.Markdown("Formulario pendiente — Task 7-12")`
- `_stub_chat()` returns a static reply `"Sección en construcción."`
- `session_id` `gr.State` is initialised to `""` and set on `.load()`
- App must launch without errors before subtask is complete

---

### 6.5 — LangGraph integration pattern (`core/agents/graph_utils.py`)

```python
from typing import TypedDict, Callable, Any
from langgraph.graph import StateGraph, END
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
    """
    graph = StateGraph(state_schema)
    for name, fn in nodes:
        graph.add_node(name, fn)
    graph.set_entry_point(nodes[0][0])
    for i in range(len(nodes) - 1):
        graph.add_edge(nodes[i][0], nodes[i + 1][0])
    graph.add_edge(nodes[-1][0], END)
    return graph.compile()
```

**Minimal 2-node example** (in `core/agents/graph_utils.py` or a dedicated
`examples/graph_example.py`):
- Uses `RestaurantInfoAgent` as both nodes (different instances, different prompts)
- State has `session_id`, `data_lake`, `user_message`, `restaurant_name`, `restaurant_type`
- Node 1 extracts restaurant name from `user_message`
- Node 2 confirms/enriches using output of Node 1
- Purpose: validate the full wiring (StateGraph → node → `agent.run()` → state merge) before
  any real section depends on it

---

### 6.6 — Tests

Two new test files:

**`tests/unit/test_gradio_session.py`** (mocked — no Gradio launch)

| Test | Setup | Assertion |
|------|-------|-----------|
| `test_create_session_returns_string` | Call `create_session(mock_data_lake)` | Result is a non-empty string |
| `test_create_session_returns_valid_uuid` | Call `create_session(mock_data_lake)` | `uuid.UUID(result)` does not raise |
| `test_create_session_is_unique` | Call `create_session()` twice | Two results are not equal |
| `test_get_data_lake_returns_data_lake_instance` | Call `get_data_lake()` | `isinstance(result, DataLake)` |

**`tests/unit/test_graph_utils.py`** (mocked providers — no API calls)

| Test | Setup | Assertion |
|------|-------|-----------|
| `test_make_agent_node_calls_agent_run` | Mock `agent.run()` returning `{"key": "val"}` | Node calls `agent.run()` exactly once |
| `test_make_agent_node_passes_correct_input_keys` | State has `a`, `b`, `c`; `input_keys=["a","b"]` | `agent.run()` receives `input_data` with keys `a`, `b`, `session_id` only |
| `test_make_agent_node_merges_result_into_state` | Agent returns `{"x": 1}`; state has `{"y": 2}` | Output state has both `x` and `y` |
| `test_make_agent_node_missing_input_key_ignored` | `input_keys=["missing"]`; key absent from state | No error raised; `input_data` has only `session_id` |
| `test_build_sequential_graph_runs_end_to_end` | 2 mock nodes; valid state schema | Graph compiles and `.invoke()` returns state with both nodes' outputs |
| `test_build_sequential_graph_single_node` | 1 node | Graph compiles and `.invoke()` returns node's output |

---

### 6.7 — Architecture documentation

**Create `docs/Architecture/architecture-gradio-and-langgraph.md`:**

Sections:
1. Overview — where this layer sits (above agent framework, below section agents)
2. Gradio session model — `session_id`, `gr.State`, DataLake factory, one session per launch
3. Section layout pattern — two-column layout, `form_fn` / `chat_fn` contract
4. LangGraph node pattern — `BaseGraphState`, `make_agent_node()`, `build_sequential_graph()`
5. State schema convention — how complex sections extend `BaseGraphState`
6. Known limitations — `DataLake` in state breaks LangGraph checkpointing; MVP scope

**Update `README.md`:**
- Add architecture table row: `| Gradio UI foundation and LangGraph pattern | architecture-gradio-and-langgraph.md |`
- Update `gradio/` block in project structure to show `app.py`, `layout.py`, `session.py`

---

## Dependencies

- Tasks 1–5 marked done
- `gradio` installed (Task 1 — verify before implementing)
- `langgraph` not yet installed — `uv add langgraph` in subtask 6.1
- `ANTHROPIC_API_KEY` in `.env` — only required for live tests in other tasks; all Task 6
  tests use mocked providers

---

## Risks and Open Questions

1. **Gradio version compatibility.** The project's `pyproject.toml` may pin an older Gradio
   version that lacks `gr.State` or `gr.Blocks.load()`. Verify the installed version in
   subtask 6.1 before designing the layout.

2. **DataLake session directory path.** `data/sessions/` does not exist yet. `get_data_lake()`
   must create it or point to an existing `data/` subdirectory. Confirm the path is consistent
   with the DataLake conventions established in Task 3.

3. **`DataLake` instance in LangGraph state.** Putting a `DataLake` object in the TypedDict
   state works for in-process graphs (MVP) but breaks LangGraph's built-in checkpointing if
   it is ever enabled (checkpointing tries to serialize the state). Document this as a known
   limitation in the architecture doc. Resolution: pass `session_id` only and reconstruct
   `DataLake` inside each node if checkpointing is needed later.

4. **`gradio/` import path conflict.** Naming the module `gradio/session.py` means
   `from gradio.session import ...` could collide with Gradio's own internal modules.
   Use `from gradio_app.session import ...` or add `gradio/` to `sys.path` explicitly
   and import as `from session import ...`. Decide and document before implementing.

---

## Deliverable Checklist

### `gradio/session.py`
- [ ] `get_data_lake()` returns a `DataLake` instance pointed at `data/sessions/`
- [ ] `create_session(data_lake)` returns a unique UUID4 string

### `gradio/layout.py`
- [ ] `create_section_layout(title, form_fn, chat_fn)` renders a two-column layout
- [ ] Chat send handler calls `chat_fn` and updates `gr.Chatbot` history
- [ ] `session_id` and `data_lake` are wired through from app-level `gr.State`

### `gradio/app.py`
- [ ] `build_app()` creates a `gr.Blocks` app with `gr.State` for `session_id`
- [ ] Session created on `.load()` event via `create_session()`
- [ ] 6 `gr.Tab` stubs: Bienvenida, Clasificación, Configuración, Alineamiento, Estructura, Manual operativo
- [ ] App launches without errors: `python gradio/app.py`

### `core/agents/graph_utils.py`
- [ ] `BaseGraphState` TypedDict with `session_id: str` and `data_lake: DataLake`
- [ ] `make_agent_node(agent, input_keys)` returns a LangGraph-compatible node function
- [ ] `build_sequential_graph(nodes, state_schema)` compiles a linear `StateGraph`
- [ ] 2-node example graph runs end-to-end via `.invoke()`

### Tests
- [ ] `test_create_session_returns_string` passes
- [ ] `test_create_session_returns_valid_uuid` passes
- [ ] `test_create_session_is_unique` passes
- [ ] `test_get_data_lake_returns_data_lake_instance` passes
- [ ] `test_make_agent_node_calls_agent_run` passes
- [ ] `test_make_agent_node_passes_correct_input_keys` passes
- [ ] `test_make_agent_node_merges_result_into_state` passes
- [ ] `test_make_agent_node_missing_input_key_ignored` passes
- [ ] `test_build_sequential_graph_runs_end_to_end` passes
- [ ] `test_build_sequential_graph_single_node` passes
- [ ] Full suite passes: `python -m pytest tests/unit/ -v`

### `docs/Architecture/architecture-gradio-and-langgraph.md`
- [ ] Created at correct path
- [ ] Section 1: Overview
- [ ] Section 2: Gradio session model
- [ ] Section 3: Section layout pattern
- [ ] Section 4: LangGraph node pattern
- [ ] Section 5: State schema convention
- [ ] Section 6: Known limitations

### `README.md`
- [ ] Architecture table row added for Gradio + LangGraph pattern
- [ ] `gradio/` block updated in project structure
