"""Unit tests for ConfigurationAgent, ConsistencyCheckAgent, _make_confirm_fn, and _save_step.

16 mocked (offline) tests + 3 live tests guarded by ANTHROPIC_API_KEY.
"""

import json
import os
import tempfile
import unittest
from typing import Any

from core.agents import ConfigurationAgent, ConsistencyCheckAgent, create_agent
from core.ai.providers import LlmProvider
from core.storage.persistence import DataLake
from gradio_app.sections.configuracion import _make_confirm_fn, _save_step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_data_lake() -> DataLake:
    return DataLake(data_dir=tempfile.mkdtemp())


def _config_response(
    reply: str = "Ok.",
    entities: list | None = None,
    step_complete: bool | None = None,
) -> str:
    return json.dumps({"reply": reply, "entities": entities, "step_complete": step_complete})


def _check_response(
    issues: list[str] | None = None,
    suggestions: list[str] | None = None,
    looks_good: bool = True,
) -> str:
    return json.dumps({
        "issues": issues or [],
        "suggestions": suggestions or [],
        "looks_good": looks_good,
    })


# ---------------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------------

class _MockProvider(LlmProvider):
    def __init__(self, response: str | None = None) -> None:
        super().__init__(model_name="mock")
        self.response = response or _config_response()
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
# Sample fixtures for confirm/save tests
# ---------------------------------------------------------------------------

_SAMPLE_CATS = [{"name": "Comidas", "description": "Platillos del día"}]
_SAMPLE_FAMS = [{"name": "Lácteos", "description": "Productos lácteos"}]
_SAMPLE_RU   = [{"name": "gramo", "symbol": "g", "description": "Unidad de peso"}]
_SAMPLE_IU   = [{"name": "kilogramo", "symbol": "kg", "is_standard": True, "description": "Unidad base"}]


# ---------------------------------------------------------------------------
# TestConfigurationAgent — 10 mocked tests
# ---------------------------------------------------------------------------

class TestConfigurationAgent(unittest.TestCase):

    def _make_agent(self, response: str | None = None):
        provider = _MockProvider(response=response)
        agent = create_agent(ConfigurationAgent, provider=provider, name="configuration_agent")
        return agent, provider

    def test_agent_instantiates_via_factory(self):
        agent, _ = self._make_agent()
        self.assertIsInstance(agent, ConfigurationAgent)

    def test_response_model_is_set(self):
        self.assertIsNotNone(ConfigurationAgent.RESPONSE_MODEL)

    def test_run_returns_reply(self):
        agent, _ = self._make_agent()
        result = agent.run(
            input_data={"user_message": "Hola"},
            context={"current_step": "categories"},
        )
        self.assertTrue(result["reply"])

    def test_run_stores_entities_in_data_store(self):
        entities = [{"name": "Comidas", "description": "Platillos del día"}]
        agent, _ = self._make_agent(response=_config_response(entities=entities))
        agent.run(
            input_data={"user_message": "Sí, así está bien."},
            context={"current_step": "categories"},
        )
        self.assertEqual(agent.retrieve("categories"), entities)

    def test_run_does_not_overwrite_existing_entities(self):
        entities = [{"name": "Comidas", "description": "Platillos del día"}]
        agent, _ = self._make_agent(response=_config_response(entities=entities))
        agent.run(
            input_data={"user_message": "Primera vuelta."},
            context={"current_step": "categories"},
        )
        # Second turn returns entities=None — must not overwrite
        agent.provider.response = _config_response(entities=None)
        agent.run(
            input_data={"user_message": "Segunda vuelta."},
            context={"current_step": "categories"},
        )
        self.assertEqual(agent.retrieve("categories"), entities)

    def test_context_injects_restaurant_type(self):
        agent, provider = self._make_agent()
        agent.run(
            input_data={"user_message": "Hola"},
            context={"current_step": "categories", "restaurant_type": "Casual"},
        )
        self.assertIn("Casual", provider.last_system)

    def test_context_injects_classification_level(self):
        agent, provider = self._make_agent()
        agent.run(
            input_data={"user_message": "Hola"},
            context={"current_step": "categories", "standardization_level": 3},
        )
        self.assertIn("3", provider.last_system)

    def test_draft_injected_in_prompt(self):
        entities = [{"name": "Comidas", "description": "Platillos del día"}]
        agent, provider = self._make_agent(response=_config_response(entities=entities))
        agent.run(
            input_data={"user_message": "Primera vuelta."},
            context={"current_step": "categories"},
        )
        agent.provider.response = _config_response(entities=None)
        agent.run(
            input_data={"user_message": "Segunda vuelta."},
            context={"current_step": "categories"},
        )
        # Existing draft must appear in system prompt on second turn
        self.assertIn("Comidas", provider.last_system)

    def test_save_load_state_preserves_all_steps(self):
        dl = _make_data_lake()
        step_entities: dict[str, Any] = {
            "categories":      [{"name": "Comidas", "description": ""}],
            "families":        [{"name": "Lácteos", "description": ""}],
            "recipe_units":    [{"name": "gramo", "symbol": "g", "description": ""}],
            "inventory_units": [{"name": "kg", "symbol": "kg", "is_standard": True, "description": ""}],
        }
        agent, _ = self._make_agent()
        for step_key, entities in step_entities.items():
            agent.provider.response = _config_response(entities=entities)
            agent.run(
                input_data={"user_message": "Ok."},
                context={"current_step": step_key},
            )
        agent.save_state(dl, session_id="configuration_agent_test")

        agent2 = create_agent(ConfigurationAgent, provider=_MockProvider(), name="configuration_agent")
        agent2.load_state(dl, session_id="configuration_agent_test")
        for step_key, entities in step_entities.items():
            self.assertEqual(agent2.retrieve(step_key), entities)

    def test_missing_user_message_raises(self):
        agent, _ = self._make_agent()
        with self.assertRaises(ValueError):
            agent.run(input_data={})


