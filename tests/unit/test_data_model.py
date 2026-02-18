"""Unit tests for core data model entities (subtask 2.1 and 2.2)."""

import unittest

from core.data_model import (
    CategoryRecipe,
    CategoryRecipeRegistry,
    DEFAULT_INVENTORY_CATEGORIES,
    DEFAULT_RESTAURANT_TYPES,
    FamilyInventory,
    get_category_recipe_template,
    get_family_inventory_template,
    FamilyInventoryRegistry,
    Ingredient,
    InventoryCategory,
    InventoryItem,
    InventoryItemRegistry,
    InventoryUnit,
    InventoryUnitEquivalence,
    InventoryUnitEquivalenceRegistry,
    InventoryUnitRegistry,
    Recipe,
    RecipeUnit,
    RecipeUnitRegistry,
    Restaurant,
    RestaurantType,
    User,
    UserRegistry,
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

    def test_instantiation_with_equivalence(self):
        u = InventoryUnit(
            id=2, name="Caja", symbol="caja",
            base_unit_id=1, factor_to_base=10.0,
        )
        self.assertEqual(u.base_unit_id, 1)
        self.assertEqual(u.factor_to_base, 10.0)

    def test_is_standard_default_true(self):
        u = InventoryUnit(id=1, name="litro", symbol="L")
        self.assertTrue(u.is_standard)

    def test_is_standard_explicit_true(self):
        u = InventoryUnit(id=1, name="kg", symbol="kg", is_standard=True)
        self.assertTrue(u.is_standard)

    def test_is_standard_explicit_false(self):
        u = InventoryUnit(id=1, name="caja", symbol="caja", is_standard=False)
        self.assertFalse(u.is_standard)


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


class TestRestaurantType(unittest.TestCase):
    def test_instantiation(self):
        t = RestaurantType(id=1, name="Casual")
        self.assertEqual(t.id, 1)
        self.assertEqual(t.name, "Casual")

    def test_instantiation_with_description(self):
        t = RestaurantType(id=2, name="Gourmet", description="Alta cocina")
        self.assertEqual(t.description, "Alta cocina")


class TestUser(unittest.TestCase):
    def test_instantiation(self):
        u = User(id=1, name="Ana López", email="ana@example.com", role="admin")
        self.assertEqual(u.id, 1)
        self.assertEqual(u.name, "Ana López")
        self.assertEqual(u.email, "ana@example.com")
        self.assertEqual(u.role, "admin")

    def test_instantiation_user_role(self):
        u = User(id=2, name="Juan Pérez", email="juan@example.com", role="mesero")
        self.assertEqual(u.role, "mesero")


class TestRestaurant(unittest.TestCase):
    def test_instantiation_required(self):
        r = Restaurant(id=1, name="Mi Restaurante")
        self.assertEqual(r.id, 1)
        self.assertEqual(r.name, "Mi Restaurante")
        self.assertIsNone(r.address)
        self.assertIsNone(r.restaurant_type_id)

    def test_instantiation_with_optionals(self):
        r = Restaurant(
            id=1,
            name="Test",
            address="Calle 1",
            restaurant_type_id=1,
            notes="Notas",
        )
        self.assertEqual(r.restaurant_type_id, 1)


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
            id=0,
            name="Pasta Carbonara",
            description="Clásica pasta italiana",
            steps=["Paso 1", "Paso 2"],
            category_id=1,
        )
        self.assertEqual(r.name, "Pasta Carbonara")
        self.assertEqual(r.category_id, 1)
        self.assertEqual(r.ingredients, [])
        self.assertEqual(r.id, 0)

    def test_instantiation_with_ingredients(self):
        ing1 = Ingredient(name="Pasta", quantity=200.0, unit_id=1)
        ing2 = Ingredient(name="Huevo", quantity=2.0, unit_id=2)
        r = Recipe(
            id=0,
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
        r1 = Recipe(0, "A", "Desc A", [], 1)
        r2 = Recipe(0, "B", "Desc B", [], 1)
        r1.ingredients.append(Ingredient("X", 1.0, 1))
        self.assertEqual(len(r1.ingredients), 1)
        self.assertEqual(len(r2.ingredients), 0)

    def test_recipe_required_id(self):
        r = Recipe(
            id=42,
            name="R",
            description="D",
            steps=[],
            category_id=1,
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
            id=0,
            name="Caldo",
            description="Caldo simple",
            steps=["Hervir agua", "Añadir sal"],
            category_id=1,
            ingredients=ings,
        )
        self.assertEqual(len(recipe.ingredients), 2)
        self.assertEqual(recipe.ingredients[0].name, "Agua")
        self.assertEqual(recipe.ingredients[1].quantity, 10.0)


# --- Subtask 2.2: Recipe add_ingredient, remove_ingredient, helpers ---


class TestRecipeAddIngredient(unittest.TestCase):
    def test_add_ingredient_success(self):
        recipe = Recipe(0, "R", "D", [], 1)
        valid = {1, 2}
        ing = Ingredient("Harina", 250.0, 1)
        out = recipe.add_ingredient(ing, valid)
        self.assertIsNone(out)
        self.assertEqual(len(recipe.ingredients), 1)
        self.assertEqual(recipe.ingredients[0].name, "Harina")

    def test_add_ingredient_empty_name_raises(self):
        recipe = Recipe(0, "R", "D", [], 1)
        ing = Ingredient("  ", 1.0, 1)
        with self.assertRaises(ValueError) as ctx:
            recipe.add_ingredient(ing, {1})
        self.assertIn("non-empty", str(ctx.exception))

    def test_add_ingredient_quantity_zero_raises(self):
        recipe = Recipe(0, "R", "D", [], 1)
        ing = Ingredient("Sal", 0.0, 1)
        with self.assertRaises(ValueError) as ctx:
            recipe.add_ingredient(ing, {1})
        self.assertIn("finite and > 0", str(ctx.exception))

    def test_add_ingredient_nan_raises(self):
        recipe = Recipe(0, "R", "D", [], 1)
        ing = Ingredient("X", float("nan"), 1)
        with self.assertRaises(ValueError):
            recipe.add_ingredient(ing, {1})

    def test_add_ingredient_invalid_unit_id_raises(self):
        recipe = Recipe(0, "R", "D", [], 1)
        ing = Ingredient("Harina", 1.0, 99)
        with self.assertRaises(ValueError) as ctx:
            recipe.add_ingredient(ing, {1, 2})
        self.assertIn("valid_unit_ids", str(ctx.exception))

    def test_add_ingredient_creates_inventory_item_when_category_provided(self):
        recipe = Recipe(0, "R", "D", [], 1)
        ing = Ingredient("Leche", 100.0, 1)
        valid_units = {1}
        valid_inv_units = {1, 2}
        new_item = recipe.add_ingredient(
            ing,
            valid_units,
            category_id=1,
            unit_id_for_inventory=1,
            valid_inventory_unit_ids=valid_inv_units,
        )
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.id, 0)
        self.assertEqual(new_item.name, "Leche")
        self.assertEqual(new_item.unit_id, 1)
        self.assertEqual(new_item.category_id, 1)
        self.assertEqual(len(recipe.ingredients), 1)

    def test_add_ingredient_category_without_valid_inventory_unit_ids_raises(self):
        recipe = Recipe(0, "R", "D", [], 1)
        ing = Ingredient("Leche", 1.0, 1)
        with self.assertRaises(ValueError) as ctx:
            recipe.add_ingredient(ing, {1}, category_id=1, unit_id_for_inventory=1)
        self.assertIn("valid_inventory_unit_ids", str(ctx.exception))

    def test_add_ingredient_family_id_requires_valid_family_ids(self):
        recipe = Recipe(0, "R", "D", [], 1)
        ing = Ingredient("Queso", 50.0, 1)
        with self.assertRaises(ValueError) as ctx:
            recipe.add_ingredient(
                ing, {1},
                category_id=1, unit_id_for_inventory=1,
                valid_inventory_unit_ids={1},
                family_id=99,
                valid_family_inventory_ids={1, 2},
            )
        self.assertIn("valid_family_inventory_ids", str(ctx.exception))

    def test_add_ingredient_invalid_category_id_raises(self):
        recipe = Recipe(0, "R", "D", [], 1)
        ing = Ingredient("Leche", 100.0, 1)
        with self.assertRaises(ValueError) as ctx:
            recipe.add_ingredient(
                ing, {1},
                category_id=99,
                unit_id_for_inventory=1,
                valid_inventory_unit_ids={1},
            )
        self.assertIn("category_id", str(ctx.exception))
        self.assertIn("Perecedero", str(ctx.exception))

    def test_add_ingredient_new_item_standard_unit_no_equivalence(self):
        """Creating new item with standard unit does not require equivalence args."""
        recipe = Recipe(0, "R", "D", [], 1)
        ing = Ingredient("Harina", 500.0, 1)
        valid_units = {1}
        valid_inv_units = {1, 2}
        new_item = recipe.add_ingredient(
            ing,
            valid_units,
            category_id=1,
            unit_id_for_inventory=1,
            valid_inventory_unit_ids=valid_inv_units,
            unit_requires_equivalence=False,
        )
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.unit_id, 1)
        self.assertEqual(len(recipe.ingredients), 1)

    def test_add_ingredient_new_item_non_standard_unit_without_equivalence_raises(self):
        """Creating new item with unit_requires_equivalence=True but no equivalence args raises."""
        recipe = Recipe(0, "R", "D", [], 1)
        ing = Ingredient("Fresas", 2.0, 1)
        valid_units = {1}
        valid_inv_units = {1, 2}  # 1=kg, 2=caja
        with self.assertRaises(ValueError) as ctx:
            recipe.add_ingredient(
                ing,
                valid_units,
                category_id=1,
                unit_id_for_inventory=2,
                valid_inventory_unit_ids=valid_inv_units,
                unit_requires_equivalence=True,
            )
        self.assertIn("equivalence_base_unit_id", str(ctx.exception))
        self.assertIn("equivalence_factor_to_base", str(ctx.exception))

    def test_add_ingredient_new_item_non_standard_unit_with_valid_equivalence_succeeds(self):
        """Creating new item with unit_requires_equivalence=True and valid equivalence args succeeds."""
        recipe = Recipe(0, "R", "D", [], 1)
        ing = Ingredient("Fresas", 2.0, 1)
        valid_units = {1}
        valid_inv_units = {1, 2}  # 1=kg (base), 2=caja
        new_item = recipe.add_ingredient(
            ing,
            valid_units,
            category_id=1,
            unit_id_for_inventory=2,
            valid_inventory_unit_ids=valid_inv_units,
            unit_requires_equivalence=True,
            equivalence_base_unit_id=1,
            equivalence_factor_to_base=5.0,
        )
        self.assertIsNotNone(new_item)
        self.assertEqual(new_item.unit_id, 2)
        self.assertEqual(len(recipe.ingredients), 1)

    def test_add_ingredient_equivalence_base_unit_id_not_in_valid_raises(self):
        recipe = Recipe(0, "R", "D", [], 1)
        ing = Ingredient("Fresas", 1.0, 1)
        with self.assertRaises(ValueError) as ctx:
            recipe.add_ingredient(
                ing, {1},
                category_id=1,
                unit_id_for_inventory=2,
                valid_inventory_unit_ids={1, 2},
                unit_requires_equivalence=True,
                equivalence_base_unit_id=99,
                equivalence_factor_to_base=5.0,
            )
        self.assertIn("equivalence_base_unit_id", str(ctx.exception))
        self.assertIn("valid_inventory_unit_ids", str(ctx.exception))

    def test_add_ingredient_equivalence_factor_invalid_raises(self):
        recipe = Recipe(0, "R", "D", [], 1)
        ing = Ingredient("Fresas", 1.0, 1)
        with self.assertRaises(ValueError) as ctx:
            recipe.add_ingredient(
                ing, {1},
                category_id=1,
                unit_id_for_inventory=2,
                valid_inventory_unit_ids={1, 2},
                unit_requires_equivalence=True,
                equivalence_base_unit_id=1,
                equivalence_factor_to_base=0.0,
            )
        self.assertIn("equivalence_factor_to_base", str(ctx.exception))

    def test_add_ingredient_duplicate_name_replaces_and_returns_none(self):
        """Adding an ingredient with same name (case-insensitive) updates existing and returns None."""
        recipe = Recipe(0, "R", "D", [], 1)
        valid = {1, 2}
        recipe.add_ingredient(Ingredient("Queso Oaxaca", 100.0, 1), valid)
        self.assertEqual(len(recipe.ingredients), 1)
        self.assertEqual(recipe.ingredients[0].quantity, 100.0)
        out = recipe.add_ingredient(
            Ingredient("queso oaxaca", 250.0, 2),
            valid,
        )
        self.assertIsNone(out)
        self.assertEqual(len(recipe.ingredients), 1)
        self.assertEqual(recipe.ingredients[0].name, "Queso Oaxaca")
        self.assertEqual(recipe.ingredients[0].quantity, 250.0)
        self.assertEqual(recipe.ingredients[0].unit_id, 2)

    def test_add_ingredient_different_names_both_present(self):
        """Adding ingredients with different names keeps both."""
        recipe = Recipe(0, "R", "D", [], 1)
        valid = {1}
        recipe.add_ingredient(Ingredient("Harina", 200.0, 1), valid)
        recipe.add_ingredient(Ingredient("Azúcar", 50.0, 1), valid)
        self.assertEqual(len(recipe.ingredients), 2)
        self.assertEqual(recipe.ingredients[0].name, "Harina")
        self.assertEqual(recipe.ingredients[1].name, "Azúcar")


