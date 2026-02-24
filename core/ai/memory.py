"""
Conversation memory for multi-turn LLM interactions.

Provides ConversationMemory class for tracking user/assistant messages
across multiple turns in a conversation. Supports tool use for agents
that need to call functions during conversations.
"""

import copy
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ConversationMemory"]


@dataclass
class ConversationMemory:
    """
    In-memory conversation history for multi-turn LLM interactions.

    Automatically truncates to keep the most recent `max_turns` messages.
    Messages are stored in OpenAI/Anthropic format:
    [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

    Supports tool use via `add_tool_call()` and `add_tool_result()` for agents
    that need to call functions during conversations.

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
    _messages: list[dict[str, Any]] = field(default_factory=list, init=False, repr=False)

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

    def get_messages(self) -> list[dict[str, Any]]:
        """
        Get all messages in OpenAI/Anthropic format.

        Returns:
            List of message dicts with 'role' and 'content' keys

        Example:
            >>> messages = memory.get_messages()
            >>> messages[0]
            {'role': 'user', 'content': 'Hello'}
        """
        return copy.deepcopy(self._messages)

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
        return copy.deepcopy(self._messages[-n:])

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
        if self.max_turns == 0:
            # Special case: keep no messages
            self._messages = []
        elif len(self._messages) > self.max_turns:
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
            "messages": copy.deepcopy(self._messages),
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
        memory._messages = copy.deepcopy(data.get("messages", []))
        return memory
