"""Unit tests for entity ↔ dict serialization (Task 3.3, Task 3.7 complete coverage)."""

import unittest

from core.domain.data_model import (
    CategoryRecipe,
    FamilyInventory,
    Ingredient,
    InventoryItem,
    InventoryUnit,
    Recipe,
    RecipeUnit,
    Restaurant,
    User,
)
from core.domain.serialization import (
    category_recipe_from_dict,
    category_recipe_to_dict,
    family_inventory_from_dict,
    family_inventory_to_dict,
    inventory_item_from_dict,
    inventory_item_to_dict,
    inventory_unit_from_dict,
    inventory_unit_to_dict,
    recipe_from_dict,
    recipe_to_dict,
    recipe_unit_from_dict,
    recipe_unit_to_dict,
    restaurant_from_dict,
    restaurant_to_dict,
    user_from_dict,
    user_to_dict,
)


class TestRecipeRoundTrip(unittest.TestCase):
    """Round-trip tests for Recipe and embedded ingredients."""

    def test_recipe_with_ingredients_round_trip(self) -> None:
        recipe = Recipe(
            id=1,
            name="Tacos al pastor",
            category_id=2,
            description="Tacos tradicionales",
            steps=["Marinar", "Cortar", "Servir"],
            ingredients=[
                Ingredient("Carne de cerdo", 500.0, 1, 5),
                Ingredient("Tortillas", 12.0, 3, 10),
                Ingredient("Cilantro", 50.0, 1, None),
            ],
        )
        d = recipe_to_dict(recipe)
        restored = recipe_from_dict(d)
        self.assertEqual(restored.id, recipe.id)
        self.assertEqual(restored.name, recipe.name)
        self.assertEqual(restored.category_id, recipe.category_id)
        self.assertEqual(restored.description, recipe.description)
        self.assertEqual(restored.steps, recipe.steps)
        self.assertEqual(len(restored.ingredients), 3)
        self.assertEqual(restored.ingredients[0].name, "Carne de cerdo")
        self.assertEqual(restored.ingredients[0].quantity, 500.0)
        self.assertEqual(restored.ingredients[0].unit_id, 1)
        self.assertEqual(restored.ingredients[0].inventory_item_id, 5)
        self.assertEqual(restored.ingredients[2].inventory_item_id, None)

    def test_recipe_minimal_round_trip(self) -> None:
        recipe = Recipe(
            id=2,
            name="Enchiladas",
            category_id=2,
            description=None,
            steps=None,
            ingredients=[],
        )
        d = recipe_to_dict(recipe)
        restored = recipe_from_dict(d)
        self.assertEqual(restored.id, recipe.id)
        self.assertEqual(restored.name, recipe.name)
        self.assertIsNone(restored.description)
        self.assertIsNone(restored.steps)
        self.assertEqual(restored.ingredients, [])


class TestRestaurantRoundTrip(unittest.TestCase):
    """Round-trip tests for Restaurant."""

    def test_restaurant_full_round_trip(self) -> None:
        r = Restaurant(
            id=1,
            name="La Cocina",
            address="Calle Principal 123",
            restaurant_type_id=1,
            notes="Restaurant principal",
        )
        d = restaurant_to_dict(r)
        restored = restaurant_from_dict(d)
        self.assertEqual(restored.id, r.id)
        self.assertEqual(restored.name, r.name)
        self.assertEqual(restored.address, r.address)
        self.assertEqual(restored.restaurant_type_id, r.restaurant_type_id)
        self.assertEqual(restored.notes, r.notes)

    def test_restaurant_with_nulls_round_trip(self) -> None:
        r = Restaurant(
            id=2,
            name="El Café",
            address=None,
            restaurant_type_id=None,
            notes=None,
        )
        d = restaurant_to_dict(r)
        restored = restaurant_from_dict(d)
        self.assertEqual(restored.id, r.id)
        self.assertEqual(restored.name, r.name)
        self.assertIsNone(restored.address)
        self.assertIsNone(restored.restaurant_type_id)
        self.assertIsNone(restored.notes)


class TestUserRoundTrip(unittest.TestCase):
    """Round-trip tests for User (Task 3.7)."""

    def test_user_round_trip(self) -> None:
        user = User(id=1, name="Alice", email="alice@example.com", role="admin")
        d = user_to_dict(user)
        restored = user_from_dict(d)
        self.assertEqual(restored.id, user.id)
        self.assertEqual(restored.name, user.name)
        self.assertEqual(restored.email, user.email)
        self.assertEqual(restored.role, user.role)


class TestRecipeUnitRoundTrip(unittest.TestCase):
    """Round-trip tests for RecipeUnit (Task 3.7)."""

    def test_recipe_unit_round_trip(self) -> None:
        unit = RecipeUnit(id=1, name="gramo", symbol="g", description="Unidad de masa")
        d = recipe_unit_to_dict(unit)
        restored = recipe_unit_from_dict(d)
        self.assertEqual(restored.id, unit.id)
        self.assertEqual(restored.name, unit.name)
        self.assertEqual(restored.symbol, unit.symbol)
        self.assertEqual(restored.description, unit.description)

    def test_recipe_unit_with_null_description_round_trip(self) -> None:
        unit = RecipeUnit(id=2, name="pieza", symbol="pza", description=None)
        d = recipe_unit_to_dict(unit)
        restored = recipe_unit_from_dict(d)
        self.assertEqual(restored.id, unit.id)
        self.assertIsNone(restored.description)