class TestRecipeRemoveIngredient(unittest.TestCase):
    def test_remove_by_index(self):
        recipe = Recipe(
            0, "R", "D", [], 1,
            ingredients=[
                Ingredient("A", 1.0, 1),
                Ingredient("B", 2.0, 1),
            ],
        )
        removed = recipe.remove_ingredient(0)
        self.assertIsNotNone(removed)
        self.assertEqual(removed.name, "A")
        self.assertEqual(len(recipe.ingredients), 1)
        self.assertEqual(recipe.ingredients[0].name, "B")

    def test_remove_by_index_out_of_range_raises(self):
        recipe = Recipe(0, "R", "D", [], 1, ingredients=[Ingredient("A", 1.0, 1)])
        with self.assertRaises(IndexError):
            recipe.remove_ingredient(1)
        with self.assertRaises(IndexError):
            recipe.remove_ingredient(-1)

    def test_remove_by_name(self):
        recipe = Recipe(
            0, "R", "D", [], 1,
            ingredients=[Ingredient("Sal", 10.0, 1), Ingredient("Pimienta", 1.0, 1)],
        )
        removed = recipe.remove_ingredient("sal")
        self.assertIsNotNone(removed)
        self.assertEqual(removed.name, "Sal")
        self.assertEqual(len(recipe.ingredients), 1)

    def test_remove_by_name_missing_returns_none(self):
        recipe = Recipe(0, "R", "D", [], 1, ingredients=[Ingredient("A", 1.0, 1)])
        self.assertIsNone(recipe.remove_ingredient("NoExiste"))

    def test_remove_by_ingredient_object(self):
        a = Ingredient("A", 1.0, 1)
        recipe = Recipe(0, "R", "D", [], 1, ingredients=[a, Ingredient("B", 2.0, 1)])
        removed = recipe.remove_ingredient(a)
        self.assertIsNotNone(removed)
        self.assertEqual(removed.name, "A")
        self.assertEqual(len(recipe.ingredients), 1)


