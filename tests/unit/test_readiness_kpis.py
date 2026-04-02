"""Unit tests for core.readiness_kpis.py (subtask 2.7)."""

import unittest

from core import compute_readiness_report
from core.domain.data_model import (
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
from core.operations.normalization import RecipeUnitConversionRegistry
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
        item_reg.add(InventoryItem(1, "Harina", 1, 1, 1, family_id=1))

        recipes = [
            Recipe(
                10,
                "Pan",
                1,
                "Desc",
                ["mezclar"],
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
        item_reg.add(InventoryItem(1, "Harina", 1, 1, 1, family_id=1))

        recipes = [
            Recipe(
                10,
                "Test",
                1,
                "Desc",
                ["x"],
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
        item_reg.add(InventoryItem(1, "Leche", 1, 1, 1, family_id=1))

        recipes = [
            Recipe(
                10,
                "Test",
                1,
                "Desc",
                ["x"],
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


class TestReadinessReportSchema(unittest.TestCase):
    """Edge-case tests for report structure with empty registries."""

    def _empty_report(self):
        return compute_readiness_report(
            Restaurant(id=1, name="T", restaurant_type_id=1),
            recipes=[],
            recipe_unit_registry=RecipeUnitRegistry(),
            inventory_unit_registry=InventoryUnitRegistry(),
            category_recipe_registry=CategoryRecipeRegistry(),
            family_inventory_registry=FamilyInventoryRegistry(),
            inventory_item_registry=InventoryItemRegistry(),
            conversion_table=RecipeUnitConversionRegistry(),
        )

    def test_empty_registries_returns_zero_score_and_d_grade(self):
        report = self._empty_report()
        # _overall_score returns 0.0 when no dimension has a computable score
        self.assertEqual(report["overall"]["score_0_100"], 0.0)
        # _grade_from_score(0.0) → "D"; "N/D" is only a UI fallback, never a report value
        self.assertEqual(report["overall"]["grade"], "D")

    def test_report_has_required_top_level_keys(self):
        report = self._empty_report()
        for key in ("schema_version", "generated_at", "overall", "dimensions", "kpis"):
            self.assertIn(key, report)

    def test_deduction_coverage_kpi_is_present(self):
        report = self._empty_report()
        kpi_ids = [k.get("kpi_id") for k in report.get("kpis", [])]
        self.assertIn("normalization.deductionCoveragePct", kpi_ids)


if __name__ == "__main__":
    unittest.main()

