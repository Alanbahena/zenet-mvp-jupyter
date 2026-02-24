"""
Unit tests for conversation memory (core/memory.py).

Tests cover:
- Basic operations (add, get, clear)
- Truncation (under/over/exact limit)
- Serialization (to_dict, from_dict, round-trip)
- Edge cases (empty, single message, boundary conditions)
- Integration with LLM providers
- Tool use (tool calls and results)
- Convenience methods (message_count, get_recent)
"""

import unittest
from unittest.mock import Mock

from core import ConversationMemory, ClaudeProvider


class TestConversationMemoryBasicOperations(unittest.TestCase):
    """Test basic operations: instantiation, add, get, clear."""

    def test_instantiation_default(self):
        """Test instantiation with default max_turns."""
        memory = ConversationMemory()
        self.assertEqual(memory.max_turns, 20)
        self.assertEqual(len(memory.get_messages()), 0)

    def test_instantiation_custom(self):
        """Test instantiation with custom max_turns."""
        memory = ConversationMemory(max_turns=10)
        self.assertEqual(memory.max_turns, 10)
        self.assertEqual(len(memory.get_messages()), 0)

    def test_add_user_message(self):
        """Test adding a user message."""
        memory = ConversationMemory()
        memory.add_user("Hello")

        messages = memory.get_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "Hello")

    def test_add_assistant_message(self):
        """Test adding an assistant message."""
        memory = ConversationMemory()
        memory.add_assistant("Hi there!")

        messages = memory.get_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "assistant")
        self.assertEqual(messages[0]["content"], "Hi there!")

    def test_get_messages_returns_copy(self):
        """Test that get_messages() returns a copy."""
        memory = ConversationMemory()
        memory.add_user("Hello")

        messages = memory.get_messages()
        messages.append({"role": "hacker", "content": "pwned"})

        # Original should be unchanged
        self.assertEqual(len(memory.get_messages()), 1)
        self.assertEqual(memory.get_messages()[0]["role"], "user")

    def test_clear(self):
        """Test clearing all messages."""
        memory = ConversationMemory()
        memory.add_user("Hello")
        memory.add_assistant("Hi")

        self.assertEqual(len(memory.get_messages()), 2)

        memory.clear()
        self.assertEqual(len(memory.get_messages()), 0)


class TestConversationMemoryTruncation(unittest.TestCase):
    """Test truncation behavior."""

    def test_no_truncation_under_limit(self):
        """Test no truncation when under limit."""
        memory = ConversationMemory(max_turns=20)

        for i in range(10):
            memory.add_user(f"Message {i}")

        self.assertEqual(len(memory.get_messages()), 10)

    def test_truncation_over_limit(self):
        """Test truncation when over limit."""
        memory = ConversationMemory(max_turns=20)

        for i in range(25):
            memory.add_user(f"Message {i}")

        messages = memory.get_messages()
        self.assertEqual(len(messages), 20)
        # First message should be "Message 5" (messages 0-4 dropped)
        self.assertEqual(messages[0]["content"], "Message 5")
        self.assertEqual(messages[-1]["content"], "Message 24")

    def test_truncation_drops_oldest(self):
        """Test that truncation drops oldest messages."""
        memory = ConversationMemory(max_turns=2)

        memory.add_user("A")
        memory.add_user("B")
        memory.add_user("C")
        memory.add_user("D")

        messages = memory.get_messages()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["content"], "C")
        self.assertEqual(messages[1]["content"], "D")

    def test_exact_boundary(self):
        """Test exact boundary (max_turns messages, no truncation)."""
        memory = ConversationMemory(max_turns=5)

        for i in range(5):
            memory.add_user(f"Message {i}")

        messages = memory.get_messages()
        self.assertEqual(len(messages), 5)
        self.assertEqual(messages[0]["content"], "Message 0")
        self.assertEqual(messages[-1]["content"], "Message 4")

    def test_truncation_on_every_add(self):
        """Test truncation happens on every add."""
        memory = ConversationMemory(max_turns=3)

        memory.add_user("A")
        self.assertEqual(len(memory.get_messages()), 1)

        memory.add_user("B")
        self.assertEqual(len(memory.get_messages()), 2)

        memory.add_user("C")
        self.assertEqual(len(memory.get_messages()), 3)

        memory.add_user("D")
        self.assertEqual(len(memory.get_messages()), 3)
        messages = memory.get_messages()
        self.assertEqual(messages[0]["content"], "B")


