# Implementation Plan: Subtask 5.3 — State and Memory Management

## Goal

Add a structured data store to `BaseAgent` so agents can persist business data extracted
during a conversation — separate from the LLM message history — and survive session
interruptions via `save_state()` / `load_state()`.

5.1 gave agents `ConversationMemory` (the LLM message list).
5.2 gave agents the tool calling loop.
5.3 gives agents a second, independent storage layer: `_data_store`.

The distinction matters for Task 6 (workflow engine): it reads business outputs from
the data store, not from the raw conversation transcript.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `_data_store` field on `BaseAgent` | Changes to `run()` |
| `store(key, value)` method | Changes to `_generate_response()` |
| `retrieve(key, default)` method | Changes to `ToolRegistry` or `ConversationMemory` |
| `clear_store()` method | `AgentRegistry`, `create_agent()` factory (5.5) |
| Extend `save_state()` to persist data store | Retry / backoff logic (5.5) |
| Extend `load_state()` to restore data store | Concrete agent implementations (5.4) |
| Update docstrings that reference 5.3 | Architecture documentation (5.7) |
| 7 new unit tests | Live tests (5.6) |

---

## Dependencies

All dependencies were introduced in earlier subtasks. Nothing new to install.

| Component | Source | Used for |
|-----------|--------|----------|
| `BaseAgent` | `core/agents/base_agent.py` | Modified in place |
| `ConversationMemory` | `core/ai/memory.py` | Already on `BaseAgent.memory`; untouched |
| `DataLake` | `core/storage/persistence.py` | `save_state()` / `load_state()` backend |

No `uv add` required.

---

## Files to Modify

| Action | File |
|--------|------|
| Modify | `core/agents/base_agent.py` — add `_data_store` field and three methods; extend `save_state()` and `load_state()`; update three docstrings |
| Modify | `tests/unit/test_agents.py` — add 7 new tests to `TestBaseAgentStateManagement` class |

No new files. No changes to `core/__init__.py`.

---

## What is NOT changing

The following methods in `base_agent.py` are untouched in 5.3:

- `run()` — orchestration loop unchanged
- `_generate_response()` — tool loop unchanged (note already in its docstring: "Subtask 5.3 does not change this method.")
- `_execute_tool()` — unchanged
- `register_tool()` — unchanged
- `_validate_input()` — unchanged
- `_parse_response()` — unchanged
- `reset_memory()` — logic unchanged; only its docstring is updated (see Step 3)

---

## Implementation Steps

### Step 1: Add `_data_store` field to `BaseAgent`

Add as the last field in the dataclass, after `tools`:

```python
_data_store: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
```

**Field placement:**
Python dataclasses require fields with defaults to come after fields without defaults.
The field order in `BaseAgent` is:

```
name: str                          # required (no default) — position 1
provider: LlmProvider              # required (no default) — position 2
memory: ConversationMemory         # optional (default_factory) — position 3
tools: ToolRegistry | None         # optional (default None) — position 4
_data_store: dict[str, Any]        # internal (default_factory) — position 5  <-- NEW
```

`_data_store` is placed last because it is internal state, not a constructor argument.

**`init=False`:**
Callers never pass `_data_store` at construction time. It is always initialized to an
empty dict. If `init=False` were omitted, the dataclass would expose it as a constructor
parameter, which is incorrect.

**`repr=False`:**
The data store accumulates extracted business data across conversation turns and can grow
large. Excluding it from `repr()` keeps `print(agent)` and debug output readable.
`ConversationMemory` is similarly verbose and would also merit `repr=False` if it were
a plain dict; it is excluded from repr via its own class definition.

---

### Step 2: Add `store()`, `retrieve()`, and `clear_store()` methods

Add after `reset_memory()` and before `save_state()`:

```python
def store(self, key: str, value: Any) -> None:
    """
    Store a value in the agent's data store.

    The data store holds structured business data extracted during the conversation
    (e.g. restaurant name, operator concerns). It is separate from conversation memory
    and is persisted by save_state() alongside the message history.

    Args:
        key:   String key. Overwrites existing value if key already exists.
        value: Any Python value. No type constraint — store what the agent extracts.
    """
    self._data_store[key] = value

def retrieve(self, key: str, default: Any = None) -> Any:
    """
    Retrieve a value from the agent's data store.

    Args:
        key:     Key to look up.
        default: Value returned when key is not present. Defaults to None.

    Returns:
        The stored value, or default if key does not exist.
    """
    return self._data_store.get(key, default)

def clear_store(self) -> None:
    """
    Clear all data in the agent's data store.

    Does not affect conversation memory. Use reset_memory() to clear message history.
    Use this to reset collected business data without discarding the conversation.
    """
    self._data_store.clear()
```

**Design decisions:**

- `store`/`retrieve` is a simple key-value interface — no namespacing, no nested keys.
  Agents are small and self-contained; adding complexity here is premature.

- `retrieve()` matches `dict.get()` semantics exactly: returns `default` (not `None`)
  when the key is absent. Callers can distinguish "not found" from "found with value None"
  by passing a sentinel as `default`.

- `clear_store()` clears only the data store. `reset_memory()` clears only conversation
  memory. Neither touches the other. This symmetry is intentional and should be preserved.

---

### Step 3: Update `reset_memory()` docstring

The existing docstring already references 5.3 as a future subtask. Update it to present
tense now that 5.3 is implemented:

**Before:**
```python
def reset_memory(self) -> None:
    """
    Clear conversation history.

    Does not affect the agent data store (subtask 5.3).
    ...
    """
```

**After:**
```python
def reset_memory(self) -> None:
    """
    Clear conversation history.

    Does not affect the agent data store. Use clear_store() to reset stored data.
    Use this to start a fresh conversation without creating a new agent instance.
    """
```

---

### Step 4: Extend `save_state()` to persist the data store

**Before (5.1 implementation):**
```python
def save_state(self, data_lake: DataLake, *, session_id: str) -> None:
    """
    Persist conversation memory to DataLake.

    Subtask 5.3 extends this to also persist the agent data store.
    ...
    """
    data_lake.save_entity("agent_state", session_id, {
        "agent_name": self.name,
        "memory": self.memory.to_dict(),
    })
```

**After:**
```python
def save_state(self, data_lake: DataLake, *, session_id: str) -> None:
    """
    Persist conversation memory and data store to DataLake.

    Both are saved together under the same session_id. Call load_state() with
    the same session_id and DataLake instance to restore both.

    Args:
        data_lake:  DataLake instance for storage.
        session_id: Unique session identifier. Must be unique per agent instance
                    to avoid key collisions in multi-agent workflows.
    """
    data_lake.save_entity("agent_state", session_id, {
        "agent_name": self.name,
        "memory": self.memory.to_dict(),
        "data_store": self._data_store,
    })
```

---

### Step 5: Extend `load_state()` to restore the data store

**Before (5.1 implementation):**
```python
def load_state(self, data_lake: DataLake, *, session_id: str) -> None:
    """
    Restore conversation memory from DataLake.

    No-op if session_id does not exist in storage — agent state is unchanged.
    Subtask 5.3 extends this to also restore the agent data store.
    ...
    """
    state = data_lake.load_entity("agent_state", session_id)
    if state:
        self.memory = ConversationMemory.from_dict(state["memory"])
```

**After:**
```python
def load_state(self, data_lake: DataLake, *, session_id: str) -> None:
    """
    Restore conversation memory and data store from DataLake.

    No-op if session_id does not exist in storage — agent state is unchanged.
    Memory and data store are always restored together to maintain consistency.

    Args:
        data_lake:  DataLake instance for storage.
        session_id: Session identifier used when save_state() was called.
    """
    state = data_lake.load_entity("agent_state", session_id)
    if state:
        self.memory = ConversationMemory.from_dict(state["memory"])
        self._data_store = state.get("data_store", {})
```

**Backwards compatibility:**
`state.get("data_store", {})` is required. Sessions saved before 5.3 do not have a
`data_store` key in their stored dict. The fallback to `{}` prevents `KeyError` when
loading old sessions. This is the only backwards-compatibility concern in this subtask.

---

## Usage in Concrete Agents

