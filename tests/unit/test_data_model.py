"""Unit tests for core data model entities (subtask 2.1)."""

import unittest

from core.data_model import (
    CategoryRecipe,
    FamilyInventory,
    Ingredient,
    InventoryCategory,
    InventoryItem,
    InventoryUnit,
    Recipe,
    RecipeUnit,
    Restaurant,
)


class TestRecipeUnit(unittest.TestCase):
    def test_instantiation_required(self):
        u = RecipeUnit(id=1, name="gramo", symbol="g")
        self.assertEqual(u.id, 1)
        self.assertEqual(u.name, "gramo")
        self.assertEqual(u.symbol, "g")
        self.assertIsNone(u.description)

    def test_instantiation_with_optional(self):
        u = RecipeUnit(id=2, name="kilogramo", symbol="kg", description="Peso en kilogramos")
        self.assertEqual(u.description, "Peso en kilogramos")


class TestInventoryUnit(unittest.TestCase):
    def test_instantiation_required(self):
        u = InventoryUnit(id=1, name="litro", symbol="L")
        self.assertEqual(u.id, 1)
        self.assertEqual(u.symbol, "L")


class TestCategoryRecipe(unittest.TestCase):
    def test_instantiation(self):
        c = CategoryRecipe(id=1, name="desayuno")
        self.assertEqual(c.id, 1)
        self.assertEqual(c.name, "desayuno")

    def test_instantiation_with_description(self):
        c = CategoryRecipe(id=2, name="comida", description="Platos fuertes")
        self.assertEqual(c.description, "Platos fuertes")


class TestFamilyInventory(unittest.TestCase):
    def test_instantiation(self):
        f = FamilyInventory(id=1, name="Lácteos")
        self.assertEqual(f.id, 1)
        self.assertEqual(f.name, "Lácteos")


class TestInventoryCategory(unittest.TestCase):
    def test_instantiation_perecedero(self):
        c = InventoryCategory(id=1, name="perecedero")
        self.assertEqual(c.id, 1)
        self.assertEqual(c.name, "perecedero")

    def test_instantiation_no_perecedero(self):
        c = InventoryCategory(id=2, name="no perecedero", description="Productos no perecederos")
        self.assertEqual(c.name, "no perecedero")
        self.assertEqual(c.description, "Productos no perecederos")


class TestRestaurant(unittest.TestCase):
    def test_instantiation_required(self):
        r = Restaurant(id=1, name="Mi Restaurante")
        self.assertEqual(r.id, 1)
        self.assertEqual(r.name, "Mi Restaurante")
        self.assertIsNone(r.address)

    def test_instantiation_with_optionals(self):
        r = Restaurant(
            id=1,
            name="Test",
            address="Calle 1",
            restaurant_type="café",
            notes="Notas",
        )
        self.assertEqual(r.restaurant_type, "café")


class TestInventoryItem(unittest.TestCase):
    def test_instantiation_required(self):
        i = InventoryItem(
            id=1,
            name="Leche",
            unit_id=1,
            category_id=1,
        )
        self.assertEqual(i.name, "Leche")
        self.assertEqual(i.unit_id, 1)
        self.assertEqual(i.category_id, 1)
        self.assertIsNone(i.family_id)

    def test_instantiation_with_family(self):
        i = InventoryItem(
            id=2,
            name="Arroz",
            unit_id=2,
            category_id=2,
            family_id=1,
        )
        self.assertEqual(i.category_id, 2)
        self.assertEqual(i.family_id, 1)


class TestIngredient(unittest.TestCase):
    def test_instantiation_required(self):
        ing = Ingredient(name="Harina", quantity=250.0, unit_id=1)
        self.assertEqual(ing.name, "Harina")
        self.assertEqual(ing.quantity, 250.0)
        self.assertEqual(ing.unit_id, 1)
        self.assertIsNone(ing.inventory_item_id)

    def test_instantiation_with_inventory_item_id(self):
        ing = Ingredient(
            name="Leche",
            quantity=100.0,
            unit_id=2,
            inventory_item_id=5,
        )
        self.assertEqual(ing.inventory_item_id, 5)


class TestRecipe(unittest.TestCase):
    def test_instantiation_empty_ingredients(self):
        r = Recipe(
            name="Pasta Carbonara",
            description="Clásica pasta italiana",
            steps=["Paso 1", "Paso 2"],
            category_id=1,
        )
        self.assertEqual(r.name, "Pasta Carbonara")
        self.assertEqual(r.category_id, 1)
        self.assertEqual(r.ingredients, [])
        self.assertIsNone(r.id)

    def test_instantiation_with_ingredients(self):
        ing1 = Ingredient(name="Pasta", quantity=200.0, unit_id=1)
        ing2 = Ingredient(name="Huevo", quantity=2.0, unit_id=2)
        r = Recipe(
            name="Pasta",
            description="Desc",
            steps=["Cocer pasta"],
            category_id=1,
            ingredients=[ing1, ing2],
        )
        self.assertEqual(len(r.ingredients), 2)
        self.assertEqual(r.ingredients[0].name, "Pasta")
        self.assertEqual(r.ingredients[0].quantity, 200.0)
        self.assertEqual(r.ingredients[1].name, "Huevo")

    def test_recipe_ingredients_default_factory(self):
        """Each recipe gets its own list; mutating one does not affect another."""
        r1 = Recipe("A", "Desc A", [], category_id=1)
        r2 = Recipe("B", "Desc B", [], category_id=1)
        r1.ingredients.append(Ingredient("X", 1.0, 1))
        self.assertEqual(len(r1.ingredients), 1)
        self.assertEqual(len(r2.ingredients), 0)

    def test_recipe_with_optional_id(self):
        r = Recipe(
            name="R",
            description="D",
            steps=[],
            category_id=1,
            id=42,
        )
        self.assertEqual(r.id, 42)


class TestRecipeIngredientRelationship(unittest.TestCase):
    """Test that Recipe–Ingredient relationship works correctly."""

    def test_add_ingredients_to_recipe_via_constructor(self):
        ings = [
            Ingredient("Agua", 500.0, 1),
            Ingredient("Sal", 10.0, 2),
        ]
        recipe = Recipe(
            name="Caldo",
            description="Caldo simple",
            steps=["Hervir agua", "Añadir sal"],
            category_id=1,
            ingredients=ings,
        )
        self.assertEqual(len(recipe.ingredients), 2)
        self.assertEqual(recipe.ingredients[0].name, "Agua")
        self.assertEqual(recipe.ingredients[1].quantity, 10.0)


if __name__ == "__main__":
    unittest.main()
