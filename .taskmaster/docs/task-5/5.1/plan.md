# Implementation Plan: Subtask 5.1 — BaseAgent Class and Input/Output Contract

## Goal

Create the abstract `BaseAgent` class that every notebook agent (Tasks 7–12) will extend.
Defines the agent lifecycle (`run()`), input/output contract enforcement, conversation memory
integration, and state persistence. No tool calling, no data store, no retry — those come
in subtasks 5.2, 5.3, and 5.5.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `BaseAgent` abstract class | Concrete agent implementations (5.4, Tasks 7–12) |
| `INPUT_SCHEMA` / `OUTPUT_SCHEMA` as `ClassVar` | Tool calling loop (5.2) |
| `run()` orchestration with keyword-only args | Agent data store (`store`/`retrieve`) (5.3) |
| `_validate_input()` against `INPUT_SCHEMA` | `AgentRegistry`, `create_agent()` factory (5.5) |
| `_generate_response()` handoff for 5.2 | Retry with exponential backoff (5.5) |
| `reset_memory()` | `register_tool()` auto-creation (5.2) |
| `save_state()` / `load_state()` (memory only) | Data store persistence (5.3 extends these) |
| `__post_init__` field validation | External framework adapters |
| 8 unit tests with mock provider | Live tests (added in 5.6) |
| Export `BaseAgent` from `core/__init__.py` | Architecture documentation (5.7) |

---

## Dependencies

All components below are from Task 4, already implemented and exported from `core/__init__.py`:

| Component | Source | Used for |
|-----------|--------|----------|
| `LlmProvider` | `core/ai/providers.py` | Type annotation for `provider` field |
| `ToolRegistry` | `core/ai/providers.py` | Type annotation for `tools` field |
| `ConversationMemory` | `core/ai/memory.py` | Default for `memory` field; `to_dict`/`from_dict` in persistence |
| `DataLake` | `core/storage/persistence.py` | `save_state()` / `load_state()` backend |

---

## Files to Create / Modify

| Action | File |
|--------|------|
| Create | `core/agents/__init__.py` |
| Create | `core/agents/base_agent.py` |
| Modify | `core/__init__.py` — add `BaseAgent` export |
| Modify | `tests/unit/test_agents.py` — create with 5.1 tests (more added in 5.2–5.6) |

---

## Implementation Steps

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

from core.ai.providers import LlmProvider, ToolRegistry
from core.ai.memory import ConversationMemory
from core.storage.persistence import DataLake
```

**Note on `from __future__ import annotations`:**
Enables forward references and the `X | Y` union syntax in type hints on Python 3.10+.
Required because `ToolRegistry | None` in field annotations needs it on older minor versions.

---

### Step 3: `INPUT_SCHEMA` and `OUTPUT_SCHEMA` as `ClassVar`

These are **class-level attributes**, not dataclass instance fields. `ClassVar` tells the
`@dataclass` decorator to exclude them from `__init__`. Each concrete agent overrides them
at class definition time.

```python
INPUT_SCHEMA: ClassVar[dict[str, str]] = {}
OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {}
```

**Why `ClassVar` matters:**

```python
# Correct — class-level, inspectable before instantiation
class WelcomeAgent(BaseAgent):
    INPUT_SCHEMA = {"user_message": "Message from the restaurant operator."}
    OUTPUT_SCHEMA = {"restaurant_name": "...", "restaurant_type": "..."}

