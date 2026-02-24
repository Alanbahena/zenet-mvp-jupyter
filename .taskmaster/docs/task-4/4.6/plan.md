# Implementation plan: Subtask 4.6 — Conversation memory

## Goal

Create an in-memory conversation history manager that tracks user/assistant messages for multi-turn LLM interactions. Enables chatbots, conversational agents, and context-aware responses.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `ConversationMemory` class with add/get/clear methods | Persistent storage (deferred to Task 5) |
| Message truncation by count (`max_turns`) | Token-based truncation (requires tiktoken/tokenizer) |
| Serialization via `to_dict()` / `from_dict()` | Automatic summarization of old messages |
| In-memory storage only | Database or file-based persistence |
| Simple append-only message list | Message editing or deletion |
| Compatible with OpenAI/Anthropic formats | Streaming support |
| **Tool use support** (add_tool_call, add_tool_result) | Message validation (defer to callers) |
| **Convenience methods** (message_count, get_recent) | Conversation metadata (IDs, timestamps) |

---

## Dependencies

- **Task 4.1** — LlmProvider base, OpenAiProvider (done) — `generate()` accepts `messages` param
- **Task 4.2** — ClaudeProvider (done)
- **Task 4.3** — ToolRegistry (done)
- **Task 4.4** — Structured output parsing (done)
- **Task 4.5** — Prompt utilities (done)
- **External:** None (stdlib only)

---

## Files to Create / Modify

- **Create:** `core/memory.py` — new file for conversation memory (or add to `llm_framework.py`)
- **Modify:** `core/__init__.py` — export ConversationMemory
- **Create/Modify:** `tests/unit/test_memory.py` — new test file (or add to `test_llm_framework.py`)

---

## File Location Decision

**Option A:** Add to `core/llm_framework.py`
- ✅ Keeps all LLM utilities together
- ❌ File is already ~400 lines

**Option B:** Create `core/memory.py`
- ✅ Cleaner separation of concerns
- ✅ Can grow independently
- ✅ Easier to test in isolation

**Recommendation:** **Option B** (`core/memory.py`) — cleaner and more maintainable.

---

## Implementation Breakdown

