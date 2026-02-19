"""Unit tests for core.readiness_kpis.py (subtask 2.7)."""

import unittest

from core import compute_readiness_report
from core.data_model import (
    CategoryRecipe,
    CategoryRecipeRegistry,
    FamilyInventory,
    FamilyInventoryRegistry,
    Ingredient,
    InventoryItem,
    InventoryItemRegistry,
    InventoryUnit,
    InventoryUnitRegistry,
    Recipe,
    RecipeUnit,
    RecipeUnitRegistry,
    Restaurant,
)
from core.normalization import RecipeUnitConversionRegistry
from typing import Optional


def _kpi_by_id(report: dict, kpi_id: str) -> dict:
    for k in report.get("kpis", []):
        if k.get("kpi_id") == kpi_id:
            return k
    raise KeyError(f"kpi_id not found: {kpi_id}")


def _rec_ids(report: dict) -> set[str]:
    return {r.get("recommendation_id") for r in report.get("recommendations", [])}


def _make_recipe_unit_registry(*units: tuple[int, str, str]) -> RecipeUnitRegistry:
    reg = RecipeUnitRegistry()
    for uid, name, sym in units:
        reg.add(RecipeUnit(uid, name, sym))
    return reg


def _make_inventory_unit_registry(*units: tuple[int, str, str, Optional[int], float]) -> InventoryUnitRegistry:
    reg = InventoryUnitRegistry()
    for uid, name, sym, base_id, factor in units:
        reg.add(InventoryUnit(uid, name, sym, description=None, base_unit_id=base_id, factor_to_base=factor))
    return reg


def _make_category_registry() -> CategoryRecipeRegistry:
    reg = CategoryRecipeRegistry()
    reg.add(CategoryRecipe(1, "Cat", None))
    return reg


def _make_family_registry() -> FamilyInventoryRegistry:
    reg = FamilyInventoryRegistry()
    reg.add(FamilyInventory(1, "Fam", None, None))
    return reg


class TestReadinessKpis(unittest.TestCase):
    def test_good_minimal_setup_is_ok(self):
        restaurant = Restaurant(id=1, name="R", restaurant_type_id=4)

        ru_reg = _make_recipe_unit_registry((1, "gramo", "g"))
        iu_reg = _make_inventory_unit_registry((1, "gramo", "g", None, 1.0))
        cat_reg = _make_category_registry()
        fam_reg = _make_family_registry()
        item_reg = InventoryItemRegistry()
        item_reg.add(InventoryItem(1, "Harina", 1, 1, family_id=1))

        recipes = [
            Recipe(
                10,
                "Pan",
                "Desc",
                steps=["mezclar"],
                category_id=1,
                ingredients=[Ingredient("Harina", 100.0, 1, inventory_item_id=1)],
            )
        ]
        conv = RecipeUnitConversionRegistry()

        report = compute_readiness_report(
            restaurant,
            recipes=recipes,
            recipe_unit_registry=ru_reg,
            inventory_unit_registry=iu_reg,
            category_recipe_registry=cat_reg,
            family_inventory_registry=fam_reg,
            inventory_item_registry=item_reg,
            conversion_table=conv,
        )

        self.assertEqual(report["schema_version"], "1.0")
        self.assertIn("generated_at", report)
        self.assertEqual(report["overall"]["status"], "ok")
        self.assertEqual(report["overall"]["grade"], "A")

        link = _kpi_by_id(report, "recipes.ingredientsLinkedToInventoryPct")
        self.assertEqual(link["status"], "ok")
        cov = _kpi_by_id(report, "normalization.deductionCoveragePct")
        self.assertEqual(cov["status"], "ok")

    def test_partial_missing_inventory_links_fails_truth_kpi(self):
        ru_reg = _make_recipe_unit_registry((1, "gramo", "g"))
        iu_reg = _make_inventory_unit_registry((1, "gramo", "g", None, 1.0))
        cat_reg = _make_category_registry()
        fam_reg = _make_family_registry()
        item_reg = InventoryItemRegistry()
        item_reg.add(InventoryItem(1, "Harina", 1, 1, family_id=1))

        recipes = [
            Recipe(
                10,
                "Test",
                "Desc",
                steps=["x"],
                category_id=1,
                ingredients=[
                    Ingredient("Harina", 100.0, 1, inventory_item_id=1),
                    Ingredient("Sal", 10.0, 1, inventory_item_id=None),
                ],
            )
        ]
        conv = RecipeUnitConversionRegistry()

        report = compute_readiness_report(
            None,
            recipes=recipes,
            recipe_unit_registry=ru_reg,
            inventory_unit_registry=iu_reg,
            category_recipe_registry=cat_reg,
            family_inventory_registry=fam_reg,
            inventory_item_registry=item_reg,
            conversion_table=conv,
        )

        link = _kpi_by_id(report, "recipes.ingredientsLinkedToInventoryPct")
        self.assertEqual(link["status"], "fail")
        # Overall status is derived from worst dimension status.
        self.assertEqual(report["overall"]["status"], "fail")
        self.assertIn("rec.linkIngredientsToInventory", _rec_ids(report))

    def test_broken_normalization_incompatible_units_fails_coverage(self):
        # Two unit roots: g (1) and ml (10). Ingredient uses ml, item uses g.
        ru_reg = _make_recipe_unit_registry((10, "mililitro", "ml"))
        iu_reg = _make_inventory_unit_registry(
            (1, "gramo", "g", None, 1.0),
            (10, "mililitro", "ml", None, 1.0),
        )
        cat_reg = _make_category_registry()
        fam_reg = _make_family_registry()
        item_reg = InventoryItemRegistry()
        item_reg.add(InventoryItem(1, "Leche", 1, 1, family_id=1))

        recipes = [
            Recipe(
                10,
                "Test",
                "Desc",
                steps=["x"],
                category_id=1,
                ingredients=[Ingredient("Leche", 100.0, 10, inventory_item_id=1)],
            )
        ]
        conv = RecipeUnitConversionRegistry()  # no conversion entry provided

        report = compute_readiness_report(
            None,
            recipes=recipes,
            recipe_unit_registry=ru_reg,
            inventory_unit_registry=iu_reg,
            category_recipe_registry=cat_reg,
            family_inventory_registry=fam_reg,
            inventory_item_registry=item_reg,
            conversion_table=conv,
        )

        cov = _kpi_by_id(report, "normalization.deductionCoveragePct")
        self.assertEqual(cov["status"], "fail")
        self.assertEqual(report["overall"]["status"], "fail")
        self.assertIn("rec.increaseDeductionCoverage", _rec_ids(report))


if __name__ == "__main__":
    unittest.main()

