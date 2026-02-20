# Ingredient → Inventory Item Workflow

This document describes the workflow for creating recipe ingredients and optionally linking or creating inventory items.

**Related:** 
- Data model: `core/data_model.py` (Ingredient, Recipe.add_ingredient)
- Schema: `.taskmaster/docs/task-3/3.4/plan.md` (recipe_ingredient table)
- Contract: `.taskmaster/docs/task-3/3.1/serialization-contract.md` (section 3.8)

---

## Overview

When a user creates an ingredient in a recipe, the ingredient can exist in three states:

1. **Recipe-only ingredient** — exists in recipe but not tracked in inventory (e.g. "salt", "water")
2. **Linked ingredient** — exists in recipe and links to an existing inventory item (tracked for deduction)
3. **New inventory item** — ingredient doesn't exist in inventory yet; user creates both simultaneously

The schema supports all three cases via the **nullable** `inventory_item_id` field in the `recipe_ingredient` table.

---

## Schema Support

### recipe_ingredient table (SQLite)

```sql
CREATE TABLE recipe_ingredient (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit_id INTEGER NOT NULL,
    inventory_item_id INTEGER,  -- ✅ NULLABLE (optional link)
    FOREIGN KEY (recipe_id) REFERENCES recipe(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES recipe_unit(id),
    FOREIGN KEY (inventory_item_id) REFERENCES inventory_item(id)
);
```

**Key design:** `inventory_item_id` is **nullable**, allowing ingredients to exist without inventory tracking.

### Data model (Python)

From `core/data_model.py`:

```python
@dataclass
class Ingredient:
    name: str
    quantity: float
    unit_id: int
    inventory_item_id: Optional[int] = None  # ✅ Optional link
```

---

## UI/Business Logic Workflow

### Flowchart

```
┌─────────────────────────────────────────────────────┐
│ User adds ingredient to recipe                      │
│ Example: "Cilantro, 50g"                           │
└─────────────────────────────────────────────────────┘
                    ↓
       ┌────────────┴────────────┐
       │ Search inventory by name │
       │ (case-insensitive)       │
       └────────────┬────────────┘
              ↙           ↘
    Found in             NOT found
    inventory            in inventory
         ↓                    ↓
   ┌─────────────┐    ┌──────────────────┐
   │ Show match  │    │ Prompt user:     │
   │ "Link to    │    │ "Cilantro is not │
   │ existing    │    │ in inventory.    │
   │ Cilantro?"  │    │ Add it?"         │
   └──────┬──────┘    └────────┬─────────┘
          │                    │
     ┌────┴────┐         ┌─────┴─────┐
     │   YES   │         │    YES    │    NO
     │   ↓     │         │     ↓     │     ↓
     │  Link   │         │  Create   │  Save with
     │  it     │         │  new item │  NULL link
     └────┬────┘         └─────┬─────┘     ↓
          │                    │        ┌──┴───┐
          │              Update link    │ DONE │
          │                    │        └──────┘
          └────────────────────┘
                    ↓
              ┌──────────┐
              │   DONE   │
              └──────────┘
```

---

## Implementation Steps

### Step 1: User creates ingredient

```python
# User input: "Cilantro, 50, g"
ingredient = Ingredient(
    name="Cilantro",
    quantity=50.0,
    unit_id=recipe_unit_id_for_grams,
    inventory_item_id=None  # Start with NULL
)
```

### Step 2: Check if ingredient exists in inventory

```python
# Query inventory_item table (case-insensitive name match)
cursor = db.execute(
    "SELECT id, name, unit_id FROM inventory_item WHERE LOWER(name) = LOWER(?)",
    (ingredient.name,)
)
existing_item = cursor.fetchone()
```

### Step 3: Handle three cases

#### Case A: Ingredient found in inventory → Prompt to link

```python
if existing_item:
    response = ask_user(
        f"Found '{existing_item['name']}' in inventory. Link to it?",
        options=["Yes", "No, keep separate"]
    )
    
    if response == "Yes":
        ingredient.inventory_item_id = existing_item['id']
        show_message(f"✓ Linked to inventory item: {existing_item['name']}")
    else:
        # User wants to keep ingredient separate (recipe-only)
        ingredient.inventory_item_id = None
        show_message("✓ Ingredient saved (not tracked in inventory)")
```

#### Case B: Not found → Prompt to create inventory item

```python
else:
    response = ask_user(
        f"'{ingredient.name}' is not in inventory. Add it now?",
        options=["Yes, add to inventory", "No, recipe only"]
    )
    
    if response == "Yes, add to inventory":
        # Show form to collect inventory item details
        inventory_item = show_inventory_item_form(
            default_name=ingredient.name,
            default_unit_id=get_inventory_unit_for_recipe_unit(ingredient.unit_id)
        )
        # Form collects: unit_id, category_id, family_id, description
        
        # Validate and create
        new_item = InventoryItem(
            id=0,  # Assigned on save
            name=inventory_item['name'],
            unit_id=inventory_item['unit_id'],
            category_id=inventory_item['category_id'],  # e.g. PERECEDERO
            family_id=inventory_item['family_id'],
            description=inventory_item.get('description')
        )
        
        # Save to database
        new_item_id = persistence.save_inventory_item(new_item)
        
        # Link ingredient to new inventory item
        ingredient.inventory_item_id = new_item_id
        show_message(f"✓ Created and linked to inventory: {new_item.name}")
    else:
        # User doesn't want to track in inventory
        ingredient.inventory_item_id = None
        show_message("✓ Ingredient saved (recipe only)")
```

### Step 4: Save ingredient to recipe

