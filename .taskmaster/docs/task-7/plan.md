# Task 7 — Bienvenida Section: Welcome Agent + Onboarding Form

## Context

Task 7 is the first user-facing section of Zenet MVP 0.1. The target audience is Mexican
restaurant operators who are unfamiliar with operational software. The Bienvenida tab must
accomplish two things: (1) capture basic user and restaurant information through a form, and
(2) provide a warm, supportive chat companion ("Zeni") that reduces anxiety and answers
questions about Zenet and the onboarding process. The chat agent is NOT a data extractor —
it's a companion. The form handles data capture.

**Prior tasks (5, 6):** Delivered `BaseAgent`, `create_agent()`, `AgentRegistry`,
`ConversationMemory`, `DataLake`, the Gradio shell (`build_app()`), `render_chat_panel()`,
section stubs, and the LangGraph integration pattern. All are inputs to Task 7.

**Next task (8 — Clasificacion):** Will need the saved `Restaurant` and `User` entities
from this section's form to proceed with classification. Task 7 establishes the
section-agent wiring pattern that Tasks 8–12 will follow.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `WelcomeAgent` companion agent (plain-text, Spanish) | LangGraph graph (single agent, no graph needed) |
| Onboarding form (user name, restaurant name, type dropdown) | Real email collection |
| Auto-greeting from Zeni on tab load | Notebook integration (separate task) |
| Chat error handling (graceful Spanish error messages) | `RestaurantInfoAgent` modifications |
| Form validation (required fields) | Other section stubs (Tasks 8–12) |
| `render_chat_panel()` `initial_messages` support | Internationalization beyond Spanish |
| `core/__init__.py` re-exports for `WelcomeAgent` | Agent tool calling |
| Mocked + live tests | Session persistence across app restarts |
| `.taskmaster/docs/task-7/plan.md` documentation | Architecture doc updates |

---

## Architectural Decisions

### Decision 1: `RESPONSE_MODEL = None` — plain prose, not JSON

**Choice:** `WelcomeAgent` sets `RESPONSE_MODEL = None`. The agent returns natural language
text, not structured JSON.

**Rationale:** The agent is a companion, not a data extractor. Setting `RESPONSE_MODEL = None`
causes `BaseAgent._generate_response()` to pass `structured_output=False` to the provider
automatically (line 313 of `base_agent.py`), so no JSON-forcing instruction is appended.

---

### Decision 2: Form handles data capture; agent handles emotions

**Choice:** The form's save button creates and persists `Restaurant` + `User` entities.
The chat agent never writes to DataLake directly.

**Rationale:** Separation of concerns. The form is reliable, validated, and deterministic.
The agent is conversational and non-deterministic. Mixing data capture with chat would
complicate validation and error recovery.

---

### Decision 3: Agent re-created per chat turn with `load_state`/`save_state`

**Choice:** Each chat turn creates a fresh `WelcomeAgent` via `create_agent()`, loads state
from DataLake, runs, then saves state back.

**Rationale:** Avoids storing mutable agent objects in `gr.State` (which requires
serialization). Matches the `BaseAgent` lifecycle pattern established in Task 5. State is
persisted via DataLake using composite key `f"welcome_agent_{session_id}"`.

---

### Decision 4: Static auto-greeting (no LLM call)

**Choice:** Zeni's initial greeting is a static string injected as `gr.Chatbot(value=[...])`.
No LLM call on tab load.

**Rationale:** Faster, no API cost, always consistent. Requires a minor backwards-compatible
change to `render_chat_panel()` — adding an optional `initial_messages` parameter
(default `None`).

---

### Decision 5: Placeholder email for `User`

**Choice:** `User.email` is set to `f"{session_id}@zenet.local"` since the form doesn't
collect email.

**Rationale:** `User` dataclass requires `email: str` (non-optional). Adding an email field
to the form is unnecessary for MVP onboarding. The placeholder satisfies the contract without
adding UX complexity.

---

### Decision 6: Session-scoped entity keys

**Choice:** Entities are saved under `f"{session_id}_restaurant"` and `f"{session_id}_user"`
as `entity_id`.

**Rationale:** Prevents collisions across sessions in `JsonStorage`. Consistent with how
`agent.save_state()` uses `session_id` as the key.

---

### Decision 7: Chat error handling wraps `agent.run()` in try/except

**Choice:** `chat_fn` catches exceptions from `agent.run()` and returns a user-friendly
Spanish error message instead of crashing the Gradio UI.

