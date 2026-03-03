# Implementation Plan: Subtask 5.4 — Concrete Minimal Agent

## Goal

Build `RestaurantInfoAgent` — the first concrete agent in the system — to validate the entire
BaseAgent stack (5.1 + 5.2 + 5.3) against a realistic use case before Task 7 begins.

The agent captures restaurant name and type from a conversational message, using the same
extraction pattern the full Welcome Agent (Task 7) will need. A generic `TestAgent` that
returns `{"result": "ok"}` only proves the framework compiles; a realistic one proves it works
for the actual problem it will solve.

5.1 gave agents a lifecycle and memory.
5.2 gave agents a tool calling loop.
5.3 gave agents a data store and persistence.
5.4 proves all three layers work together in a concrete, end-to-end scenario.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `RestaurantInfoAgent` class in `simple_agent.py` | Changes to `base_agent.py` |
| `_RestaurantInfoResponse` Pydantic model (module-private) | Changes to `ToolRegistry` or `ConversationMemory` |
| Export from `core/agents/__init__.py` | Export from `core/__init__.py` (deferred to 5.7) |
| 6 mocked unit tests in `TestRestaurantInfoAgent` | `AgentRegistry`, `create_agent()` factory (5.5) |
| 2 live tests in `TestLiveRestaurantInfoAgent` | Retry logic (5.5) |
| Import additions to `test_agents.py` | Full Welcome Agent (Task 7) |

---

## Dependencies

All dependencies exist. Nothing new to install.

| Component | Source | Used for |
|-----------|--------|----------|
| `BaseAgent` | `core/agents/base_agent.py` | Subclassed directly |
| `parse_structured_output` | `core/ai/utils.py` | Not used directly — `_parse_response()` calls it |
| `BaseModel` | `pydantic` | `_RestaurantInfoResponse` model |
| `ClaudeProvider` | `core/ai/providers.py` | Live tests only |
| `ConversationMemory` | `core/ai/memory.py` | Used internally by agent (default-constructed; never injected in tests) |

No `uv add` required. Pydantic is already a project dependency (used in `base_agent.py`).

---

## Files to Modify

| Action | File |
|--------|------|
| Create | `core/agents/simple_agent.py` — `RestaurantInfoAgent` class |
| Modify | `core/agents/__init__.py` — add `RestaurantInfoAgent` export |
| Modify | `tests/unit/test_agents.py` — add `TestRestaurantInfoAgent` and `TestLiveRestaurantInfoAgent` |

No changes to `core/__init__.py` — that export is part of subtask 5.7.
No changes to `base_agent.py`.

---

## What is NOT changing

- `base_agent.py` — untouched
- All 36 existing tests (11 from 5.1, 8 from 5.2, 7 from 5.3, 10 from other modules) continue to pass
- `core/__init__.py` — `RestaurantInfoAgent` is NOT exported here yet (5.7 does this)

---

## Design Decisions

### 1. Use `RESPONSE_MODEL` (Pydantic), not manual `parse_structured_output()`

`BaseAgent` has built-in `RESPONSE_MODEL` support: when set, `_generate_response()` enables
structured output mode on the provider, and `_parse_response()` validates the JSON against
the Pydantic model with a graceful fallback to raw dict on validation failure, and to `{}`
on JSON parse failure. This means:

- **No manual try/except** needed in `_process_response()`
- **Malformed responses are handled automatically** — `_parse_response()` returns `{}`, so
  `data.get("restaurant_name")` returns `None`. The agent never crashes.
- **The `RESPONSE_MODEL` path is exercised** in real conditions, not just in the
  `_TypedAgent` fixture used in structured output tests.

The alternative (calling `parse_structured_output()` directly) would duplicate the fallback
logic already implemented in `_parse_response()` and bypass the structured output provider flag.

### 2. System prompt is written inline — do NOT use `format_system_prompt()`