# Task 6 can inspect schemas statically:
WelcomeAgent.INPUT_SCHEMA   # works without creating an instance
WelcomeAgent.OUTPUT_SCHEMA  # works without creating an instance
```

If `INPUT_SCHEMA` were a regular dataclass `field()`, each instance would get its own copy
and class-level inspection would not work reliably.

**`OUTPUT_SCHEMA` is documentation, not a runtime enforcer:**
`_validate_input()` enforces `INPUT_SCHEMA` before any API call. `OUTPUT_SCHEMA` is
intentionally not validated automatically — some output keys may be `None` (valid),
and the workflow engine (Task 6) validates contracts when chaining steps.
This design decision must be respected by all concrete agents: declare `OUTPUT_SCHEMA`
accurately, but BaseAgent will not reject a response dict that is missing keys.

---

### Step 4: Dataclass field definition

Field order is strict in Python dataclasses: required fields (no default) must precede
optional fields (with default).

```python
@dataclass
class BaseAgent(ABC):
    INPUT_SCHEMA: ClassVar[dict[str, str]] = {}
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {}

    name: str                                                               # required
    provider: LlmProvider                                                   # required
    memory: ConversationMemory = field(default_factory=ConversationMemory)  # optional
    tools: ToolRegistry | None = None                                       # optional
```

**Design decisions:**

- `name` — plain string, used in error messages and DataLake keys. Not a registry ID.
  Must be unique within a workflow for state persistence to work correctly.

- `provider` — required, no default. An agent without an LLM provider cannot function.

- `memory` — defaults to a fresh `ConversationMemory()`. Can be injected to resume a
  session (e.g. the operator left mid-onboarding and returns later). Injecting the same
  `ConversationMemory` instance into two agents will cause them to share history — this
  is unintended and the caller's responsibility to avoid.

- `tools` — defaults to `None`. Agents that don't use tools carry no overhead. Subtask 5.2
  adds `register_tool()` which auto-creates a `ToolRegistry` when first called.

**Dataclass inheritance constraint for Tasks 7–12:**
When a concrete agent is also decorated with `@dataclass` and adds its own fields,
Python requires that fields with defaults do not precede fields without defaults.
Because `BaseAgent` already has fields with defaults (`memory`, `tools`), concrete
subclasses **cannot add new required fields** (fields without defaults) through
`@dataclass`. If a concrete agent needs required configuration beyond `name` and
`provider`, pass it as part of `input_data` at call time, not as a constructor field.

---

### Step 5: `__post_init__` validation

```python
def __post_init__(self) -> None:
    """Validate fields after dataclass initialization."""
    if not self.name.strip():
        raise ValueError("Agent name cannot be empty.")
```

Validates at construction time, not at `run()` time. Consistent with the project's
"validate at system boundaries" principle.

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
    """

@abstractmethod
def _process_response(self, response: str) -> dict[str, Any]:
    """
    Parse the raw LLM response string into a structured output dict.

    Args:
        response: Raw LLM response string as returned by the provider.

    Returns:
        Dict conforming to OUTPUT_SCHEMA. Keys declared in OUTPUT_SCHEMA may be
        None if the information was not present in the response — BaseAgent does
        not validate the output dict against OUTPUT_SCHEMA.
    """
```

**Why `(system_prompt, user_prompt)` tuple:**
All providers accept system and user content as separate parameters. Merging them into a
single string would embed system instructions in the user turn, which is semantically
incorrect and inconsistent with how `provider.generate(system=..., prompt=...)` works.

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
- Extra keys are accepted silently — allows callers to pass a rich context dict without
  filtering it to exactly what the agent declared.

---

### Step 8: `_generate_response()` — handoff point for subtask 5.2

This method is the **clean boundary between 5.1 and 5.2**. Subtask 5.2 will replace this
single-turn implementation with a multi-turn tool calling loop — without touching `run()`.

```python
def _generate_response(self, system_prompt: str) -> str:
    """
    Generate LLM response using current conversation memory.

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
    )
```

**Critical design note — why `prompt=None`:**
By the time `_generate_response()` is called, `run()` has already added the user message
to `self.memory` via `memory.add_user(user_prompt)`. The messages list returned by
`memory.get_messages()` therefore already contains the user message as its last entry.

