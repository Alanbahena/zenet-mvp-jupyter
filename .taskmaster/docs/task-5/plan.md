# Task 5 — Agent Framework and Base Agent Class

## Goal

Build the foundational agent layer that all specific agents (Tasks 7–12) will extend.
This layer sits between the LLM integration framework (Task 4) and the individual notebook agents,
providing a consistent, composable interface for execution, tool use, memory, state management,
and error handling.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `BaseAgent` abstract class with core lifecycle | External framework adapters (LangChain, CrewAI, Autogen) |
| Input/output contract definition for all agents | Full agent implementations (Tasks 7–12) |
| Tool calling mechanism integrated with `ToolRegistry` | Workflow orchestration (Task 6) |
| Conversation memory integration with `ConversationMemory` | File parsing / multi-agent collaboration (Task 10) |
| Agent-level state management and persistence | Streaming responses |
| Concrete minimal agent validating the framework | Multi-modal inputs (images, audio) |
| Agent utilities (factory, serialization, registry) | Token usage tracking and billing |
| Error handling and recovery within a single agent | Agent-to-agent communication protocol |
| Comprehensive unit and live tests | External API mocking beyond unit tests |
| Architecture documentation | Gradio UI for agents |

---

## Architectural Decisions

### A. No external framework adapters in Task 5

External frameworks (LangChain, LangGraph, CrewAI, Autogen) are **not integrated here**.

**Rationale:**
- All agents in Tasks 7–12 extend `BaseAgent` directly, using `LlmProvider` and `ToolRegistry` from Task 4.
  None of them require a specific external framework at the foundation layer.
- The first concrete use case for a framework is **Task 10 (Alignment Agent)**: a user uploads a PDF or Excel
  file and multiple agents collaborate to extract, normalize, and structure the data.
  That scenario maps to **LangGraph** (cyclic multi-agent workflows with conditional branching and shared state).
  Introducing it there — where requirements are concrete — avoids premature abstraction.
- Adding adapters for 4 frameworks now would create competing abstractions with no immediate consumer.

**Decision:** Defer external framework integration to the subtask or task that first needs it.
For Task 10, evaluate LangGraph specifically for multi-agent file processing.
Note this deferral in the Task 10 plan so the decision lives where it will be acted on.

**Design constraint:** `BaseAgent` must not close the door on framework integration.
Its interface should be simple and composable so adapters can wrap it later without changes.

---

### B. Input/output contract is explicit and required

Every agent must declare:
- **Input schema:** What `input_data` dict it accepts and what keys are required.
- **Output schema:** What dict structure `run()` always returns.

This is not optional. Task 6 (workflow engine) will rely on these contracts to chain agents
and map outputs from one step to inputs of the next.
Agents that do not declare a contract cannot participate in a workflow.

**Implementation:** Each concrete agent defines `INPUT_SCHEMA` and `OUTPUT_SCHEMA` class attributes
(or class-level docstrings at minimum). BaseAgent validates input against the schema before running.

---

### C. Concrete example mirrors Task 7 requirements

Subtask 5.4 builds a minimal but realistic agent that closely mirrors what the Welcome Agent (Task 7)
will need: capture restaurant name, type, and operator concerns from a conversation.
Using a realistic target (rather than a generic `TestAgent`) ensures the framework is validated
against actual downstream requirements before Task 7 begins.

---

## Dependencies

All components below are from Task 4 and already exported from `core/__init__.py`:

| Component | Source | Used for |
|-----------|--------|----------|
| `LlmProvider` | `core/ai/providers.py` | Base provider interface |
| `OpenAiProvider` | `core/ai/providers.py` | Concrete provider for agents |
| `ClaudeProvider` | `core/ai/providers.py` | Concrete provider for agents |
| `ToolRegistry` | `core/ai/providers.py` | Tool registration and execution |
| `ConversationMemory` | `core/ai/memory.py` | Conversation context tracking |
| `PromptTemplate` | `core/ai/prompts.py` | Prompt construction |
| `parse_structured_output` | `core/ai/utils.py` | Structured response parsing |
| `validate_structured_output` | `core/ai/utils.py` | Output validation |
| `DataLake` | `core/storage/persistence.py` | Agent state persistence |

