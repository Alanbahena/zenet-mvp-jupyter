# Implementation Plan: Subtask 5.1 — BaseAgent Class and Input/Output Contract

## Goal

Create the abstract `BaseAgent` class that every notebook agent (Tasks 7–12) will extend.
Defines the agent lifecycle (`run()`), input/output contract enforcement, structured output
schema via Pydantic, conversation memory integration, and state persistence.
No tool calling, no data store, no retry — those come in subtasks 5.2, 5.3, and 5.5.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `BaseAgent` abstract class | Concrete agent implementations (5.4, Tasks 7–12) |
| `INPUT_SCHEMA` / `OUTPUT_SCHEMA` as `ClassVar` | Tool calling loop (5.2) |
| `RESPONSE_MODEL` as `ClassVar[type[BaseModel]]` | Agent data store (`store`/`retrieve`) (5.3) |
| `_parse_response()` Pydantic validation helper | `AgentRegistry`, `create_agent()` factory (5.5) |
| `run()` orchestration with keyword-only args | Retry with exponential backoff (5.5) |
| `_validate_input()` against `INPUT_SCHEMA` | `register_tool()` auto-creation (5.2) |
| `_generate_response()` handoff for 5.2 | Data store persistence (5.3 extends save/load) |
| `reset_memory()` | External framework adapters |
| `save_state()` / `load_state()` (memory only) | Architecture documentation (5.7) |
| `__post_init__` field validation | Live tests (added in 5.6) |
| 11 unit tests with mock provider | |
| Export `BaseAgent` from `core/__init__.py` | |

---

## Dependencies

| Component | Source | Used for |
|-----------|--------|----------|
| `LlmProvider` | `core/ai/providers.py` | Type annotation for `provider` field |
| `ToolRegistry` | `core/ai/providers.py` | Type annotation for `tools` field |
| `ConversationMemory` | `core/ai/memory.py` | Default for `memory` field; `to_dict`/`from_dict` in persistence |
| `DataLake` | `core/storage/persistence.py` | `save_state()` / `load_state()` backend |
| `parse_structured_output` | `core/ai/utils.py` | JSON parsing in `_parse_response()` |
| `pydantic.BaseModel` | `pydantic` (v2.12.5) | `RESPONSE_MODEL` definition and validation |

**Pydantic status:** Already installed as a transitive dependency via `openai` and `anthropic`
SDKs (`pydantic==2.12.5` in `requirements.txt`). Must be declared as a direct dependency
before use. First implementation step: `uv add pydantic`.

---

## Files to Create / Modify

| Action | File |
|--------|------|
| Create | `core/agents/__init__.py` |
| Create | `core/agents/base_agent.py` |
| Modify | `core/__init__.py` — add `BaseAgent` export |
| Modify | `pyproject.toml` — add `pydantic` as direct dependency via `uv add pydantic` |
| Modify | `tests/unit/test_agents.py` — create with 5.1 tests (more added in 5.2–5.6) |

---

## Implementation Steps

### Step 0: Declare Pydantic as a direct dependency

```bash
uv add pydantic
```

Pydantic is already installed transitively via `openai` and `anthropic`, but using it
directly in production code requires an explicit declaration. This command updates
`pyproject.toml` and `requirements.txt`. Run before writing any code.

---

### Step 1: Module setup

Create `core/agents/` as a new package alongside `core/ai/`, `core/domain/`,
`core/storage/`, and `core/operations/`.

**`core/agents/__init__.py`:**
```python
"""
Agent framework for Zenet MVP 0.1.

Provides BaseAgent and concrete agent implementations used across
the notebook pipeline (Tasks 7–12).
"""

from core.agents.base_agent import BaseAgent

__all__ = ["BaseAgent"]
```

**`core/agents/base_agent.py`** — module docstring:
```python
"""
BaseAgent — abstract base class for all Zenet agents.

Every notebook agent (WelcomeAgent, ClassificationAgent, etc.) extends BaseAgent
and implements two abstract methods:
    - _generate_prompt(input_data, context) -> tuple[str, str]
    - _process_response(response) -> dict

The run() method orchestrates the full lifecycle:
    validate input → build prompts → generate response → parse output

Tool calling (5.2), data store (5.3), and retry logic (5.5) are added
in subsequent subtasks without modifying run().
"""
```

---

### Step 2: Imports

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel

