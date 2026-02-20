# Serialization Contract Specification

This document defines the **persistence scope** and **JSON-serializable dict shape** for all entities in the Zenet MVP data model. This is the single source of truth for subtasks 3.2 (JsonStorage), 3.3 (serialization), and 3.4 (SQLite schema).

**Version:** 1.0  
**Date:** Created for Task 3.1

---

## 1. Persistence scope and principles

### 1.1 Persisted entity types

The following entity types are persisted:

1. **Restaurant**
2. **Recipe**
3. **Ingredient** (embedded in Recipe; not a top-level entity)
4. **InventoryItem**
5. **RecipeUnit**
6. **InventoryUnit**
7. **CategoryRecipe**
8. **FamilyInventory**
9. **User**
10. **InventoryUnitEquivalence**

### 1.2 NOT persisted (out of scope)

- **RestaurantType** — Fixed constants in code (`DEFAULT_RESTAURANT_TYPES`); only IDs are stored
- **InventoryCategory** — Fixed constants in code (`DEFAULT_INVENTORY_CATEGORIES`); only IDs are stored
- **Templates** — Category/family/unit templates are code constants; not persisted
- **Registries** — Registry state is NOT persisted; registries are rebuilt from loaded entities (Option A)

### 1.3 Entity type naming convention

Each entity type uses a stable string identifier for storage:

| Entity Type | String Identifier |
|-------------|-------------------|
| Restaurant | `"restaurant"` |
| Recipe | `"recipe"` |
| InventoryItem | `"inventory_item"` |
| RecipeUnit | `"recipe_unit"` |
| InventoryUnit | `"inventory_unit"` |
| CategoryRecipe | `"category_recipe"` |
| FamilyInventory | `"family_inventory"` |
| User | `"user"` |
| InventoryUnitEquivalence | `"inventory_unit_equivalence"` |

---

## 2. Core persistence rules

### 2.1 ID generation strategy

- **Type:** IDs are **integers** (not UUIDs or strings)
- **Assignment:** New entities use `id=0`; the persistence layer assigns a real ID on first save
- **Uniqueness:** IDs are unique per entity type (e.g. Recipe id=1 and InventoryItem id=1 are different entities)

### 2.2 Relationship representation

- **All relationships are stored by ID only** (foreign keys)
- **No nested full objects** in the canonical dict
- Examples: `recipe_id`, `unit_id`, `category_id`, `family_id`, `inventory_item_id`

### 2.3 Registry reconstruction

- **Registries are NOT persisted**
- On load: Load all entities of a type → rebuild the registry in memory
- Example: Load all Recipe entities → call `RecipeRegistry.add()` for each

### 2.4 JSON null convention

For optional (nullable) fields:

- **Always write the key** with `null` if the value is `None` (explicit schema)
- Do not omit keys for optional fields
- Example: `{"address": null}` not `{}`

### 2.5 Validation on load

- **Lenient:** `from_dict()` does NOT validate FK integrity
- Caller is responsible for ensuring referenced entities are loaded first (or FKs are valid)
- No runtime FK validation in serialization layer

---

## 3. Entity dict shapes

For each entity type, the following sections define:
- **Fields:** Name, type, and whether required or optional
- **Dict example:** A concrete JSON example

### 3.1 Restaurant

**Entity type string:** `"restaurant"`

| Field | Type | Required? | Notes |
|-------|------|-----------|-------|
| id | int | Yes | |
| name | str | Yes | |
| address | str \| None | No | Nullable |
| restaurant_type_id | int \| None | No | FK to RestaurantType (fixed constant); nullable |
| notes | str \| None | No | Nullable |

**Dict example:**

```json
{
  "id": 1,
  "name": "La Cocina",
  "address": "Calle Principal 123",
  "restaurant_type_id": 1,
  "notes": "Restaurant principal"
}
```

**With nulls:**

```json
{
  "id": 2,
  "name": "El Café",
  "address": null,
  "restaurant_type_id": null,
  "notes": null
}
```

---

### 3.2 User

**Entity type string:** `"user"`

| Field | Type | Required? | Notes |
|-------|------|-----------|-------|
| id | int | Yes | |
| name | str | Yes | |
| email | str | Yes | |
| role | str | Yes | One of: "admin", "mesero", "cocinero", "inventario" |

**Dict example:**

```json
{
  "id": 1,
  "name": "Juan Pérez",
  "email": "juan@example.com",
  "role": "admin"
}
```

---

### 3.3 RecipeUnit

**Entity type string:** `"recipe_unit"`

| Field | Type | Required? | Notes |
|-------|------|-----------|-------|
| id | int | Yes | |
| name | str | Yes | |
| symbol | str | Yes | |
| description | str \| None | No | Nullable |

