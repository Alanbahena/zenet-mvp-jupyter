# Task 6 — Gradio UI Foundation and LangGraph Integration Pattern

## Context

Task 6 builds two things that every subsequent task depends on:

1. **Gradio UI foundation** — the multi-section shell with navigation, session management,
   a reusable chat panel component, and section stub files. Tasks 7–12 own their section's
   complete left-column form design and plug their agents into the shell. Without it, no
   section can be built.

2. **LangGraph integration pattern** — a reusable pattern showing how `BaseAgent.run()`
   maps to a LangGraph node, with a shared state schema. Tasks 10 (Alineamiento) and 11
   (Estructura) use LangGraph. Establishing the pattern here prevents each of those tasks
   from inventing their own approach.

**Prior task (5):** Delivered `BaseAgent`, `AgentRegistry`, `create_agent()`,
`ConversationMemory`, `ToolRegistry`, `DataLake`. All are inputs to Task 6.

**Next tasks (7–12):** Each section task receives a stub file in `gradio_app/sections/`
and owns its complete left-column form design — Task 6 does not define it. Complex
sections (10, 11) also receive the LangGraph pattern to build their graphs on.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| Gradio app shell with 6 tab stubs (`gradio_app/app.py`) | Left-column form design for any section (Tasks 7–12) |
| Reusable chat panel component (`render_chat_panel()`) | Full agent implementations |
| Session management (`session_id` + DataLake wired to `gr.State`) | LangGraph graphs for specific sections |
| 6 section stub files in `gradio_app/sections/` | Multi-agent graph design for Alineamiento or Estructura |
| LangGraph + BaseAgent node wrapper pattern | File upload UI (Task 10) |
| Minimal working 2-node example graph (`examples/graph_example.py`) | OpenAI live costs — example graph uses mocked agents in tests |
| `uv add gradio` and `uv add langgraph` dependencies | Gradio theming or styling polish |
| Architecture doc update (`docs/Architecture/`) | |

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

### Decision 6: Section form layouts are owned entirely by Tasks 7–12

---

### Decision 7: `make_agent_node()` is always the bridge; graph structure is native LangGraph

**Choice:** Two pieces from `graph_utils.py` are used in every LangGraph graph in this
project — linear or not:
- `make_agent_node(agent, input_keys)` — always used to wrap any `BaseAgent` as a node
- `BaseGraphState` — always used as the base TypedDict for any graph's state schema

`build_sequential_graph()` is a convenience helper for simple linear chains only
(Tasks 7–9, 12 if they ever need a graph). It is **not** used by Tasks 10 and 11.

For non-linear graphs (conditional routing, validation loops, human-in-the-loop),
Tasks 10 and 11 build their graph structure directly with native LangGraph
`StateGraph` API — `add_conditional_edges()`, cycles, interrupts — using
`make_agent_node()` and `BaseGraphState` as the only project-level abstractions.

**Rationale:** Non-linear graph structure is highly specific to each section.
Abstracting conditional routing or loop patterns before knowing exactly what
Alineamiento and Estructura need is premature. Native LangGraph API is not
complicated for these cases and does not need a wrapper. The only reusable pieces
are the agent bridge (`make_agent_node`) and the base state (`BaseGraphState`).

**Choice:** Task 6 creates a minimal stub `render()` function for each section in
`gradio_app/sections/<section>.py`. The stub renders a placeholder markdown only.
Tasks 7–12 replace it with the real form — dropdowns, text inputs, file uploads,
data grids, whatever the section requires.

**Rationale:** Each section has genuinely different UI needs (Alineamiento has file
upload + results table; Bienvenida has a simple name input and type selector; Estructura
has a structured data editor). A shared form abstraction would either be too rigid to
cover all cases or too generic to be useful. Letting each section own its layout
eliminates coupling between Task 6 and the section tasks.

**Layout pattern for section tasks:** The base layout is two columns — left form,
right chat panel (`render_chat_panel`). Sections that need to display data or tables
(e.g. Alineamiento extraction results, Estructura inventory grid) may add a **third
bottom row** below the two columns using a `gr.Row` after the columns block. Task 6
does not implement this — each section task decides whether it needs a bottom row and
owns its full layout including that row.

