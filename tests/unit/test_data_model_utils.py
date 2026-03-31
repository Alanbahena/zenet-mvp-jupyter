"""Unit tests for core/data_model_utils.py (subtask 2.5)."""

import unittest

from core.domain.data_model import (
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
)
from core.domain.data_model_utils import (
    build_ingredient,
    create_inventory_item_from_ingredient,
    format_deduction_line_for_display,
    format_ingredient_for_display,
    ingredients_to_display,
    make_resolver_from_item_registry,
    parse_quantity_and_unit,
    resolve_ingredient_to_inventory_item,
    units_used_by_recipe,
    validate_ingredient_with_registries,
    validate_recipe_for_deduction,
)
from core.operations.normalization import (
    RecipeUnitConversionRegistry,
    normalize_recipe_for_deduction,
)


def _make_recipe_unit_registry():
    reg = RecipeUnitRegistry()
    reg.add(RecipeUnit(1, "gramo", "g"))
    reg.add(RecipeUnit(2, "kilogramo", "kg"))
    return reg


def _make_inventory_unit_registry():
    reg = InventoryUnitRegistry()
    reg.add(InventoryUnit(1, "gramo", "g"))
    reg.add(InventoryUnit(2, "kilogramo", "kg"))
    return reg


class TestFormatDeductionLineForDisplay(unittest.TestCase):
    def test_valid_line(self):
        unit_reg = _make_inventory_unit_registry()
        item_reg = InventoryItemRegistry()
        item_reg.add(InventoryItem(1, "Leche", 2, 2, 1))  # stock_unit_id 2 = kg
        line = (1, 0.5, 2)
        out = format_deduction_line_for_display(line, unit_reg, item_reg)
        self.assertEqual(out, "0.5 kg Leche")

    def test_missing_unit_fallback(self):
        unit_reg = InventoryUnitRegistry()
        item_reg = InventoryItemRegistry()
        item_reg.add(InventoryItem(1, "X", 99, 99, 1))
        line = (1, 1.0, 99)
        out = format_deduction_line_for_display(line, unit_reg, item_reg)
        self.assertIn("99", out)
        self.assertIn("X", out)

    def test_missing_item_fallback(self):
        unit_reg = _make_inventory_unit_registry()
        item_reg = InventoryItemRegistry()
        line = (999, 1.0, 1)
        out = format_deduction_line_for_display(line, unit_reg, item_reg)
        self.assertIn("999", out)
        self.assertIn("g", out)


class TestFormatIngredientForDisplay(unittest.TestCase):
    def test_valid(self):
        reg = _make_recipe_unit_registry()
        ing = Ingredient("Harina", 250.0, 1)
        out = format_ingredient_for_display(ing, reg)
        self.assertEqual(out, "250.0 g Harina")

    def test_missing_unit_fallback(self):
        reg = RecipeUnitRegistry()
        ing = Ingredient("X", 1.0, 99)
        out = format_ingredient_for_display(ing, reg)
        self.assertIn("99", out)
        self.assertIn("X", out)


class TestIngredientsToDisplay(unittest.TestCase):
    def test_one_ingredient_without_item_registry(self):
        recipe = Recipe(0, "R", 1, "D", [], ingredients=[Ingredient("Harina", 250.0, 1)])
        ru_reg = _make_recipe_unit_registry()
        out = ingredients_to_display(recipe, ru_reg)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["name"], "Harina")
        self.assertEqual(out[0]["quantity"], 250.0)
        self.assertEqual(out[0]["unit_symbol"], "g")
        self.assertEqual(out[0]["unit_id"], 1)
        self.assertNotIn("inventory_item_name", out[0])

    def test_with_inventory_item_registry(self):
        recipe = Recipe(0, "R", 1, "D", [], ingredients=[Ingredient("Leche", 100.0, 1)])
        ru_reg = _make_recipe_unit_registry()
        item_reg = InventoryItemRegistry()
        item_reg.add(InventoryItem(1, "Leche", 1, 1, 1))
        out = ingredients_to_display(recipe, ru_reg, inventory_item_registry=item_reg)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["inventory_item_name"], "Leche")

    def test_missing_unit_uses_id_fallback(self):
        recipe = Recipe(0, "R", 1, "D", [], ingredients=[Ingredient("X", 1.0, 99)])
        ru_reg = RecipeUnitRegistry()
        out = ingredients_to_display(recipe, ru_reg)
        self.assertEqual(out[0]["unit_symbol"], "99")


