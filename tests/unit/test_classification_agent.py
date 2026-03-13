"""Unit tests for ClassificationAgent, _format_draft, _make_confirm_fn, and storage.

16 mocked (offline) tests + 3 live tests guarded by ANTHROPIC_API_KEY.
"""

import json
import os
import tempfile
import unittest
from typing import Any

from core.agents.classification_agent import ClassificationAgent
from core.agents.utils import create_agent
from core.ai.providers import LlmProvider
from core.storage.persistence import DataLake
from gradio_app.components import _format_draft
from gradio_app.sections.clasificacion import _make_confirm_fn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_data_lake() -> DataLake:
    return DataLake(data_dir=tempfile.mkdtemp())


def _json_response(reply: str = "Hola.", level: int | None = 2) -> str:
    payload: dict[str, Any] = {"reply": reply}
    if level is not None:
        payload["standardization_level"] = level
    return json.dumps(payload)


# ---------------------------------------------------------------------------
# Mock providers
# ---------------------------------------------------------------------------

class _MockProvider(LlmProvider):
    def __init__(self, response: str | None = None) -> None:
        super().__init__(model_name="mock")
        self.response = response or _json_response()
        self.last_system: str = ""

    def _do_generate(
        self,
        *,
        prompt: str | None,
        system: str | None,
        tools: list | None,
        structured_output: bool,
        messages: list | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        self.last_system = system or ""
        return self.response


# ---------------------------------------------------------------------------
# TestClassificationAgent — 10 mocked tests
# ---------------------------------------------------------------------------

class TestClassificationAgent(unittest.TestCase):

    def _make_agent(self, response: str | None = None):
        provider = _MockProvider(response=response)
        agent = create_agent(ClassificationAgent, provider=provider, name="classification_agent")
        return agent, provider

    def test_agent_instantiates_via_factory(self):
        agent, _ = self._make_agent()
        self.assertIsInstance(agent, ClassificationAgent)

    def test_response_model_is_set(self):
        self.assertIsNotNone(ClassificationAgent.RESPONSE_MODEL)

    def test_input_schema_has_user_message(self):
        self.assertIn("user_message", ClassificationAgent.INPUT_SCHEMA)

    def test_run_returns_reply(self):
        agent, _ = self._make_agent()
        result = agent.run(input_data={"user_message": "Hola"})
        self.assertTrue(result["reply"])

    def test_run_stores_level_in_data_store(self):
        agent, _ = self._make_agent(response=_json_response(level=2))
        agent.run(input_data={"user_message": "Operamos desde hace 5 años."})
        self.assertEqual(agent.retrieve("standardization_level"), 2)

    def test_run_does_not_overwrite_existing_level(self):
        # First turn sets level 2; second turn returns null level — must not overwrite
        agent, _ = self._make_agent(response=_json_response(level=2))
        agent.run(input_data={"user_message": "Primera vuelta."})
        agent.provider.response = _json_response(level=None)
        agent.run(input_data={"user_message": "Segunda vuelta."})
        self.assertEqual(agent.retrieve("standardization_level"), 2)

    def test_context_injects_restaurant_name(self):
        agent, provider = self._make_agent()
        agent.run(
            input_data={"user_message": "Hola"},
            context={"restaurant_name": "Tacos El Güero"},
        )
        self.assertIn("Tacos El Güero", provider.last_system)

    def test_draft_injected_in_prompt(self):
        agent, provider = self._make_agent(response=_json_response(level=1))
        agent.run(input_data={"user_message": "Primera vuelta."})
        agent.run(input_data={"user_message": "Segunda vuelta."})
        self.assertIn("standardization_level", provider.last_system)

    def test_missing_user_message_raises(self):
        agent, _ = self._make_agent()
        with self.assertRaises((ValueError, KeyError)):
            agent.run(input_data={})

    def test_save_load_state_preserves_draft(self):
        dl = _make_data_lake()
        agent, _ = self._make_agent(response=_json_response(level=3))
        agent.run(input_data={"user_message": "Hola"})
        agent.save_state(dl, session_id="classification_agent_test")

        agent2 = create_agent(ClassificationAgent, provider=_MockProvider(), name="classification_agent")
        agent2.load_state(dl, session_id="classification_agent_test")
        self.assertEqual(agent2.retrieve("standardization_level"), 3)


# ---------------------------------------------------------------------------
# TestFormatDraft — 3 tests
# ---------------------------------------------------------------------------

class TestFormatDraft(unittest.TestCase):

    def test_empty_draft_shows_placeholder(self):
        text, btn = _format_draft({})
        self.assertIn("asistente", text.lower())
        self.assertFalse(btn["interactive"])

    def test_level_set_shows_label(self):
        text, btn = _format_draft({"standardization_level": 2})
        self.assertIn("Nivel 2", text)
        self.assertTrue(btn["interactive"])

    def test_unknown_level_does_not_raise(self):
        text, btn = _format_draft({"standardization_level": 99})
        self.assertIn("99", text)
        self.assertTrue(btn["interactive"])


# ---------------------------------------------------------------------------
# TestConfirmFn — 2 tests
# ---------------------------------------------------------------------------

class TestConfirmFn(unittest.TestCase):

    def test_confirm_fn_persists_classification(self):
        dl = _make_data_lake()
        confirm_fn = _make_confirm_fn(dl)
        session_id = "test_session"
        draft = {"standardization_level": 2}
        result = confirm_fn(draft, session_id)
        entity_id = abs(hash(session_id)) % (2**31 - 1)
        saved = dl.load_entity("classification", entity_id)
        self.assertEqual(saved["standardization_level"], 2)
        self.assertIn("2", result)

    def test_confirm_fn_empty_session_returns_error(self):
        dl = _make_data_lake()
        confirm_fn = _make_confirm_fn(dl)
        result = confirm_fn({"standardization_level": 1}, "")
        self.assertIn("Sesión", result)
        entity_id = abs(hash("")) % (2**31 - 1)
        self.assertIsNone(dl.load_entity("classification", entity_id))


# ---------------------------------------------------------------------------
# TestClassificationStorage — 1 round-trip test
# ---------------------------------------------------------------------------

class TestClassificationStorage(unittest.TestCase):

    def test_classification_save_load_round_trip(self):
        dl = _make_data_lake()
        data = {"standardization_level": 3}
        dl.save_entity("classification", 1, data)
        loaded = dl.load_entity("classification", 1)
        self.assertEqual(loaded, data)


# ---------------------------------------------------------------------------
# TestClassificationAgentLive — 3 live tests (requires ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------

@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "requires ANTHROPIC_API_KEY")
class TestClassificationAgentLive(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from core.ai.providers import ClaudeProvider
        cls.provider = ClaudeProvider()

    def test_live_responds_in_spanish(self):
        agent = create_agent(ClassificationAgent, provider=self.provider, name="classification_agent")
        result = agent.run(input_data={"user_message": "Hola, ¿cómo funciona esta sección?"})
        reply = result["reply"].lower()
        spanish_words = ["nivel", "restaurante", "hola", "operación", "estandarización", "zenet"]
        self.assertTrue(any(w in reply for w in spanish_words))
        self.assertNotIn("{", result["reply"])

    def test_live_diagnoses_level(self):
        agent = create_agent(ClassificationAgent, provider=self.provider, name="classification_agent")
        agent.run(input_data={
            "user_message": (
                "Llevamos 2 años operando. Todo está en nuestra cabeza, "
                "no tenemos recetas escritas ni inventarios documentados."
            )
        })
        level = agent.retrieve("standardization_level")
        if level is not None:
            self.assertIn(level, {1, 2, 3})

    def test_live_multi_turn_accumulates(self):
        agent = create_agent(ClassificationAgent, provider=self.provider, name="classification_agent")
        agent.run(input_data={"user_message": "Hola"})
        agent.run(input_data={
            "user_message": (
                "Tenemos un Excel con recetas pero no está completo. "
                "Trabajamos así desde hace 3 años."
            )
        })
        self.assertGreater(agent.memory.message_count, 2)


if __name__ == "__main__":
    unittest.main()
