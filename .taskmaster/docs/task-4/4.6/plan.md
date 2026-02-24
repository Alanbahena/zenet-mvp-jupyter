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

### 4. Module docstring and exports

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

### 2. Workflow engine (Task 6)

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

### 3. Future persistence (Task 5+)

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
  - [ ] `get_messages() -> list[dict[str, str]]` returns copy
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
- [ ] Run tests: `python -m pytest tests/unit/test_memory.py -v`
- [ ] Run full test suite: `python -m pytest tests/unit/ -v`

---

## Notes

- **In-memory only:** Persistence deferred to Task 5 (agents). `to_dict()`/`from_dict()` enable future DataLake integration.
- **No token counting:** Count-based truncation is simpler and sufficient for MVP. Token-based can be added later if needed.
- **Message format:** Uses OpenAI/Anthropic standard (`{"role": "...", "content": "..."}`). Both providers (4.1-4.2) already support this.
- **Automatic truncation:** Happens on every `add_*()` call. Simple and prevents manual truncation errors.
- **Thread safety:** Not addressed in MVP (single-threaded usage assumed). Add locks if needed for multi-threaded agents.
- **Append-only:** No message editing or deletion. Simplifies implementation and prevents bugs.
- **get_messages() returns copy:** Prevents accidental external modification of internal state.
- **Empty messages allowed:** Callers should validate if needed; memory doesn't enforce non-empty.
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

- **Implementation:** 30-45 minutes (dataclass + methods)
- **Tests:** 45-60 minutes (23 test cases)
- **Total:** 1.5-2 hours
