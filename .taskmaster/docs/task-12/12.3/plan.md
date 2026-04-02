# Subtask 12.3 — Mi Restaurante tab + Recetas tab + Inventario tab

## Goal

Add three pure Markdown-builder functions to `gradio_app/sections/manual_operativo.py`
so that subtask 12.4 can assemble all four tab contents and wire them into the Gradio
two-state UI.

- **12.2 delivered:** `_build_resumen_md` and `_build_manual_context` — complete.
- **12.4 needs from 12.3:** three builder functions with stable signatures, ready to be
  called inside `generate_fn`.

---

## Files to Modify / Create

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/sections/manual_operativo.py` | Modify | Add three private helper functions after `_build_resumen_md` |

No other files touched.

---

## Dependencies

- Subtask 12.1 done: `_build_manual_context`, `ManualOperativoAgent`, re-exports in place.
- Subtask 12.2 done: `_build_resumen_md` implemented (pattern and constants established).
- `core.domain.data_model.DEFAULT_INVENTORY_CATEGORIES` — `InventoryCategory(1, "Perecedero")`,
  `InventoryCategory(2, "No perecedero")`.
- `validate_recipe_for_deduction` exists in `core/domain/data_model_utils.py` and is
  re-exported via `core/__init__.py`. Returns `list[str]` of issues; empty = deduction-ready.
- No new packages required.

---

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| Pure functions, no DataLake access | Follows `_build_resumen_md` pattern; all data loaded once in `generate_fn` |
| Mi Restaurante shows entity counts, not lists | Entity lists belong to Recetas and Inventario tabs; Mi Restaurante is a profile summary |
| Recetas badge derived from `validate_recipe_for_deduction` | Reuses existing utility; no new logic |
| Inventario grouped by `category_id` (1=Perecedero, 2=No perecedero) | `DEFAULT_INVENTORY_CATEGORIES` defines these fixed IDs |
| Markdown only — no Gradio components | Tab content is plain string for `gr.Markdown`; same as `_build_resumen_md` |

---

## Implementation steps

### 1. Add `validate_recipe_for_deduction` import

At the top of `manual_operativo.py`, add to the existing `core` import block:

```python
from core.domain.data_model_utils import validate_recipe_for_deduction
```

Check first — it may not yet be imported.

### 2. Add `_build_mi_restaurante_md`

Insert after `_build_resumen_md`. Signature:

```python
def _build_mi_restaurante_md(
    restaurant,
    user_data: dict,
    classification_data: dict,
    *,
    recipe_units: list,
    inventory_units: list,
    categories: list,
    families: list,
    recipes: list,
    items: list,
) -> str:
```

Content:
- `## [restaurant.name]`
- `Tipo: [restaurant.restaurant_type_id]  |  Operador: [user_data.get("name", "—")]`
- `Nivel de estandarización: [classification_data.get("standardization_level", "N/D")]`
- Optional description line if `classification_data.get("restaurant_description")` is non-empty
- Blank line, then `**Configuración:**` section:
  ```
  - Unidades de receta: N
  - Unidades de inventario: N
  - Categorías de receta: N
  - Familias de inventario: N
  - Artículos de inventario: N
  - Recetas: N
  ```

### 3. Add `_build_recetas_md`

Insert after `_build_mi_restaurante_md`. Signature:

```python
def _build_recetas_md(
    recipes: list,
    recipe_unit_registry: RecipeUnitRegistry,
    item_registry: InventoryItemRegistry,
    category_registry: CategoryRecipeRegistry,
    inventory_unit_registry: InventoryUnitRegistry,
    conversion_table,
    family_registry: FamilyInventoryRegistry,
) -> str:
```

Logic:
- If `recipes` is empty: return `"_(Sin recetas capturadas)_"`.
- Per recipe:
  - Call `validate_recipe_for_deduction(recipe, item_registry, inventory_unit_registry, conversion_table, family_registry)`.
  - Badge: `"✓ Lista para deducción"` if issues list is empty, else `"⚠ Incompleta"`.
  - `### [recipe.name]  —  [badge]`
  - `Categoría: [cat_name]` (resolve via `category_registry.get(recipe.category_id)`, fall back to `"—"`)
  - `**Ingredientes:**` then per ingredient:
    - Resolve unit symbol: `recipe_unit_registry.get(ing.unit_id)` → `.symbol`, fallback `str(ing.unit_id)`
    - Link status: `ing.inventory_item_id` set **or** `item_registry.get_by_name(ing.name)` found → `"✓ vinculado"`, else `"⚠ sin vincular"`
    - Line: `  - [ing.name]: [ing.quantity] [unit_sym]  [[link_status]]`
  - Blank line between recipes

