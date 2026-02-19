#!/usr/bin/env python3
"""
Zenet MVP 0.1 — Quickstart: data model, normalization, and readiness in one flow.

Run from project root:
  python examples/quickstart.py
  # If core is not installed: PYTHONPATH=. python examples/quickstart.py

Demonstrates:
  1. Building registries (recipe units, inventory units, categories, families, inventory items).
  2. Creating a recipe with ingredients linked to inventory.
  3. Display formatting (ingredients_to_display, format_deduction_line_for_display).
  4. Normalization: normalize_recipe_for_deduction and deduction lines.
  5. Readiness: compute_readiness_report and overall score / KPIs.
"""

from core import (
    compute_readiness_report,
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
    Restaurant,
)
from core.normalization import RecipeUnitConversionRegistry


def main() -> None:
    # --- 1. Registries ---
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

    family_reg = FamilyInventoryRegistry()
    family_reg.add(FamilyInventory(1, "Granos", None, base_unit_id=1))

    item_reg = InventoryItemRegistry()
    item_reg.add(
        InventoryItem(
            id=1,
            name="Harina",
            unit_id=1,
            category_id=1,
            family_id=1,
        )
    )
    item_reg.add(
        InventoryItem(
            id=2,
            name="Azúcar",
            unit_id=1,
            category_id=2,
            family_id=1,
        )
    )

    # --- 2. Recipe with ingredients linked to inventory ---
    recipe = Recipe(
        id=10,
        name="Pan simple",
        description="Pan básico",
        steps=["Mezclar harina y azúcar.", "Hornear."],
        category_id=1,
        ingredients=[
            Ingredient("Harina", 250.0, 1, inventory_item_id=1),
            Ingredient("Azúcar", 50.0, 1, inventory_item_id=2),
        ],
    )

    print("=== 1. Display: ingredients ===\n")
    rows = ingredients_to_display(recipe, recipe_unit_reg, item_reg)
    for row in rows:
        part = f"{row['quantity']} {row['unit_symbol']} {row['name']}"
        if row.get("inventory_item_name"):
            part += f" → {row['inventory_item_name']}"
        print(f"  {part}")

    # --- 3. Normalization: deduction lines ---
    conversion_table = RecipeUnitConversionRegistry()
    resolver = make_resolver_from_item_registry(item_reg)
    deduction_lines = normalize_recipe_for_deduction(
        recipe,
        family_reg,
        inv_unit_reg,
        conversion_table,
        resolver,
    )

    print("\n=== 2. Deduction lines (consumo teórico por platillo) ===\n")
    for line in deduction_lines:
        display = format_deduction_line_for_display(line, inv_unit_reg, item_reg)
        print(f"  {display}")

    # --- 4. Readiness report ---
    restaurant = Restaurant(id=1, name="Panadería Demo", restaurant_type_id=4)
    report = compute_readiness_report(
        restaurant,
        recipes=[recipe],
        recipe_unit_registry=recipe_unit_reg,
        inventory_unit_registry=inv_unit_reg,
        category_recipe_registry=category_reg,
        family_inventory_registry=family_reg,
        inventory_item_registry=item_reg,
        conversion_table=conversion_table,
    )

    print("\n=== 3. Readiness report ===\n")
    overall = report["overall"]
    print(f"  Status: {overall['status']}")
    print(f"  Grade:  {overall['grade']}")
    print(f"  Score:  {overall.get('score', 'N/A')}")
    print("\n  Sample KPIs:")
    for kpi in report.get("kpis", [])[:4]:
        print(f"    - {kpi.get('kpi_id', '')}: {kpi.get('status', '')} ({kpi.get('value', '')})")

    print("\nDone.")


if __name__ == "__main__":
    main()
