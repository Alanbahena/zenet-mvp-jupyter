"""Unit tests for BaseAgent and RestaurantInfoAgent. No API calls -- all LLM calls are mocked."""

import os
import tempfile
import unittest
import unittest.mock
from typing import Any

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent
from core.agents.simple_agent import RestaurantInfoAgent
from core.agents.utils import AgentRegistry, _is_retryable, create_agent
from core.ai.memory import ConversationMemory
from core.ai.providers import ClaudeProvider, LlmProvider, ProviderResponse, ToolRegistry
from core.storage.persistence import DataLake


# ---------------------------------------------------------------------------
# Exception stubs for retry tests
# ---------------------------------------------------------------------------

class RateLimitError(Exception):
    pass


class AuthenticationError(Exception):
    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _MockProvider(LlmProvider):
    """Minimal mock provider for unit testing. No API calls."""

    def __init__(self, response: str = '{"result": "ok"}') -> None:
        super().__init__(model_name="mock")
        self.response = response
        self.last_call_kwargs: dict[str, Any] = {}

    def _do_generate(self, *, prompt, system, tools, structured_output, messages, max_tokens, temperature) -> str:
        self.last_call_kwargs = {
            "prompt": prompt,
            "system": system,
            "tools": tools,
            "structured_output": structured_output,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        return self.response


class _ConcreteAgent(BaseAgent):
    """Minimal concrete agent for testing -- no RESPONSE_MODEL."""

    INPUT_SCHEMA  = {"message": "A message."}
    OUTPUT_SCHEMA = {"reply": "The agent's reply."}

    def _generate_prompt(self, input_data: dict, context: dict) -> tuple[str, str]:
        return "You are a test agent.", input_data["message"]

    def _process_response(self, response: str) -> dict[str, Any]:
        return {"reply": response}


class _AgentResponse(BaseModel):
    reply: str = ""
    confidence: float = 1.0


class _TypedAgent(BaseAgent):
    """Concrete agent with RESPONSE_MODEL for structured output testing."""

    INPUT_SCHEMA   = {"message": "A message."}
    OUTPUT_SCHEMA  = {"reply": "The agent's reply.", "confidence": "Confidence score."}
    RESPONSE_MODEL = _AgentResponse

    def _generate_prompt(self, input_data: dict, context: dict) -> tuple[str, str]:
        return "You are a test agent.", input_data["message"]

    def _process_response(self, response: str) -> dict[str, Any]:
        data = self._parse_response(response)
        return {
            "reply": data.get("reply", ""),
            "confidence": data.get("confidence", 1.0),
        }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBaseAgentInstantiation(unittest.TestCase):
    """Tests 1-4: dataclass construction, ABC enforcement, and field validation."""

    def test_concrete_agent_instantiates(self) -> None:
        """_ConcreteAgent instantiates correctly with name and provider."""
        provider = _MockProvider()
        agent = _ConcreteAgent(name="test-agent", provider=provider)

        self.assertEqual(agent.name, "test-agent")
        self.assertIs(agent.provider, provider)
        self.assertIsInstance(agent.memory, ConversationMemory)
        self.assertIsNone(agent.tools)

    def test_base_agent_direct_instantiation_raises(self) -> None:
        """BaseAgent cannot be instantiated directly -- abstract methods not implemented."""
        provider = _MockProvider()
        with self.assertRaises(TypeError):
            BaseAgent(name="x", provider=provider)  # type: ignore[abstract]

    def test_subclass_missing_abstract_methods_raises(self) -> None:
        """A subclass that omits abstract methods raises TypeError at instantiation."""
        class _Incomplete(BaseAgent):
            pass  # missing _generate_prompt and _process_response

        provider = _MockProvider()
        with self.assertRaises(TypeError):
            _Incomplete(name="x", provider=provider)  # type: ignore[abstract]

    def test_empty_name_raises_value_error(self) -> None:
        """Empty or whitespace-only name raises ValueError in __post_init__."""
        provider = _MockProvider()
        with self.assertRaises(ValueError) as ctx:
            _ConcreteAgent(name="", provider=provider)
        self.assertIn("cannot be empty", str(ctx.exception))

        with self.assertRaises(ValueError):
            _ConcreteAgent(name="   ", provider=provider)


class TestInputValidation(unittest.TestCase):
    """Test 5: _validate_input raises before any API call."""

    def test_missing_schema_key_raises_before_api_call(self) -> None:
        """run() with missing INPUT_SCHEMA key raises ValueError; provider not called."""
        provider = _MockProvider()
        agent = _ConcreteAgent(name="test", provider=provider)

        with self.assertRaises(ValueError) as ctx:
            agent.run(input_data={})  # missing "message"

        self.assertIn("message", str(ctx.exception))
        self.assertIn("test", str(ctx.exception))
        # Provider must not have been called
        self.assertEqual(provider.last_call_kwargs, {})

    def test_extra_keys_accepted_silently(self) -> None:
        """Extra keys beyond INPUT_SCHEMA are silently accepted."""
        provider = _MockProvider(response="hello")
        agent = _ConcreteAgent(name="test", provider=provider)
        result = agent.run(input_data={"message": "hi", "extra_key": "ignored"})
        self.assertEqual(result, {"reply": "hello"})

    def test_empty_schema_accepts_any_input(self) -> None:
        """INPUT_SCHEMA = {} means no validation -- all inputs accepted."""
        class _NoSchemaAgent(BaseAgent):
            INPUT_SCHEMA = {}
            def _generate_prompt(self, i, c): return "sys", "user"
            def _process_response(self, r): return {"done": True}

        provider = _MockProvider(response="ok")
        agent = _NoSchemaAgent(name="test", provider=provider)
        result = agent.run(input_data={})
        self.assertEqual(result, {"done": True})


class TestRunLifecycle(unittest.TestCase):
    """Tests 6-7: run() orchestration and memory population."""

    def setUp(self) -> None:
        self.provider = _MockProvider(response="mock-response")
        self.agent = _ConcreteAgent(name="test", provider=self.provider)

    def test_run_returns_expected_output(self) -> None:
        """run() with valid input returns dict from _process_response()."""
        result = self.agent.run(input_data={"message": "hello"})
        self.assertEqual(result, {"reply": "mock-response"})

    def test_run_populates_memory_in_order(self) -> None:
        """After run(), memory contains user message then assistant response."""
        self.agent.run(input_data={"message": "hello"})

        messages = self.agent.memory.get_messages()
        self.assertEqual(self.agent.memory.message_count, 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "hello")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], "mock-response")

    def test_run_passes_context_to_generate_prompt(self) -> None:
        """run() passes context dict through to _generate_prompt()."""
        received_context: dict = {}

        class _ContextAgent(BaseAgent):
            INPUT_SCHEMA = {"q": "question"}
            def _generate_prompt(self, input_data, context):
                received_context.update(context)
                return "sys", input_data["q"]
            def _process_response(self, r):
                return {}

        provider = _MockProvider(response="{}")
        agent = _ContextAgent(name="test", provider=provider)
        agent.run(input_data={"q": "hi"}, context={"step": "onboarding"})
        self.assertEqual(received_context, {"step": "onboarding"})

    def test_run_none_context_normalized_to_empty_dict(self) -> None:
        """run(context=None) passes {} to _generate_prompt(), not None."""
        received_context: list = []

        class _CtxAgent(BaseAgent):
            INPUT_SCHEMA = {}
            def _generate_prompt(self, i, context):
                received_context.append(context)
                return "sys", "user"
            def _process_response(self, r):
                return {}

        provider = _MockProvider(response="{}")
        agent = _CtxAgent(name="test", provider=provider)
        agent.run(input_data={}, context=None)
        self.assertEqual(received_context[0], {})


