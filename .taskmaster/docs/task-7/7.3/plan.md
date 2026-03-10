# Subtask 7.3 — Bienvenida section UI (`gradio_app/sections/bienvenida.py`)

## Context

**Parent task:** Task 7 — Bienvenida Section: Welcome Agent + Onboarding Form
**Source of truth:** `.taskmaster/docs/task-7/plan.md`

Replaces the `bienvenida.py` stub with the full two-column section: a registration
form (left) that captures and persists `Restaurant` + `User` entities, and a chat
panel (right) wiring `WelcomeAgent` with conversation memory and a static auto-greeting.

Also migrates the app to SQLite storage (from JSON) by updating `schema.py`,
`persistence.py`, and `session.py`. SQLite is already fully implemented — there is no
good reason to delay it. JSON remains the backend for tests only (ephemeral tempfile).

**Prior (7.1 + 7.2):** `WelcomeAgent` exists at `core/agents/welcome_agent.py`;
`render_chat_panel()` accepts `initial_messages`. Both are required by this subtask.

**Next (7.4):** Error handling and form validation are integrated directly into
`_make_chat_fn` and `_make_save_fn` here — 7.4 has no separate file.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `gradio_app/sections/bienvenida.py` full implementation | Any other section stub (Tasks 8–12) |
| `core/storage/schema.py` — add `agent_state` table | LangGraph graph |
| `core/storage/persistence.py` — add `agent_state` handler | Real email field in form |
| `gradio_app/session.py` — switch to SQLite backend | Notebook integration |
| Two-column layout (form + chat) | `RestaurantInfoAgent` modifications |
| `_make_save_fn` — form save + entity persistence | Role selection in form |
| `_make_chat_fn` — agent lifecycle per chat turn | Session persistence across app restarts |
| `_load_form_context` — context injection | |
| `_INITIAL_GREETING` static auto-greeting | |
| Form validation (required fields, Spanish errors) | |
| Chat error handling (try/except, Spanish error) | |

**Note on role:** The person registering in Bienvenida is always the restaurant owner
setting up the system. `User.role` is hardcoded to `"admin"` per the data model docstring:
*"The person who creates the business profile gets admin rights automatically."*
Other roles (mesero, cocinero, inventario) are for staff added later by the admin.

---

## Architectural Decisions

### Decision 1: Form handles data capture; agent handles emotions

**Choice:** `_make_save_fn` creates and persists `Restaurant` + `User`. `WelcomeAgent`
never writes to DataLake directly.

**Rationale:** Form is deterministic and validated. Agent is conversational and
non-deterministic. Mixing data capture with chat complicates validation and error recovery.

---

### Decision 2: Agent re-created per chat turn with `load_state`/`save_state`

**Choice:** Each chat turn creates a fresh `WelcomeAgent` via `create_agent()`, restores
state from DataLake, runs, then saves state back.

**Rationale:** Avoids storing mutable agent objects in `gr.State` (requires serialization).
Matches the `BaseAgent` lifecycle pattern from Task 5. State key: `f"welcome_agent_{session_id}"`.

---

### Decision 3: Static auto-greeting — no LLM call

**Choice:** `_INITIAL_GREETING` is a hardcoded list injected via `initial_messages`.

**Rationale:** No API cost, no latency, always consistent. The `render_chat_panel()`
update in 7.2 enables this. Content is a warm Spanish welcome from Zeni.

---

### Decision 4: Placeholder email for `User`

**Choice:** `User.email = f"{session_id}@zenet.local"`

**Rationale:** `User.email: str` is required (non-optional). The form does not collect
email in MVP. Session UUID4 produces a syntactically valid email that matches
`_BASIC_EMAIL_RE` in `data_model.py`. User is persisted directly — not via
`UserRegistry.add()` — so email format validation is not triggered.

---

### Decision 5: Session-derived integer entity id

**Choice:** `entity_id = abs(hash(session_id)) % (2**31 - 1)`

**Rationale:** `restaurant` and `user` tables use `INTEGER PRIMARY KEY`. The form
is submitted once per session; the same session_id always produces the same integer.
Using `abs(hash(...))` is deterministic within a Python process. Collisions are
astronomically unlikely across the UUID4 space. This avoids hardcoded `id=1` which
would collide in SQLite across sessions.

---

### Decision 6: Chat error handling wraps `agent.run()` in try/except

**Choice:** `try/except Exception` around `agent.run()`. `save_state()` always runs
(after the try/except block, not inside it).

**Rationale:** API failures should not crash the Gradio UI. `save_state()` outside the
try/except ensures partial memory is preserved even after a failed turn.

---

