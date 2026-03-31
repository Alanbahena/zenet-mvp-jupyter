"""
Tests for StructuringAgent — batch inference, context injection, data store
accumulation, confirm/save flow, and live LLM compliance.

Tests 1–12: mocked (offline, no API key required).
Tests 13–14: live (skipped unless ANTHROPIC_API_KEY is set).
"""

import json
import os
import tempfile
import unittest

from core.agents.structuring_agent import StructuringAgent
from core.agents.utils import create_agent
from core.ai.providers import LlmProvider
from core.domain.data_model import FamilyInventory, InventoryItem, InventoryUnit
from core.domain.serialization import (
    family_inventory_to_dict,
    inventory_item_to_dict,
    inventory_unit_to_dict,
)
from core.storage.persistence import DataLake
from gradio_app.sections.estructura import _make_confirm_fn


# ---------------------------------------------------------------------------
# DataLake helper
# ---------------------------------------------------------------------------

def _make_data_lake() -> DataLake:
    """JSON-backed DataLake for all structuring tests."""
    return DataLake(data_dir=tempfile.mkdtemp())


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

def _structuring_response(
    reply: str = "Ok.",
    proposals: list | None = None,
    gap_questions: list | None = None,
    needs_supplier_doc: bool | None = None,
) -> str:
    return json.dumps({
        "reply":              reply,
        "proposals":          proposals,
        "gap_questions":      gap_questions,
        "needs_supplier_doc": needs_supplier_doc,
    })


def _proposal(
    name: str = "Pollo",
    stock_unit_symbol: str = "kg",
    purchase_unit_symbol: str = "kg",
    purchase_to_stock_factor: float | None = 1.0,
    family_name: str | None = None,
    category_name: str = "Perecedero",
    confidence: str = "high",
    is_new_item: bool = False,
    description: str | None = None,
) -> dict:
    return {
        "name":                    name,
        "stock_unit_symbol":       stock_unit_symbol,
        "purchase_unit_symbol":    purchase_unit_symbol,
        "purchase_to_stock_factor": purchase_to_stock_factor,
        "family_name":             family_name,
        "category_name":           category_name,
        "confidence":              confidence,
        "is_new_item":             is_new_item,
        "description":             description,
    }


# ---------------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------------

class _MockProvider(LlmProvider):
    def __init__(self, response: str | None = None) -> None:
        super().__init__(model_name="mock")
        self.response = response or _structuring_response()
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

def _seed_inventory_unit(
    dl: DataLake, uid: int, symbol: str, is_standard: bool = True
) -> None:
    iu = InventoryUnit(id=uid, name=symbol, symbol=symbol, is_standard=is_standard, factor_to_base=1.0)
    dl.save_entity("inventory_unit", uid, inventory_unit_to_dict(iu))


def _seed_inventory_item(
    dl: DataLake, iid: int, name: str, category_id: int = 1
) -> None:
    item = InventoryItem(
        id=iid, name=name,
        stock_unit_id=1, purchase_unit_id=1,
        category_id=category_id,
    )
    dl.save_entity("inventory_item", iid, inventory_item_to_dict(item))


def _seed_family_inventory(dl: DataLake, fid: int, name: str) -> None:
    fam = FamilyInventory(id=fid, name=name)
    dl.save_entity("family_inventory", fid, family_inventory_to_dict(fam))


# ---------------------------------------------------------------------------
# TestStructuringAgentCore — tests 1–11
# ---------------------------------------------------------------------------