from core.ai.providers import LlmProvider, ToolRegistry
from core.ai.memory import ConversationMemory
from core.ai.utils import parse_structured_output
from core.storage.persistence import DataLake
```

**Note on `from __future__ import annotations`:**
Enables forward references and the `X | Y` union syntax in type hints on Python 3.10+.
Required because `ToolRegistry | None` and `type[BaseModel] | None` in field annotations
need it on older minor versions.

---

### Step 3: Three `ClassVar` schemas

All three are **class-level attributes**, not dataclass instance fields. `ClassVar` tells
the `@dataclass` decorator to exclude them from `__init__`. Each concrete agent overrides
them at class definition time.

```python
INPUT_SCHEMA:   ClassVar[dict[str, str]]          = {}    # workflow contract — input
OUTPUT_SCHEMA:  ClassVar[dict[str, str]]          = {}    # workflow contract — output
RESPONSE_MODEL: ClassVar[type[BaseModel] | None]  = None  # LLM response schema
```

**What each one does:**

| Schema | Audience | Enforced by |
|--------|----------|-------------|
| `INPUT_SCHEMA` | `BaseAgent._validate_input()` | Runtime, before API call |
| `OUTPUT_SCHEMA` | Task 6 workflow engine | Documentation only — not enforced by BaseAgent |
| `RESPONSE_MODEL` | `BaseAgent._parse_response()` | Runtime, after LLM response |

**`INPUT_SCHEMA`** — enforced strictly. Missing keys raise `ValueError` before any API call.

**`OUTPUT_SCHEMA`** — documentation contract for Task 6. BaseAgent does not validate
that `_process_response()` returns all declared keys. Some keys may be `None` (valid).
Task 6 (workflow engine) validates contracts when chaining steps, not BaseAgent.

**`RESPONSE_MODEL`** — a Pydantic `BaseModel` subclass defining the JSON structure the
LLM is expected to return. When defined:
- `_generate_response()` automatically passes `structured_output=True` to the provider,
  enabling JSON mode (OpenAI) or JSON instruction injection (Claude).
- `_parse_response()` validates the parsed response against the model.
When `None`, no structured output is requested and `_parse_response()` returns the raw
parsed dict without Pydantic validation.

**Why `ClassVar` matters:**

```python
class WelcomeAgent(BaseAgent):
    INPUT_SCHEMA = {"user_message": "Message from the restaurant operator."}
    OUTPUT_SCHEMA = {"restaurant_name": "...", "restaurant_type": "..."}

    class _Response(BaseModel):
        restaurant_name: str | None = None
        restaurant_type: str | None = None

    RESPONSE_MODEL = _Response

# Task 6 can inspect all schemas statically, before instantiation:
WelcomeAgent.INPUT_SCHEMA    # {"user_message": "..."}
WelcomeAgent.OUTPUT_SCHEMA   # {"restaurant_name": "...", ...}
WelcomeAgent.RESPONSE_MODEL  # <class '_Response'>
WelcomeAgent.RESPONSE_MODEL.model_json_schema()  # JSON schema dict for prompt injection
```

If these were regular dataclass `field()` attributes, each instance would get its own
copy and class-level inspection would not work reliably.

---

### Step 4: Dataclass field definition

Field order is strict in Python dataclasses: required fields (no default) must precede
optional fields (with default).

```python
@dataclass
class BaseAgent(ABC):
    INPUT_SCHEMA:   ClassVar[dict[str, str]]         = {}
    OUTPUT_SCHEMA:  ClassVar[dict[str, str]]         = {}
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = None

    name: str                                                               # required
    provider: LlmProvider                                                   # required
    memory: ConversationMemory = field(default_factory=ConversationMemory)  # optional
    tools: ToolRegistry | None = None                                       # optional
