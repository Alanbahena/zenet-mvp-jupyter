# Bienvenida Section Architecture

## 1. Overview

The Bienvenida section is the first tab the operator sees. It has two jobs:

1. **Form** — captures the operator's name, restaurant name, and restaurant type, then persists a `Restaurant` and `User` entity to DataLake.
2. **Chat** — provides a warm companion agent ("Zeni") that answers questions about Zenet and reduces onboarding anxiety. Zeni does **not** extract or store data — the form handles that.

Data produced by this section:

| Entity | Stored as | Used by |
|--------|-----------|---------|
| `Restaurant` | `data_lake.save_entity("restaurant", entity_id, ...)` | Tasks 8–12 |
| `User` | `data_lake.save_entity("user", entity_id, ...)` | Tasks 8–12 |
| Agent conversation state | `data_lake.save_entity("agent_state", "welcome_agent_{session_id}", ...)` | Resumed on next chat turn |

**Implementation files:**

| File | Role |
|------|------|
| `gradio_app/sections/bienvenida.py` | `render()`, `_make_save_fn()`, `_make_chat_fn()`, `_load_form_context()` |
| `core/agents/welcome_agent.py` | `WelcomeAgent` — companion agent |

---

## 2. Section Wiring Pattern

This is the **canonical pattern** that all sections (Tasks 7–12) follow. Later section docs
reference this section rather than repeating it.

### Layout

Every section uses a two-column `gr.Row`:

```
gr.Row
├── gr.Column (scale=1) — Form / data capture
└── gr.Column (scale=1) — Chat (render_chat_panel)
```

### `_make_save_fn(data_lake)` — form save handler factory

Returns a closure `save_fn(...)` wired to the save button's `.click()` event.

```python
def _make_save_fn(data_lake):
    def save_fn(user_name, restaurant_name, restaurant_type_label, session_id):
        # 1. Validate required fields → return (error_str, gr.update()) on failure
        # 2. Derive entity_id from session_id
        # 3. Build domain entities
        # 4. try: data_lake.save_entity(...) × 2
        #    except Exception: return (db_error_str, gr.update())
        # 5. Return (success_str, gr.update(value=..., interactive=False))
    return save_fn
```

**Return type:** always `(str, gr.update())` — a 2-tuple.
- `[0]` — status message rendered in `gr.Markdown`
- `[1]` — `gr.update()` targeting the save button (disable on success, re-enable on field edit)

### `_make_chat_fn(provider, data_lake)` — chat handler factory

Returns a closure `chat_fn(message, history, session_id)` wired to `render_chat_panel()`.

```python
def _make_chat_fn(provider, data_lake):
    def chat_fn(message, history, session_id):
        # 1. Guard: empty session or empty message → return early
        # 2. agent = create_agent(SectionAgent, provider=provider, name="...")
        # 3. agent.load_state(data_lake, session_id=f"{agent_name}_{session_id}")
        # 4. context = _load_form_context(data_lake, session_id)
        # 5. try: result = agent.run(input_data={...}, context=context)
        #    except Exception: reply = friendly Spanish error message
        # 6. agent.save_state(data_lake, session_id=f"{agent_name}_{session_id}")
        # 7. Append user + assistant turns to history
        # 8. return history, ""
    return chat_fn
```

**Key rules:**
- Agent is re-created on every turn (stateless Gradio model — no mutable objects in `gr.State`)
- `load_state` before `run()`, `save_state` after — always, even on error
- `save_state` is called outside the try/except so partial state is not lost on API failure

### `_load_form_context(data_lake, session_id)` — context injection

Loads saved form data and returns it as a context dict for the agent:

```python
def _load_form_context(data_lake, session_id) -> dict:
    entity_id = abs(hash(session_id)) % (2**31 - 1)
    restaurant_data = data_lake.load_entity("restaurant", entity_id)
    user_data = data_lake.load_entity("user", entity_id)
    if restaurant_data and user_data:
        return {"operator_name": user_data["name"], "restaurant_name": restaurant_data["name"]}
    return {}
```

Returns `{}` if the form has not been saved yet — agent runs with base prompt only.

### Field re-enable on edit

After a successful save, the save button is disabled. Each form field wires a `.change()`
handler to re-enable it when the operator edits any field:

```python
for field in [name_input, restaurant_input, type_dropdown]:
    field.change(
        fn=lambda: gr.update(value="Guardar registro", interactive=True),
        inputs=[],
        outputs=[save_btn],
    )
```

---

## 3. Form Fields

