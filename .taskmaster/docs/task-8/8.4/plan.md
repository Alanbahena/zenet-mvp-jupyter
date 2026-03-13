# Subtask 8.4 — Clasificación Section UI

## Context

Replaces the `clasificacion.py` stub with the full section UI: a two-column layout
with a chat panel on the left and a live classification preview on the right.
Completes the propose→preview→confirm flow — the operator converses with
`ClassificationAgent`, sees the diagnosed level update in real time, and confirms
to persist it to DataLake.

**Prior:** 8.3 delivered `render_draft_preview()` in `components.py`, which wires
`draft.change()` and `confirm_btn.click()` internally and returns `confirm_btn`.

**Next:** 8.5 adds `ClassificationAgent` to `core/agents/__init__.py` and `core/__init__.py`.

---

## Files to Modify

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/sections/clasificacion.py` | Modify | Replace stub with full `render()` + helpers |

---

## Dependencies

- 8.1 done — `ClassificationAgent` at `core/agents/classification_agent.py`
- 8.2 done — `data_lake.save_entity("classification", ...)` works
- 8.3 done — `render_draft_preview`, `_format_draft`, constants in `components.py`
- `create_agent` factory at `core/agents/utils.py`
- `ClaudeProvider` at `core/ai/providers.py`
- `DEFAULT_RESTAURANT_TYPES` at `core/domain/data_model.py`
- `ANTHROPIC_API_KEY` in `.env` for live usage

---

## Design Decisions

### Decision 1: Build chat panel inline — do NOT use `render_chat_panel`

`render_chat_panel` hardwires `outputs=[chatbot, textbox]`. The clasificacion send
button needs `outputs=[chatbot, textbox, draft_state]` to update the draft state.
Build chatbot, textbox, and send button directly in `render()`.

### Decision 2: `draft_state = gr.State({})` defined before `gr.Row()`

`draft_state` is referenced in both `send_btn.click()` outputs and passed to
`render_draft_preview()`. Gradio requires State components to be instantiated before
they are used in event wiring.

### Decision 3: `chat_fn` returns 3 values

`(history, "", draft_dict)` — the third value updates `draft_state` so `draft.change()`
fires automatically and the preview re-renders without additional wiring.

### Decision 4: `draft_dict` built from `agent.retrieve()` after run

`{"standardization_level": level} if level is not None else {}` — agent's `_data_store`
is the source of truth; empty dict preserves placeholder state when level not yet diagnosed.

### Decision 5: `confirm_fn` validates level before saving

Returns a Spanish error string if `standardization_level` is None in the draft.
Guards against the confirm button being clicked before the level is set (even though
the button is disabled until then, the guard is a safety net for edge cases).

### Decision 6: `entity_id` derived from `session_id`

`abs(hash(session_id)) % (2**31 - 1)` — same pattern as `bienvenida.py`. Deterministic
and upsert-safe: same session always maps to the same row.

### Decision 7: Import `ClassificationAgent` directly

`from core.agents.classification_agent import ClassificationAgent` — 8.5 adds it to
`__init__.py`. Until then, import directly (same pattern as bienvenida.py with WelcomeAgent).

### Decision 8: No separate status message after confirm

`confirm_btn.click()` is already wired inside `render_draft_preview` with `outputs=[]`.
The preview already shows the level — that is sufficient feedback for MVP. Adding a
second status component would require changing the `render_draft_preview` signature.

---

## Implementation

### Imports

```python
import gradio as gr

from core.agents.classification_agent import ClassificationAgent
from core.agents.utils import create_agent
from core.ai.providers import ClaudeProvider
from core.domain.data_model import DEFAULT_RESTAURANT_TYPES
from gradio_app.components import render_draft_preview
```

### `_load_classification_context(data_lake, session_id) -> dict`

```python
def _load_classification_context(data_lake, session_id: str) -> dict:
    entity_id = abs(hash(session_id)) % (2**31 - 1)
    restaurant_data = data_lake.load_entity("restaurant", entity_id)
    if not restaurant_data:
        return {}
    context = {"restaurant_name": restaurant_data.get("name")}
    type_id = restaurant_data.get("restaurant_type_id")
    if type_id is not None:
        type_map = {t.id: t.name for t in DEFAULT_RESTAURANT_TYPES}
        context["restaurant_type"] = type_map.get(type_id)
    return context
```

### `_make_chat_fn(provider, data_lake)`

```python
def _make_chat_fn(provider, data_lake):
    def chat_fn(message, history, session_id):
        if not session_id:
            history = list(history)
            history.append({"role": "assistant", "content": "Sesión no iniciada. Recarga la página."})
            return history, "", {}
        if not (message or "").strip():
            return history, "", {}
        agent = create_agent(ClassificationAgent, provider=provider, name="classification_agent")
        agent.load_state(data_lake, session_id=f"classification_agent_{session_id}")
        context = _load_classification_context(data_lake, session_id)
        try:
            result = agent.run(input_data={"user_message": message}, context=context)
            reply = result["reply"]
        except Exception:
            reply = "Hubo un problema al conectar con el asistente. Por favor, intenta de nuevo."
        agent.save_state(data_lake, session_id=f"classification_agent_{session_id}")
        history = list(history)
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        level = agent.retrieve("standardization_level")
        draft_dict = {"standardization_level": level} if level is not None else {}
        return history, "", draft_dict
    return chat_fn