```

**Design decisions:**

- `name` — plain string, used in error messages and DataLake storage keys. Not a registry
  ID. Must be unique within a workflow for state persistence to work correctly.

- `provider` — required, no default. An agent without an LLM provider cannot function.

- `memory` — defaults to a fresh `ConversationMemory()`. Can be injected to resume a
  session (e.g. the operator left mid-onboarding and returns later). Injecting the same
  `ConversationMemory` instance into two agents will cause them to share history — this
  is unintended and the caller's responsibility to avoid.

- `tools` — defaults to `None`. Agents that don't use tools carry no overhead. Subtask 5.2
  adds `register_tool()` which auto-creates a `ToolRegistry` when first called.

**Dataclass inheritance constraint for Tasks 7–12:**
Because `BaseAgent` already has fields with defaults (`memory`, `tools`), concrete
subclasses decorated with `@dataclass` **cannot add new required fields** (fields without
defaults). If a concrete agent needs required configuration beyond `name` and `provider`,
pass it as part of `input_data` at call time, not as a constructor field.

---

### Step 5: `__post_init__` validation

```python
def __post_init__(self) -> None:
    """Validate fields after dataclass initialization."""
    if not self.name.strip():
        raise ValueError("Agent name cannot be empty.")
```

Validates at construction time. Consistent with the project's "validate at system
boundaries" principle.

---

### Step 6: Abstract methods

Both methods are abstract and must be implemented by every concrete agent.
Python's ABC mechanism raises `TypeError` at instantiation time if either is missing.

```python
@abstractmethod
def _generate_prompt(
    self,
    input_data: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str]:
    """
    Build system and user prompts from input data and workflow context.

    Args:
        input_data: Validated input dict. All INPUT_SCHEMA keys are guaranteed present.
        context:    Workflow context passed from the previous step. May be empty ({}).
                    BaseAgent does not define the structure of context — it is opaque
                    at this level and passed through unchanged from run().

    Returns:
        (system_prompt, user_prompt) — always a 2-tuple of non-empty strings.
        System and user content must be separated; never merge them into one string.

    Note:
        When RESPONSE_MODEL is defined, _generate_response() automatically enables
        structured output mode. The system prompt does not need to manually instruct
        the LLM to return JSON — that is handled at the provider level.
    """

@abstractmethod
def _process_response(self, response: str) -> dict[str, Any]:
    """
    Parse the raw LLM response string into a structured output dict.

    Args:
        response: Raw LLM response string as returned by the provider.

    Returns:
        Dict conforming to OUTPUT_SCHEMA. Keys declared in OUTPUT_SCHEMA may be
        None if the information was not present — BaseAgent does not validate
        the output dict against OUTPUT_SCHEMA.

    Tip:
        Use self._parse_response(response) to handle JSON parsing and Pydantic
        validation against RESPONSE_MODEL in one call, then build the output dict
        from the validated result.
    """
```

**Why `(system_prompt, user_prompt)` tuple:**
All providers accept system and user content as separate parameters. Merging them into a
single string embeds system instructions in the user turn — semantically incorrect and
inconsistent with `provider.generate(system=..., prompt=...)`.

**Note on prompt format instructions:**
When `RESPONSE_MODEL` is defined, `_generate_response()` passes `structured_output=True`
to the provider automatically. For OpenAI this enables JSON mode at the API level. For
Claude it injects a JSON instruction into the system prompt. Concrete agents should
**not** manually write "return a JSON object" in `_generate_prompt()` when using
`RESPONSE_MODEL` — the framework handles it.

---

### Step 7: `_validate_input()`

```python
def _validate_input(self, input_data: dict[str, Any]) -> None:
    """
    Raise ValueError if any INPUT_SCHEMA keys are missing from input_data.

    Called at the start of run() before any prompt construction or API call.
    Extra keys in input_data beyond INPUT_SCHEMA are silently accepted.
    An empty INPUT_SCHEMA ({}) means no validation — all inputs accepted.
    """
    missing = [k for k in self.INPUT_SCHEMA if k not in input_data]
    if missing:
        raise ValueError(
            f"[{self.name}] Missing required input keys: {missing}. "
            f"Expected: {list(self.INPUT_SCHEMA.keys())}"
        )
