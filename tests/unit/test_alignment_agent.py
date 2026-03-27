"""
Tests for AlignmentAgent — recipe extraction, inventory proposal, context loading,
confirm/save flow, persistence roundtrip, and utility functions.

Tests 1–21: mocked (offline, no API key required).
Tests 22–23: live (skipped unless ANTHROPIC_API_KEY is set).
"""

import json
import os
import tempfile
import unittest
from typing import Any

from core.agents.alignment_agent import AlignmentAgent
from core.agents.utils import create_agent
from core.ai.providers import LlmProvider
from core.domain.data_model import (
    CategoryRecipe,
    FamilyInventory,
    Ingredient,
    InventoryItem,
    InventoryUnit,
    Recipe,
    RecipeUnit,
    is_standard_recipe_unit,
)
from core.domain.data_model_utils import ingredients_to_display
from core.domain.serialization import (
    category_recipe_to_dict,
    family_inventory_to_dict,
    inventory_item_to_dict,
    inventory_unit_to_dict,
    recipe_unit_conversion_to_dict,
    recipe_unit_to_dict,
)
from core.operations.normalization import (
    RecipeUnitConversionEntry,
    RecipeUnitConversionKey,
)
from core.storage.persistence import DataLake
from gradio_app.sections.alineamiento import _load_alignment_context, _make_confirm_fn


# ---------------------------------------------------------------------------
# DataLake helpers
# ---------------------------------------------------------------------------

def _make_data_lake() -> DataLake:
    """JSON-backed DataLake for general entity tests."""
    return DataLake(data_dir=tempfile.mkdtemp())


def _make_sqlite_data_lake() -> DataLake:
    """SQLite-backed DataLake required for recipe_unit_conversion and confirm tests."""
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return DataLake(db_path=f.name)


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

def _alignment_response(
    reply: str = "Entendido.",
    recipe_name: str | None = None,
    recipe_category: str | None = None,
    recipe_description: str | None = None,
    recipe_steps: list | None = None,
    ingredients: list | None = None,
    inventory_proposals: list | None = None,
    show_file_upload: bool = False,
) -> str:
    return json.dumps({
        "reply":               reply,
        "recipe_name":         recipe_name,
        "recipe_category":     recipe_category,
        "recipe_description":  recipe_description,
        "recipe_steps":        recipe_steps,
        "ingredients":         ingredients,
        "inventory_proposals": inventory_proposals,
        "show_file_upload":    show_file_upload,
    })


# ---------------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------------

class _MockProvider(LlmProvider):
    def __init__(self, response: str | None = None) -> None:
        super().__init__(model_name="mock")
        self.response = response or _alignment_response()
        self.last_system: str = ""
        self.call_count: int = 0

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
        self.call_count += 1
        return self.response


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_recipe_unit(dl: DataLake, uid: int, symbol: str) -> None:
    ru = RecipeUnit(id=uid, name=symbol, symbol=symbol)
    dl.save_entity("recipe_unit", uid, recipe_unit_to_dict(ru))


def _seed_inventory_unit(dl: DataLake, uid: int, symbol: str) -> None:
    iu = InventoryUnit(id=uid, name=symbol, symbol=symbol, is_standard=True, factor_to_base=1.0)
    dl.save_entity("inventory_unit", uid, inventory_unit_to_dict(iu))


def _seed_category_recipe(dl: DataLake, cid: int, name: str) -> None:
    cat = CategoryRecipe(id=cid, name=name)
    dl.save_entity("category_recipe", cid, category_recipe_to_dict(cat))


def _seed_family_inventory(dl: DataLake, fid: int, name: str) -> None:
    fam = FamilyInventory(id=fid, name=name)
    dl.save_entity("family_inventory", fid, family_inventory_to_dict(fam))


def _seed_inventory_item(dl: DataLake, iid: int, name: str) -> None:
    item = InventoryItem(id=iid, name=name, stock_unit_id=1, purchase_unit_id=1, category_id=1)
    dl.save_entity("inventory_item", iid, inventory_item_to_dict(item))


# ---------------------------------------------------------------------------
# TestAlignmentAgentCore — tests 1–7, 17–21
# ---------------------------------------------------------------------------

