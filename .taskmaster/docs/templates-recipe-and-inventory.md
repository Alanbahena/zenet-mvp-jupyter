# Templates: recipe categories, inventory families, and units by restaurant type

## Summary

**Yes.** The product should provide **templates** so the user can select options easily according to their **restaurant type**:

- **Recipe categories** and **inventory families** (as in the PRD).
- **Recipe units** and **inventory units** as well, so the user gets standard units (e.g. g, kg, L, pza, caja) without defining them from scratch.

This doc makes the design explicit.

---

## Purpose

- **Recipe category template**: predefined set of `CategoryRecipe`-like entries (e.g. desayuno, comida, cena, bebidas, entradas, postres) so the user doesn’t start from zero.
- **Inventory family template**: predefined set of `FamilyInventory`-like entries (e.g. Lácteos, Granos, Carnes, Verduras, Bebidas) so inventory is structured consistently.
- **Recipe unit template**: predefined set of `RecipeUnit` entries (e.g. g, kg, ml, L, pza, cucharada, taza) so recipes and ingredients use consistent units from the start.
- **Inventory unit template**: predefined set of `InventoryUnit` entries (e.g. kg, L, caja, bolsa, pza, litro) so inventory items share the same units and normalization is easier.
- **Restaurant type** (from Classification) drives which template(s) are suggested; the user selects one (or customizes) in Configuration.

---

## Flow

1. **Classification agent**: Classify restaurant type (e.g. café, restaurante completo, bar, cocina rápida).
2. **Template suggestion**: According to restaurant type, suggest one or more templates (recipe categories, inventory families, **recipe units**, **inventory units**). Templates are editable presets.
3. **Configuration agent**: User selects a template (or “start from scratch”). The agent guides setup of:
   - recipe categories and inventory families (pre-filled from template);
   - **recipe units and inventory units** (pre-filled from template so the user can select options easily).
   User can add, remove, or rename any of these.
4. Result: initial `CategoryRecipe`, `FamilyInventory`, **`RecipeUnit`**, and **`InventoryUnit`** instances for that restaurant.

---

## What to implement (when doing Classification / Configuration)

- **Template definitions**: Data or config (e.g. JSON/YAML) keyed by restaurant type, each containing:
  - **Recipe category template**: list of category names (and optional descriptions), e.g. for “restaurante completo”: desayuno, comida, cena, bebidas, entradas, postres, especiales.
  - **Inventory family template**: list of family names (and optional descriptions), e.g. Lácteos, Granos, Carnes, Verduras, Bebidas, Limpieza.
  - **Recipe unit template**: list of units with `name` and `symbol` (e.g. gramo/g, kilogramo/kg, mililitro/ml, litro/L, pieza/pza, cucharada/cda, taza/taza). Optionally keyed by region (metric vs imperial) or restaurant type.
  - **Inventory unit template**: list of units with `name` and `symbol` (e.g. kg, L, ml, pza, caja, bolsa, bote). Same idea: user selects a template and gets standard options without typing each unit.
- **Classification agent**: Uses restaurant type (and optionally region/locale) to suggest which template(s) to use.
- **Configuration agent**: Loads the selected template and creates/edits `CategoryRecipe`, `FamilyInventory`, **`RecipeUnit`**, and **`InventoryUnit`** entities (user can edit before confirming).

---

## Relation to data model (subtask 2.1)

Templates do **not** change the entity classes. They are **preset data** used to create instances of those entities. So:

- 2.1: define `CategoryRecipe`, `FamilyInventory`, `RecipeUnit`, and `InventoryUnit` in `core/data_model.py`.
- Later (Classification/Configuration): add template definitions (categories, families, **recipe units**, **inventory units**) and agent logic to suggest/apply them by restaurant type so the user can select options easily.
