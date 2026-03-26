"""
seed_data.py — Pre-populate the DataLake with test data for steps 1–3.

Run this script once before launching the app to skip the first three sections
and land directly on step 4 (Alineamiento):

    uv run python scripts/seed_data.py

To wipe and re-seed:

    uv run python scripts/reset_session.py && uv run python scripts/seed_data.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gradio_app.session import get_data_lake, stable_entity_id

# ---------------------------------------------------------------------------
# Configuration — edit these values to match your restaurant
# ---------------------------------------------------------------------------

SESSION_ID   = "primary_session"
ENTITY_ID    = stable_entity_id(SESSION_ID)

# Step 1 — Restaurant (Bienvenida)
RESTAURANT = {
    "id":                 ENTITY_ID,
    "name":               "Mi Restaurante",
    "restaurant_type_id": 1,          # 1=Restaurante, 2=Cafetería, 3=Bar, 4=Panadería, 5=Food truck
}

USER = {
    "id":    ENTITY_ID,
    "name":  "Operador Demo",
    "email": "demo@mirestaurante.com",
    "role":  "owner",
}

# Step 2 — Classification (Clasificación)
CLASSIFICATION = {
    "id":                    ENTITY_ID,
    "standardization_level": 1,        # 1=básico, 2=intermedio, 3=avanzado
    "restaurant_description": (
        "Restaurante de cocina mexicana contemporánea con menú de temporada."
    ),
}

# Step 3 — Configuration (Configuración)
# Customize these lists to match what was configured in step 3.

CATEGORY_RECIPES = [
    {"id": 1, "name": "Entradas"},
    {"id": 2, "name": "Platos fuertes"},
    {"id": 3, "name": "Postres"},
    {"id": 4, "name": "Bebidas"},
]

FAMILY_INVENTORIES = [
    {"id": 1, "name": "Carnes y proteínas"},
    {"id": 2, "name": "Verduras y hortalizas"},
    {"id": 3, "name": "Lácteos"},
    {"id": 4, "name": "Granos y cereales"},
    {"id": 5, "name": "Salsas y condimentos"},
    {"id": 6, "name": "Bebidas"},
]

RECIPE_UNITS = [
    {"id": 1,  "name": "gramo",        "symbol": "g"},
    {"id": 2,  "name": "kilogramo",    "symbol": "kg"},
    {"id": 3,  "name": "mililitro",    "symbol": "ml"},
    {"id": 4,  "name": "litro",        "symbol": "L"},
    {"id": 5,  "name": "pieza",        "symbol": "pza"},
    {"id": 6,  "name": "cucharada",    "symbol": "cda"},
    {"id": 7,  "name": "cucharadita",  "symbol": "cdta"},
    {"id": 8,  "name": "onza",         "symbol": "oz"},
    {"id": 9,  "name": "taza",         "symbol": "taza"},
    {"id": 10, "name": "scoop rojo",   "symbol": "scoop rojo"},
    {"id": 11, "name": "scoop morado", "symbol": "scoop morado"},
    {"id": 12, "name": "rodaja",       "symbol": "rodaja"},
    {"id": 13, "name": "manojo",       "symbol": "manojo"},
]

INVENTORY_UNITS = [
    {"id": 1, "name": "gramo",      "symbol": "g",   "base_unit_id": None, "factor_to_base": 1.0},
    {"id": 2, "name": "kilogramo",  "symbol": "kg",  "base_unit_id": None, "factor_to_base": 1.0},
    {"id": 3, "name": "mililitro",  "symbol": "ml",  "base_unit_id": None, "factor_to_base": 1.0},
    {"id": 4, "name": "litro",      "symbol": "L",   "base_unit_id": None, "factor_to_base": 1.0},
    {"id": 5, "name": "pieza",      "symbol": "pza", "base_unit_id": None, "factor_to_base": 1.0},
]

# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def main() -> None:
    data_lake = get_data_lake()

    data_lake.save_entity("restaurant",   ENTITY_ID, RESTAURANT)
    data_lake.save_entity("user",         ENTITY_ID, USER)
    data_lake.save_entity("classification", ENTITY_ID, CLASSIFICATION)

    for cat in CATEGORY_RECIPES:
        data_lake.save_entity("category_recipe", cat["id"], cat)

    for fam in FAMILY_INVENTORIES:
        data_lake.save_entity("family_inventory", fam["id"], fam)

    for ru in RECIPE_UNITS:
        data_lake.save_entity("recipe_unit", ru["id"], ru)

    for iu in INVENTORY_UNITS:
        data_lake.save_entity("inventory_unit", iu["id"], iu)

    print(f"Seed complete. Entity ID: {ENTITY_ID}")
    print(f"  Restaurant:      {RESTAURANT['name']}")
    print(f"  Level:           {CLASSIFICATION['standardization_level']}")
    print(f"  Categories:      {len(CATEGORY_RECIPES)}")
    print(f"  Families:        {len(FAMILY_INVENTORIES)}")
    print(f"  Recipe units:    {len(RECIPE_UNITS)}")
    print(f"  Inventory units: {len(INVENTORY_UNITS)}")
    print("\nLaunch the app and go straight to step 4 — Alineamiento.")


if __name__ == "__main__":
    main()