class TestRecipeIngredientHelpers(unittest.TestCase):
    def test_ingredient_count(self):
        recipe = Recipe(
            0, "R", "D", [], 1,
            ingredients=[Ingredient("A", 1.0, 1), Ingredient("B", 1.0, 1)],
        )
        self.assertEqual(recipe.ingredient_count(), 2)

    def test_has_ingredient(self):
        recipe = Recipe(0, "R", "D", [], 1, ingredients=[Ingredient("Harina", 1.0, 1)])
        self.assertTrue(recipe.has_ingredient("harina"))
        self.assertTrue(recipe.has_ingredient("HARINA"))
        self.assertFalse(recipe.has_ingredient("Sal"))

    def test_get_ingredient_by_name(self):
        recipe = Recipe(0, "R", "D", [], 1, ingredients=[Ingredient("Sal", 10.0, 1)])
        ing = recipe.get_ingredient_by_name("sal")
        self.assertIsNotNone(ing)
        self.assertEqual(ing.quantity, 10.0)
        self.assertIsNone(recipe.get_ingredient_by_name("NoExiste"))

    def test_update_category_id(self):
        recipe = Recipe(0, "R", "D", [], 1)
        recipe.update_category_id(2, valid_ids={1, 2, 3})
        self.assertEqual(recipe.category_id, 2)

    def test_update_category_id_invalid_raises(self):
        recipe = Recipe(0, "R", "D", [], 1)
        with self.assertRaises(ValueError) as ctx:
            recipe.update_category_id(99, valid_ids={1, 2})
        self.assertIn("valid_ids", str(ctx.exception))