### 4. Add `_build_inventario_md`

Insert after `_build_recetas_md`. Signature:

```python
def _build_inventario_md(
    items: list,
    inventory_unit_registry: InventoryUnitRegistry,
    family_registry: FamilyInventoryRegistry,
) -> str:
```

Logic:
- Split items: `perecederos = [i for i in items if i.category_id == 1]`,
  `no_perecederos = [i for i in items if i.category_id == 2]`.
- For each group, render:
  ```
  ## Perecederos (N artículos)
  - [name]   compra: [pu_sym]   stock: [su_sym]   factor: [X]   familia: [fam_name]
  ```
  - Resolve `pu_sym`: `inventory_unit_registry.get(item.purchase_unit_id)` → `.symbol`, fallback `str(item.purchase_unit_id)`
  - Resolve `su_sym`: same pattern for `item.stock_unit_id`
  - Resolve `fam_name`: `family_registry.get(item.family_id).name if item.family_id else "sin familia"`
  - If group is empty: `_(sin artículos)_`
- If `items` is empty: return `"_(Sin artículos de inventario)_"`.

---

## Integration note for subtask 12.4

`generate_fn` in 12.4 will need to:
1. Load all DataLake entities (recipes, items, units, etc.) — same pattern as `_build_manual_context`.
2. Build in-memory registries.
3. Call each of the four builders with the loaded registries and lists.
4. Pass the results to `gr.Markdown` components in the corresponding tabs.

**Do not** refactor `_build_manual_context` to return registries. Instead, `generate_fn`
rebuilds them independently — this keeps `_build_manual_context` focused on producing the
agent's context string and avoids coupling the two paths.

---

## Out of scope

- Gradio wiring (12.4)
- "Regenerar" button (12.4)
- Agent sidebar (12.4)
- Unit tests (12.5)
- Architecture doc (12.6)
- No changes to `core/`, `tests/`, or any other file

---

## Test coverage

No new unit tests in this subtask. Subtask 12.5 should add:
- `test_build_recetas_md_empty` — empty recipes list returns non-empty string without crash
- `test_build_recetas_md_linked_ingredient` — linked ingredient shows `✓ vinculado`
- `test_build_inventario_md_groups_by_category` — items split correctly into Perecedero / No Perecedero

---

## Risks and open questions

- `validate_recipe_for_deduction` import must be added to `manual_operativo.py` — verify it
  is not already present before adding (check existing import block).
- `validate_recipe_for_deduction` signature:
  `(recipe, item_registry, unit_registry: InventoryUnitRegistry, conversion_table: RecipeUnitConversionRegistry, family_registry: FamilyInventoryRegistry) -> list[str]`.
  The `conversion_table` parameter must be a `RecipeUnitConversionRegistry` instance — 12.4's
  `generate_fn` must build it from DataLake before calling `_build_recetas_md`.

---

## Deliverable checklist

`gradio_app/sections/manual_operativo.py`:
- [ ] `validate_recipe_for_deduction` imported at module level
- [ ] `_build_mi_restaurante_md(restaurant, user_data, classification_data, *, recipe_units, inventory_units, categories, families, recipes, items) -> str` added
- [ ] Mi Restaurante shows: name, type, operator, standardization level, optional description, 6 entity counts
- [ ] `_build_recetas_md(recipes, recipe_unit_registry, item_registry, category_registry, inventory_unit_registry, conversion_table, family_registry) -> str` added
- [ ] Recetas badge uses `validate_recipe_for_deduction` — empty issues → `✓ Lista`, non-empty → `⚠ Incompleta`
- [ ] Each ingredient shows linked/unlinked status
- [ ] Empty recipes list returns placeholder string without crash
- [ ] `_build_inventario_md(items, inventory_unit_registry, family_registry) -> str` added
- [ ] Inventario grouped by `category_id` (1=Perecedero, 2=No perecedero)
- [ ] Each item shows: name, purchase unit symbol, stock unit symbol, factor, family name
- [ ] Empty groups render `_(sin artículos)_`, not a crash
- [ ] Empty items list returns placeholder string without crash