`format_system_prompt(role, context)` produces `"You are a {role} {context}."` — a one-line
sentence with no room for JSON format instructions. The `RestaurantInfoAgent` system prompt
needs multi-line structure: role, task description, and exact JSON schema. Writing it inline
as a plain string constant `_SYSTEM_PROMPT` at module level keeps it readable and avoids
misusing a utility that was designed for simpler prompts.

### 3. `_RestaurantInfoResponse` is module-private (underscore prefix)

The Pydantic model is an implementation detail of this agent, not a public contract.
Underscore prefix signals this clearly and keeps `__all__` clean.

### 4. Call `self.store()` inside `_process_response()`

Per the 5.3 usage pattern, extracted business data should be written to the data store
immediately after extraction so the workflow engine (Task 6) can read it later without
parsing the conversation transcript. Both `restaurant_name` and `restaurant_type` are stored.

### 5. Export from `core/agents/__init__.py` only

`core/__init__.py` exports all public symbols for the whole package. Adding `RestaurantInfoAgent`
there is part of the 5.7 deliverable checklist (which also adds `AgentRegistry` and
`create_agent`). Exporting from `core/agents/__init__.py` now is sufficient for 5.4 and
avoids a partial state in `core/__init__.py`.

### 6. Live tests use `ANTHROPIC_API_KEY` with `ClaudeProvider`

Per CLAUDE.md, the default model is `claude-sonnet-4-6`. Live tests are skipped if the
key is absent (`@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), ...)`). This matches
the live test pattern established in Task 4.

### 7. `_SYSTEM_PROMPT` does NOT include JSON format instructions

`BaseAgent._generate_prompt()` docstring states explicitly:

> "When RESPONSE_MODEL is defined, _generate_response() automatically enables structured
> output mode. The system prompt does not need to manually instruct the LLM to return JSON
> — that is handled at the provider level."

`RestaurantInfoAgent` sets `RESPONSE_MODEL = _RestaurantInfoResponse`, so the provider
already enforces JSON output via structured output mode. Adding JSON format instructions
to the system prompt would contradict the BaseAgent contract and set a wrong precedent for
Tasks 7–12. The system prompt describes the agent's role and extraction task only.

This is the correct pattern for all future agents: if you set `RESPONSE_MODEL`, trust the
provider to handle the format; do not duplicate format instructions in the system prompt.

---

## Implementation Steps

### Step 1: Create `core/agents/simple_agent.py`

```python
"""
RestaurantInfoAgent -- concrete minimal agent for framework validation.

Extracts restaurant name and type from a conversational message.
Models the core extraction pattern of the full Welcome Agent (Task 7).
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent


_SYSTEM_PROMPT = (
    "You are a restaurant data assistant. "
    "When the operator describes their restaurant, extract two pieces of information: "
    "the restaurant name (if mentioned) and the restaurant type "
    "(e.g. fast-casual, full-service, cafeteria, food truck)."
)


class _RestaurantInfoResponse(BaseModel):
    restaurant_name: str | None = None
    restaurant_type: str | None = None


class RestaurantInfoAgent(BaseAgent):
    """
    Minimal agent that extracts restaurant name and type from a conversation.

    Models the core interaction pattern of the full Welcome Agent (Task 7):
        - System prompt establishes role and extraction task
        - User provides information conversationally
        - Agent extracts structured data and stores it via self.store()

    This agent is for framework validation only. The full Welcome Agent (Task 7)
    extends this pattern with onboarding flow and notebook integration.

    Input:
        user_message: A message from the restaurant operator.

    Output:
        restaurant_name: Extracted name, or None if not mentioned.
        restaurant_type: Extracted type, or None if not mentioned.
        raw_response:    Full LLM response string before parsing.
    """

    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "A message from the restaurant operator describing their restaurant.",
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "restaurant_name": "Extracted restaurant name, or None if not mentioned.",
        "restaurant_type": "Extracted restaurant type, or None if not mentioned.",
        "raw_response":    "Full LLM response string before parsing.",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = _RestaurantInfoResponse

    def _generate_prompt(
        self,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[str, str]:
        return _SYSTEM_PROMPT, input_data["user_message"]

    def _process_response(self, response: str) -> dict[str, Any]:
        data = self._parse_response(response)
        self.store("restaurant_name", data.get("restaurant_name"))
        self.store("restaurant_type", data.get("restaurant_type"))
        return {
            "restaurant_name": data.get("restaurant_name"),
            "restaurant_type": data.get("restaurant_type"),
            "raw_response": response,
        }
```

