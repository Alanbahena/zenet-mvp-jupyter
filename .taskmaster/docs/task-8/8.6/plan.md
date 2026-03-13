# Subtask 8.6 — Tests (`tests/unit/test_classification_agent.py`)

## Context

Creates the full test suite for the Clasificación section: `ClassificationAgent` unit
tests, `_format_draft` pure-function tests, `_make_confirm_fn` integration tests, a
`SqliteStorage` round-trip test for the `classification` entity, and live tests guarded
by `ANTHROPIC_API_KEY`.

**Prior:** 8.5 exported `ClassificationAgent` from `core/agents/__init__.py` and
`core/__init__.py`. All production code for Task 8 is complete.

**Next:** 8.7 creates the architecture doc and marks Task 8 done.

---

## Files to Create

| File | Action | Summary |
|------|--------|---------|
| `tests/unit/test_classification_agent.py` | Create | 16 mocked/offline tests + 3 live tests |

---

## Dependencies

- 8.1 done — `ClassificationAgent` at `core/agents/classification_agent.py`
- 8.2 done — `"classification"` in `_SQLITE_ENTITY_TYPES`; save/load handlers in `persistence.py`
- 8.3 done — `_format_draft`, `render_draft_preview` in `gradio_app/components.py`
- 8.4 done — `_make_confirm_fn`, `_load_classification_context` in `gradio_app/sections/clasificacion.py`
- 8.5 done — `ClassificationAgent` exported from `core.agents` and `core`
- `ANTHROPIC_API_KEY` in `.env` for live tests (skipped automatically if absent)

---

## Design Decisions

### Decision 1: `_MockProvider` returns valid JSON strings

`ClassificationAgent.RESPONSE_MODEL = _ClassificationResponse` — the base agent parses
the LLM response as JSON via `_parse_response()`. The mock provider must return a valid
JSON string, e.g. `'{"reply": "Hola.", "standardization_level": 2}'`. Returning plain
text would raise a parse error.

### Decision 2: Test `_format_draft` directly, not via Gradio events

`_format_draft` is a pure Python function. Tests call it directly and assert on the
`(str, dict)` return value. No Gradio component instantiation needed.

### Decision 3: `_make_confirm_fn` tests use SqliteStorage-backed DataLake

Confirm requires `data_lake.save_entity("classification", ...)`. Tests use
`DataLake(data_dir=tempfile.mkdtemp())` (same as `test_welcome_agent.py`). This also
covers the SQLite path because `SqliteStorage` is the default backend for a temp dir
DataLake that has no `json/` override.

### Decision 4: Storage round-trip test goes through `DataLake`, not `SqliteStorage` directly

`DataLake.save_entity` → `SqliteStorage.save` → SQLite; `DataLake.load_entity` → `SqliteStorage.load`.
Testing via `DataLake` is the canonical usage pattern and also exercises the full path.

### Decision 5: `test_run_accumulates_sections_across_turns` replaced

The parent plan listed this test but `sections` was removed from `ClassificationAgent`.
It is replaced by `test_run_does_not_overwrite_existing_level` — verifying that a second
turn with `standardization_level: null` in the JSON does not overwrite a level already
set in `_data_store`.

### Decision 6: Live tests use `setUpClass` with a shared `ClaudeProvider`

Same pattern as `TestWelcomeAgentLive`. One provider instance for all three live tests.

---

## Implementation Steps

### 1. Module-level helpers

```python
import json
import os
import tempfile
import unittest
from typing import Any

from core.agents.classification_agent import ClassificationAgent
from core.agents.utils import create_agent
from core.ai.providers import LlmProvider
from core.storage.persistence import DataLake
from gradio_app.components import _format_draft
from gradio_app.sections.clasificacion import _make_confirm_fn


def _make_data_lake() -> DataLake:
    return DataLake(data_dir=tempfile.mkdtemp())


def _json_response(reply: str = "Hola.", level: int | None = 2) -> str:
    payload: dict[str, Any] = {"reply": reply}
    if level is not None:
        payload["standardization_level"] = level
    return json.dumps(payload)
```

### 2. `_MockProvider`

```python
class _MockProvider(LlmProvider):
    def __init__(self, response: str | None = None) -> None:
        super().__init__(model_name="mock")
        self.response = response or _json_response()
        self.last_system: str = ""

    def _do_generate(self, *, prompt, system, tools, structured_output,
                     messages, max_tokens, temperature) -> str:
        self.last_system = system
        return self.response
```

### 3. `TestClassificationAgent` — 10 mocked tests

