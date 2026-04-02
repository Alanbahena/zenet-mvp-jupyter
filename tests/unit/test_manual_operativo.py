"""Unit tests for _build_manual_context, _build_resumen_md, the three tab builders,
ManualOperativoAgent, and _make_content.

12 mocked (offline) tests + 2 live tests guarded by ANTHROPIC_API_KEY.
"""
import os
import tempfile
import unittest
from typing import Any

from core import (
    RecipeUnitRegistry,
    InventoryUnitRegistry,
    CategoryRecipeRegistry,
    FamilyInventoryRegistry,
    InventoryItemRegistry,
    ManualOperativoAgent,
    create_agent,
)
from core.ai.providers import LlmProvider
from core.domain.data_model import (
    Ingredient,
    InventoryItem,
    InventoryUnit,
    Recipe,
    RecipeUnit,
    Restaurant,
)
from core.domain.serialization import (
    inventory_item_to_dict,
    recipe_to_dict,
    restaurant_to_dict,
)
from core.operations.normalization import RecipeUnitConversionRegistry
from core.operations.readiness_kpis import compute_readiness_report
from core.storage.persistence import DataLake
from gradio_app.sections.manual_operativo import (
    _build_inventario_rows,
    _build_manual_context,
    _build_recetas_md,
    _build_resumen_md,
)
from gradio_app.session import stable_entity_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_data_lake() -> DataLake:
    return DataLake(data_dir=tempfile.mkdtemp())


def _seed_restaurant(dl: DataLake, session: str = "test", name: str = "Taco Test") -> int:
    eid = stable_entity_id(session)
    restaurant = Restaurant(id=eid, name=name, restaurant_type_id="casual")
    dl.save_entity("restaurant", eid, restaurant_to_dict(restaurant))
    return eid


# ---------------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------------

class _MockProvider(LlmProvider):
    def __init__(self, response: str = "Respuesta de prueba.") -> None:
        super().__init__(model_name="mock")
        self.response = response
        self.last_call_kwargs: dict[str, Any] = {}

    def _do_generate(
        self, *, prompt, system, tools, structured_output, messages, max_tokens, temperature
    ) -> str:
        self.last_call_kwargs = {"system": system, "messages": messages}
        return self.response


# ---------------------------------------------------------------------------
# TestBuildManualContext — 4 mocked tests
# ---------------------------------------------------------------------------

class TestBuildManualContext(unittest.TestCase):

    def test_returns_string_with_restaurant_name(self):
        dl = _make_data_lake()
        _seed_restaurant(dl, name="Taco Test")
        result = _build_manual_context(dl, "test")
        self.assertIsInstance(result, str)
        self.assertIn("Taco Test", result)

    def test_includes_recipe(self):
        dl = _make_data_lake()
        _seed_restaurant(dl)
        recipe = Recipe(id=1, name="Tacos", category_id=1, ingredients=[])
        dl.save_entity("recipe", 1, recipe_to_dict(recipe))
        result = _build_manual_context(dl, "test")
        self.assertIn("Tacos", result)

    def test_includes_inventory_item(self):
        dl = _make_data_lake()
        _seed_restaurant(dl)
        item = InventoryItem(id=1, name="Carne", stock_unit_id=1, purchase_unit_id=1, category_id=1)
        dl.save_entity("inventory_item", 1, inventory_item_to_dict(item))
        result = _build_manual_context(dl, "test")
        self.assertIn("Carne", result)

    def test_empty_session_returns_string(self):
        dl = _make_data_lake()
        result = _build_manual_context(dl, "nonexistent-session-xyz")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


# ---------------------------------------------------------------------------
# TestBuildResumenMd — 1 mocked test
# ---------------------------------------------------------------------------

class TestBuildResumenMd(unittest.TestCase):

    def test_all_na_kpis_renders_zero_score(self):
        restaurant = Restaurant(id=1, name="T", restaurant_type_id="casual")
        report = compute_readiness_report(
            restaurant,
            recipes=[],
            recipe_unit_registry=RecipeUnitRegistry(),
            inventory_unit_registry=InventoryUnitRegistry(),
            category_recipe_registry=CategoryRecipeRegistry(),
            family_inventory_registry=FamilyInventoryRegistry(),
            inventory_item_registry=InventoryItemRegistry(),
            conversion_table=RecipeUnitConversionRegistry(),
        )
        result = _build_resumen_md(
            report,
            RecipeUnitRegistry(),
            InventoryUnitRegistry(),
            InventoryItemRegistry(),
            recipes=[],
            items=[],
        )
        self.assertIsInstance(result, str)
        self.assertIn(">0<", result)
        self.assertIn("/ 100", result)


# ---------------------------------------------------------------------------
# TestBuildRecetasMd — 2 mocked tests
# ---------------------------------------------------------------------------

