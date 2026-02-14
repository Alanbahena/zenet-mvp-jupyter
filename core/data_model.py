"""
Core entity classes for recipes, inventory, units, and categories.

Defines the foundational data model for Zenet MVP: Restaurant, RestaurantType, User,
Recipe, Ingredient, RecipeUnit, InventoryItem, InventoryUnit, FamilyInventory,
CategoryRecipe, and InventoryCategory. Includes registries and relationship methods (2.2).
"""

import math
import re
from dataclasses import dataclass, field
from typing import Optional

# Allowed roles for User (2.2 validation)
ALLOWED_USER_ROLES = frozenset({"admin", "mesero", "cocinero", "inventario"})


@dataclass
class RecipeUnit:
    """Unit of measure used in recipes (e.g. g, kg, pza, cucharada)."""

    id: int
    name: str
    symbol: str
    description: Optional[str] = None


@dataclass
class InventoryUnit:
    """
    Unit of measure used for inventory (e.g. kg, L, caja, bolsa).
    Optional equivalence: base_unit_id and factor_to_base (e.g. 1 Caja = 10 kg).
    """

    id: int
    name: str
    symbol: str
    description: Optional[str] = None
    base_unit_id: Optional[int] = None
    factor_to_base: float = 1.0


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
    """Category for inventory items by perishability (perecedero, no perecedero)."""

    id: int
    name: str
    description: Optional[str] = None


# Fixed inventory categories (user selects only; no add/remove)
DEFAULT_INVENTORY_CATEGORIES = (
    InventoryCategory(1, "Perecedero", None),
    InventoryCategory(2, "No perecedero", None),
)


def _valid_inventory_category_ids() -> set[int]:
    """Return valid inventory category ids from the fixed set (for validation)."""
    return {c.id for c in DEFAULT_INVENTORY_CATEGORIES}


@dataclass
class RestaurantType:
    """Type of restaurant (e.g. Casual, Rápida, Gourmet, Cafeterías, Cafés)."""

    id: int
    name: str
    description: Optional[str] = None


# Fixed restaurant types (user selects only; no add/remove)
DEFAULT_RESTAURANT_TYPES = (
    RestaurantType(1, "Casual", None),
    RestaurantType(2, "Rápida", None),
    RestaurantType(3, "Gourmet", None),
    RestaurantType(4, "Cafeterías", None),
    RestaurantType(5, "Cafés", None),
)


def _valid_restaurant_type_ids() -> set[int]:
    """Return valid restaurant type ids from the fixed set (for validation)."""
    return {t.id for t in DEFAULT_RESTAURANT_TYPES}