class TestParseQuantityAndUnit(unittest.TestCase):
    def test_quantity_and_unit(self):
        reg = _make_recipe_unit_registry()
        qty, uid = parse_quantity_and_unit("250 g", reg)
        self.assertEqual(qty, 250.0)
        self.assertEqual(uid, 1)

    def test_single_number_raises(self):
        reg = _make_recipe_unit_registry()
        with self.assertRaises(ValueError) as ctx:
            parse_quantity_and_unit("250", reg)
        self.assertIn("unit", str(ctx.exception).lower())

    def test_unknown_symbol_raises(self):
        reg = _make_recipe_unit_registry()
        with self.assertRaises(ValueError) as ctx:
            parse_quantity_and_unit("250 oz", reg)
        self.assertIn("not found", str(ctx.exception))


class TestValidateRecipeForDeduction(unittest.TestCase):
    def test_valid_recipe_empty_issues(self):
        item_reg = InventoryItemRegistry()
        item_reg.add(InventoryItem(1, "Leche", 1, 1, 1))
        recipe = Recipe(0, "R", 1, "D", [], ingredients=[Ingredient("Leche", 100.0, 1)])
        unit_reg = _make_inventory_unit_registry()
        conv = RecipeUnitConversionRegistry()
        fam_reg = FamilyInventoryRegistry()
        issues = validate_recipe_for_deduction(
            recipe, item_reg, unit_reg, conv, fam_reg
        )
        self.assertEqual(issues, [])

    def test_unresolved_ingredient_issue(self):
        item_reg = InventoryItemRegistry()
        recipe = Recipe(0, "R", 1, "D", [], ingredients=[Ingredient("Unknown", 1.0, 1)])
        unit_reg = _make_inventory_unit_registry()
        conv = RecipeUnitConversionRegistry()
        fam_reg = FamilyInventoryRegistry()
        issues = validate_recipe_for_deduction(
            recipe, item_reg, unit_reg, conv, fam_reg
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("no inventory item", issues[0])


class TestValidateIngredientWithRegistries(unittest.TestCase):
    def test_valid_empty_list(self):
        ing = Ingredient("Harina", 250.0, 1)
        issues = validate_ingredient_with_registries(ing, {1, 2})
        self.assertEqual(issues, [])

    def test_empty_name(self):
        ing = Ingredient("  ", 1.0, 1)
        issues = validate_ingredient_with_registries(ing, {1})
        self.assertTrue(any("non-empty" in m for m in issues))

    def test_invalid_quantity(self):
        ing = Ingredient("X", 0.0, 1)
        issues = validate_ingredient_with_registries(ing, {1})
        self.assertTrue(any("quantity" in m for m in issues))

    def test_invalid_unit_id(self):
        ing = Ingredient("X", 1.0, 99)
        issues = validate_ingredient_with_registries(ing, {1, 2})
        self.assertTrue(any("unit_id" in m or "valid" in m for m in issues))


class TestResolveIngredientToInventoryItem(unittest.TestCase):
    def test_by_id(self):
        item_reg = InventoryItemRegistry()
        item_reg.add(InventoryItem(1, "Leche", 1, 1, 1))
        ing = Ingredient("Leche", 100.0, 1, inventory_item_id=1)
        out = resolve_ingredient_to_inventory_item(ing, item_reg)
        self.assertIsNotNone(out)
        self.assertEqual(out.id, 1)

    def test_by_name(self):
        item_reg = InventoryItemRegistry()
        item_reg.add(InventoryItem(1, "Leche", 1, 1, 1))
        ing = Ingredient("Leche", 100.0, 1)
        out = resolve_ingredient_to_inventory_item(ing, item_reg)
        self.assertIsNotNone(out)
        self.assertEqual(out.name, "Leche")

    def test_missing_returns_none(self):
        item_reg = InventoryItemRegistry()
        ing = Ingredient("Missing", 1.0, 1)
        out = resolve_ingredient_to_inventory_item(ing, item_reg)
        self.assertIsNone(out)


class TestMakeResolverFromItemRegistry(unittest.TestCase):
    def test_use_with_normalize_recipe_for_deduction(self):
        item_reg = InventoryItemRegistry()
        item_reg.add(InventoryItem(1, "Harina", 1, 1, 1))
        recipe = Recipe(0, "R", 1, "D", [], ingredients=[Ingredient("Harina", 500.0, 1)])
        ru_reg = _make_recipe_unit_registry()
        iu_reg = _make_inventory_unit_registry()
        conv = RecipeUnitConversionRegistry()
        conv.add(1, 1.0, 1)
        fam_reg = FamilyInventoryRegistry()
        resolver = make_resolver_from_item_registry(item_reg)
        lines = normalize_recipe_for_deduction(
            recipe, fam_reg, iu_reg, conv, resolver
        )
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0][0], 1)
        self.assertEqual(lines[0][2], 1)