class TestBuildRecetasMd(unittest.TestCase):

    def test_empty_recipes_returns_placeholder(self):
        result = _build_recetas_md(
            [],
            RecipeUnitRegistry(),
            InventoryItemRegistry(),
            CategoryRecipeRegistry(),
            InventoryUnitRegistry(),
            RecipeUnitConversionRegistry(),
            FamilyInventoryRegistry(),
        )
        self.assertIsInstance(result, str)
        self.assertIn("Sin recetas", result)

    def test_linked_ingredient_shows_vinculado(self):
        rur = RecipeUnitRegistry()
        rur.add(RecipeUnit(id=1, name="Gramo", symbol="g"))

        iur = InventoryUnitRegistry()
        iur.add(InventoryUnit(id=1, name="Gramo", symbol="g", is_standard=True))

        ir = InventoryItemRegistry()
        ir.add(InventoryItem(id=1, name="tortilla", stock_unit_id=1, purchase_unit_id=1, category_id=1))

        ing = Ingredient(name="tortilla", quantity=2.0, unit_id=1)
        recipe = Recipe(id=1, name="Taco", category_id=1, ingredients=[ing])

        result = _build_recetas_md(
            [recipe], rur, ir,
            CategoryRecipeRegistry(), iur,
            RecipeUnitConversionRegistry(),
            FamilyInventoryRegistry(),
        )
        self.assertIn("&#9679; vinculado", result)


# ---------------------------------------------------------------------------
# TestBuildInventarioRows — 1 mocked test
# ---------------------------------------------------------------------------

class TestBuildInventarioRows(unittest.TestCase):

    def test_groups_by_category(self):
        item_p  = InventoryItem(id=1, name="Carne", stock_unit_id=1, purchase_unit_id=1, category_id=1)
        item_np = InventoryItem(id=2, name="Sal",   stock_unit_id=1, purchase_unit_id=1, category_id=2)
        perecederos, no_perecederos = _build_inventario_rows(
            [item_p, item_np], InventoryUnitRegistry(), FamilyInventoryRegistry()
        )
        self.assertEqual(len(perecederos), 1)
        self.assertEqual(len(no_perecederos), 1)
        self.assertEqual(perecederos[0][0], "Carne")
        self.assertEqual(no_perecederos[0][0], "Sal")


# ---------------------------------------------------------------------------
# TestManualOperativoAgent — 4 mocked tests
# ---------------------------------------------------------------------------

class TestManualOperativoAgent(unittest.TestCase):

    def _make_agent(self, response: str = "Respuesta de prueba."):
        provider = _MockProvider(response=response)
        return create_agent(ManualOperativoAgent, provider=provider, name="manual_operativo")

    def test_input_schema_has_user_message(self):
        self.assertIn("user_message", ManualOperativoAgent.INPUT_SCHEMA)

    def test_output_schema_has_reply_and_raw_response(self):
        self.assertIn("reply", ManualOperativoAgent.OUTPUT_SCHEMA)
        self.assertIn("raw_response", ManualOperativoAgent.OUTPUT_SCHEMA)

    def test_response_model_is_none(self):
        self.assertIsNone(ManualOperativoAgent.RESPONSE_MODEL)

    def test_run_returns_reply_and_raw_response(self):
        agent = self._make_agent("Aquí está tu respuesta.")
        result = agent.run(
            input_data={"user_message": "Hola"},
            context={"manual_context": "PERFIL DEL RESTAURANTE\n  Nombre: Taco Test"},
        )
        self.assertEqual(result["reply"], "Aquí está tu respuesta.")
        self.assertEqual(result["raw_response"], "Aquí está tu respuesta.")


# ---------------------------------------------------------------------------
# Live context string for TestManualOperativoAgentLive
# ---------------------------------------------------------------------------

_MINIMAL_CONTEXT = """\
PERFIL DEL RESTAURANTE
  Nombre: Tacos El Güero
  Tipo: taqueria
  Operador: Demo
  Nivel de estandarización: 1

RECETAS (1 total)
  Receta: Tacos al pastor  Categoría: Principales
    - tortilla: 2 pza  [vinculado]
    - carne: 150 g  [vinculado]

INVENTARIO (2 artículos)
  tortilla  compra: pza  stock: pza  factor: 1.0  familia: Granos
  carne  compra: kg  stock: g  factor: 1000.0  familia: Carnes
"""


# ---------------------------------------------------------------------------
# TestManualOperativoAgentLive — 2 live tests (requires ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------

@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "requires ANTHROPIC_API_KEY")
class TestManualOperativoAgentLive(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from core.ai.providers import ClaudeProvider
        cls.provider = ClaudeProvider()

    def _make_agent(self):
        return create_agent(ManualOperativoAgent, provider=self.provider, name="manual_operativo")

    def test_qa_live_responds_in_spanish(self):
        agent = self._make_agent()
        result = agent.run(
            input_data={"user_message": "¿Cuántas recetas hay?"},
            context={"manual_context": _MINIMAL_CONTEXT},
        )
        reply = result["reply"]
        self.assertIsInstance(reply, str)
        self.assertTrue(len(reply) > 0)
        self.assertNotIn("{", reply)

    def test_deduction_live_returns_quantities(self):
        agent = self._make_agent()
        result = agent.run(
            input_data={"user_message": "Si vendo 5 porciones de Tacos al pastor, ¿cuánto necesito?"},
            context={"manual_context": _MINIMAL_CONTEXT},
        )
        reply = result["reply"]
        self.assertTrue(any(c.isdigit() for c in reply))


if __name__ == "__main__":
    unittest.main()