class TestAlignmentAgentCore(unittest.TestCase):

    def _make_agent(self, response: str | None = None):
        provider = _MockProvider(response=response)
        agent = create_agent(AlignmentAgent, provider=provider, name="alignment_agent")
        return agent, provider

    # --- Test 1 ---
    def test_extracts_recipe_from_plain_text(self):
        resp = _alignment_response(
            recipe_name="Tacos de pollo",
            recipe_category="Platillos",
            ingredients=[{"name": "Pollo", "quantity": 200, "unit_symbol": "g",
                          "inventory_link_status": "new"}],
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "Mi receta es tacos de pollo",
                        "recipe_source": "conversation", "page_index": 0},
            context={},
        )
        self.assertEqual(result["recipe_draft"]["recipe_name"], "Tacos de pollo")
        self.assertEqual(result["recipe_draft"]["recipe_category"], "Platillos")
        self.assertEqual(len(result["recipe_draft"]["ingredients"]), 1)

    # --- Test 2 ---
    def test_matches_existing_inventory_item(self):
        resp = _alignment_response(
            recipe_name="Sopa",
            ingredients=[{
                "name": "Zanahoria", "quantity": 100, "unit_symbol": "g",
                "inventory_link_status": "matched_existing",
                "matched_item_name": "Zanahoria",
            }],
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "Sopa de zanahoria",
                        "recipe_source": "conversation", "page_index": 0},
            context={"existing_inventory_items": ["Zanahoria"]},
        )
        ing = result["recipe_draft"]["ingredients"][0]
        self.assertEqual(ing["inventory_link_status"], "matched_existing")
        self.assertEqual(ing["matched_item_name"], "Zanahoria")

    # --- Test 3 ---
    def test_proposes_new_inventory_item_with_category_and_family(self):
        resp = _alignment_response(
            recipe_name="Pasta",
            inventory_proposals=[{
                "name": "Pasta seca", "category": "No perecedero",
                "family": "Granos", "status": "new",
            }],
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "Pasta con tomate",
                        "recipe_source": "conversation", "page_index": 0},
            context={"families": ["Granos"]},
        )
        proposal = result["inventory_proposals"][0]
        self.assertEqual(proposal["category"], "No perecedero")
        self.assertEqual(proposal["family"], "Granos")
        self.assertEqual(proposal["status"], "new")

    # --- Test 4 ---
    def test_nonstandard_unit_per_ingredient_equivalent(self):
        resp = _alignment_response(
            recipe_name="Pan",
            ingredients=[{
                "name": "Harina", "quantity": 1, "unit_symbol": "taza",
                "equivalent": "≈ 120 g", "inventory_link_status": "new",
            }],
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "1 taza de harina",
                        "recipe_source": "conversation", "page_index": 0},
            context={},
        )
        ing = result["recipe_draft"]["ingredients"][0]
        self.assertEqual(ing["equivalent"], "≈ 120 g")

    # --- Test 5 ---
    def test_per_ingredient_equivalent_differs_by_ingredient(self):
        resp = _alignment_response(
            recipe_name="Arroz con leche",
            ingredients=[
                {"name": "Harina", "quantity": 1, "unit_symbol": "taza",
                 "equivalent": "≈ 120 g", "inventory_link_status": "new"},
                {"name": "Arroz", "quantity": 1, "unit_symbol": "taza",
                 "equivalent": "≈ 185 g", "inventory_link_status": "new"},
            ],
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "1 taza harina, 1 taza arroz",
                        "recipe_source": "conversation", "page_index": 0},
            context={},
        )
        ings = result["recipe_draft"]["ingredients"]
        eq_harina = next(i["equivalent"] for i in ings if i["name"] == "Harina")
        eq_arroz  = next(i["equivalent"] for i in ings if i["name"] == "Arroz")
        self.assertNotEqual(eq_harina, eq_arroz)

    # --- Test 6 ---
    def test_no_hallucination_on_sparse_input(self):
        resp = _alignment_response(
            recipe_name="Caldo",
            ingredients=[{"name": "Agua", "quantity": 1, "unit_symbol": "L",
                          "inventory_link_status": "new"}],
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "Solo agua",
                        "recipe_source": "conversation", "page_index": 0},
            context={},
        )
        self.assertEqual(len(result["recipe_draft"]["ingredients"]), 1)
        self.assertEqual(result["recipe_draft"]["ingredients"][0]["name"], "Agua")

    # --- Test 7 ---
    def test_draft_accumulates_across_turns(self):
        resp1 = _alignment_response(recipe_name="Pozole")
        resp2 = _alignment_response(recipe_name="Pozole", recipe_category="Sopas")
        dl = _make_data_lake()

        agent = create_agent(AlignmentAgent, provider=_MockProvider(resp1), name="alignment_agent")
        agent.run(
            input_data={"user_message": "Se llama Pozole",
                        "recipe_source": "conversation", "page_index": 0},
            context={},
        )
        agent.save_state(dl, session_id="test_turn")

        agent2 = create_agent(AlignmentAgent, provider=_MockProvider(resp2), name="alignment_agent")
        agent2.load_state(dl, session_id="test_turn")
        result2 = agent2.run(
            input_data={"user_message": "Es una sopa",
                        "recipe_source": "conversation", "page_index": 0},
            context={},
        )
        self.assertEqual(result2["recipe_draft"]["recipe_name"], "Pozole")
        self.assertEqual(result2["recipe_draft"]["recipe_category"], "Sopas")

    # --- Test 17 ---
    def test_create_entity_tool_creates_category(self):
        dl = _make_data_lake()
        agent = create_agent(AlignmentAgent, provider=_MockProvider(), name="alignment_agent")
        agent._data_lake = dl
        agent._context = {"categories": []}
        result = agent._create_entity_tool("category_recipe", "Postres")
        self.assertIn("Postres", result)
        ids = dl.list_entity_ids("category_recipe")
        self.assertEqual(len(ids), 1)
        entity = dl.load_entity("category_recipe", ids[0])
        self.assertEqual(entity["name"], "Postres")

    # --- Test 18 ---
    def test_create_entity_tool_creates_recipe_unit(self):
        dl = _make_data_lake()
        agent = create_agent(AlignmentAgent, provider=_MockProvider(), name="alignment_agent")
        agent._data_lake = dl
        agent._context = {"recipe_units": []}
        result = agent._create_entity_tool("recipe_unit", "Manojo", symbol="manojo")
        self.assertIn("manojo", result)
        ids = dl.list_entity_ids("recipe_unit")
        entity = dl.load_entity("recipe_unit", ids[0])
        self.assertEqual(entity["symbol"], "manojo")

    # --- Test 19 ---
    def test_create_entity_tool_updates_agent_context(self):
        dl = _make_data_lake()
        agent = create_agent(AlignmentAgent, provider=_MockProvider(), name="alignment_agent")
        agent._data_lake = dl
        agent._context = {"categories": ["Entradas"]}
        agent._create_entity_tool("category_recipe", "Postres")
        self.assertIn("Postres", agent._context["categories"])

    # --- Test 20 ---
    def test_agent_does_not_create_without_confirmation(self):
        dl = _make_data_lake()
        resp = _alignment_response(
            reply="¿Quieres usar 'Entradas' o crear una nueva categoría?"
        )
        agent = create_agent(AlignmentAgent, provider=_MockProvider(resp), name="alignment_agent")
        agent.run(
            input_data={"user_message": "Tengo una categoría nueva",
                        "recipe_source": "conversation", "page_index": 0},
            context={"data_lake": dl, "session_id": "test"},
        )
        self.assertEqual(dl.list_entity_ids("category_recipe"), [])

    # --- Test 21 ---
    def test_missing_steps_asks_once_then_saves_none(self):
        resp = _alignment_response(
            recipe_name="Guisado",
            recipe_steps=None,
            reply="No encontré los pasos. ¿Me los puedes dictar?",
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "Solo tengo ingredientes",
                        "recipe_source": "conversation", "page_index": 0},
            context={},
        )
        self.assertIsNone(result["recipe_draft"].get("recipe_steps"))


