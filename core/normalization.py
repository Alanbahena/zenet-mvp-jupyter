"""
Unit conversion and normalization for inventory deduction (subtask 2.3).

Provides: to_base_quantity / from_base_quantity for InventoryUnit chains;
family base unit resolution; recipe-unit conversion table application;
normalized recipe (list per recipe for deduction on order).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional

from core.data_model import (
    FamilyInventoryRegistry,
    Ingredient,
    InventoryUnit,
    InventoryUnitEquivalenceRegistry,
    InventoryUnitRegistry,
    Recipe,
)


# --- Step 2.3.1: to_base_quantity --------------------------------------------

def to_base_quantity(
    quantity: float,
    unit: InventoryUnit,
    registry: InventoryUnitRegistry,
    *,
    inventory_item_id: Optional[int] = None,
    equivalence_registry: Optional[InventoryUnitEquivalenceRegistry] = None,
) -> float:
    """Convert quantity from the given unit to its base (root of base_unit_id chain).

    If inventory_item_id and equivalence_registry are provided and an item-specific
    equivalence exists, use it for the first step (e.g. 1 box strawberries = 2 kg);
    otherwise use the unit's built-in base_unit_id/factor_to_base chain.
    If unit.base_unit_id is None (and no equivalence), returns quantity * unit.factor_to_base.
    Detects cycles and broken chains; raises ValueError.
    """
    if not math.isfinite(quantity):
        raise ValueError("quantity must be finite")

    if inventory_item_id is not None and equivalence_registry is not None:
        equiv = equivalence_registry.get(unit.id, inventory_item_id)
        if equiv is not None:
            result = quantity * equiv.factor_to_base
            base_unit = registry.get(equiv.base_unit_id)
            if base_unit is None:
                raise ValueError(
                    f"equivalence base_unit_id {equiv.base_unit_id} not found in registry"
                )
            if base_unit.base_unit_id is None:
                return result
            return to_base_quantity(result, base_unit, registry)

    visited: set[int] = set()
    current: Optional[InventoryUnit] = unit
    result = quantity
    while current is not None:
        if current.id in visited:
            raise ValueError("base_unit_id chain contains a cycle")
        visited.add(current.id)
        result *= current.factor_to_base
        if current.base_unit_id is None:
            return result
        next_unit = registry.get(current.base_unit_id)
        if next_unit is None:
            raise ValueError(
                f"base_unit_id {current.base_unit_id} not found in registry (broken chain)"
            )
        current = next_unit
    return result


# --- Step 2.3.2: from_base_quantity -----------------------------------------

def from_base_quantity(
    base_quantity: float,
    unit: InventoryUnit,
    registry: InventoryUnitRegistry,
    *,
    inventory_item_id: Optional[int] = None,
    equivalence_registry: Optional[InventoryUnitEquivalenceRegistry] = None,
) -> float:
    """Convert a quantity expressed in the base (root) of the unit's chain into the given unit.

    If inventory_item_id and equivalence_registry are provided and an item-specific
    equivalence exists, use it; otherwise use the unit's built-in chain.
    Inverse of to_base_quantity. Detects cycles and broken chains; raises ValueError.
    """
    if not math.isfinite(base_quantity):
        raise ValueError("base_quantity must be finite")

    if inventory_item_id is not None and equivalence_registry is not None:
        equiv = equivalence_registry.get(unit.id, inventory_item_id)
        if equiv is not None:
            base_unit = registry.get(equiv.base_unit_id)
            if base_unit is None:
                raise ValueError(
                    f"equivalence base_unit_id {equiv.base_unit_id} not found in registry"
                )
            product_rest = _factor_product_to_base(base_unit, registry)
            return base_quantity / (equiv.factor_to_base * product_rest)

    product = _factor_product_to_base(unit, registry)
    return base_quantity / product


def _factor_product_to_base(
    unit: InventoryUnit,
    registry: InventoryUnitRegistry,
) -> float:
    """Product of factor_to_base along the chain from unit to root. Used for from_base."""
    visited: set[int] = set()
    current: Optional[InventoryUnit] = unit
    product = 1.0
    while current is not None:
        if current.id in visited:
            raise ValueError("base_unit_id chain contains a cycle")
        visited.add(current.id)
        product *= current.factor_to_base
        if current.base_unit_id is None:
            return product
        next_unit = registry.get(current.base_unit_id)
        if next_unit is None:
            raise ValueError(
                f"base_unit_id {current.base_unit_id} not found in registry (broken chain)"
            )
        current = next_unit
    return product


# --- Step 2.3.3: Overloads by unit_id ---------------------------------------

def to_base_quantity_by_id(
    quantity: float,
    unit_id: int,
    registry: InventoryUnitRegistry,
    *,
    inventory_item_id: Optional[int] = None,
    equivalence_registry: Optional[InventoryUnitEquivalenceRegistry] = None,
) -> float:
    """Look up unit by id and convert quantity to base. Raises ValueError if unit_id not found."""
    unit = registry.get(unit_id)
    if unit is None:
        raise ValueError(f"unit_id {unit_id} not found")
    return to_base_quantity(
        quantity,
        unit,
        registry,
        inventory_item_id=inventory_item_id,
        equivalence_registry=equivalence_registry,
    )


def from_base_quantity_by_id(
    base_quantity: float,
    unit_id: int,
    registry: InventoryUnitRegistry,
    *,
    inventory_item_id: Optional[int] = None,
    equivalence_registry: Optional[InventoryUnitEquivalenceRegistry] = None,
) -> float:
    """Look up unit by id and convert base quantity to that unit. Raises if unit_id not found."""
    unit = registry.get(unit_id)
    if unit is None:
        raise ValueError(f"unit_id {unit_id} not found")
    return from_base_quantity(
        base_quantity,
        unit,
        registry,
        inventory_item_id=inventory_item_id,
        equivalence_registry=equivalence_registry,
    )


# --- Step 2.3.5: convert_quantity (same family) ------------------------------

def _root_base_unit_id(unit_id: int, registry: InventoryUnitRegistry) -> int:
    """Return the id of the root unit (base_unit_id is None) in the chain from unit_id."""
    visited: set[int] = set()
    current_id: Optional[int] = unit_id
    while current_id is not None:
        if current_id in visited:
            raise ValueError("base_unit_id chain contains a cycle")
        visited.add(current_id)
        u = registry.get(current_id)
        if u is None:
            raise ValueError(f"unit_id {current_id} not found in registry (broken chain)")
        if u.base_unit_id is None:
            return u.id
        current_id = u.base_unit_id
    raise ValueError("chain did not reach a root unit")


def convert_quantity(
    quantity: float,
    from_unit_id: int,
    to_unit_id: int,
    registry: InventoryUnitRegistry,
    *,
    inventory_item_id: Optional[int] = None,
    equivalence_registry: Optional[InventoryUnitEquivalenceRegistry] = None,
) -> float:
    """Convert quantity between two units that share the same root base.

    If the two units have different root bases (e.g. kg vs L), raises ValueError.
    Optional inventory_item_id and equivalence_registry apply when converting
    from_unit_id to base (e.g. 1 caja strawberries = 2 kg); the step from base
    to to_unit_id uses the unit chain only.
    """
    if not math.isfinite(quantity):
        raise ValueError("quantity must be finite")
    root_from = _root_base_unit_id(from_unit_id, registry)
    root_to = _root_base_unit_id(to_unit_id, registry)
    if root_from != root_to:
        raise ValueError(
            f"incompatible units: from_unit_id {from_unit_id} (root {root_from}) "
            f"and to_unit_id {to_unit_id} (root {root_to})"
        )
    base_qty = to_base_quantity_by_id(
        quantity,
        from_unit_id,
        registry,
        inventory_item_id=inventory_item_id,
        equivalence_registry=equivalence_registry,
    )
    return from_base_quantity_by_id(base_qty, to_unit_id, registry)


# --- Step 2.3.6: Family base unit -------------------------------------------

def get_family_base_unit_id(
    family_id: int,
    family_registry: FamilyInventoryRegistry,
    unit_registry: InventoryUnitRegistry,
) -> Optional[int]:
    """Return the base_unit_id for the given family, or None if not set.

    If base_unit_id is set but not in unit_registry, raises ValueError.
    """
    family = family_registry.get(family_id)
    if family is None:
        return None
    bid = family.base_unit_id
    if bid is None:
        return None
    if unit_registry.get(bid) is None:
        raise ValueError(f"family {family_id} base_unit_id {bid} not found in unit registry")
    return bid


# --- Step 2.3.7: Recipe-unit conversion table --------------------------------

@dataclass(frozen=True)
class RecipeUnitConversionKey:
    """Key for recipe-unit conversion: recipe_unit_id + optional context."""

    recipe_unit_id: int
    family_id: Optional[int] = None
    inventory_item_id: Optional[int] = None


@dataclass
class RecipeUnitConversionEntry:
    """One conversion: normalized quantity and base_unit_id."""

    quantity: float
    base_unit_id: int


class RecipeUnitConversionRegistry:
    """Registry of recipe-unit -> (quantity, base_unit_id) for unofficial units (scoop, cucharada, etc.)."""

    def __init__(self) -> None:
        self._entries: dict[tuple[int, Optional[int], Optional[int]], RecipeUnitConversionEntry] = {}

    def add(
        self,
        recipe_unit_id: int,
        quantity: float,
        base_unit_id: int,
        *,
        family_id: Optional[int] = None,
        inventory_item_id: Optional[int] = None,
    ) -> None:
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("quantity must be finite and > 0")
        key = (recipe_unit_id, family_id, inventory_item_id)
        self._entries[key] = RecipeUnitConversionEntry(quantity=quantity, base_unit_id=base_unit_id)

    def get(
        self,
        recipe_unit_id: int,
        family_id: Optional[int] = None,
        inventory_item_id: Optional[int] = None,
    ) -> Optional[RecipeUnitConversionEntry]:
        """Best match: (ru, family, item) then (ru, family, None) then (ru, None, item) then (ru, None, None)."""
        for key in (
            (recipe_unit_id, family_id, inventory_item_id),
            (recipe_unit_id, family_id, None),
            (recipe_unit_id, None, inventory_item_id),
            (recipe_unit_id, None, None),
        ):
            if key in self._entries:
                return self._entries[key]
        return None


def normalize_recipe_unit_quantity(
    quantity: float,
    recipe_unit_id: int,
    family_id: Optional[int],
    inventory_item_id: Optional[int],
    conversion_table: RecipeUnitConversionRegistry,
    unit_registry: InventoryUnitRegistry,
) -> tuple[float, int]:
    """Return (normalized_quantity, base_unit_id) for the given recipe unit and context.

    Looks up best match in the conversion table. If found, returns (quantity * entry.quantity, entry.base_unit_id)
    when the table stores a per-unit conversion (e.g. 1 scoop = 30 g), so normalized_quantity = quantity * 30.
    Assumes table entries are for "1 unit" so we multiply: quantity * entry.quantity.
    If no match, raises ValueError.
    """
    if not math.isfinite(quantity) or quantity <= 0:
        raise ValueError("quantity must be finite and > 0")
    entry = conversion_table.get(recipe_unit_id, family_id, inventory_item_id)
    if entry is None:
        raise ValueError(
            f"no conversion for recipe_unit_id={recipe_unit_id}, "
            f"family_id={family_id}, inventory_item_id={inventory_item_id}"
        )
    if unit_registry.get(entry.base_unit_id) is None:
        raise ValueError(
            f"conversion table entry has base_unit_id {entry.base_unit_id} not in registry"
        )
    normalized = quantity * entry.quantity
    return (normalized, entry.base_unit_id)


# --- Step 2.3.8: Normalized recipe for deduction ----------------------------

DeductionLine = tuple[int, float, int]  # (inventory_item_id, normalized_quantity, base_unit_id)


def normalize_recipe_for_deduction(
    recipe: Recipe,
    family_registry: FamilyInventoryRegistry,
    unit_registry: InventoryUnitRegistry,
    conversion_table: RecipeUnitConversionRegistry,
    resolve_ingredient_to_inventory: Callable[[Ingredient], tuple[int, Optional[int]]],
    *,
    equivalence_registry: Optional[InventoryUnitEquivalenceRegistry] = None,
) -> list[DeductionLine]:
    """Produce the normalized recipe: list of (inventory_item_id, normalized_quantity, base_unit_id).

    For each ingredient, resolves to (inventory_item_id, family_id) via resolve_ingredient_to_inventory.
    Then normalizes using conversion table (recipe unit -> quantity, base_unit_id) or family base.
    When equivalence_registry is provided, item-specific unit equivalences (e.g. 1 box strawberries
    = 2 kg, 1 box oranges = 10 kg) are used in the fallback path. Ingredients that cannot be
    normalized are skipped. Returns "consumo teórico por platillo" for one order of this recipe.
    """
    result: list[DeductionLine] = []
    for ing in recipe.ingredients:
        try:
            inventory_item_id, family_id = resolve_ingredient_to_inventory(ing)
        except (ValueError, KeyError):
            continue
        try:
            norm_qty, base_unit_id = normalize_recipe_unit_quantity(
                ing.quantity,
                ing.unit_id,
                family_id,
                ing.inventory_item_id,
                conversion_table,
                unit_registry,
            )
            result.append((inventory_item_id, norm_qty, base_unit_id))
        except ValueError:
            # Fallback: if ingredient.unit_id is in unit_registry (inventory unit) and family has base, convert to family base
            base_uid = get_family_base_unit_id(family_id, family_registry, unit_registry)
            if base_uid is None:
                continue
            if unit_registry.get(ing.unit_id) is None:
                continue  # recipe-only unit, no conversion table entry and not in inventory registry
            try:
                root_ing = _root_base_unit_id(ing.unit_id, unit_registry)
                root_base = _root_base_unit_id(base_uid, unit_registry)
                if root_ing != root_base:
                    continue  # incompatible dimensions
                base_qty = to_base_quantity_by_id(
                    ing.quantity,
                    ing.unit_id,
                    unit_registry,
                    inventory_item_id=inventory_item_id,
                    equivalence_registry=equivalence_registry,
                )
                norm_qty = from_base_quantity_by_id(base_qty, base_uid, unit_registry)
                result.append((inventory_item_id, norm_qty, base_uid))
            except ValueError:
                continue
    return result