**No `@dataclass` decorator on `RestaurantInfoAgent`:** Concrete subclasses that add no new
instance fields do not need `@dataclass`. Python inherits `__init__` from the `@dataclass`
parent automatically. All existing concrete agents in the test suite (`_ConcreteAgent`,
`_TypedAgent`, `_ToolAgent`) follow this same pattern — none carry `@dataclass`.

---

### Step 2: Update `core/agents/__init__.py`

```python
from core.agents.base_agent import BaseAgent
from core.agents.simple_agent import RestaurantInfoAgent

__all__ = ["BaseAgent", "RestaurantInfoAgent"]
```

---

### Step 3: Add imports to `test_agents.py`

Add to the existing import block at the top of the file:

```python
import os

from core.agents.simple_agent import RestaurantInfoAgent
from core.ai.providers import ClaudeProvider
```

`os` is needed for `os.getenv("ANTHROPIC_API_KEY")` in the live test skip decorator.

---

### Step 4: Add `TestRestaurantInfoAgent` (6 mocked tests)

Add as a new class after `TestBaseAgentStateManagement`, before the `if __name__ == "__main__"` block.

The class reuses `_MockProvider` from the existing fixtures.

```python
class TestRestaurantInfoAgent(unittest.TestCase):
    """6 mocked tests for RestaurantInfoAgent end-to-end behaviour."""

    def setUp(self) -> None:
        self.valid_response = '{"restaurant_name": "La Palapa", "restaurant_type": "casual"}'
        self.provider = _MockProvider(response=self.valid_response)
        self.agent = RestaurantInfoAgent(name="test-restaurant-agent", provider=self.provider)
```

**Test 1 — `run()` returns correct output structure:**
```python
result = self.agent.run(input_data={"user_message": "My restaurant is La Palapa, casual dining."})

self.assertIn("restaurant_name", result)
self.assertIn("restaurant_type", result)
self.assertIn("raw_response", result)
self.assertEqual(result["restaurant_name"], "La Palapa")
self.assertEqual(result["restaurant_type"], "casual")
self.assertEqual(result["raw_response"], self.valid_response)
```

**Test 2 — `run()` populates memory with user message and assistant response:**
```python
self.agent.run(input_data={"user_message": "My restaurant is La Palapa."})

messages = self.agent.memory.get_messages()
self.assertEqual(len(messages), 2)
self.assertEqual(messages[0]["role"], "user")
self.assertEqual(messages[0]["content"], "My restaurant is La Palapa.")
self.assertEqual(messages[1]["role"], "assistant")
self.assertEqual(messages[1]["content"], self.valid_response)
```

**Test 3 — Missing `user_message` raises `ValueError` before any API call:**
```python
with self.assertRaises(ValueError) as ctx:
    self.agent.run(input_data={})

self.assertIn("user_message", str(ctx.exception))
self.assertEqual(self.provider.last_call_kwargs, {})  # provider never called
```

**Test 4 — Malformed LLM response handled gracefully; no crash, values are `None`:**
```python
provider = _MockProvider(response="Sorry, I could not understand that.")
agent = RestaurantInfoAgent(name="test", provider=provider)

result = agent.run(input_data={"user_message": "hello"})

# No exception; output keys present; extracted values default to None
self.assertIn("restaurant_name", result)
self.assertIsNone(result["restaurant_name"])
self.assertIsNone(result["restaurant_type"])
self.assertEqual(result["raw_response"], "Sorry, I could not understand that.")
```