# ---------------------------------------------------------------------------
# TestAlignmentContext — tests 8–9
# ---------------------------------------------------------------------------

class TestAlignmentContext(unittest.TestCase):

    # --- Test 8 ---
    def test_load_alignment_context_all_keys_present(self):
        dl = _make_data_lake()
        _seed_category_recipe(dl, 1, "Entradas")
        _seed_family_inventory(dl, 1, "Lácteos")
        _seed_recipe_unit(dl, 1, "g")
        _seed_inventory_unit(dl, 1, "g")
        _seed_inventory_item(dl, 1, "Leche")

        ctx = _load_alignment_context(dl, "test_session")

        for key in ("restaurant_name", "restaurant_type", "restaurant_description",
                    "standardization_level", "categories", "families",
                    "recipe_units", "inventory_units", "existing_inventory_items",
                    "data_lake", "session_id"):
            self.assertIn(key, ctx)
        self.assertIn("Entradas", ctx["categories"])
        self.assertIn("Lácteos", ctx["families"])
        self.assertIn("g", ctx["recipe_units"])
        self.assertIn("Leche", ctx["existing_inventory_items"])

    # --- Test 9 ---
    def test_load_alignment_context_defaults_on_empty_datalake(self):
        dl = _make_data_lake()
        ctx = _load_alignment_context(dl, "empty_session")
        self.assertEqual(ctx["categories"], [])
        self.assertEqual(ctx["families"], [])
        self.assertEqual(ctx["existing_inventory_items"], [])
        self.assertEqual(ctx["standardization_level"], 1)


