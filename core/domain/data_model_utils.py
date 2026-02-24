"""
Data model integration utilities (subtask 2.5).

Integrates core/data_model, core/normalization, and core/taxonomy.
Provides: format conversion (normalized <-> display), combined validation,
helpers across entity types, and factory methods for related entities.
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from core.domain.data_model import (
    FamilyInventoryRegistry,
    Ingredient,
    InventoryItem,
    InventoryItemRegistry,
    InventoryUnitRegistry,
    Recipe,
    RecipeUnitRegistry,
)
from core.operations.normalization import (
    DeductionLine,
    RecipeUnitConversionRegistry,
    make_resolver,
)


def format_deduction_line_for_display(
    line: DeductionLine,
    unit_registry: InventoryUnitRegistry,
    item_registry: InventoryItemRegistry,
) -> str:
    """Format a deduction line as a human-readable string (e.g. '0.5 kg Leche').

    Resolves item name and unit symbol from registries. If item or unit is missing,
    returns a fallback string with raw id/quantity/unit_id.
    """
    inventory_item_id, quantity, unit_id = line
    item = item_registry.get(inventory_item_id)
    unit = unit_registry.get(unit_id)
    item_name = item.name if item else f"<id:{inventory_item_id}>"
    symbol = unit.symbol if unit else str(unit_id)
    return f"{quantity} {symbol} {item_name}"


def format_ingredient_for_display(
    ingredient: Ingredient,
    recipe_unit_registry: RecipeUnitRegistry,
) -> str:
    """Format an ingredient as a human-readable string (e.g. '250 g Harina').

    Looks up unit symbol via recipe_unit_registry. If unit is missing, uses
    unit_id as fallback.
    """
    unit = recipe_unit_registry.get(ingredient.unit_id)
    symbol = unit.symbol if unit else str(ingredient.unit_id)
    return f"{ingredient.quantity} {symbol} {ingredient.name}"


def ingredients_to_display(
    recipe: Recipe,
    recipe_unit_registry: RecipeUnitRegistry,
    inventory_item_registry: Optional[InventoryItemRegistry] = None,
) -> list[dict]:
    """Return a list of dicts suitable for UI: name, quantity, unit_symbol, unit_id, optional inventory_item_name.

    Resolves unit symbol from recipe_unit_registry. If inventory_item_registry is given,
    resolves inventory item name by inventory_item_id or get_by_name(ing.name).
    """
    result: list[dict] = []
    for ing in recipe.ingredients:
        unit = recipe_unit_registry.get(ing.unit_id)
        symbol = unit.symbol if unit else str(ing.unit_id)
        row: dict = {
            "name": ing.name,
            "quantity": ing.quantity,
            "unit_symbol": symbol,
            "unit_id": ing.unit_id,
        }
        if inventory_item_registry is not None:
            item = inventory_item_registry.get(ing.inventory_item_id) if ing.inventory_item_id else None
            if item is None:
                item = inventory_item_registry.get_by_name(ing.name)
            row["inventory_item_name"] = item.name if item else None
        result.append(row)
    return result


def parse_quantity_and_unit(
    quantity_str: str,
    unit_registry: RecipeUnitRegistry,
) -> tuple[float, int]:
    """Parse a string like '250' or '250 g' to (quantity, unit_id).

    For '250 g', looks up unit by symbol (case-insensitive) in registry.
    For '250' with no unit token, raises ValueError (unit required).
    Limitations: single unit symbol token; first matching symbol used.
    """
    s = (quantity_str or "").strip()
    if not s:
        raise ValueError("quantity_str must be non-empty")
    parts = s.split()
    if len(parts) == 1:
        try:
            qty = float(parts[0])
        except ValueError:
            raise ValueError(f"could not parse quantity from {quantity_str!r}")
        raise ValueError("unit symbol required (e.g. '250 g')")
    if len(parts) < 2:
        raise ValueError(f"expected 'quantity unit' in {quantity_str!r}")
    try:
        qty = float(parts[0])
    except ValueError:
        raise ValueError(f"could not parse quantity from {parts[0]!r}")
    symbol = parts[1].strip()
    for uid in unit_registry.valid_ids():
        u = unit_registry.get(uid)
        if u and u.symbol.strip().lower() == symbol.lower():
            return (qty, uid)
    raise ValueError(f"unit symbol {symbol!r} not found in registry")


def validate_recipe_for_deduction(
    recipe: Recipe,
    item_registry: InventoryItemRegistry,
    unit_registry: InventoryUnitRegistry,
    conversion_table: RecipeUnitConversionRegistry,
    family_registry: FamilyInventoryRegistry,
) -> list[str]:
    """Check that every ingredient can be resolved to an inventory item and has a valid unit.

    Returns a list of human-readable issues. Empty list means the recipe is valid for deduction.
    Does not run full normalization; only checks resolution and unit existence.
    """
    issues: list[str] = []
    for ing in recipe.ingredients:
        item = resolve_ingredient_to_inventory_item(ing, item_registry)
        if item is None:
            issues.append(f"Ingredient {ing.name!r} has no inventory item")
            continue
        if unit_registry.get(item.unit_id) is None:
            issues.append(f"Unit id {item.unit_id} for item {item.name!r} not in registry")
    return issues


def validate_ingredient_with_registries(
    ingredient: Ingredient,
    valid_recipe_unit_ids: set[int],
) -> list[str]:
    """Entity-level validation: name non-empty, quantity > 0 and finite, unit_id in valid set.

    Returns a list of error messages; empty if valid.
    """
    issues: list[str] = []
    if not (ingredient.name or "").strip():
        issues.append("ingredient.name must be non-empty")
    if not math.isfinite(ingredient.quantity) or ingredient.quantity <= 0:
        issues.append("ingredient.quantity must be finite and > 0")
    if ingredient.unit_id not in valid_recipe_unit_ids:
        issues.append(
            f"ingredient.unit_id {ingredient.unit_id} not in valid_recipe_unit_ids"
        )
    return issues


def resolve_ingredient_to_inventory_item(
    ingredient: Ingredient,
    item_registry: InventoryItemRegistry,
) -> Optional[InventoryItem]:
    """Resolve an ingredient to its inventory item by inventory_item_id or by name.

    Returns item_registry.get(ingredient.inventory_item_id) if set and found;
    else item_registry.get_by_name(ingredient.name). Returns None if not found.
    """
    if ingredient.inventory_item_id is not None:
        item = item_registry.get(ingredient.inventory_item_id)
        if item is not None:
            return item
    return item_registry.get_by_name(ingredient.name)


def make_resolver_from_item_registry(
    item_registry: InventoryItemRegistry,
) -> Callable[[Ingredient], tuple[int, Optional[int], int]]:
    """Return a resolver for `normalize_recipe_for_deduction` using the given item registry.

    Usage:

    - `normalize_recipe_for_deduction(..., resolve_ingredient_to_inventory=make_resolver_from_item_registry(reg))`

    The returned callable maps an Ingredient to `(inventory_item_id, family_id, item_unit_id)`.
    """
    return make_resolver(lambda ing: resolve_ingredient_to_inventory_item(ing, item_registry))


def units_used_by_recipe(
    recipe: Recipe,
    recipe_unit_registry: RecipeUnitRegistry,
    item_registry: InventoryItemRegistry,
    inventory_unit_registry: InventoryUnitRegistry,
) -> tuple[set[int], set[int]]:
    """Return (recipe_unit_ids, inventory_unit_ids) used by this recipe.

    Recipe unit ids are from ingredient.unit_id; inventory unit ids are from
    resolved inventory items' unit_id.
    """
    recipe_ids: set[int] = set()
    inventory_ids: set[int] = set()
    for ing in recipe.ingredients:
        recipe_ids.add(ing.unit_id)
        item = resolve_ingredient_to_inventory_item(ing, item_registry)
        if item is not None:
            inventory_ids.add(item.unit_id)
    return (recipe_ids, inventory_ids)


def create_inventory_item_from_ingredient(
    ingredient: Ingredient,
    category_id: int,
    unit_id_for_inventory: int,
    family_id: Optional[int] = None,
) -> InventoryItem:
    """Create an InventoryItem from an ingredient (id=0) for the caller to add to a registry.

    No validation inside; callers must validate category_id and unit_id_for_inventory
    (e.g. against _valid_inventory_category_ids() and an inventory unit registry).
    """
    return InventoryItem(
        id=0,
        name=ingredient.name.strip(),
        unit_id=unit_id_for_inventory,
        category_id=category_id,
        family_id=family_id,
    )


def build_ingredient(
    name: str,
    quantity: float,
    unit_id: int,
    inventory_item_id: Optional[int] = None,
) -> Ingredient:
    """Build an Ingredient with the given fields (convenience wrapper)."""
    return Ingredient(
        name=name,
        quantity=quantity,
        unit_id=unit_id,
        inventory_item_id=inventory_item_id,
    )