class TestRestaurantUpdateClear(unittest.TestCase):
    def test_update_restaurant_type_id_valid(self):
        r = Restaurant(1, "Test")
        r.update_restaurant_type_id(1)
        self.assertEqual(r.restaurant_type_id, 1)
        r.update_restaurant_type_id(5)
        self.assertEqual(r.restaurant_type_id, 5)

    def test_update_restaurant_type_id_invalid_raises(self):
        r = Restaurant(1, "Test")
        with self.assertRaises(ValueError) as ctx:
            r.update_restaurant_type_id(99)
        self.assertIn("restaurant_type_id", str(ctx.exception))

    def test_clear_address_restaurant_type_notes(self):
        r = Restaurant(1, "T", address="Calle", restaurant_type_id=1, notes="N")
        r.clear_address()
        r.clear_restaurant_type_id()
        r.clear_notes()
        self.assertIsNone(r.address)
        self.assertIsNone(r.restaurant_type_id)
        self.assertIsNone(r.notes)


class TestInventoryItemUpdateFamilyId(unittest.TestCase):
    def test_update_family_id_success(self):
        item = InventoryItem(1, "Leche", 1, 1)
        item.update_family_id(2, valid_ids={1, 2, 3})
        self.assertEqual(item.family_id, 2)

    def test_update_family_id_invalid_raises(self):
        item = InventoryItem(1, "Leche", 1, 1)
        with self.assertRaises(ValueError) as ctx:
            item.update_family_id(99, valid_ids={1, 2})
        self.assertIn("valid_ids", str(ctx.exception))


class TestInventoryItemUpdateCategoryId(unittest.TestCase):
    def test_update_category_id_default_valid_ids(self):
        item = InventoryItem(1, "Leche", 1, 1)
        item.update_category_id(2)  # No perecedero; valid_ids=None uses fixed set {1, 2}
        self.assertEqual(item.category_id, 2)

    def test_update_category_id_invalid_raises(self):
        item = InventoryItem(1, "Leche", 1, 1)
        with self.assertRaises(ValueError) as ctx:
            item.update_category_id(99)
        self.assertIn("valid_ids", str(ctx.exception))


