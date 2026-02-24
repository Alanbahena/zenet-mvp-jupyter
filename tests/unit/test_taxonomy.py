"""Unit tests for core.taxonomy (subtask 2.4)."""

from __future__ import annotations

import unittest

from core.domain.taxonomy import (
    IS_A,
    PART_OF,
    find_related_items,
    IngredientTaxonomy,
    InventoryTaxonomy,
    RecipeTaxonomy,
    Taxonomy,
)


class TestTaxonomyBasics(unittest.TestCase):
    def test_add_node_and_has_node(self):
        t = Taxonomy()
        t.add_node("a")
        self.assertTrue(t.has_node("a"))
        self.assertFalse(t.has_node("b"))
        t.add_node("b")
        self.assertTrue(t.has_node("b"))

    def test_add_relationship_creates_nodes(self):
        t = Taxonomy()
        t.add_relationship("child", "parent", IS_A)
        self.assertTrue(t.has_node("child"))
        self.assertTrue(t.has_node("parent"))

    def test_get_children_and_parents_is_a(self):
        t = Taxonomy()
        # is_a: (child, parent) -> source=child, target=parent
        t.add_relationship("tomate", "verdura", IS_A)
        t.add_relationship("lechuga", "verdura", IS_A)
        self.assertEqual(t.get_children("verdura"), ["tomate", "lechuga"])
        self.assertEqual(t.get_parents("tomate"), ["verdura"])
        self.assertEqual(t.get_parents("lechuga"), ["verdura"])
        self.assertEqual(t.get_children("tomate"), [])
        self.assertEqual(t.get_parents("verdura"), [])

    def test_multiple_roots(self):
        t = Taxonomy()
        t.add_node("root1")
        t.add_node("root2")
        t.add_relationship("a", "root1", IS_A)
        t.add_relationship("b", "root2", IS_A)
        self.assertEqual(t.get_children("root1"), ["a"])
        self.assertEqual(t.get_children("root2"), ["b"])
        self.assertEqual(t.get_parents("root1"), [])
        self.assertEqual(t.get_parents("root2"), [])

    def test_get_children_empty_for_unknown_node(self):
        t = Taxonomy()
        self.assertEqual(t.get_children("x"), [])
        self.assertEqual(t.get_parents("x"), [])


class TestTaxonomyTypedRelationships(unittest.TestCase):
    def test_get_related_is_a(self):
        t = Taxonomy()
        t.add_relationship("tomate", "verdura", IS_A)
        t.add_relationship("queso", "lacteo", IS_A)
        self.assertEqual(set(t.get_related("tomate", IS_A)), {"verdura"})
        self.assertEqual(set(t.get_related("verdura", IS_A)), {"tomate"})
        self.assertEqual(set(t.get_related("unknown", IS_A)), set())

    def test_get_related_part_of(self):
        t = Taxonomy()
        t.add_relationship("salsa", "tacos", PART_OF)
        self.assertEqual(set(t.get_related("salsa", PART_OF)), {"tacos"})
        self.assertEqual(set(t.get_related("tacos", PART_OF)), {"salsa"})

    def test_has_relationship(self):
        t = Taxonomy()
        t.add_relationship("a", "b", IS_A)
        self.assertTrue(t.has_relationship("a", "b", IS_A))
        self.assertTrue(t.has_relationship("b", "a", IS_A))
        self.assertFalse(t.has_relationship("a", "b", PART_OF))
        self.assertFalse(t.has_relationship("x", "y", IS_A))


class TestIngredientTaxonomy(unittest.TestCase):
    def test_add_and_ancestors(self):
        ing = IngredientTaxonomy()
        ing.add_ingredient("tomate")
        ing.add_ingredient("verdura")
        ing.add_ingredient("alimento")
        ing.add_is_a("tomate", "verdura")
        ing.add_is_a("verdura", "alimento")
        ancestors = ing.get_ingredient_ancestors("tomate")
        self.assertIn("verdura", ancestors)
        self.assertIn("alimento", ancestors)
        self.assertEqual(len(ancestors), 2)

    def test_get_ingredient_related(self):
        ing = IngredientTaxonomy()
        ing.add_ingredient("tomate")
        ing.add_ingredient("verdura")
        ing.add_is_a("tomate", "verdura")
        self.assertEqual(set(ing.get_ingredient_related("tomate", IS_A)), {"verdura"})
        self.assertEqual(set(ing.get_ingredient_related("verdura", IS_A)), {"tomate"})


class TestRecipeTaxonomy(unittest.TestCase):
    def test_categories_and_related(self):
        rec = RecipeTaxonomy()
        rec.add_recipe("tacos")
        rec.add_recipe("comida_mexicana")
        rec.add_recipe("entrada")
        rec.add_is_a("tacos", "comida_mexicana")
        rec.add_is_a("tacos", "entrada")
        cats = rec.get_recipe_categories("tacos")
        self.assertEqual(set(cats), {"comida_mexicana", "entrada"})
        self.assertEqual(set(rec.get_related_recipes("tacos", IS_A)), {"comida_mexicana", "entrada"})


class TestInventoryTaxonomy(unittest.TestCase):
    def test_ancestors_and_related(self):
        inv = InventoryTaxonomy()
        inv.add_item("item1")
        inv.add_item("carnes")
        inv.add_item("proteina")
        inv.add_is_a("item1", "carnes")
        inv.add_is_a("carnes", "proteina")
        ancestors = inv.get_inventory_ancestors("item1")
        self.assertIn("carnes", ancestors)
        self.assertIn("proteina", ancestors)
        self.assertEqual(set(inv.get_related_inventory_items("item1", IS_A)), {"carnes"})


class TestFindRelatedByProximity(unittest.TestCase):
    def test_self_distance_zero(self):
        t = Taxonomy()
        t.add_node("a")
        result = find_related_items(t, "a", max_depth=0)
        self.assertEqual(result, [("a", 0)])

    def test_neighbors_distance_one(self):
        t = Taxonomy()
        t.add_relationship("a", "b", IS_A)
        t.add_relationship("a", "c", IS_A)
        result = find_related_items(t, "a", max_depth=1)
        self.assertEqual(len(result), 3)  # a(0), b(1), c(1)
        by_dist = {}
        for n, d in result:
            by_dist.setdefault(d, []).append(n)
        self.assertEqual(by_dist[0], ["a"])
        self.assertEqual(set(by_dist[1]), {"b", "c"})

    def test_max_depth_limits(self):
        t = Taxonomy()
        t.add_relationship("a", "b", IS_A)
        t.add_relationship("b", "c", IS_A)
        t.add_relationship("c", "d", IS_A)
        result = find_related_items(t, "a", max_depth=1)
        nodes = [n for n, _ in result]
        self.assertIn("a", nodes)
        self.assertIn("b", nodes)
        self.assertNotIn("c", nodes)
        self.assertNotIn("d", nodes)

    def test_limit_caps_results(self):
        t = Taxonomy()
        t.add_node("a")
        for i in range(5):
            t.add_relationship("a", f"n{i}", IS_A)
        result = find_related_items(t, "a", limit=3)
        self.assertEqual(len(result), 3)

    def test_unknown_node_returns_empty(self):
        t = Taxonomy()
        t.add_node("a")
        self.assertEqual(find_related_items(t, "z"), [])


if __name__ == "__main__":
    unittest.main()
