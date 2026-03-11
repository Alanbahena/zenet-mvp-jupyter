# Subtask 7.6 — Tests (mocked + live)

## Context

**Parent task:** Task 7 — Bienvenida Section: Welcome Agent + Onboarding Form
**Source of truth:** `.taskmaster/docs/task-7/plan.md` §7.6

Creates `tests/unit/test_welcome_agent.py` with 18 mocked (offline) tests and 3 live
tests. Covers `WelcomeAgent` agent logic, `_make_save_fn` form validation and
persistence, `_load_form_context`, and `_make_chat_fn` error handling.

**Prior (7.5):** `WelcomeAgent` is exported from both `core.agents` and `core` —
both import paths resolve cleanly.

**Next (7.7):** Tests passing is the gate for marking Task 7 done in documentation.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `WelcomeAgent` unit tests (agent logic, memory, state) | Testing `render()` (requires Gradio context) |
| `_make_save_fn` tests (validation + persistence) | Button disable/enable UI behavior |
| `_load_form_context` tests | `reset_session.py` |
| `_make_chat_fn` error handling test | Any Task 8+ agents |
| 3 live tests guarded by `ANTHROPIC_API_KEY` | `get_data_lake()` (never called in tests) |

---

## Storage backend decision

**Tests use JSON, app uses SQLite. Never both at the same time.**

| Context | Backend | Reason |
|---------|---------|--------|
| Running app | `DataLake(db_path="data/zenet.db")` | Persistent, survives restarts |
| Unit tests | `DataLake(data_dir=tempfile.mkdtemp())` | Ephemeral, isolated per test |

`JsonStorage` has no `_SQLITE_ENTITY_TYPES` restriction — any entity_type string is
valid. Integer entity_ids are converted to strings for filenames transparently.
`DataLake.save_entity()` calls `self._storage.save()` directly with no routing logic.
No issues with `restaurant`, `user`, or `agent_state` entity types via JSON.

---

## Key design decisions

### Decision 1: `_MockProvider` defined locally

**Choice:** Copy the `_MockProvider` pattern from `tests/unit/test_agents.py:35`
into this file. Do not import it.

**Rationale:** Each test file is self-contained. Import coupling between test files
creates fragile dependencies.

---

### Decision 2: Default mock response is plain Spanish text

**Choice:** `_MockProvider(response="Hola, soy Zeni.")` — plain text, not JSON.

**Rationale:** `WelcomeAgent.RESPONSE_MODEL = None` — the agent returns plain prose.
The default `'{"result": "ok"}'` from `test_agents.py` would be returned verbatim as
the reply, which is misleading for WelcomeAgent tests.

---

### Decision 3: `save_fn` returns a 2-tuple

**Choice:** All `_make_save_fn` assertions check `result[0]` for the message string.

**Rationale:** `save_fn` returns `(str, gr.update())` — not just `str`. Added in
7.3 (button disable) and 7.4 (DB error handling). Parent plan §7.6 predates these
changes and shows bare string assertions — they would fail as written.

---

### Decision 4: `_FailingProvider` for error handling test

**Choice:** Define a `_FailingProvider` subclass of `_MockProvider` that raises
`RuntimeError` in `_do_generate`.

**Rationale:** `_make_chat_fn` catches `Exception` from `agent.run()`. Injecting a
failing provider is the cleanest way to trigger that path without mocking internals.

---

## Files to Create

| File | Action | Summary |
|------|--------|---------|
| `tests/unit/test_welcome_agent.py` | Create | 18 mocked + 3 live tests |

---

## `_MockProvider` (exact signature — must match `test_agents.py:43`)

```python
class _MockProvider(LlmProvider):
    def __init__(self, response: str = "Hola, soy Zeni.") -> None:
        super().__init__(model_name="mock")
        self.response = response
        self.last_call_kwargs: dict[str, Any] = {}

    def _do_generate(self, *, prompt, system, tools, structured_output, messages, max_tokens, temperature) -> str:
        self.last_call_kwargs = {
            "prompt": prompt,
            "system": system,
            "tools": tools,
            "structured_output": structured_output,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        return self.response


class _FailingProvider(_MockProvider):
    def _do_generate(self, **kwargs) -> str:
        raise RuntimeError("API down")
```

---

## Implementation Steps

### Step 1 — Imports and fixtures

```python
import os
import tempfile
import unittest
from typing import Any

from core.agents.utils import create_agent
from core.agents.welcome_agent import WelcomeAgent
from core.ai.providers import LlmProvider
from core.storage.persistence import DataLake
from gradio_app.sections.bienvenida import (
    _load_form_context,
    _make_chat_fn,
    _make_save_fn,
)
```

Helper fixture used across multiple tests:
```python
def _make_data_lake() -> DataLake:
    return DataLake(data_dir=tempfile.mkdtemp())
```

---

### Step 2 — WelcomeAgent tests (`TestWelcomeAgent`)

11 tests covering agent instantiation, run, context, memory, and state persistence.

| Test | What to assert |
|------|----------------|
| `test_agent_instantiates_via_factory` | `isinstance(agent, WelcomeAgent)` |
| `test_response_model_is_none` | `WelcomeAgent.RESPONSE_MODEL is None` |
| `test_input_schema_has_user_message` | `"user_message" in WelcomeAgent.INPUT_SCHEMA` |
| `test_run_returns_reply_and_raw_response` | `result["reply"] == "Hola, soy Zeni."` and `result["raw_response"] == "Hola, soy Zeni."` |
| `test_run_adds_messages_to_memory` | `agent.memory.message_count == 2` after one `run()` |
| `test_missing_user_message_raises` | `run(input_data={})` raises `ValueError` |
| `test_response_is_plain_text` | `result["reply"]` equals mock string verbatim |
| `test_context_with_operator_name` | `provider.last_call_kwargs["system"]` contains `"Juan"` |
| `test_context_empty_uses_base_prompt` | `run(context={})` does not raise |
| `test_multi_turn_accumulates_memory` | Two `run()` calls → `agent.memory.message_count == 4` |
| `test_save_load_state_round_trip` | After save+load, `agent2.memory.message_count == 2` in new agent instance |