```python
class TestClassificationAgent(unittest.TestCase):

    def _make_agent(self, response: str | None = None):
        provider = _MockProvider(response=response)
        agent = create_agent(ClassificationAgent, provider=provider, name="classification_agent")
        return agent, provider

    def test_agent_instantiates_via_factory(self):
        agent, _ = self._make_agent()
        self.assertIsInstance(agent, ClassificationAgent)

    def test_response_model_is_set(self):
        self.assertIsNotNone(ClassificationAgent.RESPONSE_MODEL)

    def test_input_schema_has_user_message(self):
        self.assertIn("user_message", ClassificationAgent.INPUT_SCHEMA)

    def test_run_returns_reply(self):
        agent, _ = self._make_agent()
        result = agent.run(input_data={"user_message": "Hola"})
        self.assertTrue(result["reply"])

    def test_run_stores_level_in_data_store(self):
        agent, _ = self._make_agent(response=_json_response(level=2))
        agent.run(input_data={"user_message": "Operamos desde hace 5 años."})
        self.assertEqual(agent.retrieve("standardization_level"), 2)

    def test_run_does_not_overwrite_existing_level(self):
        # First turn sets level 2; second turn returns null level — must not overwrite
        agent, _ = self._make_agent(response=_json_response(level=2))
        agent.run(input_data={"user_message": "Primera vuelta."})
        agent.provider.response = _json_response(level=None)
        agent.run(input_data={"user_message": "Segunda vuelta."})
        self.assertEqual(agent.retrieve("standardization_level"), 2)

    def test_context_injects_restaurant_name(self):
        agent, provider = self._make_agent()
        agent.run(
            input_data={"user_message": "Hola"},
            context={"restaurant_name": "Tacos El Güero"},
        )
        self.assertIn("Tacos El Güero", provider.last_system)

    def test_draft_injected_in_prompt(self):
        agent, provider = self._make_agent(response=_json_response(level=1))
        agent.run(input_data={"user_message": "Primera vuelta."})
        agent.run(input_data={"user_message": "Segunda vuelta."})
        self.assertIn("standardization_level", provider.last_system)

    def test_missing_user_message_raises(self):
        agent, _ = self._make_agent()
        with self.assertRaises((ValueError, KeyError)):
            agent.run(input_data={})

    def test_save_load_state_preserves_draft(self):
        dl = _make_data_lake()
        agent, _ = self._make_agent(response=_json_response(level=3))
        agent.run(input_data={"user_message": "Hola"})
        agent.save_state(dl, session_id="classification_agent_test")

        agent2 = create_agent(ClassificationAgent, provider=_MockProvider(), name="classification_agent")
        agent2.load_state(dl, session_id="classification_agent_test")
        self.assertEqual(agent2.retrieve("standardization_level"), 3)
```

**Note on `test_run_does_not_overwrite_existing_level`:** Agent must be given a way to
swap the provider response between turns. `_MockProvider` stores response on `self.response`.
After `create_agent`, access via `agent.provider` — verify `BaseAgent` exposes `.provider`.
If not, use two agents with `save_state / load_state`.

### 4. `TestFormatDraft` — 3 tests

```python
class TestFormatDraft(unittest.TestCase):

    def test_empty_draft_shows_placeholder(self):
        text, btn = _format_draft({})
        self.assertIn("asistente", text.lower())
        self.assertFalse(btn["interactive"])

    def test_level_set_shows_label(self):
        text, btn = _format_draft({"standardization_level": 2})
        self.assertIn("Nivel 2", text)
        self.assertTrue(btn["interactive"])

    def test_unknown_level_does_not_raise(self):
        text, btn = _format_draft({"standardization_level": 99})
        self.assertIn("99", text)
        self.assertTrue(btn["interactive"])
```

### 5. `TestConfirmFn` — 2 tests

```python
class TestConfirmFn(unittest.TestCase):

    def test_confirm_fn_persists_classification(self):
        dl = _make_data_lake()
        confirm_fn = _make_confirm_fn(dl)
        session_id = "test_session"
        draft = {"standardization_level": 2}
        result = confirm_fn(draft, session_id)
        entity_id = abs(hash(session_id)) % (2**31 - 1)
        saved = dl.load_entity("classification", entity_id)
        self.assertEqual(saved["standardization_level"], 2)
        self.assertIn("2", result)

    def test_confirm_fn_empty_session_returns_error(self):
        dl = _make_data_lake()
        confirm_fn = _make_confirm_fn(dl)
        result = confirm_fn({"standardization_level": 1}, "")
        self.assertIn("Sesión", result)
        # No entity written
        entity_id = abs(hash("")) % (2**31 - 1)
        self.assertIsNone(dl.load_entity("classification", entity_id))
```

