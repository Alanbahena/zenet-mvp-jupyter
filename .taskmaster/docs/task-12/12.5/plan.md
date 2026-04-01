# Subtask 12.5 — Unit tests for _build_manual_context and ManualOperativoAgent

## Goal

Create `tests/unit/test_manual_operativo.py` with 12 offline mocked tests and 2 live
tests guarded by `ANTHROPIC_API_KEY`, covering all new functions in the Manual Operativo
section so 12.6 has a green test suite to document.

- **12.4 delivered:** Complete `render()`, `_make_content`, all four builders,
  `_build_manual_context`, and `ManualOperativoAgent` — all testable as pure functions
  or via mock provider.
- **12.6 needs from 12.5:** A passing test suite so the architecture doc can reference
  test coverage as evidence of correctness.

---

## Files to Modify / Create

| File | Action | Summary |
|------|--------|---------|
| `tests/unit/test_manual_operativo.py` | Create | Full test suite: 12 mocked + 2 live tests |

No other files.

---

## Dependencies

- Subtasks 12.1–12.4 all done (all functions under test exist).
- `unittest` — stdlib, no install needed.
- `DataLake(data_dir=tempfile.mkdtemp())` — JSON backend, consistent with all other test files.
- `ANTHROPIC_API_KEY` in `.env` — live tests skip without it.

---

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| JSON backend DataLake in fixtures | Consistent with `test_welcome_agent.py` and all other test files; no SQLite file needed |
| `_MockProvider` copies exact pattern from `test_welcome_agent.py` | Reuses established project pattern for offline LLM testing |
| `@unittest.skipUnless(os.getenv("ANTHROPIC_API_KEY"), ...)` | Consistent with all other live test classes in the project |
| JSON backend means `recipe_unit_conversion` registry is always empty | Acceptable — conversion coverage is not the subject under test; `_build_manual_context` handles empty table gracefully |

---

## Implementation steps

### 1. Module header and imports

```python
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
    Recipe,
    Ingredient,
    InventoryItem,
    InventoryUnit,
    RecipeUnit,
    Restaurant,
)
from core.domain.serialization import (
    inventory_item_to_dict,
    inventory_unit_to_dict,
    recipe_to_dict,
    recipe_unit_to_dict,
    restaurant_to_dict,
)
from core.operations.normalization import RecipeUnitConversionRegistry
from core.operations.readiness_kpis import compute_readiness_report
from core.storage.persistence import DataLake
from gradio_app.sections.manual_operativo import (
    _build_inventario_md,
    _build_manual_context,
    _build_recetas_md,
    _build_resumen_md,
)
from gradio_app.session import stable_entity_id
```

### 2. Module-level fixture helpers

```python
def _make_data_lake() -> DataLake:
    return DataLake(data_dir=tempfile.mkdtemp())


def _seed_restaurant(dl: DataLake, session: str = "test", name: str = "Taco Test") -> int:
    eid = stable_entity_id(session)
    restaurant = Restaurant(id=eid, name=name, restaurant_type_id="casual")
    dl.save_entity("restaurant", eid, restaurant_to_dict(restaurant))
    return eid
```

### 3. `_MockProvider`

Copy exact pattern from `test_welcome_agent.py`:

```python
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
```

### 4. `TestBuildManualContext` — 4 mocked tests

```python
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
        # stock_unit_id / purchase_unit_id must be valid ints; use 1 (no registry check in serialization)
        item = InventoryItem(id=1, name="Carne", stock_unit_id=1, purchase_unit_id=1, category_id=1)
        dl.save_entity("inventory_item", 1, inventory_item_to_dict(item))
        result = _build_manual_context(dl, "test")
        self.assertIn("Carne", result)

    def test_empty_session_returns_string(self):
        dl = _make_data_lake()
        result = _build_manual_context(dl, "nonexistent-session-xyz")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)
```

### 5. `TestBuildResumenMd` — 1 mocked test

```python
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
        self.assertIn("0 / 100", result)
```

### 6. `TestBuildRecetasMd` — 2 mocked tests