class TestResetMemory(unittest.TestCase):
    """Test 8: reset_memory() clears conversation history."""

    def test_reset_memory_clears_history(self) -> None:
        """reset_memory() removes all messages from memory."""
        provider = _MockProvider(response="r")
        agent = _ConcreteAgent(name="test", provider=provider)
        agent.run(input_data={"message": "hi"})

        self.assertEqual(agent.memory.message_count, 2)
        agent.reset_memory()
        self.assertEqual(agent.memory.message_count, 0)
        self.assertEqual(agent.memory.get_messages(), [])


class TestStatepersistence(unittest.TestCase):
    """Test 9: save_state() / load_state() round-trip preserves memory."""

    def test_save_and_load_state_round_trip(self) -> None:
        """Memory is preserved across save_state / load_state with a fresh agent."""
        provider = _MockProvider(response="stored-response")

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_lake = DataLake(data_dir=tmp_dir)

            # Run agent and save state
            agent_a = _ConcreteAgent(name="test", provider=provider)
            agent_a.run(input_data={"message": "remember this"})
            agent_a.save_state(data_lake, session_id="session-1")

            # Load into a fresh agent
            agent_b = _ConcreteAgent(name="test", provider=provider)
            self.assertEqual(agent_b.memory.message_count, 0)
            agent_b.load_state(data_lake, session_id="session-1")

            messages_a = agent_a.memory.get_messages()
            messages_b = agent_b.memory.get_messages()
            self.assertEqual(messages_a, messages_b)

    def test_load_state_unknown_session_is_noop(self) -> None:
        """load_state() with an unknown session_id leaves agent memory unchanged."""
        provider = _MockProvider(response="r")

        with tempfile.TemporaryDirectory() as tmp_dir:
            data_lake = DataLake(data_dir=tmp_dir)

            agent = _ConcreteAgent(name="test", provider=provider)
            agent.memory.add_user("existing message")
            agent.load_state(data_lake, session_id="does-not-exist")

            # Memory unchanged
            self.assertEqual(agent.memory.message_count, 1)


