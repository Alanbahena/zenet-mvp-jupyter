# Subtask 6.3 — Chat Panel Component (`gradio_app/components.py`)

## Context

**Parent task (6):** Gradio UI Foundation and LangGraph Integration Pattern.

**What this subtask achieves:** Creates the reusable right-column chat component that
every section (Tasks 7–12) will call to render their AI assistant interface. This is the
only shared UI component Task 6 delivers — section form layouts are owned by each section task.

**Prior subtask (6.2):** Delivered `gradio_app/__init__.py` (package marker) and
`gradio_app/session.py` (`get_data_lake`, `create_session`).
`from gradio_app.components import render_chat_panel` will resolve once this subtask is done.

**Next subtask (6.4):** Requires `from gradio_app.components import render_chat_panel`
to wire the chat panel into each section stub in `app.py`.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `gradio_app/components.py` with `render_chat_panel()` | Any section's `chat_fn` implementation (Tasks 7–12) |
| Docstring documenting `data_lake_ref` closure pattern | `gr.Textbox.submit()` wiring for Enter key |
| Docstring documenting Gradio 6.x messages format | Streaming responses |
| | Chat history persistence |
| | `gradio_app/app.py` (subtask 6.4) |
| | Unit tests for `render_chat_panel` (no suitable unit test pattern for Gradio rendering) |

---

## Files to Create

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/components.py` | Create | `render_chat_panel(chat_fn, session_id, data_lake_ref)` |

No other files change in this subtask.

---

## Dependencies

- Subtask 6.2 done: `gradio_app/__init__.py` exists
- `gradio` 6.8.0 installed — all components confirmed present:
  `gr.Chatbot`, `gr.Textbox`, `gr.Button`, `gr.Column`, `gr.State`
- No env vars required

---

## Key Design Decisions

### `data_lake_ref` travels via closure, not Gradio event inputs

**Choice:** Gradio wires only `[textbox, chatbot, session_id]` as component inputs to the
Send button handler. `data_lake_ref` is captured in the caller's `chat_fn` closure — it
is never passed through Gradio's event system.

**Rationale:** Gradio cannot serialize a `DataLake` object. Passing it as a `gr.State`
would require JSON-serialization or pickling, which DataLake does not support. The closure
pattern gives each section's `chat_fn` access to `data_lake` without involving Gradio.

---

### `chat_fn` signature is `(message, history, session_id)` — Tasks 7–12 contract

**Choice:** `render_chat_panel` passes exactly three arguments to `chat_fn`:
`message: str`, `history: list`, `session_id: str`.

**Rationale:** These are the three values Gradio wires as component inputs. `data_lake`
is already in scope inside `chat_fn` via the section's closure. Adding `data_lake` as a
fourth argument would require it to go through Gradio, which is not possible.

---

### Gradio 6.x messages format — history is `list[dict]`, not tuples

**Choice:** History passed to and returned from `chat_fn` uses the Gradio 6.x messages
format: `list[{"role": str, "content": str}]`. The old tuple format
`[(user_str, bot_str)]` is not supported in Gradio 6.8.0.

**Rationale:** `gr.Chatbot` in Gradio 6.8.0 expects `list[ChatMessage | MessageDict]`.
Each message has `role` ("user" or "assistant") and `content` (str). Tasks 7–12 must
append messages in this format when implementing their `chat_fn`.

---

### `render_chat_panel` renders inside the caller's active column context

**Choice:** The function does not create a `gr.Column` itself. The caller enters a column
context before calling `render_chat_panel`.

**Rationale:** Column width, scale, and layout are section-specific decisions. Forcing
a column inside the component would prevent sections from controlling their layout.

---

## Implementation Steps

1. **Create `gradio_app/components.py`:**

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
      - history uses Gradio 6.x messages format: list[{"role": str, "content": str}]
      - returns: (updated_history, "") where updated_history appends user + assistant turns
      - example:
          history.append({"role": "user",      "content": message})
          history.append({"role": "assistant",  "content": response})
          return history, ""

    data_lake_ref is NOT a Gradio component and cannot be a Gradio event handler input.
    data_lake_ref is accepted as a parameter but is NOT passed to chat_fn by this component.
    Gradio wires only [textbox, chatbot, session_id] as component inputs.
    Tasks 7-12 define chat_fn as receiving (message, history, session_id) — data_lake is
    already in scope inside chat_fn via the section's own closure over data_lake.

    Layout note: sections that need a bottom data/table row may add a gr.Row after the
    two-column block in their render() function. See Decision 6 in the Task 6 plan.
    """
    chatbot = gr.Chatbot(label="Asistente Zenet")
    textbox = gr.Textbox(placeholder="Escribe tu mensaje...", show_label=False)
    send_btn = gr.Button("Enviar")

    def _handler(message: str, history: list, sid: str) -> tuple[list, str]:
        return chat_fn(message, history, sid)

    send_btn.click(
        fn=_handler,
        inputs=[textbox, chatbot, session_id],
        outputs=[chatbot, textbox],
    )
```

   Constraints:
   - `gr.Button.click(fn, inputs, outputs)` — confirmed signature for Gradio 6.8.0
   - `inputs` is exactly `[textbox, chatbot, session_id]` — `data_lake_ref` is NOT here
   - `outputs` is `[chatbot, textbox]` — chatbot receives updated history; textbox receives `""` to clear
   - `_handler` returns `tuple[list, str]` — `(updated_history, "")` to clear the input
   - The `_handler` closure exists so `data_lake_ref` is captured in scope even if unused
     in this subtask — it is available for future resume behavior without signature changes

---

## Test Coverage

No unit tests in this subtask. Testing `render_chat_panel` requires an active Gradio
`gr.Blocks` context — there is no suitable lightweight unit test pattern for Gradio
component rendering at MVP scope.

Functional verification happens in subtask 6.4: the app must launch without errors and
all 6 tabs must render — this confirms `render_chat_panel` wires correctly in context.

---

## Risks and Open Questions

1. **Tasks 7–12 must use Gradio 6.x messages format.** `chat_fn` must return
   `list[{"role": ..., "content": ...}]`, not tuples. This is documented in the docstring
   and must be repeated in each section task's plan. If a section returns tuples, the
   Chatbot will render incorrectly without raising an error.

2. **Enter key not wired.** The plan only wires the Send button via `.click()`. Operators
   who press Enter will not submit. Adding `.submit()` on `gr.Textbox` with the same
   handler is a one-line fix any section task can add, or it can be added to this file
   in a future subtask. Not a blocker for MVP.

3. **No unit tests for `render_chat_panel`.** Functional check deferred to 6.4 app launch.
   Acceptable for MVP.

---

## Deliverable Checklist

- [ ] `gradio_app/components.py` created
- [ ] `render_chat_panel(chat_fn, session_id, data_lake_ref)` renders `gr.Chatbot` + `gr.Textbox` + Send button
- [ ] Send button click calls `chat_fn(message, history, session_id)` and updates chatbot
- [ ] `outputs=[chatbot, textbox]` — chatbot updated, textbox cleared on submit
- [ ] Docstring documents `data_lake_ref` is a closure variable, not a `gr.State`
- [ ] Docstring documents Gradio 6.x messages format for `chat_fn` return value
- [ ] Docstring references bottom row pattern (Decision 6 in parent plan)
