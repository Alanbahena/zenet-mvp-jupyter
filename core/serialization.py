"""
Entity ↔ dict serialization for persistence (Task 3.3).

Converts core data model entities to/from plain dicts per the serialization contract (3.1).
Used by JsonStorage, SqliteStorage, and DataLake. No FK validation; caller is responsible.
"""

from __future__ import annotations

from typing import Any

from core.data_model import (
    CategoryRecipe,
    FamilyInventory,
    Ingredient,
    InventoryItem,
    InventoryUnit,
    InventoryUnitEquivalence,
    Recipe,
    RecipeUnit,
    Restaurant,
    User,
)


def _require(d: dict[str, Any], key: str, entity_name: str) -> Any:
    if key not in d:
        raise ValueError(f"Required field '{key}' missing from {entity_name} dict")
    return d[key]


# --- Ingredient (embedded in Recipe; not top-level entity) ---


def ingredient_to_dict(ing: Ingredient) -> dict[str, Any]:
    """Serialize one recipe ingredient to contract dict."""
    return {
        "name": ing.name,
        "quantity": ing.quantity,
        "unit_id": ing.unit_id,
        "inventory_item_id": ing.inventory_item_id,
    }


def ingredient_from_dict(d: dict[str, Any]) -> Ingredient:
    """Build Ingredient from contract dict."""
    return Ingredient(
        name=_require(d, "name", "ingredient"),
        quantity=float(_require(d, "quantity", "ingredient")),
        unit_id=int(_require(d, "unit_id", "ingredient")),
        inventory_item_id=d.get("inventory_item_id"),
    )


# --- Restaurant ---


def restaurant_to_dict(r: Restaurant) -> dict[str, Any]:
    """Serialize Restaurant to contract dict."""
    return {
        "id": r.id,
        "name": r.name,
        "address": r.address,
        "restaurant_type_id": r.restaurant_type_id,
        "notes": r.notes,
    }


def restaurant_from_dict(d: dict[str, Any]) -> Restaurant:
    """Build Restaurant from contract dict."""
    return Restaurant(
        id=int(_require(d, "id", "restaurant")),
        name=_require(d, "name", "restaurant"),
        address=d.get("address"),
        restaurant_type_id=d.get("restaurant_type_id"),
        notes=d.get("notes"),
    )


# --- User ---


def user_to_dict(u: User) -> dict[str, Any]:
    """Serialize User to contract dict."""
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": u.role,
    }


def user_from_dict(d: dict[str, Any]) -> User:
    """Build User from contract dict."""
    return User(
        id=int(_require(d, "id", "user")),
        name=_require(d, "name", "user"),
        email=_require(d, "email", "user"),
        role=_require(d, "role", "user"),
    )


# --- RecipeUnit ---


def recipe_unit_to_dict(u: RecipeUnit) -> dict[str, Any]:
    """Serialize RecipeUnit to contract dict."""
    return {
        "id": u.id,
        "name": u.name,
        "symbol": u.symbol,
        "description": u.description,
    }


def recipe_unit_from_dict(d: dict[str, Any]) -> RecipeUnit:
    """Build RecipeUnit from contract dict."""
    return RecipeUnit(
        id=int(_require(d, "id", "recipe_unit")),
        name=_require(d, "name", "recipe_unit"),
        symbol=_require(d, "symbol", "recipe_unit"),
        description=d.get("description"),
    )


# --- InventoryUnit ---


def inventory_unit_to_dict(u: InventoryUnit) -> dict[str, Any]:
    """Serialize InventoryUnit to contract dict."""
    return {
        "id": u.id,
        "name": u.name,
        "symbol": u.symbol,
        "description": u.description,
        "base_unit_id": u.base_unit_id,
        "factor_to_base": u.factor_to_base,
        "is_standard": u.is_standard,
    }


def inventory_unit_from_dict(d: dict[str, Any]) -> InventoryUnit:
    """Build InventoryUnit from contract dict."""
    return InventoryUnit(
        id=int(_require(d, "id", "inventory_unit")),
        name=_require(d, "name", "inventory_unit"),
        symbol=_require(d, "symbol", "inventory_unit"),
        description=d.get("description"),
        base_unit_id=d.get("base_unit_id"),
        factor_to_base=float(d.get("factor_to_base", 1.0)),
        is_standard=d.get("is_standard", True),
    )