class TestStructuredOutput(unittest.TestCase):
    """Tests 10-11: structured output mode and Pydantic response validation."""

    def test_response_model_passes_structured_output_true(self) -> None:
        """When RESPONSE_MODEL is defined, _generate_response() passes structured_output=True."""
        provider = _MockProvider(response='{"reply": "hi", "confidence": 0.9}')
        agent = _TypedAgent(name="typed", provider=provider)
        agent.run(input_data={"message": "test"})

        self.assertTrue(provider.last_call_kwargs["structured_output"])

    def test_no_response_model_passes_structured_output_false(self) -> None:
        """When RESPONSE_MODEL is None, _generate_response() passes structured_output=False."""
        provider = _MockProvider(response="plain text")
        agent = _ConcreteAgent(name="plain", provider=provider)
        agent.run(input_data={"message": "test"})

        self.assertFalse(provider.last_call_kwargs["structured_output"])

    def test_parse_response_validates_against_response_model(self) -> None:
        """_parse_response() validates JSON against RESPONSE_MODEL and returns model_dump()."""
        provider = _MockProvider()
        agent = _TypedAgent(name="typed", provider=provider)

        result = agent._parse_response('{"reply": "hello", "confidence": 0.9}')
        self.assertEqual(result, {"reply": "hello", "confidence": 0.9})

    def test_parse_response_invalid_json_returns_empty_dict(self) -> None:
        """_parse_response() returns {} when the input is not valid JSON."""
        provider = _MockProvider()
        agent = _TypedAgent(name="typed", provider=provider)

        result = agent._parse_response("not json at all")
        self.assertEqual(result, {})

    def test_parse_response_validation_failure_returns_raw_dict(self) -> None:
        """_parse_response() falls back to raw parsed dict when Pydantic validation fails."""
        class _StrictResponse(BaseModel):
            required_field: str  # no default -- validation will fail if missing

        class _StrictAgent(BaseAgent):
            INPUT_SCHEMA   = {}
            RESPONSE_MODEL = _StrictResponse
            def _generate_prompt(self, i, c): return "s", "u"
            def _process_response(self, r): return {}

        provider = _MockProvider()
        agent = _StrictAgent(name="strict", provider=provider)

        # JSON is valid but missing required_field -- Pydantic validation fails
        result = agent._parse_response('{"other_key": "value"}')
        self.assertEqual(result, {"other_key": "value"})

    def test_parse_response_no_response_model_returns_raw_dict(self) -> None:
        """_parse_response() returns raw parsed dict when RESPONSE_MODEL is None."""
        provider = _MockProvider()
        agent = _ConcreteAgent(name="plain", provider=provider)

        result = agent._parse_response('{"key": "value"}')
        self.assertEqual(result, {"key": "value"})

    def test_prompt_none_passed_to_provider(self) -> None:
        """_generate_response() passes prompt=None to avoid duplicating the user message."""
        provider = _MockProvider(response="r")
        agent = _ConcreteAgent(name="test", provider=provider)
        agent.run(input_data={"message": "hi"})

        self.assertIsNone(provider.last_call_kwargs["prompt"])
        # Messages list is non-empty (contains the user message added by run())
        self.assertIsNotNone(provider.last_call_kwargs["messages"])
        self.assertGreater(len(provider.last_call_kwargs["messages"]), 0)