### 1. ConversationMemory class

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ConversationMemory:
    """
    In-memory conversation history for multi-turn LLM interactions.

    Automatically truncates to keep the most recent `max_turns` messages.
    Messages are stored in OpenAI/Anthropic format:
    [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

    Attributes:
        max_turns: Maximum number of messages to keep (default 20)

    Example:
        >>> memory = ConversationMemory(max_turns=10)
        >>> memory.add_user("Hello")
        >>> memory.add_assistant("Hi there!")
        >>> messages = memory.get_messages()
        >>> messages
        [{'role': 'user', 'content': 'Hello'}, {'role': 'assistant', 'content': 'Hi there!'}]
    """

    max_turns: int = 20
    _messages: list[dict[str, str]] = field(default_factory=list, init=False, repr=False)

    def add_user(self, message: str) -> None:
        """
        Add a user message to the conversation.

        Args:
            message: The user's message content

        Example:
            >>> memory.add_user("How many fruits do I have?")
        """
        self._messages.append({"role": "user", "content": message})
        self._truncate()

    def add_assistant(self, message: str) -> None:
        """
        Add an assistant message to the conversation.

        Args:
            message: The assistant's response content

        Example:
            >>> memory.add_assistant("You have 50 apples and 30 oranges.")
        """
        self._messages.append({"role": "assistant", "content": message})
        self._truncate()

    def get_messages(self) -> list[dict[str, str]]:
        """
        Get all messages in OpenAI/Anthropic format.

        Returns:
            List of message dicts with 'role' and 'content' keys

        Example:
            >>> messages = memory.get_messages()
            >>> messages[0]
            {'role': 'user', 'content': 'Hello'}
        """
        return self._messages.copy()

    def clear(self) -> None:
        """
        Clear all messages from the conversation.

        Example:
            >>> memory.clear()
            >>> memory.get_messages()
            []
        """
        self._messages.clear()

    def _truncate(self) -> None:
        """
        Truncate messages to keep only the most recent max_turns messages.

        Called automatically after each add operation.
        """
        if len(self._messages) > self.max_turns:
            # Keep only the last max_turns messages
            self._messages = self._messages[-self.max_turns:]

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize conversation to a dictionary.

        Returns:
            Dict with 'messages' and 'max_turns' keys

        Example:
            >>> state = memory.to_dict()
            >>> state
            {'messages': [{'role': 'user', 'content': 'Hello'}], 'max_turns': 20}
        """
        return {
            "messages": self._messages.copy(),
            "max_turns": self.max_turns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationMemory":
        """
        Deserialize conversation from a dictionary.

        Args:
            data: Dict with 'messages' and optionally 'max_turns'

        Returns:
            ConversationMemory instance

        Example:
            >>> state = {'messages': [{'role': 'user', 'content': 'Hi'}], 'max_turns': 10}
            >>> memory = ConversationMemory.from_dict(state)
            >>> memory.max_turns
            10
        """
        max_turns = data.get("max_turns", 20)
        memory = cls(max_turns=max_turns)
        memory._messages = data.get("messages", []).copy()
        return memory
```

**Design decisions:**
- Use `@dataclass` for consistency with project
- `_messages` is private (use methods to modify)
- Automatic truncation on every add (simple, prevents overflow)
- `get_messages()` returns copy (prevents external modification)
- `max_turns` is count of total messages, not turns (turn = 2 messages)

---

### 2. Message format (OpenAI/Anthropic compatible)

```python
# Standard format (both providers accept this)
{
    "role": "user" | "assistant" | "system",
    "content": str
}
```

**Notes:**
- We only store "user" and "assistant" roles (system is passed separately)
- Content is always a string (no complex message types for MVP)
- Compatible with both `OpenAiProvider` and `ClaudeProvider` from 4.1-4.2

---

### 3. Truncation strategy

**Simple count-based truncation:**

```python
def _truncate(self) -> None:
    if len(self._messages) > self.max_turns:
        # Drop oldest messages, keep newest
        self._messages = self._messages[-self.max_turns:]
```

**Why not token-based?**
- Token counting requires provider-specific libraries:
  - OpenAI: `tiktoken` (external dependency)
  - Anthropic: custom tokenizer
- Complex to implement correctly
- Count-based is "good enough" for MVP

**Future enhancement:** Add token-based truncation in later phase when needed.

---

### 4. Tool use support

**Rationale:** Agents in Task 5 will use tools (from ToolRegistry in 4.3). Without tool message support, memory can't track multi-turn conversations involving tool calls.

**Tool call message format:**

```python
# Assistant uses a tool
{
    "role": "assistant",
    "content": None,
    "tool_calls": [
        {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "get_inventory_item",
                "arguments": '{"name": "tomato"}'
            }
        }
    ]
}

# Tool returns result
{
    "role": "tool",
    "tool_call_id": "call_abc123",
    "content": '{"name": "tomato", "quantity": 50, "unit": "kg"}'
}
```

**Implementation:**

```python
def add_tool_call(self, tool_calls: list[dict[str, Any]]) -> None:
    """
    Add an assistant message with tool calls.

    Args:
        tool_calls: List of tool call dicts (OpenAI/Anthropic format)

    Example:
        >>> memory.add_tool_call([{
        ...     "id": "call_abc123",
        ...     "type": "function",
        ...     "function": {
        ...         "name": "get_inventory_item",
        ...         "arguments": '{"name": "tomato"}'
        ...     }
        ... }])
    """
    self._messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": tool_calls
    })
    self._truncate()

def add_tool_result(self, tool_call_id: str, content: str) -> None:
    """
    Add a tool result message.

    Args:
        tool_call_id: ID from the original tool call
        content: Tool result (typically JSON string)

    Example:
        >>> memory.add_tool_result(
        ...     "call_abc123",
        ...     '{"name": "tomato", "quantity": 50, "unit": "kg"}'
        ... )
    """
    self._messages.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content
    })
    self._truncate()
```

**Design notes:**
- Compatible with both OpenAI and Anthropic tool calling formats
- Tool calls are assistant messages with `content=None` and `tool_calls` list
- Tool results reference the original call via `tool_call_id`
- Both methods apply automatic truncation like other add methods

---

### 5. Convenience methods

**Rationale:** Simple utilities that improve API usability and debugging.

**Implementation:**

```python
@property
def message_count(self) -> int:
    """
    Get the total number of messages in memory.

    Returns:
        Number of messages currently stored

    Example:
        >>> memory.message_count
        5
    """
    return len(self._messages)

def get_recent(self, n: int) -> list[dict[str, Any]]:
    """
    Get the N most recent messages.

    Args:
        n: Number of recent messages to return

    Returns:
        List of the last N messages (or all if fewer than N exist)

    Example:
        >>> memory.get_recent(3)  # Get last 3 messages
        [{'role': 'user', 'content': '...'}, ...]
    """
    if n <= 0:
        return []
    return self._messages[-n:].copy()
```

**Design notes:**
- `message_count` is a property (read-only, cleaner than `len(memory.get_messages())`)
- `get_recent(n)` returns copy (like `get_messages()`) to prevent external modification
- Useful for debugging, logging, and context window management

---

### 6. Module docstring and exports

```python
"""
Conversation memory for multi-turn LLM interactions.