---

## Files to Create

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/__init__.py` | Create | Empty — marks `gradio_app` as a package |
| `gradio_app/session.py` | Create | `create_session()` and `get_data_lake()` — session and DataLake factory |
| `gradio_app/components.py` | Create | `render_chat_panel()` — reusable right-column chatbot component |
| `gradio_app/sections/__init__.py` | Create | Empty — marks `sections` as a sub-package |
| `gradio_app/sections/bienvenida.py` | Create | Stub `render()` — placeholder markdown, replaced by Task 7 |
| `gradio_app/sections/clasificacion.py` | Create | Stub `render()` — placeholder markdown, replaced by Task 8 |
| `gradio_app/sections/configuracion.py` | Create | Stub `render()` — placeholder markdown, replaced by Task 9 |
| `gradio_app/sections/alineamiento.py` | Create | Stub `render()` — placeholder markdown, replaced by Task 10 |
| `gradio_app/sections/estructura.py` | Create | Stub `render()` — placeholder markdown, replaced by Task 11 |
| `gradio_app/sections/manual_operativo.py` | Create | Stub `render()` — placeholder markdown, replaced by Task 12 |
| `gradio_app/app.py` | Create | Main Gradio app — `gr.Blocks` with 6 `gr.Tab`; delegates to section modules |
| `examples/graph_example.py` | Create | Minimal 2-node LangGraph example using `RestaurantInfoAgent` |
| `core/agents/graph_utils.py` | Create | `make_agent_node()`, `BaseGraphState`, `build_sequential_graph()` |
| `docs/Architecture/architecture-gradio-and-langgraph.md` | Create | Architecture doc: Gradio session model, chat panel, LangGraph node pattern |
| `README.md` | Modify | Add architecture table row; update `gradio_app/` block in project structure |

---

## Subtask Breakdown

### 6.1 — Install dependencies

- Install Gradio: `uv add gradio`
- Verify: `python -c "import gradio as gr; print(gr.__version__)"`
- Install LangGraph: `uv add langgraph`
- Verify: `python -c "from langgraph.graph import StateGraph; print('ok')"`
- Both are pinned in `pyproject.toml` automatically via `uv add`

---

### 6.2 — Session management (`gradio_app/session.py`)

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

### 6.3 — Chat panel component (`gradio_app/components.py`)

```python
import gradio as gr
from typing import Callable

def render_chat_panel(
    chat_fn: Callable,
    session_id: gr.State,
    data_lake_ref: object,
) -> None:
    """
    Render the right-column chat panel inside an active gr.Column context.

    Renders: gr.Chatbot + gr.Textbox (user input) + Send gr.Button.
    Send button click calls chat_fn and updates the chatbot history.

    chat_fn signature: (message: str, history: list, session_id: str) -> tuple[list, str]

    data_lake_ref is NOT a Gradio component and cannot be a Gradio event handler input.
    render_chat_panel creates an internal closure that captures data_lake_ref and passes
    it to chat_fn. Gradio wires only [textbox, chatbot, session_id] as component inputs.
    Tasks 7-12 define chat_fn as receiving (message, history, session_id) — data_lake is
    already in scope inside chat_fn via the section's own closure over data_lake.
    """
```

- `gr.Chatbot`, `gr.Textbox`, and Send `gr.Button` are rendered inside the active column
- Send button click: Gradio wires `[textbox, chatbot, session_id]` as component inputs
- `render_chat_panel` creates an internal closure: `lambda msg, hist, sid: chat_fn(msg, hist, sid)` with `data_lake_ref` already captured by the caller's `chat_fn`
- `session_id` comes from `gr.State`; `data_lake_ref` reaches `chat_fn` via closure — never via Gradio
- Each section's `render()` function calls `render_chat_panel()` for its right column
- Tasks 7–12 define `chat_fn` to accept `(message: str, history: list, session_id: str)` and capture `data_lake` in their own closure

---

### 6.4 — Gradio shell (`gradio_app/app.py`) and section stubs

**`gradio_app/app.py`:**

```python
import gradio as gr
from gradio_app.session import create_session, get_data_lake
from gradio_app.sections import (
    bienvenida, clasificacion, configuracion,
    alineamiento, estructura, manual_operativo,
)

