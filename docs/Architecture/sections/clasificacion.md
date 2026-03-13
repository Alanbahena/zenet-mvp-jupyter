# Clasificación Section Architecture

## 1. Overview

The Clasificación section is the second tab in the pipeline. It diagnoses the operator's
standardization level (1–3) through a short conversation and persists the result to DataLake.

Layout: **two-column** — chat on the left, live classification preview on the right.

Data produced by this section:

| Entity | Stored as | Used by |
|--------|-----------|---------|
| `classification` | `data_lake.save_entity("classification", entity_id, {"standardization_level": int})` | Tasks 9–12 to calibrate agent tone and approach |
| Agent conversation state | `data_lake.save_entity("agent_state", "classification_agent_{session_id}", ...)` | Resumed on next chat turn |

**Implementation files:**

| File | Role |
|------|------|
| `gradio_app/sections/clasificacion.py` | `render()`, `_make_chat_fn()`, `_make_confirm_fn()`, `_load_classification_context()`, `_chat_and_format()` |
| `gradio_app/components.py` | `_format_draft()`, `render_draft_preview()`, level label/description constants |
| `core/agents/classification_agent.py` | `ClassificationAgent` — conversational diagnosis agent |

---

## 2. Propose → Preview → Confirm Pattern (canonical for Tasks 9–12)

Every section from Task 8 onward that collects structured data follows this three-phase pattern:

```
Conversation turn
      │
      ▼
agent accumulates draft in _data_store
      │
      ▼
draft rendered live in right column after each turn
      │
      ▼
operator clicks Confirm → draft persisted to DataLake
```

**Rules:**
- Nothing is written to DataLake until the operator explicitly confirms
- The agent accumulates the draft in `_data_store` across turns via `agent.store()` / `agent.retrieve()`
- The right column reflects the current draft after every send, including partial states
- Tasks 9–12 reuse this same pattern — only the entity type, schema, and agent differ

---

## 3. Key Components

### `ClassificationAgent`

Conversational diagnosis agent. Identifies `standardization_level` (1, 2, or 3) through 2–4 questions.

| Attribute | Value |
|-----------|-------|
| `INPUT_SCHEMA` | `{"user_message": "A message from the restaurant operator."}` |
| `OUTPUT_SCHEMA` | `{"reply": str, "standardization_level": int\|None, "raw_response": str}` |
| `RESPONSE_MODEL` | `_ClassificationResponse` — Pydantic model enforcing `reply` + `standardization_level` |
| Language | Always Spanish |
| Tone | Warm, direct, 2–4 sentences |

`RESPONSE_MODEL` requires the LLM to return JSON with exactly these two fields. The system
prompt's `## Formato de respuesta` section names the fields explicitly — this is required
because `ClaudeProvider` with `structured_output=True` appends only a generic
"Respond with valid JSON only" instruction and does not inject field names from the schema.
Without the explicit naming, the LLM improvised `"level"` instead of `"standardization_level"`.

### `_format_draft(draft: dict) -> tuple[str, dict]`

Pure function. Converts the draft dict to a Markdown string and a `gr.update()` for the
confirm button.

- Empty dict / no level → returns `_SPECTRUM_PENDING` (full spectrum reference) + `interactive=False`
- Level set → returns enriched Markdown (headline + description + next-steps + spectrum with
  blockquote highlight on selected level) + `interactive=True`

### `render_draft_preview(draft, confirm_fn, session_id) -> tuple[gr.Markdown, gr.Button]`

Renders the right-column preview panel: `gr.Markdown` (live draft) + `gr.Button` (Confirm).
Returns both components so the caller can wire them as outputs of the send button click.

### `_make_chat_fn(provider, data_lake)`

Returns `chat_fn(message, history, session_id) -> tuple[list, str, dict]`.
- Loads agent state, runs the agent, saves agent state
- Returns `(updated_history, "", draft_dict)` — three values (extended from the Task 7 pattern)
- The extra `draft_dict` carries the current `standardization_level` for the format step

### `_make_confirm_fn(data_lake)`