class TestDEFAULT_RESTAURANT_TYPES(unittest.TestCase):
    def test_five_types(self):
        self.assertEqual(len(DEFAULT_RESTAURANT_TYPES), 5)
        ids = {t.id for t in DEFAULT_RESTAURANT_TYPES}
        self.assertEqual(ids, {1, 2, 3, 4, 5})


class TestDEFAULT_INVENTORY_CATEGORIES(unittest.TestCase):
    def test_two_categories_perecedero_no_perecedero(self):
        self.assertEqual(len(DEFAULT_INVENTORY_CATEGORIES), 2)
        ids = {c.id for c in DEFAULT_INVENTORY_CATEGORIES}
        names = {c.name for c in DEFAULT_INVENTORY_CATEGORIES}
        self.assertEqual(ids, {1, 2})
        self.assertEqual(names, {"Perecedero", "No perecedero"})


# --- Registries (2.2) ---


class TestRecipeUnitRegistry(unittest.TestCase):
    def test_add_success(self):
        reg = RecipeUnitRegistry()
        reg.add(RecipeUnit(1, "gramo", "g"))
        self.assertEqual(reg.valid_ids(), {1})
        self.assertEqual(reg.get(1).name, "gramo")

    def test_add_duplicate_id_raises(self):
        reg = RecipeUnitRegistry()
        reg.add(RecipeUnit(1, "gramo", "g"))
        with self.assertRaises(ValueError) as ctx:
            reg.add(RecipeUnit(1, "otro", "o"))
        self.assertIn("duplicate", str(ctx.exception))

    def test_add_duplicate_symbol_raises(self):
        reg = RecipeUnitRegistry()
        reg.add(RecipeUnit(1, "gramo", "g"))
        with self.assertRaises(ValueError) as ctx:
            reg.add(RecipeUnit(2, "gramos", "g"))
        self.assertIn("symbol", str(ctx.exception))

    def test_add_empty_name_raises(self):
        reg = RecipeUnitRegistry()
        with self.assertRaises(ValueError):
            reg.add(RecipeUnit(1, "  ", "g"))

    def test_add_empty_symbol_raises(self):
        reg = RecipeUnitRegistry()
        with self.assertRaises(ValueError):
            reg.add(RecipeUnit(1, "gramo", ""))

    def test_remove_success(self):
        reg = RecipeUnitRegistry()
        reg.add(RecipeUnit(1, "g", "g"))
        u = reg.remove(1)
        self.assertIsNotNone(u)
        self.assertEqual(u.id, 1)
        self.assertEqual(reg.valid_ids(), set())

    def test_remove_in_use_raises(self):
        reg = RecipeUnitRegistry()
        reg.add(RecipeUnit(1, "g", "g"))
        ings = [Ingredient("A", 1.0, 1)]
        with self.assertRaises(ValueError) as ctx:
            reg.remove(1, ingredients=ings)
        self.assertIn("in use", str(ctx.exception))


class TestInventoryUnitRegistry(unittest.TestCase):
    def test_add_success_no_base(self):
        reg = InventoryUnitRegistry()
        reg.add(InventoryUnit(1, "kg", "kg"))
        self.assertEqual(reg.valid_ids(), {1})

    def test_add_with_base_unit(self):
        reg = InventoryUnitRegistry()
        reg.add(InventoryUnit(1, "kg", "kg"))
        reg.add(InventoryUnit(2, "Caja", "caja", base_unit_id=1, factor_to_base=10.0))
        self.assertEqual(reg.valid_ids(), {1, 2})

    def test_add_base_unit_id_not_in_registry_raises(self):
        reg = InventoryUnitRegistry()
        with self.assertRaises(ValueError) as ctx:
            reg.add(InventoryUnit(1, "Caja", "caja", base_unit_id=99, factor_to_base=10.0))
        self.assertIn("base_unit_id", str(ctx.exception))

    def test_add_factor_to_base_zero_raises(self):
        reg = InventoryUnitRegistry()
        reg.add(InventoryUnit(1, "kg", "kg"))
        with self.assertRaises(ValueError):
            reg.add(InventoryUnit(2, "Caja", "caja", base_unit_id=1, factor_to_base=0.0))

    def test_add_self_reference_raises(self):
        reg = InventoryUnitRegistry()
        reg.add(InventoryUnit(1, "kg", "kg"))
        with self.assertRaises(ValueError) as ctx:
            reg.add(InventoryUnit(2, "Caja", "caja", base_unit_id=2, factor_to_base=10.0))
        self.assertIn("cycle", str(ctx.exception).lower())

    def test_remove_in_use_raises(self):
        reg = InventoryUnitRegistry()
        reg.add(InventoryUnit(1, "kg", "kg"))
        items = [InventoryItem(1, "X", 1, 1)]
        with self.assertRaises(ValueError):
            reg.remove(1, inventory_items=items)