# ---------------------------------------------------------------------------
# TestAlignmentConfirm — tests 10–12
# ---------------------------------------------------------------------------

class TestAlignmentConfirm(unittest.TestCase):

    def _setup_dl(self):
        """SQLite DataLake seeded with minimum required entities."""
        dl = _make_sqlite_data_lake()
        _seed_recipe_unit(dl, 1, "g")
        _seed_inventory_unit(dl, 1, "g")
        _seed_category_recipe(dl, 1, "Entradas")
        _seed_family_inventory(dl, 1, "Lácteos")
        return dl

    def _run_confirm(self, dl, draft, proposals):
        confirm_fn = _make_confirm_fn(dl)
        results = list(confirm_fn(draft, proposals, "test_session"))
        return results

    # --- Test 10 ---
    def test_confirm_saves_recipe_to_datalake(self):
        dl = self._setup_dl()
        draft = {
            "recipe_name": "Tacos", "recipe_category": "Entradas",
            "ingredients": [{"name": "Pollo", "quantity": 200, "unit_symbol": "g"}],
        }
        results = self._run_confirm(dl, draft, [])
        status, success = results[-1]
        self.assertTrue(success)
        ids = dl.list_entity_ids("recipe")
        self.assertEqual(len(ids), 1)
        entity = dl.load_entity("recipe", ids[0])
        self.assertEqual(entity["name"], "Tacos")

    # --- Test 11 ---
    def test_confirm_saves_new_inventory_items(self):
        dl = self._setup_dl()
        draft = {
            "recipe_name": "Arroz", "recipe_category": "Entradas",
            "ingredients": [{"name": "Arroz", "quantity": 200, "unit_symbol": "g"}],
        }
        proposals = [{"name": "Arroz", "category": "No perecedero", "family": None, "status": "new"}]
        self._run_confirm(dl, draft, proposals)
        ids = dl.list_entity_ids("inventory_item")
        names = [dl.load_entity("inventory_item", i)["name"] for i in ids]
        self.assertIn("Arroz", names)

    # --- Test 12 ---
    def test_confirm_links_ingredient_to_existing_item(self):
        dl = self._setup_dl()
        _seed_inventory_item(dl, 1, "Pollo")
        draft = {
            "recipe_name": "Pollo asado", "recipe_category": "Entradas",
            "ingredients": [{"name": "Pollo", "quantity": 500, "unit_symbol": "g"}],
        }
        proposals = [{"name": "Pollo", "category": "Perecedero", "family": None,
                      "status": "matched_existing"}]
        self._run_confirm(dl, draft, proposals)
        recipe_ids = dl.list_entity_ids("recipe")
        recipe = dl.load_entity("recipe", recipe_ids[0])
        ing = recipe["ingredients"][0]
        self.assertIsNotNone(ing.get("inventory_item_id"))


# ---------------------------------------------------------------------------
# TestAlignmentPersistence — test 13
# ---------------------------------------------------------------------------

