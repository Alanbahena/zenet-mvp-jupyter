"""Unit tests for core.normalization (subtask 2.3)."""

from __future__ import annotations

import unittest
from typing import Optional

from core.data_model import (
    FamilyInventory,
    FamilyInventoryRegistry,
    Ingredient,
    InventoryItem,
    InventoryUnit,
    InventoryUnitEquivalence,
    InventoryUnitEquivalenceRegistry,
    InventoryUnitRegistry,
    Recipe,
)
from core.normalization import (
    apply_deduction_lines,
    convert_quantity,
    from_base_quantity,
    from_base_quantity_by_id,
    get_family_base_unit_id,
    make_resolver,
    normalize_recipe_for_deduction,
    normalize_recipe_unit_quantity,
    RecipeUnitConversionEntry,
    RecipeUnitConversionRegistry,
    to_base_quantity,
    to_base_quantity_by_id,
)


def _make_registry_kg_g() -> InventoryUnitRegistry:
    """g (id=1) base; kg (id=2) -> g factor 1000."""
    reg = InventoryUnitRegistry()
    reg.add(InventoryUnit(1, "gramo", "g", None, None, 1.0))
    reg.add(InventoryUnit(2, "kilogramo", "kg", None, 1, 1000.0))
    return reg


def _make_registry_chain() -> InventoryUnitRegistry:
    """g (1), kg (2) -> g 1000, caja (3) -> kg 10."""
    reg = InventoryUnitRegistry()
    reg.add(InventoryUnit(1, "gramo", "g", None, None, 1.0))
    reg.add(InventoryUnit(2, "kilogramo", "kg", None, 1, 1000.0))
    reg.add(InventoryUnit(3, "caja", "caja", None, 2, 10.0))
    return reg


def _make_registry_two_families() -> InventoryUnitRegistry:
    """Mass: g (1), kg (2). Volume: ml (10), L (11)."""
    reg = InventoryUnitRegistry()
    reg.add(InventoryUnit(1, "gramo", "g", None, None, 1.0))
    reg.add(InventoryUnit(2, "kilogramo", "kg", None, 1, 1000.0))
    reg.add(InventoryUnit(10, "mililitro", "ml", None, None, 1.0))
    reg.add(InventoryUnit(11, "litro", "L", None, 10, 1000.0))
    return reg


class TestToBaseQuantity(unittest.TestCase):
    def test_unit_as_own_base(self):
        reg = _make_registry_kg_g()
        g = reg.get(1)
        self.assertIsNotNone(g)
        self.assertEqual(to_base_quantity(1.0, g, reg), 1.0)
        self.assertEqual(to_base_quantity(100.0, g, reg), 100.0)

    def test_unit_with_base_one_step(self):
        reg = _make_registry_kg_g()
        kg = reg.get(2)
        self.assertIsNotNone(kg)
        self.assertEqual(to_base_quantity(1.0, kg, reg), 1000.0)
        self.assertEqual(to_base_quantity(0.5, kg, reg), 500.0)

    def test_chain_two_steps(self):
        reg = _make_registry_chain()
        caja = reg.get(3)
        self.assertIsNotNone(caja)
        # 1 caja = 10 kg = 10000 g
        self.assertEqual(to_base_quantity(1.0, caja, reg), 10000.0)
        self.assertEqual(to_base_quantity(0.5, caja, reg), 5000.0)


class TestFromBaseQuantity(unittest.TestCase):
    def test_round_trip(self):
        reg = _make_registry_kg_g()
        kg = reg.get(2)
        self.assertIsNotNone(kg)
        for q in (0.5, 1.0, 2.5):
            base = to_base_quantity(q, kg, reg)
            back = from_base_quantity(base, kg, reg)
            self.assertAlmostEqual(back, q, places=9)

    def test_from_base_explicit(self):
        reg = _make_registry_kg_g()
        kg = reg.get(2)
        self.assertIsNotNone(kg)
        # 500 g in base -> 0.5 kg
        self.assertAlmostEqual(from_base_quantity(500.0, kg, reg), 0.5)

    def test_chain_round_trip(self):
        reg = _make_registry_chain()
        caja = reg.get(3)
        self.assertIsNotNone(caja)
        self.assertAlmostEqual(
            from_base_quantity(to_base_quantity(1.0, caja, reg), caja, reg), 1.0
        )


