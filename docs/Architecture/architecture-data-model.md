# Architecture: `core/data_model.py`

Core entity classes for recipes, inventory, units, and categories. Defines the foundational data model for Zenet MVP: Restaurant, RestaurantType, User, Recipe, Ingredient, RecipeUnit, InventoryItem, InventoryUnit, FamilyInventory, CategoryRecipe, and InventoryCategory. Includes registries and relationship methods (2.2).

---

## 1. Entity and registry overview

```mermaid
flowchart TB
    subgraph fixed["Fixed / templates (by RestaurantType)"]
        RT[RestaurantType]
        IC[InventoryCategory]
        T[CategoryRecipe template]
        T2[FamilyInventory template]
        T3[RecipeUnit template]
        T4[InventoryUnit template]
    end

    subgraph entities["Core entities"]
        R[Restaurant]
        U[User]
        Rec[Recipe]
        Ing[Ingredient]
        II[InventoryItem]
        RU[RecipeUnit]
        IU[InventoryUnit]
        CR[CategoryRecipe]
        FI[FamilyInventory]
    end

    subgraph registries["Registries (add/remove/valid_ids/get)"]
        RUR[RecipeUnitRegistry]
        IUR[InventoryUnitRegistry]
        IIR[InventoryItemRegistry]
        CRR[CategoryRecipeRegistry]
        FIR[FamilyInventoryRegistry]
        UR[UserRegistry]
    end

    R -->|restaurant_type_id| RT
    Rec -->|category_id| CR
    Rec -->|ingredients| Ing
    Ing -->|unit_id| RU
    Ing -.->|inventory_item_id| II
    II -->|stock_unit_id| IU
    II -->|purchase_unit_id| IU
    II -->|category_id| IC
    II -.->|family_id| FI
    U -->|role| ROLES[admin, mesero, cocinero, inventario]

    RUR -.->|stores| RU
    IUR -.->|stores| IU
    IIR -.->|stores| II
    CRR -.->|stores| CR
    FIR -.->|stores| FI
    UR -.->|stores| U
```

![Entity and registry overview](images/data-model-01-entity-registry.png)

---

## 2. Class diagram

```mermaid
classDiagram
    class RecipeUnit {
        +int id
        +str name
        +str symbol
        +str? description
    }
    class InventoryUnit {
        +int id
        +str name
        +str symbol
        +str? description
        +int? base_unit_id
        +float factor_to_base
        +bool is_standard
    }
    class CategoryRecipe {
        +int id
        +str name
        +str? description
    }
    class FamilyInventory {
        +int id
        +str name
        +str? description
        +int? base_unit_id
    }
    class InventoryCategory {
        +int id
        +str name
        +str? description
    }
    class RestaurantType {
        +int id
        +str name
        +str? description
    }
    class Restaurant {
        +int id
        +str name
        +str? address
        +int? restaurant_type_id
        +str? notes
        +update_address()
        +update_restaurant_type_id()
        +clear_*()
    }
    %% Note: restaurant_description is NOT a field on the Restaurant dataclass.
    %% It lives in the classification entity JSON blob. See Task 17 note below.
    class User {
        +int id
        +str name
        +str email
        +str role
    }
    class InventoryItem {
        +int id
        +str name
        +int stock_unit_id
        +int purchase_unit_id
        +float purchase_to_stock_factor
        +int category_id
        +int? family_id
        +str? description
        +update_family_id()
        +update_category_id()
    }
    class Ingredient {
        +str name
        +float quantity
        +int unit_id
        +int? inventory_item_id
    }
    class Recipe {
        +int id
        +str name
        +str description
        +list~str~ steps
        +int category_id
        +list~Ingredient~ ingredients
        +add_ingredient()
        +remove_ingredient()
        +ingredient_count()
        +has_ingredient()
        +get_ingredient_by_name()
        +update_category_id()
    }

    Recipe "1" --> "*" Ingredient : ingredients
    Ingredient --> RecipeUnit : unit_id
    Ingredient ..> InventoryItem : inventory_item_id
    Recipe --> CategoryRecipe : category_id
    Restaurant --> RestaurantType : restaurant_type_id
    InventoryItem --> InventoryUnit : stock_unit_id
    InventoryItem --> InventoryUnit : purchase_unit_id
    InventoryItem --> InventoryCategory : category_id
    InventoryItem ..> FamilyInventory : family_id
```