class TestAlignmentPersistence(unittest.TestCase):

    # --- Test 13 ---
    def test_recipe_unit_conversion_roundtrip(self):
        dl = _make_sqlite_data_lake()
        key = RecipeUnitConversionKey(recipe_unit_id=1, family_id=None, inventory_item_id=5)
        entry = RecipeUnitConversionEntry(quantity=120.0, base_unit_id=2,
                                          source="agent_confirmed")
        composite_id = f"{key.recipe_unit_id}_{key.family_id}_{key.inventory_item_id}"
        dl.save_entity("recipe_unit_conversion", composite_id,
                       recipe_unit_conversion_to_dict(entry, key))

        loaded = dl.load_entity("recipe_unit_conversion", composite_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["quantity"], 120.0)
        self.assertEqual(loaded["source"], "agent_confirmed")
        self.assertIsNone(loaded.get("family_id"))
        self.assertEqual(loaded["inventory_item_id"], 5)


# ---------------------------------------------------------------------------
# TestAlignmentUtils — tests 14–16
# ---------------------------------------------------------------------------

class TestAlignmentUtils(unittest.TestCase):

    # --- Test 14 ---
    def test_ingredients_to_display_equivalent_and_status_columns(self):
        from core.domain.data_model import RecipeUnitRegistry
        ru = RecipeUnit(id=1, name="gramo", symbol="g")
        reg = RecipeUnitRegistry()
        reg.add(ru)
        recipe = Recipe(
            id=1, name="Test", category_id=1,
            ingredients=[Ingredient(name="Sal", quantity=5.0, unit_id=1)],
        )
        rows = ingredients_to_display(recipe, reg)
        self.assertEqual(len(rows), 1)
        self.assertIn("equivalent", rows[0])
        self.assertIn("inventory_link_status", rows[0])

    # --- Test 15 ---
    def test_is_standard_recipe_unit_true_for_standard(self):
        for sym in ("g", "kg", "ml", "L", "pza"):
            with self.subTest(sym=sym):
                self.assertTrue(is_standard_recipe_unit(sym))

    # --- Test 16 ---
    def test_is_standard_recipe_unit_false_for_nonstandard(self):
        for sym in ("taza", "cda", "cdta", "oz", "manojo", "pizca"):
            with self.subTest(sym=sym):
                self.assertFalse(is_standard_recipe_unit(sym))


# ---------------------------------------------------------------------------
# Live tests — tests 22–23
# ---------------------------------------------------------------------------

@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY not set")
class TestAlignmentAgentLive(unittest.TestCase):

    def _make_live_agent(self):
        from core.ai.providers import ClaudeProvider
        provider = ClaudeProvider()
        return create_agent(AlignmentAgent, provider=provider, name="alignment_agent_live")

    # --- Test 22 ---
    def test_live_alignment_agent_spanish_recipe_text(self):
        agent = self._make_live_agent()
        result = agent.run(
            input_data={
                "user_message": "Mi receta es guacamole: 2 aguacates, 1 limón, sal al gusto.",
                "recipe_source": "conversation",
                "page_index": 0,
            },
            context={},
        )
        self.assertTrue(result["recipe_draft"].get("recipe_name"))
        self.assertGreaterEqual(len(result["recipe_draft"].get("ingredients") or []), 1)

    # --- Test 23 ---
    def test_live_alignment_agent_multi_recipe_pagination(self):
        agent = self._make_live_agent()
        result0 = agent.run(
            input_data={
                "user_message": "[Contenido de archivo, receta #1]\nTacos de pollo: 300g pollo, 6 tortillas.",
                "recipe_source": "file_content",
                "page_index": 0,
            },
            context={},
        )
        result1 = agent.run(
            input_data={
                "user_message": "[Contenido de archivo, receta #2]\nGuacamole: 2 aguacates, sal.",
                "recipe_source": "file_content",
                "page_index": 1,
            },
            context={},
        )
        name0 = result0["recipe_draft"].get("recipe_name", "")
        name1 = result1["recipe_draft"].get("recipe_name", "")
        self.assertTrue(name0 or name1)


if __name__ == "__main__":
    unittest.main()