### Decision 7: Provider instantiated inside `render()`

**Choice:** `provider = ClaudeProvider()` is created at the top of `render()` and
closed over by `_make_chat_fn(provider, data_lake)`.

**Rationale:** `render()` signature is `render(session_id, data_lake)` per `app.py` —
no provider argument. `ClaudeProvider()` reads `ANTHROPIC_API_KEY` from `.env`
automatically (via `load_dotenv()` in `providers.py`). Module-level instantiation
would run at import time before `.env` is loaded.

---

### Decision 8: SQLite as production backend from Task 7.3 onward

**Choice:** `session.py` switches to `DataLake(db_path="data/zenet.db")`.
`schema.py` adds the `agent_state` table. `persistence.py` adds the handler.
JSON storage remains only for unit tests (ephemeral `tempfile.mkdtemp()`).

**Rationale:** SQLite is already fully implemented in Tasks 3.4–3.5. There is no
benefit to continuing with JSON files in the running app. One backend at a time —
never both simultaneously. Tests use JSON (or SQLite with a temp db) so they
remain ephemeral and independent of the production database.

---

### Decision 9: Fixed session key `"primary_session"`

**Choice:** `create_session()` returns the hardcoded string `"primary_session"` instead
of a random UUID4.

**Rationale:** The MVP is a local single-operator install used in in-person demos.
A random UUID meant all persisted data was unreachable on every app restart — the
operator had to re-enter everything from scratch each session. One install = one
restaurant = one fixed key. Reset is handled by `reset_session.py`. Multi-user
isolation is not a requirement until cloud deployment (post-MVP).

---

## Files to Modify

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/sections/bienvenida.py` | Replace stub | Full render() with form, chat, save/load logic |
| `core/storage/schema.py` | Modify | Add `agent_state` table |
| `core/storage/persistence.py` | Modify | Add `"agent_state"` to `_SQLITE_ENTITY_TYPES`; add save/load/delete/list_ids handlers |
| `gradio_app/session.py` | Modify | Switch `get_data_lake()` to SQLite; fix `create_session()` to return `"primary_session"` |
| `reset_session.py` | Create | One-command script to wipe `data/zenet.db` and start fresh |

---

## Current state of `gradio_app/sections/bienvenida.py`

```python
import gradio as gr

def render(session_id: gr.State, data_lake) -> None:
    """Stub — replaced by Task 7."""
    gr.Markdown("### Bienvenida\nPendiente — Task 7.")
```

Entire file is a stub. Replace completely.

---

## Imports

```python
import gradio as gr