Returns `confirm_fn(draft_dict, session_id) -> str`.
- Validates that `standardization_level` is present in the draft
- Saves `{"standardization_level": level}` to DataLake under entity type `"classification"`
- Returns a Spanish status message with the level label and next-step instruction

---

## 4. Gradio Wiring: Single-Handler Pattern

### Problem

`gr.State.change()` does **not** fire when a `gr.State` is updated as a return value from
a click handler. This means:

```python
# This does NOT work — draft_state.change() never fires after send_btn.click()
send_btn.click(fn=chat_fn, ..., outputs=[chatbot, textbox, draft_state])
draft_state.change(fn=_format_draft, inputs=[draft_state], outputs=[draft_markdown, confirm_btn])
```

The right column never updates because `.change()` on a `gr.State` is triggered only by
direct user interaction, not by programmatic state updates from event handlers.

### Fix: merge into a single handler

All outputs are returned from one function wired directly to `send_btn.click()`:

```python
def _chat_and_format(message, history, session_id):
    history, text, draft_dict = chat_fn(message, history, session_id)
    md, btn = _format_draft(draft_dict)
    return history, text, draft_dict, md, btn

send_btn.click(
    fn=_chat_and_format,
    inputs=[textbox, chatbot, session_id],
    outputs=[chatbot, textbox, draft_state, draft_markdown, confirm_btn],
)
```

`_chat_and_format` returns 5 values in one shot — no `.then()` chain, no `State.change()`
dependency. Tasks 9–12 must follow this same pattern when their sections update a preview
component after each chat turn.

---

## 5. Entity Stored

| Field | Value |
|-------|-------|
| Entity type | `"classification"` |
| Entity ID | `abs(hash(session_id)) % (2**31 - 1)` |
| Schema | `{"standardization_level": 1 \| 2 \| 3}` |
| Written when | Operator clicks Confirm button — not during conversation |

---

## 6. Standardization Levels

| Level | Label | Meaning | Zenet approach |
|-------|-------|---------|----------------|
| 1 | Operación en la cabeza | Everything in team memory, no documentation | Build from scratch using base templates |
| 2 | Parcialmente documentado | Some written material (Excel, notes, photos) but dispersed | Use existing material and fill gaps with templates |
| 3 | Operación estructurada | Recipes, inventory, and processes documented and organized | Import and normalize existing information |

**Used by Tasks 9–12** to calibrate agent tone, suggestions, and onboarding approach for
each section of the pipeline. Level 1 operators get step-by-step hand-holding; Level 3
operators get import-first flows.

---

## 7. Context Injection

`_load_classification_context(data_lake, session_id)` loads the restaurant entity saved by
Task 7 (Bienvenida) and returns `{"restaurant_name": str, "restaurant_type": str}`. This
context is injected into `ClassificationAgent._generate_prompt()` so the agent can
personalize its questions and diagnosis.

---

## 8. Error Handling

| Scenario | Where caught | User sees |
|----------|-------------|-----------|
| Empty session_id (chat) | `chat_fn` guard | Error message appended to history |
| Empty message | `chat_fn` guard | No-op — returns history unchanged |
| Agent API failure | `chat_fn` try/except around `agent.run()` | `"Hubo un problema al conectar con el asistente."` |
| Empty session_id (confirm) | `confirm_fn` guard | `"Sesión no iniciada. Recarga la página."` |
| No level in draft | `confirm_fn` guard | `"La clasificación no está completa. Continúa la conversación."` |
| DataLake write failure | `confirm_fn` try/except | `"Error al guardar la clasificación."` |

---

## See Also

- [Bienvenida Section Architecture](bienvenida.md) — canonical section wiring pattern
- [Agent Framework Architecture](../architecture-agent-framework.md) — `BaseAgent`, `save_state`, `load_state`
- [Gradio and LangGraph Architecture](../architecture-gradio-and-langgraph.md) — session model, `render_chat_panel()`
- [Persistence Architecture](../architecture-persistence.md) — `DataLake`, entity types