The data store is typically written in `_process_response()` after extracting structured
data from the LLM response, and read later (in subsequent turns or by the workflow engine):

```python
class WelcomeAgent(BaseAgent):
    INPUT_SCHEMA  = {"user_message": "Message from the restaurant operator."}
    OUTPUT_SCHEMA = {"restaurant_name": "Extracted name.", "restaurant_type": "Extracted type."}

    def _process_response(self, response: str) -> dict:
        data = self._parse_response(response)
        # Persist extracted data for later retrieval
        self.store("restaurant_name", data.get("restaurant_name"))
        self.store("restaurant_type", data.get("restaurant_type"))
        return {
            "restaurant_name": data.get("restaurant_name"),
            "restaurant_type": data.get("restaurant_type"),
        }

# Later, in a multi-turn session:
name = agent.retrieve("restaurant_name")           # value from first turn
agent.save_state(data_lake, session_id="sess_001") # persists both memory + store
```

---

## Edge Cases

| Case | Behavior |
|------|----------|
| `store()` called twice with the same key | Second value overwrites the first |
| `retrieve()` with a key that does not exist | Returns `default` (default is `None`) |
| `retrieve()` with an explicit `default` sentinel | Returns that sentinel, not `None` |
| `clear_store()` called on an already-empty store | No-op; no error |
| `reset_memory()` called after `store()` | Memory is cleared; data store is unchanged |
| `clear_store()` called after `memory.add_user()` | Data store is cleared; memory is unchanged |
| `save_state()` then `load_state()` on a new agent instance | Both memory and data store match original |
| `load_state()` with an unknown `session_id` | No-op; memory and data store unchanged |
| `load_state()` on a session saved before 5.3 (no `data_store` key) | `_data_store` defaults to `{}`; no error |
| `_data_store` contains non-serializable objects | `data_lake.save_entity()` will raise; caller's responsibility to store serializable values |

---

## Test Strategy

All 7 tests are added to a new `TestBaseAgentStateManagement` class in
`tests/unit/test_agents.py`. All are mocked — no API calls.

The existing `_ConcreteAgent` and `_MockProvider` fixtures from 5.1 are reused.
For `save_state()` / `load_state()` tests, use an in-memory `JsonStorage` backend
with a `tempfile.TemporaryDirectory()` — consistent with how 5.1 tests state persistence.

### 7 Tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `store()` and `retrieve()` basic round-trip | Value stored is the value returned |
| 2 | `retrieve()` with missing key returns `None` by default | Default is `None` when not specified |
| 3 | `retrieve()` with missing key returns explicit `default` | `retrieve("x", "fallback")` → `"fallback"` |
| 4 | `clear_store()` empties the data store; memory is unchanged | Store is cleared; memory messages still present |
| 5 | `reset_memory()` clears memory; data store is unchanged | Memory is empty; previously stored value still retrievable |
| 6 | `save_state()` and `load_state()` round-trip preserves both memory and data store | Full persistence end-to-end |
| 7 | `load_state()` with unknown `session_id` is a no-op | Agent state unchanged; no exception raised |

---

### Test Details

**Test 1 — `store()` / `retrieve()` round-trip:**
```python
agent.store("restaurant_name", "La Palapa")
assert agent.retrieve("restaurant_name") == "La Palapa"
```

**Test 2 — `retrieve()` returns `None` for missing key:**
```python
assert agent.retrieve("nonexistent_key") is None
```

**Test 3 — `retrieve()` returns explicit default for missing key:**
```python
assert agent.retrieve("nonexistent_key", "fallback") == "fallback"
```

**Test 4 — `clear_store()` clears store but not memory:**
```python
agent.memory.add_user("hello")
agent.store("restaurant_name", "La Palapa")
agent.clear_store()
assert agent.retrieve("restaurant_name") is None        # store cleared
assert len(agent.memory.get_messages()) == 1            # memory untouched
```

**Test 5 — `reset_memory()` clears memory but not store:**
```python
agent.memory.add_user("hello")
agent.store("restaurant_name", "La Palapa")
agent.reset_memory()
assert agent.retrieve("restaurant_name") == "La Palapa" # store untouched
assert len(agent.memory.get_messages()) == 0            # memory cleared
```