---

### Step 3 — `_make_save_fn` tests (`TestSaveFn`)

5 tests. All use `_make_data_lake()` fixture.
**All assertions on `result[0]`** — save_fn returns `(str, gr.update())`.

| Test | Inputs | Assert `result[0]` |
|------|--------|-------------------|
| `test_save_fn_error_empty_session` | `session_id=""` | contains `"Sesión no iniciada"` |
| `test_save_fn_error_missing_user_name` | `user_name=""` | contains `"obligatorio"` |
| `test_save_fn_error_missing_restaurant_name` | `restaurant_name=""` | contains `"obligatorio"` |
| `test_save_fn_persists_entities` | valid inputs | contains `"Bienvenido"`; entities loadable from DataLake |
| `test_save_fn_none_restaurant_type` | `restaurant_type_label=None` | saved restaurant dict has `restaurant_type_id` is `None` |

For `test_save_fn_persists_entities`:
```python
dl = _make_data_lake()
save_fn = _make_save_fn(dl)
result = save_fn("Juan", "Tacos El Güero", "Casual", "test_session")
assert "Bienvenido" in result[0]
entity_id = abs(hash("test_session")) % (2**31 - 1)
restaurant = dl.load_entity("restaurant", entity_id)
user = dl.load_entity("user", entity_id)
assert restaurant["name"] == "Tacos El Güero"
assert user["name"] == "Juan"
assert user["role"] == "admin"
```

---

### Step 4 — `_load_form_context` tests (`TestLoadFormContext`)

2 tests.

| Test | Setup | Assert |
|------|-------|--------|
| `test_load_form_context_empty_session` | Empty DataLake | returns `{}` |
| `test_load_form_context_after_save` | Call `save_fn` first, then `_load_form_context` | returns `{"operator_name": "Juan", "restaurant_name": "Tacos El Güero"}` |

---

### Step 5 — `_make_chat_fn` error handling test (`TestChatFn`)

1 test.

```python
def test_chat_fn_error_handling(self):
    dl = _make_data_lake()
    chat_fn = _make_chat_fn(_FailingProvider(), dl)
    history, text = chat_fn("Hola", [], "test_session")
    assert text == ""
    assert any("problema" in m["content"] for m in history if m["role"] == "assistant")
```

---

### Step 6 — Live tests (`TestWelcomeAgentLive`)

Guarded by `@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "requires ANTHROPIC_API_KEY")`.

```python
@classmethod
def setUpClass(cls):
    from core.ai.providers import ClaudeProvider
    cls.provider = ClaudeProvider()
    cls.dl = _make_data_lake()
```

| Test | Assert |
|------|--------|
| `test_live_responds_in_spanish` | reply contains at least one Spanish word (e.g. "hola", "bienvenido", "restaurante", "zenet") — case-insensitive |
| `test_live_warm_tone` | reply does not contain JSON brackets `{` or `}` |
| `test_live_multi_turn_context` | second turn reply is non-empty and `agent.memory.message_count == 4` |

---

## Verification

```bash
# Mocked only (no API key needed)
PYTHONPATH=. uv run python -m pytest tests/unit/test_welcome_agent.py -k "not live" -v

# Live tests (requires ANTHROPIC_API_KEY in .env)
PYTHONPATH=. uv run python -m pytest tests/unit/test_welcome_agent.py -k "live" -v

# Full suite — must not regress
PYTHONPATH=. uv run python -m pytest tests/unit/ -v
```

---

## Deliverable Checklist

### `tests/unit/test_welcome_agent.py`
- [ ] `_MockProvider` defined locally — matches `test_agents.py:35` signature exactly
- [ ] `_FailingProvider` defined locally — raises `RuntimeError` in `_do_generate`
- [ ] `_make_data_lake()` helper uses `DataLake(data_dir=tempfile.mkdtemp())`
- [ ] 11 `TestWelcomeAgent` mocked tests
- [ ] 5 `TestSaveFn` tests — all check `result[0]` for message string
- [ ] 2 `TestLoadFormContext` tests
- [ ] 1 `TestChatFn` error handling test
- [ ] 3 `TestWelcomeAgentLive` tests guarded by `ANTHROPIC_API_KEY`
- [ ] All mocked tests pass: `uv run python -m pytest tests/unit/test_welcome_agent.py -k "not live"`
- [ ] Full suite passes: `uv run python -m pytest tests/unit/ -v`

---

## Risks and Open Questions

### [OPEN] — "Casual" may not match any DEFAULT_RESTAURANT_TYPES name
**Source:** Validation of subtask 7.6
**Problem:** `test_save_fn_persists_entities` calls `save_fn("Juan", "Tacos El Güero", "Casual", "test_session")`. If "Casual" is not in `DEFAULT_RESTAURANT_TYPES`, `restaurant_type_id` resolves silently to `None`. The test still passes (only asserts `name` and `role`), so the type mapping is never validated.
**Impact:** Test gives false confidence that the restaurant_type label→id lookup works correctly.
**Suggested action:** Before implementing, check `DEFAULT_RESTAURANT_TYPES` names in `core/domain/data_model.py` and use a real type name, or add `assert restaurant["restaurant_type_id"] is not None` to the test.

### Fix applied during validation
- `ConversationMemory` has no public `.messages` attribute. All plan references to `len(agent.memory.messages)` corrected to `agent.memory.message_count` (int property — no `len()` needed).