class TestStructuringAgentCore(unittest.TestCase):

    def _make_agent(self, response: str | None = None):
        provider = _MockProvider(response=response)
        agent = create_agent(StructuringAgent, provider=provider, name="structuring_agent")
        return agent, provider

    # --- Test 1 ---
    def test_create_via_factory(self):
        agent, _ = self._make_agent()
        self.assertIsInstance(agent, StructuringAgent)
        self.assertIsNotNone(agent.tools)
        self.assertIn("create_inventory_unit", agent.tools._tools)
        self.assertIn("create_family_inventory", agent.tools._tools)

    # --- Test 2 ---
    def test_response_model_fields(self):
        resp = _structuring_response(
            reply="Propuesta generada.",
            proposals=[_proposal()],
            gap_questions=[],
            needs_supplier_doc=False,
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "Aquí está mi inventario.", "category": "Perecedero"},
            context={},
        )
        for key in ("reply", "proposals", "gap_questions", "needs_supplier_doc", "raw_response"):
            self.assertIn(key, result)

    # --- Test 3 ---
    def test_bulk_inference_standard_units(self):
        resp = _structuring_response(
            proposals=[_proposal(
                stock_unit_symbol="kg",
                purchase_unit_symbol="kg",
                purchase_to_stock_factor=1.0,
                confidence="high",
            )],
            gap_questions=[],
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "Bistec por kilo.", "category": "Perecedero"},
            context={},
        )
        self.assertEqual(result["proposals"][0]["purchase_to_stock_factor"], 1.0)
        self.assertEqual(result["gap_questions"], [])

    # --- Test 4 ---
    def test_bulk_inference_non_standard_unit(self):
        resp = _structuring_response(
            proposals=[_proposal(
                name="Harina",
                stock_unit_symbol="kg",
                purchase_unit_symbol="costal",
                purchase_to_stock_factor=None,
                confidence="missing",
            )],
            gap_questions=["¿Cuántos kg tiene un costal de Harina?"],
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "Harina en costal.", "category": "No perecedero"},
            context={},
        )
        self.assertIsNone(result["proposals"][0]["purchase_to_stock_factor"])
        self.assertGreaterEqual(len(result["gap_questions"]), 1)

    # --- Test 5 ---
    def test_missing_purchase_unit_flag(self):
        resp = _structuring_response(
            reply="¿Tienes un recibo de proveedor?",
            needs_supplier_doc=True,
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "No sé las unidades.", "category": "Perecedero"},
            context={},
        )
        self.assertTrue(result["needs_supplier_doc"])

    # --- Test 6 ---
    def test_no_equivalence_for_pza(self):
        resp = _structuring_response(
            proposals=[_proposal(
                name="Limón",
                stock_unit_symbol="pza",
                purchase_unit_symbol="pza",
                purchase_to_stock_factor=1.0,
                confidence="high",
            )],
            gap_questions=[],
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "Limón por pieza.", "category": "Perecedero"},
            context={},
        )
        self.assertEqual(result["gap_questions"], [])
        self.assertEqual(result["proposals"][0]["purchase_to_stock_factor"], 1.0)

    # --- Test 7 ---
    def test_new_item_detection(self):
        resp = _structuring_response(
            proposals=[_proposal(name="Salsa nueva", is_new_item=True)],
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "Salsa nueva que no estaba antes.", "category": "Perecedero"},
            context={},
        )
        self.assertTrue(result["proposals"][0]["is_new_item"])

    # --- Test 8 ---
    def test_data_store_accumulation(self):
        dl = _make_data_lake()
        resp1 = _structuring_response(proposals=[_proposal(name="Pollo")])
        resp2 = _structuring_response(proposals=[_proposal(name="Cebolla")])

        agent1 = create_agent(StructuringAgent, provider=_MockProvider(resp1), name="sa")
        agent1.run(
            input_data={"user_message": "Primer turno.", "category": "Perecedero"},
            context={},
        )
        agent1.save_state(dl, session_id="test_accum")

        agent2 = create_agent(StructuringAgent, provider=_MockProvider(resp2), name="sa")
        agent2.load_state(dl, session_id="test_accum")
        agent2.run(
            input_data={"user_message": "Segundo turno.", "category": "Perecedero"},
            context={},
        )

        # store() is replace — latest proposals are "Cebolla" batch
        stored = agent2.retrieve("proposals", [])
        self.assertTrue(len(stored) >= 1)
        self.assertEqual(stored[0]["name"], "Cebolla")

    # --- Test 9 ---
    def test_perecedero_category_inference(self):
        resp = _structuring_response(
            proposals=[_proposal(name="Jitomate", category_name="Perecedero")],
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "Jitomate.", "category": "Perecedero"},
            context={},
        )
        self.assertEqual(result["proposals"][0]["category_name"], "Perecedero")

    # --- Test 10 ---
    def test_no_perecedero_category_inference(self):
        resp = _structuring_response(
            proposals=[_proposal(name="Aceite", category_name="No perecedero")],
        )
        agent, _ = self._make_agent(resp)
        result = agent.run(
            input_data={"user_message": "Aceite.", "category": "No perecedero"},
            context={},
        )
        self.assertEqual(result["proposals"][0]["category_name"], "No perecedero")

    # --- Test 11 ---
    def test_context_injection(self):
        resp = _structuring_response(proposals=[_proposal()])
        agent, provider = self._make_agent(resp)
        agent.run(
            input_data={"user_message": "Inventario.", "category": "Perecedero"},
            context={
                "restaurant_name":  "El Paisa",
                "restaurant_type":  "Taquería",
                "families":         ["Lácteos"],
                "inventory_units":  ["kg"],
                "inventory_items":  ["Pollo"],
                "category":         "Perecedero",
            },
        )
        self.assertIn("El Paisa", provider.last_system)
        self.assertIn("Lácteos", provider.last_system)


