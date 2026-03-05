# Subtask 6.4 — Gradio Shell and Section Stubs

## Context

**Parent task (6):** Gradio UI Foundation and LangGraph Integration Pattern.

**What this subtask achieves:** Assembles the full Gradio app shell — `gradio_app/app.py`
with 6 tabs and session wiring — and creates stub `render()` files for all 6 sections.
This is the first moment the app can be launched. Tasks 7–12 replace each stub body with
their real implementation.

**Prior subtask (6.3):** Delivered `gradio_app/components.py` with `render_chat_panel()`.
All of `gradio_app/__init__.py`, `session.py`, and `components.py` are importable.

**Next subtasks (6.5, 6.6):** 6.5 is independent (LangGraph utilities — no dependency on
6.4). 6.6 (tests) depends on both 6.4 and 6.5 being done.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `gradio_app/sections/__init__.py` (empty) | Any section's real form layout (Tasks 7–12) |
| 6 section stub files in `gradio_app/sections/` | `render_chat_panel()` calls from stubs |
| `gradio_app/app.py` with `build_app()` | `core/agents/graph_utils.py` (subtask 6.5) |
| App launch verification | Unit tests (subtask 6.6) |
| | Architecture doc (subtask 6.7) |

---

## Files to Create

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/sections/__init__.py` | Create | Empty — marks `sections/` as a sub-package |
| `gradio_app/sections/bienvenida.py` | Create | Stub `render()` — placeholder markdown, replaced by Task 7 |
| `gradio_app/sections/clasificacion.py` | Create | Stub `render()` — placeholder markdown, replaced by Task 8 |
| `gradio_app/sections/configuracion.py` | Create | Stub `render()` — placeholder markdown, replaced by Task 9 |
| `gradio_app/sections/alineamiento.py` | Create | Stub `render()` — placeholder markdown, replaced by Task 10 |
| `gradio_app/sections/estructura.py` | Create | Stub `render()` — placeholder markdown, replaced by Task 11 |
| `gradio_app/sections/manual_operativo.py` | Create | Stub `render()` — placeholder markdown, replaced by Task 12 |
| `gradio_app/app.py` | Create | `build_app()` — `gr.Blocks` with 6 `gr.Tab`, session wiring |

No other files change in this subtask.

---

## Dependencies

- Subtask 6.1 done: `gradio` 6.8.0 installed
- Subtask 6.2 done: `get_data_lake()`, `create_session()` importable from `gradio_app.session`
- Subtask 6.3 done: `render_chat_panel()` importable from `gradio_app.components`
- Gradio 6.8.0 API confirmed: `gr.Blocks`, `gr.Tabs`, `gr.Tab`, `gr.State`, `gr.Row`,
  `gr.Blocks.load()` all present
- No env vars required for launch

---

## Key Design Decisions

### One `data_lake` instance per app launch, shared across all sections

**Choice:** `data_lake = get_data_lake()` is called once inside `build_app()` and passed
as a plain Python argument to each section's `render(session_id, data_lake)`.

**Rationale:** All sections share the same storage backend and session. A single `DataLake`
instance avoids opening multiple file handles to the same directory and keeps the session
model simple.

---

### `session_id` initialized empty in `gr.State`, populated by `demo.load()`

**Choice:** `session_id = gr.State(value="")` starts empty. `demo.load()` fires when the
browser connects and sets it to a UUID4 via `create_session(data_lake)`.

**Rationale:** `gr.State` cannot be initialized with a function call — only a literal value.
`demo.load()` is the correct Gradio hook for running setup logic at connection time.

---

### Section stubs render placeholder markdown only

**Choice:** Each stub's `render()` body is a single `gr.Markdown(...)` call. No chat panel,
no form elements.

**Rationale:** Stubs exist only to establish the `render(session_id, data_lake) -> None`
contract and allow the app to launch. Adding any real UI here would create coupling between
Task 6 and section tasks that would need to be undone.

---

### `render()` is the section contract — signature never changes

**Choice:** Every section file exposes exactly `render(session_id: gr.State, data_lake) -> None`.
`app.py` always calls it the same way. Section tasks replace the body, not the signature.

**Rationale:** `app.py` is written once in this subtask and never touched by section tasks.
A fixed contract eliminates coordination overhead between Task 6 and Tasks 7–12.

---

## Implementation Steps

1. **Create `gradio_app/sections/__init__.py`** — empty file.

2. **Create the 6 section stubs** — all follow the same pattern:

```python
import gradio as gr