# ---------------------------------------------------------------------------
# Fixture for tool calling tests (5.2)
# ---------------------------------------------------------------------------

class _MockToolProvider(LlmProvider):
    """
    Provider that returns a pre-configured sequence of ProviderResponse objects.

    Used to simulate multi-turn tool interactions without any API calls.
    Raises StopIteration if more calls are made than responses configured.
    """

    def __init__(self, responses: list[ProviderResponse]) -> None:
        super().__init__(model_name="mock-tool")
        self._responses = iter(responses)
        self.call_count = 0

    def _do_generate(self, **kwargs) -> str:
        # Not used in tool calling tests -- generate_raw() is called instead.
        return ""

    def generate_raw(self, **kwargs) -> ProviderResponse:
        self.call_count += 1
        return next(self._responses)


class _ToolAgent(BaseAgent):
    """Concrete agent used in tool calling tests."""

    INPUT_SCHEMA  = {"message": "A message."}
    OUTPUT_SCHEMA = {"reply": "The agent's reply."}

    def _generate_prompt(self, input_data: dict, context: dict) -> tuple[str, str]:
        return "You are a tool-calling test agent.", input_data["message"]

    def _process_response(self, response: str) -> dict[str, Any]:
        return {"reply": response}


# ---------------------------------------------------------------------------
# Tool calling tests (5.2)
# ---------------------------------------------------------------------------