class TestToBaseQuantityWithEquivalence(unittest.TestCase):
    """Item-specific equivalence: e.g. 1 box strawberries = 2 kg, 1 box oranges = 10 kg."""

    def test_item_specific_overrides_global(self):
        reg = InventoryUnitRegistry()
        reg.add(InventoryUnit(1, "gramo", "g", None, None, 1.0))
        reg.add(InventoryUnit(2, "kilogramo", "kg", None, 1, 1000.0))
        reg.add(InventoryUnit(3, "caja", "caja", None, 2, 10.0))
        eq_reg = InventoryUnitEquivalenceRegistry()
        eq_reg.add(
            InventoryUnitEquivalence(unit_id=3, inventory_item_id=101, base_unit_id=1, factor_to_base=2.0),
            reg,
        )
        caja = reg.get(3)
        self.assertIsNotNone(caja)
        self.assertEqual(
            to_base_quantity(1.0, caja, reg, inventory_item_id=101, equivalence_registry=eq_reg),
            2.0,
        )
        self.assertEqual(
            to_base_quantity(3.0, caja, reg, inventory_item_id=101, equivalence_registry=eq_reg),
            6.0,
        )

    def test_different_items_different_factors(self):
        reg = InventoryUnitRegistry()
        reg.add(InventoryUnit(1, "gramo", "g", None, None, 1.0))
        reg.add(InventoryUnit(2, "kilogramo", "kg", None, 1, 1000.0))
        reg.add(InventoryUnit(3, "caja", "caja", None, 2, 10.0))
        eq_reg = InventoryUnitEquivalenceRegistry()
        eq_reg.add(
            InventoryUnitEquivalence(unit_id=3, inventory_item_id=101, base_unit_id=1, factor_to_base=2.0),
            reg,
        )
        eq_reg.add(
            InventoryUnitEquivalence(unit_id=3, inventory_item_id=102, base_unit_id=1, factor_to_base=10.0),
            reg,
        )
        caja = reg.get(3)
        self.assertIsNotNone(caja)
        self.assertEqual(
            to_base_quantity(1.0, caja, reg, inventory_item_id=101, equivalence_registry=eq_reg),
            2.0,
        )
        self.assertEqual(
            to_base_quantity(1.0, caja, reg, inventory_item_id=102, equivalence_registry=eq_reg),
            10.0,
        )

    def test_no_equivalence_falls_back_to_unit_chain(self):
        reg = _make_registry_chain()
        eq_reg = InventoryUnitEquivalenceRegistry()
        caja = reg.get(3)
        self.assertIsNotNone(caja)
        self.assertEqual(
            to_base_quantity(1.0, caja, reg, inventory_item_id=999, equivalence_registry=eq_reg),
            10000.0,
        )


class TestByIdOverloads(unittest.TestCase):
    def test_to_base_quantity_by_id_valid(self):
        reg = _make_registry_kg_g()
        self.assertEqual(to_base_quantity_by_id(1.0, 2, reg), 1000.0)

    def test_to_base_quantity_by_id_invalid_raises(self):
        reg = _make_registry_kg_g()
        with self.assertRaises(ValueError) as ctx:
            to_base_quantity_by_id(1.0, 99, reg)
        self.assertIn("99", str(ctx.exception))

    def test_from_base_quantity_by_id_valid(self):
        reg = _make_registry_kg_g()
        self.assertAlmostEqual(from_base_quantity_by_id(1000.0, 2, reg), 1.0)

    def test_from_base_quantity_by_id_invalid_raises(self):
        reg = _make_registry_kg_g()
        with self.assertRaises(ValueError) as ctx:
            from_base_quantity_by_id(1000.0, 99, reg)
        self.assertIn("99", str(ctx.exception))