@dataclass
class Restaurant:
    """Top-level entity: basic restaurant information."""

    id: int
    name: str
    address: Optional[str] = None
    restaurant_type_id: Optional[int] = None
    notes: Optional[str] = None

    def update_address(self, value: Optional[str]) -> None:
        self.address = value

    def update_restaurant_type_id(self, value: Optional[int]) -> None:
        if value is not None and value not in _valid_restaurant_type_ids():
            raise ValueError(
                f"restaurant_type_id must be one of {sorted(_valid_restaurant_type_ids())}"
            )
        self.restaurant_type_id = value

    def update_notes(self, value: Optional[str]) -> None:
        self.notes = value

    def clear_address(self) -> None:
        self.address = None

    def clear_restaurant_type_id(self) -> None:
        self.restaurant_type_id = None

    def clear_notes(self) -> None:
        self.notes = None


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

    def update_family_id(
        self, family_id: Optional[int], valid_ids: Optional[set[int]] = None
    ) -> None:
        if family_id is not None and valid_ids is not None and family_id not in valid_ids:
            raise ValueError(f"family_id must be in valid_ids, got {family_id}")
        self.family_id = family_id

    def update_category_id(
        self, category_id: int, valid_ids: Optional[set[int]] = None
    ) -> None:
        ids = valid_ids if valid_ids is not None else _valid_inventory_category_ids()
        if category_id not in ids:
            raise ValueError(f"category_id must be in valid_ids, got {category_id}")
        self.category_id = category_id


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

    def add_ingredient(
        self,
        ingredient: Ingredient,
        valid_unit_ids: set[int],
        category_id: Optional[int] = None,
        unit_id_for_inventory: Optional[int] = None,
        family_id: Optional[int] = None,
        valid_inventory_unit_ids: Optional[set[int]] = None,
        valid_family_inventory_ids: Optional[set[int]] = None,
    ) -> Optional[InventoryItem]:
        if not (ingredient.name or "").strip():
            raise ValueError("ingredient.name must be non-empty")
        if not math.isfinite(ingredient.quantity) or ingredient.quantity <= 0:
            raise ValueError("ingredient.quantity must be finite and > 0")
        if ingredient.unit_id not in valid_unit_ids:
            raise ValueError(
                f"ingredient.unit_id {ingredient.unit_id} not in valid_unit_ids"
            )
        new_item: Optional[InventoryItem] = None
        if category_id is not None:
            if category_id not in _valid_inventory_category_ids():
                raise ValueError(
                    f"category_id must be one of {sorted(_valid_inventory_category_ids())} (Perecedero / No perecedero)"
                )
            if valid_inventory_unit_ids is None:
                raise ValueError(
                    "valid_inventory_unit_ids required when category_id is provided"
                )
            if unit_id_for_inventory is None or unit_id_for_inventory not in valid_inventory_unit_ids:
                raise ValueError(
                    "unit_id_for_inventory required and must be in valid_inventory_unit_ids when creating new InventoryItem"
                )
            if family_id is not None:
                if valid_family_inventory_ids is None or family_id not in valid_family_inventory_ids:
                    raise ValueError(
                        "family_id must be in valid_family_inventory_ids when provided"
                    )
            new_item = InventoryItem(
                id=0,
                name=ingredient.name.strip(),
                unit_id=unit_id_for_inventory,
                category_id=category_id,
                family_id=family_id,
            )
        self.ingredients.append(ingredient)
        return new_item

    def remove_ingredient(
        self, ingredient: Ingredient | int | str
    ) -> Optional[Ingredient]:
        if isinstance(ingredient, int):
            if ingredient < 0 or ingredient >= len(self.ingredients):
                raise IndexError(
                    f"ingredient index {ingredient} out of range [0, {len(self.ingredients)})"
                )
            return self.ingredients.pop(ingredient)
        if isinstance(ingredient, str):
            name_lower = ingredient.casefold()
            for i, ing in enumerate(self.ingredients):
                if ing.name.casefold() == name_lower:
                    return self.ingredients.pop(i)
            return None
        # Ingredient: remove by name match
        name_lower = ingredient.name.casefold()
        for i, ing in enumerate(self.ingredients):
            if ing.name.casefold() == name_lower:
                return self.ingredients.pop(i)
        return None

    def ingredient_count(self) -> int:
        return len(self.ingredients)

    def has_ingredient(self, name: str) -> bool:
        name_lower = name.casefold()
        return any(ing.name.casefold() == name_lower for ing in self.ingredients)

    def get_ingredient_by_name(self, name: str) -> Optional[Ingredient]:
        name_lower = name.casefold()
        for ing in self.ingredients:
            if ing.name.casefold() == name_lower:
                return ing
        return None

    def update_category_id(
        self, category_id: int, valid_ids: Optional[set[int]] = None
    ) -> None:
        if valid_ids is not None and category_id not in valid_ids:
            raise ValueError(f"category_id must be in valid_ids, got {category_id}")
        self.category_id = category_id


# --- Registries (2.2) ---

_BASIC_EMAIL_RE = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