**Dict example:**

```json
{
  "id": 1,
  "name": "gramo",
  "symbol": "g",
  "description": "Unidad de masa"
}
```

---

### 3.4 InventoryUnit

**Entity type string:** `"inventory_unit"`

| Field | Type | Required? | Notes |
|-------|------|-----------|-------|
| id | int | Yes | |
| name | str | Yes | |
| symbol | str | Yes | |
| description | str \| None | No | Nullable |
| base_unit_id | int \| None | No | FK to InventoryUnit (for conversions); nullable |
| factor_to_base | float | Yes | Default: 1.0 |
| is_standard | bool | Yes | Default: true |

**Dict example (standard unit):**

```json
{
  "id": 1,
  "name": "kilogramo",
  "symbol": "kg",
  "description": "Unidad de masa",
  "base_unit_id": null,
  "factor_to_base": 1.0,
  "is_standard": true
}
```

**Dict example (non-standard unit with conversion):**

```json
{
  "id": 10,
  "name": "caja",
  "symbol": "caja",
  "description": "Caja estándar",
  "base_unit_id": 1,
  "factor_to_base": 10.0,
  "is_standard": false
}
```

---

### 3.5 CategoryRecipe

**Entity type string:** `"category_recipe"`

| Field | Type | Required? | Notes |
|-------|------|-----------|-------|
| id | int | Yes | |
| name | str | Yes | |
| description | str \| None | No | Nullable |

**Dict example:**

```json
{
  "id": 1,
  "name": "Entradas",
  "description": "Platillos de entrada"
}
```

---

### 3.6 FamilyInventory

**Entity type string:** `"family_inventory"`

| Field | Type | Required? | Notes |
|-------|------|-----------|-------|
| id | int | Yes | |
| name | str | Yes | |
| description | str \| None | No | Nullable |
| base_unit_id | int \| None | No | FK to InventoryUnit; nullable |

**Dict example:**

```json
{
  "id": 1,
  "name": "Lácteos",
  "description": "Productos lácteos",
  "base_unit_id": 1
}
```

---

### 3.7 InventoryItem

**Entity type string:** `"inventory_item"`

**Note:** `unit_id` always references **InventoryUnit** (never InventoryUnitEquivalence). For the relationship between InventoryItem, InventoryUnit, and InventoryUnitEquivalence, see [../units-and-equivalences-relationship.md](../units-and-equivalences-relationship.md).

| Field | Type | Required? | Notes |
|-------|------|-----------|-------|
| id | int | Yes | |
| name | str | Yes | |
| unit_id | int | Yes | FK to InventoryUnit (standard or non-standard) |
| category_id | int | Yes | FK to InventoryCategory (fixed constant) |
| family_id | int \| None | No | FK to FamilyInventory; nullable |
| description | str \| None | No | Nullable |

**Dict example:**

```json
{
  "id": 1,
  "name": "Leche entera",
  "unit_id": 2,
  "category_id": 1,
  "family_id": 1,
  "description": "Leche fresca 1L"
}
```

---

### 3.8 Recipe

**Entity type string:** `"recipe"`

| Field | Type | Required? | Notes |
|-------|------|-----------|-------|
| id | int | Yes | |
| name | str | Yes | |
| description | str \| None | No | Nullable; user can add later |
| steps | list[str] \| None | No | Nullable; list of instruction strings; user can add later |
| category_id | int | Yes | FK to CategoryRecipe |
| ingredients | list[dict] | Yes | List of ingredient dicts (see below) |

**Ingredient dict shape (embedded in Recipe.ingredients):**

Each element in the `ingredients` list has this shape:

| Field | Type | Required? | Notes |
|-------|------|-----------|-------|
| name | str | Yes | Ingredient name |
| quantity | float | Yes | Amount |
| unit_id | int | Yes | FK to RecipeUnit |
| inventory_item_id | int \| None | No | FK to InventoryItem; nullable |

**Dict example (with description and steps):**

```json
{
  "id": 1,
  "name": "Tacos al pastor",
  "description": "Tacos tradicionales de pastor",
  "steps": [
    "Marinar la carne",
    "Cortar en trozos",
    "Calentar tortillas",
    "Servir con cebolla y cilantro"
  ],
  "category_id": 2,
  "ingredients": [
    {
      "name": "Carne de cerdo",
      "quantity": 500.0,
      "unit_id": 1,
      "inventory_item_id": 5
    },
    {
      "name": "Tortillas",
      "quantity": 12.0,
      "unit_id": 3,
      "inventory_item_id": 10
    },
    {
      "name": "Cilantro",
      "quantity": 50.0,
      "unit_id": 1,
      "inventory_item_id": null
    }
  ]
}
```