class TestToolCalling(unittest.TestCase):
    """Tests for register_tool(), _execute_tool(), and the tool calling loop."""

    def test_register_tool_creates_registry_when_none(self) -> None:
        """register_tool() auto-creates ToolRegistry when tools=None."""
        provider = _MockToolProvider([ProviderResponse(text="done")])
        agent = _ToolAgent(name="test", provider=provider)

        self.assertIsNone(agent.tools)
        agent.register_tool("my_tool", lambda: "ok", description="A tool.")
        self.assertIsNotNone(agent.tools)
        self.assertIsInstance(agent.tools, ToolRegistry)

    def test_register_tool_reuses_existing_registry(self) -> None:
        """register_tool() reuses the existing ToolRegistry when already set."""
        provider = _MockToolProvider([ProviderResponse(text="done")])
        registry = ToolRegistry()
        agent = _ToolAgent(name="test", provider=provider, tools=registry)

        agent.register_tool("my_tool", lambda: "ok", description="A tool.")
        self.assertIs(agent.tools, registry)

    def test_execute_tool_returns_result_for_valid_tool(self) -> None:
        """_execute_tool() returns str(result) for a registered tool."""
        provider = _MockToolProvider([ProviderResponse(text="done")])
        agent = _ToolAgent(name="test", provider=provider)
        agent.register_tool("add", lambda a, b: a + b, description="Add two numbers.")

        tool_call = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "add", "arguments": '{"a": 3, "b": 4}'},
        }
        result = agent._execute_tool(tool_call)
        self.assertEqual(result, "7")

    def test_execute_tool_returns_error_string_for_unknown_tool(self) -> None:
        """_execute_tool() returns error string for unregistered tool -- never raises."""
        provider = _MockToolProvider([ProviderResponse(text="done")])
        agent = _ToolAgent(name="test", provider=provider)
        agent.register_tool("known_tool", lambda: "ok", description="Known.")

        tool_call = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "unknown_tool", "arguments": "{}"},
        }
        result = agent._execute_tool(tool_call)
        self.assertIn("unknown_tool", result)
        self.assertIn("Error", result)

    def test_execute_tool_returns_error_string_when_tool_raises(self) -> None:
        """_execute_tool() returns error string when tool function raises -- never raises."""
        def _bad_tool():
            raise ValueError("something went wrong")

        provider = _MockToolProvider([ProviderResponse(text="done")])
        agent = _ToolAgent(name="test", provider=provider)
        agent.register_tool("bad_tool", _bad_tool, description="Always fails.")

        tool_call = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "bad_tool", "arguments": "{}"},
        }
        result = agent._execute_tool(tool_call)
        self.assertIn("bad_tool", result)
        self.assertIn("Error", result)

    def test_multi_turn_tool_loop_returns_final_text(self) -> None:
        """Tool call on turn 1, text on turn 2 -- run() returns the final text."""
        tool_call_response = ProviderResponse(tool_calls=[{
            "id": "call_1",
            "type": "function",
            "function": {"name": "get_value", "arguments": '{"key": "x"}'},
        }])
        text_response = ProviderResponse(text="final answer")

        provider = _MockToolProvider([tool_call_response, text_response])
        agent = _ToolAgent(name="test", provider=provider)
        agent.register_tool(
            "get_value", lambda key: "42", description="Get value by key.",
            parameters_schema={"type": "object", "properties": {"key": {"type": "string"}}},
        )

        result = agent.run(input_data={"message": "what is x?"})

        self.assertEqual(result, {"reply": "final answer"})
        self.assertEqual(provider.call_count, 2)

    def test_memory_contains_tool_call_and_result_after_tool_use(self) -> None:
        """Memory has tool call and tool result messages after a tool-use turn."""
        tool_call_response = ProviderResponse(tool_calls=[{
            "id": "call_1",
            "type": "function",
            "function": {"name": "get_value", "arguments": '{"key": "x"}'},
        }])
        text_response = ProviderResponse(text="done")

        provider = _MockToolProvider([tool_call_response, text_response])
        agent = _ToolAgent(name="test", provider=provider)
        agent.register_tool("get_value", lambda key: "42", description="Get value.")

        agent.run(input_data={"message": "hi"})

        messages = agent.memory.get_messages()
        roles = [m["role"] for m in messages]

        self.assertIn("tool", roles)
        tool_call_msgs = [m for m in messages if m.get("tool_calls")]
        self.assertTrue(len(tool_call_msgs) >= 1)
        tool_result_msgs = [m for m in messages if m.get("role") == "tool"]
        self.assertEqual(tool_result_msgs[0]["content"], "42")

    def test_exceeding_max_tool_rounds_raises_runtime_error(self) -> None:
        """_generate_response() raises RuntimeError after _MAX_TOOL_ROUNDS tool responses."""
        responses = [
            ProviderResponse(tool_calls=[{
                "id": f"call_{i}",
                "type": "function",
                "function": {"name": "loop_tool", "arguments": "{}"},
            }])
            for i in range(BaseAgent._MAX_TOOL_ROUNDS + 1)
        ]
        provider = _MockToolProvider(responses)
        agent = _ToolAgent(name="test", provider=provider)
        agent.register_tool("loop_tool", lambda: "ok", description="Loops forever.")

        with self.assertRaises(RuntimeError) as ctx:
            agent.run(input_data={"message": "go"})

        self.assertIn(str(BaseAgent._MAX_TOOL_ROUNDS), str(ctx.exception))
        self.assertIn("test", str(ctx.exception))