class TestConversationMemorySerialization(unittest.TestCase):
    """Test serialization: to_dict, from_dict, round-trip."""

    def test_to_dict_structure(self):
        """Test to_dict() returns correct structure."""
        memory = ConversationMemory(max_turns=10)
        memory.add_user("Hello")
        memory.add_assistant("Hi")

        state = memory.to_dict()

        self.assertIn("messages", state)
        self.assertIn("max_turns", state)
        self.assertEqual(state["max_turns"], 10)
        self.assertEqual(len(state["messages"]), 2)
        self.assertIsInstance(state["messages"], list)

    def test_from_dict_reconstruction(self):
        """Test from_dict() reconstructs memory."""
        state = {
            "max_turns": 15,
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"}
            ]
        }

        memory = ConversationMemory.from_dict(state)

        self.assertEqual(memory.max_turns, 15)
        messages = memory.get_messages()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")

    def test_round_trip_preserves_state(self):
        """Test round-trip (to_dict → from_dict) preserves state."""
        memory1 = ConversationMemory(max_turns=12)
        memory1.add_user("Question 1")
        memory1.add_assistant("Answer 1")
        memory1.add_user("Question 2")

        state = memory1.to_dict()
        memory2 = ConversationMemory.from_dict(state)

        self.assertEqual(memory2.max_turns, memory1.max_turns)
        self.assertEqual(memory2.get_messages(), memory1.get_messages())

    def test_serialize_empty_memory(self):
        """Test serializing empty memory."""
        memory = ConversationMemory()
        state = memory.to_dict()

        self.assertEqual(state["messages"], [])
        self.assertEqual(state["max_turns"], 20)

        # Deserialize empty
        memory2 = ConversationMemory.from_dict(state)
        self.assertEqual(len(memory2.get_messages()), 0)

    def test_from_dict_missing_keys(self):
        """Test from_dict() with missing keys uses defaults."""
        # Missing max_turns
        state1 = {"messages": [{"role": "user", "content": "Hi"}]}
        memory1 = ConversationMemory.from_dict(state1)
        self.assertEqual(memory1.max_turns, 20)  # Default
        self.assertEqual(len(memory1.get_messages()), 1)

        # Missing messages
        state2 = {"max_turns": 10}
        memory2 = ConversationMemory.from_dict(state2)
        self.assertEqual(memory2.max_turns, 10)
        self.assertEqual(len(memory2.get_messages()), 0)

        # Both missing
        state3 = {}
        memory3 = ConversationMemory.from_dict(state3)
        self.assertEqual(memory3.max_turns, 20)
        self.assertEqual(len(memory3.get_messages()), 0)


class TestConversationMemoryEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_empty_conversation(self):
        """Test empty conversation."""
        memory = ConversationMemory()
        self.assertEqual(len(memory.get_messages()), 0)
        self.assertEqual(memory.get_messages(), [])

    def test_single_message(self):
        """Test single message."""
        memory = ConversationMemory()
        memory.add_user("Only message")

        messages = memory.get_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "Only message")

    def test_max_turns_zero(self):
        """Test max_turns=0 (no messages retained)."""
        memory = ConversationMemory(max_turns=0)
        memory.add_user("A")
        memory.add_user("B")

        # All messages should be truncated
        self.assertEqual(len(memory.get_messages()), 0)

    def test_max_turns_one(self):
        """Test max_turns=1 (only last message retained)."""
        memory = ConversationMemory(max_turns=1)
        memory.add_user("A")
        memory.add_user("B")
        memory.add_user("C")

        messages = memory.get_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "C")

    def test_alternating_user_assistant(self):
        """Test alternating user/assistant messages preserve order."""
        memory = ConversationMemory()
        memory.add_user("Q1")
        memory.add_assistant("A1")
        memory.add_user("Q2")
        memory.add_assistant("A2")

        messages = memory.get_messages()
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[2]["role"], "user")
        self.assertEqual(messages[3]["role"], "assistant")