**Rationale:** API failures (rate limits, timeouts, auth errors) should not crash the UI.
The operator sees a friendly message and can retry.

---

## Files to Create/Modify

| File | Action | Summary |
|------|--------|---------|
| `core/agents/welcome_agent.py` | Create | `WelcomeAgent(BaseAgent)` — conversational companion |
| `gradio_app/components.py` | Modify | Add optional `initial_messages` param to `render_chat_panel()` |
| `gradio_app/sections/bienvenida.py` | Replace stub | Two-column layout: form + chat with error handling |
| `core/__init__.py` | Modify | Add `WelcomeAgent` to re-exports |
| `tests/unit/test_welcome_agent.py` | Create | Mocked + live tests |
| `.taskmaster/docs/task-7/plan.md` | Create | This file |
| `.taskmaster/tasks/tasks.json` | Modify | Update task 7 status to `done` |
| `CLAUDE.md` | Modify | Update task status table |

---

## Subtask Breakdown

### 7.1 — WelcomeAgent (`core/agents/welcome_agent.py`)

Create the `WelcomeAgent` class following the `RestaurantInfoAgent` pattern exactly.

- `@dataclass` class extending `BaseAgent` (not `__init__`)
- `INPUT_SCHEMA`: `{"user_message": "A message from the restaurant operator."}`
- `OUTPUT_SCHEMA`: `{"reply": "The agent's conversational response.", "raw_response": "Full LLM response string."}`
- `RESPONSE_MODEL = None`
- Module-level `_SYSTEM_PROMPT` constant in Spanish:
  - Introduces herself as "Zeni", Zenet's welcome assistant
  - Warm, professional tone — always speaks Spanish
  - Explains Zenet's 6-section pipeline when asked
  - Validates operator feelings if they express anxiety or uncertainty
  - Does NOT extract data — the form handles that
  - Concise responses (2-4 sentences)
- `_generate_prompt(input_data, context) -> tuple[str, str]`:
  - Returns `(_SYSTEM_PROMPT, input_data["user_message"])`
  - If `context.get("operator_name")` is truthy, append personalization line to system prompt
- `_process_response(response) -> dict`:
  - Returns `{"reply": response, "raw_response": response}`
  - No `_parse_response()` call needed (plain text, not JSON)

---

### 7.2 — Chat panel update (`gradio_app/components.py`)

Add `initial_messages` support to `render_chat_panel()`:

```python
def render_chat_panel(
    chat_fn: Callable,
    session_id: gr.State,
    data_lake_ref: object,
    initial_messages: list[dict[str, str]] | None = None,  # NEW
) -> None:
```

- Pass `value=initial_messages` to `gr.Chatbot(label="Asistente Zenet", value=initial_messages)`
- Default `None` preserves current behavior for all other sections (backwards-compatible)
- No other changes to the function

---

### 7.3 — Bienvenida section UI (`gradio_app/sections/bienvenida.py`)

Replace the stub with the full `render()` function.

**Layout:**

```
gr.Row
├── gr.Column (scale=1) — Form
│   ├── gr.Markdown("## Registro inicial")
│   ├── gr.Textbox("Tu nombre")
│   ├── gr.Textbox("Nombre del restaurante")
│   ├── gr.Dropdown("Tipo de restaurante", optional, 5 choices)
│   ├── gr.Button("Guardar registro", variant="primary")
│   └── gr.Markdown("") — save status feedback
│
└── gr.Column (scale=1) — Chat
    ├── gr.Markdown("## Asistente de bienvenida")
    └── render_chat_panel(chat_fn, session_id, data_lake, initial_messages=[greeting])
```

**Module-level constants:**
- `_RESTAURANT_TYPE_OPTIONS = [t.name for t in DEFAULT_RESTAURANT_TYPES]`
- `_RESTAURANT_TYPE_NAME_TO_ID = {t.name: t.id for t in DEFAULT_RESTAURANT_TYPES}`
- `_INITIAL_GREETING` — Zeni's static welcome message in Spanish (no LLM call)

**`_make_save_fn(data_lake)` — returns closure `save_fn(user_name, restaurant_name, restaurant_type_label, session_id) -> str`:**
1. Strip and validate: user name required, restaurant name required
2. Map dropdown label → `restaurant_type_id` via `_RESTAURANT_TYPE_NAME_TO_ID`
3. Create `Restaurant(id=1, name=..., restaurant_type_id=...)` and `User(id=1, name=..., email=f"{session_id}@zenet.local", role="admin")`
4. `data_lake.save_entity("restaurant", f"{session_id}_restaurant", restaurant_to_dict(restaurant))`
5. `data_lake.save_entity("user", f"{session_id}_user", user_to_dict(user))`
6. Return Spanish confirmation string