```

### `_make_confirm_fn(data_lake)`

```python
def _make_confirm_fn(data_lake):
    def confirm_fn(draft_dict, session_id):
        if not session_id:
            return "Sesión no iniciada. Recarga la página."
        level = (draft_dict or {}).get("standardization_level")
        if level is None:
            return "La clasificación no está completa. Continúa la conversación con el asistente."
        entity_id = abs(hash(session_id)) % (2**31 - 1)
        try:
            data_lake.save_entity("classification", entity_id, {"standardization_level": level})
        except Exception:
            return "Error al guardar la clasificación. Por favor, intenta de nuevo."
        return f"Clasificación guardada: Nivel {level}."
    return confirm_fn
```

### `render(session_id, data_lake)`

```python
def render(session_id: gr.State, data_lake) -> None:
    provider = ClaudeProvider()
    draft_state = gr.State({})

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## Asistente de clasificación")
            chatbot = gr.Chatbot(label="Asistente Zenet", height="70vh")
            textbox = gr.Textbox(placeholder="Escribe tu mensaje...", show_label=False)
            send_btn = gr.Button("Enviar")

        with gr.Column(scale=1):
            gr.Markdown("## Clasificación propuesta")
            render_draft_preview(
                draft=draft_state,
                confirm_fn=_make_confirm_fn(data_lake),
                session_id=session_id,
            )

    chat_fn = _make_chat_fn(provider, data_lake)
    send_btn.click(
        fn=chat_fn,
        inputs=[textbox, chatbot, session_id],
        outputs=[chatbot, textbox, draft_state],
    )
```

---

## Plan Completeness

| Category | Status |
|----------|--------|
| Unit tests | Covered in 8.6 (`test_confirm_fn_persists_classification`, `test_confirm_fn_empty_session_returns_error`) |
| Live tests | Covered in 8.6 (`test_live_diagnoses_level`) |
| Error handling | `chat_fn` and `confirm_fn` both have `try/except` + session/input guards |
| Re-exports | Not applicable — section file, not exported from `core` |
| Status updates | Covered in 8.7 |
| Architecture doc | Covered in 8.7 (`clasificacion.md`) |

---

## Out of Scope

- No changes to `render_chat_panel` in `components.py`
- No separate status message after confirm
- No reset/undo of confirmed classification
- No file upload
- Exports (`__init__.py` files) handled in 8.5

---

## Risks and Open Questions

### [OPEN] — No confirmation feedback after Confirm click
**Problem:** `confirm_btn.click()` is wired inside `render_draft_preview` with
`outputs=[]` — the string returned by `confirm_fn` is discarded. No status message
is shown to the operator after clicking Confirm.
**Impact:** Operator has no explicit signal that the classification was saved. Relies
on the preview still showing the level as implicit confirmation.
**Suggested action:** Post-MVP: change `render_draft_preview` to accept an optional
`status` gr.Markdown component or return one, and wire it as an output of `confirm_btn.click()`.

### [OPEN] — `draft.change()` Gradio 6.x compatibility
**Problem:** Inherited from 8.3. If `gr.State.change()` does not fire when state is
updated via `send_btn.click()` return value, the preview never re-renders.
**Impact:** Preview stays as placeholder regardless of conversation progress.
**Suggested action:** If `.change()` doesn't fire: add `markdown` and `confirm_btn`
as additional outputs from `send_btn.click()`, return them from `render_draft_preview`,
and wire the re-render directly from the send button output chain.

---

## Deliverable Checklist

### `gradio_app/sections/clasificacion.py`
- [ ] Stub replaced with full `render()`
- [ ] `_load_classification_context()` loads restaurant name and type from DataLake
- [ ] `_make_chat_fn()` follows load_state / run / save_state pattern
- [ ] `chat_fn` returns `(history, "", draft_dict)` — 3 values
- [ ] `draft_state = gr.State({})` defined before `gr.Row()`
- [ ] Chat panel built inline (chatbot + textbox + send_btn), NOT via `render_chat_panel`
- [ ] `send_btn.click()` wired with `outputs=[chatbot, textbox, draft_state]`
- [ ] `render_draft_preview()` called with `draft_state`, `_make_confirm_fn(data_lake)`, `session_id`
- [ ] `_make_confirm_fn()` validates level before saving
- [ ] `_make_confirm_fn()` saves `{"standardization_level": level}` to DataLake