Passing `prompt=user_prompt` here in addition to the messages list would cause the user
message to appear **twice** in the conversation — once in `messages` and once as the
standalone prompt. This was validated against the Task 4.7 live tests, which confirm
that the correct pattern when passing `messages` is `prompt=None`.

---

### Step 9: `run()` — orchestration method

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
        5. Add response to conversation memory
        6. Parse response into output dict via _process_response()
        7. Return output dict

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
  like `agent.run(data, ctx)` where argument order is unclear.

- `context or {}` — `None` context is normalized to an empty dict so `_generate_prompt()`
  always receives a dict. Concrete agents can safely call `context.get(...)` without
  checking for `None`.

- Memory receives `user_prompt` (the formatted, LLM-ready string), not `input_data` raw.
  Conversation history must be LLM-ready content.

- No exception handling in `run()` for 5.1. API errors, rate limits, and other failures
  propagate to the caller. Retry logic is added in subtask 5.5 via `_generate_response()`.

---

### Step 10: `reset_memory()`

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

Exists as a named method rather than `agent.memory.clear()` for two reasons:
1. Part of the public agent interface — callers should not need to know about `memory` internals.
2. Subtask 5.3 may extend this to also clear the data store if needed.

---

### Step 11: `save_state()` and `load_state()`

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
                    Must be unique per agent instance to avoid collisions.
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
- `data_lake.load()` returns `None` if the key doesn't exist; the `if state:` guard
  handles that silently without raising.

---

### Step 12: Export from `core/__init__.py`

Add to `core/__init__.py`:

```python
from core.agents.base_agent import BaseAgent
```

Add `"BaseAgent"` to `__all__`.

This is the only export added in 5.1. Concrete agents and utilities are added in 5.4 and 5.5.

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
| `memory` injected and shared between two agents | Both share history — caller's responsibility to avoid |
| Concrete subclass missing abstract method | `TypeError` raised at instantiation (Python ABC) |
| `provider.generate()` raises | Exception propagates to caller — no handling in 5.1 |

---

## Test Strategy

### Mock provider fixture

All 5.1 tests use a `_MockProvider` that returns a predictable string:

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

`last_call_kwargs` lets tests assert what arguments were passed to `generate()`.

### Concrete agent fixture

All tests use a minimal `_ConcreteAgent` that implements the two abstract methods:

```python
class _ConcreteAgent(BaseAgent):
    INPUT_SCHEMA = {"message": "A message."}
    OUTPUT_SCHEMA = {"reply": "The agent's reply."}

    def _generate_prompt(self, input_data, context):
        return "You are a test agent.", input_data["message"]

    def _process_response(self, response):
        return {"reply": response}
```

### Tests (8 tests)

| # | Test | Verifies |
|---|------|----------|
| 1 | `_ConcreteAgent` instantiates with `name` and `_MockProvider` | `@dataclass` + `ABC` work together; `__post_init__` runs |
| 2 | Instantiating `BaseAgent` directly (without subclassing) raises `TypeError` | Abstract method enforcement |
| 3 | `_ConcreteAgent` without abstract methods raises `TypeError` at instantiation | ABC enforcement on subclass |
| 4 | `run()` with missing `INPUT_SCHEMA` key raises `ValueError` | `_validate_input()` fires before API call |
| 5 | `run()` with all required keys returns dict with `OUTPUT_SCHEMA` shape | Full lifecycle, valid input |
| 6 | Memory contains user and assistant messages after `run()` | Memory population in correct order |
| 7 | `reset_memory()` clears conversation history | Memory state reset |
| 8 | `save_state()` / `load_state()` round-trip preserves memory | Persistence end-to-end |

**Test 4 detail:** Call `agent.run(input_data={})` with `INPUT_SCHEMA = {"message": "..."}`.
Assert `ValueError` is raised and the mock provider's `generate()` was never called
(zero API calls for bad input).

