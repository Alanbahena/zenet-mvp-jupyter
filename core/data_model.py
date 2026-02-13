"""
Core entity classes for recipes, inventory, units, and categories.

Defines the foundational data model for Zenet MVP: Restaurant, Recipe, Ingredient,
RecipeUnit, InventoryItem, InventoryUnit, FamilyInventory, CategoryRecipe, and InventoryCategory.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RecipeUnit:
    """Unit of measure used in recipes (e.g. g, kg, pza, cucharada)."""

    id: int
    name: str
    symbol: str
    description: Optional[str] = None


@dataclass
class InventoryUnit:
    """Unit of measure used for inventory (e.g. kg, L, caja, bolsa)."""

    id: int
    name: str
    symbol: str
    description: Optional[str] = None


@dataclass
class CategoryRecipe:
    """Grouping of recipes (e.g. desayuno, comida, cena, bebidas)."""

    id: int
    name: str
    description: Optional[str] = None


@dataclass
class FamilyInventory:
    """Grouping of inventory items (e.g. Lácteos, Granos, Carnes)."""

    id: int
    name: str
    description: Optional[str] = None


@dataclass
class InventoryCategory:
    """Category for inventory items by perishability (e.g. perecedero, no perecedero)."""

    id: int
    name: str
    description: Optional[str] = None


@dataclass
class Restaurant:
    """Top-level entity: basic restaurant information."""

    id: int
    name: str
    address: Optional[str] = None
    restaurant_type: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class InventoryItem:
    """
    One inventory item; unit of measure via unit_id (InventoryUnit).
    category_id references InventoryCategory (e.g. perecedero, no perecedero).
    """

    id: int
    name: str
    unit_id: int
    category_id: int
    family_id: Optional[int] = None
    description: Optional[str] = None


@dataclass
class Ingredient:
    """One ingredient in a recipe; quantity and unit_id, optional link to InventoryItem."""

    name: str
    quantity: float
    unit_id: int
    inventory_item_id: Optional[int] = None


@dataclass
class Recipe:
    """Recipe with name, description, steps, category, and list of ingredients."""

    name: str
    description: str
    steps: list[str]
    category_id: int
    ingredients: list[Ingredient] = field(default_factory=list)
    id: Optional[int] = None