class TestInventoryUnitEquivalence(unittest.TestCase):
    def test_instantiation(self):
        eq = InventoryUnitEquivalence(
            unit_id=3,
            inventory_item_id=101,
            base_unit_id=1,
            factor_to_base=2.0,
        )
        self.assertEqual(eq.unit_id, 3)
        self.assertEqual(eq.inventory_item_id, 101)
        self.assertEqual(eq.base_unit_id, 1)
        self.assertEqual(eq.factor_to_base, 2.0)


class TestInventoryUnitEquivalenceRegistry(unittest.TestCase):
    def _unit_registry(self):
        reg = InventoryUnitRegistry()
        reg.add(InventoryUnit(1, "gramo", "g"))
        reg.add(InventoryUnit(2, "kilogramo", "kg", base_unit_id=1, factor_to_base=1000.0))
        reg.add(InventoryUnit(3, "caja", "caja"))
        return reg

    def test_add_and_get(self):
        unit_reg = self._unit_registry()
        eq_reg = InventoryUnitEquivalenceRegistry()
        eq = InventoryUnitEquivalence(
            unit_id=3, inventory_item_id=10, base_unit_id=1, factor_to_base=2.0
        )
        eq_reg.add(eq, unit_reg)
        self.assertIs(eq_reg.get(3, 10), eq)
        self.assertIsNone(eq_reg.get(3, 99))
        self.assertIsNone(eq_reg.get(2, 10))

    def test_add_duplicate_raises(self):
        unit_reg = self._unit_registry()
        eq_reg = InventoryUnitEquivalenceRegistry()
        eq = InventoryUnitEquivalence(
            unit_id=3, inventory_item_id=10, base_unit_id=1, factor_to_base=2.0
        )
        eq_reg.add(eq, unit_reg)
        with self.assertRaises(ValueError) as ctx:
            eq_reg.add(eq, unit_reg)
        self.assertIn("duplicate", str(ctx.exception))

    def test_add_invalid_unit_id_raises(self):
        unit_reg = self._unit_registry()
        eq_reg = InventoryUnitEquivalenceRegistry()
        eq = InventoryUnitEquivalence(
            unit_id=99, inventory_item_id=10, base_unit_id=1, factor_to_base=2.0
        )
        with self.assertRaises(ValueError) as ctx:
            eq_reg.add(eq, unit_reg)
        self.assertIn("unit_id", str(ctx.exception))

    def test_add_invalid_base_unit_id_raises(self):
        unit_reg = self._unit_registry()
        eq_reg = InventoryUnitEquivalenceRegistry()
        eq = InventoryUnitEquivalence(
            unit_id=3, inventory_item_id=10, base_unit_id=99, factor_to_base=2.0
        )
        with self.assertRaises(ValueError) as ctx:
            eq_reg.add(eq, unit_reg)
        self.assertIn("base_unit_id", str(ctx.exception))

    def test_add_factor_to_base_zero_raises(self):
        unit_reg = self._unit_registry()
        eq_reg = InventoryUnitEquivalenceRegistry()
        eq = InventoryUnitEquivalence(
            unit_id=3, inventory_item_id=10, base_unit_id=1, factor_to_base=0.0
        )
        with self.assertRaises(ValueError) as ctx:
            eq_reg.add(eq, unit_reg)
        self.assertIn("factor_to_base", str(ctx.exception))

    def test_remove(self):
        unit_reg = self._unit_registry()
        eq_reg = InventoryUnitEquivalenceRegistry()
        eq = InventoryUnitEquivalence(
            unit_id=3, inventory_item_id=10, base_unit_id=1, factor_to_base=2.0
        )
        eq_reg.add(eq, unit_reg)
        removed = eq_reg.remove(3, 10)
        self.assertIs(removed, eq)
        self.assertIsNone(eq_reg.get(3, 10))
        self.assertIsNone(eq_reg.remove(3, 10))


class TestGetCategoryRecipeTemplate(unittest.TestCase):
    def test_template_for_casual_has_four_categories(self):
        t = get_category_recipe_template(1)
        self.assertEqual(len(t), 4)
        names = {c.name for c in t}
        self.assertIn("Entradas", names)
        self.assertIn("Bebidas", names)
        for c in t:
            self.assertEqual(c.id, 0, "template categories use id=0")

    def test_template_for_cafes_has_four_categories(self):
        t = get_category_recipe_template(5)
        self.assertEqual(len(t), 4)
        self.assertIn("Bebidas calientes", {c.name for c in t})

    def test_template_invalid_restaurant_type_returns_empty(self):
        self.assertEqual(get_category_recipe_template(99), ())