**Test 6 — `save_state()` / `load_state()` round-trip:**
```python
import tempfile
from core.storage.persistence import JsonStorage, DataLake

with tempfile.TemporaryDirectory() as tmp:
    dl = DataLake(JsonStorage(tmp))

    # Populate original agent
    agent.memory.add_user("hello")
    agent.memory.add_assistant("world")
    agent.store("restaurant_name", "La Palapa")
    agent.store("restaurant_type", "casual")
    agent.save_state(dl, session_id="test_session")

    # Create a fresh agent and restore state
    fresh = _ConcreteAgent(name="test", provider=_MockProvider())
    fresh.load_state(dl, session_id="test_session")

    # Assert both are restored
    assert fresh.retrieve("restaurant_name") == "La Palapa"
    assert fresh.retrieve("restaurant_type") == "casual"
    messages = fresh.memory.get_messages()
    assert len(messages) == 2
    assert messages[0]["content"] == "hello"
    assert messages[1]["content"] == "world"
```

**Test 7 — `load_state()` with unknown `session_id` is a no-op:**
```python
with tempfile.TemporaryDirectory() as tmp:
    dl = DataLake(JsonStorage(tmp))
    agent.store("key", "value")
    agent.load_state(dl, session_id="does_not_exist")   # no-op
    assert agent.retrieve("key") == "value"             # store unchanged
    assert len(agent.memory.get_messages()) == 0        # memory unchanged
```

---

## Deliverable Checklist

### `core/agents/base_agent.py`
- [ ] `_data_store: dict[str, Any] = field(default_factory=dict, init=False, repr=False)` added as last field
- [ ] `store(key, value)` method added after `reset_memory()`
- [ ] `retrieve(key, default=None)` method added after `store()`
- [ ] `clear_store()` method added after `retrieve()`
- [ ] `reset_memory()` docstring updated — removes "subtask 5.3" forward reference
- [ ] `save_state()` extended to persist `_data_store`; docstring updated
- [ ] `load_state()` extended to restore `_data_store` with `state.get("data_store", {})`; docstring updated

### `tests/unit/test_agents.py`
- [ ] `TestBaseAgentStateManagement` class added
- [ ] 7 tests implemented and passing
- [ ] All 7 pass: `python -m pytest tests/unit/test_agents.py::TestBaseAgentStateManagement -v`
- [ ] All prior tests still pass: `python -m pytest tests/unit/test_agents.py -v`
- [ ] Full suite still passes: `python -m pytest tests/unit/ -v`

---

## Notes

- **No changes to `run()` or `_generate_response()`:** 5.3 is purely additive. The tool
  loop (5.2) and the lifecycle orchestration (5.1) are not touched. All 29 existing tests
  (11 from 5.1 + 8 from 5.2 + 10 from other modules) continue to pass unchanged.

- **`_data_store` is not exposed in `repr()`:** The `repr=False` flag is set intentionally.
  Agents will accumulate multiple extracted fields over a session; including them in repr
  would make debug output unreadable.

- **Store only serializable values:** `save_state()` delegates to `DataLake.save_entity()`,
  which serializes to JSON. Storing non-serializable objects (e.g. dataclass instances,
  custom objects) will cause a `TypeError` at save time. Agents should convert extracted
  entities to dicts before storing if persistence is needed.

- **Memory and data store are always saved and loaded together:** They are stored in a
  single dict under the same `session_id`. Loading one without the other is not supported.
  This simplifies the API and avoids partial-restore inconsistencies.

- **`save_entity()` not `save()`:** The existing 5.1 implementation uses
  `data_lake.save_entity()` (as confirmed in the current `base_agent.py`). The `save()`
  name shown in the Task 5 overview plan is outdated. Use `save_entity()` and
  `load_entity()` consistently.

- **Subtask 5.4** builds `RestaurantInfoAgent` which will call `self.store()` inside
  `_process_response()`. The 5.3 implementation must be complete before 5.4 is implemented.

- **Subtask 5.5** adds retry logic by wrapping the provider call inside
  `_generate_response()`. Neither `_data_store` nor `store()`/`retrieve()` are involved.