class RecipeUnitRegistry:
    """Registry of RecipeUnit instances; validates on add, guards on remove."""

    def __init__(self) -> None:
        self._units: list[RecipeUnit] = []

    def add(self, unit: RecipeUnit) -> None:
        if not (unit.name or "").strip():
            raise ValueError("unit.name must be non-empty")
        if not (unit.symbol or "").strip():
            raise ValueError("unit.symbol must be non-empty")
        for u in self._units:
            if u.id == unit.id:
                raise ValueError(f"duplicate unit id: {unit.id}")
            if u.symbol.strip().lower() == unit.symbol.strip().lower():
                raise ValueError(f"duplicate unit symbol: {unit.symbol!r}")
        self._units.append(unit)

    def remove(
        self, unit_id: int, ingredients: Optional[list[Ingredient]] = None
    ) -> Optional[RecipeUnit]:
        if ingredients is not None:
            for ing in ingredients:
                if ing.unit_id == unit_id:
                    raise ValueError("Unit is in use; reassign or remove dependent entities first.")
        for i, u in enumerate(self._units):
            if u.id == unit_id:
                return self._units.pop(i)
        return None

    def valid_ids(self) -> set[int]:
        return {u.id for u in self._units}

    def get(self, unit_id: int) -> Optional[RecipeUnit]:
        for u in self._units:
            if u.id == unit_id:
                return u
        return None


def _inventory_unit_cycle(unit: InventoryUnit, registry: "InventoryUnitRegistry") -> bool:
    """Return True if following base_unit_id chain from unit leads back to unit.id (cycle)."""
    seen: set[int] = {unit.id}
    current_id: Optional[int] = unit.base_unit_id
    while current_id is not None:
        if current_id in seen:
            return True
        seen.add(current_id)
        u = registry.get(current_id)
        if u is None:
            break
        current_id = u.base_unit_id
    return False


class InventoryUnitRegistry:
    """Registry of InventoryUnit instances; validates on add (including equivalence), guards on remove."""

    def __init__(self) -> None:
        self._units: list[InventoryUnit] = []

    def add(self, unit: InventoryUnit) -> None:
        if not (unit.name or "").strip():
            raise ValueError("unit.name must be non-empty")
        if not (unit.symbol or "").strip():
            raise ValueError("unit.symbol must be non-empty")
        for u in self._units:
            if u.id == unit.id:
                raise ValueError(f"duplicate unit id: {unit.id}")
            if u.symbol.strip().lower() == unit.symbol.strip().lower():
                raise ValueError(f"duplicate unit symbol: {unit.symbol!r}")
        if unit.base_unit_id is not None:
            if unit.base_unit_id == unit.id:
                raise ValueError("base_unit_id must not equal unit id (cycle)")
            ids = {u.id for u in self._units}
            if unit.base_unit_id not in ids:
                raise ValueError(
                    f"base_unit_id {unit.base_unit_id} must be in registry"
                )
            if unit.factor_to_base <= 0:
                raise ValueError("factor_to_base must be > 0")
        self._units.append(unit)
        # Cycle check after add (need self in list for lookup)
        if unit.base_unit_id is not None and _inventory_unit_cycle(unit, self):
            self._units.pop()
            raise ValueError("base_unit_id chain must not form a cycle")

    def remove(
        self, unit_id: int, inventory_items: Optional[list[InventoryItem]] = None
    ) -> Optional[InventoryUnit]:
        if inventory_items is not None:
            for item in inventory_items:
                if item.unit_id == unit_id:
                    raise ValueError(
                        "Unit is in use; reassign or remove dependent entities first."
                    )
        for i, u in enumerate(self._units):
            if u.id == unit_id:
                return self._units.pop(i)
        return None

    def valid_ids(self) -> set[int]:
        return {u.id for u in self._units}

    def get(self, unit_id: int) -> Optional[InventoryUnit]:
        for u in self._units:
            if u.id == unit_id:
                return u
        return None