from core.agents.utils import create_agent
from core.agents.welcome_agent import WelcomeAgent
from core.ai.providers import ClaudeProvider
from core.domain.data_model import DEFAULT_RESTAURANT_TYPES, Restaurant, User
from core.domain.serialization import restaurant_to_dict, user_to_dict
from gradio_app.components import render_chat_panel
```

**Constraint:** Import `WelcomeAgent` from `core.agents.welcome_agent` directly —
NOT from `core`. The `core/__init__.py` re-export is added in subtask 7.5, which runs
after this one.

---

## Implementation Steps

### Step 1 — Add `agent_state` table to `core/storage/schema.py`

Add after the `schema_version` table (before the indexes block):

```python
    # 9. Agent conversation state (text blob, keyed by session_id string)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_state (
            session_id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    """)
```

`session_id` here is the agent-scoped key (e.g. `"welcome_agent_<uuid>"`), not the
Gradio session UUID. `data` stores the full state dict serialized as a JSON string.

---

### Step 2 — Add `agent_state` handler to `core/storage/persistence.py`

**2a.** Add `"agent_state"` to `_SQLITE_ENTITY_TYPES`:

```python
_SQLITE_ENTITY_TYPES = frozenset({
    "restaurant",
    "user",
    "recipe_unit",
    "inventory_unit",
    "category_recipe",
    "family_inventory",
    "inventory_item",
    "recipe",
    "inventory_unit_equivalence",
    "agent_state",          # <-- add this
})
```

**2b.** In `SqliteStorage.save()`, add an `elif` branch before the final `self._conn.commit()`:

```python
            elif entity_type == "agent_state":
                cursor.execute(
                    """
                    INSERT INTO agent_state (session_id, data)
                    VALUES (?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        data = excluded.data
                    """,
                    (str(entity_id), json.dumps(data_dict)),
                )
```

**2c.** In `SqliteStorage.load()`, add an `elif` branch:

```python
            elif entity_type == "agent_state":
                cursor.execute(
                    "SELECT data FROM agent_state WHERE session_id = ?", (str(entity_id),)
                )
                row = cursor.fetchone()
                return json.loads(row[0]) if row else None
```

**2d.** In `SqliteStorage.delete()`, add an `elif` branch (before the generic `else`):

```python
            elif entity_type == "agent_state":
                cursor.execute(
                    "DELETE FROM agent_state WHERE session_id = ?", (str(entity_id),)
                )
```

**2e.** In `SqliteStorage.list_ids()`, add an `elif` branch (before the generic `table = entity_type`):

```python
            elif entity_type == "agent_state":
                cursor.execute("SELECT session_id FROM agent_state")
                return [row[0] for row in cursor.fetchall()]
```

---

### Step 3 — Update `gradio_app/session.py`

Replace the entire file:

```python
import os
import uuid
from core.storage.persistence import DataLake


def get_data_lake() -> DataLake:
    """Create a SQLite DataLake instance for session storage.

    Database path: data/zenet.db (created automatically on first call).
    """
    os.makedirs("data", exist_ok=True)
    return DataLake(db_path="data/zenet.db")


def create_session(data_lake: DataLake) -> str:
    """Return the fixed session key for this MVP install.

    MVP design: one install = one restaurant = one session key.
    Data persists across restarts. To reset, run reset_session.py.
    """
    return "primary_session"
```

Two changes: `get_data_lake()` switches to SQLite; `create_session()` returns
`"primary_session"` instead of a random UUID4.

---

### Step 4 (new) — Create `reset_session.py` at project root

```python
import os

db_path = "data/zenet.db"
if os.path.exists(db_path):
    os.remove(db_path)
    print("Sesión borrada. Reinicia la aplicación para empezar de nuevo.")
else:
    print("No hay sesión activa.")
```

Usage: `uv run python reset_session.py` then restart the app.

---

### Step 5 — Module-level constants in `bienvenida.py`

```python
_RESTAURANT_TYPE_OPTIONS = [t.name for t in DEFAULT_RESTAURANT_TYPES]
_RESTAURANT_TYPE_NAME_TO_ID = {t.name: t.id for t in DEFAULT_RESTAURANT_TYPES}
_INITIAL_GREETING = [
    {
        "role": "assistant",
        "content": (
            "Hola, soy Zeni, tu asistente de bienvenida en Zenet. "
            "Estoy aquí para acompañarte durante este proceso y resolver "
            "cualquier duda que tengas sobre Zenet o el registro. "
            "¿Por dónde quieres empezar?"
        ),
    }
]
```

`_INITIAL_GREETING` content is in the format `list[{"role": str, "content": str}]`
required by `gr.Chatbot` (Gradio 6.x messages format).

---

### Step 6 — `_load_form_context`

```python
def _load_form_context(data_lake, session_id: str) -> dict:
    entity_id = abs(hash(session_id)) % (2**31 - 1)
    restaurant_data = data_lake.load_entity("restaurant", entity_id)
    user_data = data_lake.load_entity("user", entity_id)
    if restaurant_data and user_data:
        return {
            "operator_name": user_data["name"],
            "restaurant_name": restaurant_data["name"],
        }
    return {}
```

Returns `{}` if either entity is missing (form not yet saved). No exceptions raised.
Uses `entity_id` (integer) — not a composite string key.

---

### Step 7 — `_make_save_fn`

Returns a closure `save_fn(user_name, restaurant_name, restaurant_type_label, session_id) -> str`:

```python
def _make_save_fn(data_lake):
    def save_fn(user_name, restaurant_name, restaurant_type_label, session_id):
        if not session_id:
            return "Sesión no iniciada. Recarga la página e intenta de nuevo."
        if not (user_name or "").strip():
            return "El nombre del operador es obligatorio."
        if not (restaurant_name or "").strip():
            return "El nombre del restaurante es obligatorio."
        entity_id = abs(hash(session_id)) % (2**31 - 1)
        restaurant_type_id = _RESTAURANT_TYPE_NAME_TO_ID.get(restaurant_type_label)
        restaurant = Restaurant(
            id=entity_id,
            name=restaurant_name.strip(),
            restaurant_type_id=restaurant_type_id,
        )
        user = User(
            id=entity_id,
            name=user_name.strip(),
            email=f"{session_id}@zenet.local",
            role="admin",
        )
        data_lake.save_entity(
            "restaurant", entity_id, restaurant_to_dict(restaurant)
        )
        data_lake.save_entity(
            "user", entity_id, user_to_dict(user)
        )
        return f"Registro guardado. Bienvenido, {user.name}."
    return save_fn
```

**Constraints:**
- Guard `if not session_id` at the top — fixes the race condition (OPEN from validation).
- Use `_RESTAURANT_TYPE_NAME_TO_ID.get(restaurant_type_label)` — NOT `[...]`. The
  dropdown returns `None` when nothing is selected; dict `[]` raises `KeyError`.
- `entity_id` is an integer — matches `restaurant` and `user` INTEGER PRIMARY KEY.

---

### Step 8 — `_make_chat_fn`

Returns a closure `chat_fn(message, history, session_id) -> tuple[list, str]`:

```python
def _make_chat_fn(provider, data_lake):
    def chat_fn(message, history, session_id):
        if not session_id:
            history = list(history)
            history.append({"role": "assistant", "content": "Sesión no iniciada. Recarga la página."})
            return history, ""
        if not (message or "").strip():
            return history, ""
        agent = create_agent(WelcomeAgent, provider=provider, name="welcome_agent")
        agent.load_state(data_lake, session_id=f"welcome_agent_{session_id}")
        context = _load_form_context(data_lake, session_id)
        try:
            result = agent.run(input_data={"user_message": message}, context=context)
            reply = result["reply"]
        except Exception:
            reply = "Hubo un problema al conectar con el asistente. Por favor, intenta de nuevo."
        agent.save_state(data_lake, session_id=f"welcome_agent_{session_id}")
        history = list(history)
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        return history, ""
    return chat_fn
```

**Constraint:** `agent.save_state()` is called AFTER the try/except block (not inside
`except`). This preserves partial memory regardless of whether the LLM call succeeded.

---

### Step 9 — `render()`

```python
def render(session_id: gr.State, data_lake) -> None:
    provider = ClaudeProvider()

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## Registro inicial")
            name_input = gr.Textbox(label="Tu nombre")
            restaurant_input = gr.Textbox(label="Nombre del restaurante")
            type_dropdown = gr.Dropdown(
                choices=_RESTAURANT_TYPE_OPTIONS,
                label="Tipo de restaurante",
                value=None,
            )
            save_btn = gr.Button("Guardar registro", variant="primary")
            save_status = gr.Markdown("")

        with gr.Column(scale=1):
            gr.Markdown("## Asistente de bienvenida")
            render_chat_panel(
                chat_fn=_make_chat_fn(provider, data_lake),
                session_id=session_id,
                data_lake_ref=data_lake,
                initial_messages=_INITIAL_GREETING,
            )

    save_btn.click(
        fn=_make_save_fn(data_lake),
        inputs=[name_input, restaurant_input, type_dropdown, session_id],
        outputs=[save_status],
    )
```

---

## Dependencies

- `core/agents/welcome_agent.py` — `WelcomeAgent` (subtask 7.1, confirmed done)
- `gradio_app/components.py` — `render_chat_panel(initial_messages=...)` (subtask 7.2, confirmed done)
- `core/ai/providers.py` — `ClaudeProvider` (confirmed present)
- `core/agents/utils.py` — `create_agent()` (confirmed present)
- `core/domain/data_model.py` — `DEFAULT_RESTAURANT_TYPES`, `Restaurant`, `User` (confirmed present)
- `core/domain/serialization.py` — `restaurant_to_dict()`, `user_to_dict()` (confirmed present)
- `core/storage/schema.py` — `_create_tables()` (confirmed present; `agent_state` table added here)
- `core/storage/persistence.py` — `SqliteStorage`, `DataLake` (confirmed present; `agent_state` handler added here)
- `ANTHROPIC_API_KEY` in `.env` — required for live chat turns

---

## Risks and Open Questions

1. **`history` mutation in `chat_fn`.** `gr.Chatbot` passes history as a list. Using
   `list(history)` before appending is safer and avoids surprising side effects. Done.

2. **`save_btn.click()` wiring placement.** All component variables are defined before
   the `.click()` call, which is placed after the `with gr.Row()` block. Either placement
   works in Gradio 6.x; after-block is cleaner.

3. **`gr.Dropdown(value=None)` for unselected state.** Gradio 6.x accepts `value=None`
   on a Dropdown with `choices=[...]`. The handler receives `None` when nothing is
   selected. `_make_save_fn` handles this correctly via `.get()`.

4. **`abs(hash(session_id))` stability.** Python's `hash()` for strings is
   randomized per-process (`PYTHONHASHSEED`). Within a single Gradio session
   (single Python process), the same `session_id` always yields the same hash.
   Across restarts the hash may differ — but `session_id` itself is not persisted
   across restarts either, so this is not a problem in MVP.

5. **Test backend.** Unit tests for `bienvenida.py` (subtask 7.6) must use JSON or
   a temp SQLite db, not `data/zenet.db`. `get_data_lake()` in production now returns
   SQLite. Tests must not call `get_data_lake()` directly; they inject a DataLake fixture.

### [OPEN] — Empty session_id race condition in save_fn
**Source:** Validation of subtask 7.3
**Problem:** `app.py` initializes `gr.State(value="")` and fires `demo.load()` to assign a UUID. If the operator submits the form before `demo.load()` completes, `session_id` is `""`.
**Impact:** Two simultaneous sessions with empty `session_id` overwrite each other's form data. Agent state also collides under `"welcome_agent_"`.
**Suggested action:** Guard at the top of `save_fn`: `if not session_id: return "Sesión no iniciada. Recarga la página e intenta de nuevo."` — included in Step 6 above.

---

## Deliverable Checklist

### `core/storage/schema.py`
- [ ] `agent_state (session_id TEXT PRIMARY KEY, data TEXT NOT NULL)` table added

### `core/storage/persistence.py`
- [ ] `"agent_state"` added to `_SQLITE_ENTITY_TYPES`
- [ ] `save()` handler: upsert JSON blob into `agent_state` by `session_id`
- [ ] `load()` handler: deserialize JSON blob from `agent_state` by `session_id`
- [ ] `delete()` handler: delete row from `agent_state` by `session_id`
- [ ] `list_ids()` handler: return all `session_id` values from `agent_state`

### `gradio_app/session.py`
- [ ] `get_data_lake()` returns `DataLake(db_path="data/zenet.db")`
- [ ] `os.makedirs("data", exist_ok=True)` called before `DataLake()`
- [ ] `import os` added
- [ ] `create_session()` returns `"primary_session"` (fixed key, not UUID4)
- [ ] Docstring updated to document fixed-key design and reset_session.py

### `reset_session.py`
- [ ] File exists at project root
- [ ] Deletes `data/zenet.db` if it exists; prints Spanish confirmation
- [ ] Prints "No hay sesión activa." if file not found
- [ ] Runnable with `uv run python reset_session.py`

### `gradio_app/sections/bienvenida.py`
- [ ] Two-column layout: form (left, `scale=1`) + chat (right, `scale=1`)
- [ ] `gr.Textbox` for user name (required)
- [ ] `gr.Textbox` for restaurant name (required)
- [ ] `gr.Dropdown` for restaurant type (optional, choices from `DEFAULT_RESTAURANT_TYPES`, `value=None`)
- [ ] `gr.Button("Guardar registro", variant="primary")` wired to save handler
- [ ] `gr.Markdown("")` for save status feedback output
- [ ] `if not session_id` guard in `save_fn` (returns Spanish error)
- [ ] Save validates user name (Spanish error if empty)
- [ ] Save validates restaurant name (Spanish error if empty)
- [ ] `entity_id = abs(hash(session_id)) % (2**31 - 1)` — integer, not string key
- [ ] `Restaurant` + `User` entities persisted to DataLake on save using `entity_id`
- [ ] `restaurant_type_id` mapped via `.get()` — handles `None` dropdown value
- [ ] `User.role = "admin"` hardcoded — no role selector in form
- [ ] `_INITIAL_GREETING` passed via `initial_messages` to `render_chat_panel()`
- [ ] `if not session_id` guard in `chat_fn` (returns friendly message)
- [ ] `_make_chat_fn` creates agent, calls `load_state` before `run()`
- [ ] `agent.save_state()` called after try/except (always runs)
- [ ] `_load_form_context()` uses integer `entity_id` — returns operator name and restaurant name when saved
- [ ] `try/except Exception` around `agent.run()` with friendly Spanish error reply
- [ ] `WelcomeAgent` imported from `core.agents.welcome_agent` (not `core`)

---

## Verification

```bash
# Smoke test — renders without error
PYTHONPATH=. uv run python -c "
import gradio as gr
from gradio_app.app import build_app
app = build_app()
print('App built OK')
"

# Full mocked test suite (after 7.6 is written)
uv run python -m pytest tests/unit/test_welcome_agent.py -k 'not live' -v

# Manual smoke test
PYTHONPATH=. uv run python -m gradio gradio_app/app.py
# 1. Open Bienvenida tab — verify Zeni's greeting appears immediately
# 2. Fill in name + restaurant, click Guardar — verify Spanish confirmation
# 3. Send a message — verify Zeni responds in Spanish
# 4. Send 2-3 messages — verify conversation history is maintained
# 5. Save form first, then chat — verify agent uses operator name in response
# 6. Use invalid API key — verify friendly Spanish error appears instead of crash
# 7. Verify data/zenet.db is created and contains restaurant + user rows
```