def render(session_id: gr.State, data_lake) -> None:
    """Stub — replaced by Task <N>."""
    gr.Markdown("### <Section name>\nPendiente — Task <N>.")
```

   Section names and replacement tasks:

   | File | `gr.Markdown` heading | Replaced by |
   |------|-----------------------|-------------|
   | `bienvenida.py` | `### Bienvenida` | Task 7 |
   | `clasificacion.py` | `### Clasificación` | Task 8 |
   | `configuracion.py` | `### Configuración` | Task 9 |
   | `alineamiento.py` | `### Alineamiento` | Task 10 |
   | `estructura.py` | `### Estructura` | Task 11 |
   | `manual_operativo.py` | `### Manual operativo` | Task 12 |

3. **Create `gradio_app/app.py`:**

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

   Constraints:
   - `session_id = gr.State(value="")` — `value=""` is required; `gr.State` does not
     accept a callable as initial value
   - `demo.load(fn=lambda: create_session(data_lake), outputs=[session_id])` — `data_lake`
     is captured in the lambda closure from `build_app()` scope; `session_id` is a valid
     `gr.State` output
   - Section `render()` calls happen inside their respective `gr.Tab` context — Gradio
     registers each component to the correct tab automatically
   - `if __name__ == "__main__"` block is required for `uv run python -m gradio_app.app`
     to work

4. **Verify app launches:**

```bash
uv run python -c "from gradio_app.app import build_app; app = build_app(); print('build_app() OK')"
```

   This confirms the module imports, all section stubs are importable, and `build_app()`
   constructs the `gr.Blocks` object without errors — without starting the web server.

---

## Test Coverage

No unit tests in this subtask. Functional verification via import check (step 4 above).

Full browser launch (`uv run python -m gradio_app.app`) is the final confirmation but
is a manual check — not automated. The import check is sufficient to confirm correctness
at this stage.

---

## Risks and Open Questions

1. **`demo.load()` lambda and multiple `build_app()` calls.** Each `build_app()` call
   creates a fresh `data_lake` and a new lambda. In tests (6.6), `build_app()` may be
   called to test session behavior — each call is independent. Acceptable for MVP.

2. **Section stubs don't call `render_chat_panel()`.** The chat panel is intentionally
   absent from stubs. Tasks 7–12 add it. If a section task forgets to call
   `render_chat_panel()`, the tab will silently have no chat — no error is raised.
   Mitigation: each section task's plan should include a checklist item for it.

---

## Deliverable Checklist

### `gradio_app/sections/` stubs
- [x] `bienvenida.py` — `render(session_id, data_lake)` renders placeholder markdown
- [x] `clasificacion.py` — `render(session_id, data_lake)` renders placeholder markdown
- [x] `configuracion.py` — `render(session_id, data_lake)` renders placeholder markdown
- [x] `alineamiento.py` — `render(session_id, data_lake)` renders placeholder markdown
- [x] `estructura.py` — `render(session_id, data_lake)` renders placeholder markdown
- [x] `manual_operativo.py` — `render(session_id, data_lake)` renders placeholder markdown

### `gradio_app/app.py`
- [x] `build_app()` creates a `gr.Blocks` app with `gr.State` for `session_id`
- [x] `data_lake` created once via `get_data_lake()` and passed as closure to all sections
- [x] Session created on `.load()` event via `create_session(data_lake)`
- [x] 6 `gr.Tab` components delegate to section `render()` functions
- [x] `build_app()` constructs without errors — returns `Blocks` instance