class TestBaseAgentStateManagement(unittest.TestCase):
    """Tests for store(), retrieve(), clear_store(), and extended save/load_state() (5.3)."""

    def setUp(self) -> None:
        self.provider = _MockProvider()
        self.agent = _ConcreteAgent(name="test", provider=self.provider)

    def test_store_and_retrieve_round_trip(self) -> None:
        """store() and retrieve() return the same value."""
        self.agent.store("restaurant_name", "La Palapa")
        self.assertEqual(self.agent.retrieve("restaurant_name"), "La Palapa")

    def test_retrieve_missing_key_returns_none_by_default(self) -> None:
        """retrieve() returns None when key is absent and no default is given."""
        self.assertIsNone(self.agent.retrieve("nonexistent_key"))

    def test_retrieve_missing_key_returns_explicit_default(self) -> None:
        """retrieve() returns the caller-supplied default when key is absent."""
        self.assertEqual(self.agent.retrieve("nonexistent_key", "fallback"), "fallback")

    def test_clear_store_empties_store_and_leaves_memory_unchanged(self) -> None:
        """clear_store() removes all stored values without touching conversation memory."""
        self.agent.memory.add_user("hello")
        self.agent.store("restaurant_name", "La Palapa")

        self.agent.clear_store()

        self.assertIsNone(self.agent.retrieve("restaurant_name"))
        self.assertEqual(len(self.agent.memory.get_messages()), 1)

    def test_reset_memory_clears_memory_and_leaves_store_unchanged(self) -> None:
        """reset_memory() removes all messages without touching the data store."""
        self.agent.memory.add_user("hello")
        self.agent.store("restaurant_name", "La Palapa")

        self.agent.reset_memory()

        self.assertEqual(self.agent.retrieve("restaurant_name"), "La Palapa")
        self.assertEqual(len(self.agent.memory.get_messages()), 0)

    def test_save_and_load_state_round_trip_preserves_memory_and_store(self) -> None:
        """save_state / load_state restore both conversation memory and data store."""
        with tempfile.TemporaryDirectory() as tmp:
            data_lake = DataLake(data_dir=tmp)

            self.agent.memory.add_user("hello")
            self.agent.memory.add_assistant("world")
            self.agent.store("restaurant_name", "La Palapa")
            self.agent.store("restaurant_type", "casual")
            self.agent.save_state(data_lake, session_id="test_session")

            fresh = _ConcreteAgent(name="test", provider=self.provider)
            fresh.load_state(data_lake, session_id="test_session")

            self.assertEqual(fresh.retrieve("restaurant_name"), "La Palapa")
            self.assertEqual(fresh.retrieve("restaurant_type"), "casual")
            messages = fresh.memory.get_messages()
            self.assertEqual(len(messages), 2)
            self.assertEqual(messages[0]["content"], "hello")
            self.assertEqual(messages[1]["content"], "world")

    def test_load_state_unknown_session_is_noop(self) -> None:
        """load_state() with an unknown session_id leaves memory and store unchanged."""
        with tempfile.TemporaryDirectory() as tmp:
            data_lake = DataLake(data_dir=tmp)

            self.agent.store("key", "value")
            self.agent.load_state(data_lake, session_id="does_not_exist")

            self.assertEqual(self.agent.retrieve("key"), "value")
            self.assertEqual(len(self.agent.memory.get_messages()), 0)


class TestRestaurantInfoAgent(unittest.TestCase):
    """6 mocked tests for RestaurantInfoAgent end-to-end behaviour."""

    def setUp(self) -> None:
        self.valid_response = '{"restaurant_name": "La Palapa", "restaurant_type": "casual"}'
        self.provider = _MockProvider(response=self.valid_response)
        self.agent = RestaurantInfoAgent(name="test-restaurant-agent", provider=self.provider)

    def test_run_returns_correct_output_structure(self) -> None:
        """run() returns all three OUTPUT_SCHEMA keys with correct extracted values."""
        result = self.agent.run(input_data={"user_message": "My restaurant is La Palapa, casual dining."})

        self.assertIn("restaurant_name", result)
        self.assertIn("restaurant_type", result)
        self.assertIn("raw_response", result)
        self.assertEqual(result["restaurant_name"], "La Palapa")
        self.assertEqual(result["restaurant_type"], "casual")
        self.assertEqual(result["raw_response"], self.valid_response)

    def test_run_populates_memory(self) -> None:
        """run() adds user message and assistant response to conversation memory."""
        self.agent.run(input_data={"user_message": "My restaurant is La Palapa."})

        messages = self.agent.memory.get_messages()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "My restaurant is La Palapa.")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], self.valid_response)

    def test_missing_user_message_raises_before_api_call(self) -> None:
        """run() with missing user_message raises ValueError; provider never called."""
        with self.assertRaises(ValueError) as ctx:
            self.agent.run(input_data={})

        self.assertIn("user_message", str(ctx.exception))
        self.assertEqual(self.provider.last_call_kwargs, {})

    def test_malformed_response_handled_gracefully(self) -> None:
        """Non-JSON LLM response does not crash; extracted values default to None."""
        provider = _MockProvider(response="Sorry, I could not understand that.")
        agent = RestaurantInfoAgent(name="test", provider=provider)

        result = agent.run(input_data={"user_message": "hello"})

        self.assertIn("restaurant_name", result)
        self.assertIsNone(result["restaurant_name"])
        self.assertIsNone(result["restaurant_type"])
        self.assertEqual(result["raw_response"], "Sorry, I could not understand that.")

    def test_multi_turn_accumulates_memory(self) -> None:
        """Two consecutive run() calls accumulate four messages in memory."""
        self.agent.run(input_data={"user_message": "First message."})
        self.agent.run(input_data={"user_message": "Second message."})

        messages = self.agent.memory.get_messages()
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0]["content"], "First message.")
        self.assertEqual(messages[2]["content"], "Second message.")

    def test_data_store_populated_after_run(self) -> None:
        """_process_response() calls store() so retrieve() returns extracted values."""
        self.agent.run(input_data={"user_message": "My restaurant is La Palapa, casual dining."})

        self.assertEqual(self.agent.retrieve("restaurant_name"), "La Palapa")
        self.assertEqual(self.agent.retrieve("restaurant_type"), "casual")