# ---------------------------------------------------------------------------
# TestConsistencyCheckAgent — 3 mocked tests
# ---------------------------------------------------------------------------

class TestConsistencyCheckAgent(unittest.TestCase):

    def _make_agent(self, response: str) -> ConsistencyCheckAgent:
        provider = _MockProvider(response=response)
        return create_agent(ConsistencyCheckAgent, provider=provider, name="consistency_check")

    def test_consistency_check_returns_issues(self):
        agent = self._make_agent(
            _check_response(issues=["Falta unidad de volumen"], looks_good=False)
        )
        result = agent.run(input_data={
            "step": "recipe_units",
            "entities": [],
            "restaurant_type": "Casual",
        })
        self.assertFalse(result["looks_good"])
        self.assertTrue(result["issues"])

    def test_consistency_check_no_issues_looks_good(self):
        agent = self._make_agent(_check_response(looks_good=True))
        result = agent.run(input_data={
            "step": "recipe_units",
            "entities": [
                {"name": "gramo", "symbol": "g"},
                {"name": "mililitro", "symbol": "ml"},
                {"name": "pieza", "symbol": "pza"},
            ],
            "restaurant_type": "Casual",
        })
        self.assertTrue(result["looks_good"])
        self.assertEqual(result["issues"], [])

    def test_consistency_check_cross_entity(self):
        agent = self._make_agent(
            _check_response(issues=["Sin unidad de volumen estándar en inventario"], looks_good=False)
        )
        result = agent.run(input_data={
            "categories":      [{"name": "Comidas", "description": ""}],
            "families":        [{"name": "Lácteos", "description": ""}],
            "recipe_units":    [{"name": "taza", "symbol": "taza", "description": ""}],
            "inventory_units": [],
            "restaurant_type": "Casual",
        })
        self.assertFalse(result["looks_good"])
        self.assertGreater(len(result["issues"]), 0)
        self.assertIn("volumen", result["issues"][0].lower())


# ---------------------------------------------------------------------------
# TestConfirmFn — 3 mocked tests
# ---------------------------------------------------------------------------

class TestConfirmFn(unittest.TestCase):
    """
    All tests use issues_ack=True to bypass the internal ConsistencyCheckAgent
    LLM call — _make_confirm_fn creates its own ClaudeProvider() internally,
    so the early-exit path (issues_ack=True → save immediately) is the correct
    offline approach.
    """

    def test_confirm_fn_persists_entities(self):
        dl = _make_data_lake()
        confirm_fn = _make_confirm_fn(dl)
        confirm_fn(0, _SAMPLE_CATS, [], [], [], True, "sess")
        ids = dl.list_entity_ids("category_recipe")
        self.assertTrue(ids)
        saved = dl.load_entity("category_recipe", 1)
        self.assertEqual(saved["name"], "Comidas")

    def test_confirm_fn_empty_session_returns_error(self):
        dl = _make_data_lake()
        confirm_fn = _make_confirm_fn(dl)
        status, *_ = confirm_fn(0, _SAMPLE_CATS, [], [], [], True, "")
        self.assertIn("Sesión", status)
        self.assertEqual(dl.list_entity_ids("category_recipe"), [])

    def test_id_assignment_sequential(self):
        dl = _make_data_lake()
        draft = [
            {"name": "A", "description": None},
            {"name": "B", "description": None},
        ]
        _save_step(dl, "categories", draft)
        self.assertEqual(dl.load_entity("category_recipe", 1)["name"], "A")
        self.assertEqual(dl.load_entity("category_recipe", 2)["name"], "B")


# ---------------------------------------------------------------------------
# TestConfigurationAgentLive — 3 live tests (requires ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------

@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "requires ANTHROPIC_API_KEY")
class TestConfigurationAgentLive(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from core.ai.providers import ClaudeProvider
        cls.provider = ClaudeProvider()

    def test_live_responds_in_spanish(self):
        agent = create_agent(ConfigurationAgent, provider=self.provider, name="configuration_agent")
        result = agent.run(
            input_data={"user_message": "Hola, ¿cómo funciona esta sección?"},
            context={"current_step": "categories", "restaurant_type": "Casual", "standardization_level": 1},
        )
        reply = result["reply"].lower()
        spanish_words = ["categoría", "receta", "restaurante", "zenet", "nivel", "inventario"]
        self.assertTrue(any(w in reply for w in spanish_words))
        self.assertNotIn("{", result["reply"])

    def test_live_proposes_categories_for_casual(self):
        agent = create_agent(ConfigurationAgent, provider=self.provider, name="configuration_agent")
        result = agent.run(
            input_data={"user_message": "Sí, continúa con las categorías."},
            context={
                "current_step": "categories",
                "restaurant_type": "Casual",
                "restaurant_type_id": 1,
                "standardization_level": 1,
            },
        )
        self.assertIsNotNone(result["entities"])
        self.assertGreaterEqual(len(result["entities"]), 1)

    def test_live_consistency_check_flags_missing_unit(self):
        agent = create_agent(ConsistencyCheckAgent, provider=self.provider, name="consistency_check")
        result = agent.run(input_data={
            "step": "recipe_units",
            "entities": [],
            "restaurant_type": "Casual",
        })
        self.assertFalse(result["looks_good"])
        self.assertGreaterEqual(len(result["issues"]), 1)


if __name__ == "__main__":
    unittest.main()