**`_make_chat_fn(provider, data_lake)` — returns closure `chat_fn(message, history, session_id) -> tuple[list, str]`:**
1. Guard: `if not message.strip(): return (history, "")`
2. `agent = create_agent(WelcomeAgent, provider=provider, name="welcome_agent")`
3. `agent.load_state(data_lake, session_id=f"welcome_agent_{session_id}")`
4. `context = _load_form_context(data_lake, session_id)`
5. `try: result = agent.run(input_data={"user_message": message}, context=context)`
6. `except Exception: reply = "Hubo un problema al conectar con el asistente. Por favor, intenta de nuevo."`
7. `agent.save_state(data_lake, session_id=f"welcome_agent_{session_id}")`
8. Append user + assistant turns to history, return `(history, "")`

**`_load_form_context(data_lake, session_id) -> dict`:**
- Load restaurant and user entities from DataLake
- Return `{"operator_name": user_data["name"], "restaurant_name": restaurant_data["name"]}` or `{}`

---

### 7.4 — Error handling and validation

**Chat error handling** (integrated in `_make_chat_fn` above):
- `try/except Exception` around `agent.run()`
- On failure, assistant reply = `"Hubo un problema al conectar con el asistente. Por favor, intenta de nuevo."`
- `agent.save_state()` still called after error so partial state is not lost

**Form validation** (integrated in `_make_save_fn` above):
- User name: `.strip()` then check truthiness — return `"El nombre del operador es obligatorio."` if empty
- Restaurant name: same pattern — return `"El nombre del restaurante es obligatorio."` if empty
- Restaurant type: `None` is valid — no validation needed

---

### 7.5 — Exports and task status

**`core/__init__.py`:**
- Add `WelcomeAgent` to re-exports alongside existing agent exports

**`.taskmaster/tasks/tasks.json`:**
- Update task 7 `status` field from `"pending"` to `"done"` after all subtasks complete

**`CLAUDE.md`:**
- Task status table: Task 7 row `pending` → `**done**`
- Active task note: update to point to Task 8

---

### 7.6 — Tests (mocked + live)

**File:** `tests/unit/test_welcome_agent.py`

Use `_MockProvider` pattern from `tests/unit/test_agents.py:35`. All mocked tests offline.

**`_MockProvider` signature** (must match existing exactly):
```python
def _do_generate(self, *, prompt, system, tools, structured_output, messages, max_tokens, temperature) -> str:
```

**Mocked tests:**

| Test | Validates |
|------|-----------|
| `test_agent_instantiates_via_factory` | `create_agent(WelcomeAgent, ...)` returns `WelcomeAgent` instance |
| `test_response_model_is_none` | `WelcomeAgent.RESPONSE_MODEL is None` |
| `test_input_schema_has_user_message` | `"user_message"` in `INPUT_SCHEMA` |
| `test_run_returns_reply_and_raw_response` | Output dict has `reply` and `raw_response` matching mock text |
| `test_run_adds_messages_to_memory` | After `run()`, memory has 2 messages (user + assistant) |
| `test_missing_user_message_raises` | `run(input_data={})` raises `ValueError` without calling provider |
| `test_response_is_plain_text` | `result["reply"]` equals mock text verbatim (no JSON parsing) |
| `test_context_with_operator_name` | System prompt passed to provider contains operator name |
| `test_context_empty_uses_base_prompt` | `context={}` uses base `_SYSTEM_PROMPT` without error |
| `test_multi_turn_accumulates_memory` | Two `run()` calls produce 4 messages in memory |
| `test_save_load_state_round_trip` | `save_state`/`load_state` preserves memory (uses `tempfile`) |
| `test_save_fn_error_missing_user_name` | Empty user name returns Spanish validation error string |
| `test_save_fn_error_missing_restaurant_name` | Empty restaurant name returns Spanish validation error string |
| `test_save_fn_persists_entities` | Valid inputs write restaurant + user to DataLake |
| `test_save_fn_none_restaurant_type` | `None` type → `restaurant_type_id=None` in saved dict |
| `test_load_form_context_empty_session` | Returns `{}` for unsaved session |
| `test_load_form_context_after_save` | Returns `{"operator_name": ..., "restaurant_name": ...}` |
| `test_chat_fn_error_handling` | `agent.run()` exception → friendly Spanish error in history |