@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY not set")
class TestLiveRestaurantInfoAgent(unittest.TestCase):
    """Live tests against the Claude API. Skipped if ANTHROPIC_API_KEY is not set."""

    def setUp(self) -> None:
        self.provider = ClaudeProvider(model_name="claude-haiku-4-5-20251001")
        self.agent = RestaurantInfoAgent(name="live-test", provider=self.provider)

    def test_live_extracts_restaurant_info(self) -> None:
        """Real LLM call returns non-None restaurant name and type for a clear message."""
        result = self.agent.run(
            input_data={"user_message": "My restaurant is called Tacos El Gordo, it's a fast casual taco spot."}
        )

        self.assertIn("restaurant_name", result)
        self.assertIn("restaurant_type", result)
        self.assertIsNotNone(result["restaurant_name"])
        self.assertIsNotNone(result["restaurant_type"])

    def test_live_multi_turn_extracts_across_turns(self) -> None:
        """Real LLM extracts restaurant_type from second turn; memory accumulates correctly."""
        self.agent.run(
            input_data={"user_message": "My restaurant is called El Fogón."}
        )
        result2 = self.agent.run(
            input_data={"user_message": "It's a full-service Mexican restaurant."}
        )

        messages = self.agent.memory.get_messages()
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0]["content"], "My restaurant is called El Fogón.")
        self.assertEqual(messages[2]["content"], "It's a full-service Mexican restaurant.")
        self.assertIsNotNone(result2["restaurant_type"])


class _FailingProvider(LlmProvider):
    """
    Mock provider that works through a list of side effects in order.
    Each element is either a string (returned) or an Exception instance (raised).
    """

    def __init__(self, side_effects: list) -> None:
        super().__init__(model_name="mock-failing")
        self._side_effects = list(side_effects)
        self._call_count = 0

    def _do_generate(self, *, prompt, system, tools, structured_output, messages, max_tokens, temperature) -> str:
        effect = self._side_effects[self._call_count]
        self._call_count += 1
        if isinstance(effect, Exception):
            raise effect
        return effect