| Field | Widget | Required | Validation |
|-------|--------|----------|------------|
| Operator name | `gr.Textbox` | Yes | `.strip()` → non-empty; error: `"El nombre del operador es obligatorio."` |
| Restaurant name | `gr.Textbox` | Yes | `.strip()` → non-empty; error: `"El nombre del restaurante es obligatorio."` |
| Restaurant type | `gr.Dropdown` | No | `None` is valid — saves `restaurant_type_id=None` |

**Dropdown choices:** names from `DEFAULT_RESTAURANT_TYPES` in `core/domain/data_model.py`:
`"Casual"`, `"Rápida"`, `"Gourmet"`, `"Cafeterías"`, `"Cafés"`

---

## 4. Entities Saved

### Entity ID derivation

Both entities share one integer `entity_id` derived deterministically from `session_id`:

```python
entity_id = abs(hash(session_id)) % (2**31 - 1)
```

For the fixed MVP session key `"primary_session"`, this always produces the same integer,
so re-saving overwrites the prior record cleanly.

### `Restaurant`

| Field | Value |
|-------|-------|
| `id` | `entity_id` |
| `name` | `restaurant_name.strip()` |
| `restaurant_type_id` | Looked up from `_RESTAURANT_TYPE_NAME_TO_ID`; `None` if dropdown left empty |

### `User`

| Field | Value |
|-------|-------|
| `id` | `entity_id` |
| `name` | `user_name.strip()` |
| `email` | `f"{session_id}@zenet.local"` (placeholder — form does not collect email) |
| `role` | `"admin"` |

---

## 5. WelcomeAgent

`WelcomeAgent` is a plain-text companion agent. It does not extract structured data.

| Attribute | Value |
|-----------|-------|
| `INPUT_SCHEMA` | `{"user_message": "A message from the restaurant operator."}` |
| `OUTPUT_SCHEMA` | `{"reply": "Conversational response in Spanish.", "raw_response": "Full LLM response string."}` |
| `RESPONSE_MODEL` | `None` — plain prose, no JSON parsing |
| Language | Always Spanish |
| Tone | Warm, human, 2–4 sentences max |

**Context injection** — `_generate_prompt()` appends operator and restaurant name to the
system prompt when available:

```python
if context.get("operator_name"):
    context_lines.append(f"El operador se llama {context['operator_name']}.")
if context.get("restaurant_name"):
    context_lines.append(f"El restaurante se llama {context['restaurant_name']}.")
```

**Plain-text pattern** (`RESPONSE_MODEL = None`):

```python
def _process_response(self, response: str) -> dict[str, Any]:
    return {"reply": response, "raw_response": response}
    # No _parse_response() call — response is plain prose, not JSON
```

---

## 6. Session and State Keys

| Key | Format | Used for |
|-----|--------|----------|
| Session ID | `"primary_session"` (fixed, MVP) | Single-operator install |
| Entity ID | `abs(hash("primary_session")) % (2**31 - 1)` | Restaurant + User lookup |
| Agent state key | `"welcome_agent_primary_session"` | `save_state` / `load_state` |

Agent state is stored under entity type `"agent_state"` in DataLake. With the SQLite
backend, this maps to the `agent_state` table (`session_id TEXT PRIMARY KEY, data TEXT`).

---

## 7. Error Handling

| Scenario | Where caught | User sees |
|----------|-------------|-----------|
| Empty session_id | `save_fn` guard | `"Sesión no iniciada. Recarga la página e intenta de nuevo."` |
| Empty operator name | `save_fn` validation | `"El nombre del operador es obligatorio."` |
| Empty restaurant name | `save_fn` validation | `"El nombre del restaurante es obligatorio."` |
| DataLake write failure | `save_fn` try/except | `"Error al guardar el registro. Por favor, intenta de nuevo."` |
| Empty message | `chat_fn` guard | No-op — returns history unchanged |
| Empty session in chat | `chat_fn` guard | Appends `"Sesión no iniciada. Recarga la página."` to history |
| Agent API failure | `chat_fn` try/except around `agent.run()` | `"Hubo un problema al conectar con el asistente. Por favor, intenta de nuevo."` |

---

## 8. Success Message

After a successful save, the status area shows:

> Bienvenido, {operator_name}. A partir de hoy, **{restaurant_name}** empieza a operar como sistema inteligente.
>
> Cuando estés listo, continúa con **2. Clasificación** en la barra de navegación.

The save button label changes to `"Registro guardado"` and becomes non-interactive until
the operator edits a field.

---

## See Also

- [Agent Framework Architecture](../architecture-agent-framework.md) — `BaseAgent`, `save_state`, `load_state`
- [Gradio and LangGraph Architecture](../architecture-gradio-and-langgraph.md) — session model, `render_chat_panel()`
- [Persistence Architecture](../architecture-persistence.md) — `DataLake`, `JsonStorage`, `SqliteStorage`