**Live tests** (skipped without `ANTHROPIC_API_KEY`):

```python
@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "requires ANTHROPIC_API_KEY")
```

| Test | Validates |
|------|-----------|
| `test_live_responds_in_spanish` | Response contains Spanish characters/words |
| `test_live_warm_tone` | Response is conversational, not extractive |
| `test_live_multi_turn_context` | Second turn references first turn's content |

---

### 7.7 — Documentation

Create `.taskmaster/docs/task-7/plan.md` (this file). No subtask-level plan files.

---

## Dependencies

- Tasks 5–6 marked done
- `gradio`, `anthropic`, `pydantic` already installed via `uv sync`
- `ANTHROPIC_API_KEY` in `.env` — required only for live tests and manual smoke testing
- `core/agents/base_agent.py` — `BaseAgent.run()`, `save_state()`, `load_state()`
- `core/agents/utils.py` — `create_agent()` factory
- `gradio_app/components.py` — `render_chat_panel()` (modified in 7.2 before 7.3)
- `gradio_app/app.py` — already wires `bienvenida.render(session_id, data_lake)`
- `core/domain/data_model.py` — `Restaurant`, `User`, `DEFAULT_RESTAURANT_TYPES`
- `core/domain/serialization.py` — `restaurant_to_dict()`, `user_to_dict()`

**Subtask execution order:** 7.1 → 7.2 → 7.3 (depends on 7.1 and 7.2) → 7.4 (integrated in 7.3) → 7.5 → 7.6 → 7.7

---

## Risks and Open Questions

### [OPEN] — WelcomeAgent import path in bienvenida.py not specified
**Source:** Validation of Task 7
**Problem:** Subtask 7.3 uses `WelcomeAgent` in `bienvenida.py` but the plan does not specify whether to import from `core.agents.welcome_agent` (direct) or `core` (re-export added in 7.5). If 7.3 runs before 7.5, `from core import WelcomeAgent` will raise `ImportError`.
**Impact:** Runtime `ImportError` if implementer uses the re-export path before 7.5 is complete.
**Suggested action:** `bienvenida.py` should import `from core.agents.welcome_agent import WelcomeAgent` directly (independent of 7.5 execution order).

### [OPEN] — gr.Chatbot message format not specified in render_chat_panel update
**Source:** Validation of Task 7
**Problem:** The plan uses dict-format chat history `{"role": ..., "content": ...}` but subtask 7.2 does not add `type="messages"` to `gr.Chatbot(...)` in `components.py`. Older Gradio defaults to tuple format.
**Impact:** Chat history may not render if installed Gradio version expects tuple format by default.
**Suggested action:** Add `type="messages"` to `gr.Chatbot(label="Asistente Zenet", type="messages", value=initial_messages)` in subtask 7.2, or verify the installed Gradio version uses dict format by default.

1. **`User.email` non-optional.** `email: str` at line 393 of `data_model.py` is required.
   Placeholder `{session_id}@zenet.local` satisfies the contract. If Task 8+ requires a real
   email, the form must be updated.

2. **Entity key format.** `f"{session_id}_restaurant"` as `entity_id` works with
   `DataLake.save_entity`/`load_entity` (accepts `str | int`). No conflict with
   `save_entity_obj` which uses integer `entity.id`. Verified.

3. **Agent re-creation overhead.** Re-creating `WelcomeAgent` on every chat turn and
   restoring from state is slightly more expensive than caching in `gr.State`, but avoids
   serialization complexity. Acceptable for chat turn frequency in MVP.

4. **`render_chat_panel` signature change.** Adding `initial_messages` changes the public
   API. Only the `bienvenida.py` stub calls it today. Default `None` is backwards-compatible.
   Verified: other section stubs render placeholder markdown and do not call `render_chat_panel`.

5. **`_MockProvider._do_generate` signature.** Has 7 keyword args (`prompt`, `system`,
   `tools`, `structured_output`, `messages`, `max_tokens`, `temperature`). Tests must
   replicate this exactly. Verified against `tests/unit/test_agents.py:43`.