class TestAgentUtils(unittest.TestCase):
    """Tests for _is_retryable(), create_agent(), and AgentRegistry (5.5)."""

    def setUp(self) -> None:
        self.provider = _MockProvider()

    def test_is_retryable_returns_true_for_retryable_name(self) -> None:
        """_is_retryable() returns True for a known retryable exception class name."""
        self.assertTrue(_is_retryable(RateLimitError()))

    def test_is_retryable_returns_false_for_non_retryable_name(self) -> None:
        """_is_retryable() returns False for an unrecognised exception class name."""
        self.assertFalse(_is_retryable(ValueError("bad input")))

    def test_create_agent_returns_correct_instance(self) -> None:
        """create_agent() returns an agent of the requested class with correct fields."""
        agent = create_agent(RestaurantInfoAgent, provider=self.provider, name="info-agent")
        self.assertIsInstance(agent, RestaurantInfoAgent)
        self.assertEqual(agent.name, "info-agent")
        self.assertIs(agent.provider, self.provider)

    def test_create_agent_with_non_baseagent_class_raises_type_error(self) -> None:
        """create_agent() raises TypeError when passed a non-BaseAgent class."""
        with self.assertRaises(TypeError):
            create_agent(str, provider=self.provider, name="x")  # type: ignore[arg-type]

    def test_agent_registry_register_and_get(self) -> None:
        """register() + get() round-trip returns the correct agent instances."""
        agent_a = _ConcreteAgent(name="agent-a", provider=self.provider)
        agent_b = _ConcreteAgent(name="agent-b", provider=self.provider)
        registry = AgentRegistry()
        registry.register(agent_a)
        registry.register(agent_b)
        self.assertIs(registry.get("agent-a"), agent_a)
        self.assertIs(registry.get("agent-b"), agent_b)

    def test_agent_registry_get_unknown_name_returns_none(self) -> None:
        """get() returns None for a name that was never registered."""
        registry = AgentRegistry()
        self.assertIsNone(registry.get("nonexistent"))

    def test_agent_registry_list_names_reflects_registered_agents(self) -> None:
        """list_names() contains the names of all registered agents."""
        agent_alpha = _ConcreteAgent(name="alpha", provider=self.provider)
        agent_beta = _ConcreteAgent(name="beta", provider=self.provider)
        registry = AgentRegistry()
        registry.register(agent_alpha)
        registry.register(agent_beta)
        names = registry.list_names()
        self.assertIn("alpha", names)
        self.assertIn("beta", names)


class TestBaseAgentRetry(unittest.TestCase):
    """Tests for _generate_with_retry() and empty response check (5.5)."""

    def _make_agent(self, provider: LlmProvider) -> RestaurantInfoAgent:
        return RestaurantInfoAgent(name="retry-test", provider=provider)

    @unittest.mock.patch("core.agents.base_agent.time.sleep")
    def test_retry_succeeds_on_transient_error(self, mock_sleep: unittest.mock.MagicMock) -> None:
        """_generate_with_retry() retries on a retryable error and returns on third attempt."""
        valid = '{"restaurant_name": "El Cielo", "restaurant_type": "fine-dining"}'
        provider = _FailingProvider([RateLimitError(), RateLimitError(), valid])
        agent = self._make_agent(provider)

        result = agent.run(input_data={"user_message": "My restaurant is El Cielo."})

        self.assertEqual(result["restaurant_name"], "El Cielo")
        self.assertEqual(provider._call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @unittest.mock.patch("core.agents.base_agent.time.sleep")
    def test_retry_raises_after_max_retries_exhausted(self, mock_sleep: unittest.mock.MagicMock) -> None:
        """_generate_with_retry() re-raises after all 3 attempts fail."""
        provider = _FailingProvider([RateLimitError(), RateLimitError(), RateLimitError()])
        agent = self._make_agent(provider)

        with self.assertRaises(RateLimitError):
            agent.run(input_data={"user_message": "hello"})

        self.assertEqual(provider._call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @unittest.mock.patch("core.agents.base_agent.time.sleep")
    def test_no_retry_on_non_retryable_error(self, mock_sleep: unittest.mock.MagicMock) -> None:
        """_generate_with_retry() raises immediately for a non-retryable error."""
        provider = _FailingProvider([AuthenticationError()])
        agent = self._make_agent(provider)

        with self.assertRaises(AuthenticationError):
            agent.run(input_data={"user_message": "hello"})

        self.assertEqual(provider._call_count, 1)
        mock_sleep.assert_not_called()

    def test_empty_response_raises_runtime_error(self) -> None:
        """_generate_response() raises RuntimeError when the provider returns ''."""
        provider = _MockProvider(response="")
        agent = self._make_agent(provider)

        with self.assertRaises(RuntimeError) as ctx:
            agent.run(input_data={"user_message": "hello"})

        self.assertIn("retry-test", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