class TestErrorHandling(unittest.TestCase):
    def test_broken_chain_raises(self):
        reg = InventoryUnitRegistry()
        reg.add(InventoryUnit(1, "gramo", "g", None, None, 1.0))
        reg.add(InventoryUnit(2, "kilogramo", "kg", None, 1, 1000.0))
        reg.remove(1)
        kg = reg.get(2)
        self.assertIsNotNone(kg)
        with self.assertRaises(ValueError) as ctx:
            to_base_quantity(1.0, kg, reg)
        self.assertIn("broken chain", str(ctx.exception).lower())

    def test_invalid_quantity_raises(self):
        reg = _make_registry_kg_g()
        g = reg.get(1)
        self.assertIsNotNone(g)
        with self.assertRaises(ValueError):
            to_base_quantity(float("nan"), g, reg)
        with self.assertRaises(ValueError):
            to_base_quantity(float("inf"), g, reg)


class TestConvertQuantity(unittest.TestCase):
    def test_kg_to_g(self):
        reg = _make_registry_kg_g()
        self.assertEqual(convert_quantity(0.5, 2, 1, reg), 500.0)

    def test_caja_to_g(self):
        reg = _make_registry_chain()
        self.assertEqual(convert_quantity(1.0, 3, 1, reg), 10000.0)

    def test_incompatible_units_raise(self):
        reg = _make_registry_two_families()
        with self.assertRaises(ValueError) as ctx:
            convert_quantity(1.0, 2, 11, reg)
        self.assertIn("incompatible", str(ctx.exception).lower())

    def test_convert_quantity_with_item_equivalence_uses_item_specific_factor(self):
        """With inventory_item_id and equivalence_registry, from_unit uses item-specific conversion."""
        reg = InventoryUnitRegistry()
        reg.add(InventoryUnit(1, "gramo", "g", None, None, 1.0))
        reg.add(InventoryUnit(2, "kilogramo", "kg", None, 1, 1000.0))
        reg.add(InventoryUnit(3, "caja", "caja", None, 2, 10.0))  # global: 1 caja = 10 kg
        eq_reg = InventoryUnitEquivalenceRegistry()
        eq_reg.add(
            InventoryUnitEquivalence(unit_id=3, inventory_item_id=101, base_unit_id=2, factor_to_base=2.0),
            reg,
        )  # item 101: 1 caja = 2 kg
        # Without item: 1 caja -> 10 kg -> 10_000 g
        self.assertEqual(convert_quantity(1.0, 3, 1, reg), 10000.0)
        # With item 101: 1 caja -> 2 kg -> 2000 g
        self.assertEqual(
            convert_quantity(1.0, 3, 1, reg, inventory_item_id=101, equivalence_registry=eq_reg),
            2000.0,
        )
        # Same item, convert to kg: 1 caja -> 2 kg
        self.assertEqual(
            convert_quantity(1.0, 3, 2, reg, inventory_item_id=101, equivalence_registry=eq_reg),
            2.0,
        )


class TestGetFamilyBaseUnitId(unittest.TestCase):
    def test_family_with_base_returns_id(self):
        fam_reg = FamilyInventoryRegistry()
        fam_reg.add(FamilyInventory(1, "Carnes", None, 1))
        unit_reg = _make_registry_kg_g()
        self.assertEqual(
            get_family_base_unit_id(1, fam_reg, unit_reg), 1
        )

    def test_family_without_base_returns_none(self):
        fam_reg = FamilyInventoryRegistry()
        fam_reg.add(FamilyInventory(1, "Carnes", None, None))
        unit_reg = _make_registry_kg_g()
        self.assertIsNone(get_family_base_unit_id(1, fam_reg, unit_reg))

    def test_family_not_found_returns_none(self):
        fam_reg = FamilyInventoryRegistry()
        unit_reg = _make_registry_kg_g()
        self.assertIsNone(get_family_base_unit_id(99, fam_reg, unit_reg))

    def test_invalid_base_unit_id_raises(self):
        fam_reg = FamilyInventoryRegistry()
        fam_reg.add(FamilyInventory(1, "Carnes", None, 999))
        unit_reg = _make_registry_kg_g()
        with self.assertRaises(ValueError) as ctx:
            get_family_base_unit_id(1, fam_reg, unit_reg)
        self.assertIn("999", str(ctx.exception))