### 6. `TestClassificationStorage` — 1 round-trip test

```python
class TestClassificationStorage(unittest.TestCase):

    def test_classification_save_load_round_trip(self):
        dl = _make_data_lake()
        data = {"standardization_level": 3}
        dl.save_entity("classification", 1, data)
        loaded = dl.load_entity("classification", 1)
        self.assertEqual(loaded, data)
```

### 7. `TestClassificationAgentLive` — 3 live tests

```python
@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "requires ANTHROPIC_API_KEY")
class TestClassificationAgentLive(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from core.ai.providers import ClaudeProvider
        cls.provider = ClaudeProvider()

    def test_live_responds_in_spanish(self):
        agent = create_agent(ClassificationAgent, provider=self.provider, name="classification_agent")
        result = agent.run(input_data={"user_message": "Hola, ¿cómo funciona esta sección?"})
        reply = result["reply"].lower()
        spanish_words = ["nivel", "restaurante", "hola", "operación", "estandarización", "zenet"]
        self.assertTrue(any(w in reply for w in spanish_words))
        self.assertNotIn("{", result["reply"])

    def test_live_diagnoses_level(self):
        agent = create_agent(ClassificationAgent, provider=self.provider, name="classification_agent")
        agent.run(input_data={
            "user_message": (
                "Llevamos 2 años operando. Todo está en nuestra cabeza, "
                "no tenemos recetas escritas ni inventarios documentados."
            )
        })
        level = agent.retrieve("standardization_level")
        # Level may or may not be set on first turn — agent may ask follow-up
        if level is not None:
            self.assertIn(level, {1, 2, 3})

    def test_live_multi_turn_accumulates(self):
        agent = create_agent(ClassificationAgent, provider=self.provider, name="classification_agent")
        agent.run(input_data={"user_message": "Hola"})
        agent.run(input_data={
            "user_message": (
                "Tenemos un Excel con recetas pero no está completo. "
                "Trabajamos así desde hace 3 años."
            )
        })
        # After two turns, memory grows
        self.assertGreater(agent.memory.message_count, 2)
```

---

## Plan Completeness

| Category | Status |
|----------|--------|
| Unit tests | Yes — 16 mocked/offline tests |
| Live tests | Yes — 3 live tests guarded by `ANTHROPIC_API_KEY` |
| Error handling | Covered by `test_missing_user_message_raises`, `test_confirm_fn_empty_session_returns_error` |
| Re-exports | Not applicable — test file, no new exports |
| Status updates | Covered in 8.7 |
| Documentation | Not applicable |

---

## Out of Scope

- No changes to any production file
- No test for `_load_classification_context` (pure DataLake read, covered by `TestConfirmFn` setup pattern)
- No Gradio UI rendering tests (would require `gr.Blocks` context; deferred post-MVP)
- No test for `render_draft_preview` event wiring (Gradio component, not unit-testable without browser)

---

## Risks and Open Questions

None identified. `provider` is a public dataclass field on `BaseAgent` (line 62 of
`base_agent.py`) — `agent.provider.response` can be swapped directly between turns.

---

## Verification

```bash
# Mocked tests only
PYTHONPATH=. uv run python -m pytest tests/unit/test_classification_agent.py -k "not live" -v

# Live tests
PYTHONPATH=. uv run python -m pytest tests/unit/test_classification_agent.py -k "live" -v

# Full suite — must not regress
PYTHONPATH=. uv run python -m pytest tests/unit/ -v
```

---

## Deliverable Checklist

### `tests/unit/test_classification_agent.py`
- [ ] `_MockProvider` returns valid JSON strings (required by `RESPONSE_MODEL`)
- [ ] `_json_response(reply, level)` helper builds mock JSON strings
- [ ] `TestClassificationAgent` — 10 mocked tests pass without API key
- [ ] `TestFormatDraft` — 3 tests for `_format_draft` pure function
- [ ] `TestConfirmFn` — 2 tests: persists to DataLake, empty session error
- [ ] `TestClassificationStorage` — 1 round-trip test via DataLake
- [ ] `TestClassificationAgentLive` — 3 live tests guarded by `ANTHROPIC_API_KEY`
- [ ] Full suite passes: `uv run python -m pytest tests/unit/ -v`
