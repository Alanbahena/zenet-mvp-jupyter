"""Unit tests for WelcomeAgent, _make_save_fn, _load_form_context, and _make_chat_fn.

18 mocked (offline) tests + 3 live tests guarded by ANTHROPIC_API_KEY.
"""

import os
import tempfile
import unittest
from typing import Any

from core.agents.utils import create_agent
from core.agents.welcome_agent import WelcomeAgent
from core.ai.providers import LlmProvider
from core.storage.persistence import DataLake
from gradio_app.sections.bienvenida import (
    _load_form_context,
    _make_chat_fn,
    _make_save_fn,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_data_lake() -> DataLake:
    return DataLake(data_dir=tempfile.mkdtemp())


# ---------------------------------------------------------------------------
# Mock providers
# ---------------------------------------------------------------------------

class _MockProvider(LlmProvider):
    def __init__(self, response: str = "Hola, soy Zeni.") -> None:
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


class _FailingProvider(_MockProvider):
    def _do_generate(self, **kwargs) -> str:
        raise RuntimeError("API down")


# ---------------------------------------------------------------------------
# TestWelcomeAgent — 11 mocked tests
# ---------------------------------------------------------------------------

class TestWelcomeAgent(unittest.TestCase):

    def _make_agent(self, response: str = "Hola, soy Zeni.") -> tuple[WelcomeAgent, _MockProvider]:
        provider = _MockProvider(response=response)
        agent = create_agent(WelcomeAgent, provider=provider, name="welcome_agent")
        return agent, provider

    def test_agent_instantiates_via_factory(self):
        agent, _ = self._make_agent()
        self.assertIsInstance(agent, WelcomeAgent)

    def test_response_model_is_none(self):
        self.assertIsNone(WelcomeAgent.RESPONSE_MODEL)

    def test_input_schema_has_user_message(self):
        self.assertIn("user_message", WelcomeAgent.INPUT_SCHEMA)

    def test_run_returns_reply_and_raw_response(self):
        agent, _ = self._make_agent()
        result = agent.run(input_data={"user_message": "Hola"})
        self.assertEqual(result["reply"], "Hola, soy Zeni.")
        self.assertEqual(result["raw_response"], "Hola, soy Zeni.")

    def test_run_adds_messages_to_memory(self):
        agent, _ = self._make_agent()
        agent.run(input_data={"user_message": "Hola"})
        self.assertEqual(agent.memory.message_count, 2)

    def test_missing_user_message_raises(self):
        agent, _ = self._make_agent()
        with self.assertRaises(ValueError):
            agent.run(input_data={})

    def test_response_is_plain_text(self):
        agent, _ = self._make_agent(response="Bienvenido al sistema.")
        result = agent.run(input_data={"user_message": "Hola"})
        self.assertEqual(result["reply"], "Bienvenido al sistema.")

    def test_context_with_operator_name(self):
        agent, provider = self._make_agent()
        agent.run(input_data={"user_message": "Hola"}, context={"operator_name": "Juan"})
        self.assertIn("Juan", provider.last_call_kwargs["system"])

    def test_context_empty_uses_base_prompt(self):
        agent, _ = self._make_agent()
        # Should not raise
        result = agent.run(input_data={"user_message": "Hola"}, context={})
        self.assertIn("reply", result)

    def test_multi_turn_accumulates_memory(self):
        agent, _ = self._make_agent()
        agent.run(input_data={"user_message": "Hola"})
        agent.run(input_data={"user_message": "¿Qué es Zenet?"})
        self.assertEqual(agent.memory.message_count, 4)

    def test_save_load_state_round_trip(self):
        dl = _make_data_lake()
        agent, _ = self._make_agent()
        agent.run(input_data={"user_message": "Hola"})
        agent.save_state(dl, session_id="welcome_agent_test")

        agent2 = create_agent(WelcomeAgent, provider=_MockProvider(), name="welcome_agent")
        agent2.load_state(dl, session_id="welcome_agent_test")
        self.assertEqual(agent2.memory.message_count, 2)


# ---------------------------------------------------------------------------
# TestSaveFn — 5 tests
# ---------------------------------------------------------------------------

class TestSaveFn(unittest.TestCase):

    def test_save_fn_error_empty_session(self):
        dl = _make_data_lake()
        save_fn = _make_save_fn(dl)
        result = save_fn("Juan", "Tacos El Güero", "Casual", "")
        self.assertIn("Sesión no iniciada", result[0])

    def test_save_fn_error_missing_user_name(self):
        dl = _make_data_lake()
        save_fn = _make_save_fn(dl)
        result = save_fn("", "Tacos El Güero", "Casual", "test_session")
        self.assertIn("obligatorio", result[0])

    def test_save_fn_error_missing_restaurant_name(self):
        dl = _make_data_lake()
        save_fn = _make_save_fn(dl)
        result = save_fn("Juan", "", "Casual", "test_session")
        self.assertIn("obligatorio", result[0])

    def test_save_fn_persists_entities(self):
        dl = _make_data_lake()
        save_fn = _make_save_fn(dl)
        result = save_fn("Juan", "Tacos El Güero", "Casual", "test_session")
        self.assertIn("Bienvenido", result[0])
        entity_id = abs(hash("test_session")) % (2**31 - 1)
        restaurant = dl.load_entity("restaurant", entity_id)
        user = dl.load_entity("user", entity_id)
        self.assertEqual(restaurant["name"], "Tacos El Güero")
        self.assertEqual(user["name"], "Juan")
        self.assertEqual(user["role"], "admin")

    def test_save_fn_none_restaurant_type(self):
        dl = _make_data_lake()
        save_fn = _make_save_fn(dl)
        result = save_fn("Juan", "Tacos El Güero", None, "test_session")
        self.assertIn("Bienvenido", result[0])
        entity_id = abs(hash("test_session")) % (2**31 - 1)
        restaurant = dl.load_entity("restaurant", entity_id)
        self.assertIsNone(restaurant["restaurant_type_id"])


# ---------------------------------------------------------------------------
# TestLoadFormContext — 2 tests
# ---------------------------------------------------------------------------

class TestLoadFormContext(unittest.TestCase):

    def test_load_form_context_empty_session(self):
        dl = _make_data_lake()
        result = _load_form_context(dl, "empty_session")
        self.assertEqual(result, {})

    def test_load_form_context_after_save(self):
        dl = _make_data_lake()
        save_fn = _make_save_fn(dl)
        save_fn("Juan", "Tacos El Güero", "Casual", "test_session")
        result = _load_form_context(dl, "test_session")
        self.assertEqual(result["operator_name"], "Juan")
        self.assertEqual(result["restaurant_name"], "Tacos El Güero")


# ---------------------------------------------------------------------------
# TestChatFn — 1 test
# ---------------------------------------------------------------------------

class TestChatFn(unittest.TestCase):

    def test_chat_fn_error_handling(self):
        dl = _make_data_lake()
        chat_fn = _make_chat_fn(_FailingProvider(), dl)
        history, text = chat_fn("Hola", [], "test_session")
        self.assertEqual(text, "")
        self.assertTrue(
            any("problema" in m["content"] for m in history if m["role"] == "assistant")
        )


# ---------------------------------------------------------------------------
# TestWelcomeAgentLive — 3 live tests (requires ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------

@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "requires ANTHROPIC_API_KEY")
class TestWelcomeAgentLive(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from core.ai.providers import ClaudeProvider
        cls.provider = ClaudeProvider()
        cls.dl = _make_data_lake()

    def test_live_responds_in_spanish(self):
        agent = create_agent(WelcomeAgent, provider=self.provider, name="welcome_agent")
        result = agent.run(input_data={"user_message": "Hola, ¿qué es Zenet?"})
        reply = result["reply"].lower()
        spanish_words = ["hola", "bienvenido", "restaurante", "zenet", "sistema", "proceso"]
        self.assertTrue(any(w in reply for w in spanish_words))

    def test_live_warm_tone(self):
        agent = create_agent(WelcomeAgent, provider=self.provider, name="welcome_agent")
        result = agent.run(input_data={"user_message": "¿Cómo me puede ayudar Zenet?"})
        reply = result["reply"]
        self.assertNotIn("{", reply)
        self.assertNotIn("}", reply)

    def test_live_multi_turn_context(self):
        agent = create_agent(WelcomeAgent, provider=self.provider, name="welcome_agent")
        agent.run(input_data={"user_message": "Hola"})
        result = agent.run(input_data={"user_message": "¿Qué pasa en la sección de clasificación?"})
        self.assertTrue(result["reply"])
        self.assertEqual(agent.memory.message_count, 4)


if __name__ == "__main__":
    unittest.main()
