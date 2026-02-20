"""Unit tests for entity ↔ dict serialization (Task 3.3)."""

import unittest

from core.data_model import Ingredient, Recipe, Restaurant
from core.serialization import (
    recipe_from_dict,
    recipe_to_dict,
    restaurant_from_dict,
    restaurant_to_dict,
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
