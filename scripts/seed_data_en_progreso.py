"""
seed_data_en_progreso.py — Pre-populate the DataLake with a gaps dataset (C/D scenario).

Same base data as seed_data.py but WITHOUT recipe_unit_conversion entries.
This means the three pza-based ingredients (Chile poblano, Limón, Aguacate) cannot
be converted to grams, so normalization.deductionCoveragePct = 0 % and the Resumen
tab shows unit-mismatch warnings.

Expected score: C/D (~55).

Run:
    uv run python scripts/reset_session.py && uv run python scripts/seed_data_en_progreso.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gradio_app.session import get_data_lake, stable_entity_id

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SESSION_ID = "primary_session"
ENTITY_ID  = stable_entity_id(SESSION_ID)

RESTAURANT = {
    "id":                 ENTITY_ID,
    "name":               "Mi Restaurante (En Progreso)",
    "restaurant_type_id": 1,
}

USER = {
    "id":    ENTITY_ID,
    "name":  "Operador Demo",
    "email": "demo@mirestaurante.com",
    "role":  "owner",
}

CLASSIFICATION = {
    "id":                    ENTITY_ID,
    "standardization_level": 1,
    "restaurant_description": (
        "Restaurante de cocina mexicana contemporánea con menú de temporada."
    ),
}

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
    {"id": 1, "name": "gramo",             "symbol": "g",    "is_standard": True,  "base_unit_id": None, "factor_to_base": 1.0},
    {"id": 2, "name": "kilogramo",         "symbol": "kg",   "is_standard": True,  "base_unit_id": 1,    "factor_to_base": 1000.0},
    {"id": 3, "name": "mililitro",         "symbol": "ml",   "is_standard": True,  "base_unit_id": None, "factor_to_base": 1.0},
    {"id": 4, "name": "litro",             "symbol": "L",    "is_standard": True,  "base_unit_id": 3,    "factor_to_base": 1000.0},
    {"id": 5, "name": "pieza",             "symbol": "pza",  "is_standard": True,  "base_unit_id": None, "factor_to_base": 1.0},
    {"id": 6, "name": "caja de tortillas", "symbol": "caja", "is_standard": False, "base_unit_id": 5,    "factor_to_base": 25.0},
]

_P  = 1
_NP = 2

INVENTORY_ITEMS = [
    {"id":  1, "name": "Bistec",            "stock_unit_id": 1, "purchase_unit_id": 2, "purchase_to_stock_factor": 1000.0, "category_id": _P,  "family_id": 1},
    {"id":  2, "name": "Pollo",             "stock_unit_id": 1, "purchase_unit_id": 2, "purchase_to_stock_factor": 1000.0, "category_id": _P,  "family_id": 1},
    {"id":  3, "name": "Jitomate",          "stock_unit_id": 1, "purchase_unit_id": 2, "purchase_to_stock_factor": 1000.0, "category_id": _P,  "family_id": 2},
    {"id":  4, "name": "Cebolla",           "stock_unit_id": 1, "purchase_unit_id": 2, "purchase_to_stock_factor": 1000.0, "category_id": _P,  "family_id": 2},
    {"id":  5, "name": "Chile poblano",     "stock_unit_id": 1, "purchase_unit_id": 5, "purchase_to_stock_factor":  120.0, "category_id": _P,  "family_id": 2},
    {"id":  6, "name": "Lechuga",           "stock_unit_id": 1, "purchase_unit_id": 5, "purchase_to_stock_factor":  300.0, "category_id": _P,  "family_id": 2},
    {"id":  7, "name": "Limón",             "stock_unit_id": 1, "purchase_unit_id": 5, "purchase_to_stock_factor":   60.0, "category_id": _P,  "family_id": 2},
    {"id":  8, "name": "Cilantro",          "stock_unit_id": 1, "purchase_unit_id": 2, "purchase_to_stock_factor": 1000.0, "category_id": _P,  "family_id": 2},
    {"id":  9, "name": "Aguacate",          "stock_unit_id": 1, "purchase_unit_id": 5, "purchase_to_stock_factor":  200.0, "category_id": _P,  "family_id": 2},
    {"id": 10, "name": "Crema",             "stock_unit_id": 3, "purchase_unit_id": 4, "purchase_to_stock_factor": 1000.0, "category_id": _P,  "family_id": 3},
    {"id": 11, "name": "Queso fresco",      "stock_unit_id": 1, "purchase_unit_id": 2, "purchase_to_stock_factor": 1000.0, "category_id": _P,  "family_id": 3},
    {"id": 12, "name": "Huevo",             "stock_unit_id": 5, "purchase_unit_id": 5, "purchase_to_stock_factor":    1.0, "category_id": _P,  "family_id": 1},
    {"id": 13, "name": "Aceite vegetal",    "stock_unit_id": 3, "purchase_unit_id": 4, "purchase_to_stock_factor": 1000.0, "category_id": _NP, "family_id": 5},
    {"id": 14, "name": "Harina de trigo",   "stock_unit_id": 1, "purchase_unit_id": 2, "purchase_to_stock_factor": 1000.0, "category_id": _NP, "family_id": 4},
    {"id": 15, "name": "Arroz",             "stock_unit_id": 1, "purchase_unit_id": 2, "purchase_to_stock_factor": 1000.0, "category_id": _NP, "family_id": 4},
    {"id": 16, "name": "Frijoles negros",   "stock_unit_id": 1, "purchase_unit_id": 2, "purchase_to_stock_factor": 1000.0, "category_id": _NP, "family_id": 4},
    {"id": 17, "name": "Sal",               "stock_unit_id": 1, "purchase_unit_id": 2, "purchase_to_stock_factor": 1000.0, "category_id": _NP, "family_id": 5},
    {"id": 18, "name": "Azúcar",            "stock_unit_id": 1, "purchase_unit_id": 2, "purchase_to_stock_factor": 1000.0, "category_id": _NP, "family_id": 4},
    {"id": 19, "name": "Tortillas de maíz", "stock_unit_id": 5, "purchase_unit_id": 6, "purchase_to_stock_factor":   25.0, "category_id": _NP, "family_id": 4},
    {"id": 20, "name": "Chile ancho seco",  "stock_unit_id": 1, "purchase_unit_id": 2, "purchase_to_stock_factor": 1000.0, "category_id": _NP, "family_id": 5},
]

# Same 3 recipes as seed_data.py — pza ingredients present but unresolvable
RECIPES = [
    {
        "id": 1,
        "name": "Bistec a la mexicana",
        "category_id": 2,
        "description": "Bistec salteado con jitomate, cebolla y chile poblano.",
        "steps": [
            "Cortar el bistec en tiras de 1 cm.",
            "Picar jitomate, cebolla y chile poblano en brunoise.",
            "Calentar aceite en sartén a fuego alto.",
            "Sellar el bistec 2 min por lado; retirar.",
            "Sofreír cebolla 1 min, añadir jitomate y chile; cocinar 3 min.",
            "Reincorporar el bistec, salpimentar y servir.",
        ],
        "ingredients": [
            {"name": "Bistec",         "quantity": 200.0, "unit_id": 1, "inventory_item_id":  1},
            {"name": "Jitomate",       "quantity": 100.0, "unit_id": 1, "inventory_item_id":  3},
            {"name": "Cebolla",        "quantity":  50.0, "unit_id": 1, "inventory_item_id":  4},
            {"name": "Chile poblano",  "quantity":   1.0, "unit_id": 5, "inventory_item_id":  5},
            {"name": "Aceite vegetal", "quantity":  15.0, "unit_id": 3, "inventory_item_id": 13},
            {"name": "Sal",            "quantity":   5.0, "unit_id": 1, "inventory_item_id": 17},
        ],
    },
    {
        "id": 2,
        "name": "Pollo al limón",
        "category_id": 2,
        "description": "Pechuga de pollo marinada con limón y cilantro.",
        "steps": [
            "Marinar el pollo con jugo de limón, cilantro y sal por 15 min.",
            "Calentar aceite en sartén a fuego medio-alto.",
            "Cocer el pollo 6 min por lado hasta dorar.",
            "Rebanar y servir con rodajas de limón.",
        ],
        "ingredients": [
            {"name": "Pollo",          "quantity": 250.0, "unit_id": 1, "inventory_item_id":  2},
            {"name": "Limón",          "quantity":   2.0, "unit_id": 5, "inventory_item_id":  7},
            {"name": "Cilantro",       "quantity":  10.0, "unit_id": 1, "inventory_item_id":  8},
            {"name": "Aceite vegetal", "quantity":  20.0, "unit_id": 3, "inventory_item_id": 13},
            {"name": "Sal",            "quantity":   3.0, "unit_id": 1, "inventory_item_id": 17},
        ],
    },
    {
        "id": 3,
        "name": "Guacamole",
        "category_id": 1,
        "description": "Guacamole fresco con aguacate, limón, cebolla y cilantro.",
        "steps": [
            "Pelar y deshuesar los aguacates.",
            "Machacar la pulpa con tenedor hasta textura rústica.",
            "Picar finamente la cebolla y el cilantro.",
            "Mezclar aguacate con cebolla, cilantro, jugo de limón y sal.",
            "Rectificar sazón y servir inmediatamente.",
        ],
        "ingredients": [
            {"name": "Aguacate", "quantity":  2.0, "unit_id": 5, "inventory_item_id":  9},
            {"name": "Limón",    "quantity":  1.0, "unit_id": 5, "inventory_item_id":  7},
            {"name": "Cebolla",  "quantity": 30.0, "unit_id": 1, "inventory_item_id":  4},
            {"name": "Cilantro", "quantity":  5.0, "unit_id": 1, "inventory_item_id":  8},
            {"name": "Sal",      "quantity":  3.0, "unit_id": 1, "inventory_item_id": 17},
        ],
    },
]

# NO recipe_unit_conversion entries — this is the gap that drives the C/D score.

# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def seed_en_progreso(data_lake) -> None:
    """Populate data_lake with the en-progreso demo dataset.

    Same inventory and recipes as seed_data.py but without recipe_unit_conversion
    entries. The three pza-based ingredients (Chile poblano, Limón, Aguacate)
    cannot be resolved to grams, so normalization.deductionCoveragePct = 0 % and
    the Resumen tab shows unit-mismatch warnings.

    Importable by other modules (e.g. the Herramientas tab in Manual Operativo).
    Safe to call multiple times — save_entity overwrites existing entities.
    """
    data_lake.save_entity("restaurant",     ENTITY_ID, RESTAURANT)
    data_lake.save_entity("user",           ENTITY_ID, USER)
    data_lake.save_entity("classification", ENTITY_ID, CLASSIFICATION)

    for cat in CATEGORY_RECIPES:
        data_lake.save_entity("category_recipe", cat["id"], cat)

    for fam in FAMILY_INVENTORIES:
        data_lake.save_entity("family_inventory", fam["id"], fam)

    for ru in RECIPE_UNITS:
        data_lake.save_entity("recipe_unit", ru["id"], ru)

    for iu in INVENTORY_UNITS:
        data_lake.save_entity("inventory_unit", iu["id"], iu)

    for item in INVENTORY_ITEMS:
        data_lake.save_entity("inventory_item", item["id"], item)

    for recipe in RECIPES:
        data_lake.save_entity("recipe", recipe["id"], recipe)


def main() -> None:
    data_lake = get_data_lake()
    seed_en_progreso(data_lake)

    perecederos    = sum(1 for i in INVENTORY_ITEMS if i["category_id"] == 1)
    no_perecederos = sum(1 for i in INVENTORY_ITEMS if i["category_id"] == 2)

    print(f"Seed complete (en-progreso scenario). Entity ID: {ENTITY_ID}")
    print(f"  Restaurant:             {RESTAURANT['name']}")
    print(f"  Level:                  {CLASSIFICATION['standardization_level']}")
    print(f"  Categories:             {len(CATEGORY_RECIPES)}")
    print(f"  Families:               {len(FAMILY_INVENTORIES)}")
    print(f"  Recipe units:           {len(RECIPE_UNITS)}")
    print(f"  Inventory units:        {len(INVENTORY_UNITS)} (incl. 1 non-standard)")
    print(f"  Inventory items:        {len(INVENTORY_ITEMS)} ({perecederos} perecederos, {no_perecederos} no perecederos)")
    print(f"  Recipes:                {len(RECIPES)}")
    print(f"  Unit conversions (pza): 0  <- gap intentional")
    print("\nExpected score: C/D (~55). Unit mismatches visible in Manual Operativo Resumen.")


if __name__ == "__main__":
    main()