### [OPEN] — Textbox Enter-key submit not wired
**Source:** Validation of subtask 7.2
**Problem:** `render_chat_panel()` in `components.py` only wires `send_btn.click()`. `textbox.submit()` is not wired, so pressing Enter in the textbox does not trigger `chat_fn`. Pre-existing — not introduced by 7.2.
**Impact:** Operators must click "Enviar" to submit every message. Common UX expectation (Enter to submit) is unmet across all 6 sections that use `render_chat_panel()`.
**Suggested action:** Add `textbox.submit()` wiring (same fn/inputs/outputs as `send_btn.click()`) to subtask 7.3's scope, or open a dedicated subtask before 7.3 is implemented.

---

## Deliverable Checklist

### `core/agents/welcome_agent.py`
- [ ] `WelcomeAgent` dataclass extending `BaseAgent`
- [ ] `INPUT_SCHEMA` with `user_message` key
- [ ] `OUTPUT_SCHEMA` with `reply` and `raw_response` keys
- [ ] `RESPONSE_MODEL = None`
- [ ] `_SYSTEM_PROMPT` constant in Spanish (warm, companion tone, 6-section pipeline reference)
- [ ] `_generate_prompt()` returns `(system_prompt, user_message)` with optional operator name personalization
- [ ] `_process_response()` returns `{"reply": response, "raw_response": response}`

### `gradio_app/components.py`
- [ ] `initial_messages: list[dict[str, str]] | None = None` parameter added to `render_chat_panel()`
- [ ] `gr.Chatbot(value=initial_messages)` — passes initial messages when provided
- [ ] Default `None` — all other sections unaffected

### `gradio_app/sections/bienvenida.py`
- [ ] Two-column layout: form (left, `scale=1`) + chat (right, `scale=1`)
- [ ] `gr.Textbox` for user name (required)
- [ ] `gr.Textbox` for restaurant name (required)
- [ ] `gr.Dropdown` for restaurant type (optional, 5 choices from `DEFAULT_RESTAURANT_TYPES`)
- [ ] `gr.Button("Guardar registro", variant="primary")` wired to save handler
- [ ] `gr.Markdown("")` for save status feedback output
- [ ] Save validates user name and restaurant name (Spanish error messages)
- [ ] `Restaurant` + `User` entities persisted to DataLake on save
- [ ] `_INITIAL_GREETING` static message passed via `initial_messages` to `render_chat_panel()`
- [ ] `chat_fn` creates agent, calls `load_state` before and `save_state` after `run()`
- [ ] `_load_form_context()` injects saved form data as agent context
- [ ] `try/except Exception` around `agent.run()` with friendly Spanish error reply

### `core/__init__.py`
- [ ] `WelcomeAgent` added to re-exports

### `tests/unit/test_welcome_agent.py`
- [ ] `_MockProvider` defined locally (matches `tests/unit/test_agents.py:35` pattern)
- [ ] 18 mocked test cases covering: instantiation, run, context, persistence, save fn, error handling
- [ ] 3 live test cases guarded by `@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), ...)`
- [ ] All mocked tests pass: `uv run python -m pytest tests/unit/test_welcome_agent.py -k "not live"`
- [ ] Full suite still passes: `uv run python -m pytest tests/unit/ -v`

### `.taskmaster/docs/task-7/`
- [ ] `plan.md` created (this file)

### `.taskmaster/tasks/tasks.json`
- [ ] Task 7 `status` updated to `"done"`

### `CLAUDE.md`
- [ ] Task 7 row updated to `**done**` in task status table
- [ ] Active task note updated to Task 8

---

## Verification

1. **Mocked tests**: `uv run python -m pytest tests/unit/test_welcome_agent.py -k "not live"`
2. **Live tests**: `ANTHROPIC_API_KEY=... uv run python -m pytest tests/unit/test_welcome_agent.py -k "live"`
3. **Full suite**: `uv run python -m pytest tests/unit/ -v`
4. **Manual smoke test**: `python -c "from gradio_app.app import build_app; build_app().launch()"` — verify Bienvenida tab renders form + chat side by side with Zeni's auto-greeting visible
5. **Form save**: fill in name + restaurant, click save — verify Spanish confirmation message and data written to `data/sessions/`
6. **Chat**: send a message — verify Zeni responds in Spanish with warm tone
7. **Multi-turn**: send 2-3 messages — verify conversation history is maintained
8. **Form context in chat**: save form first, then chat — verify agent uses operator name in response
9. **Error handling**: use invalid API key — verify friendly Spanish error appears in chat instead of crash