class TestRecipeUnitConversionRegistry(unittest.TestCase):
    def test_add_and_get_recipe_unit_only(self):
        tbl = RecipeUnitConversionRegistry()
        tbl.add(1, 30.0, 1)
        entry = tbl.get(1, None, None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.quantity, 30.0)
        self.assertEqual(entry.base_unit_id, 1)

    def test_get_best_match_family_id(self):
        tbl = RecipeUnitConversionRegistry()
        tbl.add(1, 30.0, 1)
        tbl.add(1, 25.0, 1, family_id=2)
        entry = tbl.get(1, 2, None)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.quantity, 25.0)
        entry_any = tbl.get(1, None, None)
        self.assertEqual(entry_any.quantity, 30.0)

    def test_quantity_must_be_positive(self):
        tbl = RecipeUnitConversionRegistry()
        with self.assertRaises(ValueError):
            tbl.add(1, 0.0, 1)
        with self.assertRaises(ValueError):
            tbl.add(1, -1.0, 1)


class TestNormalizeRecipeUnitQuantity(unittest.TestCase):
    def test_lookup_recipe_unit_only(self):
        tbl = RecipeUnitConversionRegistry()
        tbl.add(1, 30.0, 1)
        unit_reg = _make_registry_kg_g()
        qty, uid = normalize_recipe_unit_quantity(2.0, 1, None, None, tbl, unit_reg)
        self.assertEqual(qty, 60.0)
        self.assertEqual(uid, 1)

    def test_missing_entry_raises(self):
        tbl = RecipeUnitConversionRegistry()
        unit_reg = _make_registry_kg_g()
        with self.assertRaises(ValueError) as ctx:
            normalize_recipe_unit_quantity(1.0, 99, None, None, tbl, unit_reg)
        self.assertIn("no conversion", str(ctx.exception).lower())

    def test_invalid_quantity_raises(self):
        tbl = RecipeUnitConversionRegistry()
        tbl.add(1, 30.0, 1)
        unit_reg = _make_registry_kg_g()
        with self.assertRaises(ValueError):
            normalize_recipe_unit_quantity(0.0, 1, None, None, tbl, unit_reg)


