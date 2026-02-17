# Architecture: `core/normalization.py`

Unit conversion and normalization for inventory deduction (subtask 2.3). Provides: `to_base_quantity` / `from_base_quantity` for InventoryUnit chains; family base unit resolution; recipe-unit conversion table application; normalized recipe (list per recipe for deduction on order).

---

## 1. High-level flow (layers)

```mermaid
flowchart TB
    subgraph layer1["Unit chain conversion (2.3.1–2.3.3)"]
        to_base[to_base_quantity]
        from_base[from_base_quantity]
        to_base_id[to_base_quantity_by_id]
        from_base_id[from_base_quantity_by_id]
        to_base --> from_base
        to_base_id --> to_base
        from_base_id --> from_base
    end

    subgraph layer2["Same-family conversion (2.3.5)"]
        root[_root_base_unit_id]
        convert[convert_quantity]
        root --> convert
        to_base_id --> convert
        from_base_id --> convert
    end

    subgraph layer3["Family base (2.3.6)"]
        family_base[get_family_base_unit_id]
    end

    subgraph layer4["Recipe-unit table (2.3.7)"]
        key[RecipeUnitConversionKey]
        entry[RecipeUnitConversionEntry]
        conv_reg[RecipeUnitConversionRegistry]
        norm_ru[normalize_recipe_unit_quantity]
        key --> conv_reg
        entry --> conv_reg
        conv_reg --> norm_ru
    end

    subgraph layer5["Recipe to deduction (2.3.8)"]
        DeductionLine["DeductionLine (item_id, qty, base_unit_id)"]
        norm_recipe[normalize_recipe_for_deduction]
        norm_ru --> norm_recipe
        family_base --> norm_recipe
        to_base_id --> norm_recipe
        from_base_id --> norm_recipe
        root --> norm_recipe
        norm_recipe --> DeductionLine
    end

    layer1 --> layer2
    layer2 --> layer5
    layer3 --> layer5
    layer4 --> layer5
```

![High-level flow (layers)](images/normalization-01-layers.png)

---

## 2. Function dependency graph

```mermaid
flowchart LR
    subgraph internal["Internal helpers"]
        _factor[_factor_product_to_base]
        _root[_root_base_unit_id]
    end

    subgraph public_api["Public API"]
        to_base_quantity
        from_base_quantity
        to_base_quantity_by_id
        from_base_quantity_by_id
        convert_quantity
        get_family_base_unit_id
        normalize_recipe_unit_quantity
        normalize_recipe_for_deduction
    end

    from_base_quantity --> _factor
    to_base_quantity_by_id --> to_base_quantity
    from_base_quantity_by_id --> from_base_quantity
    convert_quantity --> _root
    convert_quantity --> to_base_quantity_by_id
    convert_quantity --> from_base_quantity_by_id
    normalize_recipe_for_deduction --> normalize_recipe_unit_quantity
    normalize_recipe_for_deduction --> get_family_base_unit_id
    normalize_recipe_for_deduction --> to_base_quantity_by_id
    normalize_recipe_for_deduction --> from_base_quantity_by_id
    normalize_recipe_for_deduction --> _root
```

![Function dependency graph](images/normalization-02-function-deps.png)

---

## 3. Recipe-unit conversion types (2.3.7)

```mermaid
classDiagram
    class RecipeUnitConversionKey {
        <<frozen dataclass>>
        +int recipe_unit_id
        +int? family_id
        +int? inventory_item_id
    }
    class RecipeUnitConversionEntry {
        +float quantity
        +int base_unit_id
    }
    class RecipeUnitConversionRegistry {
        -dict key~Entry _entries
        +add(recipe_unit_id, quantity, base_unit_id, family_id?, inventory_item_id?)
        +get(recipe_unit_id, family_id?, inventory_item_id?) Optional~Entry~
    }

    RecipeUnitConversionRegistry ..> RecipeUnitConversionEntry : stores
    RecipeUnitConversionRegistry ..> RecipeUnitConversionKey : key as tuple
```

![Recipe-unit conversion types](images/normalization-03-conversion-types.png)

---