class CategoryRecipeRegistry:
    """Registry of CategoryRecipe instances; validates on add, guards on remove."""

    def __init__(self) -> None:
        self._categories: list[CategoryRecipe] = []

    def add(self, category: CategoryRecipe) -> None:
        if not (category.name or "").strip():
            raise ValueError("category.name must be non-empty")
        for c in self._categories:
            if c.id == category.id:
                raise ValueError(f"duplicate category id: {category.id}")
            if c.name.strip().lower() == category.name.strip().lower():
                raise ValueError(f"duplicate category name: {category.name!r}")
        self._categories.append(category)

    def remove(
        self, category_id: int, recipes: Optional[list[Recipe]] = None
    ) -> Optional[CategoryRecipe]:
        if recipes is not None:
            for r in recipes:
                if r.category_id == category_id:
                    raise ValueError("Category is in use")
        for i, c in enumerate(self._categories):
            if c.id == category_id:
                return self._categories.pop(i)
        return None

    def valid_ids(self) -> set[int]:
        return {c.id for c in self._categories}

    def get(self, category_id: int) -> Optional[CategoryRecipe]:
        for c in self._categories:
            if c.id == category_id:
                return c
        return None


class FamilyInventoryRegistry:
    """Registry of FamilyInventory instances; validates on add, guards on remove."""

    def __init__(self) -> None:
        self._families: list[FamilyInventory] = []

    def add(self, family: FamilyInventory) -> None:
        if not (family.name or "").strip():
            raise ValueError("family.name must be non-empty")
        for f in self._families:
            if f.id == family.id:
                raise ValueError(f"duplicate family id: {family.id}")
            if f.name.strip().lower() == family.name.strip().lower():
                raise ValueError(f"duplicate family name: {family.name!r}")
        self._families.append(family)

    def remove(
        self, family_id: int, inventory_items: Optional[list[InventoryItem]] = None
    ) -> Optional[FamilyInventory]:
        if inventory_items is not None:
            for item in inventory_items:
                if item.family_id == family_id:
                    raise ValueError("Family is in use")
        for i, f in enumerate(self._families):
            if f.id == family_id:
                return self._families.pop(i)
        return None

    def valid_ids(self) -> set[int]:
        return {f.id for f in self._families}

    def get(self, family_id: int) -> Optional[FamilyInventory]:
        for f in self._families:
            if f.id == family_id:
                return f
        return None


class UserRegistry:
    """Registry of User instances; add/update/delete only when current_user is admin."""

    def __init__(self) -> None:
        self._users: list[User] = []

    def add(self, user: User, current_user: User) -> None:
        if current_user.role != "admin":
            raise PermissionError("Only admin can add users")
        if user.role not in ALLOWED_USER_ROLES:
            raise ValueError(f"role must be one of {sorted(ALLOWED_USER_ROLES)}")
        if not (user.name or "").strip():
            raise ValueError("user.name must be non-empty")
        if not (user.email or "").strip():
            raise ValueError("user.email must be non-empty")
        if not _BASIC_EMAIL_RE.match(user.email.strip()):
            raise ValueError("user.email must be a valid email format")
        self._users.append(user)

    def update(
        self, user_id: int, updates: dict, current_user: User
    ) -> None:
        if current_user.role != "admin":
            raise PermissionError("Only admin can update users")
        for u in self._users:
            if u.id == user_id:
                if "name" in updates:
                    val = updates["name"]
                    if not (val or "").strip():
                        raise ValueError("name must be non-empty")
                    u.name = updates["name"]
                if "email" in updates:
                    val = updates["email"]
                    if not (val or "").strip():
                        raise ValueError("email must be non-empty")
                    if not _BASIC_EMAIL_RE.match(val.strip()):
                        raise ValueError("email must be a valid email format")
                    u.email = val
                if "role" in updates:
                    if updates["role"] not in ALLOWED_USER_ROLES:
                        raise ValueError(f"role must be one of {sorted(ALLOWED_USER_ROLES)}")
                    u.role = updates["role"]
                return
        raise ValueError(f"user id {user_id} not found")

    def delete(self, user_id: int, current_user: User) -> None:
        if current_user.role != "admin":
            raise PermissionError("Only admin can delete users")
        for i, u in enumerate(self._users):
            if u.id == user_id:
                self._users.pop(i)
                return
        raise ValueError(f"user id {user_id} not found")

    def get(self, user_id: int) -> Optional[User]:
        for u in self._users:
            if u.id == user_id:
                return u
        return None