class TestNormalizeRecipeForDeduction(unittest.TestCase):
    def test_empty_recipe_returns_empty_list(self):
        recipe = Recipe(1, "Empty", 1, "", [])
        fam_reg = FamilyInventoryRegistry()
        unit_reg = _make_registry_kg_g()
        tbl = RecipeUnitConversionRegistry()

        def resolve(ing: Ingredient) -> tuple[int, Optional[int], int]:
            return (0, None, 1)

        result = normalize_recipe_for_deduction(
            recipe, fam_reg, unit_reg, tbl, resolve
        )
        self.assertEqual(result, [])

    def test_one_ingredient_with_conversion(self):
        unit_reg = _make_registry_kg_g()
        tbl = RecipeUnitConversionRegistry()
        tbl.add(1, 30.0, 1)
        fam_reg = FamilyInventoryRegistry()
        fam_reg.add(FamilyInventory(1, "Granos", None, None))
        recipe = Recipe(1, "Test", 1, "", [], ingredients=[
            Ingredient("quinoa", 2.0, 1, None),
        ])

        def resolve(ing: Ingredient) -> tuple[int, Optional[int], int]:
            return (101, 1, 1)

        result = normalize_recipe_for_deduction(
            recipe, fam_reg, unit_reg, tbl, resolve
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 101)
        self.assertEqual(result[0][1], 60.0)
        self.assertEqual(result[0][2], 1)

    def test_ingredient_without_conversion_skipped(self):
        unit_reg = _make_registry_kg_g()
        tbl = RecipeUnitConversionRegistry()
        fam_reg = FamilyInventoryRegistry()
        recipe = Recipe(1, "Test", 1, "", [], ingredients=[
            Ingredient("mystery", 1.0, 99, None),
        ])

        def resolve(ing: Ingredient) -> tuple[int, Optional[int], int]:
            return (102, 1, 1)

        result = normalize_recipe_for_deduction(
            recipe, fam_reg, unit_reg, tbl, resolve
        )
        self.assertEqual(len(result), 0)

    def test_fallback_to_item_unit_when_unit_in_registry(self):
        unit_reg = _make_registry_kg_g()
        tbl = RecipeUnitConversionRegistry()
        fam_reg = FamilyInventoryRegistry()
        recipe = Recipe(1, "Test", 1, "", [], ingredients=[
            Ingredient("pollo", 150.0, 1, 201),
        ])
        # item 201 has unit_id 1 (g); 150 g -> 150 g in item's unit
        def resolve(ing: Ingredient) -> tuple[int, Optional[int], int]:
            return (201, 1, 1)

        result = normalize_recipe_for_deduction(
            recipe, fam_reg, unit_reg, tbl, resolve
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (201, 150.0, 1))

    def test_fallback_with_equivalence_registry_item_specific(self):
        unit_reg = InventoryUnitRegistry()
        unit_reg.add(InventoryUnit(1, "gramo", "g", None, None, 1.0))
        unit_reg.add(InventoryUnit(2, "kilogramo", "kg", None, 1, 1000.0))
        unit_reg.add(InventoryUnit(3, "caja", "caja", None, 2, 10.0))
        eq_reg = InventoryUnitEquivalenceRegistry()
        eq_reg.add(
            InventoryUnitEquivalence(unit_id=3, inventory_item_id=201, base_unit_id=1, factor_to_base=2.0),
            unit_reg,
        )
        eq_reg.add(
            InventoryUnitEquivalence(unit_id=3, inventory_item_id=202, base_unit_id=1, factor_to_base=10.0),
            unit_reg,
        )
        tbl = RecipeUnitConversionRegistry()
        fam_reg = FamilyInventoryRegistry()
        fam_reg = FamilyInventoryRegistry()
        recipe = Recipe(1, "Test", 1, "", [], ingredients=[
            Ingredient("fresas", 1.0, 3, 201),
            Ingredient("naranjas", 1.0, 3, 202),
        ])
        # items 201 and 202 use unit_id 1 (g); equivalence gives 1 caja -> 2 g and 10 g
        def resolve(ing: Ingredient) -> tuple[int, Optional[int], int]:
            return (ing.inventory_item_id or 0, 1, 1)

        result = normalize_recipe_for_deduction(
            recipe, fam_reg, unit_reg, tbl, resolve,
            equivalence_registry=eq_reg,
        )
        self.assertEqual(len(result), 2)
        by_item = {r[0]: (r[1], r[2]) for r in result}
        self.assertEqual(by_item[201][0], 2.0)
        self.assertEqual(by_item[202][0], 10.0)
        self.assertEqual(by_item[201][1], 1)
        self.assertEqual(by_item[202][1], 1)


class TestMakeResolver(unittest.TestCase):
    def test_resolver_returns_item_id_family_id_unit_id(self):
        item = InventoryItem(id=10, name="Harina", unit_id=1, category_id=1, family_id=2)
        def get_item(ing: Ingredient) -> InventoryItem | None:
            return item
        resolve = make_resolver(get_item)
        ing = Ingredient("Harina", 100.0, 1, None)
        self.assertEqual(resolve(ing), (10, 2, 1))

    def test_resolver_raises_when_get_item_returns_none(self):
        def get_item(ing: Ingredient) -> None:
            return None
        resolve = make_resolver(get_item)
        ing = Ingredient("Mystery", 1.0, 1, None)
        with self.assertRaises(ValueError) as ctx:
            resolve(ing)
        self.assertIn("no inventory item", str(ctx.exception).lower())


class TestApplyDeductionLines(unittest.TestCase):
    def test_calls_on_deduct_per_line(self):
        seen: list[tuple[int, float, int]] = []
        def on_deduct(item_id: int, qty: float, unit_id: int) -> None:
            seen.append((item_id, qty, unit_id))
        lines = [(1, 100.0, 1), (2, 0.5, 2)]
        apply_deduction_lines(lines, on_deduct)
        self.assertEqual(seen, [(1, 100.0, 1), (2, 0.5, 2)])

    def test_empty_lines_no_calls(self):
        seen: list[tuple[int, float, int]] = []
        def on_deduct(item_id: int, qty: float, unit_id: int) -> None:
            seen.append((item_id, qty, unit_id))
        apply_deduction_lines([], on_deduct)
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