**Dict example (minimal — description and steps optional):**

```json
{
  "id": 2,
  "name": "Enchiladas",
  "description": null,
  "steps": null,
  "category_id": 2,
  "ingredients": []
}
```

**Important notes about Recipe.ingredients:**

- **Ingredient is NOT a top-level entity**; ingredients are embedded in Recipe as a list
- Each ingredient dict is inline (not persisted separately)
- No separate `"ingredient"` entity type or files

---

### 3.9 InventoryUnitEquivalence

**Entity type string:** `"inventory_unit_equivalence"`

**Note:** This entity provides per-item conversion when an InventoryItem uses a non-standard unit. See [../units-and-equivalences-relationship.md](../units-and-equivalences-relationship.md) for how it relates to InventoryItem and InventoryUnit.

| Field | Type | Required? | Notes |
|-------|------|-----------|-------|
| unit_id | int | Yes | FK to InventoryUnit |
| inventory_item_id | int | Yes | FK to InventoryItem |
| base_unit_id | int | Yes | FK to InventoryUnit (base unit) |
| factor_to_base | float | Yes | Conversion factor |

**Dict example:**

```json
{
  "unit_id": 10,
  "inventory_item_id": 15,
  "base_unit_id": 1,
  "factor_to_base": 2.5
}
```

**Interpretation:** For inventory item 15, 1 unit of unit_id 10 = 2.5 units of base_unit_id 1.

**Note:** This entity has no single `id` field; the composite key is `(unit_id, inventory_item_id)`.

---

## 4. Summary table: all entity types

| Entity Type | Entity String | Top-level? | Has ID? | Key Fields |
|-------------|---------------|------------|---------|------------|
| Restaurant | `restaurant` | Yes | Yes | id, name |
| User | `user` | Yes | Yes | id, name, email, role |
| RecipeUnit | `recipe_unit` | Yes | Yes | id, name, symbol |
| InventoryUnit | `inventory_unit` | Yes | Yes | id, name, symbol |
| CategoryRecipe | `category_recipe` | Yes | Yes | id, name |
| FamilyInventory | `family_inventory` | Yes | Yes | id, name |
| InventoryItem | `inventory_item` | Yes | Yes | id, name, unit_id, category_id |
| Recipe | `recipe` | Yes | Yes | id, name, ingredients (list) |
| Ingredient | (embedded) | No | No | Inline in Recipe.ingredients |
| InventoryUnitEquivalence | `inventory_unit_equivalence` | Yes | No | (unit_id, inventory_item_id) composite key |

---

## 5. Implementation notes for 3.2–3.7

### For 3.2 (JsonStorage)

- File naming: `{entity_type}_{entity_id}.json` (e.g. `recipe_42.json`)
- For InventoryUnitEquivalence (no single id): use composite key in filename, e.g. `inventory_unit_equivalence_{unit_id}_{inventory_item_id}.json`
- Write keys with `null` for optional fields (never omit keys)

### For 3.3 (Serialization)

- Implement `to_dict` and `from_dict` for each entity type
- `recipe_to_dict`: serialize `ingredients` as list of dicts (inline)
- `recipe_from_dict`: rebuild list of Ingredient dataclass instances from dicts
- Handle optional fields: `from_dict` uses `None` as default if key missing or null

### For 3.4 (SQLite schema)

- One table per entity type (except Ingredient, which is JSON column or normalized)
- Column names match dict keys
- FKs declared where appropriate (e.g. `recipe.category_id` → `category_recipe.id`)
- For InventoryUnitEquivalence: composite PRIMARY KEY `(unit_id, inventory_item_id)`
- For Recipe.ingredients: either JSON column or separate `recipe_ingredient` table (decide in 3.4)

### For 3.6 (DataLake)

- Use entity type strings as the `entity_type` argument
- For InventoryUnitEquivalence: `entity_id` can be `"{unit_id}_{inventory_item_id}"` composite string

---

## 6. Decisions log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ID type | Integer | Simple, auto-increment friendly |
| ID assignment | Persistence layer assigns on save | New entities use id=0 |
| Relationships | Store by ID only | No nested objects; simpler serialization |
| Registry persistence | Not persisted; rebuild from entities | Simpler for MVP |
| JSON null convention | Always write key with null | Explicit schema; easier debugging |
| Validation on load | Lenient (no FK validation) | Simpler; validate at higher level if needed |
| InventoryUnitEquivalence | In scope (persisted) | Required for non-standard units |
| Templates | Not persisted | Code constants; user data derived from templates is persisted |
| Ingredient | Embedded in Recipe | Not a top-level entity; inline list |

---

**End of serialization contract specification.**
