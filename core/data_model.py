"""
Core entity classes for recipes, inventory, units, and categories.

Defines the foundational data model for Zenet MVP: Restaurant, RestaurantType, User,
Recipe, Ingredient, RecipeUnit, InventoryItem, InventoryUnit, FamilyInventory,
CategoryRecipe, and InventoryCategory.
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
class RestaurantType:
    """Type of restaurant (e.g. Casual, Rápida, Gourmet, Cafeterías, Cafés)."""

    id: int
    name: str
    description: Optional[str] = None


@dataclass
class Restaurant:
    """Top-level entity: basic restaurant information."""

    id: int
    name: str
    address: Optional[str] = None
    restaurant_type_id: Optional[int] = None
    notes: Optional[str] = None


@dataclass
class User:
    """
    User with name, email, and role.
    Only the role 'admin' can create, update, and delete users.
    The person who creates the business profile (restaurant) gets admin rights automatically.
    """

    id: int
    name: str
    email: str
    role: str


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
    """
    Recipe with name, description, steps, category, and list of ingredients.
    id is required; use 0 for a new recipe not yet persisted (persistence layer assigns a real id on save).
    """

    id: int
    name: str
    description: str
    steps: list[str]
    category_id: int
    ingredients: list[Ingredient] = field(default_factory=list)