# ---------------------------------------------------------------------------
# TestStructuringConfirm — test 12
# ---------------------------------------------------------------------------

class TestStructuringConfirm(unittest.TestCase):

    # --- Test 12 ---
    def test_confirm_fn_saves_inventory_items(self):
        dl = _make_data_lake()
        _seed_inventory_unit(dl, 1, "kg")
        _seed_inventory_item(dl, 1, "Pollo", category_id=1)

        confirm_fn = _make_confirm_fn(dl)
        rows = [["Pollo", "kg", "kg", 1.0, "", "Perecedero"]]
        results = list(confirm_fn(rows, "test_session", "Perecedero"))

        # Final yield must be success
        status, success = results[-1]
        self.assertTrue(success)

        # Existing shell must be enriched — not duplicated
        ids = dl.list_entity_ids("inventory_item")
        self.assertEqual(len(ids), 1)

        entity = dl.load_entity("inventory_item", ids[0])
        self.assertEqual(entity["stock_unit_id"], 1)
        self.assertEqual(entity["purchase_unit_id"], 1)
        self.assertEqual(entity["purchase_to_stock_factor"], 1.0)


# ---------------------------------------------------------------------------
# Live tests — tests 13–14
# ---------------------------------------------------------------------------

@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY not set")
class TestStructuringAgentLive(unittest.TestCase):

    def _make_live_agent(self):
        from core.ai.providers import ClaudeProvider
        provider = ClaudeProvider()
        return create_agent(StructuringAgent, provider=provider, name="structuring_agent_live")

    # --- Test 13 ---
    def test_live_bulk_inference_taqueria(self):
        agent = self._make_live_agent()
        result = agent.run(
            input_data={
                "user_message": (
                    "[Contenido de archivo]\n"
                    "Bistec, Limón, Cilantro, Tortillas, Cebolla"
                ),
                "recipe_source": "file_content",
                "category": "Perecedero",
            },
            context={
                "restaurant_name":  "Tacos El Paisa",
                "restaurant_type":  "Taquería",
                "inventory_items":  [],
                "inventory_units":  ["kg", "g", "pza"],
                "families":         [],
                "category":         "Perecedero",
            },
        )
        proposals = result.get("proposals") or []
        self.assertGreater(len(proposals), 0)
        for p in proposals:
            self.assertIn("stock_unit_symbol", p)
            self.assertIn("purchase_unit_symbol", p)

    # --- Test 14 ---
    def test_live_gap_question_non_standard_unit(self):
        agent = self._make_live_agent()
        result = agent.run(
            input_data={
                "user_message": "Compro harina en costales, no sé cuántos kg tiene cada uno.",
                "category": "No perecedero",
            },
            context={
                "restaurant_name":  "Panadería Central",
                "restaurant_type":  "Panadería",
                "inventory_items":  ["Harina"],
                "inventory_units":  ["kg", "g"],
                "families":         [],
                "category":         "No perecedero",
            },
        )
        proposals = result.get("proposals") or []
        gap_questions = result.get("gap_questions") or []
        # Either a gap question was generated or the factor was left null
        has_gap = len(gap_questions) >= 1
        has_null_factor = any(
            p.get("purchase_to_stock_factor") is None for p in proposals
        )
        self.assertTrue(has_gap or has_null_factor)


if __name__ == "__main__":
    unittest.main()