# --- CategoryRecipe ---


def category_recipe_to_dict(c: CategoryRecipe) -> dict[str, Any]:
    """Serialize CategoryRecipe to contract dict."""
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
    }


def category_recipe_from_dict(d: dict[str, Any]) -> CategoryRecipe:
    """Build CategoryRecipe from contract dict."""
    return CategoryRecipe(
        id=int(_require(d, "id", "category_recipe")),
        name=_require(d, "name", "category_recipe"),
        description=d.get("description"),
    )


# --- FamilyInventory ---


def family_inventory_to_dict(f: FamilyInventory) -> dict[str, Any]:
    """Serialize FamilyInventory to contract dict."""
    return {
        "id": f.id,
        "name": f.name,
        "description": f.description,
        "base_unit_id": f.base_unit_id,
    }


def family_inventory_from_dict(d: dict[str, Any]) -> FamilyInventory:
    """Build FamilyInventory from contract dict."""
    return FamilyInventory(
        id=int(_require(d, "id", "family_inventory")),
        name=_require(d, "name", "family_inventory"),
        description=d.get("description"),
        base_unit_id=d.get("base_unit_id"),
    )


# --- InventoryItem ---


def inventory_item_to_dict(item: InventoryItem) -> dict[str, Any]:
    """Serialize InventoryItem to contract dict."""
    return {
        "id": item.id,
        "name": item.name,
        "unit_id": item.unit_id,
        "category_id": item.category_id,
        "family_id": item.family_id,
        "description": item.description,
    }


def inventory_item_from_dict(d: dict[str, Any]) -> InventoryItem:
    """Build InventoryItem from contract dict."""
    return InventoryItem(
        id=int(_require(d, "id", "inventory_item")),
        name=_require(d, "name", "inventory_item"),
        unit_id=int(_require(d, "unit_id", "inventory_item")),
        category_id=int(_require(d, "category_id", "inventory_item")),
        family_id=d.get("family_id"),
        description=d.get("description"),
    )


# --- Recipe ---


def recipe_to_dict(recipe: Recipe) -> dict[str, Any]:
    """Serialize Recipe to contract dict (includes ingredients as list of dicts)."""
    return {
        "id": recipe.id,
        "name": recipe.name,
        "description": recipe.description,
        "steps": recipe.steps,
        "category_id": recipe.category_id,
        "ingredients": [ingredient_to_dict(ing) for ing in recipe.ingredients],
    }


def recipe_from_dict(d: dict[str, Any]) -> Recipe:
    """Build Recipe from contract dict."""
    return Recipe(
        id=int(_require(d, "id", "recipe")),
        name=_require(d, "name", "recipe"),
        category_id=int(_require(d, "category_id", "recipe")),
        description=d.get("description"),
        steps=d.get("steps"),
        ingredients=[ingredient_from_dict(ing_d) for ing_d in d.get("ingredients", [])],
    )


# --- InventoryUnitEquivalence (no id field; composite key external) ---


def inventory_unit_equivalence_to_dict(eq: InventoryUnitEquivalence) -> dict[str, Any]:
    """Serialize InventoryUnitEquivalence to contract dict."""
    return {
        "unit_id": eq.unit_id,
        "inventory_item_id": eq.inventory_item_id,
        "base_unit_id": eq.base_unit_id,
        "factor_to_base": eq.factor_to_base,
    }


def inventory_unit_equivalence_from_dict(d: dict[str, Any]) -> InventoryUnitEquivalence:
    """Build InventoryUnitEquivalence from contract dict."""
    return InventoryUnitEquivalence(
        unit_id=int(_require(d, "unit_id", "inventory_unit_equivalence")),
        inventory_item_id=int(_require(d, "inventory_item_id", "inventory_unit_equivalence")),
        base_unit_id=int(_require(d, "base_unit_id", "inventory_unit_equivalence")),
        factor_to_base=float(_require(d, "factor_to_base", "inventory_unit_equivalence")),
    )