## 4. Recipe to deduction flow (2.3.8)

```mermaid
flowchart LR
    Recipe[Recipe] --> ForEach[For each ingredient]
    ForEach --> Resolve[resolve_ingredient_to_inventory]
    Resolve --> inv_family[inventory_item_id, family_id]
    inv_family --> NormRU[normalize_recipe_unit_quantity]
    NormRU --> Table{Match in conversion table?}
    Table -->|Yes| Append1[Append DeductionLine]
    Table -->|No| FamilyBase[get_family_base_unit_id]
    FamilyBase --> SameRoot{Same root base?}
    SameRoot -->|Yes| ToBase[to_base_quantity_by_id]
    ToBase --> FromBase[from_base_quantity_by_id]
    FromBase --> Append2[Append DeductionLine]
    SameRoot -->|No| Skip[Skip ingredient]
    Append1 --> Result[list of DeductionLine]
    Append2 --> Result
```

![Recipe to deduction flow](images/normalization-04-recipe-to-deduction.png)

### Recipe unit vs inventory unit (same vs different dimension)

Deduction is always in the **inventory item's unit**. How we get there depends on whether the recipe unit and item unit are in the same dimension:

- **Same dimension** (e.g. recipe "2 cajas", item in kg): The fallback path converts via the unit chain and optional item-specific equivalence (e.g. 1 caja = 5 kg). No conversion table entry is required.
- **Different dimension** (e.g. recipe "1 tortilla" in pza, item stored in kg): The unit chain cannot convert pza to kg (different roots). A **recipe-unit conversion table** entry is required (e.g. "1 pza = 0.05 kg" for that item). Without it, the ingredient is skipped and no deduction line is produced.

---

## 5. External dependencies

Imports from `core.data_model`: `FamilyInventoryRegistry`, `Ingredient`, `InventoryUnit`, `InventoryUnitRegistry`, `Recipe`.

```mermaid
flowchart TB
    subgraph external["From core.data_model"]
        Recipe
        Ingredient
        InventoryUnit
        InventoryUnitRegistry
        FamilyInventoryRegistry
    end

    subgraph normalization_module["core.normalization"]
        to_base_quantity
        from_base_quantity
        convert_quantity
        get_family_base_unit_id
        RecipeUnitConversionRegistry
        normalize_recipe_unit_quantity
        normalize_recipe_for_deduction
    end

    InventoryUnit --> to_base_quantity
    InventoryUnitRegistry --> to_base_quantity
    InventoryUnitRegistry --> from_base_quantity
    InventoryUnitRegistry --> convert_quantity
    FamilyInventoryRegistry --> get_family_base_unit_id
    InventoryUnitRegistry --> get_family_base_unit_id
    Recipe --> normalize_recipe_for_deduction
    Ingredient --> normalize_recipe_for_deduction
    resolve["resolve_ingredient_to_inventory (callable)"] --> normalize_recipe_for_deduction
```

![External dependencies](images/normalization-05-external-deps.png)

---

## 6. Section summary

| Section | Responsibility |
|--------|----------------|
| **2.3.1–2.3.3** | Convert quantity along an `InventoryUnit` chain: `to_base_quantity` / `from_base_quantity` (and by-id wrappers). |
| **2.3.5** | `convert_quantity`: convert between two units that share the same root base (`_root_base_unit_id`). |
| **2.3.6** | `get_family_base_unit_id`: family’s deduction base unit from `FamilyInventoryRegistry` + `InventoryUnitRegistry`. |
| **2.3.7** | Recipe-unit conversion: `RecipeUnitConversionKey`, `RecipeUnitConversionEntry`, `RecipeUnitConversionRegistry`, and `normalize_recipe_unit_quantity` (recipe units → normalized quantity + base_unit_id). |
| **2.3.8** | `normalize_recipe_for_deduction`: for each ingredient, resolve to inventory + family, normalize (table or family-base fallback), output `list[DeductionLine]` (inventory_item_id, normalized_quantity, base_unit_id). |

**Type alias:** `DeductionLine = tuple[int, float, int]` — (inventory_item_id, normalized_quantity, base_unit_id).