![Class diagram](images/data-model-02-class-diagram.png)
<!-- NOTE: PNG is stale — class diagram Mermaid source updated for Task 11 (InventoryItem two-unit model; InventoryUnitEquivalence removed). Regenerate from Mermaid source. -->

---

## 3. Template flow (by `restaurant_type_id`)

Templates are keyed by `RestaurantType` id (1–5). Use the getter functions to obtain default categories, families, and units when setting up a new restaurant.

```mermaid
flowchart LR
    RT[RestaurantType id 1..5] --> get_category_recipe_template
    RT --> get_family_inventory_template
    RT --> get_recipe_unit_template
    RT --> get_inventory_unit_template
    get_category_recipe_template --> CR[CategoryRecipe tuple]
    get_family_inventory_template --> FI[FamilyInventory tuple]
    get_recipe_unit_template --> RU[RecipeUnit tuple]
    get_inventory_unit_template --> IU[InventoryUnit tuple]
```

![Template flow](images/data-model-03-template-flow.png)

**Template getters:**

- `get_category_recipe_template(restaurant_type_id)` → `tuple[CategoryRecipe, ...]`
- `get_family_inventory_template(restaurant_type_id)` → `tuple[FamilyInventory, ...]`
- `get_recipe_unit_template(restaurant_type_id)` → `tuple[RecipeUnit, ...]`
- `get_inventory_unit_template(restaurant_type_id)` → `tuple[InventoryUnit, ...]`

Template behavior:

- Template items use `id=0`; assign real ids when adding to a registry.
- If `restaurant_type_id` is invalid (not in `DEFAULT_RESTAURANT_TYPES`), each getter returns an **empty tuple**.

---

## 4. Note on `restaurant_description` (Task 17)

`restaurant_description` is **not** a field on the `Restaurant` dataclass and is **not** a
column on the `restaurant` SQLite table. It is stored in the `classification` entity's JSON
`data` blob alongside `standardization_level`.

**Why:** The `restaurant` table uses typed SQLite columns (see `core/storage/schema.py`).
Adding a new column requires a schema migration. The `classification` entity uses a generic
JSON blob — any keys can be added without touching the schema.

**Where to find it:**
- Stored by: `_make_confirm_fn` in `gradio_app/sections/clasificacion.py`
- Loaded by: `_load_configuration_context` in `gradio_app/sections/configuracion.py`
- Full entity schema: see `docs/Architecture/sections/clasificacion.md` Section 5

---

## 5. Fixed data (no registries)

- **RestaurantType:** `DEFAULT_RESTAURANT_TYPES` (Casual, Rápida, Gourmet, Cafeterías, Cafés). User selects only.
- **InventoryCategory:** `DEFAULT_INVENTORY_CATEGORIES` (Perecedero, No perecedero). User selects only.

Validation helpers: `_valid_restaurant_type_ids()`, `_valid_inventory_category_ids()`.

---

## 5. Registry summary

| Registry | Stores | Key behavior |
|----------|--------|--------------|
| `RecipeUnitRegistry` | `RecipeUnit` | add/remove, `valid_ids()`, `get()`. Remove guarded by optional ingredient list. |
| `InventoryUnitRegistry` | `InventoryUnit` | add/remove (cycle check on base_unit_id chain), `valid_ids()`, `get()`. Remove guarded by optional inventory items. |
| `CategoryRecipeRegistry` | `CategoryRecipe` | add/update/remove, `valid_ids()`, `get()`. Remove guarded by optional recipes. |
| `FamilyInventoryRegistry` | `FamilyInventory` | add/remove, `valid_ids()`, `get()`. Remove guarded by optional inventory items. |
| `InventoryItemRegistry` | `InventoryItem` | add/remove/get/get_by_name/list_all/valid_ids; enforces unique item name (case-insensitive). |
| `UserRegistry` | `User` | add/update/delete require `current_user.role == "admin"`; `get()`. |

Roles for `User`: `ALLOWED_USER_ROLES = {"admin", "mesero", "cocinero", "inventario"}`.

---

## 6. Key workflows & invariants (how the model is intended to be used)