class TestUnitsUsedByRecipe(unittest.TestCase):
    def test_one_ingredient(self):
        item_reg = InventoryItemRegistry()
        item_reg.add(InventoryItem(1, "Leche", 2, 2, 1))
        recipe = Recipe(0, "R", 1, "D", [], ingredients=[Ingredient("Leche", 100.0, 1)])
        ru_reg = _make_recipe_unit_registry()
        iu_reg = _make_inventory_unit_registry()
        recipe_ids, inv_ids = units_used_by_recipe(
            recipe, ru_reg, item_reg, iu_reg
        )
        self.assertEqual(recipe_ids, {1})
        self.assertEqual(inv_ids, {2})

    def test_unresolved_ingredient_omitted_from_inventory_ids(self):
        item_reg = InventoryItemRegistry()
        recipe = Recipe(0, "R", 1, "D", [], ingredients=[Ingredient("Missing", 1.0, 1)])
        ru_reg = _make_recipe_unit_registry()
        iu_reg = _make_inventory_unit_registry()
        recipe_ids, inv_ids = units_used_by_recipe(
            recipe, ru_reg, item_reg, iu_reg
        )
        self.assertEqual(recipe_ids, {1})
        self.assertEqual(inv_ids, set())


class TestCreateInventoryItemFromIngredient(unittest.TestCase):
    def test_returns_correct_fields(self):
        ing = Ingredient("Leche", 100.0, 1)
        item = create_inventory_item_from_ingredient(
            ing, category_id=1, stock_unit_id=2, purchase_unit_id=2,
            purchase_to_stock_factor=1.0, family_id=None
        )
        self.assertEqual(item.id, 0)
        self.assertEqual(item.name, "Leche")
        self.assertEqual(item.stock_unit_id, 2)
        self.assertEqual(item.purchase_unit_id, 2)
        self.assertEqual(item.category_id, 1)
        self.assertIsNone(item.family_id)


class TestBuildIngredient(unittest.TestCase):
    def test_returns_correct_ingredient(self):
        ing = build_ingredient("Harina", 250.0, 1, inventory_item_id=5)
        self.assertEqual(ing.name, "Harina")
        self.assertEqual(ing.quantity, 250.0)
        self.assertEqual(ing.unit_id, 1)
        self.assertEqual(ing.inventory_item_id, 5)

    def test_default_inventory_item_id_none(self):
        ing = build_ingredient("X", 1.0, 1)
        self.assertIsNone(ing.inventory_item_id)


if __name__ == "__main__":
    unittest.main()