class TestConversationMemoryIntegration(unittest.TestCase):
    """Test integration with LLM providers and multi-turn flows."""

    def test_use_with_llm_provider(self):
        """Test using memory with LlmProvider (mock)."""
        memory = ConversationMemory()
        provider = Mock(spec=ClaudeProvider)
        provider.generate.return_value = "Mocked response"

        # Simulate conversation
        memory.add_user("Hello")
        response = provider.generate("Hello", messages=memory.get_messages())
        memory.add_assistant(response)

        messages = memory.get_messages()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["content"], "Hello")
        self.assertEqual(messages[1]["content"], "Mocked response")

        # Verify provider was called with messages
        provider.generate.assert_called_once()
        call_args = provider.generate.call_args
        self.assertIn("messages", call_args.kwargs)

    def test_multi_turn_conversation_flow(self):
        """Test full multi-turn conversation flow."""
        memory = ConversationMemory()

        # Turn 1
        memory.add_user("How many apples?")
        memory.add_assistant("You have 50 apples.")

        # Turn 2
        memory.add_user("Are any expiring?")
        memory.add_assistant("Yes, 10 are expiring this week.")

        # Turn 3
        memory.add_user("Create a purchase order")
        memory.add_assistant("Purchase order created.")

        messages = memory.get_messages()
        self.assertEqual(len(messages), 6)

        # Verify context preserved
        self.assertEqual(messages[0]["content"], "How many apples?")
        self.assertEqual(messages[2]["content"], "Are any expiring?")
        self.assertEqual(messages[4]["content"], "Create a purchase order")

    def test_get_messages_copy_independence(self):
        """Test that modifying returned messages doesn't affect internal state."""
        memory = ConversationMemory()
        memory.add_user("Original")

        messages = memory.get_messages()
        messages[0]["content"] = "Modified"
        messages.append({"role": "evil", "content": "Injected"})

        # Internal state should be unchanged
        internal = memory.get_messages()
        self.assertEqual(len(internal), 1)
        self.assertEqual(internal[0]["content"], "Original")


class TestConversationMemoryToolUse(unittest.TestCase):
    """Test tool use support (tool calls and results)."""

    def test_tool_call_storage(self):
        """Test adding tool call message."""
        memory = ConversationMemory()

        tool_calls = [{
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "get_inventory_item",
                "arguments": '{"name": "tomato"}'
            }
        }]

        memory.add_tool_call(tool_calls)

        messages = memory.get_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "assistant")
        self.assertIsNone(messages[0]["content"])
        self.assertEqual(messages[0]["tool_calls"], tool_calls)

    def test_tool_result_storage(self):
        """Test adding tool result message."""
        memory = ConversationMemory()

        memory.add_tool_result(
            "call_abc123",
            '{"name": "tomato", "quantity": 50, "unit": "kg"}'
        )

        messages = memory.get_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "tool")
        self.assertEqual(messages[0]["tool_call_id"], "call_abc123")
        self.assertEqual(messages[0]["content"], '{"name": "tomato", "quantity": 50, "unit": "kg"}')

    def test_tool_call_round_trip(self):
        """Test full tool call flow: user → tool call → result → assistant."""
        memory = ConversationMemory()

        # User asks question
        memory.add_user("How many tomatoes?")

        # Assistant decides to use tool
        memory.add_tool_call([{
            "id": "call_123",
            "type": "function",
            "function": {"name": "get_inventory", "arguments": '{"item": "tomato"}'}
        }])

        # Tool returns result
        memory.add_tool_result("call_123", '{"quantity": 50, "unit": "kg"}')

        # Assistant synthesizes answer
        memory.add_assistant("You have 50 kg of tomatoes.")

        messages = memory.get_messages()
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertIsNone(messages[1]["content"])
        self.assertEqual(messages[2]["role"], "tool")
        self.assertEqual(messages[3]["role"], "assistant")
        self.assertEqual(messages[3]["content"], "You have 50 kg of tomatoes.")

    def test_tool_truncation_and_serialization(self):
        """Test that truncation and serialization handle tool messages."""
        memory = ConversationMemory(max_turns=3)

        memory.add_user("Q1")
        memory.add_tool_call([{"id": "call_1", "type": "function", "function": {"name": "f1", "arguments": "{}"}}])
        memory.add_tool_result("call_1", '{"result": "ok"}')
        memory.add_user("Q2")  # This should trigger truncation

        messages = memory.get_messages()
        self.assertEqual(len(messages), 3)
        # First message (Q1) should be dropped
        self.assertEqual(messages[0]["role"], "assistant")  # tool call
        self.assertEqual(messages[1]["role"], "tool")       # tool result
        self.assertEqual(messages[2]["role"], "user")       # Q2

        # Test serialization preserves tool messages
        state = memory.to_dict()
        memory2 = ConversationMemory.from_dict(state)
        self.assertEqual(memory2.get_messages(), messages)