```

**Notes:**
- Fails fast before any API call — no cost incurred for bad input.
- Error message includes `self.name` for easier debugging in multi-agent workflows.
- Extra keys are accepted silently — callers may pass a rich context dict without
  filtering it to exactly what the agent declared.

---

### Step 8: `_parse_response()` — Pydantic validation helper

```python
def _parse_response(self, response: str) -> dict[str, Any]:
    """
    Parse the raw LLM response string and validate against RESPONSE_MODEL.

    Convenience helper for use inside _process_response(). Handles:
        1. JSON parsing via parse_structured_output()
        2. Pydantic model validation when RESPONSE_MODEL is defined
        3. Graceful fallback to raw parsed dict if Pydantic validation fails

    Args:
        response: Raw LLM response string.

    Returns:
        Validated and model-dumped dict if RESPONSE_MODEL is defined and valid.
        Raw parsed dict if RESPONSE_MODEL is None or validation fails.
        Empty dict {} if JSON parsing fails entirely.

    Example:
        class _Response(BaseModel):
            restaurant_name: str | None = None
            restaurant_type: str | None = None

        class WelcomeAgent(BaseAgent):
            RESPONSE_MODEL = _Response

            def _process_response(self, response: str) -> dict:
                data = self._parse_response(response)   # validated dict
                return {
                    "restaurant_name": data.get("restaurant_name"),
                    "restaurant_type": data.get("restaurant_type"),
                    "raw_response": response,            # agent adds this
                }
    """
    data = parse_structured_output(response)
    if self.RESPONSE_MODEL is not None and data:
        try:
            validated = self.RESPONSE_MODEL.model_validate(data)
            return validated.model_dump()
        except Exception:
            return data
    return data
```

**Design decisions:**

- `parse_structured_output()` from Task 4 handles JSON extraction — including cases where
  the LLM wraps JSON in markdown code fences (` ```json ... ``` `).

- Pydantic validation is attempted only when `RESPONSE_MODEL` is defined and parsing
  produced a non-empty dict. An empty dict from a completely unparseable response is
  returned as-is without attempting validation.

- Validation failures are caught silently and fall back to the raw parsed dict. This is
  intentional — LLMs occasionally return valid JSON that doesn't perfectly match the
  schema (e.g. extra fields, slightly wrong types). The agent's `_process_response()` can
  still extract what it needs via `.get()`. Callers should not assume strict schema
  compliance for every response.

- `model_dump()` returns a plain Python dict from the validated Pydantic model. This keeps
  the rest of the codebase free from Pydantic model objects — everything flows as dicts.

---

### Step 9: `_generate_response()` — handoff point for subtask 5.2

This method is the **clean boundary between 5.1 and 5.2**. Subtask 5.2 will replace this
single-turn implementation with a multi-turn tool calling loop — without touching `run()`.

```python
def _generate_response(self, system_prompt: str) -> str:
    """
    Generate LLM response using current conversation memory.

    Automatically enables structured output mode when RESPONSE_MODEL is defined:
        - OpenAI: response_format={"type": "json_object"} (API-level guarantee)
        - Claude: JSON instruction injected into system prompt

    Subtask 5.2 replaces this method with the tool calling loop.
    In 5.1: single-turn, no tool use.
    In 5.2: multi-turn loop that executes tool calls until a final text response.

    Args:
        system_prompt: System-level instructions for the LLM.
                       User content is already in self.memory (added by run()).

    Returns:
        Raw LLM response string.
    """
    return self.provider.generate(
        prompt=None,
        system=system_prompt,
        messages=self.memory.get_messages(),
        structured_output=self.RESPONSE_MODEL is not None,
    )