**Test 5 — Multi-turn: two `run()` calls accumulate memory correctly:**
```python
self.agent.run(input_data={"user_message": "First message."})
self.agent.run(input_data={"user_message": "Second message."})

messages = self.agent.memory.get_messages()
self.assertEqual(len(messages), 4)  # user, assistant, user, assistant
self.assertEqual(messages[0]["content"], "First message.")
self.assertEqual(messages[2]["content"], "Second message.")
```

**Test 6 — Data store is populated by `_process_response()` after `run()`:**
```python
self.agent.run(input_data={"user_message": "My restaurant is La Palapa, casual dining."})

# Verify 5.3 integration: store() was called inside _process_response()
self.assertEqual(self.agent.retrieve("restaurant_name"), "La Palapa")
self.assertEqual(self.agent.retrieve("restaurant_type"), "casual")
```

This is the key 5.3 integration test. It proves the data store — not just memory and output —
is populated after a real `run()` call. Without this test, `self.store()` could be silently
removed from `_process_response()` and no other test would catch it.

---

### Step 5: Add `TestLiveRestaurantInfoAgent` (2 live tests)

```python
@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY not set")
class TestLiveRestaurantInfoAgent(unittest.TestCase):
    """Live tests against the Claude API. Skipped if ANTHROPIC_API_KEY is not set."""

    def setUp(self) -> None:
        self.provider = ClaudeProvider(model_name="claude-haiku-4-5-20251001")
        self.agent = RestaurantInfoAgent(name="live-test", provider=self.provider)
```

**Live test 1 — Real LLM call extracts parseable restaurant info:**
```python
result = self.agent.run(
    input_data={"user_message": "My restaurant is called Tacos El Gordo, it's a fast casual taco spot."}
)

self.assertIn("restaurant_name", result)
self.assertIn("restaurant_type", result)
# Values should be non-None strings for a clear, well-structured message
self.assertIsNotNone(result["restaurant_name"])
self.assertIsNotNone(result["restaurant_type"])
```

**Live test 2 — LLM extracts structured data across two consecutive turns:**
```python
self.agent.run(
    input_data={"user_message": "My restaurant is called El Fogón."}
)
result2 = self.agent.run(
    input_data={"user_message": "It's a full-service Mexican restaurant."}
)

# Memory accumulated correctly
messages = self.agent.memory.get_messages()
self.assertEqual(len(messages), 4)
self.assertEqual(messages[0]["content"], "My restaurant is called El Fogón.")
self.assertEqual(messages[2]["content"], "It's a full-service Mexican restaurant.")

# LLM extracted restaurant_type from the second turn (the value only a real call can produce)
self.assertIsNotNone(result2["restaurant_type"])
```

The final assertion is what distinguishes this from a mocked test: it proves the real LLM
correctly extracted a value from a second-turn message that contains only the type (not the
name). Memory accumulation alone can be validated with mocks; that the LLM processes the
message and returns a non-None type requires a live call.

**Note on live test model:** Use `claude-haiku-4-5-20251001` (cheapest/fastest) for live tests
to minimize cost. The live tests validate LLM extraction behaviour — not model quality — so the
smallest capable model is appropriate.

---

## Edge Cases

| Case | Behavior |
|------|----------|
| `user_message` key absent from `input_data` | `ValueError` raised before any API call |
| LLM returns non-JSON plain text | `_parse_response()` returns `{}`; both output fields are `None` |
| LLM returns JSON missing one field | `_RestaurantInfoResponse` defaults the missing field to `None` |
| LLM returns `null` values in JSON | Pydantic accepts `None` for `str \| None` fields |
| `run()` called twice | Memory accumulates 4 messages; data store is overwritten with latest values |
| Data store queried before `run()` | `self.retrieve("restaurant_name")` returns `None` (empty store default) |

---

## Test Strategy