class TestConversationMemoryConvenienceMethods(unittest.TestCase):
    """Test convenience methods: message_count, get_recent."""

    def test_message_count_property(self):
        """Test message_count property."""
        memory = ConversationMemory()

        self.assertEqual(memory.message_count, 0)

        memory.add_user("Hello")
        self.assertEqual(memory.message_count, 1)

        memory.add_assistant("Hi")
        self.assertEqual(memory.message_count, 2)

        memory.clear()
        self.assertEqual(memory.message_count, 0)

    def test_get_recent_valid_n(self):
        """Test get_recent() with valid n."""
        memory = ConversationMemory()

        for i in range(10):
            memory.add_user(f"Message {i}")

        recent = memory.get_recent(3)
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[0]["content"], "Message 7")
        self.assertEqual(recent[1]["content"], "Message 8")
        self.assertEqual(recent[2]["content"], "Message 9")

        # Verify order preserved
        self.assertEqual(recent[0]["content"], "Message 7")

    def test_get_recent_edge_cases(self):
        """Test get_recent() edge cases."""
        memory = ConversationMemory()
        memory.add_user("A")
        memory.add_user("B")
        memory.add_user("C")

        # n > total messages returns all
        recent = memory.get_recent(10)
        self.assertEqual(len(recent), 3)

        # n = 0 returns empty list
        recent = memory.get_recent(0)
        self.assertEqual(len(recent), 0)

        # n negative returns empty list
        recent = memory.get_recent(-5)
        self.assertEqual(len(recent), 0)

    def test_get_recent_returns_copy(self):
        """Test that get_recent() returns a copy."""
        memory = ConversationMemory()
        memory.add_user("Original")

        recent = memory.get_recent(1)
        recent[0]["content"] = "Modified"

        # Internal state should be unchanged
        self.assertEqual(memory.get_messages()[0]["content"], "Original")

    def test_get_recent_consistency_with_get_messages(self):
        """Test get_recent(message_count) equals get_messages()."""
        memory = ConversationMemory()
        memory.add_user("A")
        memory.add_assistant("B")
        memory.add_user("C")

        all_messages = memory.get_messages()
        recent_all = memory.get_recent(memory.message_count)

        self.assertEqual(all_messages, recent_all)


if __name__ == "__main__":
    unittest.main()


# =============================================================================
# Live Integration Test (Subtask 4.7)
# =============================================================================

import os
from core.ai.providers import OpenAiProvider


class TestLiveMemoryWithProvider(unittest.TestCase):
    """
    Live test of ConversationMemory with a real LLM provider.

    Verifies that memory correctly preserves context across multiple
    turns when used with actual API calls.

    Uses OpenAI by default (cheaper than Claude for this test).
    Cost: ~$0.001 per test with gpt-4o-mini.
    """

    def setUp(self):
        """Set up provider and memory for live tests."""
        if os.getenv("OPENAI_API_KEY"):
            test_model = os.getenv("TEST_OPENAI_MODEL", "gpt-4o-mini")
            self.provider = OpenAiProvider(model_name=test_model)
            self.memory = ConversationMemory(max_turns=10)

    @unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OpenAI API key")
    def test_live_memory_context_preservation(self):
        """
        Verify memory preserves context across multiple API calls.

        Turn 1: User provides information
        Turn 2: User asks question requiring context from Turn 1

        Expected: Provider uses memory to answer correctly.
        """
        # Turn 1: Provide information
        user_msg_1 = "My favorite color is blue."
        self.memory.add_user(user_msg_1)

        response_1 = self.provider.generate(prompt=
            user_msg_1,
            messages=self.memory.get_messages(),
            temperature=0
        )
        self.memory.add_assistant(response_1)

        # Turn 2: Ask question requiring context
        user_msg_2 = "What is my favorite color?"
        self.memory.add_user(user_msg_2)

        response_2 = self.provider.generate(
            prompt=None,  # Not used when messages provided
            messages=self.memory.get_messages(),
            temperature=0
        )
        self.memory.add_assistant(response_2)

        # Verify context was preserved
        self.assertIn("blue", response_2.lower())

        # Verify memory contains all messages
        messages = self.memory.get_messages()
        self.assertEqual(len(messages), 4)  # 2 user + 2 assistant
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[2]["role"], "user")
        self.assertEqual(messages[3]["role"], "assistant")
