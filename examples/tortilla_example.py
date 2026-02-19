#!/usr/bin/env python3
"""
Zenet MVP 0.1 — Tortilla example: recipe in piezas, inventory in kg.

Run from project root:
  python examples/tortilla_example.py
  # If core is not installed: PYTHONPATH=. python examples/tortilla_example.py

Demonstrates the conversion table for different-dimension units:
  - Recipe uses "3 tortillas" in piezas (pza).
  - Inventory stores "Tortilla" in kg.
  - A conversion entry (1 pza = 0.05 kg) lets normalize_recipe_for_deduction
    produce a deduction line in kg.
"""

from core import (
    format_deduction_line_for_display,
    ingredients_to_display,
    make_resolver_from_item_registry,
    normalize_recipe_for_deduction,
)
from core.data_model import (
    CategoryRecipe,
    CategoryRecipeRegistry,
    FamilyInventory,
    FamilyInventoryRegistry,
    Ingredient,
    InventoryItem,
    InventoryItemRegistry,
    InventoryUnit,
    InventoryUnitRegistry,
    Recipe,
    RecipeUnit,
    RecipeUnitRegistry,
)
from core.normalization import RecipeUnitConversionRegistry


def main() -> None:
    # --- Units: g, kg, pza (pieza) ---
    recipe_unit_reg = RecipeUnitRegistry()
    for uid, name, symbol in [(1, "gramo", "g"), (2, "kilogramo", "kg"), (3, "pieza", "pza")]:
        recipe_unit_reg.add(RecipeUnit(uid, name, symbol))

    inv_unit_reg = InventoryUnitRegistry()
    for uid, name, symbol, base_id, factor in [
        (1, "gramo", "g", None, 1.0),
        (2, "kilogramo", "kg", None, 1.0),
        (3, "pieza", "pza", None, 1.0),
    ]:
        inv_unit_reg.add(
            InventoryUnit(uid, name, symbol, base_unit_id=base_id, factor_to_base=factor)
        )

    category_reg = CategoryRecipeRegistry()
    category_reg.add(CategoryRecipe(1, "Platos", None))

    # Family with base unit kg for deduction
    family_reg = FamilyInventoryRegistry()
    family_reg.add(FamilyInventory(1, "Pan y tortilla", None, base_unit_id=2))

    # Tortilla: stored in kg in inventory
    item_reg = InventoryItemRegistry()
    item_reg.add(
        InventoryItem(
            id=1,
            name="Tortilla",
            unit_id=2,
            category_id=1,
            family_id=1,
        )
    )

    # --- Recipe: 3 tortillas (in pza) + 100 g salsa (same-dimension example)
    item_reg.add(
        InventoryItem(
            id=2,
            name="Salsa",
            unit_id=1,
            category_id=1,
            family_id=1,
        )
    )

    recipe = Recipe(
        id=20,
        name="Tacos al pastor",
        description="Tacos con tortilla y salsa",
        steps=["Calentar tortillas.", "Agregar salsa."],
        category_id=1,
        ingredients=[
            Ingredient("Tortilla", 3.0, 3, inventory_item_id=1),
            Ingredient("Salsa", 100.0, 1, inventory_item_id=2),
        ],
    )

    print("=== 1. Ingredients (recipe view) ===\n")
    rows = ingredients_to_display(recipe, recipe_unit_reg, item_reg)
    for row in rows:
        part = f"{row['quantity']} {row['unit_symbol']} {row['name']}"
        if row.get("inventory_item_name"):
            part += f" → {row['inventory_item_name']}"
        print(f"  {part}")

    # --- Conversion table: 1 tortilla (pza) = 0.05 kg
    # Required because recipe unit is pza and inventory unit is kg (different dimension).
    conversion_table = RecipeUnitConversionRegistry()
    conversion_table.add(
        recipe_unit_id=3,
        quantity=0.05,
        base_unit_id=2,
        inventory_item_id=1,
    )

    resolver = make_resolver_from_item_registry(item_reg)
    deduction_lines = normalize_recipe_for_deduction(
        recipe,
        family_reg,
        inv_unit_reg,
        conversion_table,
        resolver,
    )

    print("\n=== 2. Deduction lines (consumo teórico por platillo) ===\n")
    print("  (Tortilla: 3 pza × 0.05 kg/pza = 0.15 kg; Salsa: 100 g)")
    for line in deduction_lines:
        display = format_deduction_line_for_display(line, inv_unit_reg, item_reg)
        print(f"  {display}")

    print("\nDone.")


if __name__ == "__main__":
    main()