class TestInventoryUnitRoundTrip(unittest.TestCase):
    """Round-trip tests for InventoryUnit (Task 3.7)."""

    def test_inventory_unit_standard_round_trip(self) -> None:
        unit = InventoryUnit(
            id=1,
            name="kilogramo",
            symbol="kg",
            description="Unidad estándar",
            base_unit_id=None,
            factor_to_base=1.0,
            is_standard=True,
        )
        d = inventory_unit_to_dict(unit)
        restored = inventory_unit_from_dict(d)
        self.assertEqual(restored.id, unit.id)
        self.assertEqual(restored.name, unit.name)
        self.assertEqual(restored.is_standard, True)
        self.assertIsNone(restored.base_unit_id)

    def test_inventory_unit_non_standard_round_trip(self) -> None:
        unit = InventoryUnit(
            id=10,
            name="caja",
            symbol="caja",
            description=None,
            base_unit_id=1,
            factor_to_base=10.0,
            is_standard=False,
        )
        d = inventory_unit_to_dict(unit)
        restored = inventory_unit_from_dict(d)
        self.assertEqual(restored.id, unit.id)
        self.assertEqual(restored.is_standard, False)
        self.assertEqual(restored.base_unit_id, 1)
        self.assertEqual(restored.factor_to_base, 10.0)


class TestCategoryRecipeRoundTrip(unittest.TestCase):
    """Round-trip tests for CategoryRecipe (Task 3.7)."""

    def test_category_recipe_round_trip(self) -> None:
        cat = CategoryRecipe(id=1, name="Entradas", description="Platillos de entrada")
        d = category_recipe_to_dict(cat)
        restored = category_recipe_from_dict(d)
        self.assertEqual(restored.id, cat.id)
        self.assertEqual(restored.name, cat.name)
        self.assertEqual(restored.description, cat.description)

    def test_category_recipe_with_null_description_round_trip(self) -> None:
        cat = CategoryRecipe(id=2, name="Postres", description=None)
        d = category_recipe_to_dict(cat)
        restored = category_recipe_from_dict(d)
        self.assertEqual(restored.id, cat.id)
        self.assertIsNone(restored.description)


class TestFamilyInventoryRoundTrip(unittest.TestCase):
    """Round-trip tests for FamilyInventory (Task 3.7)."""

    def test_family_inventory_round_trip(self) -> None:
        fam = FamilyInventory(id=1, name="Lácteos", description="Productos lácteos", base_unit_id=1)
        d = family_inventory_to_dict(fam)
        restored = family_inventory_from_dict(d)
        self.assertEqual(restored.id, fam.id)
        self.assertEqual(restored.name, fam.name)
        self.assertEqual(restored.description, fam.description)
        self.assertEqual(restored.base_unit_id, fam.base_unit_id)

    def test_family_inventory_with_nulls_round_trip(self) -> None:
        fam = FamilyInventory(id=2, name="Carnes", description=None, base_unit_id=None)
        d = family_inventory_to_dict(fam)
        restored = family_inventory_from_dict(d)
        self.assertEqual(restored.id, fam.id)
        self.assertIsNone(restored.description)
        self.assertIsNone(restored.base_unit_id)


class TestInventoryItemRoundTrip(unittest.TestCase):
    """Round-trip tests for InventoryItem (Task 3.7)."""

    def test_inventory_item_round_trip(self) -> None:
        item = InventoryItem(
            id=15,
            name="Leche",
            stock_unit_id=2,
            purchase_unit_id=5,
            category_id=1,
            purchase_to_stock_factor=10.0,
            family_id=1,
            description="Leche entera",
        )
        d = inventory_item_to_dict(item)
        restored = inventory_item_from_dict(d)
        self.assertEqual(restored.id, item.id)
        self.assertEqual(restored.name, item.name)
        self.assertEqual(restored.stock_unit_id, item.stock_unit_id)
        self.assertEqual(restored.purchase_unit_id, item.purchase_unit_id)
        self.assertEqual(restored.category_id, item.category_id)
        self.assertEqual(restored.purchase_to_stock_factor, item.purchase_to_stock_factor)
        self.assertEqual(restored.family_id, item.family_id)
        self.assertEqual(restored.description, item.description)

    def test_inventory_item_with_null_description_round_trip(self) -> None:
        item = InventoryItem(id=20, name="Arroz", stock_unit_id=1, purchase_unit_id=1, category_id=2, family_id=3, description=None)
        d = inventory_item_to_dict(item)
        restored = inventory_item_from_dict(d)
        self.assertEqual(restored.id, item.id)
        self.assertIsNone(restored.description)