class TestGetFamilyInventoryTemplate(unittest.TestCase):
    def test_template_for_casual_has_families(self):
        t = get_family_inventory_template(1)
        self.assertGreaterEqual(len(t), 6)
        names = {f.name for f in t}
        self.assertIn("Lácteos", names)
        self.assertIn("Carnes", names)
        self.assertIn("Bebidas", names)
        for f in t:
            self.assertEqual(f.id, 0, "template families use id=0")

    def test_template_for_cafes_has_families(self):
        t = get_family_inventory_template(5)
        self.assertGreaterEqual(len(t), 4)
        self.assertIn("Panadería y repostería", {f.name for f in t})

    def test_template_invalid_restaurant_type_returns_empty(self):
        self.assertEqual(get_family_inventory_template(99), ())


class TestCategoryRecipeRegistry(unittest.TestCase):
    def test_add_remove_valid_ids_get(self):
        reg = CategoryRecipeRegistry()
        reg.add(CategoryRecipe(1, "Desayuno"))
        self.assertEqual(reg.valid_ids(), {1})
        self.assertEqual(reg.get(1).name, "Desayuno")
        reg.remove(1)
        self.assertEqual(reg.valid_ids(), set())
        self.assertIsNone(reg.get(1))

    def test_add_duplicate_name_raises(self):
        reg = CategoryRecipeRegistry()
        reg.add(CategoryRecipe(1, "Desayuno"))
        with self.assertRaises(ValueError):
            reg.add(CategoryRecipe(2, "desayuno"))

    def test_remove_in_use_raises(self):
        reg = CategoryRecipeRegistry()
        reg.add(CategoryRecipe(1, "D"))
        recipes = [Recipe(0, "R", "D", [], 1)]
        with self.assertRaises(ValueError):
            reg.remove(1, recipes=recipes)

    def test_update_name_success(self):
        reg = CategoryRecipeRegistry()
        reg.add(CategoryRecipe(1, "Desayuno"))
        reg.update(1, {"name": "Desayunos"})
        self.assertEqual(reg.get(1).name, "Desayunos")

    def test_update_description(self):
        reg = CategoryRecipeRegistry()
        reg.add(CategoryRecipe(1, "D"))
        reg.update(1, {"description": "Para la mañana"})
        self.assertEqual(reg.get(1).description, "Para la mañana")

    def test_update_empty_name_raises(self):
        reg = CategoryRecipeRegistry()
        reg.add(CategoryRecipe(1, "D"))
        with self.assertRaises(ValueError) as ctx:
            reg.update(1, {"name": "  "})
        self.assertIn("non-empty", str(ctx.exception))

    def test_update_duplicate_name_raises(self):
        reg = CategoryRecipeRegistry()
        reg.add(CategoryRecipe(1, "A"))
        reg.add(CategoryRecipe(2, "B"))
        with self.assertRaises(ValueError) as ctx:
            reg.update(2, {"name": "a"})
        self.assertIn("duplicate", str(ctx.exception))

    def test_update_category_not_found_raises(self):
        reg = CategoryRecipeRegistry()
        with self.assertRaises(ValueError) as ctx:
            reg.update(1, {"name": "X"})
        self.assertIn("not found", str(ctx.exception))


class TestFamilyInventoryRegistry(unittest.TestCase):
    def test_add_remove_valid_ids_get(self):
        reg = FamilyInventoryRegistry()
        reg.add(FamilyInventory(1, "Lácteos"))
        self.assertEqual(reg.valid_ids(), {1})
        reg.remove(1)
        self.assertIsNone(reg.get(1))

    def test_remove_in_use_raises(self):
        reg = FamilyInventoryRegistry()
        reg.add(FamilyInventory(1, "L"))
        items = [InventoryItem(1, "X", 1, 1, family_id=1)]
        with self.assertRaises(ValueError):
            reg.remove(1, inventory_items=items)