All 6 mocked tests use `_MockProvider` (already in `test_agents.py`). No new fixtures needed.
`_MockProvider.last_call_kwargs` is used in Test 3 to verify the provider was never called.

Live tests use `ClaudeProvider` with `claude-haiku-4-5-20251001` to minimise cost.
They are skipped automatically if `ANTHROPIC_API_KEY` is not set.

---

## Deliverable Checklist

### `core/agents/simple_agent.py`
- [ ] `_SYSTEM_PROMPT` module-level constant defined (role and extraction task only — no JSON format instructions)
- [ ] `_RestaurantInfoResponse` Pydantic model with `restaurant_name: str | None = None` and `restaurant_type: str | None = None`
- [ ] `RestaurantInfoAgent(BaseAgent)` — no `@dataclass` decorator (no new instance fields)
- [ ] `from typing import Any, ClassVar` import present
- [ ] `INPUT_SCHEMA`, `OUTPUT_SCHEMA`, `RESPONSE_MODEL` defined as `ClassVar`
- [ ] `_generate_prompt()` returns `(_SYSTEM_PROMPT, input_data["user_message"])`
- [ ] `_process_response()` calls `self._parse_response()`, calls `self.store()` for both fields, returns 3-key dict

### `core/agents/__init__.py`
- [ ] `RestaurantInfoAgent` imported and added to `__all__`

### `tests/unit/test_agents.py`
- [ ] `import os` added at top
- [ ] `from core.agents.simple_agent import RestaurantInfoAgent` added
- [ ] `from core.ai.providers import ClaudeProvider` added
- [ ] `TestRestaurantInfoAgent` class added with 6 tests
- [ ] `TestLiveRestaurantInfoAgent` class added with 2 tests, guarded by `@unittest.skipUnless`
- [ ] All 6 mocked tests pass: `python -m pytest tests/unit/test_agents.py::TestRestaurantInfoAgent -v`
- [ ] Live tests run (or skip cleanly): `python -m pytest tests/unit/test_agents.py::TestLiveRestaurantInfoAgent -v`
- [ ] All prior 36 tests still pass: `python -m pytest tests/unit/test_agents.py -v`
- [ ] Full suite still passes: `python -m pytest tests/unit/ -v`

---

## Notes

- **No `@dataclass` decorator on `RestaurantInfoAgent`:** `RestaurantInfoAgent` adds no new
  instance fields, so it does not need `@dataclass`. Python inherits `__init__` from the
  `@dataclass` parent automatically. All existing concrete agent classes in the test suite
  (`_ConcreteAgent`, `_TypedAgent`, `_ToolAgent`) follow the same pattern — none carry
  `@dataclass`. Adding it would be harmless but misleading for future implementers.

- **`ClassVar` is not a dataclass field:** `INPUT_SCHEMA`, `OUTPUT_SCHEMA`, and `RESPONSE_MODEL`
  are declared with `ClassVar` in `BaseAgent`. Repeating them in the subclass with `ClassVar`
  is correct — they shadow the parent class-level values without becoming instance fields.
  The dataclass machinery ignores `ClassVar` annotations entirely.

- **`raw_response` is in `OUTPUT_SCHEMA` but not stored in `_data_store`:** It is the raw LLM
  string, not structured business data. The workflow engine (Task 6) reads clean extracted
  values from the data store. `raw_response` is returned for debugging only.

- **`core/__init__.py` is not updated in 5.4:** The Task 5 deliverable checklist explicitly
  places `RestaurantInfoAgent` export there under subtask 5.7, alongside `AgentRegistry`
  and `create_agent`. Exporting from `core/agents/__init__.py` now is sufficient.

- **Subtask 5.5** adds `AgentRegistry` and `create_agent()` factory to `core/agents/utils.py`.
  `RestaurantInfoAgent` does not need to change for 5.5.

- **Task 7 (Welcome Agent)** will subclass `BaseAgent` directly (not `RestaurantInfoAgent`).
  This agent is for framework validation only. Do not use it as a base class in production agents.