def build_app() -> gr.Blocks:
    data_lake = get_data_lake()

    with gr.Blocks(title="Zenet MVP 0.1") as demo:
        session_id = gr.State(value="")

        demo.load(fn=lambda: create_session(data_lake), outputs=[session_id])

        with gr.Tabs():
            with gr.Tab("Bienvenida"):
                bienvenida.render(session_id, data_lake)
            with gr.Tab("Clasificación"):
                clasificacion.render(session_id, data_lake)
            with gr.Tab("Configuración"):
                configuracion.render(session_id, data_lake)
            with gr.Tab("Alineamiento"):
                alineamiento.render(session_id, data_lake)
            with gr.Tab("Estructura"):
                estructura.render(session_id, data_lake)
            with gr.Tab("Manual operativo"):
                manual_operativo.render(session_id, data_lake)

    return demo

if __name__ == "__main__":
    build_app().launch()
```

**Each section stub (`gradio_app/sections/<section>.py`):**

```python
import gradio as gr

def render(session_id: gr.State, data_lake) -> None:
    """Stub — replaced by Task <N>."""
    gr.Markdown("### <Section name>\nPendiente — Task <N>.")
```

- All 6 section files follow the same stub pattern: `render(session_id, data_lake) -> None`
- `session_id` is `gr.State`; `data_lake` is a plain Python closure variable
- Tasks 7–12 replace the stub body with the real form + `render_chat_panel()` call
- App must launch without errors and all 6 tabs must be visible before subtask is complete

---

### 6.5 — LangGraph integration pattern (`core/agents/graph_utils.py`)

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

**Minimal 2-node example** (`examples/graph_example.py` — kept separate from `graph_utils.py`
to avoid importing a concrete agent into the utility module):

```python
# examples/graph_example.py
from gradio_app.session import get_data_lake, create_session
from core.agents.simple_agent import RestaurantInfoAgent
from core.agents.graph_utils import BaseGraphState, make_agent_node, build_sequential_graph
from core.ai.providers import ClaudeProvider

class ExampleState(BaseGraphState):
    user_message: str
    restaurant_name: str | None
    restaurant_type: str | None

# Build two agent instances with different prompts
agent_a = RestaurantInfoAgent(name="extractor", provider=ClaudeProvider(...))
agent_b = RestaurantInfoAgent(name="confirmer", provider=ClaudeProvider(...))

graph = build_sequential_graph(
    nodes=[
        ("extract", make_agent_node(agent_a, input_keys=["user_message"])),
        ("confirm", make_agent_node(agent_b, input_keys=["restaurant_name"])),
    ],
    state_schema=ExampleState,
)

data_lake = get_data_lake()
session_id = create_session(data_lake)
result = graph.invoke({"session_id": session_id, "data_lake": data_lake,
                       "user_message": "Mi restaurante se llama El Rincón."})
print(result)
```

- Purpose: validate the full wiring (StateGraph → node → `agent.run()` → state merge)
- Requires real API keys — run manually, not in the unit test suite
- Unit tests in `test_graph_utils.py` use mock nodes and do not depend on this file

**Guidance for Tasks 10 and 11 (non-linear graphs):**

Tasks 10 (Alineamiento) and 11 (Estructura) require non-linear graphs. They do NOT
use `build_sequential_graph()`. Instead they build their graph with native LangGraph:

```python
# Pattern for Tasks 10 / 11 — non-linear graph
from langgraph.graph import StateGraph, END, START
from core.agents.graph_utils import BaseGraphState, make_agent_node

class SectionState(BaseGraphState):   # extend base — add section-specific fields
    uploaded_file: str | None
    extracted_data: list | None
    validation_passed: bool

graph = StateGraph(SectionState)

