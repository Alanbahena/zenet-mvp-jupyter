"""Unit tests for BaseAgent (subtask 5.1). No API calls -- all LLM calls are mocked."""

import tempfile
import unittest
from typing import Any

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent
from core.ai.memory import ConversationMemory
from core.ai.providers import LlmProvider, ToolRegistry
from core.storage.persistence import DataLake


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


if __name__ == "__main__":
    unittest.main()