```python
# Add to Recipe object
recipe.ingredients.append(ingredient)

# Persist to database (recipe_ingredient table)
db.execute("""
    INSERT INTO recipe_ingredient 
    (recipe_id, name, quantity, unit_id, inventory_item_id)
    VALUES (?, ?, ?, ?, ?)
""", (
    recipe.id,
    ingredient.name,
    ingredient.quantity,
    ingredient.unit_id,
    ingredient.inventory_item_id  # ✅ Can be NULL
))
```

---

## Example Scenarios

### Scenario 1: Recipe-only ingredient (common seasonings)

**User action:** Adds "Salt" to recipe

**Workflow:**
1. Search inventory → not found
2. Prompt: "Add Salt to inventory?"
3. User selects: "No, recipe only"
4. **Result:** `inventory_item_id = NULL` (not tracked in inventory)

**Why?** Salt is too common/cheap to track; user only needs it in recipe for instructions.

### Scenario 2: Link to existing inventory item

**User action:** Adds "Leche entera" to recipe

**Workflow:**
1. Search inventory → **found** "Leche entera" (id=15)
2. Prompt: "Link to existing inventory item?"
3. User selects: "Yes"
4. **Result:** `inventory_item_id = 15` (linked for inventory deduction)

**Why?** Milk is already tracked in inventory; linking enables automatic deduction when recipe is prepared.

### Scenario 3: Create new inventory item

**User action:** Adds "Carne de cerdo" to recipe

**Workflow:**
1. Search inventory → not found
2. Prompt: "Add Carne de cerdo to inventory?"
3. User selects: "Yes, add to inventory"
4. Form shown: unit_id (kg), category_id (PERECEDERO), family_id (CARNES)
5. Create InventoryItem (id=42)
6. **Result:** `inventory_item_id = 42` (new item created and linked)

**Why?** Pork is a high-value ingredient worth tracking; user wants to monitor stock levels and costs.

---

## Database Queries

### Query: Find all recipe ingredients with inventory links

```sql
SELECT 
    ri.id,
    ri.name AS ingredient_name,
    ri.quantity,
    ru.symbol AS unit_symbol,
    ii.name AS inventory_item_name,
    ii.id AS inventory_item_id
FROM recipe_ingredient ri
LEFT JOIN recipe_unit ru ON ri.unit_id = ru.id
LEFT JOIN inventory_item ii ON ri.inventory_item_id = ii.id
WHERE ri.recipe_id = ?
ORDER BY ri.id;
```

**Result example:**

| ingredient_name | quantity | unit_symbol | inventory_item_name | inventory_item_id |
|----------------|----------|-------------|-------------------|------------------|
| Carne de cerdo | 500.0 | g | Carne de cerdo | 42 |
| Tortillas | 12.0 | pza | Tortillas de maíz | 10 |
| Cilantro | 50.0 | g | NULL | NULL |

### Query: Find ingredients not linked to inventory

```sql
SELECT name, quantity, unit_id
FROM recipe_ingredient
WHERE recipe_id = ? AND inventory_item_id IS NULL;
```

---

## Data Model Integration

The `Recipe.add_ingredient()` method (in `core/data_model.py`) already supports this workflow:

### Usage A: Recipe-only ingredient

```python
ingredient = Ingredient(name="Salt", quantity=5.0, unit_id=GRAMS_UNIT_ID)
result = recipe.add_ingredient(ingredient, valid_recipe_unit_ids)
# result is None (no inventory item created)
# ingredient.inventory_item_id remains None
```

### Usage B: Create inventory item during add

```python
ingredient = Ingredient(name="Carne de cerdo", quantity=500.0, unit_id=GRAMS_UNIT_ID)
new_item = recipe.add_ingredient(
    ingredient,
    valid_unit_ids=recipe_unit_ids,
    category_id=PERECEDERO,  # ✅ Triggers inventory item creation
    unit_id_for_inventory=KILOGRAM_UNIT_ID,
    family_id=CARNES_FAMILY_ID
)
# Returns InventoryItem(id=0, name="Carne de cerdo", ...)
# Caller must:
# 1. Persist new_item to get real ID
# 2. Update ingredient.inventory_item_id = new_item.id
```

---

## Migration/Update Workflow

### Promoting recipe-only ingredient to inventory item

If a user initially created an ingredient without inventory tracking but later wants to add it:

```python
# 1. Find the ingredient in recipe
ingredient = recipe.get_ingredient_by_name("Cilantro")

# 2. Check if already linked
if ingredient.inventory_item_id is not None:
    show_message("Already tracked in inventory")
    return

# 3. Show inventory item creation form
inventory_item = show_inventory_item_form(default_name=ingredient.name)

# 4. Create inventory item
new_item = InventoryItem(
    id=0,
    name=inventory_item['name'],
    unit_id=inventory_item['unit_id'],
    category_id=inventory_item['category_id'],
    family_id=inventory_item['family_id']
)
new_item_id = persistence.save_inventory_item(new_item)

# 5. Update ingredient link
ingredient.inventory_item_id = new_item_id

# 6. Update database
db.execute(
    "UPDATE recipe_ingredient SET inventory_item_id = ? WHERE id = ?",
    (new_item_id, ingredient_db_id)
)
```

---

## Summary

**The schema and data model already support this workflow perfectly:**

✅ **Flexible linking:** `inventory_item_id` is nullable  
✅ **Three states:** recipe-only, linked to existing, create new  
✅ **No schema changes needed:** current design handles all cases  
✅ **Future-proof:** can promote recipe-only ingredients to inventory items later

**UI implementation tasks:**
1. Implement case-insensitive inventory search by name
2. Add prompts for linking/creating decisions
3. Create inventory item form (unit, category, family)
4. Handle NULL vs non-NULL `inventory_item_id` in save logic
5. Optional: Add "promote to inventory" feature for existing recipe-only ingredients