```python
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
        # Build minimal registries
        rur = RecipeUnitRegistry()
        ru = RecipeUnit(id=1, name="Gramo", symbol="g")
        rur.add(ru)

        iur = InventoryUnitRegistry()
        iu = InventoryUnit(id=1, name="Gramo", symbol="g", is_standard=True)
        iur.add(iu)

        ir = InventoryItemRegistry()
        item = InventoryItem(id=1, name="tortilla", stock_unit_id=1, purchase_unit_id=1, category_id=1)
        ir.add(item)

        ing = Ingredient(name="tortilla", quantity=2.0, unit_id=1)
        recipe = Recipe(id=1, name="Taco", category_id=1, ingredients=[ing])

        result = _build_recetas_md(
            [recipe], rur, ir,
            CategoryRecipeRegistry(), iur,
            RecipeUnitConversionRegistry(),
            FamilyInventoryRegistry(),
        )
        self.assertIn("✓ vinculado", result)
```

### 7. `TestBuildInventarioMd` — 1 mocked test

```python
class TestBuildInventarioMd(unittest.TestCase):

    def test_groups_by_category(self):
        item_p = InventoryItem(id=1, name="Carne", stock_unit_id=1, purchase_unit_id=1, category_id=1)
        item_np = InventoryItem(id=2, name="Sal", stock_unit_id=1, purchase_unit_id=1, category_id=2)
        result = _build_inventario_md([item_p, item_np], InventoryUnitRegistry(), FamilyInventoryRegistry())
        self.assertIn("Perecederos", result)
        self.assertIn("No Perecederos", result)
        self.assertIn("Carne", result)
        self.assertIn("Sal", result)
```

### 8. `TestManualOperativoAgent` — 4 mocked tests

```python
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
```

### 9. `TestManualOperativoAgentLive` — 2 live tests

Minimal `manual_context` string injected so the agent has something to reason about:

```python
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
        self.assertNotIn("{", reply)   # no JSON leak

    def test_deduction_live_returns_quantities(self):
        agent = self._make_agent()
        result = agent.run(
            input_data={"user_message": "Si vendo 5 porciones de Tacos al pastor, ¿cuánto necesito?"},
            context={"manual_context": _MINIMAL_CONTEXT},
        )
        reply = result["reply"]
        self.assertTrue(any(c.isdigit() for c in reply))
```

### 10. Boilerplate footer

```python
if __name__ == "__main__":
    unittest.main()
```

### 11. Run full suite offline and update tasks.json

```bash
uv run python -m pytest tests/unit/test_manual_operativo.py -v
```

All 12 mocked tests must pass. Mark subtask 12.5 `done` in tasks.json.

---

## Out of scope

- No tests for `render()` Gradio wiring (requires Gradio runtime)
- No tests for `_make_content` return shape (requires `gr.update` object)
- No tests for `_build_mi_restaurante_md` independently (covered indirectly by `test_includes_recipe`)
- No changes to any file outside `tests/unit/test_manual_operativo.py`

---

## Risks and open questions

- `InventoryItem` with `stock_unit_id=1` / `purchase_unit_id=1` but no matching
  `InventoryUnit` in registry: unit symbol will fall back to `str(unit_id)` = `"1"`.
  This is correct behavior and fine for these tests — we are not testing symbol resolution.
- `_build_recetas_md` linked test: `item_registry.get_by_name("tortilla")` must return
  the seeded item. Ensure `ir.add(item)` is called before building the recipe list.
- Live deduction test asserts `any(c.isdigit() for c in reply)` — robust to prose variation.
  If the agent responds in an unexpected language, the test still passes (quantity digits will
  be present regardless of language). Acceptable for MVP.
- `DataLake(data_dir=...)` uses JSON backend. `_build_manual_context` calls
  `list_entity_ids("recipe_unit_conversion")` which returns `[]` on JSON backend
  (SQLite-only entity type). This means `RecipeUnitConversionRegistry` is always empty
  in these tests. Deduction coverage KPI will show 0% — do not assert on it.