# Wrap agents with make_agent_node — same as linear case
graph.add_node("parse",    make_agent_node(parser_agent,    ["uploaded_file"]))
graph.add_node("extract",  make_agent_node(extractor_agent, ["uploaded_file"]))
graph.add_node("validate", make_agent_node(validator_agent, ["extracted_data"]))

graph.add_edge(START, "parse")
graph.add_edge("parse", "extract")

# Conditional edge — native LangGraph, no project wrapper needed
graph.add_conditional_edges(
    "validate",
    lambda state: "done" if state["validation_passed"] else "extract",
    {"done": END, "extract": "extract"},
)
```

Rules:
- Always use `make_agent_node()` to wrap agents — never call `agent.run()` directly in a node
- Always extend `BaseGraphState` — never create a TypedDict that omits `session_id` or `data_lake`
- Tool-equipped agents work unchanged — `BaseAgent` handles the tool loop internally before returning to the graph
- For human-in-the-loop (interrupt/resume): see Risk #3 — reconstruct `DataLake` from `session_id` inside nodes before enabling LangGraph checkpointing

---

### 6.6 — Tests

Two new test files:

**`tests/unit/test_gradio_session.py`** (mocked — no Gradio launch; imports from `gradio_app.session`)

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
2. Gradio session model — `session_id`, `gr.State`, DataLake closure, one session per launch
3. Section ownership model — Task 6 provides stubs; Tasks 7–12 own each section's left column; `render(session_id, data_lake)` contract
4. Chat panel component — `render_chat_panel()` usage, `chat_fn` signature contract
5. LangGraph node pattern — `BaseGraphState`, `make_agent_node()`, `build_sequential_graph()`
6. State schema convention — how sections extend `BaseGraphState`; always include `session_id` and `data_lake`
7. Non-linear graph patterns (for Tasks 10–11) — conditional routing, validation loops, human-in-the-loop; when to use native LangGraph API vs. `build_sequential_graph()`; tool-equipped agents inside nodes
8. Known limitations — `DataLake` in state breaks LangGraph checkpointing; when it matters (Tasks 10–11 human-in-the-loop); resolution path

**Update `README.md`:**
- Add architecture table row: `| Gradio UI foundation and LangGraph pattern | architecture-gradio-and-langgraph.md |`
- Update project structure to show `gradio_app/` with `app.py`, `session.py`, `components.py`, `sections/`

---

## Dependencies

- Tasks 1–5 marked done
- `gradio` not yet in `pyproject.toml` — `uv add gradio` in subtask 6.1
- `langgraph` not yet in `pyproject.toml` — `uv add langgraph` in subtask 6.1
- `ANTHROPIC_API_KEY` in `.env` — required only for `examples/graph_example.py` (run manually);
  all unit tests use mocked providers

---

## Risks and Open Questions

1. **Gradio version compatibility.** The project's `pyproject.toml` may pin an older Gradio
   version that lacks `gr.State` or `gr.Blocks.load()`. Verify the installed version in
   subtask 6.1 before designing the layout.

2. **DataLake session directory path.** `data/sessions/` does not exist yet. `get_data_lake()`
   must create it or point to an existing `data/` subdirectory. Confirm the path is consistent
   with the DataLake conventions established in Task 3.

3. **`DataLake` instance in LangGraph state breaks checkpointing (Tasks 10–11).**
   Storing a `DataLake` object in `BaseGraphState` works for in-process graphs (all MVP
   sections) but breaks LangGraph's built-in checkpointing because the object cannot be
   serialized. This matters specifically for the **human-in-the-loop** pattern in
   Tasks 10 (Alineamiento) and 11 (Estructura), where the graph must pause for user
   review and resume after confirmation — that pause requires checkpointing.
   Resolution (apply in Tasks 10–11 when implementing interrupt/resume): store only
   `session_id: str` in state; reconstruct `DataLake` inside each node via
   `get_data_lake()` rather than reading it from state. `BaseGraphState` can be updated
   at that point to remove the `data_lake` field, or a separate `CheckpointableState`
   base can be introduced without it.

4. **Session resume — `session_id` is not persisted to disk (deferred).** `session_id` lives
   only in `gr.State` for the lifetime of the app. When the app restarts, a new `session_id`
   is generated and the operator cannot resume a previous session. The data files on disk
   survive, but nothing points to them from a new session.
   Resolution (when needed, post-MVP): in `get_data_lake()` or a new `load_or_create_session()`
   function in `gradio_app/session.py`, write the current `session_id` to a known file at
   session creation (e.g. `data/sessions/.last_session`) and reload it on the next launch
   instead of generating a new UUID4. No changes to `DataLake` or any section are required.

5. ~~**`gradio/` import path conflict.**~~ Resolved — local package is named `gradio_app/`.
   All imports use `from gradio_app.session import ...`, `from gradio_app.components import ...`,
   etc. No collision with the installed `gradio` package.

~~**[OPEN] Minimal example graph location**~~ Resolved — example lives in `examples/graph_example.py`. `graph_utils.py` has no concrete agent dependency.

~~**[OPEN] — `set_entry_point()` deprecated in LangGraph >= 0.2**~~ Resolved in subtask 6.1 — LangGraph 1.0.10 installed. Both snippets in 6.5 updated to `graph.add_edge(START, ...)` with `START` imported from `langgraph.graph`.

---

## Deliverable Checklist

### `gradio_app/session.py`
- [ ] `get_data_lake()` returns a `DataLake` instance pointed at `data/sessions/`
- [ ] `create_session(data_lake)` returns a unique UUID4 string

### `gradio_app/components.py`
- [ ] `render_chat_panel(chat_fn, session_id, data_lake_ref)` renders `gr.Chatbot` + `gr.Textbox` + Send button
- [ ] Send button click calls `chat_fn(message, history, session_id, data_lake_ref)` and updates chatbot
- [ ] Docstring documents that `data_lake_ref` is a closure variable, not a `gr.State`

### `gradio_app/sections/` (stubs)
- [ ] `bienvenida.py` — `render(session_id, data_lake)` renders placeholder markdown
- [ ] `clasificacion.py` — `render(session_id, data_lake)` renders placeholder markdown
- [ ] `configuracion.py` — `render(session_id, data_lake)` renders placeholder markdown
- [ ] `alineamiento.py` — `render(session_id, data_lake)` renders placeholder markdown
- [ ] `estructura.py` — `render(session_id, data_lake)` renders placeholder markdown
- [ ] `manual_operativo.py` — `render(session_id, data_lake)` renders placeholder markdown

### `gradio_app/app.py`
- [ ] `build_app()` creates a `gr.Blocks` app with `gr.State` for `session_id`
- [ ] `data_lake` created once via `get_data_lake()` and passed as closure to all sections
- [ ] Session created on `.load()` event via `create_session(data_lake)`
- [ ] 6 `gr.Tab` components delegate to section `render()` functions
- [ ] App launches without errors: `python -m gradio_app.app`

### `core/agents/graph_utils.py`
- [ ] `BaseGraphState` TypedDict with `session_id: str` and `data_lake: DataLake`
- [ ] `make_agent_node(agent, input_keys)` returns a LangGraph-compatible node function
- [ ] `build_sequential_graph(nodes, state_schema)` compiles a linear `StateGraph`
- [ ] `build_sequential_graph` raises `ValueError` for empty `nodes` list

### `examples/graph_example.py`
- [ ] 2-node example using `RestaurantInfoAgent` and `build_sequential_graph`
- [ ] Script runs end-to-end when API keys are present: `python examples/graph_example.py`

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
- [ ] Section 3: Section ownership model and `render()` contract
- [ ] Section 4: Chat panel component
- [ ] Section 5: LangGraph node pattern
- [ ] Section 6: State schema convention
- [ ] Section 7: Non-linear graph patterns (conditional routing, validation loops, human-in-the-loop, tool-equipped nodes)
- [ ] Section 8: Known limitations

### `README.md`
- [ ] Architecture table row added for Gradio + LangGraph pattern
- [ ] `gradio_app/` block updated in project structure (shows `app.py`, `session.py`, `components.py`, `sections/`)