Provides ConversationMemory class for tracking user/assistant messages
across multiple turns in a conversation.
"""

from dataclasses import dataclass, field
from typing import Any

__all__ = ["ConversationMemory"]
```

Update `core/__init__.py`:

```python
from core.memory import ConversationMemory

__all__ = [
    # ... existing exports ...
    "ConversationMemory",
]
```

---

## Edge Cases

| Case | Behavior |
|------|----------|
| Empty conversation | `get_messages()` returns `[]` |
| Single message | Valid; returns list with 1 message |
| Exactly `max_turns` messages | No truncation |
| `max_turns + 1` messages | Drops oldest message |
| `max_turns = 0` | Keeps no messages (edge case, allowed) |
| `max_turns = 1` | Keeps only most recent message |
| Clear then add | Works fine; starts fresh |
| Add empty string message | Allowed (caller should validate if needed) |
| Serialize empty memory | `{'messages': [], 'max_turns': 20}` |
| from_dict with missing keys | Uses defaults (`max_turns=20`, `messages=[]`) |
| Only user messages (no assistant) | Valid; user hasn't gotten response yet |
| Only assistant messages (no user) | Technically valid, but unusual |
| Tool call without result | Valid; result may come in next turn |
| Tool result without call | Technically valid, but unusual (orphaned result) |
| Multiple tool calls in one message | Valid; assistant can call multiple tools |
| Truncation splits tool call/result pair | Allowed; caller should use larger `max_turns` if needed |
| get_recent(n) with n > message count | Returns all messages (no error) |
| get_recent(0) or negative | Returns empty list |

---

## Test Strategy

### Basic operations (5 tests)

1. **Instantiation:**
   - Default `max_turns=20`
   - Custom `max_turns`

2. **Add user message:**
   - `add_user()` adds to messages
   - Role is "user"

3. **Add assistant message:**
   - `add_assistant()` adds to messages
   - Role is "assistant"

4. **Get messages:**
   - Returns list of dicts
   - Returns copy (modifying result doesn't affect internal state)

5. **Clear:**
   - Empties messages
   - `get_messages()` returns `[]`

---

### Truncation (5 tests)

6. **No truncation when under limit:**
   - Add 10 messages with `max_turns=20`
   - All 10 present

7. **Truncation when over limit:**
   - Add 25 messages with `max_turns=20`
   - Only last 20 present

8. **Truncation drops oldest:**
   - Add messages "A", "B", "C", "D" with `max_turns=2`
   - Only "C" and "D" present

9. **Exact boundary:**
   - Add exactly `max_turns` messages
   - No truncation

10. **Truncation on every add:**
    - Add messages incrementally past limit
    - Verify oldest dropped each time

---

### Serialization (5 tests)

11. **to_dict() returns correct structure:**
    - Has "messages" and "max_turns" keys
    - "messages" is list of dicts

12. **from_dict() reconstructs memory:**
    - Create from dict
    - Verify max_turns and messages

13. **Round-trip preserves state:**
    - `memory2 = ConversationMemory.from_dict(memory1.to_dict())`
    - `memory2.get_messages() == memory1.get_messages()`

14. **Serialize empty memory:**
    - Empty conversation serializes correctly
    - from_dict creates empty memory

15. **from_dict with missing keys:**
    - Missing "max_turns" → uses default
    - Missing "messages" → empty list

---

### Edge cases (5 tests)

16. **Empty conversation:**
    - New memory has no messages
    - `get_messages()` returns `[]`

17. **Single message:**
    - Add one message
    - Returned correctly

18. **max_turns=0:**
    - Add messages
    - No messages retained (all truncated)

19. **max_turns=1:**
    - Add 3 messages
    - Only last message retained

20. **Alternating user/assistant:**
    - Add user, assistant, user, assistant
    - Verify order preserved

---

### Integration (3 tests)

21. **Use with LlmProvider:**
    - Create memory, add messages
    - Pass to `provider.generate(..., messages=memory.get_messages())`
    - Verify no errors

22. **Multi-turn conversation flow:**
    - Simulate full conversation (add user, get response, add assistant, repeat)
    - Verify context preserved

23. **get_messages() returns copy:**
    - Modify returned list
    - Verify internal state unchanged

---

### Tool use (4 tests)

24. **Tool call storage:**
    - Add tool call message via `add_tool_call()`
    - Verify role is "assistant"
    - Verify `tool_calls` list preserved
    - Verify `content` is None

25. **Tool result storage:**
    - Add tool result via `add_tool_result()`
    - Verify role is "tool"
    - Verify `tool_call_id` links to original call
    - Verify content preserved

26. **Tool call round-trip:**
    - Add user → tool call → tool result → assistant response
    - Verify full conversation flow preserved
    - Verify order maintained

27. **Tool truncation:**
    - Add tool calls beyond max_turns
    - Verify truncation works correctly
    - Verify serialization handles tool messages

---

### Convenience methods (4 tests)

28. **message_count property:**
    - Returns correct count after adds
    - Updates on clear
    - Zero for empty memory

29. **get_recent with valid n:**
    - Returns last N messages
    - Preserves order
    - Returns copy (modification doesn't affect internal state)

30. **get_recent edge cases:**
    - n > total messages returns all
    - n = 0 returns empty list
    - n negative returns empty list

31. **get_recent vs get_messages consistency:**
    - `get_recent(message_count)` equals `get_messages()`
    - Verify both return copies

---

## Integration Points

**Where ConversationMemory will be used:**

### 1. Chat-based agents (Tasks 7-12)

```python
from core import ConversationMemory, PromptTemplate, ClaudeProvider

memory = ConversationMemory()
provider = ClaudeProvider()
template = RESTAURANT_ASSISTANT_CHAT

# Turn 1
user_msg = "How many fruits?"
memory.add_user(user_msg)

system, user = template.render(user_message=user_msg)
response = provider.generate(
    user,
    system=system,
    messages=memory.get_messages()  # ← Provides conversation context
)
memory.add_assistant(response)

# Turn 2
user_msg = "Are any expiring?"
memory.add_user(user_msg)

system, user = template.render(user_message=user_msg)
response = provider.generate(
    user,
    system=system,
    messages=memory.get_messages()  # ← Now includes turn 1!
)
memory.add_assistant(response)
```

---

### 2. Agent with tool use (Task 5)

```python
from core import ConversationMemory, ClaudeProvider, ToolRegistry

memory = ConversationMemory()
provider = ClaudeProvider()
tools = ToolRegistry()

# Register a tool
@tools.register("get_inventory_item")
def get_inventory_item(name: str) -> dict:
    return {"name": name, "quantity": 50, "unit": "kg"}

# User asks question
user_msg = "How many tomatoes do I have?"
memory.add_user(user_msg)

# LLM decides to use tool
response = provider.generate(
    user_msg,
    tools=tools.get_tools(),
    messages=memory.get_messages()
)

# Response includes tool call
tool_calls = response.get("tool_calls", [])
if tool_calls:
    memory.add_tool_call(tool_calls)  # ← Store tool call

    # Execute tool
    for call in tool_calls:
        result = tools.execute(call["function"]["name"], call["function"]["arguments"])
        memory.add_tool_result(call["id"], result)  # ← Store result

    # Get final answer with tool context
    final_response = provider.generate(
        user_msg,
        messages=memory.get_messages()  # ← Includes tool call + result!
    )
    memory.add_assistant(final_response)
```

---

### 3. Workflow engine (Task 6)

```python
# Agent maintains memory across workflow steps
class ConversationalAgent(BaseAgent):
    def __init__(self, llm_provider):
        super().__init__(...)
        self.memory = ConversationMemory()

    def run(self, input_data, context):
        user_msg = input_data["message"]
        self.memory.add_user(user_msg)

        response = self.llm_provider.generate(
            user_msg,
            messages=self.memory.get_messages()
        )

        self.memory.add_assistant(response)
        return response
```

---

### 4. Future persistence (Task 5+)

```python
# Save conversation state
state = memory.to_dict()
data_lake.save("conversation", session_id, state)

# Load conversation state
state = data_lake.load("conversation", session_id)
memory = ConversationMemory.from_dict(state)
```

---

## Deliverable Checklist

- [ ] Create `core/memory.py` with module docstring
- [ ] Implement `ConversationMemory` dataclass
  - [ ] `max_turns` attribute (default 20)
  - [ ] `_messages` private field (list of dicts)
  - [ ] `add_user(message: str) -> None`
  - [ ] `add_assistant(message: str) -> None`
  - [ ] `add_tool_call(tool_calls: list[dict]) -> None` **[NEW]**
  - [ ] `add_tool_result(tool_call_id: str, content: str) -> None` **[NEW]**
  - [ ] `get_messages() -> list[dict[str, Any]]` returns copy
  - [ ] `get_recent(n: int) -> list[dict[str, Any]]` returns copy **[NEW]**
  - [ ] `message_count` property **[NEW]**
  - [ ] `clear() -> None`
  - [ ] `_truncate() -> None` (private, automatic)
  - [ ] `to_dict() -> dict[str, Any]`
  - [ ] `from_dict(cls, data: dict) -> ConversationMemory` classmethod
- [ ] Add comprehensive docstrings with examples
- [ ] Export from `core/__init__.py`
- [ ] Create `tests/unit/test_memory.py`
  - [ ] Test basic operations (add, get, clear) — 5 tests
  - [ ] Test truncation (under/over/exact limit) — 5 tests
  - [ ] Test serialization (to_dict, from_dict, round-trip) — 5 tests
  - [ ] Test edge cases (empty, single, max_turns=0/1) — 5 tests
  - [ ] Test integration (with LlmProvider, multi-turn) — 3 tests
  - [ ] **Test tool use (call, result, round-trip, truncation) — 4 tests [NEW]**
  - [ ] **Test convenience methods (message_count, get_recent) — 4 tests [NEW]**
- [ ] Run tests: `python -m pytest tests/unit/test_memory.py -v`
- [ ] Run full test suite: `python -m pytest tests/unit/ -v`

---

## Notes

- **In-memory only:** Persistence deferred to Task 5 (agents). `to_dict()`/`from_dict()` enable future DataLake integration.
- **No token counting:** Count-based truncation is simpler and sufficient for MVP. Token-based can be added later if needed.
- **Message format:** Uses OpenAI/Anthropic standard (`{"role": "...", "content": "..."}`). Both providers (4.1-4.2) already support this.
- **Tool use support:** Critical for Task 5 agents. Supports tool calls and results using OpenAI/Anthropic format. Agents can use tools from ToolRegistry (4.3) in multi-turn conversations.
- **Automatic truncation:** Happens on every `add_*()` call. Simple and prevents manual truncation errors.
- **Thread safety:** Not addressed in MVP (single-threaded usage assumed). Add locks if needed for multi-threaded agents.
- **Append-only:** No message editing or deletion. Simplifies implementation and prevents bugs.
- **get_messages() returns copy:** Prevents accidental external modification of internal state. Same for `get_recent()`.
- **Empty messages allowed:** Callers should validate if needed; memory doesn't enforce non-empty.
- **Convenience methods:** `message_count` and `get_recent(n)` improve API usability and debugging.
- **Future enhancements (out of scope for 4.6):**
  - Token-based truncation (requires tiktoken/tokenizer)
  - Smart summarization (compress old messages)
  - Message editing/deletion
  - Branching conversations (multiple paths)
  - Message metadata (timestamps, token counts)
  - Selective pruning (keep important messages, drop filler)
  - Persistent storage integration (via DataLake)

---

## Time Estimate

- **Implementation:** 45-60 minutes (dataclass + methods + tool use + convenience)
- **Tests:** 60-75 minutes (31 test cases: 23 original + 4 tool use + 4 convenience)
- **Total:** 2-2.5 hours (was 1.5-2 hours before tool use/convenience additions)