class TestInventoryItemRegistry(unittest.TestCase):
    def test_add_get_get_by_name_valid_ids_list_all(self):
        reg = InventoryItemRegistry()
        item = InventoryItem(1, "Leche", 1, 1)
        reg.add(item)
        self.assertEqual(reg.get(1), item)
        self.assertEqual(reg.get_by_name("Leche"), item)
        self.assertEqual(reg.get_by_name("  leche  "), item)
        self.assertEqual(reg.valid_ids(), {1})
        self.assertEqual(reg.list_all(), [item])

    def test_add_duplicate_name_raises(self):
        reg = InventoryItemRegistry()
        reg.add(InventoryItem(1, "Queso", 1, 1))
        with self.assertRaises(ValueError) as ctx:
            reg.add(InventoryItem(2, "queso", 1, 1))
        self.assertIn("duplicate", str(ctx.exception).lower())
        self.assertIn("name", str(ctx.exception).lower())

    def test_add_duplicate_id_raises(self):
        reg = InventoryItemRegistry()
        reg.add(InventoryItem(1, "A", 1, 1))
        with self.assertRaises(ValueError) as ctx:
            reg.add(InventoryItem(1, "B", 1, 1))
        self.assertIn("duplicate", str(ctx.exception).lower())
        self.assertIn("id", str(ctx.exception).lower())

    def test_add_empty_name_raises(self):
        reg = InventoryItemRegistry()
        with self.assertRaises(ValueError) as ctx:
            reg.add(InventoryItem(1, "  ", 1, 1))
        self.assertIn("non-empty", str(ctx.exception))

    def test_add_invalid_category_id_raises(self):
        reg = InventoryItemRegistry()
        with self.assertRaises(ValueError) as ctx:
            reg.add(InventoryItem(1, "X", 1, 99))
        self.assertIn("category_id", str(ctx.exception))

    def test_remove_returns_item(self):
        reg = InventoryItemRegistry()
        item = InventoryItem(1, "Harina", 1, 1)
        reg.add(item)
        removed = reg.remove(1)
        self.assertIs(removed, item)
        self.assertIsNone(reg.get(1))
        self.assertEqual(len(reg.list_all()), 0)

    def test_remove_missing_returns_none(self):
        reg = InventoryItemRegistry()
        reg.add(InventoryItem(1, "X", 1, 1))
        self.assertIsNone(reg.remove(99))

    def test_remove_when_in_use_by_recipe_raises(self):
        reg = InventoryItemRegistry()
        item = InventoryItem(1, "Leche", 1, 1)
        reg.add(item)
        recipe = Recipe(0, "R", "D", [], 1, ingredients=[Ingredient("Leche", 100.0, 1)])
        with self.assertRaises(ValueError) as ctx:
            reg.remove(1, recipes=[recipe])
        self.assertIn("in use", str(ctx.exception))

    def test_get_by_name_case_insensitive(self):
        reg = InventoryItemRegistry()
        reg.add(InventoryItem(1, "Queso Oaxaca", 1, 1))
        self.assertEqual(reg.get_by_name("QUESO OAXACA").id, 1)
        self.assertEqual(reg.get_by_name("queso oaxaca").id, 1)

    def test_get_missing_returns_none(self):
        reg = InventoryItemRegistry()
        self.assertIsNone(reg.get(1))
        self.assertIsNone(reg.get_by_name("Missing"))


class TestUserRegistry(unittest.TestCase):
    def test_add_as_admin_success(self):
        reg = UserRegistry()
        admin = User(1, "Admin", "admin@example.com", "admin")
        user = User(2, "Juan", "juan@example.com", "mesero")
        reg.add(user, admin)
        self.assertEqual(reg.get(2).name, "Juan")

    def test_add_as_non_admin_raises(self):
        reg = UserRegistry()
        admin = User(1, "A", "a@b.com", "admin")
        non_admin = User(2, "B", "b@b.com", "mesero")
        reg.add(non_admin, admin)
        other = User(3, "C", "c@b.com", "mesero")
        with self.assertRaises(PermissionError):
            reg.add(other, non_admin)

    def test_add_invalid_role_raises(self):
        reg = UserRegistry()
        admin = User(1, "Admin", "admin@example.com", "admin")
        user = User(2, "X", "x@x.com", "superuser")
        with self.assertRaises(ValueError) as ctx:
            reg.add(user, admin)
        self.assertIn("role", str(ctx.exception))

    def test_add_empty_name_raises(self):
        reg = UserRegistry()
        admin = User(1, "A", "a@b.com", "admin")
        with self.assertRaises(ValueError):
            reg.add(User(2, "  ", "x@x.com", "mesero"), admin)

    def test_add_invalid_email_raises(self):
        reg = UserRegistry()
        admin = User(1, "A", "a@b.com", "admin")
        with self.assertRaises(ValueError):
            reg.add(User(2, "X", "not-an-email", "mesero"), admin)

    def test_update_as_admin(self):
        reg = UserRegistry()
        admin = User(1, "Admin", "admin@example.com", "admin")
        user = User(2, "Juan", "juan@example.com", "mesero")
        reg.add(user, admin)
        reg.update(2, {"name": "Juan Pérez"}, admin)
        self.assertEqual(reg.get(2).name, "Juan Pérez")

    def test_update_as_non_admin_raises(self):
        reg = UserRegistry()
        admin = User(1, "A", "a@b.com", "admin")
        user = User(2, "B", "b@b.com", "mesero")
        reg.add(user, admin)
        with self.assertRaises(PermissionError):
            reg.update(2, {"name": "X"}, user)

    def test_delete_as_admin(self):
        reg = UserRegistry()
        admin = User(1, "Admin", "admin@example.com", "admin")
        user = User(2, "J", "j@j.com", "mesero")
        reg.add(user, admin)
        reg.delete(2, admin)
        self.assertIsNone(reg.get(2))

    def test_delete_as_non_admin_raises(self):
        reg = UserRegistry()
        admin = User(1, "A", "a@b.com", "admin")
        user = User(2, "B", "b@b.com", "mesero")
        reg.add(user, admin)
        with self.assertRaises(PermissionError):
            reg.delete(2, user)


if __name__ == "__main__":
    unittest.main()