```

**Critical design note — why `prompt=None`:**
By the time `_generate_response()` is called, `run()` has already added the user message
to `self.memory` via `memory.add_user(user_prompt)`. The messages list returned by
`memory.get_messages()` therefore already contains the user message as its last entry.

Passing `prompt=user_prompt` in addition to the messages list would cause the user message
to appear **twice** — once in `messages` and once as the standalone prompt. Validated
against the Task 4.7 live tests: the correct pattern when passing `messages` is
`prompt=None`.

**Automatic structured output:**
`structured_output=self.RESPONSE_MODEL is not None` is a boolean expression — `True` when
the agent has a model, `False` when it does not. This eliminates the need for concrete
agents to manually pass `structured_output=True` and ensures consistency across all agents
that declare a `RESPONSE_MODEL`.

---

### Step 10: `run()` — orchestration method

```python
def run(
    self,
    *,
    input_data: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Execute the full agent lifecycle.

    Steps:
        1. Validate input_data against INPUT_SCHEMA
        2. Build (system_prompt, user_prompt) via _generate_prompt()
        3. Add user_prompt to conversation memory
        4. Generate LLM response via _generate_response()
           (structured output enabled automatically if RESPONSE_MODEL is defined)
        5. Add response to conversation memory
        6. Parse and return structured output via _process_response()

    Args:
        input_data: Input dict; must satisfy INPUT_SCHEMA. Extra keys are accepted.
        context:    Optional workflow context from previous pipeline steps.
                    Passed through to _generate_prompt() unchanged.

    Returns:
        Dict as returned by _process_response(). Keys depend on OUTPUT_SCHEMA.

    Raises:
        ValueError: If input_data is missing required INPUT_SCHEMA keys.
    """
    self._validate_input(input_data)
    system_prompt, user_prompt = self._generate_prompt(input_data, context or {})
    self.memory.add_user(user_prompt)
    response = self._generate_response(system_prompt)
    self.memory.add_assistant(response)
    return self._process_response(response)
```

**Design decisions:**

- `*` makes `input_data` and `context` keyword-only. Prevents positional argument errors
  like `agent.run(data, ctx)` where argument order is ambiguous.

- `context or {}` — `None` context is normalized to an empty dict so `_generate_prompt()`
  always receives a dict. Concrete agents can safely call `context.get(...)`.

- Memory receives `user_prompt` (the formatted, LLM-ready string), not raw `input_data`.
  Conversation history must be LLM-ready content.

- No exception handling in 5.1. API errors and other failures propagate to the caller.
  Retry logic is added in subtask 5.5 via `_generate_response()`.

---

### Step 11: `reset_memory()`

```python
def reset_memory(self) -> None:
    """
    Clear conversation history.

    Does not affect the agent data store (subtask 5.3).
    Use this to start a fresh conversation without creating a new agent instance,
    for example when moving between pipeline stages with the same agent.
    """
    self.memory.clear()
```

---

### Step 12: `save_state()` and `load_state()`

For 5.1, these persist only conversation memory. Subtask 5.3 extends them to also
include the agent data store.

```python
def save_state(self, data_lake: DataLake, *, session_id: str) -> None:
    """
    Persist conversation memory to DataLake.

    Subtask 5.3 extends this to also persist the agent data store.

    Args:
        data_lake:  DataLake instance for storage.
        session_id: Unique session identifier. Used as the storage key.
                    Must be unique per agent instance to avoid key collisions.
    """
    data_lake.save("agent_state", session_id, {
        "agent_name": self.name,
        "memory": self.memory.to_dict(),
    })

def load_state(self, data_lake: DataLake, *, session_id: str) -> None:
    """
    Restore conversation memory from DataLake.

    No-op if session_id does not exist in storage — agent state is unchanged.
    Subtask 5.3 extends this to also restore the agent data store.

    Args:
        data_lake:  DataLake instance for storage.
        session_id: Session identifier used when save_state() was called.
    """
    state = data_lake.load("agent_state", session_id)
    if state:
        self.memory = ConversationMemory.from_dict(state["memory"])
```

**Notes:**
- `session_id` is keyword-only — it is a meaningful identifier, not a positional detail.
- Storage key is `("agent_state", session_id)` — consistent with Task 3's DataLake usage.
- `data_lake.load()` returns `None` if key doesn't exist; `if state:` handles silently.
- Subtask 5.3 adds `data_store` to the saved dict. Old sessions without it default to `{}`.

---

### Step 13: Export from `core/__init__.py`

```python
from core.agents.base_agent import BaseAgent
```

Add `"BaseAgent"` to `__all__`. Only export added in 5.1 — concrete agents and utilities
are added in 5.4 and 5.5.

---

## Edge Cases

| Case | Behavior |
|------|----------|
| `name` is empty string or whitespace | `__post_init__` raises `ValueError` |
| `INPUT_SCHEMA = {}` | All input accepted; no validation performed |
| Missing `INPUT_SCHEMA` key in `input_data` | `ValueError` raised before any API call |
| Extra keys in `input_data` beyond `INPUT_SCHEMA` | Silently accepted |
| `context=None` | Normalized to `{}` before passing to `_generate_prompt()` |
| `_process_response()` returns dict missing `OUTPUT_SCHEMA` keys | Accepted — no output validation |
| `load_state()` with unknown `session_id` | No-op — agent state unchanged |
| `memory` injected and shared between two agents | Both share history — caller's responsibility |
| Concrete subclass missing abstract method | `TypeError` raised at instantiation (Python ABC) |
| `provider.generate()` raises | Exception propagates to caller — no handling in 5.1 |
| `RESPONSE_MODEL = None` | `structured_output=False`; `_parse_response()` returns raw parsed dict |
| `RESPONSE_MODEL` defined, LLM returns valid JSON matching model | `_parse_response()` returns `model_dump()` dict |
| `RESPONSE_MODEL` defined, LLM returns valid JSON not matching model | Pydantic validation fails silently; raw parsed dict returned |
| `RESPONSE_MODEL` defined, LLM returns non-JSON | `parse_structured_output()` returns `{}`; no Pydantic validation attempted |

---

## Test Strategy

### Mock provider fixture

```python
class _MockProvider(LlmProvider):
    """Minimal mock provider for unit testing. No API calls."""

    def __init__(self, response: str = '{"result": "ok"}') -> None:
        super().__init__(model_name="mock")
        self.response = response
        self.last_call_kwargs: dict = {}

    def generate(self, prompt, **kwargs) -> str:
        self.last_call_kwargs = {"prompt": prompt, **kwargs}
        return self.response
```

`last_call_kwargs` lets tests assert what arguments were passed to `generate()` —
including whether `structured_output=True` was passed automatically.

### Concrete agent fixture

```python
class _ConcreteAgent(BaseAgent):
    INPUT_SCHEMA  = {"message": "A message."}
    OUTPUT_SCHEMA = {"reply": "The agent's reply."}

    def _generate_prompt(self, input_data, context):
        return "You are a test agent.", input_data["message"]

    def _process_response(self, response):
        return {"reply": response}
```

### Concrete agent fixture with RESPONSE_MODEL

```python
class _AgentResponse(BaseModel):
    reply: str = ""
    confidence: float = 1.0

class _TypedAgent(BaseAgent):
    INPUT_SCHEMA   = {"message": "A message."}
    OUTPUT_SCHEMA  = {"reply": "The agent's reply.", "confidence": "Confidence score."}
    RESPONSE_MODEL = _AgentResponse

    def _generate_prompt(self, input_data, context):
        return "You are a test agent.", input_data["message"]

    def _process_response(self, response):
        data = self._parse_response(response)
        return {"reply": data.get("reply", ""), "confidence": data.get("confidence", 1.0)}
```

### Tests (11 tests)

| # | Test | Verifies |
|---|------|----------|
| 1 | `_ConcreteAgent` instantiates with `name` and `_MockProvider` | `@dataclass` + `ABC` + `__post_init__` |
| 2 | `BaseAgent` instantiated directly raises `TypeError` | Abstract method enforcement |
| 3 | Subclass missing abstract methods raises `TypeError` at instantiation | ABC enforcement |
| 4 | Empty `name` raises `ValueError` at instantiation | `__post_init__` validation |
| 5 | `run()` with missing `INPUT_SCHEMA` key raises `ValueError` | `_validate_input()` fires before API call |
| 6 | `run()` with valid input returns expected output dict | Full lifecycle |
| 7 | Memory contains user and assistant messages after `run()` | Memory population in order |
| 8 | `reset_memory()` clears conversation history | Memory reset |
| 9 | `save_state()` / `load_state()` round-trip preserves memory | Persistence end-to-end |
| 10 | `_generate_response()` passes `structured_output=True` when `RESPONSE_MODEL` is defined | Automatic structured output |
| 11 | `_parse_response()` validates against `RESPONSE_MODEL` and returns `model_dump()` dict | Pydantic integration |

**Test 5 detail:** Call `agent.run(input_data={})` with `INPUT_SCHEMA = {"message": "..."}`.
Assert `ValueError` raised and mock provider's `generate()` was never called.

**Test 7 detail:** After `run()`, assert:
- `memory.message_count == 2`
- `messages[0]["role"] == "user"`
- `messages[1]["role"] == "assistant"`
- `messages[1]["content"]` matches mock provider's response string

**Test 9 detail:** Use `JsonStorage` as the DataLake backend (temp dir).
Save state, create a new agent instance with fresh memory, load state, assert messages match.

**Test 10 detail:** Instantiate `_TypedAgent` (has `RESPONSE_MODEL`). Call `run()`.
Assert `mock_provider.last_call_kwargs["structured_output"] is True`.
Instantiate `_ConcreteAgent` (no `RESPONSE_MODEL`). Call `run()`.
Assert `mock_provider.last_call_kwargs["structured_output"] is False`.

**Test 11 detail:** Call `_typed_agent._parse_response('{"reply": "hello", "confidence": 0.9}')`.
Assert result is `{"reply": "hello", "confidence": 0.9}`.
Call with invalid JSON `"not json"` — assert result is `{}`.
Call with JSON that fails model validation — assert raw parsed dict is returned (no exception).

---

## Deliverable Checklist

### Dependency
- [ ] Run `uv add pydantic` — adds `pydantic` as direct dependency in `pyproject.toml`

### Module
- [ ] Create `core/agents/` directory
- [ ] Create `core/agents/__init__.py` — exports `BaseAgent`
- [ ] Create `core/agents/base_agent.py` with module docstring

### Class definition
- [ ] `INPUT_SCHEMA: ClassVar[dict[str, str]] = {}`
- [ ] `OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {}`
- [ ] `RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = None`
- [ ] `name: str` — required field
- [ ] `provider: LlmProvider` — required field
- [ ] `memory: ConversationMemory` — optional, default factory
- [ ] `tools: ToolRegistry | None` — optional, default `None`
- [ ] `__post_init__()` — validates `name` is not empty

### Methods
- [ ] `_generate_prompt()` — abstract, returns `tuple[str, str]`
- [ ] `_process_response()` — abstract, returns `dict[str, Any]`
- [ ] `_validate_input()` — checks `INPUT_SCHEMA` keys, raises `ValueError` with agent name
- [ ] `_parse_response()` — JSON parsing + Pydantic validation, graceful fallback
- [ ] `_generate_response()` — `prompt=None`, auto `structured_output` from `RESPONSE_MODEL`
- [ ] `run()` — keyword-only args, full lifecycle, no exception handling
- [ ] `reset_memory()` — delegates to `self.memory.clear()`
- [ ] `save_state()` — keyword-only `session_id`, persists memory only
- [ ] `load_state()` — keyword-only `session_id`, no-op if session not found

### Exports
- [ ] Add `from core.agents.base_agent import BaseAgent` to `core/__init__.py`
- [ ] Add `"BaseAgent"` to `__all__` in `core/__init__.py`

### Tests
- [ ] Create `tests/unit/test_agents.py` with `_MockProvider`, `_ConcreteAgent`, `_TypedAgent` fixtures
- [ ] 11 tests implemented and passing
- [ ] All 11 pass: `python -m pytest tests/unit/test_agents.py -v`
- [ ] Full suite still passes: `python -m pytest tests/unit/ -v`

---

## Notes

- **`uv add pydantic` first:** Pydantic is a transitive dep today, but must be declared
  directly before writing code that imports it. Transitive deps can disappear if an
  upstream package changes.

- **`prompt=None` in `_generate_response()`:** Critical. The user message is already in
  `self.memory`. Passing `prompt=user_prompt` alongside `messages` would duplicate it.
  Validated against Task 4.7 live tests.

- **`OUTPUT_SCHEMA` is documentation only:** BaseAgent does not validate
  `_process_response()` output. Concrete agents must declare it accurately for Task 6.

- **Pydantic validation is a soft guarantee:** `_parse_response()` falls back silently
  when validation fails. LLMs occasionally return valid JSON with minor schema deviations.
  Do not write `_process_response()` code that assumes strict model compliance.

- **`model_dump()` returns plain dicts:** Pydantic model instances are immediately
  converted to dicts. Nothing downstream should ever receive a Pydantic model object.

- **Thread safety:** Not addressed. Single-threaded usage assumed throughout MVP.

- **`context` is opaque:** BaseAgent passes `context` through to `_generate_prompt()`
  unchanged. Its structure is defined by Task 6, not BaseAgent.

- **Subtask 5.3 extends persistence:** Adds `_data_store` to `save_state()` / `load_state()`.
  Storage format is backwards-compatible — old sessions without `data_store` default to `{}`.

---

## Time Estimate

- `uv add pydantic` + module setup: 15 minutes
- Imports and class definition: 20 minutes
- Abstract methods and docstrings: 20 minutes
- `_validate_input()`, `_parse_response()`: 25 minutes
- `_generate_response()`, `run()`: 25 minutes
- `reset_memory()`, `save_state()`, `load_state()`: 20 minutes
- Export update (`core/__init__.py`): 5 minutes
- Tests (11 tests + 3 fixtures): 55 minutes
- **Total: ~3 hours**