**Test 6 detail:** After `run()`, assert:
- `memory.message_count == 2`
- `memory.get_messages()[0]["role"] == "user"`
- `memory.get_messages()[1]["role"] == "assistant"`
- `memory.get_messages()[1]["content"]` matches the mock provider's response string

**Test 8 detail:** Use `JsonStorage` as the DataLake backend (in-memory temp dir).
Save state, create a new agent instance with a fresh memory, load state, assert messages match.

---

## Deliverable Checklist

- [ ] Create `core/agents/` directory
- [ ] Create `core/agents/__init__.py` — exports `BaseAgent`
- [ ] Create `core/agents/base_agent.py` with module docstring
- [ ] `INPUT_SCHEMA` and `OUTPUT_SCHEMA` as `ClassVar[dict[str, str]]`
- [ ] `name: str` — required field
- [ ] `provider: LlmProvider` — required field
- [ ] `memory: ConversationMemory` — optional, default factory
- [ ] `tools: ToolRegistry | None` — optional, default `None`
- [ ] `__post_init__()` — validates `name` is not empty
- [ ] `_generate_prompt()` — abstract, returns `tuple[str, str]`
- [ ] `_process_response()` — abstract, returns `dict[str, Any]`
- [ ] `_validate_input()` — checks `INPUT_SCHEMA` keys, raises `ValueError` with agent name
- [ ] `_generate_response()` — single-turn, uses `prompt=None` with `messages` from memory
- [ ] `run()` — keyword-only args, full lifecycle, no exception handling
- [ ] `reset_memory()` — delegates to `self.memory.clear()`
- [ ] `save_state()` — keyword-only `session_id`, persists memory via DataLake
- [ ] `load_state()` — keyword-only `session_id`, no-op if session not found
- [ ] Add `from core.agents.base_agent import BaseAgent` to `core/__init__.py`
- [ ] Add `"BaseAgent"` to `__all__` in `core/__init__.py`
- [ ] Create `tests/unit/test_agents.py` with `_MockProvider`, `_ConcreteAgent`, 8 tests
- [ ] All 8 tests pass: `python -m pytest tests/unit/test_agents.py -v`
- [ ] Full suite still passes: `python -m pytest tests/unit/ -v`

---

## Notes

- **`prompt=None` in `_generate_response()`:** Critical. The user message is already in
  `self.memory` before `_generate_response()` is called. Passing `prompt=user_prompt`
  alongside `messages` would duplicate the user message. Validated against Task 4.7 tests.

- **`OUTPUT_SCHEMA` is documentation only:** BaseAgent does not validate `_process_response()`
  output. Concrete agents must declare `OUTPUT_SCHEMA` accurately for Task 6 to work,
  but BaseAgent will not reject output dicts that are missing declared keys.

- **Thread safety:** Not addressed. Single-threaded usage assumed throughout MVP.
  If multiple threads share an agent instance, conversation memory and data store
  are not protected.

- **`context` is opaque:** BaseAgent passes `context` through to `_generate_prompt()`
  without inspecting or validating it. Its structure is defined by Task 6 (workflow engine),
  not by BaseAgent.

- **Subtask 5.3 extends `save_state()` / `load_state()`:** The 5.1 implementation saves
  only `memory`. Subtask 5.3 adds `_data_store` to both methods. The storage key and
  format are compatible — 5.3 adds a new key to the saved dict without breaking existing
  saved sessions (old sessions simply won't have `data_store`, which defaults to `{}`).

---

## Time Estimate

- Module setup and imports: 15 minutes
- Class definition, fields, `__post_init__`: 20 minutes
- Abstract methods and docstrings: 20 minutes
- `_validate_input()`, `_generate_response()`, `run()`: 30 minutes
- `reset_memory()`, `save_state()`, `load_state()`: 20 minutes
- Export update (`core/__init__.py`): 5 minutes
- Tests (8 tests + fixtures): 45 minutes
- **Total: ~2.5 hours**