---

## Files to Create / Modify

```
core/
└── agents/
    ├── __init__.py               # Create — exports BaseAgent and concrete agents
    ├── base_agent.py             # Create — BaseAgent abstract class (subtask 5.1)
    ├── simple_agent.py           # Create — Concrete minimal agent (subtask 5.4)
    └── utils.py                  # Create — Agent utilities, factory, registry (subtask 5.5)

tests/
└── unit/
    └── test_agents.py            # Create — All agent tests (subtasks 5.6)

docs/
└── Architecture/
    └── architecture-agent-framework.md   # Create — Architecture doc (subtask 5.7)

core/__init__.py                  # Modify — Add agent exports
```

---

## Subtask Breakdown

### Subtask 5.1 — BaseAgent class and input/output contract

**Goal:** Define the abstract foundation that all agents (Tasks 7–12) will extend.

**Interface:**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from core import LlmProvider, ConversationMemory, ToolRegistry

@dataclass
class BaseAgent(ABC):
    """
    Abstract base class for all Zenet agents.

    Subclasses must implement:
        - INPUT_SCHEMA  (class attribute: dict describing required input keys)
        - OUTPUT_SCHEMA (class attribute: dict describing output keys)
        - _generate_prompt(input_data, context) -> tuple[str, str]  (system, user)
        - _process_response(response) -> dict

    The run() method orchestrates the full lifecycle:
        validate input → build prompt → generate → process response → return output
    """

    name: str
    provider: LlmProvider
    memory: ConversationMemory = field(default_factory=ConversationMemory)
    tools: ToolRegistry | None = None

    # Subclasses must define these
    INPUT_SCHEMA: dict[str, str] = field(default_factory=dict, init=False)
    OUTPUT_SCHEMA: dict[str, str] = field(default_factory=dict, init=False)

    def run(self, *, input_data: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Execute the agent lifecycle.

        1. Validate input against INPUT_SCHEMA
        2. Build system and user prompts
        3. Generate LLM response (with tools if registered)
        4. Process response into structured output
        5. Return output dict conforming to OUTPUT_SCHEMA

        Args:
            input_data: Dict of inputs; must satisfy INPUT_SCHEMA
            context:    Optional workflow context passed from previous steps

        Returns:
            Dict conforming to OUTPUT_SCHEMA
        """
        self._validate_input(input_data)
        system_prompt, user_prompt = self._generate_prompt(input_data, context or {})
        self.memory.add_user(user_prompt)
        response = self.provider.generate(
            prompt=user_prompt,
            system=system_prompt,
            messages=self.memory.get_messages(),
            tools=self.tools.to_openai_tools() if self.tools else None,
        )
        self.memory.add_assistant(response)
        return self._process_response(response)

    @abstractmethod
    def _generate_prompt(
        self, input_data: dict[str, Any], context: dict[str, Any]
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt)."""

    @abstractmethod
    def _process_response(self, response: str) -> dict[str, Any]:
        """Parse LLM response into output dict conforming to OUTPUT_SCHEMA."""

    def _validate_input(self, input_data: dict[str, Any]) -> None:
        """Raise ValueError if required INPUT_SCHEMA keys are missing."""
        missing = [k for k in self.INPUT_SCHEMA if k not in input_data]
        if missing:
            raise ValueError(f"[{self.name}] Missing required input keys: {missing}")

    def reset_memory(self) -> None:
        """Clear conversation memory."""
        self.memory.clear()

    def save_state(self, data_lake, *, session_id: str) -> None:
        """Persist agent conversation memory via DataLake."""
        data_lake.save("agent_state", session_id, {
            "agent_name": self.name,
            "memory": self.memory.to_dict(),
        })

    def load_state(self, data_lake, *, session_id: str) -> None:
        """Restore agent conversation memory from DataLake."""
        state = data_lake.load("agent_state", session_id)
        if state:
            self.memory = ConversationMemory.from_dict(state["memory"])
```

**Design decisions:**
- `run()` is keyword-only (`input_data`, `context`) to prevent positional argument mistakes.
- `memory` defaults to a fresh `ConversationMemory()`; can be injected for session continuity.
- `tools` is optional; agents that don't use tools pass `None`.
- `INPUT_SCHEMA` and `OUTPUT_SCHEMA` are class-level dicts: `{"key": "description"}`.
  Used for validation in `_validate_input()` and documentation of the contract.
- `_generate_prompt` returns `(system, user)` tuple — agents always separate system and user content.
- `save_state`/`load_state` use `DataLake` from Task 3 — consistent with persistence architecture.

**Files:**
- Create `core/agents/__init__.py`
- Create `core/agents/base_agent.py`

**Tests:** 8 tests
- Instantiating a concrete subclass works
- Calling `run()` without required input raises `ValueError`
- `_validate_input()` passes with all required keys present
- `memory` is populated after `run()`
- `reset_memory()` clears conversation history
- `save_state()` / `load_state()` round-trip via DataLake
- Subclass without abstract methods raises `TypeError`
- `run()` returns dict conforming to subclass `OUTPUT_SCHEMA`

---

### Subtask 5.2 — Tool calling mechanism

**Goal:** Integrate `ToolRegistry` into the agent execution loop so agents can call tools
in multi-turn interactions (LLM requests tool → agent executes → LLM continues).

**Implementation:**

The basic `run()` from 5.1 handles single-turn responses. For tool use, the agent needs a loop:

```python
def run(self, *, input_data: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    self._validate_input(input_data)
    system_prompt, user_prompt = self._generate_prompt(input_data, context or {})
    self.memory.add_user(user_prompt)

    # Tool use loop — continues until LLM returns a final text response
    while True:
        response = self.provider.generate(
            prompt=user_prompt,
            system=system_prompt,
            messages=self.memory.get_messages(),
            tools=self.tools.to_openai_tools() if self.tools else None,
        )

        # If response contains tool calls, execute them and continue
        tool_calls = self._extract_tool_calls(response)
        if tool_calls and self.tools:
            self.memory.add_tool_call(tool_calls)
            for call in tool_calls:
                result = self._execute_tool(call)
                self.memory.add_tool_result(call["id"], result)
            continue  # Let LLM process tool results

        # No tool calls — final response
        self.memory.add_assistant(response)
        return self._process_response(response)
```

**Methods to add to BaseAgent:**

```python
def _extract_tool_calls(self, response: Any) -> list[dict[str, Any]]:
    """Extract tool calls from LLM response, if any. Returns [] for text responses."""

def _execute_tool(self, tool_call: dict[str, Any]) -> str:
    """
    Execute a single tool call and return result as string.

    Handles:
        - Tool not found → returns error string (does not raise)
        - Tool execution error → returns error string with details
    """
    tool_name = tool_call["function"]["name"]
    arguments = tool_call["function"]["arguments"]
    try:
        result = self.tools.execute(tool_name, arguments)
        return str(result)
    except KeyError:
        return f"Error: tool '{tool_name}' not registered."
    except Exception as e:
        return f"Error executing '{tool_name}': {e}"

def register_tool(self, name: str, func, *, description: str, parameters_schema: dict) -> None:
    """Register a tool. Creates ToolRegistry if none provided at init."""
    if self.tools is None:
        self.tools = ToolRegistry()
    self.tools.register(name, func, description=description, parameters_schema=parameters_schema)
```

**Design decisions:**
- Tool errors return error strings, not exceptions — the LLM can handle them gracefully.
- `register_tool()` auto-creates `ToolRegistry` if agent was initialized without one.
- `ConversationMemory.add_tool_call()` and `add_tool_result()` (from Task 4.6) track
  the full tool use history for context.

**Files:**
- Modify `core/agents/base_agent.py`

**Tests:** 8 tests
- `_execute_tool()` returns correct result for valid tool
- `_execute_tool()` returns error string for unregistered tool (no exception)
- `_execute_tool()` returns error string when tool raises exception (no exception)
- `register_tool()` creates `ToolRegistry` if `self.tools` is `None`
- Multi-turn tool use: user → tool call → tool result → final answer (mocked provider)
- Memory contains tool call and tool result messages after tool use
- `run()` terminates after max tool rounds (guard against infinite loops)
- Agent with no tools does not call `_extract_tool_calls` loop

---

### Subtask 5.3 — State and memory management

**Goal:** Provide explicit data storage (agent memory) separate from conversation history,
so agents can persist structured data across turns and sessions.

**Distinction:**

| Type | Class | Purpose | Scope |
|------|-------|---------|-------|
| Conversation memory | `ConversationMemory` | LLM context (messages) | Per session |
| Agent data store | `dict` on BaseAgent | Structured business data | Persistent |

**Implementation:**

```python
@dataclass
class BaseAgent(ABC):
    # ... existing fields ...
    _data_store: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def store(self, key: str, value: Any) -> None:
        """Store a value in the agent's data store."""
        self._data_store[key] = value

    def retrieve(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from the agent's data store."""
        return self._data_store.get(key, default)

    def clear_store(self) -> None:
        """Clear all stored data (does not affect conversation memory)."""
        self._data_store.clear()

    def save_state(self, data_lake, *, session_id: str) -> None:
        """Persist both conversation memory and data store."""
        data_lake.save("agent_state", session_id, {
            "agent_name": self.name,
            "memory": self.memory.to_dict(),
            "data_store": self._data_store,
        })

    def load_state(self, data_lake, *, session_id: str) -> None:
        """Restore conversation memory and data store."""
        state = data_lake.load("agent_state", session_id)
        if state:
            self.memory = ConversationMemory.from_dict(state["memory"])
            self._data_store = state.get("data_store", {})
```

**Usage in concrete agents:**

```python
class WelcomeAgent(BaseAgent):
    def _process_response(self, response: str) -> dict:
        result = parse_structured_output(response)
        # Persist extracted data for later retrieval
        self.store("restaurant_name", result.get("restaurant_name"))
        self.store("restaurant_type", result.get("restaurant_type"))
        return result
```

**Design decisions:**
- `store`/`retrieve` is intentionally simple — no namespacing or nested keys.
  Agents are small and self-contained; over-engineering the store is premature.
- `_data_store` is separate from `ConversationMemory` — business data should not
  live in the message list.
- `save_state` persists both; they are restored together to maintain consistency.

**Files:**
- Modify `core/agents/base_agent.py`

**Tests:** 7 tests
- `store()` and `retrieve()` basic round-trip
- `retrieve()` returns default when key not found
- `clear_store()` empties data store but does not affect memory
- `reset_memory()` clears memory but does not affect data store
- `save_state()` persists both memory and data store
- `load_state()` restores both memory and data store
- `load_state()` with missing session_id does nothing (no error)

---

### Subtask 5.4 — Concrete minimal agent

**Goal:** Build a working agent that validates the entire BaseAgent stack against
a realistic use case modeled on what Task 7 (Welcome Agent) will need.

**Why realistic, not generic:**
A `TestAgent` that returns `{"result": "ok"}` only proves the framework compiles.
A minimal welcome agent that captures restaurant name and type from a conversation
proves the framework works for the actual problem it will solve.

**Implementation:**

```python
class RestaurantInfoAgent(BaseAgent):
    """
    Minimal agent that captures basic restaurant information from a conversation.

    Models the core interaction pattern of the full Welcome Agent (Task 7):
    - System prompt establishes role and task
    - User provides info conversationally
    - Agent extracts structured data from unstructured text

    This agent is for framework validation only.
    The full Welcome Agent (Task 7) extends this pattern with emotional support,
    onboarding flow, and notebook integration.
    """

    INPUT_SCHEMA = {
        "user_message": "A message from the restaurant operator describing their restaurant.",
    }

    OUTPUT_SCHEMA = {
        "restaurant_name": "Extracted restaurant name, or None if not mentioned.",
        "restaurant_type": "Extracted restaurant type (e.g. fast-casual, full-service), or None.",
        "raw_response": "Full LLM response before parsing.",
    }

    def _generate_prompt(self, input_data: dict, context: dict) -> tuple[str, str]:
        system = format_system_prompt(
            "You are a restaurant data assistant. "
            "When the operator describes their restaurant, extract: "
            "1) the restaurant name and 2) the restaurant type. "
            "Respond ONLY with a JSON object: "
            '{"restaurant_name": "...", "restaurant_type": "..."}'
        )
        return system, input_data["user_message"]

    def _process_response(self, response: str) -> dict:
        data = parse_structured_output(response)
        return {
            "restaurant_name": data.get("restaurant_name"),
            "restaurant_type": data.get("restaurant_type"),
            "raw_response": response,
        }
```

**Files:**
- Create `core/agents/simple_agent.py`

**Tests:** 5 tests (mocked) + 2 live tests
- Mocked: `run()` returns correct output structure
- Mocked: `run()` with valid `input_data` populates memory
- Mocked: missing required input key raises `ValueError`
- Mocked: malformed LLM response (not JSON) handled gracefully
- Mocked: multi-turn conversation accumulates memory correctly
- Live: real LLM call returns parseable restaurant info (skip if no API key)
- Live: memory preserves context across two turns (skip if no API key)

---

### Subtask 5.5 — Agent utilities, error handling, and recovery

**Goal:** Provide supporting infrastructure: factory, serialization, registry,
and robust error handling so agents can be created, recovered, and managed consistently.

**Agent factory:**

```python
def create_agent(agent_class: type[BaseAgent], *, provider: LlmProvider, **kwargs) -> BaseAgent:
    """
    Factory function for creating agents.

    Args:
        agent_class: A concrete BaseAgent subclass
        provider:    LlmProvider instance to use
        **kwargs:    Additional init args (memory, tools, etc.)

    Returns:
        Initialized agent instance

    Raises:
        TypeError: If agent_class is not a BaseAgent subclass
    """
```

**Agent registry:**

```python
class AgentRegistry:
    """
    Registry for tracking active agent instances by name.

    Useful for workflow engine (Task 6) to look up agents by role.
    """

    def register(self, agent: BaseAgent) -> None: ...
    def get(self, name: str) -> BaseAgent | None: ...
    def list_names(self) -> list[str]: ...
    def clear(self) -> None: ...
```

**Error handling strategy:**

| Error type | Strategy |
|------------|----------|
| Missing required input | Raise `ValueError` immediately (fail fast) |
| LLM API error (rate limit, timeout) | Retry up to 3 times with exponential backoff |
| LLM returns empty response | Raise `RuntimeError` with context |
| Tool not found | Return error string to LLM (do not raise) |
| Tool execution error | Return error string to LLM (do not raise) |
| Malformed structured output | Return `{}` and log warning (caller handles) |
| DataLake error on save/load | Raise — state persistence failure is a hard error |

**Retry with backoff:**

```python
import time

def _generate_with_retry(self, *, max_retries: int = 3, **kwargs) -> str:
    """
    Generate LLM response with exponential backoff on API errors.

    Retries on: rate limit, timeout, service unavailable.
    Does not retry on: auth errors, invalid request errors.
    """
    delay = 1.0
    for attempt in range(max_retries):
        try:
            return self.provider.generate(**kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            if _is_retryable(e):
                time.sleep(delay)
                delay *= 2
            else:
                raise
```

**Files:**
- Create `core/agents/utils.py`
- Modify `core/agents/base_agent.py` (add retry logic)

**Tests:** 9 tests
- `create_agent()` with valid subclass returns correct instance
- `create_agent()` with non-BaseAgent class raises `TypeError`
- `AgentRegistry.register()` and `get()` work correctly
- `AgentRegistry.get()` returns `None` for unknown name
- `AgentRegistry.list_names()` reflects registered agents
- Retry logic retries on retryable error (mocked provider that fails twice then succeeds)
- Retry logic raises after `max_retries` exhausted
- Retry logic does not retry on non-retryable errors (e.g. auth error)
- Empty LLM response raises `RuntimeError`

---

### Subtask 5.6 — Comprehensive tests

**Goal:** Ensure full coverage of the agent framework with unit tests (mocked)
and live integration tests (real API calls, skipped if no key).

**Test file structure:**

```
tests/unit/test_agents.py
    TestBaseAgentValidation           # Input validation, schema enforcement
    TestBaseAgentLifecycle            # run() flow, memory population
    TestBaseAgentToolCalling          # Tool execution loop, error handling
    TestBaseAgentStateManagement      # store/retrieve, save/load state
    TestBaseAgentRetry                # Retry logic with mocked failures
    TestRestaurantInfoAgent           # Concrete agent end-to-end (mocked)
    TestAgentUtils                    # Factory, registry
    TestLiveRestaurantInfoAgent       # Live tests (skip if no API key)
```

**Test count targets:**

| Class | Tests | API calls |
|-------|-------|-----------|
| TestBaseAgentValidation | 5 | 0 |
| TestBaseAgentLifecycle | 8 | 0 |
| TestBaseAgentToolCalling | 8 | 0 |
| TestBaseAgentStateManagement | 7 | 0 |
| TestBaseAgentRetry | 4 | 0 |
| TestRestaurantInfoAgent | 5 | 0 |
| TestAgentUtils | 5 | 0 |
| TestLiveRestaurantInfoAgent | 2 | 2–4 |
| **Total** | **44** | **2–4** |

**Live test cost estimate:**
- 2 live tests × ~500 tokens avg = 1,000 tokens
- Using `TEST_OPENAI_MODEL` or `TEST_ANTHROPIC_MODEL` env vars (same as Task 4.7)
- Cost: ~$0.001 per run

---

### Subtask 5.7 — Documentation

**Goal:** Document the agent framework architecture so future agents (Tasks 7–12)
and the workflow engine (Task 6) can be built consistently.

**Create:** `docs/Architecture/architecture-agent-framework.md`

**Sections:**
1. Overview — what the agent framework provides and where it fits in the stack
2. BaseAgent class — attributes, lifecycle, abstract methods
3. Input/output contract — how schemas are defined and validated
4. Tool calling mechanism — the tool use loop, error handling
5. Memory and state — conversation memory vs. data store, when to use each
6. Error handling — retry strategy, error types, recovery
7. How to implement a concrete agent — step-by-step with code example
8. Integration with Task 6 (workflow engine) — what contracts agents expose
9. Deferred: external framework integration — note about Task 10 and LangGraph

**Files:**
- Create `docs/Architecture/architecture-agent-framework.md`
- Modify `README.md` — add agent framework to architecture table

---

## Integration Points

### With Task 4 (LLM framework) — already complete

```python
# Agents use Task 4 components directly
from core import (
    LlmProvider,       # BaseAgent.provider type
    ConversationMemory, # BaseAgent.memory
    ToolRegistry,       # BaseAgent.tools
    parse_structured_output,  # used in _process_response()
    PromptTemplate,     # used in _generate_prompt()
    DataLake,           # used in save_state() / load_state()
)
```

### With Task 6 (workflow engine) — upcoming

The workflow engine will call `agent.run(input_data=..., context=...)` and read the returned dict.
It relies on:
- `INPUT_SCHEMA` to know what to pass
- `OUTPUT_SCHEMA` to know what to extract and pass to the next step
- `AgentRegistry` to look up agents by name

Agents must not break this contract.

### With Tasks 7–12 (specific agents)

Each notebook agent extends `BaseAgent`:

```python
class WelcomeAgent(BaseAgent):
    INPUT_SCHEMA = {"user_message": "..."}
    OUTPUT_SCHEMA = {"restaurant_name": "...", "restaurant_type": "...", ...}

    def _generate_prompt(self, input_data, context) -> tuple[str, str]: ...
    def _process_response(self, response) -> dict: ...
```

They inherit: `run()`, `_validate_input()`, `_execute_tool()`, `store()`/`retrieve()`,
`reset_memory()`, `save_state()`/`load_state()`, retry logic.
They implement: `_generate_prompt()`, `_process_response()`, `INPUT_SCHEMA`, `OUTPUT_SCHEMA`.

---

## Edge Cases

| Case | Behavior |
|------|----------|
| Missing required input key | `ValueError` raised before any API call |
| Empty `INPUT_SCHEMA` | All inputs accepted (no validation) |
| `tools=None` and LLM requests tool call | Error string returned; loop terminates |
| Tool execution raises unexpected exception | Error string captured; LLM continues |
| LLM returns empty string | `RuntimeError` raised |
| LLM returns non-JSON when structured output expected | `{}` returned; caller handles |
| `max_retries` exceeded | Final exception propagates to caller |
| Non-retryable error (auth, bad request) | Exception propagates immediately |
| `load_state()` with missing session_id | No-op (state unchanged) |
| `AgentRegistry.get()` for unknown name | Returns `None` |
| Infinite tool use loop | Guard: raise `RuntimeError` after 10 tool rounds |

---

## Deliverable Checklist

### Subtask 5.1 — BaseAgent
- [ ] Create `core/agents/__init__.py`
- [ ] Create `core/agents/base_agent.py`
- [ ] `BaseAgent` dataclass with `name`, `provider`, `memory`, `tools`
- [ ] `run()` orchestrates full lifecycle (keyword-only args)
- [ ] `_generate_prompt()` abstract method
- [ ] `_process_response()` abstract method
- [ ] `_validate_input()` checks `INPUT_SCHEMA` keys
- [ ] `reset_memory()` clears conversation memory
- [ ] `save_state()` / `load_state()` via DataLake
- [ ] `INPUT_SCHEMA` and `OUTPUT_SCHEMA` class attributes

### Subtask 5.2 — Tool calling
- [ ] Tool use loop in `run()`
- [ ] `_extract_tool_calls()` parses tool calls from response
- [ ] `_execute_tool()` runs tool and returns string result
- [ ] Tool errors return error strings (no exceptions propagated)
- [ ] `register_tool()` auto-creates `ToolRegistry` if needed
- [ ] Guard against infinite tool use loop (max 10 rounds)

### Subtask 5.3 — State and memory
- [ ] `_data_store` dict on BaseAgent
- [ ] `store(key, value)` and `retrieve(key, default)` methods
- [ ] `clear_store()` clears data store only
- [ ] `save_state()` persists both memory and data store
- [ ] `load_state()` restores both memory and data store

### Subtask 5.4 — Concrete agent
- [ ] Create `core/agents/simple_agent.py`
- [ ] `RestaurantInfoAgent` with `INPUT_SCHEMA`, `OUTPUT_SCHEMA`
- [ ] `_generate_prompt()` returns (system, user) tuple
- [ ] `_process_response()` parses JSON and returns output dict

### Subtask 5.5 — Utilities and error handling
- [ ] Create `core/agents/utils.py`
- [ ] `create_agent()` factory function
- [ ] `AgentRegistry` with `register()`, `get()`, `list_names()`, `clear()`
- [ ] `_generate_with_retry()` with exponential backoff
- [ ] Retry on retryable errors; propagate immediately on others
- [ ] Empty response raises `RuntimeError`

### Subtask 5.6 — Tests
- [ ] Create `tests/unit/test_agents.py`
- [ ] 42 unit tests (mocked)
- [ ] 2 live tests (skip if no API key)
- [ ] All tests pass: `python -m pytest tests/unit/test_agents.py -v`
- [ ] Full suite still passes: `python -m pytest tests/unit/ -v`

### Subtask 5.7 — Documentation
- [ ] Create `docs/Architecture/architecture-agent-framework.md`
- [ ] Update `README.md` architecture table
- [ ] Export `BaseAgent`, `RestaurantInfoAgent`, `AgentRegistry`, `create_agent` from `core/__init__.py`

---

## Success Criteria

Task 5 is complete when:

1. `BaseAgent` is implemented with all abstract methods, input/output contracts,
   tool calling loop, state management, and retry logic.
2. `RestaurantInfoAgent` demonstrates the framework against a realistic use case.
3. `AgentRegistry` and `create_agent()` factory are available for Task 6.
4. All 44 tests pass (42 unit + 2 live).
5. Architecture documentation covers the full framework and integration points.
6. `BaseAgent`, `AgentRegistry`, `create_agent`, `RestaurantInfoAgent` are exported
   from `core/__init__.py`.
7. Task 6 (workflow engine) can import agents and call `run()` without changes to this layer.

---

## Risks and Open Questions

### [OPEN] — `_generate_with_retry()` type annotation imprecise for `max_retries=0`
**Source:** Validation of subtask 5.6
**Problem:** `_generate_with_retry()` in `core/agents/base_agent.py` is annotated `-> str` but implicitly returns `None` when called with `max_retries=0` (the `for` loop over `range(0)` never executes). The call site always uses the default of 3, so this is not a runtime risk today — but the annotation is technically incorrect.
**Impact:** Type checkers (mypy/pyright) will not catch callers passing `max_retries=0`. If such a call were made, `None` would propagate silently to `_generate_response()` and raise a confusing `AttributeError` instead of a clear, traceable error.
**Suggested action:** In subtask 5.7, add a note to the architecture doc under "Error handling — edge cases". Optionally add a one-line guard `if max_retries < 1: raise ValueError("max_retries must be >= 1")` to `base_agent.py` as a small defensive fix.

### [OPEN] — README test coverage table row arithmetic gap
**Source:** Validation of subtask 5.7
**Problem:** README test coverage table rows currently sum to 404 (88+54+18+42+42+70+29+8+7+33+13), but Total shows 407 — a pre-existing 3-test gap. After subtask 5.7 adds the agent framework row (55), rows sum to 459 while Total becomes 462 — the same 3-test gap persists unchanged.
**Impact:** An implementer who verifies the addition will see rows sum to 459 ≠ 462. A future maintainer adding more rows may propagate the error further.
**Suggested action:** When any later task updates the README, identify the 3 uncounted tests (likely in a file not listed in the table) and reconcile the row entries.

---

## Note on External Frameworks (LangGraph, CrewAI, LangChain, Autogen)

External framework integration is **not in scope for Task 5**.

The first concrete use case is **Task 10 (Alignment Agent)**: a user uploads a PDF, Excel, or
image file and multiple agents collaborate to extract, normalize, and classify the data.
That workflow — cyclic, conditional, multi-agent with shared state — maps well to **LangGraph**.

When writing the Task 10 plan, evaluate LangGraph for orchestrating the file processing
multi-agent workflow. At that point the requirements are concrete and the right tool can be
chosen with confidence. Introducing adapters now — before any agent needs them — would be
premature abstraction.

`BaseAgent`'s clean, composable interface (simple dataclass, `run()` returns a dict)
is easy to wrap with any framework later without breaking changes.