### Inventory units: `is_standard` and purchase-to-stock factor

`InventoryUnit.is_standard` distinguishes:

- **Standard units** (`kg`, `g`, `L`, `ml`, `pza`): conversions are expressed via the unit chain (`base_unit_id` + `factor_to_base`) and are global.
- **Non-standard / contextual units** (`caja`, `bolsa`, `costal`, `lata`, etc.): used as purchase units only. Conversion to the stock unit is stored directly on `InventoryItem.purchase_to_stock_factor`.

The **two-unit model** on `InventoryItem` (introduced in Task 11):

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `stock_unit_id` | `int` | required | Always a standard unit — used for deduction and cross-recipe comparison |
| `purchase_unit_id` | `int` | required | How the operator buys it — can be non-standard |
| `purchase_to_stock_factor` | `float` | `1.0` | 1 purchase unit = X stock units |

When `purchase_unit == stock_unit`, the factor is always `1.0`. When they differ, the Estructura section collects the factor from the operator. `InventoryUnitEquivalenceRegistry` was removed — this field replaces it for all deduction purposes.

### Recipe → Ingredient → (optional) InventoryItem creation

`Recipe.add_ingredient(...)` can be used in two ways:

- **Ingredient-only:** add the ingredient to the recipe (no inventory item created).
- **Ingredient + inventory creation:** if `category_id` is provided, `add_ingredient` returns a new `InventoryItem(id=0, ...)` for the caller to persist/add to `InventoryItemRegistry`.

```mermaid
flowchart TB
    subgraph recipe_flow["Recipe ingredient flow"]
        UI[User adds Ingredient to Recipe]
        AddIng["Recipe.add_ingredient (optional InventoryItem creation)"]
        UI --> AddIng
    end

    subgraph outcomes["Outcomes"]
        NoNewItem["Returns None (existing ingredient updated or no item requested)"]
        NewItem["Returns InventoryItem(id=0, ...) for caller to persist"]
    end

    subgraph persistence["Persistence / registries"]
        Persist["Persist InventoryItem: assign item_id"]
        AddToReg["InventoryItemRegistry.add item"]
    end

    AddIng -->|existing ingredient name| NoNewItem
    AddIng -->|category_id provided| NewItem
    NewItem --> Persist --> AddToReg
```

![Key workflows](images/data-model-04-keyworkflows.png)

### Registry invariants (high-signal)

- `InventoryUnitRegistry.add(...)`:
  - if `base_unit_id` is set, it must already exist in the registry
  - cycles in the `base_unit_id` chain are rejected
- `InventoryItemRegistry.add(...)`:
  - enforces unique item name (case-insensitive)
  - `get_by_name(...)` supports name-based resolution in early onboarding flows

---

## 7. Task 10 additions (Alineamiento)

### Standard recipe unit constant

```python
STANDARD_RECIPE_UNIT_SYMBOLS: frozenset[str] = frozenset({"g", "kg", "ml", "L", "pza"})

def is_standard_recipe_unit(symbol: str) -> bool:
    """Return True if the symbol is a standard recipe unit (no equivalent needed)."""
    return symbol in STANDARD_RECIPE_UNIT_SYMBOLS
```

Standard units need no per-ingredient mass equivalent. Any other symbol (taza, cda, cdta,
oz, manojo, pizca, etc.) is non-standard and requires an equivalent proposed per-ingredient
by `AlignmentAgent`.

### RecipeUnitConversionEntry.source

`RecipeUnitConversionEntry` (in `core/operations/normalization.py`) received a new field:

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `source` | `str` | `"agent_estimated"` | `"operator"` / `"agent_confirmed"` / `"agent_estimated"` |

Source values:
- `"operator"` — operator explicitly provided or corrected the equivalent
- `"agent_confirmed"` — operator accepted the agent's culinary estimate as-is
- `"agent_estimated"` — operator skipped; agent estimate stored without confirmation

---

## Related docs

- [`architecture-normalization.md`](architecture-normalization.md)
- [`architecture-taxonomy.md`](architecture-taxonomy.md)
- [`architecture-data-model-utils.md`](architecture-data-model-utils.md)
- [`architecture-readiness-kpis.md`](architecture-readiness-kpis.md)
